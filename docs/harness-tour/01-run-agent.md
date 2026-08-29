# 01 — `tools/run-agent`: the agent harness (deterministic path)

> **Historical walkthrough — a dated snapshot, not a specification.** The
> autonomous local-HTTP agent path described here was superseded, and the
> commercial-product lane that replaced it is not part of this public release.
> Read this file for the **deterministic** path only; where it and the code
> disagree, the code wins.

> Scope: this section covers the **deterministic** path of the agent harness —
> the path where a coding agent edits *plain source files* and the harness
> snapshots that edit as a submission. That path is fully realised by the
> **`claude-p` Baseline** backend running in a throwaway `/tmp` workspace copy.
> The `aura-*` backends (which drive a live Unreal editor and need a different
> snapshot/restore dance) are the subject of section 05; here they appear only
> where the deterministic code paths fork around them.

---

## 1. Purpose

`tools/run-agent/` is the **agent harness**: it turns *a task spec* into *a
graded run*. Concretely it:

1. extracts the agent-visible prompt from a task `.md` (dropping the answer key);
2. materialises an isolated copy of the substrate UE project that the agent may
   edit;
3. dispatches a coding agent (the `claude -p` CLI for the Baseline) against that
   copy, capturing a full telemetry transcript;
4. **snapshots the diff** the agent produced — i.e. only the files under the
   agent-writable prefixes that it changed or created — as a verifier-shaped
   *submission*;
5. shells out to the deterministic verifier (`tools/verify-single/run_task.py`)
   to grade that submission, and maps the verifier's exit code + report to a
   single harness *verdict* (`PASS` / `FAIL` / `SUBSTRATE-REJECT` /
   `SANDBOX-REJECT` / …).

The harness is the *measurement apparatus around the verifier*. It is also the
only place where the CraftBench products are made comparable. The generalist
backends — Baseline (`claude-p`), `openrouter:` (any non-Anthropic model, no Aura),
and `aura-mcp` — all funnel through the same `claude -p` invocation so that the
only variable is the tool-layer (`adapters/registry.py`). (Aura's authentic
autonomous product was measured separately over a lane that is not part of this release — the
`cb` launcher, §05; the legacy local-HTTP agent backend is
deprecated.) This section is about the Baseline funnel and the scaffolding around
it.

`run.py` is **read-only / user WIP** — do not edit it. Everything documented
here was read, not changed.

---

## 2. Key files and what each does

| File | Role |
| --- | --- |
| `run.py` | **Single-run CLI orchestrator.** Ties the whole flow together: pre-flight → extract prompt → build workspace → dispatch adapter → snapshot → verify → write `result.json`. (READ-ONLY user WIP.) |
| `run_batch.py` | **Batch orchestrator.** Async two-pool scheduler that runs many tasks against ONE product and writes the live disk contract (`status.json` + `events.jsonl` + `result.json`). Product-blind; every UE/Aura/verify seam is injected so the whole module is unit-testable with no editor. |
| `prompt_extract.py` | **The scrub.** Allow-list extraction of the agent-visible H2 sections from a task `.md`; everything else (verifier spec, anti-gaming, reference solution) is dropped. |
| `workspace.py` | **The sandbox copy.** Copies the substrate into `/tmp/run-agent-<id>/`, classifies each file writable vs read-only, hides the answer-key module, and renders `PROMPT.md`. |
| `snapshot.py` | **The diff capture.** Re-walks the post-run workspace and stages only the *changed-or-created* writable files into a submission directory. |
| `substrate_check.py` | **Integrity pre-flight.** Rejects a run if the substrate's *tracked* files have drifted from git `HEAD` (catches UE editor auto-saves before wasting a build). |
| `adapters/base.py` | **The adapter contract** (`AgentAdapter` Protocol + `AgentResult` dataclass) and the **verdict vocabulary** (`verdict_from_verifier`, the graded/non-graded split). |
| `adapters/claude_p.py` | **The Baseline adapter.** Builds the `claude -p` argv, shells it out, parses the stream-json transcript into telemetry, returns an `AgentResult`. |
| `adapters/registry.py` | **Slug → adapter factory.** `make_adapter("claude-p:opus")` → a configured `ClaudePAdapter`. |
| `environment.py` | **The Aura-isolation seam** used by `run_batch.py`. `NullEnvironment` is the deterministic (`claude-p`) world: per-task `/tmp` copy, 5-wide parallel, zero Aura. |
| `run_events.py` | **The live disk-contract writer** (`FileEventSink`, `write_result_json`) used by the batch path. |
| `AGENT_WRITABLE.json` (in the substrate, not here) | The per-substrate manifest of `writable` / `deny` path prefixes that drives both the workspace classification and the verifier's sandbox. |

---

## 3. Data flow (inputs → outputs)

### 3.1 Single run (`run.py`)

Inputs: `--task <task.md>`, `--model <slug>` (e.g. `claude-p:opus`),
`--ue-root <UE_5.8>`. Output: a `runs/<backend>/<run_id>/` directory —
the backend (the slug part before `:`) gets its own folder
(`runs/claude-p/`, `runs/openrouter/`, ...), mirroring
`runs/<backend>/`; an explicit `--run-dir` is used as-is.

```
tasks/<id>.md
   │  (0) substrate-integrity pre-flight        run.py:106-122 → substrate_check.check_substrate_clean
   │      reject (exit 4) if tracked substrate files drifted from HEAD
   │
   │  (1) extract agent-visible prompt          run.py:124-129 → prompt_extract.extract_agent_visible_prompt
   ▼
prompt text (scrubbed; only the 2 allow-listed H2 sections)
   │
   │  (2) build workspace                        run.py:138-149 → workspace.build_workspace
   ▼
/tmp/run-agent-<id>/CraftBenchTemplate/  (substrate copy)
/tmp/run-agent-<id>/PROMPT.md            (prompt + writable-file listing + constraints)
   │
   │  (3) A2 pre-flight handshake (interactive)  run.py:171-186   [skipped by --no-preflight / tests]
   │      "open this .uproject in your editor, press Enter"
   │
   │  (4) dispatch the agent                     run.py:188-211 → adapter.run(...)
   ▼
AgentResult (transcript + telemetry); agent has mutated the /tmp copy in place
   │
   │  (5) snapshot the submission                run.py:216-223 → snapshot.snapshot_submission
   ▼
runs/<id>/submission/Source/CraftBenchTemplate/...   (only changed/created writable files)
   │  └─ if EMPTY → exit 2, overall = FAIL_NO_EDITS   run.py:219-222
   │
   │  (6) run the verifier                       run.py:225-243 → subprocess: verify-single/run_task.py
   ▼
verifier exit code + stdout + report.json
   │  (7) map to a harness verdict               run.py:242 → adapters.base.verdict_from_verifier
   ▼
runs/<id>/result.json   {overall, agent:{telemetry}, verifier:{report}}
   │  (8) teardown the /tmp workspace            run.py:248-250  [unless --keep-workspace]
```

The process exit code mirrors the verdict: `0` PASS, `2` empty submission,
`3` any non-PASS verdict, `4` harness error / dirty substrate
(`run.py:12-17`, `run.py:252`).

### 3.2 Artefacts written to `runs/<backend>/<run_id>/`

`run_id = <UTC YYYYMMDD-HHMMSS>-<task_id>-<model_slug_safe>`
(`run.py:88-92`; `:` and `/` in the slug are flattened to `-`/`_`). Files:

- `prompt.md` — a copy of the rendered `PROMPT.md` (`run.py:150`).
- `workspace_manifest.json` — `{project_dir, writable_files[], readonly_files_count}` (`run.py:151,429-437`).
- `agent_transcript.jsonl` — raw model stdout (stream-json, line-delimited) (`run.py:199`).
- `agent_result.json` — the serialized `AgentResult` (`run.py:200`).
- `submission/` — the staged diff (`run.py:217-218`).
- `verifier_stdout.txt` / `verifier_stderr.txt` — captured verifier output (`run.py:234-235`).
- `result.json` — the top-level run record (`run.py:469-487`).

### 3.3 Batch run (`run_batch.py`)

`run_batch.py` runs the same per-task flow many-wide, but its concurrency and
the live-status disk contract are the point. For `claude-p` the
`Environment.for_product()` factory returns a `NullEnvironment`
(`environment.py:409-425`) with `max_concurrency = 5` (`environment.py:91`), so
Pool A width is `min(--concurrency, 5)` (`run_batch.py:332`) — i.e. up to 5
agents run in parallel in independent `/tmp` copies (each copy is its own
isolated sandbox, so there is no cross-task contention). A second
**Pool B** semaphore (default width 1, `run_batch.py:334`) serialises the
verification step, because each verify spawns a *separate cold UE process* and
you do not want N heavyweight UE builds at once.

Each task walks a phase machine
`queued → running → grading → done` (terminal `error|timeout|cancelled`)
(`run_batch.py:73-80, 403-481`). For each task the orchestrator writes:

- `status.json` — a **rolling full-state snapshot**, atomically rewritten on
  every phase change (`run_events.py:157-208`); schema `craftbench.livestatus/v1`.
- `events.jsonl` — an append-only tape, one JSON line per `emit`, each stamped
  with a monotonic `seq` (from 1) and a `ts` (`run_events.py:140-153`).
- `result.json` — written **atomically and BEFORE** `status.json.phase` flips to
  `done` (`run_batch.py:464-470`), so a TUI/reader that sees `done` can always
  find a complete matrix entry (the torn-read guard, `run_events.py:223-233`).

The TUI/`live.py` are *read-only tailers* of these three files; `run_batch.py`
is the sole writer (`run_events.py:24-26` one-writer invariant).

---

## 4. Important data structures / schemas

### 4.1 `AgentResult` (`adapters/base.py:136-151`)

The single value an adapter returns. The deterministic path produces it via
`ClaudePAdapter.run`:

```python
@dataclass
class AgentResult:
    exit_code: int               # 0 = adapter ran cleanly; 124 = timeout; else process error
    transcript: str              # raw model stdout (stream-json for claude-p) + appended STDERR
    summary: Optional[str]       # final assistant text (from the `result` event)
    tool_use_count: Optional[int]
    duration_s: float
    mcp_tool_use_count: Optional[int] = None   # subset of tools whose name starts with "mcp__"
    tool_names: Optional[List[str]] = None     # ordered, verbatim
    cost_usd: Optional[float] = None
    num_turns: Optional[int] = None
    tokens_in: Optional[int] = None            # None when the usage block is absent — never faked as 0
    tokens_out: Optional[int] = None
```

`to_json()` serialises all fields; `run.py:469-487` lifts a subset into
`result.json`'s `agent` block. Note `result.json`'s `agent` block does **not**
include `tokens_in`/`tokens_out` even though `AgentResult` carries them
(`run.py:475-484` — they are persisted in `agent_result.json` only). That is a
minor inconsistency worth knowing if you are wiring a cost dashboard off
`result.json`.

### 4.2 `AgentAdapter` Protocol (`adapters/base.py:154-165`)

The only model-specific seam. Any backend satisfying:

```python
class AgentAdapter(Protocol):
    name: str
    def run(self, prompt_path, workspace_dir, max_turns, timeout_s) -> AgentResult: ...
```

can be dropped into the registry without touching the rest of the harness.
(Note: the batch path's `NullEnvironment.run_one` calls `adapter.run(..., events=events)`
with an **extra keyword** — `environment.py:131-136` — so a batch-capable adapter
must accept `events` too. The single-run `run.py:192-197` calls it *without*
`events`. `ClaudePAdapter.run` does **not** declare `events`
(`claude_p.py:197-203`), so it is single-run-only as written — the batch
`NullEnvironment` path would `TypeError` on it. Flagging this as a real gap, not
inventing a feature.)

### 4.3 The verdict vocabulary (`adapters/base.py:35-133`)

This is the load-bearing schema for *what counts as a graded outcome*. The
verifier (`verify-single/run_task.py`) signals via process exit code +
`report.json`:

| verify-single exit | meaning | harness verdict | graded? |
| --- | --- | --- | --- |
| `0` | PASS | `PASS` (read from `report.json`) | yes |
| `1` | FAIL | `FAIL` (read from `report.json`) | yes |
| `3` | substrate-pin reject | `SUBSTRATE-REJECT` | **no** |
| `4` | sandbox reject | `SANDBOX-REJECT` | **no** |

(Verifier exit codes confirmed at `verify-single/run_task.py:1390` (3),
`:1407` (4), `:1472` (`0 if pass else 1`).)

`verdict_from_verifier(returncode, stdout)` (`base.py:118-133`) implements the
precedence: **(1)** a non-graded exit code (3/4) wins outright — those are
*verifier-noise*, never an agent FAIL; **(2)** otherwise read the authoritative
`overall` from `report.json` (whose path the verifier prints as
`json report: <path>`, parsed at `base.py:81-102`); **(3)** fall back to a
stdout regex on the `overall : <value>` line, defaulting to FAIL
(`base.py:105-115`). `GRADED_VERDICTS = {PASS, FAIL}` (`base.py:54`) is the
**pass-rate denominator** — `pass_rate()` (`base.py:67-78`) and the batch
`summarize_verdicts()` (`run_batch.py:202-227`) exclude rejects/timeouts so a
verifier hiccup can never be silently relabelled an agent failure. This is the
single most important correctness rule in the harness.

### 4.4 `status.json` schema (`run_events.py:37-58`)

Frozen key set, batch-only: `schema, run_id, task_id, product, phase, step,
max_steps, current_tool, tool_count, tokens_in, tokens_out, started_at,
updated_at, elapsed_s, result, error`. Always rewritten in full
(`write_status_full` lays the shape; `status(**fields)` merges-then-rewrites,
always bumping `updated_at`).

### 4.5 `AGENT_WRITABLE.json` (the substrate manifest)

Read by `workspace.build_workspace` and `snapshot.snapshot_submission` (and,
independently, by the verifier's sandbox). The deterministic path only uses the
`writable` array:

```json
"writable":       ["Source/CraftBenchTemplate/", "Content/Tasks/"],
"asset_writable": ["Content/Tasks/", "Content/Blueprints/", "Content/Abilities/",
                   "Content/Generated_Materials/", "Content/Generated_Audio/"],
"deny":           ["Source/CraftBenchTests/", "Config/", "Content/Maps/",
                   "Tools/", "Plugins/", "CraftBenchTemplate.uproject", "AGENT_WRITABLE.json"]
```

`writable` prefixes are matched against POSIX-normalised, substrate-relative
paths to classify and snapshot. `deny` and `asset_writable` are *not* consulted
by the harness — they govern the verifier's sandbox acceptance — but `deny` and
the workspace's own `HIDDEN_PATHS` overlap deliberately (see gotcha §6.3).

---

## 5. How `claude-p` produces a submission diff (the heart of the deterministic path)

### 5.1 The scrub (`prompt_extract.py`)

`extract_agent_visible_prompt(task_md)` splits the task `.md` into `## H2`
sections (exact, case-sensitive heading match — `prompt_extract.py:28-51`) and
keeps **only** an allow-list: `"Prompt given to the agent"` and
`"Workspace state pre-task"` (`prompt_extract.py:22-25`). Everything else — the
`## Verifier specification`, `## Anti-gaming notes`, `## Reference solution
metadata`, etc. (confirmed present in a real task at
`tasks/gp-spawn-sequence.md:73,128,135`) — is **dropped**. The allow-list is the
point: a future answer-key section added to the spec is dropped *by default*, so
new sections cannot accidentally leak. A task with no
`## Prompt given to the agent` section raises `ValueError`, which `run.py:127-129`
converts to a harness error (exit 4).

### 5.2 The sandbox copy (`workspace.py`)

`build_workspace(...)` creates `/tmp/run-agent-<id>/CraftBenchTemplate/` and
walks the substrate file-by-file (`workspace.py:88-107`):

- `SKIP_SUBTREES = (Binaries, Intermediate, DerivedDataCache, Saved)` — never
  copied; UE regenerates them on project open (`workspace.py:36, 94-95`).
- `HIDDEN_PATHS = ("Source/CraftBenchTests/", "AGENT_WRITABLE.json")` — copied
  files matching these are **skipped entirely** so the agent never even *sees*
  the verifier-only test module (whose fixture bodies are the answer) or the
  sandbox manifest (`workspace.py:38-41, 96-97`). This is **narrower** than the
  manifest's `deny` list, because deny-listed-but-needed dirs (`Config/`,
  `Content/`, `Plugins/`, the `.uproject`) still get copied so UE can open the
  project — they are "agent can see, can't write," whereas HIDDEN_PATHS is "must
  not see" (`workspace.py:14-23`).
- Every copied file is classified: matches a `writable` prefix → `writable_files`;
  else → `readonly_files` (`workspace.py:103-106`).

Then it renders `PROMPT.md` (`workspace.py:121-158`): the scrubbed task body, a
literal listing of the writable files ("your edits to these are the
submission"), the workspace path, and the constraints (edit only writable files,
don't touch anything outside the workspace dir). The rendered prompt also tells
the agent the UE editor is already open and it may use `mcp__unreal_editor__*`
tools — but for the **Baseline** that text is moot: `claude-p` runs with
`--strict-mcp-config` and no `--mcp-config`, so it has *zero* MCP servers and
actuates purely via Read/Write/Edit/Bash on the `/tmp` files.

### 5.3 The dispatch (`adapters/claude_p.py` + `adapters/registry.py`)

`make_adapter("claude-p:opus")` parses the `<backend>:<model>` slug
(`registry.py:56-66`) and returns `ClaudePAdapter(model="opus", strict_mcp=True)`.

`build_claude_command` (`claude_p.py:26-81`) assembles the argv:

```
claude -p
  --output-format stream-json   # line-delimited JSON events (so tool calls are visible)
  --verbose                     # required by stream-json
  --add-dir <workspace_dir>     # file-access scope = the /tmp copy
  --permission-mode bypassPermissions   # single-shot agent runs allowed tools w/o prompts
  --max-turns <N>
  [--model <slug>]              # only when a model was given
  [--strict-mcp-config]         # Baseline: present, with NO --mcp-config → zero MCP servers
```

Two design choices stand out:

- **The prompt is on stdin, not in argv** (`claude_p.py:38-40`, `:225`). The
  variadic `--allowedTools`/`--disallowedTools` lists could otherwise swallow a
  positional prompt; stdin sidesteps that entirely. (Confirmed by
  `test_claude_p_command.py:42-45`.)
- **`bypassPermissions`** (`claude_p.py:50-53`): a single-shot agent must run its
  allowed tools without interactive prompts. `auto` was found to *deny* MCP write
  tools in the parent context — relevant to `aura-mcp`, harmless but consistent
  for the Baseline.
- The **cwd is `workspace_dir.parent`** (`claude_p.py:216-217`) — i.e.
  `/tmp/run-agent-<id>/`, deliberately *not* the repo — so the repo is not
  implicitly on the agent's path.

`run()` (`claude_p.py:197-265`) shells the command with a `timeout_s`, captures
stdout/stderr, parses telemetry, and returns the `AgentResult`. On
`TimeoutExpired` it still parses whatever partial stdout arrived and returns an
`AgentResult` with `exit_code=124` (`claude_p.py:249-265`) — a timeout is *not* a
crash; the partial work is still snapshotted downstream.

### 5.4 The telemetry capture (`parse_stream_json`, `claude_p.py:84-170`)

stream-json was chosen over plain text precisely so the harness can *see* tool
calls (plain `-p` text drops them). The parser walks newline-delimited JSON
events (malformed lines silently skipped — `claude_p.py:123-126` — the raw
transcript is saved verbatim so nothing is truly lost) and pulls:

- from each `assistant` event's `content[]`: every `tool_use` item's `name`, in
  order → `tool_names` (`claude_p.py:131-137`);
- `tool_use_count = len(tool_names)`, and `mcp_tool_use_count = ` count of names
  starting with `"mcp__"` (`claude_p.py:159-160`) — for the Baseline this is
  always 0, which is exactly how the harness *verifies* the Baseline used no MCP;
- from the single `result` event: `summary` (final text), `cost_usd`
  (`total_cost_usd`), `num_turns`, and `tokens_in/out` from the `usage` block
  (absent ⇒ `None`, never fabricated as 0 — `claude_p.py:150-157`);
- `session_id` from the `init` event (for forensics).

(All of this is pinned by `test_claude_p_command.py:96-196`.)

### 5.5 The diff snapshot (`snapshot.py`)

This is the **submission**. `snapshot_submission(workspace, submission_dir,
substrate_root)` does **not** trust the build-time `workspace.writable_files`
list — it **re-walks** `workspace.project_dir` for everything under the
`writable` prefixes (`snapshot.py:39-43`). The reason is sharp: the build-time
list was frozen *before* the agent ran, so it misses **agent-created** files;
trusting it silently dropped whole submissions for create-new-file tasks
(`snapshot.py:5-9`). For each writable file, it byte-compares against the
pristine substrate counterpart and stages it only if it is **new (no pristine)
or different** (`snapshot.py:46-53`). Files outside the writable prefixes are
never staged — the substrate is authoritative for those and the verifier's
sandbox would reject them anyway. The submission directory mirrors the
substrate-relative layout (e.g. `submission/Source/CraftBenchTemplate/Foo.cpp`),
which is exactly what `verify-single` overlays onto its own clean substrate copy.

If nothing was staged → empty submission → `run.py:219-222` exits 2 with
`overall = FAIL_NO_EDITS` (a non-graded condition).

> The live-project (`aura-*`) snapshot deliberately uses an *identical* re-walk +
> byte-compare against a pre-run backup (`run.py:342-357`) so the two paths
> capture submissions the same way — but the live path is section 05's concern.

---

## 6. Non-obvious gotchas (the things that bite newcomers)

### 6.1 The substrate-integrity pre-flight only checks *tracked* files

`check_substrate_clean` (`substrate_check.py:59-120`) runs `git status
--porcelain` against the substrate and returns dirty *tracked* entries. It
**drops untracked (`??`) entries** (`substrate_check.py:104-105`), drops
`SKIP_SUBTREES` (which for *this* module includes `Plugins` — Aura's working
area — `substrate_check.py:39`), and drops `.uproject` changes
(`substrate_check.py:44`, rewritten on every project open). So: a UE editor
auto-save of `L_SanityTask.umap` (a tracked binary) **fails** the pre-flight
(good — it would silently invalidate the run), but the mountain of untracked
build output and uncommitted WIP under `Plugins/` does **not**. This matches the
repo's the repo conventions warning that the substrate carries load-bearing untracked
state — do not "fix" the pre-flight to flag untracked files. If you genuinely
need to run against modified substrate, `--allow-dirty-substrate`
(`run.py:75-78, 106`) skips the gate.

### 6.2 The interactive A2 pre-flight will hang a non-interactive caller

`run.py:171-186` prints "open this `.uproject`, then press Enter" and blocks on
`input()`. For CI, tests, or any scripted invocation you **must** pass
`--no-preflight` (or `--prepare-only` for the two-step open-then-dispatch flow).
For the pure-Baseline deterministic path the editor handshake is irrelevant
(`claude-p` edits files, not a live editor), so `--no-preflight` is the normal
mode. The batch path never hits this — `NullEnvironment.setup/precheck` are
no-ops (`environment.py:96-103`).

### 6.3 `HIDDEN_PATHS` (workspace) ≠ `deny` (sandbox) — two different defenses

It is tempting to think one list governs "what the agent can't touch." There are
actually two, at two stages: `workspace.HIDDEN_PATHS` decides what is *copied
into the workspace at all* (visibility), and `AGENT_WRITABLE.json.deny` decides
what the *verifier's sandbox rejects at submission time* (write acceptance,
enforced in `verify-single/sandbox.py`, not here). They overlap on
`Source/CraftBenchTests/` and `AGENT_WRITABLE.json` but are deliberately
different sizes — see §5.2. Editing one without the other creates a gap.

### 6.4 An agent exit code ≠ 0 does not abort the run

`run.py:209-211` only *warns* on a non-zero adapter exit and proceeds to
snapshot anyway — a crashed/timed-out agent may still have produced a partial,
gradeable diff. The run's actual outcome is decided entirely by the snapshot
(empty? → exit 2) and the verifier (PASS/FAIL). Do not assume `result.json`'s
`agent.exit_code` tells you whether the task passed.

### 6.5 The pass-rate denominator excludes rejects — by design

If you compute "pass rate" by counting PASS over *all* runs you will be wrong.
`SUBSTRATE-REJECT`, `SANDBOX-REJECT`, `TIMEOUT`, `FAIL_NO_EDITS`, and harness
errors are **not graded** (`base.py:49-64`) and are excluded from the
denominator (`base.py:67-78`, `run_batch.py:202-227`). Use
`adapters.base.pass_rate()` / `is_graded_verdict()` — never hand-roll the ratio.
`pass_rate([])` returns `None`, not 0, to distinguish "0% pass" from "nothing
graded."

### 6.6 `ClaudePAdapter` is single-run-only as written (batch gap)

As noted in §4.2: `NullEnvironment.run_one` passes `events=` to `adapter.run`
(`environment.py:131-136`) but `ClaudePAdapter.run` does not accept it
(`claude_p.py:197-203`). The single-run `run.py` path does not pass `events`, so
it works; the batch path's `NullEnvironment` would raise `TypeError`. Either the
adapter needs an `events=None` parameter, or `NullEnvironment` is currently
exercised only with fakes that accept `events`. Treat the batch+`claude-p`
combination as not-yet-wired rather than assuming it runs — and verify before
relying on it.

### 6.7 `result.json` and `agent_result.json` are different shapes

`agent_result.json` is the *full* serialized `AgentResult` (all fields incl.
tokens). `result.json`'s `agent` block is a *hand-picked subset* (no tokens —
`run.py:475-484`). The batch path builds its own `result.json` via
`_agent_result_to_dict` (`run_batch.py:147-165`), which is tolerant of partial
fakes. If a tool reads tokens, read `agent_result.json`, not `result.json`.

---

## 7. How to run / observe it

The deterministic path has no UE dependency *to test the harness logic*. The
pure-Python units cover the scrub, the workspace copy, the snapshot, the command
build, the stream-json parse, and the verdict mapping:

```sh
# All 55 deterministic-path units (no UE, no claude binary, no network):
python3 -m unittest \
  tools.run-agent.tests.test_claude_p_command \
  tools.run-agent.tests.test_workspace \
  tools.run-agent.tests.test_snapshot \
  tools.run-agent.tests.test_prompt_extract \
  tools.run-agent.tests.test_verdict_mapping
# → Ran 55 tests ... OK   (verified)
```

A real single run (needs the `claude` CLI on PATH + a UE 5.8 install) — for the
deterministic Baseline you would add `--no-preflight`:

```sh
python3 tools/run-agent/run.py \
  --task tasks/gp-spawn-sequence.md \
  --model claude-p:opus \
  --ue-root "/Users/Shared/Epic Games/UE_5.8" \
  --no-preflight --keep-workspace
```

Then read `runs/<run_id>/result.json` for the verdict + telemetry,
`agent_transcript.jsonl` for the full tool-by-tool tape, and `submission/` for
the exact diff that was graded. (No UE is installed in this environment, so the
end-to-end run was not exercised here; only the static reading + the 55
pure-Python units were.)

> One sentence on the other arms, per scope: `registry.py` also wires
> `openrouter:` (the same `claude -p` shell pointed at OpenRouter's
> Anthropic-compatible API via `OPENROUTER_API_KEY`/`OPENROUTER_BASE_URL`, so a
> non-Anthropic model runs on the baseline with zero new code), `unreal-mcp`
> (same shell plus Epic's first-party in-editor MCP server, file tools kept),
> `aura-mcp` (same shell but given a commercial product's MCP servers and denied
> the generic actuators — disclosed here, not runnable), and `bare:` (our own
> minimal five-tool loop over any OpenAI-compatible endpoint).

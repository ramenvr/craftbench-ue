# CraftBench — Onboarding

> **Quick path:** the **[README](README.md) Quick start** gets you productive in
> ~10 minutes *on a box that already has UE 5.8 installed* — `setup.ps1` /
> `setup.sh`, then `cb smoke`. This doc is the deep
> tiered runbook for when you need the *why* (secrets, run layout,
> troubleshooting beyond what the pre-spend preflight gate auto-detects).

**CraftBench** is a benchmark for evaluating AI coding agents on **Unreal Engine
5.8** gameplay-programming tasks. Each task is a behavior-only prompt; a
**deterministic verifier** decides PASS/FAIL by building the project (**L1**) and
driving it in a real headless PIE world (**L2**) — no LLM-as-judge in the gate.
The benchmark is engine-pinned (UE 5.8) and substrate-pinned: `CraftBenchTemplate`
(a minimal C++ scaffold with per-task actor pairs) by default, with
`UE-projects/ThirdPerson/` (the stock Third Person C++ template) as the second
substrate via the spec's `substrate:` key.

> **One-page command reference:** [docs/CHEATSHEET.md](docs/CHEATSHEET.md).

---

## Two shareability tiers — pick yours first

What you need to install depends entirely on *which* part of CraftBench you run.

| You want to… | Needs | Secrets |
|---|---|---|
| **Grade** a submission against a task (deterministic verifier) | UE 5.8 + Python 3.11+ (3.12 recommended) + `git` + `tar` | **none** |
| Run an **agent arm** (`claude-p`, `unreal-mcp`, or any **OpenRouter** model), then auto-grade | the above + `claude` CLI + `ANTHROPIC_API_KEY` (and `OPENROUTER_API_KEY` for `openrouter:`) | 1–2 keys |

**After setup, run `cb smoke` first — whatever your tier** (preflight →
verifier unit tests → a real t0 reference grade). Then:

- **Grade-only:** the `run_task.py` smoke run below (the no-pip alternative if you can't install `cb`) — or `cb batch-eval --references all` to sweep every committed reference solution (the full-set gate).
- **Agent arms:** `cb eval --model claude-p:<model> --task cpp/t0-sanity-log-on-beginplay`, or the same with `--model unreal-mcp:<model>`.

> **Both tiers are clone-and-go.** The deterministic verifier and every arm you
> can run from this repository need one clone, one UE install and at most one
> API key — no second repository, no service account, no vendor login. The
> agent tier is **multi-model**: `cb eval --model claude-p:<model>` runs any
> Claude model, `--model unreal-mcp:<model>` gives that same model Epic's
> first-party in-editor MCP server, `--model openrouter:<provider/model>` runs
> a non-Anthropic model through OpenRouter's Anthropic-compatible API (same
> `claude` CLI), and `cb matrix --model A,B,C --task <set>` runs a
> {model}×{task} leaderboard.
>
> The **third** arm the published measurement reports, `aura-mcp`, is
> deliberately absent from this table: it drives a commercial third-party
> product and is **disclosed but not reproducible** here. Its dispatch, its
> exact tool-access configuration and its verifier path are all in the tree and
> readable; only the vendor bring-up and login were removed. `cb` refuses the
> slug in the first second rather than failing eight minutes into a stack that
> was never going to come up. See [README](README.md) §"The three measured
> arms" and [THIRD-PARTY.md](THIRD-PARTY.md).

---

## Prerequisites

| Tool | Version / detail |
|---|---|
| **Unreal Engine** | **5.8** (engine-pinned). Install via the Epic Games Launcher — one-time, ~100 GB disk, allow hours. Default Epic path: `C:\Program Files\Epic Games\UE_5.8` (Windows) / `/Users/Shared/Epic Games/UE_5.8` (macOS). Override with `--ue-root` or `CB_UE_ROOT`. |
| **Python** | **3.11+ (3.12 recommended)** (verifier core alone runs on 3.10) — `cb.cmd` tries **`py -3.12` → `py -3` → `python` → `python3`** (first working 3.11+); override with `CB_PYLAUNCH` (e.g. `set CB_PYLAUNCH=python`). |
| **git** | Required — the verifier materializes a clean substrate via `git archive`, and `.gitattributes` must apply at checkout. |
| **tar** | Required for the `git archive HEAD \| tar -x` pipe. Windows 10 1803+/11 ship `tar.exe`; Git for Windows also bundles it. |

UE is **not** required to run the verifier unit tests — only to grade for real.

---

## Clone

```sh
git clone -c core.longpaths=true https://github.com/ramenvr/craftbench-ue.git craftbench-ue
```

`-c core.longpaths=true` is not optional on Windows: the longest path this
repository tracks is 214 characters, and Git for Windows aborts the checkout
without it (README section 3 has the details and the recovery).

**That single clone is the whole setup.** There is no second repository to
fetch, no plugin to drop into `Plugins/`, and no vendor stack to bring up:
both tiers above are clone-and-go, and the two one-time steps that used to
follow a clone (pulling a generated env file from a vendor's hosting account,
and building a proprietary plugin's editor binary) belonged to the `aura-mcp`
runtime, which this release deliberately does not ship. See
[README](README.md) for what that arm still discloses.

`UE-projects/<substrate>/Plugins/` stays **gitignored** and, on this release,
empty. The graded path never reads it: the verifier copies the substrate from
git HEAD and excludes all of `Plugins/` from that copy, so an empty `Plugins/`
changes no verdict. `CB_GENIUS` still exists as an explicit override for a
locally-supplied plugin tree, but nothing in the published arms consults it.

---

## Run the verifier

### Unit tests — no UE required

```sh
python -m unittest discover -v tools/verify-single/tests
```

These cover task parsing, the sandbox, the layer registry,
and report logic. On Windows the `TestL1DualTarget` cases **SKIP by design**
(they stub UBT with a `#!/bin/sh` script Windows can't exec) — a SKIP there is
expected, not a failure.

### Grade a reference solution end-to-end — needs UE 5.8

```sh
py -3.12 tools/verify-single/run_task.py \
    --task tasks/cpp/t0-sanity-log-on-beginplay/task.md \
    --submission tasks/cpp/t0-sanity-log-on-beginplay/reference \
    --ue-root "C:/Program Files/Epic Games/UE_5.8" \
    --workdir C:/cb58/wd   # Windows MAX_PATH: pick a SHORT, NON-EXISTENT dir — the verifier requires the workdir not to exist, and a deep/long path silently trips the 260-char limit
```

On Windows use the `py` launcher (`py -3.12`) — a stock box often has no bare
`python` on PATH; off Windows use `python3`.

PASS ⇒ your machine grades correctly. Then point `--task` / `--submission` at any
task + agent output directory. The runner builds **both** the `<Module>Editor`
and `<Module>` (Game) targets (L1), then runs the `AFunctionalTest` fixture in a
headless PIE world (L2) and writes a JSON report. **Exit codes:** `0` pass · `1`
fail · `2` bad invocation · `3` retired/reserved (historical hash-gate) · `4`
sandbox violation · `5` substrate bug.
---

## The `cb` launcher

`cb` is the CraftBench CLI (module `aura_rig.cb`). Three ways to run it, most
convenient first:

- **PATH-wide `cb`** — `setup.ps1` / `setup.sh` pip-installs it as a console
  script (`pip install -e tools/run-agent`); works from any shell once your
  Python Scripts dir is on PATH (setup reports the dir if it isn't).
- **Repo-root shims, no install**: `.\cb <cmd>` (PowerShell/cmd) / `./cb <cmd>`
  (bash) from the repo root — always work on a fresh clone.
- **No launcher at all**: `py -3.12 -m aura_rig.cb <cmd>` run from
  `tools/run-agent` (use `python`/`python3` off Windows).

Useful overrides — **shell environment only, not `.env`**: `CB_PYLAUNCH`
(the interpreter the shims boot `cb` with) and `CB_CRAFTBENCH` (repo root).
Neither can come from `.env`: `CB_PYLAUNCH` is read by the shim before any
Python starts, and `CB_CRAFTBENCH` is read straight from `os.environ` and is
not in the `.env` export whitelist. `CB_UE_ROOT` (UE path) does work in
`.env`.

### Commands you'll actually use

```sh
cb doctor                          # read-only per-tier readiness + a fix hint per blocker
cb smoke                           # preflight -> verifier unit tests -> a real t0 grade
cb tasks                           # interactive: browse task sets -> tasks -> run the chosen one
cb eval --task t0-sanity-log-on-beginplay --model claude-p:sonnet    # GRADED: drive -> L1 -> L2 -> VERDICT
cb eval --task t0-sanity-log-on-beginplay --model unreal-mcp:sonnet  # same model + Epic's in-editor MCP
cb eval --task t0-sanity-log-on-beginplay --model openrouter:openai/gpt-5   # GRADED, non-Anthropic reasoner
cb bench --model A,B --task <set>/<id> --repeat 1  # head-to-head -> runs/bench-<ts>/leaderboard.html
cb matrix --model A,B,C --task bp-g2               # {model}x{task} leaderboard, one run per cell
cb discriminate --task <id>        # token-FREE FR-017 matrix: reference PASS / empty + variants FAIL
cb batch-eval <dir-of-submissions> # token-FREE PARALLEL grade of a folder of isolated submission dirs (defaults to 1-wide, safe on <=32 GB; add --verify-concurrency 2+ on a >32 GB host)
cb batch-eval --references all     # same, but sweeps every committed reference solution (the smoke input)
cb batch-eval --references all     # fuller setup certification: grade every committed reference
cb warm-prime --warm-slots 2       # build the L1 warm-cache pool (one cold build per slot)
cb lint                            # static spec lint (instant, no UE)
```

| Command | What it does | Tokens? |
|---|---|---|
| `doctor` | Read-only env diagnostic; per-tier readiness (grade-only / agent arms) + fix hints. Exit 0 iff the highest provisioned tier is READY. | no |
| `smoke` | The golden-path proof: preflight → verifier unit tests → a real t0 reference grade. Run it first, whatever your tier. | no |
| `tasks` | Interactive picker: sets → tasks → detail, then runs the one you pick (same as `cb eval --task <id>`). | only if you run one |
| `eval` | Graded benchmark eval: drive → L1 build → L2 PIE → `VERDICT`. `--task` is set-aware (bare id, or `<set>/<id>`); `--model` selects the arm — `claude-p:<m>`, `unreal-mcp:<m>`, `openrouter:<p/m>`, `bare:<p/m>`. `aura-mcp:*` is refused in the first second (disclosed, not reproducible). Editor-backed arms restart the editor fresh per drive for isolation (`--reuse-editor` opts out). | yes |
| `bench` / `matrix` | Run a {model}×{task} cross product through the same runner → a `leaderboard.{html,md,json}`. `bench` repeats a cell (`--repeat N`); `matrix` is the one-run-per-cell sibling. `aura-mcp` slugs are unsupported here for the same reason `eval` refuses them. | yes |
| `discriminate` | Token-free deterministic discrimination batch — re-runs the full FR-017 matrix per task (reference→PASS, empty + each anti-gaming variant→FAIL via its named assertion). No agent, no stack. | no |
| `batch-eval` | Token-free parallel grade of a folder of already-isolated submission dirs (memory-gated cold verifies; `cb batch-eval --references all` grades every committed reference solution — the ready smoke input). Defaults to 1-wide (safe on ≤32 GB); 2-wide L2 PIE can contend and spuriously FAIL an L1-passing solution, so raise `--verify-concurrency` only on a >32 GB host. | no |
| `refgate` | **Retired.** Still dispatchable, but `cb discriminate` is the authoring gate and `cb batch-eval --references all` is the fuller setup sweep. See `docs/CHEATSHEET.md`. | no |
| `warm-prime` | Build the L1 warm-cache pool (`--warm-slots N`), so later verifies build incrementally. | no |
| `view` | Open a **windowed** editor to see / Play(PIE) a change (`--map`, `--run <run-dir>`). | no |
| `review` | Overlay a run's `deliverable/` onto the scratch project and open a windowed editor on it. | no |
| `lint` | Static task-spec + repo-inventory lint. Instant, no UE. | no |
| `up` / `status` / `clean` / `down` | Bring the editor-backed lane up and gate on its MCP catalog (no run) · one-shot stack + recent-runs overview · reset the managed headless scratch project to pristine · stop everything and free the engine. | no |

> **You don't need `cb up`.** `eval` auto-brings-up whatever an arm needs before
> it runs, and every command is idempotent. `cb up` is only a no-run gate check.

---

## After you run — reading a run

Every graded run lands in a per-backend folder:
`runs/<backend>/<ts>-<task>-<model>/` (`runs/claude-p/`, `runs/unreal-mcp/`,
`runs/openrouter/`, ...). Where to look:

- **`summary.json`** — the outcome (`verdict`; the run writes `result.json`
  with `overall`). It **embeds the full verifier report**
  under `"verifier"` — no stdout scraping needed — plus `"artifacts"` (the
  swept `--capture` screenshots) and `"graded_workdir"` (where the built
  project lives).
- **`verifier_stdout.txt`** and **`report.json`** — the per-layer L1/L2 detail
  when the one-line verdict is not enough.
- **Dashboard:** `python -m tools.dashboard.web` serves the {arm}×{task}
  matrix; clicking a cell opens the full report modal — with artifact
  thumbnails when the run used `--capture`.
- **Look at it in the editor:** `cb review runs/<run>` overlays the run's
  `deliverable/` onto the scratch project and opens a **windowed** editor (it
  also prints the run's artifacts).
- **Retention:** the built project persists at the run's
  `graded_workdir` (default `<CB_ROOT>/wd`, e.g. `C:\cb\wd` — the old
  `C:\cbwd` default is RETIRED; `CRAFTBENCH_WD_ROOT` is a back-compat
  override, not the source of the default). It is **slimmed by default**
  (`CB_WORKDIR_RETENTION`, modes `full`/`slim`/`none`): `slim` drops the
  compiler intermediates and the debug binaries, so a finished workdir is
  ~42 MB rather than the ~5.9 GB it built, and what survives is still `out/`
  plus a project that launches. A FAILED build is never slimmed — the object
  tree is the evidence. **Read that narrowly:** retention only ever decides the
  fate of a workdir somebody KEPT. On the plain `run_task.py` / `cb batch-eval`
  path the runner owns the tempdir and deletes it verdict-blind, so "never
  slimmed" does not mean "still there". Since 2026-08-15 a bounded excerpt of
  every non-passing layer's log lands beside the report either way
  (`failure_evidence.py`).
  `cb eval --keep` additionally snapshots a lean copy (no
  Binaries/Intermediate) under `runs/<run>/project-lean/` — note **lean is not
  slim**: the `--keep` snapshot EXCLUDES `Binaries/`, slim KEEPS them. Reclaim
  disk with `cb clean --workdirs [--older-than N]` — it prunes only workdirs no
  `runs/**/summary.json` still references — or `cb clean --workdirs --slim`,
  which slims every workdir in place, referenced or not (those are exactly the
  ones the prune can never touch). Add `cb clean --presnaps` for
  orphaned crash-debris pre-run snapshots (60-min in-flight floor, which every
  one of these paths applies).
- **Crash recovery:** a hard-killed run (taskkill, console close) can leave
  the substrate half-hidden and the next run's DIRTY-SUBSTRATE gate tripped.
  The gate now **self-heals**: it restores the crashed run's leftover
  `fairness_backup` (which carries a machine-readable `fairness_state.json`)
  and reverts leftover agent edits from the orphaned presnap, then re-checks.
  Only dirt those artifacts can't explain still aborts.

---

## Batch evals
Generation and grading are deliberately **decoupled**:
Generation and grading are two deliberately **decoupled** batch commands:

- **`cb batch-eval --references all`** — token-free parallel grade of every
  committed reference solution. This is the standing **full-set gate**: on
  a healthy machine every committed reference PASSes (the current sweep
  result lives in [tasks/CATALOG.md](tasks/CATALOG.md)).
  `--references bp-g2` filters
  to one set; add `--warm-cache` (below) and/or `--keep`.
- **`cb batch-eval <dir-of-submissions>`** — the same grader pointed at a
  folder of already-isolated **agent submission** dirs, each named by its task
  id. This is how you grade a batch of agent outputs.
- **Generation** is `cb eval` / `cb bench` / `cb matrix` — there is no batch
  generation command on this release: the one that existed drove N
  concurrent chats against the commercial product's own UI and went with the
  rest of that lane. Generation and grading were always deliberately
  decoupled, so grade whatever a run produced with `cb eval` / `cb batch-eval`
  regardless of what made it.

---

## Faster verifies — the L1 warm cache

L1 (the UBT build of both targets) is the dominant cost of a cold verify. The
**warm cache** keeps a prebuilt baseline at a fixed slot and builds
*incrementally* (measured **~5–6× faster L1**; a 5-task batch ran 153 s vs 795 s
cold). Prime once, then pass `--warm-cache`:

```sh
cb warm-prime --warm-slots 2                                   # one cold build per slot (~2 min, ~5 GB each)
cb batch-eval <dir-of-submissions> --warm-cache --verify-concurrency 2
cb discriminate --task <id> --warm-cache                       # the matrix legs build warm too
```

Match `--warm-slots` to your `--verify-concurrency` so N concurrent verifies all
run warm. Warming never blocks and never changes a verdict — a stale/missing pool
is a cache miss that silently falls back to a cold build.

---

## Registering a new eval (authoring a task)

Registration is **pure file-drop** — no registry to edit. `mkdir
tasks/<basket>/<id>/` (`bp` for Blueprint/asset/editor deliverables, `cpp`
for C++ source deliverables),
drop the entries below, and every enumerator (`cb tasks`,
`cb eval --task`, `batch-eval --references`) discovers the task from disk.
Confirm resolution with `python -m aura_rig.tasks resolve <id>` (from
`tools/run-agent`). **The single end-to-end TODO sheet is
[docs/TASK-AUTHOR-GUIDE.md](docs/TASK-AUTHOR-GUIDE.md)** —
start there. (Two internal Claude Code skills used to automate the two halves of
that flow; they are not part of this release, so the checklist and the guides
below are the whole authoring path.) The narrative guide is
[docs/TASK-AUTHOR-GUIDE.md](docs/TASK-AUTHOR-GUIDE.md); the normative spec
format is
[docs/AUTHORING_TEMPLATE.md](docs/AUTHORING_TEMPLATE.md).

**The task folder** (`tasks/<set>/<id>/` — layout contract:
[tasks/README.md](tasks/README.md)):

| entry | contract |
|---|---|
| `task.md` | The spec: a **v2 front-matter block** (`--- id/layers/fixtures/… ---`) + markdown body, per the authoring template; the front-matter `id:` MUST equal the folder name. |
| `reference/` | The PASS oracle — mirrors agent-writable prefixes only (`Source/CraftBenchTemplate/...`, `Content/...`), exactly like a submission overlay. |
| `discrimination/` | One `<variant>/` submission overlay per anti-gaming variant + `MATRIX.md` (one row per submission: expected verdict + the NAMED assertion; the reference row points at `../reference`). |
| `ue-config/` *(optional)* | Per-task `Config/*.ini` overlay fragments — verifier-owned, applied at verify staging and before live drives; `Config/` stays agent-denied. |

**The substrate side** — per-task UE folders are the convention;
`t0-sanity-log-on-beginplay` is the migrated template, copy its shape:

- **Scaffold** (the actor the agent extends) →
  `Source/CraftBenchTemplate/Tasks/<id>/` (the agent-writable module).
- **Fixture** (the L2 `ACraftBenchFunctionalTest` subclass) →
  `Source/CraftBenchTests/Tasks/<id>/` (the verifier-only module). Edits there
  are review-gated on commit and only take grading effect once
  committed — the runner materializes the graded substrate from git HEAD.
- **Map** → commit the binary `Content/Maps/<id>/L_<Map>.umap` (author
  in-editor or via aura-mcp) — the committed binary is the **only** map source;
  a missing binary is an explicit L2 FAIL (scaffolders retired 2026-07). Add
  the map's row to `docs/MAPS.md`. The runner derives the L2 automation filter
  itself (`Project.Functional Tests.Maps.<id>.<Map>.<ClassNoAPrefix>` for
  foldered maps).
- **Asset baselines** (a broken/starter `.uasset` the task ships) →
  `Content/Tasks/<id>/`.
- Both modules' `Build.cs` already do `PrivateIncludePaths.Add(ModuleDirectory)`,
  so sources under `Tasks/<id>/` see the flat-module headers — nothing to wire.

**Validate before you call it done:**

```sh
cb discriminate --task <id>       # reference PASS; empty + each variant FAILs at its NAMED assertion
cb batch-eval --references all    # the full-set gate still passes (all committed references)
```

---

## Check your machine: `cb doctor`

`cb doctor` is **read-only** and prints per-tier readiness (grade-only /
agent arms) with a fix hint per blocker. It mutates nothing, so a grade-only
user can safely ignore every key-related warning.

```sh
cb doctor          # or  .\tools\run-agent\cb.cmd doctor  /  ./tools/run-agent/cb doctor
```

---

## Secrets (`.env`) — only for the agent tiers

Grading needs **no secrets**. For the agent arms, `cp .env.example .env` at the
repo root and fill in:

- **`ANTHROPIC_API_KEY`** — the `claude-p` and `unreal-mcp` arms (both drive the
  `claude` CLI).
- **`OPENROUTER_API_KEY`** — only for the `openrouter:<provider/model>` baseline.
  Sent as the Bearer token — don't wrap it in quotes.

That is the entire list. There is no vendor login, no service account and no
second checkout anywhere in it: the `aura-mcp` arm, which is the only thing that
ever needed one, is disclosed but **not runnable** from this repository and
`cb` refuses its slug in the first second rather than asking you for a
credential it could not use. Almost everything else auto-detects. `.env` is
gitignored; `.env.example` is the authoritative list of every variable.

---

## Troubleshooting

**Most of this table is now auto-detected**: every eval-family command opens with
a ~2s preflight gate (`aura_rig/envgate.py`) that catches the known environment
failures (Live Coding mutex, MAX_PATH workdir, RAM/C3859, a missing UE root, a
missing API key for the tier you asked for) and prints the one-line fix before
anything is built or spent. Read the gate's output first; this table is the
deep version.

| Symptom | Cause / fix |
|---|---|
| **`cb: command not found` / `not recognized`** | Run `.\cb <cmd>` / `./cb <cmd>` from the repo root (the shims always work), or re-run `setup.ps1` — it pip-installs the `cb` console script and reports the Scripts dir to add to PATH if `cb` still doesn't resolve. **For grading you don't need `cb` — use `run_task.py`.** |
| **`no working Python 3.11+ found` / `'py' is not recognized`** | `cb.cmd` tries `py -3.12` → `py -3` → `python` → `python3` and uses the first working 3.11+. Install Python 3.11+ (3.12 recommended), **or** `set CB_PYLAUNCH=<exe>` to pin one. The launcher prints this exact hint if no interpreter starts. |
| **`cb doctor` → UE FAIL / "UnrealEditor not found"** | UE isn't at the Epic default. `set CB_UE_ROOT=<your UE 5.8 path>` (or pass `--ue-root`). |
| **L1 build crashes on UE 5.8 (`C3859`, `0xC0000005`, or "paging file too small")** | Two UE-5.8 knobs, both handled in code: the verifier builds with **`-NoUBA`** by default (UE 5.8's Unreal Build Accelerator crashes on a dirty cross-run cache — set `CRAFTBENCH_ALLOW_UBA=1` only to re-enable). On a RAM-constrained host (≤32 GB), the parallel editor-PCH compiles can still exhaust the commit charge → cap UBT with `CRAFTBENCH_L1_MAX_PARALLEL=2` (`.env.example` warns that `4` can still overflow; `4` is only safe on a host with nothing else running). See `.env.example` and `tools/verify-single/layers/l1_build.py`. |
| **`'git' not found` / `'tar' not found`** | The substrate-from-git pipe needs both. Install Git for Windows (ships both) or pass `--substrate-from-live` to grade the live working tree instead. |

**Quickest way to get unblocked:** paste the exact error from your first command
plus the full output of `cb doctor`, and say which tier you want.

---

## Go deeper

- **[README.md](README.md)** — what CraftBench-UE is, the three measured arms, and how the verifier works.
- **[EVALS.md](EVALS.md)** — the one-page run-book for every eval tier.
- **[docs/TASK-AUTHOR-GUIDE.md](docs/TASK-AUTHOR-GUIDE.md)** — writing and testing tasks: how to author a task spec and make it runnable.
- **[tools/verify-single/README.md](tools/verify-single/README.md)** — verifier flag reference + resolved Mac/UE 5.7 quirks.
- **[`docs/WINDOWS.md`](docs/WINDOWS.md)** — Windows platform notes (line endings, MAX_PATH, quoting).
- **[THIRD-PARTY.md](THIRD-PARTY.md)** — what in this tree is ours to license and what is not.
- **[.env.example](.env.example)** — every env var, keyed by tier (copy to `.env`; never commit `.env`).

# 04 — The Output Side: how runs become the leaderboard

> **Historical walkthrough — a dated snapshot, not a specification.** The
> autonomous local-HTTP agent path described here was superseded, and the
> commercial-product lane that replaced it is not part of this public release.
> Read this file for the **deterministic** path only; where it and the code
> disagree, the code wins.

> **Scope.** This is the *aggregation* half of CraftBench. The harness (section 03)
> runs one **product × task** attempt and writes a small bundle of files into
> `runs/<run_id>/`. This section documents those files, the schema of the
> authoritative `result.json`, and how `tools/compare/compare_products.py` rolls
> many `result.json` into the per-capability grid + head-to-head. It then covers
> the live-status disk contract (`status.json` / `events.jsonl`) and the
> read-only `tools/dashboard` that consumes all of it.
>
> Everything here is **pure-stdlib, read-only Python** — no UE, no network, no
> API key. You can run all of it on the `result.json` files alone.

---

## 1. Purpose

CraftBench's headline question is **"which product is strong at what"** (spec
SC-003). A *product* is a `<tool_layer>:<model>` slug — e.g. `claude-p:opus`
(the Baseline), `openrouter:openai/gpt-4o-mini` (a non-Anthropic model on the same
generalist baseline backend), `aura-mcp:claude-sonnet-4-6`. The same scrubbed
tasks are run across products; each `(product × task)` attempt produces one
`result.json`. The `cb matrix` command runs a `{model} × {task}` cross product over
the **baseline** backends (`claude-p`, `openrouter` — no Aura needed) and rolls the
cells up into a leaderboard. The output side answers the headline by:

1. mapping each `result.json` → a `(product, task, capability, pass/fail)` record,
2. bucketing tasks by **capability** (so a product can't win just by being good at
   an oversampled bucket), and
3. distinguishing **true head-to-heads** (same task run by ≥2 products) from
   capability rows that merely *aggregate disjoint tasks*.

The gate is the **deterministic** `overall` (`PASS`/`FAIL`/`FAIL_NO_EDITS`). The
R2 LLM-judge advisory is reported *alongside* but **never folded into the
pass-rate** — this is FR-020d, enforced structurally throughout this pipeline
(`compare_products.py:10-14`).

---

## 2. The `runs/<run_id>/` directory layout

There are **two distinct producers** that write into `runs/`, and they do **not**
write the same files. This is the single biggest trap for a newcomer (see §8.1).

### 2a. The canonical harness (`run.py` / `run_batch.py`) — writes `result.json`

This is the path the aggregation pipeline reads. A completed run directory
(nested one level under a per-backend folder by default — `runs/claude-p/`,
`runs/openrouter/`, ... — one directory per backend; pre-2026-07 runs and
explicit `--run-dir` callers sit elsewhere, which is fine: discovery is a
recursive `runs/**/result.json` glob):

```
runs/<backend>/<run_id>/
  result.json          ← AUTHORITATIVE. the (product,task)→verdict record. §3.
  verifier_stdout.txt   ← report.py::render_text() dump; the ONLY place per-layer
                          L1/L2/L2I detail survives on disk. §3c.
  status.json           ← live rolling state (one object, atomically rewritten). §5.
  events.jsonl          ← append-only tool-by-tool tape (one JSON object/line). §5.
  submission/...         ← the agent's writable-tree output (Source/, Content/Tasks/, …)
```

`run_id` convention is `YYYYMMDD-HHMMSS-<task>-<product-slug>` — the 15-char
`YYYYMMDD-HHMMSS` prefix is parsed back into `started_at` by the dashboard
(`collect.py:242`, `_parse_started_at` at `:245`). A `run_id` whose prefix doesn't
parse simply yields `started_at = None` (sorts earliest).

### 2b. Retired: the vendor-product runs that wrote only `summary.json`

Two arms once wrote a **different** file set from the canonical harness —
`summary.json` plus `trace.jsonl`, `trace.md`, `report.html`, `prompt.txt`, and
**no `result.json`** — under `runs/<backend>/<task>-<ts>/`. Both were vendor
lanes (the browser-drive of a proprietary product, and an earlier
local-HTTP autonomous loop) and neither is part of this release; their run CLIs
are gone from `aura_rig/`.

The shape is worth keeping in mind anyway, because it is the failure mode any
new arm can reintroduce: those `summary.json` files used a *different* `model`
convention (a bare model key like `"sonnet-4.6"`) than the arm slug the
aggregator keys on, so the compare/dashboard pipeline simply **could not see
those runs** — the runs existed, graded correctly, and were invisible on the
leaderboard. An arm that does not emit a slug-bearing `result.json` is an arm
that will silently not appear. For multi-model comparison that *does* feed the
leaderboard, see `cb bench` / `cb matrix` over the `claude-p` / `unreal-mcp` /
`openrouter` arms — §1.

---

## 3. The `result.json` schema (the authoritative record)

Emitted by two equivalent code paths that deliberately share a shape:
`run.py::_write_result` (`run.py:469-487`) and `run_batch.py::_build_result_obj`
(`run_batch.py:168-186`). The batch path writes it atomically via
`run_events.write_result_json` (tmp + `os.replace`, `run_events.py:223-233`).

```jsonc
{
  "run_id": "20260602-100000-gp-alpha-claude-p-opus",
  "task":   "tasks/gp-alpha.md",          // path or id; .stem is the join key
  "model":  "claude-p:opus",              // the PRODUCT SLUG. the join key. §3a.
  "overall": "PASS",                      // PASS | FAIL | FAIL_NO_EDITS. UPPERCASE. §3b.
  "agent": {                              // null if the agent step produced nothing
    "exit_code": 0,
    "duration_s": 42.7,
    "summary": "…one-line agent summary…",
    "tool_use_count": 12,
    "mcp_tool_use_count": 0,
    "tool_names": ["Write", "Edit", …],
    "cost_usd": 0.30,                      // None on older runs (no telemetry)
    "num_turns": 7
  },
  "verifier": null,                       // the verify-single Report dict — see §3c
  "error": "…"                            // present ONLY on harness error/timeout
}
```

### 3a. `model` is the join key — and the skip rule

`model` is the **product slug**, and it is the field everything joins on. A
`result.json` **without a non-empty `model` is silently dropped** by both the
aggregator (`compare_products.py:62-63`) and the dashboard
(`collect.py:312-314`). This is *the same rule in two places* and it exists to
exclude the legacy `runs/aura-smoke-*/iter-*/result.json` files, which use an
unrelated `iteration/ok/blocker` schema. The slug is split as
`tool_layer, _, model = product.partition(":")` (`collect.py:318`) — `claude-p` is
itself the Baseline product's `tool_layer`.

### 3b. `overall` — the casing trap

`result.json.overall` is **UPPERCASE** (`PASS`/`FAIL`/`FAIL_NO_EDITS`), whereas a
verify-single `report.overall` (inside `verifier`) is **lowercase**
(`pass`/`fail`). They are never compared naively — `passed` is computed *only* from
`overall.upper() == "PASS"` (`model.py:18-20` comments this trap explicitly;
`collect.py:320`, `compare_products.py:76`). `FAIL_NO_EDITS` is the sentinel for an
empty submission (agent wrote nothing) and is counted separately from `FAIL`
(`model.py:261-266`).

### 3c. `verifier` is null in practice — and where detail actually lives

`verifier` is *meant* to carry the full verify-single `Report.to_dict()`
(`report.py:74-87`): `task_id`, `submission_sha`, a `layers` map of per-layer
`LayerReport`s (`status`, `exit_code`, `tests_passed/tests_run`,
`warnings_in_agent_files`, `notes`, `log` — `report.py:15-34`), `duration_seconds`,
`ue_version`, `host`, `sandbox_violations`, and the optional **`r2_advisory`** block.

**But it is `null` in every current product run** (dashboard README,
`collect.py:18-22`, `model.py:120`): the harness only embeds the report if
verify-single's `out/report.json` survives, and verify-single deletes its tempdir —
so the embedded report is gone even on PASS. The coarse top-level `overall` is
therefore the only authoritative signal, and per-layer L1/L2/L2I detail survives
**only as rendered text** in the sibling `verifier_stdout.txt` (the
`report.py::render_text()` dump, `report.py:96-131`). `collect.py` *text-parses*
that file (§6c). Because `verifier` is null, the R2 `advisory_score` is `null`
everywhere today — the field is modeled forward-compat; **the UI must not imply R2
ran**.

The **`r2_advisory`** block, when present, carries `advisory_score`, `confidence`,
and crucially `gating: false` / `NON_GATING: true`. The non-gating invariant is
*executable*: `Report.__post_init__` (`report.py:68-72`) refuses to construct a
report whose `r2_advisory.gating` is true. The judge that produced it never saw
`overall` (anti-anchoring firewall, `report.py:62-65`).

---

## 4. The aggregator: `tools/compare/compare_products.py`

Pure stdlib, ~280 lines, no UE/network (`compare_products.py:16`). It is the
*single source of aggregation math*; the dashboard imports it and does **zero**
matrix math of its own (§6).

### 4a. Data flow (inputs → outputs)

```
result.json files                          tasks/<id>.md (capability_bucket)
        │                                            │
        ├── load_result()  ───── RunRecord ──────────┤   (parses capability via regex)
        │   :53-79                                    │   _capability_for() :44-50
        ▼                                             ▼
   list[RunRecord]  ──── aggregate() ────►  Comparison  ──┬─ render_markdown()  → stdout
                          :141-166          (cells +      └─ to_dict()           → --out JSON
                                            task_cells)
```

- **`load_result(path)`** (`:53`) parses one `result.json` → a `RunRecord`
  (`:34-41`: `product`, `task_id`, `capability`, `passed`, `advisory_score`,
  `cost_usd`). Returns `None` (skip) if `model` is empty (§3a) or the file is
  unreadable. `advisory_score` is pulled from `verifier.r2_advisory.advisory_score`
  if present (`:66-70`) — informational only.
- **`_capability_for(task_path)`** (`:44`) reads the task's `.md` and regex-greps
  the `- capability_bucket: <x>` line (`_CAP_RE`, `:30`), resolving the path
  relative to repo root; returns `"uncategorized"` if absent.
- **`aggregate(records)`** (`:141`) builds the `Comparison`: a `cells` map keyed
  `(capability, product) → Cell`, **and** a parallel `task_cells` map keyed
  `(task_id, product) → Cell` for head-to-head, plus `task_caps` (`task_id →
  capability`). A `Cell` (`:82-95`) accumulates `n`, `n_pass`, the list of
  `advisories`, and summed `cost`; `pass_rate = n_pass/n`.

### 4b. The two-axis output — and "grounding"

The headline table is **capability × product → `n_pass/n (pass-rate)`**, with the
R2 advisory mean appended *informationally* (`render_markdown:169-189`). Each
capability row gets a **leader** — the product with the best
`(pass_rate, mean_advisory)` (`Comparison.leader`, `:116-121`).

The key correctness idea is **grounding** (`is_grounded`, `:134-138`): a capability
row is only a *real* comparison if **≥1 of its tasks was run by ≥2 products**.
Otherwise the row's cells aggregate *disjoint tasks* (product A ran task X, product
B ran task Y — they never competed) and the "leader" is meaningless. Ungrounded
rows are flagged with ⚠ and their leader cell prints `_n/a_` (`:178`, `:186`).

The **Head-to-head** section (`render_markdown:191-205`) lists only
`shared_tasks()` — tasks run by ≥2 products (`:130-132`) — as `task × capability ×
per-product pass-rate`. This is the *only* apples-to-apples view. If no task has ≥2
products, the section prints an explicit "_every capability cell above aggregates
disjoint tasks_" warning (`:194-196`).

The **Per-product capability profile** (`:207-217`) classifies each product's
capabilities into strong (pass-rate ≥ 99.9%), weak (≤ 0.1%), and partial.

### 4c. The JSON form (`to_dict`, `:221-242`)

`--out` writes a `craftbench.compare/v1` object: `products`, `capabilities`,
`cells` (only `n>0`), `leaders`, `head_to_head`, and `ungrounded_capabilities`.
This is what the dashboard re-serves verbatim.

### 4d. How to run it

```sh
# all runs under runs/
python3 tools/compare/compare_products.py --runs-dir runs --out compare.json

# or specific files
python3 tools/compare/compare_products.py runs/A/result.json runs/B/result.json
```

`--runs-dir` globs `<dir>/**/result.json` (`collect_result_paths`, `:245-249`).
Exit 2 if nothing readable; skipped non-product files are reported on stderr
(`main`, `:252-272`). Tests: `cd tools/compare && python3 -m unittest tests.test_compare`.

---

## 5. The live-status disk contract (`status.json` + `events.jsonl`)

This is the *in-flight* contract, written by the harness while a run is executing
and tailed read-only by the dashboard's live view. Schema tag
`craftbench.livestatus/v1`. The **writer** lives in `run-agent/run_events.py`; the
**reader** in `dashboard/live.py`. The two are coupled **by name only** — the reader
never imports the writer, so an adapter in any language can satisfy the contract
(`live.py:22-25`).

### 5a. `status.json` — one rolling, atomically-rewritten full-state object

`FileEventSink.status(**fields)` (`run_events.py:157-162`) merges fields into an
in-memory mirror and rewrites the *whole* object atomically (tmp + `os.replace`,
same-dir rename → atomic on POSIX, `:91-116`), always bumping `updated_at`. The
full key set (`STATUS_FIELDS`, `:41-58`): `schema`, `run_id`, `task_id`, `product`,
`phase`, `step`, `max_steps`, `current_tool`, `tool_count`, `tokens_in`,
`tokens_out`, `started_at`, `updated_at`, `elapsed_s`, `result`, `error`.

The **`phase`** enum drives the run lifecycle and is sequenced by `run_batch.py`
(`:404-477`): `queued → launching → running → grading → done` (with `error` /
`timeout` / `cancelled` as terminal alternatives). Reader semantics
(`live.py:38-43`):
- `_TERMINAL_PHASES = {done, error, timeout, cancelled}` — excluded from the Active
  panel (the run reappears in the post-hoc matrix once `result.json` lands).
- `_STALE_PHASES = {running, launching}` — only here does an old `updated_at`
  flag the run **stale** (the killed-orchestrator signal); `queued`/`grading` are
  not heartbeated, so a stale timestamp there is *expected*, not an error.

### 5b. `events.jsonl` — append-only tool tape

`FileEventSink.emit(event)` (`run_events.py:140-153`) appends one JSON object per
line, stamping a sink-owned monotonic `seq` (from 1) and a `ts`. Any
caller-supplied `seq`/`ts` is **overwritten** so the tape stays authoritative.
Opened per-call so a killed orchestrator still leaves a complete, flushed tape.
`tail_events(run_dir, after_seq)` (`live.py:224-258`) returns lines with
`seq > after_seq`, skipping blank/garbage/torn-final lines.

### 5c. The torn-read ordering invariant

`result.json` is written **before** `status.json.phase` flips to `done`
(`run_events.py:14-17`, `run_batch.py:24` / `:36`, sequence at
`run_batch.py:465-470`). So any reader that sees `phase == done` can always find a
complete matrix entry — closing the window where a reader sees "done" but no
result yet. The reader side is **best-effort everywhere**: a torn atomic-rewrite, a
missing file, or a garbage line is *skipped, never raised* (`live.py:18-19`,
`active_runs:194-211`).

> **On-disk reality check.** The recent runs are Aura runs (`summary.json`-based,
> §2b — one `runs/<backend>/` directory per backend)
> and old matrix submissions, so `runs/` may carry **zero** `status.json` /
> `events.jsonl` files. The contract is fully implemented and unit-tested but the
> live panel has no live data when the tree holds only Aura-rig output.

---

## 6. The dashboard (`tools/dashboard/`) — read-only consumer

A read-only visualization over what's on disk. **Through v1 strictly read-only;
v1.5 added exactly one web-only write action** (Launch-a-run, §7). The data layer
(`model.py` + `collect.py`) is **pure stdlib** — importable and testable without
`textual`/`fastapi` installed.

### 6a. What it reads

`collect(repo_root)` (`collect.py:360-400`) is the SINGLE entry point both UIs call.
It globs:
- `runs/**/result.json` → parsed into `Run` rows (`parse_run`, `:300-352`),
- `runs/<id>/verifier_stdout.txt` → text-parsed into `Run.layer_results` (§6c),
- `tasks/*.md` (**non-recursive**) → `Task` rows (`parse_task`, `:140-155`),
  mirroring `run_task.py`'s H2-section/metadata parsing primitives.

It **never** launches a run, shells out, or writes. The live view (`live.py`)
separately globs `runs/*/status.json` plus `runs/*/*/status.json` (the
per-backend folders — bounded depths, not `**`) and `events.jsonl`.

### 6b. The frozen data model (`model.py`)

All `@dataclass(frozen=True)` so a `Snapshot` is shareable across the watcher
thread and request handlers without copying. Key types:
- `Run` (`:94-138`) — one `(product × task)` attempt. Carries the full `product`
  slug **and** derived `tool_layer`/`model` halves, `overall`, `passed`,
  `started_at`, `duration_s`, `cost_usd`, a **synthesized** `blocker` (a "why not
  PASS" string — *not* a schema field, derived in `collect._derive_blocker`,
  `:270-287`), and `layer_results`.
- `Task` (`:63-91`) — `task_id`, `title`, `capability_bucket`, `tier`, `set_name`,
  declared `layers`, `prompt_excerpt`.
- `Snapshot` (`:148-371`) — the immutable disk view: `tasks`, **all** `runs` (no
  dedupe), `products`, `capabilities`.

### 6c. The aggregation bridge — dashboard does ZERO matrix math

`Snapshot.comparison()` (`model.py:173-204`) is the **only** method that imports a
non-stdlib intra-repo module: it converts each `Run` → a `compare.RunRecord` and
calls `compare.aggregate`. The import is lazy + cached + by-basename off
`sys.path` (`_import_compare`, `:409-428`), so `model`/`collect` stay dep-free at
import time. `matrix()`, `head_to_head()`, `leaders`, `ungrounded_capabilities`
all come **verbatim** from `compare.to_dict` (`to_dict`, `:345-371`); only
`coverage_gaps`/`totals`/`task_progress` are dashboard-only derived views.

The `latest_only` flag (default **False** everywhere = all-attempts, matching
`compare.aggregate`'s n-counting) optionally dedupes duplicate `(product, task_id)`
attempts to the newest `started_at` *before* aggregating (`_dedupe_latest`,
`:374-389`), so a re-run sweep doesn't inflate `n`.

### 6d. The web payload + live refresh

`Snapshot.to_dict()` (`:345-371`) is the `craftbench.dashboard/v1` payload served
at `GET /api/snapshot`. `watch()` (`collect.py:436-463`) polls a fingerprint
(max-mtime + the *set* of watched paths, so an add/delete at equal mtime still
fires — `_fingerprint`, `:415-433`) and re-`collect()`s on change. Pure-stdlib
mtime polling, no `watchdog`.

### 6e. `verifier_stdout.txt` text-parsing (best-effort)

Because `verifier` is null on disk (§3c), the per-layer L1/L2/L2I/L3/ART/R2 detail
is recovered by *parsing the rendered text* in `verifier_stdout.txt`
(`parse_verifier_stdout`, `collect.py:186-234`). It matches lines like
`  L1  : PASS [exit=0, warn=4] log=…` (`_LAYER_LINE_RE`, `:166-171`), normalizes
UPPERCASE status → lowercase enum (`_STATUS_MAP`, `:176-183`; `SKIPPED → skip`),
and attaches indented `- note` lines. **By contract this is best-effort**: an
absent/empty file (every `FAIL_NO_EDITS`) or any parse surprise yields `[]` and the
coarse `overall` stays authoritative.

### 6f. Other files in the dir (FYI)

- `render.py` — pre-existing **single-run** HTML report generator (the rich
  banner + agent submission + per-layer log report). v1.5's web drill-in re-uses
  it via `web/report_bridge.py` (`GET /api/run/{run_id}/report`), not the matrix
  pipeline.
- `tui.py` — Textual TUI (read-only); `web/` — FastAPI app; `serve.py` — the
  older agent-loop demo server; `live.py` — the §5 live reader; `README.md`
  — the design + run instructions (a `DESIGN.md` sibling was internal
  working material and is not part of this release).

### 6g. How to run / observe

```sh
# data-layer tests (no deps):
python3 -m unittest tools.dashboard.tests.test_collect

# full suite (web by DOTTED module paths — discover -s breaks web/ rel-imports):
python3 -m unittest \
  tools.dashboard.tests.test_collect tools.dashboard.tests.test_tui \
  tools.dashboard.web.tests.test_app tools.dashboard.web.tests.test_report_bridge \
  tools.dashboard.web.tests.test_launcher

# UIs (need: pip install -r tools/dashboard/requirements.txt):
python3 -m tools.dashboard.tui [--repo-root <path>]
python3 -m tools.dashboard.web [--repo-root <path>]   # then GET /api/snapshot
```

---

## 7. v1.5 — the one write action (Launch-a-run)

The web app's **⚡ Launch a run** panel POSTs `/api/launch`, which spawns one
`(task × model)` job via the canonical `tools/run-agent/run.py`, returns a
`job_id`, and the UI polls `/api/jobs/{job_id}`. When the job lands a new
`runs/<id>/result.json`, the matrix updates on the next refresh — closing the
"launch → run lands → leaderboard updates" Agent-Loop. Safety (in
`web/launcher.py`): **argv-only** (no shell), validate-before-spawn (`task_id` must
resolve to a real `tasks/*.md`; `model` must match
`^(claude-p|unreal-mcp|aura-mcp|openrouter|bare):[A-Za-z0-9._-]+$`), injectable
runner command (tests inject a fake echo). The **TUI stays fully read-only.**

---

## 8. Non-obvious gotchas that will bite a newcomer

1. **Two producers, only one feeds the leaderboard.** The canonical harness
   (`run.py`/`run_batch.py`, and `cb matrix` over the baseline backends) writes
   `result.json`; the **Aura rig writes `summary.json`** with a *different* `model`
   convention (`"sonnet-4.6"`, not a `<layer>:<model>` slug) — this is true of both
   every `runs/<backend>/` path, current or deprecated.
   So a `runs/` tree of only Aura runs makes `compare_products.py --runs-dir runs`
   and the dashboard matrix show **nothing**, and the live panel has no `status.json`
   to read. Bridging an Aura `summary.json` → a slug-bearing `result.json` does not
   exist in this tree; don't assume the leaderboard is auto-populated from Aura runs.
2. **`model` empty ⇒ silently skipped.** The skip rule lives in *two* places
   (`compare_products.py:62`, `collect.py:312`). A run with a typo'd or missing
   `model` just vanishes from every view — no error, no warning beyond compare's
   stderr count.
3. **The casing trap is real.** Top-level `overall` is UPPERCASE; nested
   `verifier.overall` (if it ever survives) is lowercase. Use `overall.upper() ==
   "PASS"`; never compare the two naively.
4. **`verifier` is null ⇒ R2 advisory is null ⇒ per-layer detail is text-only.**
   Anything richer than `overall` is *parsed from rendered stdout*, by contract
   best-effort, `[]` on any surprise. Don't build logic that *requires* the
   structured `verifier` block — it isn't there.
5. **"Leader" without grounding is a lie.** A capability row can show a leader even
   when no two products ran the same task. Always check the ⚠ flag /
   `ungrounded_capabilities` before quoting a winner. The head-to-head section is
   the only true comparison.
6. **all-attempts vs latest-only.** `collect()`/`compare.aggregate` count **every**
   attempt by default — a re-run sweep inflates `n` and `pass_rate`. Pass
   `latest_only=True` to dedupe to the newest `(product, task)` attempt. The two
   give different numbers; know which one a chart is showing.
7. **Atomic-write ordering is load-bearing.** `result.json` lands *before*
   `status.json.phase = done`. If you ever reorder those writes you reopen the
   torn-read window (a reader sees "done" with no matrix entry).
8. **`active_runs` globs `runs/*/status.json` + `runs/*/*/status.json` (two
   bounded levels — flat + per-backend folders); `collect` globs
   `runs/**/result.json` (fully recursive).** A run dir nested DEEPER than two
   levels (e.g. matrix `cells/**` or bench `reps/**`) is found by `collect`
   but *not* by the live panel.
9. **Tasks glob is non-recursive** (`tasks/*.md`). A task under a subfolder (e.g.
   `tasks/<set>/<id>/task.md`) is **not** parsed by `collect`, so its
   `capability_bucket` is unknown and runs against it bucket as `"uncategorized"`.
10. **`cost_usd` / telemetry can be `None`.** Older runs (and the `_num` finite-
    guard against `NaN`/`Inf`, `collect.py:257-267`) mean cost roll-ups must be
    None-tolerant; `totals()` only sums present values.

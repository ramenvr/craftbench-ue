# CraftBench dashboard

A dashboard over what CraftBench has written to disk. It visualizes runs and
tasks and lets you drill into any single run's full report.

> **Boundary change at v1.5.** Through v1 the web app was strictly read-only. As
> of **v1.5** the web app gains **one write action** — the *Launch a run* panel,
> which spawns a real `tools/run-agent/run.py` job. Everything *else* is still
> read-only: the data layer (`collect.py` / `model.py`), the matrix, the
> report-bridge, and the JSON/SSE routes never launch anything or write under
> `runs/` / `tasks/` / `UE-projects/`. The launch action is gated, argv-only, and
> input-validated (see *v1.5* below). The **TUI remains fully read-only** — the
> launch capability is web-only.

CraftBench runs the **same** scrubbed tasks across **products** (a product is a
`<tool_layer>:<model>` slug, e.g. `claude-p:claude-opus-5` — the Baseline — or
`unreal-mcp:claude-sonnet-5`) and scores each with a deterministic verifier. The
dashboard reads those results and answers "which product is strong at what."

The **viewer** shows every product it finds in `runs/`, including arms this
repository can no longer drive (`aura-mcp`, and the removed private lanes) — a
historical run set stays fully readable. The **launcher** is narrower on
purpose: it offers only the four routes a clone can actually run (see *v1.5*).

## Architecture

```
tools/dashboard/
  model.py      frozen dataclasses (LayerResult, Task, Run, Snapshot) + the
                compare bridge. PURE STDLIB.
  collect.py    collect(repo_root) -> Snapshot, and watch(). Disk I/O, the
                skip rule, the verifier_stdout.txt text parser, and the task
                parser (mirrors tools/verify-single/run_task.py). PURE STDLIB.
  live.py       the live "Active runs" contract (status.json readers). PURE
                STDLIB.
  render.py     the single-run report renderer (report.html). PURE STDLIB.
  requirements.txt   UI deps only (textual, fastapi, uvicorn, httpx) — the data
                     layer imports none of them.
  tui.py        Textual TUI (read-only).
  web/          FastAPI web API + static client (the one write action).
```

Both UIs sit on **one shared data layer** (`model.py` + `collect.py`). That layer
is pure stdlib so it is importable and unit-testable without `textual` or
`fastapi` installed. The single entry point is:

```python
from tools.dashboard.collect import collect
snapshot = collect(repo_root)        # repo_root = the dir containing runs/ + tasks/
payload  = snapshot.to_dict()        # the JSON served at GET /api/snapshot
```

`repo_root` is the checkout root; both UIs resolve it as
`pathlib.Path(__file__).resolve().parents[2]` with an optional `--repo-root`
override.

## Two important caveats (what's actually on disk)

1. **New runs embed the verifier report; old runs don't.** The harness now pins
   the verify-single report into the run dir (`--report-json`) and embeds it at
   `result.json.verifier` / `summary.json.verifier`, so the per-layer machine
   contract survives. On **old runs** `verifier` is `null` even on PASS (the
   report used to live in a tempdir verify-single deleted). Either way the coarse
   `result.json.overall` (`PASS` / `FAIL` / `FAIL_NO_EDITS`, UPPERCASE) remains
   the **authoritative** pass/fail signal.

2. **Per-layer L1/L2/L2I/L3/ART/R2 detail prefers the embedded report.**
   `collect.py` builds `Run.layer_results` from `result.json.verifier` when
   present; for old runs (verifier `null`) it falls back to **text-parsing**
   `runs/<id>/verifier_stdout.txt` (the `report.py::Report.render_text()` dump) —
   best-effort by contract: an absent/empty file (every `FAIL_NO_EDITS`, and any
   run whose verifier text wasn't captured) yields `layer_results == []`, and any
   parse surprise also degrades to `[]` while `overall` stays authoritative.
   `advisory_score` (R2) is still `null` everywhere today; the field is modeled
   forward-compat — **the UI must not imply R2 ran**.

**Capture artifacts.** A run may also carry `runs/<id>/artifacts/*.png` — the
assert-free checkpoint screenshots a `--capture` eval sweeps in. `collect()`
attaches the sorted basenames as `Run.artifacts` (`[]` default), the web app
serves each at `GET /api/run/{run_id}/artifact/{name}` (validated against the
collected list — no path traversal), and the single-run report modal renders
them as thumbnails in its Artifacts section.

Aggregation (per-capability pass-rate matrix, head-to-head, leaders, grounding)
is delegated **verbatim** to `tools/compare/compare_products.py` — the dashboard
does zero matrix math. `collect()` returns **all** attempts (no dedupe); the
matrix/head-to-head accessors take `latest_only=True` to dedupe duplicate
`(product, task)` attempts to the newest `started_at` before aggregating.

Non-product `result.json` files (e.g. `runs/aura-smoke-*/iter-1/`, which use a
different `iteration/ok/blocker` schema) are skipped: any `result.json` without a
non-empty `model` is dropped — the same rule `tools/compare` uses.

## Running the tests (no deps required)

The data layer is pure stdlib; its tests need nothing installed:

```sh
cd <repo-root>
python3 -m unittest tools.dashboard.tests.test_collect
```

The suite uses synthetic `tasks/` + `runs/` in a tempdir and pins the
`verifier_stdout.txt` format with a golden fixture (so a `report.py` rendering
change is caught here, not silently in production).

Everything (data layer + TUI + web) runs in one discovery pass — the command CI
uses:

```sh
python3 -m unittest discover -v -s tools/dashboard -t .
```

`-t .` is load-bearing: it keeps the repo root as the top-level dir, so tests
import as `tools.dashboard.web.tests.test_app` and the `web/` package's relative
imports resolve. Drop it and every `web/` module fails at import. Individual
suites still run by dotted module path:

```sh
python3 -m unittest \
  tools.dashboard.tests.test_collect \
  tools.dashboard.tests.test_render \
  tools.dashboard.tests.test_live \
  tools.dashboard.tests.test_tui \
  tools.dashboard.web.tests.test_app \
  tools.dashboard.web.tests.test_report_bridge \
  tools.dashboard.web.tests.test_launcher
```

The `test_launcher` suite injects a fake echo command, so it exercises the full
job lifecycle + input validation + no-shell-injection **without** spawning
`run.py` or UnrealEditor.

## Running the UIs

Install the UI deps first (the data layer needs none of these):

```sh
pip install -r tools/dashboard/requirements.txt
```

Then, from the repo root:

```sh
# Textual TUI
python3 -m tools.dashboard.tui [--repo-root <path>]

# Web API + client (uvicorn ASGI server)
python3 -m tools.dashboard.web [--repo-root <path>]
# then open the printed http://127.0.0.1:<port>/ ; GET /api/snapshot for the JSON
```

Both refresh live via `watch()` (stdlib mtime polling, no `watchdog`); `collect()`
is always the on-demand source of truth.

## v1.5 — single-run report drill-in + launch a run (web app)

Two features extend the web app. Neither touches the pure-stdlib data layer.

### 1. Single-run report drill-in (read-only)

Clicking any matrix cell (or a failure card) now opens the **full self-contained
single-run report** in an iframe modal (also "open in new tab") instead of the
small JSON detail. The report is the *same* rich HTML that `render.py` writes
into a run dir as `report.html` — banner, task-spec excerpts, agent submission
files, and per-layer verification log excerpts.

- Route: `GET /api/run/{run_id}/report` → an `HTMLResponse`.
- It re-uses `render.py` via `web/report_bridge.py` (no report HTML is
  reimplemented). The bridge maps `runs/<id>/result.json` to `render_html`'s
  inputs exactly as `render.py:main()` does for a directory.
- **Degrades gracefully.** Current `run-agent` runs have `verifier: null` and no
  live verifier workdir; the bridge synthesizes a minimal banner from the
  top-level `overall` so the page still shows task id + outcome, and passes
  `workdir=None`. It never crashes on missing optional inputs.
- **Status:** `200` rendered · `404` unknown run_id (incl. path-traversal ids,
  which the bridge rejects as unknown) · `500` corrupt `result.json`. The route
  always returns a real HTML page, so the iframe shows *something* either way.

The older `GET /api/run/{run_id}` JSON route and its lightweight modal still
exist as a fallback; the default click is now the full report.

**Scene stills (the live `--preview` bundle).** When a run has
`runs/<id>/preview/` next to its envelope, the report grows a **"Scene stills"**
section — hero + the remaining stills + `surround.mp4` in a native
`<video controls loop muted>` block — carrying the mandatory
`EDITOR SCENE — not runtime` disclosure and, on a `partial`/`error` capture, a
"Capture did not complete" line above the frames it salvaged. Both surfaces
share the renderer. Nothing is written back to
`summary.json`/`result.json`. Non-gating: no
material — or a half-written bundle — means no section and a byte-identical
page.

### 2. Launch a run (the ONE write action)

A clearly-labelled **⚡ Launch a run** panel (collapsed by default) picks a `task`
(from the real specs on disk, both layouts) + a **route** + a `model` from that
route's own menu, with an auto-detected UE root and a `live-project` checkbox. Pressing **Launch** — behind a `confirm()` so it is never
accidental — POSTs `/api/launch`, which spawns one `(task × model)` run via the
**canonical harness** `tools/run-agent/run.py` in the background and returns a
`job_id`. The UI then polls `/api/jobs/{job_id}` and shows live status; when the
job finishes, the new `runs/<id>/result.json` it wrote shows up in the live matrix
on the next refresh. That round-trip — *launch from the dashboard → run lands in
`runs/` → matrix updates* — is the **Agent-Loop closure**.

Routes:

| route | does |
|-------|------|
| `GET /api/launch/options` | `{tasks, routes, models_by_route, ue_root_default, models, backends}` for the panel (tasks = real specs on disk; `models`/`backends` are the flat back-compat lists) |
| `POST /api/launch` | body `{task_id, route, model, ue_root?, live_project?}` → validate → spawn → `{job_id}` (`202`); bad input → `400`, **no job registered**. A full `backend:model` slug in `model` (no `route`) is still accepted |
| `POST /api/jobs/{job_id}/cancel` | best-effort terminate a running job (`404` if unknown) |
| `GET /api/jobs` | all jobs' status envelopes, newest first |
| `GET /api/jobs/{job_id}` | one job's envelope (`404` if unknown) |

**Safety scoping (non-negotiable, lives in `web/launcher.py`):**

- **Argv-only, never a shell.** The subprocess is always an argv *list* handed to
  `subprocess.Popen` with the default `shell=False`. No user string ever reaches a
  shell.
- **Validate before spawn.** `task_id` must resolve to a real task spec on disk —
  flat `tasks/[<set>/]<id>.md` or folder-form `tasks/<set>/<id>/task.md` (rejects
  traversal / made-up ids); `model` must match `launcher.MODEL_SLUG_RE`, whose
  backend alternation is exactly the four runnable backends (a test pins the
  alternation to `known_backends()` so the gate and the panel cannot drift). Two
  details that look like typos and are not: the model part admits `/` because
  `bare:` and `openrouter:` take OpenRouter `provider/model` ids, and the pattern
  is anchored with the end-of-string anchor rather than `$` — `$` also matches
  just before a trailing newline, which once let a slug with a trailing newline
  through into argv. A bad request raises *before* any process starts, so no job
  is registered.
- **Injectable runner command.** The builder that turns `(task, model, …)` into the
  argv list is a constructor parameter; production targets `run.py`, and the test
  suite injects a fake echo command so it **never spawns UnrealEditor or run.py for
  real**. One `JobManager` is stashed on `app.state` per app.
- **Only launchable lanes are offered.** The four routes are the four RUNNABLE
  `tools/run-agent/adapters/registry.py::make_adapter` branches, and nothing else:

  | route (UI) | backend | model menu | live editor? |
  |------------|---------|------------|--------------|
  | Baseline (Claude Code, no editor) | `claude-p` (registry.py:485) | native Claude ids | no |
  | Epic's in-editor MCP (live editor) | `unreal-mcp` (registry.py:514) | native Claude ids | **yes** |
  | Baseline via OpenRouter (any model) | `openrouter` (registry.py:546) | `provider/model` | no |
  | Minimal scaffold (5 file tools, no editor) | `bare` (registry.py:531) | `provider/model` | no |

  `openrouter` is the same Claude CLI pointed at another provider; `bare` is our
  own minimal loop over any OpenAI-compatible endpoint. They measure different
  things, so the panel keeps them separate — see the warning at `registry.py:534`.

  `aura-mcp` (registry.py:490) is **disclosed but not launchable** here: it still
  dispatches in the registry, but its MCP servers ship with Aura's private UE
  plugin, which is not in this repository. It and the removed private lanes
  (`aura-product`, `aura-agent`, `aura-baseline`, `aura-mcp-bridge`) are refused
  **by name** as a `400` *before any spawn*, in the same voice as
  `registry.py::_REMOVED_BACKENDS` — an operator arriving with an older slug is
  told what happened to it rather than handed a regex miss that reads like a typo.
  None of them is ever offered in the panel.

**unreal-mcp needs a live editor.** Epic's MCP server runs *inside* the editor, so
an `unreal-mcp:*` launch requires `ue_root` + `live_project=true` + a running
UnrealEditor. The launcher does **not** manage UE — if those are absent, `run.py`
itself fails and the job surfaces as `failed` with its captured log. The other
three routes write files and open no editor. Failures are surfaced honestly, not
hidden.

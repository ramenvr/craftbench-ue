# 02 — `tools/verify-single`: the deterministic verifier

> The PASS/FAIL gate. Everything in this directory is deterministic by design
> (spec FR-020d): no LLM, no rendering, no pixel comparison decides the verdict.
> An optional advisory judge (R2) can annotate the report but is firewalled from
> the outcome. This section is the end-to-end reading guide for the verifier.
>
> **⚠ Dated snapshot:** the hash manifest (`verifier_hashes.json`,
> `--regen-verifier-hashes`, exit-3 REJECT) and the map scaffolders
> (`scaffold_map.py`) described below retired 2026-07-16 / 2026-07 — integrity
> is now git-HEAD provenance + human review, and committed `.umap`
> binaries are the only map source. Read those passages as history.

---

## 1. Purpose

`tools/verify-single` answers one question: **does this agent submission satisfy
this task's behavior spec?** It does so by:

1. Materializing a clean copy of the UE 5.8 substrate (`CraftBenchTemplate`).
2. Integrity-checking the verifier-only test module against pinned hashes.
3. Sandbox-checking the submission against an agent-writable allowlist.
4. Overlaying the accepted submission files onto the substrate copy.
5. Running a set of verification **layers** (build / PIE test / asset
   introspection) selected by the task spec.
6. Emitting a machine-readable `report.json` and a human summary, and returning
   an exit code.

The orchestrator is `run_task.py`; each verification method is a pluggable
`Layer`; integrity and sandboxing are two independent defenses that run *before*
any layer.

---

## 2. The key files and what each does

| File | Role |
|---|---|
| `run_task.py` | CLI entry + orchestrator. Parses the task spec, materializes the substrate, runs the two pre-flight defenses, builds a `LayerContext`, calls `run_layers`, composes the `Report`, returns the exit code. (~1500 lines; this is the file to read first.) |
| `layers/base.py` | The `Layer` protocol + the `LayerContext` dataclass shared by all layers. |
| `layers/registry.py` | The `REGISTRY` list of concrete layer adapters (`ArtifactLayer`, `L1Layer`, `L2Layer`, `L3RenderLayer`, `L2IntrospectLayer`, `R2Layer`) and the `run_layers()` loop. |
| `layers/l1_build.py` | L1 — UBT build of both the Editor and Game targets (`run_l1`). |
| `layers/l2_pie.py` | L2 — drives an `AFunctionalTest` in PIE via `UnrealEditor-Cmd` and parses the automation result (`run_l2`). Also exports the editor-binary resolver and the marker-kill Popen helper reused by the scaffolder and L2I. |
| `layers/l2_introspect.py` | L2I — runs a verifier-owned editor-Python introspection script headlessly and parses a JSON verdict (`run_l2_introspect`). |
| `sandbox.py` | `AGENT_WRITABLE.json` enforcement. `scan_submission()` classifies each submission file accept/reject. |
| `pinning.py` / `hashes.py` | Integrity-pin machinery. `hashes.py` re-exports `run_task.verify_tests_module_integrity` as a raises-on-drift API; `pinning.py` is the separate score-report provenance collector (FR-002). |
| `report.py` | `Report` / `LayerReport` / `HostInfo` dataclasses → `report.json` + stdout text. |
| `scaffold_map.py` | Materializes a missing test `.umap` headlessly from a `Tools/scaffold_<map>.py` UE-Python scaffolder (called by `L2Layer`). |
| `asset_capture.py` | `--capture-assets` support: save-all-dirty + sweep `Content/` for `.uasset`/`.umap` deliverables. |
| `verifier_hashes.json` | The pinned SHA-256 manifest for `Source/CraftBenchTests/`, keyed by substrate name. |
| `introspect/*.py` | The verifier-owned L2I scripts (e.g. `mat_emissive_pulse.py`, `bp_collectible_coin.py`). |

---

## 3. Data flow: inputs → outputs

Inputs (CLI, `run_task.build_parser` at `run_task.py:1024`):
`--task <task.md>`, one of `--submission <dir>` / `--submission-from-project <UE-project>`,
`--ue-root <UE_5.8>`, optional `--layers`, `--r2`, `--harness`, `--model`, etc.

`main()` (`run_task.py:1259`) executes, in strict order:

```
parse_task_spec(--task)                       # run_task.py:152  → TaskSpec
  ↓
resolve substrate dir + load AGENT_WRITABLE.json (WritableManifest.load)
  ↓  [exit 2 if substrate / manifest missing, or bad flags]
(optional) extract_writable_subset_from_project()   # --submission-from-project
  ↓
make a fresh workdir + out/ dir
  ↓
1) copy_substrate()       run_task.py:822  — clone substrate into workdir
2) verify_tests_module_integrity()  run_task.py:578  — INTEGRITY  [exit 3 on drift]
3) scan_submission()      sandbox.py:152   — SANDBOX     [exit 4 on violation]
4) apply_submission()     run_task.py:882  — overlay accepted files
4b) _disable_plugin_in_uproject("Aura")  unless --harness aura
   ↓  [exit 5 if .uproject missing after copy]
5) run_layers(LayerContext)   registry.py:353  — runs applicable layers in order
   ↓
6) overall = pass iff ALL gating layers passed
   Report(...).write_json(report.json) + render_text()
   ↓
return 0 if pass else 1
```

Outputs:
- `report.json` (default `<workdir>/out/report.json`, overridable with
  `--report-json`) — schema in §5.
- Per-layer logs under `<workdir>/out/` (`l1_build.log`, `l2_pie.log`,
  `l2_introspect_<stem>.log`, `scaffold_<map>.log`, `l2_report/index.json`).
- A stdout summary (`Report.render_text`, `report.py:96`).
- An exit code (§7).

**Substrate materialization is from git HEAD by default**
(`copy_substrate` → `copy_substrate_from_git`, `run_task.py:739`): it pipes
`git archive HEAD -- <substrate-relpath>` into `tar -x`, so **only committed
files** enter the graded tree. This is the root-cause fix for the
"uncommitted disk state decides the verdict" contamination risk (stability
findings F1/F3/F4 cited in the docstring). It silently falls back to a live
copy (`copy_substrate_from_live`, `run_task.py:810`) when: not in a git
work-tree, the substrate path is untracked in HEAD, or `git archive` fails —
each with a `WARNING` on stderr. `--substrate-from-live` (or
`CRAFTBENCH_SUBSTRATE_FROM_LIVE=1`) forces the live path for debugging.

> ℹ️ **Grading from HEAD is the clone-and-go default.** The legit substrate
> (gold `.umap` maps, `Build.cs` GAS deps, the `CraftBenchTests` fixtures, the
> `verifier_hashes.json` pin) is **committed to HEAD** — a fresh `git clone`
> grades cleanly with no `--substrate-from-live`. Validated 2026-06-21: a fresh
> clone graded 22/22 reference solutions PASS on Windows + UE 5.8 (including the
> two L2I tasks). `--substrate-from-live` is now an *option* (grade uncommitted
> WIP without a commit), not a requirement.

---

## 4. The pluggable Layer registry (the architecture to internalize)

A `Layer` (`layers/base.py:63`) is a `Protocol` with four class attrs and two
methods:

```python
key: str                  # report key: "L1" / "L2" / "L2I" / "L3" / "ART" / "R2"
gating: bool              # True → contributes to certified overall; False → advisory
order: int                # ascending run order
requires: Tuple[str, ...] # layer keys that must PASS first, else this is "skipped"
def applies(ctx) -> bool  # selection predicate (hides L-token vs section vs --flag)
def run(ctx) -> LayerReport
```

`LayerContext` (`layers/base.py:35`) is assembled once after pre-flight and
carries everything a layer needs: `task`, `args`, `project_path`,
`workdir_substrate`, `out_dir`, `manifest`, `substrate_src`, `requested_layers`,
plus `prior` (results so far) and `advisory_out` (where non-gating layers stash
their rich payloads). `ctx.agent_prefixes` is a convenience property exposing
`manifest.writable`.

**`run_layers()` (`registry.py:353`)** is the whole loop:

```python
for layer in sorted(registry, key=lambda l: l.order):
    if not layer.applies(ctx): continue
    failed_dep = first key in layer.requires whose result ran and != "pass"
    if failed_dep:
        if layer.gating: layers_out[key] = LayerReport(status="skipped", ...)
        continue                       # advisory deps short-circuit silently
    report = layer.run(ctx)
    if layer.gating: layers_out[key] = report   # advisory layers do NOT land here
return layers_out, advisory_out
```

Two consequences worth burning in:
- **`overall` is computed by the caller over `layers_out` alone** (the gating
  dict), so an advisory layer (R2) is *structurally* incapable of flipping the
  verdict — it never enters `layers_out` (`run_task.py:1454`).
- **`run_layers` does NOT topo-sort.** A `requires` dependency is only seen if
  the required layer has a *lower* `order` (ran earlier). This is enforced by
  hand in the `order` values, not by the loop. (Documented in `base.py:67`.)

### The current registry (`registry.py:348`), in run order

| key | class | order | gating | applies when | requires |
|---|---|---|---|---|---|
| `ART` | `ArtifactLayer` | 8 | ✅ | `task.artifact_path` set (from `- ART (artifact: …)`) | — |
| `L1` | `L1Layer` | 10 | ✅ | `"L1"` in requested layers | — |
| `L2` | `L2Layer` | 20 | ✅ | `"L2"` in requested layers | `L1` |
| `L3` | `L3RenderLayer` | 25 | ✅ | `task.l3_fixtures` non-empty | `L1` |
| `L2I` | `L2IntrospectLayer` | 30 | ✅ | `task.introspect_scripts` non-empty | `L1` |
| `R2` | `R2Layer` | 40 | ❌ | `--r2` **and** `## R2 advisory rubric` in spec | — |

**Adding a verification method = write a `Layer` + append it to `REGISTRY`.**
That is the entire extension story; this registry was the consolidation of
previously hand-coded L1/L2/L2I/R2 blocks in `main()` (see the
`project_pluggable_layers` design note), and the per-layer logic was *relocated
verbatim* so behavior is preserved.

### What each layer asserts and how

**`ArtifactLayer` (`registry.py:30`)** — a deterministic "deliverable present"
floor: PASS iff `workdir_substrate / task.artifact_path` is a file and
non-empty. Gives advisory-heavy tasks (e.g. `summarize-project`, judged by R2)
a real non-vacuous gate. Opt-in via the unified-block `- ART (artifact: <path>)`.

**`L1Layer` → `run_l1` (`l1_build.py:87`)** — builds **both** UBT targets:
`<Module>Editor` then `<Module>` (Game). Both must exit 0. Building both is the
defense against the `#if WITH_EDITOR` escape hatch (editor-only code passes the
Editor target but fails the Game target — which is what would happen at
packaging time). It **short-circuits on the first failing target**
(`l1_build.py:155`) to save wall-clock. UBT invocation per target
(`l1_build.py:182`): `<Build.sh|Build.bat> <Target> <Platform> Development
-project=<abs .uproject> -waitmutex`. Warnings are counted by regex
(`l1_build.py:51`, clang + MSVC forms); warnings under an agent-writable prefix
are summed separately so `--strict-warnings` can fail L1 on agent-introduced
warnings only (`registry.py:70`). `_build_script` / `_platform_arg` pick the
Mac/Linux/Windows path.

**`L2Layer` → `run_l2` (`l2_pie.py:234`)** — the runtime-behavior layer. It is
the most subtle:
1. **Scaffold the map(s)** first (`registry.py:109`) via
   `materialize_map_if_missing`. Multi-fixture tasks scaffold each distinct map
   in spec order; a scaffold failure fails L2 immediately.
2. **Derive the test filter** (`derive_test_filter`, `run_task.py:968`): a
   `## Verifier fixtures` block builds a `+`-joined multi-test filter
   (`Project.Functional Tests.Maps.<map>.<class>`); otherwise it derives from
   the parsed `map_name` + `test_class_hint`. **UE strips the leading `A`** from
   `AActor` class names in the filter (`ASanityFunctionalTest` →
   `SanityFunctionalTest`), done in `_strip_class_prefix` (`run_task.py:1004`).
3. **Spawn the editor** (`l2_pie.py:275`):
   `UnrealEditor-Cmd <project> /Game/Maps/<Map>
   -ExecCmds="Automation RunTests <filter>; Quit" -unattended -nopause -nosplash
   -nosound -deterministic -FPS=<fps> -log -stdout -fullstdoutlogoutput
   -testexit="Automation Test Queue Empty" [-nullrhi] [-ReportExportPath=<dir>]`.
   Determinism comes from `-deterministic -FPS=<fps>` (fixed timestep), **not**
   `t.MaxFPS` (a wall-clock limiter).
4. **Parse the result** (`_parse_results`, `l2_pie.py:408`): **primary** =
   `index.json` under `-ReportExportPath` (per-test `state` + `succeeded`/`failed`
   counts; `parse_index_json` at `l2_pie.py:430`); **fallback** = stdout grep
   (`parse_automation_log`, `l2_pie.py:494`) for `Test Completed. Result={…}`,
   then the locale-stable `TestResult=Passed|Failed|Skipped`, then the old
   `Automation Test Succeeded/Failed`. The editor exits 0 even on test failure,
   so **exit code is NOT the pass signal** — only the JSON/stdout are.
5. Status: `tests_run==0` → `skipped`; all-passed → `pass`; else `fail`.
   Under `-nullrhi`, an all-skipped/zero-discovered result triggers **one retry
   without `-nullrhi`** (`registry.py:181`).
   Framerate-independence tasks (`_DT_LEGS_BY_TASK`, `run_task.py:64`; only
   `gp-timer-delayed-destroy`) run the same fixture at multiple fixed dts in
   separate PIE processes and require ALL legs to pass.

**`L3RenderLayer` (`registry.py:264`)** — same `run_l2` machinery but with
`use_nullrhi=False` so the PIE scene actually renders (a one-shot editor-Python
capture would render black: no frame advances). The fixture asserts structural
predicates (the gate) and writes a screenshot to
`workdir/Saved/CraftBench/*.png`, which this layer hands to the R2 *visual*
advisory track (`ctx.advisory_out["L3_visual"]`). Pixel/SSIM stays out of the
gate. Triggered by `- L3 (fixtures: …)`.

**`L2IntrospectLayer` → `run_l2_introspect` (`l2_introspect.py:135`)** —
deterministic *structural* asset verification. Runs a verifier-owned
editor-Python script via `UnrealEditor-Cmd -ExecutePythonScript=<script>` (no
PIE, no LLM, no render). The script loads an asset (material graph, BP graph,
AnimBP state machine, UMG WidgetTree, …) through stock UE reflection and prints
a verdict block:

```
CRAFTBENCH-INTROSPECT-JSON-START
{"checks": [{"id": "<str>", "passed": <bool>, "detail": "<str>"}, ...]}
CRAFTBENCH-INTROSPECT-JSON-END
```

Parsing (`parse_introspect_verdict`, `l2_introspect.py:79`) is **fail-safe**: a
missing/malformed block → `error` (never a pass on an unconfirmed verdict). If
the block appears twice, the **last** one wins. Status: PASS iff the block
parses, has ≥1 check, and every `passed` is true. The script must be
**verifier-owned, READ-ONLY, identity-by-content-path/tag, stock-UE-Python only**
(anti-circularity — never grade Aura through Aura's MCP tools). See
`introspect/mat_emissive_pulse.py` for the canonical example (it walks the
EmissiveColor expression graph for `MaterialExpressionTime`/`…Sine` class names —
strictly stronger than HLSL string matching).

**`R2Layer` (`registry.py:325`)** — the **non-gating** advisory judge. Its rich
block goes to `ctx.advisory_out["R2"]` → `report.r2_advisory`, never to
`layers_out`. Delegates to `run_task._maybe_run_r2` (`run_task.py:1207`), which
shells out to `tools/verify-r2/run_r2.py` in a firewalled workspace (the judge
never sees this run's verdict — anti-anchoring). Best-effort: any failure yields
an error-shaped advisory and never raises. `Report.__post_init__` (`report.py:68`)
**refuses an advisory that claims `gating: True`** — a belt-and-braces enforcement
of non-gating at the report door.

---

## 5. Important data structures / schemas

### `TaskSpec` (`run_task.py:86`) — what the parser pulls out of `tasks/<set>/<id>/task.md`
`parse_task_spec` (`run_task.py:152`) splits the markdown into **H2 sections by
exact heading text** (`_split_h2_sections`, `run_task.py:482`) and extracts:
- `task_id`, `substrate` (from `## Task ID and metadata` `- key: value` bullets);
- `layers` (L-tokens regex'd from `## Verifier layers used`);
- `map_name`, `test_class_hint` (regex over the whole spec);
- `fixtures` (`## Verifier fixtures`, `<map> :: <class>` bullets);
- `deadline_seconds` (600 default), `action_budget` (30 default);
- `randomize_tokens` (`## Randomization`);
- `introspect_scripts` (`## Verifier introspection`);
- `artifact_path` / `l3_fixtures` (from the unified block).

**Unified `## Verifier layers` block** (`_parse_verifier_layers_block`,
`run_task.py:452`) is the single-source-of-truth alternative: when present it
**overrides** the legacy multi-channel parsing. Each bullet is `- KEY` or
`- KEY (param: value; param: value)`, e.g.:

```
## Verifier layers
- L1
- L2 (fixtures: L_TimerTask60 :: ATimerTask60HzFunctionalTest, L_TimerTask20 :: ATimerTask20HzFunctionalTest)
- L2I (scripts: mat_emissive_pulse.py)
- ART (artifact: Content/Tasks/summarize-project/OVERVIEW.md)
- R2
```

Insertion order = run-selection order. The legacy parsing stays as the fallback
for un-migrated tasks.

### `WritableManifest` (`sandbox.py:33`) — `AGENT_WRITABLE.json`
Fields: `substrate`, `game_module`, `writable` (tuple), `deny` (tuple),
`asset_writable` (tuple, default empty). Live values for `CraftBenchTemplate`:
- `writable`: `Source/CraftBenchTemplate/`, `Content/Tasks/`
- `asset_writable`: `Content/Tasks/`, `Content/Blueprints/`, `Content/Abilities/`,
  `Content/Generated_Materials/`, `Content/Generated_Audio/`
- `deny`: `Source/CraftBenchTests/`, `Config/`, `Content/Maps/`, `Tools/`,
  `Plugins/`, `CraftBenchTemplate.uproject`, `AGENT_WRITABLE.json`

### `report.json` (from `Report.to_dict`, `report.py:74`)
```json
{
  "task_id": "...",
  "submission_sha": "<sha256 of submission tree>",
  "layers": {
    "L1": {"status": "pass", "exit_code": 0, "log": ".../l1_build.log",
           "warnings_in_agent_files": 0, "duration_seconds": 12.3, "notes": [...]},
    "L2": {"status": "pass", "exit_code": 0, "log": ".../l2_pie.log",
           "tests_run": 1, "tests_passed": 1, "duration_seconds": 33.4, "notes": [...]}
  },
  "overall": "pass",
  "duration_seconds": 46.0,
  "ue_version": "5.7.4",
  "host": {"os": "darwin", "arch": "arm64"},
  "sandbox_violations": 0,
  "r2_advisory": { "gating": false, ... }   // present only when --r2 produced one
}
```
`LayerReport.to_dict` (`report.py:31`) drops `None`/empty fields, so the actual
key set per layer varies (e.g. L2I emits `tests_run`/`tests_passed`/`notes` but
no `exit_code`).

---

## 6. How to run / observe it

Unit tests (no UE required, pure stdlib `unittest`):
```sh
python3 -m unittest discover -v tools/verify-single/tests
```
A single class/method:
```sh
python3 -m unittest tools.verify-single.tests.test_run_task.TestMultiFixtureParsing
```

Grade a submission (needs a UE 5.8 install). *Update 2026-07: tasks now live
folder-per-task — spec at `tasks/<set>/<id>/task.md`, reference solution at
`tasks/<set>/<id>/reference/` (layout contract: `tasks/README.md`).*
```sh
python3 tools/verify-single/run_task.py \
    --task tasks/cpp/t0-sanity-log-on-beginplay/task.md \
    --submission tasks/cpp/t0-sanity-log-on-beginplay/reference \
    --ue-root /path/to/UE_5.8 --keep-workdir
```

Score in-place Aura edits (extract the writable subtree from a live UE project):
```sh
python3 tools/verify-single/run_task.py --task tasks/<set>/<id>/task.md \
    --submission-from-project UE-projects/CraftBenchTemplate/ \
    --ue-root /path/to/UE_5.8 [--capture-assets]
```

Bump the integrity pin (substrate maintainers only, same commit as the
`CraftBenchTests/` edit):
```sh
python3 tools/verify-single/run_task.py --regen-verifier-hashes <other args>
```

Observe a failure: **pass `--keep-workdir` (or an explicit `--workdir`) or the
workdir is gone.** This paragraph said the workdir was "always kept on failure"
until 2026-08-15 — it never was; `run_task`'s cleanup is verdict-blind. A bounded
excerpt of each non-passing layer's log is now written beside `--report-json`
automatically (`failure_evidence.py`), but the full tree below exists only if you
asked for it. Useful contents: `out/report.json`, `out/l1_build.log`,
`out/l2_pie.log` (grep `Test Completed. Result=`), `out/l2_report/index.json`,
and `<workdir>/CraftBenchTemplate/` (the applied substrate copy, openable in the
editor to repro by hand).

---

## 7. The exit-code map (and short-circuit order)

`main()` returns these (verified at the `return` sites in `run_task.py`):

| Code | Meaning | Where |
|---|---|---|
| `0` | All gating layers passed; `overall=pass`. | `run_task.py:1472` |
| `1` | At least one gating layer failed; `overall=fail`. | `run_task.py:1472` |
| `2` | Bad invocation: both/neither submission flag, missing substrate, missing `AGENT_WRITABLE.json`, no layers declared, `--workdir` exists, `--submission-from-project` path missing. | `:1269/1275/1285/1293/1305/1346/1355` |
| `3` | `Source/CraftBenchTests/` integrity check failed (drift / missing manifest / missing substrate entry). | `run_task.py:1390` |
| `4` | Sandbox violation: a submission file is outside the writable allowlist / under a deny prefix / path traversal. | `run_task.py:1407` |
| `5` | `.uproject` missing in the workdir after substrate copy (substrate bug). | `run_task.py:1431` |

**Short-circuit / precedence order** (each gate aborts before the next runs):

```
bad flags / missing inputs   → 2
   ↓ (substrate copied)
integrity pin drift          → 3
   ↓
sandbox violation            → 4
   ↓ (submission applied; Aura disabled)
missing .uproject            → 5
   ↓
run_layers:
   ART (8) → L1 (10) → L2 (20) → L3 (25) → L2I (30) → R2 (40, advisory)
   within layers: a failed `requires` dep marks the layer "skipped" (not run)
   L1 itself short-circuits on the first failing UBT target
   ↓
harness_error_reasons(layers_out, requested)  → 7  (non-empty ⇒ no verdict)
   ↓
overall = pass iff all gating layers pass  → 0, else 1
```

The harness-error gate sits **before** `overall` deliberately: two of the shapes
it catches would otherwise be scored as real verdicts — an empty gating set
grades a vacuous PASS (`all({})` is `True`), and a layer that ran but counted
nothing grades a FAIL that no measurement supports.

So the two integrity/sandbox defenses (3, 4) are **complementary and both run
before any layer**: the hash pin protects the verifier-owned test module from
tampering; the sandbox protects the substrate from agent writes outside the
allowlist. `deny` wins over `writable` in `_is_writable` (`sandbox.py:113`);
`asset_writable` only widens which generated `.uasset`/`.umap` folders are
gradeable (`--capture-assets`), never which source/config paths an agent may
write, and is still subject to `deny`.

---

## 8. Non-obvious gotchas that will bite a newcomer

- **Exit `6` does not exist here.** Project memory references an "L1 FAIL exit=6"
  on every task; that is *not* a `run_task.py` return value. An L1 failure
  produces a failing gating layer → `overall=fail` → **exit 1**. If you see exit 6
  it is coming from a wrapper/harness, not this verifier. *(Flagging because it
  contradicts a memory note.)*
- **Exit `7` = HARNESS-ERROR, and it is NOT graded.** The codes are 0–5 **and 7**
  (README §"Exit codes" has the full table). 7 means the verifier produced no
  verdict at all: an empty/incomplete gating layer set, L1 exit 127 (the build
  tool could not be executed), a gating layer that ran and counted nothing while
  its dependencies passed, or an uncaught exception in `main()`. It is kept out
  of `adapters.base.GRADED_VERDICTS`, so such a run is excluded from pass-rates
  rather than silently scored as an agent FAIL. `report.json` carries
  `overall: "harness-error"` (7 is deliberately below 126 so it cannot collide
  with the POSIX 124/126/127/128+N conventions).
- **`skipped` is NOT always non-graded.** `run_layers` emits `status="skipped"`
  for *every* dependent of a failed layer, so "L2 skipped" is the ordinary shape
  of "the agent's C++ does not compile" — that stays a graded **FAIL**. Only a
  `skipped` whose declared dependencies all PASSED is the harness failing to
  answer (exit 7). The discriminator is the dependency, never the note text: the
  two skip producers differ only in their notes prose
  (`run_task.harness_error_reasons`).
- **`run_layers` is not topo-sorted.** `requires` only works because the
  required layer's `order` is numerically lower. If you add a layer with a
  `requires` pointing at a *higher*-order layer, the dependency check silently
  sees nothing and the gate runs anyway. Pick `order` deliberately (`base.py:67`).
- **R2 cannot fail the build, by construction** — it's not in `layers_out`, and
  `Report.__post_init__` rejects a `gating:true` advisory. Don't try to "make R2
  count"; that's a deliberate firewall (FR-020d).
- **Default substrate clone is git HEAD, not your working tree.** Edits to
  `UE-projects/CraftBenchTemplate/` that are uncommitted/untracked are *invisible*
  to a default run. The legit substrate (gold maps, GAS `Build.cs` deps, the
  `CraftBenchTests` fixtures, the pin) is fully committed to HEAD, so a default
  clone-and-go run grades cleanly (validated 2026-06-21: 22/22 reference PASS on
  Windows + UE 5.8). Use `--substrate-from-live` only when you want to grade
  *uncommitted* WIP without committing it first.
- **The editor exits 0 even when tests fail.** L2 ignores the process exit code
  for pass/fail and trusts `index.json` (primary) then stdout grep (fallback).
  If a report shows `tests_run=0 → skipped`, the filter didn't match a
  discoverable test — not a pass.
- **UE strips the leading `A` in automation filters.** The filter builder does
  this (`_strip_class_prefix`); don't "fix" it back to `A…` or the filter matches
  nothing.
- **L1 builds the Game target too** — an editor-only (`#if WITH_EDITOR`) solution
  that compiles in the editor will fail the Game target. This is intentional
  anti-gaming.
- **Map authoring drops `-nullrhi`; test runs keep it.** `scaffold_map.py`
  deliberately omits `-nullrhi` (`scaffold_map.py:90`) because the
  editor-context actor spawn indexes a viewport array that's empty under nullrhi
  (the `Array.h` "Index out of bounds" assert). `run_l2`/`run_l2_introspect`
  *do* use `-nullrhi`. Don't unify these.
- **Marker-kill, not clean exit.** UE-Mac frequently never returns from its
  Cocoa runloop after `RequestExit`. `_run_editor_with_marker_kill`
  (`l2_pie.py:120`) tails stdout and SIGTERM/SIGKILLs on a terminal marker
  (`**** TEST COMPLETE. EXIT CODE:`, `FPlatformMisc::RequestExit`,
  `LogExit: Exiting.`), giving the editor 8s to flush its JSON first. A "force
  killed (known UE-Mac RequestExit quirk)" note in the report is expected, not an
  error.
- **Integrity strict-mode is a footgun closer, not a bootstrap.** Deleting
  `verifier_hashes.json` does NOT re-pin on next run — it returns exit 3. Only
  `--regen-verifier-hashes` writes the manifest (`run_task.py:612`). The
  pre-strict behavior used to silently re-record whatever was on disk; that was
  removed on purpose.
- **`hashes.py`/`pinning.py` are different things.** `hashes.py` is a thin
  raises-on-drift wrapper around `run_task.verify_tests_module_integrity`
  (the `CraftBenchTests/` tamper pin). `pinning.py` is unrelated — it collects
  *score-report provenance* (substrate/task/verifier git revisions, engine
  version, harness/model ids) per FR-002 and is **not wired into the `main()`
  flow** read above (it's a separate API for report metadata).
- **`layers/INTROSPECT_CONTRACT.md` is stale.** It says runner wiring + the first
  task "are the **next** step." That's outdated: `L2IntrospectLayer` is in the
  registry (`registry.py:207`) and `mat_emissive_pulse` ships and is validated.
  Trust the code/registry over that doc. *(Flagging the contradiction.)*
- **The L1 dual-target unit tests skip on Windows** (they shell-stub UBT); that's
  expected, not a failure.

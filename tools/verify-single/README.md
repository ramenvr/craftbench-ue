# CraftBench verifier runner

`tools/verify-single/run_task.py` is the script that takes an agent's submission,
applies it to a CraftBench substrate, and runs the per-layer verifier
(L1 build via UnrealBuildTool, L2 functional test in PIE via the editor
automation harness) to decide pass/fail.

> **Status: current engine pin is UE 5.8.** Historical macOS / UE 5.7.4
> runs validated the PIE-native model; **Windows + UE 5.8 is now validated
> end-to-end** — a fresh clone graded 22/22 reference solutions PASS
> (L1+L2+L2I, including the two L2I asset tasks) via `cb batch-eval` on
> 2026-06-21 (pre-cull set; the 2026-07-08 fresh start reduced the task
> tree). Linux and broad task-set parity remain unvalidated. The
> Windows-conditional code paths (UBT via `cmd /c Build.bat`, the `Win64`
> editor `.exe` + variant-OS detection, the LF-pinned manifest via
> `.gitattributes`) are documented in `docs/WINDOWS.md`.
> Seven Mac / UE-5.7 quirks surfaced and were resolved during the first
> runs — see *Mac / UE 5.7 quirks resolved on first real run* below.
> **L2 now runs in a real PIE world** (the fixture base overrides
> `IsEditorOnlyLoadedInPIE()→true`); BeginPlay auto-fires, `FTimerManager`
> and `CharacterMovement` tick, and fixtures observe via a checkpoint
> schedule rather than manual ticking — see *PIE-native fixture conventions*
> below and `docs/pie-verification-playbook.md`.

## Install

1. Python 3.10 or newer. The runner uses only the standard library
   (`subprocess`, `pathlib`, `argparse`, `json`, `re`, `hashlib`,
   `dataclasses`). No `pip install` step. (That 3.10 floor is the
   verifier's only; the `cb` harness wants 3.11+, 3.12 preferred —
   `cb.cmd` defaults to `py -3.12`.)
2. Unreal Engine 5.8 installed at a known path. On macOS the default
   Epic Games Launcher location is
   `/Users/Shared/Epic Games/UE_5.8`. The runner needs the directory
   that contains `Engine/` (i.e. the `UE_5.8/` directory itself).
3. A CraftBench substrate scaffolded under `UE-projects/<name>/`. The
   reference substrate is `UE-projects/CraftBenchTemplate/`; an agent-
   writable manifest lives at `UE-projects/<name>/AGENT_WRITABLE.json`.

## CLI

```text
python tools/verify-single/run_task.py \
  --task        tasks/cpp/t0-sanity-log-on-beginplay/task.md \
  --submission  /path/to/agent/output \
  --ue-root     /Users/Shared/Epic\ Games/UE_5.8 \
  [--substrate-overlay UE-projects/CraftBenchTemplate] \
  [--report-json out/report.json] \
  [--layers L1,L2] \
  [--test-filter "Project.Functional Tests.Maps.t0-sanity-log-on-beginplay.L_SanityTask.SanityFunctionalTest"] \
  [--no-nullrhi] \
  [--strict-warnings] \
  [--workdir /path/to/scratch] \
  [--keep-workdir]
```

| Flag | Default | What it does |
|---|---|---|
| `--task` | required | Path to a task `.md` under `tasks/`. The runner parses it via `spec.py::parse_task_file` — v2 front matter (`id` / `substrate` / `layers` / `fixtures` / …), with the legacy H2 fallback for un-migrated specs. No code in the spec is executed. |
| `--submission` | required | Root of the agent's output. Every file under here is checked against the substrate's `AGENT_WRITABLE.json` and rejected if it lies outside the writable set. |
| `--ue-root` | required | Path to the UE install directory that contains `Engine/`. |
| `--substrate-overlay` | `UE-projects/<name>` | Override the on-disk substrate root. Used when developing a new substrate. |
| `--report-json` | `<workdir>/out/report.json` | Where the JSON report is written. |
| `--layers` | from task spec | Comma-separated subset (e.g. `L1` only). Defaults to the spec's front-matter `layers:` list (legacy specs: the `Verifier layers used` H2). |
| `--test-filter` | derived | Override the L2 automation-test filter. See **Known unverified assumptions** for the default-derivation rule. |
| `--no-nullrhi` | off (i.e. nullrhi is on) | Use a full RHI for L2; the runner also auto-retries without `-nullrhi` if the first nullrhi run finds zero tests. |
| `--strict-warnings` | off | Fail L1 if any compiler warning is found in agent-writable files. **Was unfailable before 2026-08-15** — the counter's regex rejected MSVC's `file(line,col):` form, so it read 0 on every build. Now that it counts, expect it to FAIL committed references that use deprecated engine APIs (`gp-poison-dot-stack-cpp`'s reference warns `C4996` on `UGameplayEffect::StackingType`). Do not switch it on mid-bench. |
| `--workdir` | fresh tempdir | Use this explicit path as the run workdir (must not exist). |
| `--keep-workdir` | off | Keep the workdir. **It is NOT "always kept on failure"** — this row said so until 2026-08-15 and it was never true: the `finally` runs `robust_rmtree(workdir)` verdict-blind whenever the runner owns the tempdir, so a FAILED build's `out/*.log` is deleted exactly as eagerly as a passing one's. Pass this flag (or `--workdir`) when you intend to read the logs. Since 2026-08-15 a bounded excerpt of every non-passing layer's log is copied beside `--report-json` regardless (`failure_evidence.py`), which is what makes an intermittent failure diagnosable after the fact. |
| `--full-substrate` | off (per-task staging is the default) | Escape hatch: stage the ENTIRE substrate `Content/` tree instead of pruning other tasks' maps / `Content/Tasks/` baselines / OFPA mirrors from the graded workdir (`content_staging.py`). Env equivalent: `CB_FULL_SUBSTRATE=1`. `Source/` is always staged whole either way; the report records the staging mode (`content_staging`). |

## What the runner does, step by step

1. **Parse the task spec** for `task_id`, `substrate`, and the layer
   list — via `spec.py::parse_task_file` (v2 front matter, with the
   legacy H2 fallback for un-migrated specs).
2. **Materialize the substrate from git HEAD** into a fresh workdir under
   a tempdir (or `--workdir`) via `git archive` — committed files only, so
   uncommitted/untracked disk state (including any tampering with
   `Source/CraftBenchTests/`) never reaches the graded tree. This git-HEAD
   provenance replaced the retired hash-manifest gate (exit 3 +
   `--regen-verifier-hashes`, removed 2026-07-16); committed changes to the
   verifier module are review-gated on commit.
   `--substrate-from-live` opts into copying the live working tree
   (UNCERTIFIED debug path; annotated `substrate_source: "live"`).
   Then **per-task CONTENT staging** (`content_staging.py`, default ON) prunes
   other tasks' content from the staged tree so the graded project carries
   only what THIS task needs: other tasks' `Content/Maps/<task-id>/` folders
   and flat pre-convention maps (ownership derived from the task specs via
   `spec.py` — never hand-coded), other tasks' `Content/Tasks/<id>/`
   baselines, and their OFPA mirrors under `Content/__External*__/Tasks/<id>`.
   `Source/` is ALWAYS staged whole (CraftBenchTests compiles every fixture,
   and fixtures `#include` their scaffolds). The filter is fail-open — an
   unattributable path is KEPT, and any derivation error stages the full
   substrate with a note (a wrongly-excluded map would be a false L2 FAIL,
   which is never acceptable). It is non-gating and can never fail a run.
   Escape hatch: `--full-substrate` / `CB_FULL_SUBSTRATE=1`. The report
   records the outcome either way (`content_staging`: mode + excluded count
   + entries).
3. **Sandbox the submission** against the substrate's
   `AGENT_WRITABLE.json`. Anything outside the writable set or under
   the deny set is reported as a violation; if any violation is found
   the runner prints the violation report, writes a JSON report with
   `overall=fail` and `sandbox_violations>0`, and exits with code 4
   *before* running any layer.
4. **Overlay** the accepted submission files into the workdir
   substrate copy.
5. **L1 build.** UBT against `<Project>Editor` target. If L1 fails,
   L2 is skipped.
6. **Locate each declared test `.umap`.** Maps ship exclusively as
   committed binaries (scaffolders retired 2026-07); a missing binary is
   an explicit L2 FAIL (`map binary missing: ...`) — there is no re-bake
   fallback.
7. **L2 PIE.** `UnrealEditor-Cmd ... -ExecCmds="Automation RunTests
   <filter>; Quit" -ReportOutputPath=<out>/l2_report`. The runner
   parses `index.json` for authoritative pass/fail; stdout grep is
   the fallback if the JSON is missing. **The editor process exits 0
   even on test failure** — the JSON is the only honest pass/fail
   signal.
8. **Write the report** as JSON and print a compact stdout summary.
9. **Clean up the workdir** unless `--keep-workdir` or `--workdir` is set —
   **verdict-blind**, i.e. a FAILED run's workdir is removed just as eagerly as a
   passing one's. This line claimed the opposite ("always kept on failure so
   logs can be inspected") until 2026-08-15; it was never true, and one
   intermittent L1 failure is permanently undiagnosed because of it.
   What DOES survive a failure, since 2026-08-15, is a bounded excerpt of every
   non-passing layer's log, written beside `--report-json`
   (`failure_evidence.py`). To inspect the full tree, ask for it.

### Report shape

```json
{
  "task_id": "t0-sanity-log-on-beginplay",
  "submission_sha": "<sha256 of submission tree>",
  "layers": {
    "L1": {"status": "pass", "exit_code": 0, "log": ".../out/l1_build.log", "warnings_in_agent_files": 0, "duration_seconds": 12.3},
    "L2": {"status": "pass", "exit_code": 0, "log": ".../out/l2_pie.log", "tests_run": 1, "tests_passed": 1, "duration_seconds": 33.4}
  },
  "overall": "pass",
  "duration_seconds": 46.0,
  "phases": {
    "layers": 45.7, "stage_substrate": 0.2, "sandbox": 0.0,
    "apply_submission": 0.0, "config_overlay": 0.0,
    "compose_report": 0.05, "unaccounted": 0.05
  },
  "ue_version": "5.8.0",
  "host": {"os": "darwin", "arch": "arm64"},
  "sandbox_violations": 0,
  "content_staging": {"mode": "per-task", "excluded_count": 27, "excluded": ["Content/Maps/L_GlideStamina.umap", "..."]}
}
```

**`content_staging`** records how the graded workdir's `Content/` was staged:
`mode` is `"per-task"` (other tasks' maps/baselines/OFPA mirrors pruned) or
`"full"` (the `--full-substrate` / `CB_FULL_SUBSTRATE=1` escape hatch, or the
filter's fail-open on a derivation error — `notes` says which), plus the
excluded entry list. Non-gating and purely descriptive; OMITTED from reports
that predate it.

**`phases`** (`phase_timer.py`) is wall-clock accounting of the runner's own
work, non-gating and purely descriptive. Its one contract is that **it closes**:
the values always sum to `duration_seconds`, because `unaccounted` is derived as
the remainder rather than measured. A phase nobody instrumented therefore shows
up as a growing `unaccounted`, not as cost that quietly disappeared — which is
what made "where does a grade's time actually go" unanswerable before. `phases`
is OMITTED from reports that predate it, so older artifacts round-trip
unchanged.

Every layer now carries `duration_seconds`. L1 and L2 measure the UBT / editor
subprocess themselves (the tighter number, excluding adapter overhead) and that
value is kept; layers that do not self-measure — L2I, L3, R2 — are timed by
`registry.run_layers` around their `run()` call. Before this, L2I reported no
duration at all, so a pathological introspect run could only be identified by
reading logs. A short-circuited layer (`status: "skipped"`) carries no duration:
it is not billed for time it never spent.

### `--lite` — iteration mode, never a grade

L1 is ~87–93% of a verify (measured 2026-07-31: 87.4% on t0, 87.7–87.8% across
eight kp- legs, 93.3% on `t1-engine-source-pixel-formats` cold), so the build
is the only thing a lighter mode can meaningfully trim. `--lite` skips it and
runs the remaining layers against a warm slot's already-built binaries:
`t1-engine-source-pixel-formats` went **344.8s → 22.6s** with byte-identical L2I
results (5/5 either way).

It exits **8 / `UNGRADED`** whatever the layers report — unconditionally, even
when everything passes. "L2I 5/5 against a binary we did not build" is a useful
iteration signal and not a certification, and a flag that leaves a `PASS` in the
report is how a forgotten flag reaches a certification run.

Two REFUSALS, not warnings, because each one makes the layer results describe a
binary unrelated to the submission:

1. **The submission contains compile inputs.** No build runs, so that source
   cannot be under test. (`--lite` is for asset/structural rows — all 18 kp-
   rows carry 0 C++ files.)
2. **The slot's binaries are not pristine.** A warm slot's `Binaries/` stop being
   the baseline after the first grade; they hold *that grade's* compiled code.
   `warm_cache.read_binaries_state` records what they were last built from, and
   `--lite` requires `pristine`. This is regression cover for a real observation:
   on 2026-07-31 a `--lite` run reported t0 `L2 1/1 PASS` purely because a warm
   grade a minute earlier had linked that submission into the slot. A warning
   above a green result is not a defence.

A `--lite` run never builds, so it never dirties a slot — one `cb warm-prime`
serves an unlimited iteration loop.

### Exit codes

| Code | Meaning |
|---|---|
| `0` | All requested layers passed; `overall=pass`. |
| `1` | At least one layer failed; `overall=fail`. |
| `2` | Bad invocation (missing substrate, missing manifest, no layers). |
| `3` | retired/reserved (the historical hash-gate REJECT — never emitted since 2026-07-16). |
| `4` | Sandbox violation: submission wrote outside agent-writable paths. |
| `5` | Workdir missing `.uproject` after substrate copy (substrate bug). |
| `6` | **FORBIDDEN — never emitted.** 6 is UBT's own build-failure code; an L1 build failure surfaces here as exit 1. |
| `8` | `UNGRADED` — `--lite` ran: no build, so no verdict was attempted. A CHOICE, not a fault (that is `7`). Non-graded by omission from `GRADED_VERDICTS`. |
| `7` | **HARNESS-ERROR — the verifier produced no verdict.** NOT graded: excluded from every pass-rate denominator (`adapters.base.GRADED_VERDICTS`), and `report.json` records `overall: "harness-error"`. |

Only `0` and `1` are **graded** (a real agent outcome that belongs in a
pass-rate). Everything else says "no measurement happened"; the harness maps it
to a non-graded verdict via `adapters/base.py::VERIFIER_EXIT_VERDICT` and
`aura_rig/driver.py::VERDICT`, which agree key-for-key.

Exit `7` is emitted for four structurally-detected shapes (see
`run_task.harness_error_reasons`):

1. **the gating layer set is empty** — a spec naming only `L4`/`L5` (recognized
   but unimplemented) used to grade a vacuous PASS at exit 0, because
   `all({})` is `True`;
2. **a requested gating layer produced no verdict** — the declared gate silently
   did not run, so the grade was narrower than the spec claimed;
3. **L1 exit 127** — the build tool could not be executed at all (missing UBT
   script / editor binary). Note that L1 exit **124** (the governed build
   timeout) deliberately stays a graded FAIL: a pathological submission can hang
   a compile, and routing it here would let an agent opt out of the denominator;
4. **a gating layer with `status: skipped` while every dependency it declares
   PASSED** — the layer ran and counted nothing ("no tests counted"), so no
   behavior was measured. A `skipped` whose dependency did NOT pass is the
   ordinary short-circuit downstream of an agent failure and stays a graded FAIL.

An uncaught exception also exits `7` (the `cli()` trap) instead of letting
Python's default `1` be read as an agent FAIL.

## Worked example — T0 (`t0-sanity-log-on-beginplay`)

### Known-good submission

A correct submission consists of edits to the existing
`SanityActor.h`/`SanityActor.cpp` adding a `BeginPlay` override that
emits `UE_LOG(LogTemp, Display, TEXT("CRAFTBENCH_SANITY_OK"))` once.
Place the two edited files under
`/tmp/good-submission/Source/CraftBenchTemplate/`, then:

```bash
python tools/verify-single/run_task.py \
  --task tasks/cpp/t0-sanity-log-on-beginplay/task.md \
  --submission /tmp/good-submission \
  --ue-root "/Users/Shared/Epic Games/UE_5.8" \
  --keep-workdir
```

Expected output (paraphrased):

```text
sandbox: accepted 2 file(s), 0 violations
CraftBench verifier report
  task_id   : t0-sanity-log-on-beginplay
  L1        : PASS    [exit=0, warn=0]
  L2        : PASS    [exit=0, tests=1/1]
  overall   : PASS
```

### Known-bad (empty) submission

Pass an empty directory as the submission. The sandbox accepts (no
files = no violations) and the runner proceeds to L1, which still
passes (the substrate compiles even without agent edits). L2 then
runs and fails because the `CRAFTBENCH_SANITY_OK` log line never
appears: `tests_run=1, tests_passed=0`. `overall=fail`, exit code `1`.

If T0 ever returns `overall=pass` for an empty submission, the
verifier is broken; see the smoke-task rationale at the top of
`tasks/cpp/t0-sanity-log-on-beginplay/task.md`.

### Debugging with `--keep-workdir`

When a layer fails, the workdir is preserved automatically. Pass
`--keep-workdir` (or `--workdir /explicit/path`) to keep it even on
success. Useful contents:

- `<workdir>/CraftBenchTemplate/` — the substrate copy with the
  agent submission applied. Open in the UE editor to repro by hand.
- `<workdir>/out/l1_build.log` — full UBT stdout+stderr.
- `<workdir>/out/l2_pie.log` — full editor automation log; grep for
  `Test Completed. Result=` for per-test outcomes.
- `<workdir>/out/report.json` — the machine-readable report.

## Running the unit tests

```bash
python -m unittest discover -v tools/verify-single/tests
```

The unit tests cover task parsing, sandbox enforcement, and report
round-tripping. They do **not** require UE.

## Warm build cache (optional — ~6× faster L1)

L1 (the UBT build of both targets) is ~64% of a cold verify's wall time: each
verify normally recompiles the project's C++ from scratch in a fresh tempdir.
The **warm cache** keeps a prebuilt baseline and builds *incrementally* instead.
Historical UE 5.7.4 Win64 measurement: L1 **~21 s vs ~126 s cold** (full
L1+L2 **~58 s vs ~250 s**) — and L2 also drops because the slot's shader
DDC stays warm. Re-measure on UE 5.8 before publishing exact speedup claims.

Why a "slot", not a seed-into-tempdir: UBT bakes **absolute paths** into its
makefiles / `.response` files / action graph, so an incremental build is only
valid at the path the baseline was built at (seeding into a new tempdir rebuilds
almost everything — measured 64 s vs 70 s, no win). So the cache keeps a **fixed
slot** and *resets it to pristine* before each verify — restoring the
agent-writable dirs from a snapshot while KEEPING `Intermediate/`+`Binaries/` —
instead of a fresh tempdir. Then **every** source under the writable prefixes
(the reset-restored pristine files *and* the agent's overlaid files) gets its
mtime bumped strictly newer than every cached artifact, so UBT recompiles the
writable module against the EXACT current source. **This is the correctness
gate.** Bumping only the overlaid files is NOT enough: when a submission *edits*
an existing substrate file, the next verify's reset restores the pristine
version with its old snapshot mtime — older than the previous verify's `.obj` —
so UBT would skip recompiling it and silently reuse the prior compiled behavior
(e.g. an empty submission "passing" because a reference edit is still linked in).
Recompiling the whole (small) writable module each verify is the price of
correctness; the large modules (verifier tests, engine) stay cached, so warm is
still far faster than cold. A broken submission still recompiles and still FAILs.

Prime once (one cold build per slot, ~2 min + ~5 GB disk each), then add
`--warm-cache`:

```bash
# one slot (interactive single verifies)
python3 tools/verify-single/build_warm_baseline.py \
    --substrate CraftBenchTemplate --ue-root /path/to/UE_5.8

python3 tools/verify-single/run_task.py --warm-cache \
    --task tasks/<set>/<id>/task.md --submission <dir> --ue-root /path/to/UE_5.8

# N slots → N concurrent verifies all run warm (match batch-eval width)
python3 tools/verify-single/build_warm_baseline.py \
    --substrate CraftBenchTemplate --ue-root /path/to/UE_5.8 --slots 2
```

Invalidation is automatic + conservative: the baseline is keyed on the substrate
git **tree SHA** + UE version. A mismatch, an uncommitted substrate, a busy slot,
or a missing pool is a **cache miss → cold build** — warming never blocks and
never changes a verdict (at worst it does nothing). `--warm-cache` also honors
`CB_WARM_CACHE=1`. The pool lives at
`%LOCALAPPDATA%/CraftBench/warm-baseline/<substrate>/slot-<i>/` (override with
`CB_WARM_CACHE_DIR`). Forced cold by `--workdir`, `--substrate-from-live`, and
`--harness aura` (the baseline is built Aura-disabled). Via the `cb` launcher:
`cb warm-prime --warm-slots N`, then `cb batch-eval <dir> --warm-cache` or
`cb discriminate --task <id> --warm-cache` (the discrimination matrix's legs each
build warm; `cb discriminate` keeps logs readable via `run_task.py --out-dir`).

## Scoring an in-place Aura (or other UE-Editor-plugin) agent

The default `--submission` flow assumes the agent produced a clean
directory tree of edits that the runner overlays onto a fresh
substrate copy. For an interactive UE Editor plugin like Aura, edits
land directly in the live UE project (`UE-projects/CraftBenchTemplate/
Source/CraftBenchTemplate/...`) — there's no separate "submission
directory."

Use `--submission-from-project` for this case:

```sh
# 1. Open UE-projects/CraftBenchTemplate/CraftBenchTemplate.uproject
# 2. Paste the task prompt into Aura's input UI
# 3. Aura makes edits; close + save the editor
# 4. Score the current project state:
python tools/verify-single/run_task.py \
    --task tasks/flagship/gp-spawn-sequence/task.md \
    --submission-from-project UE-projects/CraftBenchTemplate/ \
    --ue-root "/Users/Shared/Epic Games/UE_5.8" \
    --no-nullrhi
```

The runner extracts the agent-**submittable** subtree into a tempdir
and uses that as the submission. Aura's intent IS the submittable-subtree
state.

**This paragraph deliberately does not restate what "submittable" means.**
`extract_writable_subset_from_project` decides every candidate path by
calling `sandbox._is_writable` — literally the predicate `scan_submission`
runs over its output moments later — against the substrate's
`AGENT_WRITABLE.json`. For the paths, read that manifest; for the rule,
read `sandbox.py::_is_writable`; for what happens to an accepted `Config/`
file afterwards, read `config_lane.py`.

Why the pointer instead of a list: the list that used to sit here had
drifted. It said files under `Config/` are never submitted, which stopped
being true when the manifest's `config_writable` key opened the semantic
config lane (a listed `Config/` file is path-accepted by exact rel-path,
then its ini diff is gated against the task spec's `config_allow`), and
`extract_writable_subset_from_project` honours that key as of 2026-08-19.
A prose copy of a rule is still a copy of the rule.

Anything the predicate rejects is simply not extracted. This lane can only
decline to submit a file, never raise a per-path sandbox violation — the
deliberate difference from `--submission`.

### Resetting between tasks

The verifier never modifies your project (it operates on a workdir
copy), so a reset is just restoring the writable subtree to the
substrate baseline. Easiest if the substrate is in git:

```sh
git checkout -- UE-projects/CraftBenchTemplate/Source/CraftBenchTemplate/
```

Then move on to the next task: paste its prompt into Aura, repeat.

### Headless / multi-task automation

A full "start a new conversation, generate, verify, repeat" loop needs
Aura to be invocable from outside the editor. As of 2026-05-20, Aura
is paste-prompt-in-UI interactive, so the loop above is human-driven.
When Aura adds a programmatic invocation path (CLI, IPC, Python API
inside the editor), the manual paste step becomes a single
`subprocess.run` call and the whole pipeline can run unattended; the
agent-backend interface is already shaped to receive it.

## PIE-native fixture conventions

The runner's L2 stage runs `AFunctionalTest`-derived fixtures in a **real PIE
world** (headless, `-nullrhi`). The base class `ACraftBenchFunctionalTest`
overrides `IsEditorOnlyLoadedInPIE()→true`, which routes the map-based automation
test into PIE rather than the Editor World it used to land in. Full pattern +
recipes: `docs/pie-verification-playbook.md` (the original pattern doc with
the engine citations was deleted with the specs tree; git history). The key
conventions (the inverse of the old Editor-World ones):

1. **Let the engine drive the lifecycle — never tick it yourself.** In PIE,
   `BeginPlay` auto-fires on placed actors *before* `PrepareTest`, the engine
   ticks the fixture every frame, and `FTimerManager`/`CharacterMovement` run
   naturally. A manual `World->Tick`/`Actor->Tick` from inside the test is
   **re-entrant** (StartTest/Tick already run inside the engine's world tick) and
   trips `Assertion failed: !TickCompletionEvents[Index].Num()
   [TickTaskManager.cpp:1097]`. Do **not** call `DispatchBeginPlay` or
   `AdvanceWorldBy` — they are the dead Editor-World pattern.

2. **Observe via a checkpoint schedule.** A fixture overrides `PrepareTest`
   (resolve the tagged actor + `SetCheckpointSchedule({t0, t1, ...})`) and
   `OnCheckpoint(idx, t)` (sample state + `FinishTest(Failed)` on a miss). The
   base's `Tick` fires `OnCheckpoint` as each scheduled **world game-time**
   (`GetWorld()->GetTimeSeconds()` — the clock the agent's timers/gravity use)
   is crossed, then `FinishTest(Succeeded)`. See `SpawnSequenceFunctionalTest`
   (~30 lines) for the reference. `SetCheckpointSchedule` also sets a `TimeLimit`
   so a stuck test FAILS instead of hanging.

3. **`FTimerManager` now works** — it ticks in PIE. The retired
   `gp-timer-delayed-destroy` task modeled framerate-independence checks by
   running the same fixture in two PIE processes at different `-FPS` rates
   (60Hz + 20Hz — today declared via the spec's `fps_legs:` front-matter key /
   `## Verifier framerate legs` section); a wall-clock `SetTimer` solution
   passes both, a tick-count overfit fails the 20Hz leg.

4. **BeginPlay-window observation** (e.g. "logged *during* BeginPlay"): the
   listener must be installed *before* BeginPlay, which auto-fires before
   `PrepareTest`. Use `FWorldDelegates::OnWorldInitializedActors` (fires after
   `PostInitializeComponents`, before BeginPlay), filtered to
   `Params.World == GetWorld()` + a single-shot guard. See `SanityFunctionalTest`.

5. **Determinism + Aura.** The runner passes `-deterministic -FPS=<rate>` (fixed
   dt from frame 0) and disables the Aura plugin in the cloned workdir `.uproject`
   (Aura needs CEF3, absent headless — its load failure otherwise aborts the
   editor). Both are handled by `run_l2` / `_disable_plugin_in_uproject`.

## Mac / UE 5.7 quirks resolved on first real run (2026-05-19)

The four-assumption "TODO(verify-against-UE)" list that previously
lived here was discharged by the first end-to-end run against UE 5.7.4
on Apple Silicon Mac. Recording outcomes here so future contributors
have the resolution trail.

1. **L2 test-filter syntax — resolved.** Confirmed via UE's own
   `Automation List` output: canonical form is
   `Project.Functional Tests.Maps.<MapName>.<ClassNoAPrefix>`. UE
   strips `/Game/` from the level path (so `/Game/Maps/L_X` becomes
   `Maps.L_X`) AND strips the `A` prefix from `AActor` subclass
   names. `derive_test_filter` in `run_task.py` produces this form.

2. **`-testexit` is honored but `RequestExit` is not** — resolved by
   workaround. `-testexit="Automation Test Queue Empty"` is the correct
   spelling and is honored by the automation framework, but the Mac
   build of `UnrealEditor-Cmd` ignores `FPlatformMisc::RequestExit`
   ("return code will be ignored by the generic implementation").
   The editor logs `**** TEST COMPLETE. EXIT CODE: N ****` and
   `LogExit: Exiting.` but then sits in the Cocoa runloop indefinitely.
   `l2_pie.py::_run_editor_with_marker_kill` streams stdout line by
   line and SIGTERMs the process when any terminal marker appears,
   giving it an 8 s grace period to flush the JSON report first.

3. **Warning-line regex pinning to agent files — still advisory.**
   `_WARNING_RE` in `l1_build.py` matches clang+MSVC formats and
   substring-matches against the manifest's writable prefixes. Not yet
   exercised on a real warning-emitting submission; the
   `.gen.cpp`-back-mapping caveat below remains hypothetical.

4. **`UnrealEditor-Cmd` binary location on macOS — resolved.** UE 5.7
   ships the binary at flat `Engine/Binaries/Mac/UnrealEditor-Cmd`,
   NOT inside `UnrealEditor.app/Contents/MacOS/`. `_editor_binary`
   tries the flat path first and falls back to the bundled path for
   older installs.

5. **NEW: UE writes `index.json` with a UTF-8 BOM.** Python's
   `json.loads` rejects BOMs with `JSONDecodeError`. `parse_index_json`
   strips a leading `﻿` defensively before parse.

6. **NEW: editor logs are localized.** On a non-English-locale
   install, `Result={...}` is also localized (Chinese:
   `Result={失败}`), so the `_RESULT_RE` regex misses. Added
   `_TEST_RESULT_RE` matching `TestResult=(Passed|Failed|Skipped)` as
   a locale-stable fallback — `FinishTest` always emits in English.
   `index.json` should be the primary signal in any case (its `state`
   field is locale-stable English).

7. ~~**AFunctionalTest runs in Editor World, not PIE.**~~ **SUPERSEDED
   2026-06-01 — L2 now runs in a real PIE world** (the fixture base
   overrides `IsEditorOnlyLoadedInPIE()→true`), so `BeginPlay` auto-fires
   and fixtures no longer call `DispatchBeginPlay`. BeginPlay-window
   observation now installs its listener via
   `FWorldDelegates::OnWorldInitializedActors` (before BeginPlay). See
   *PIE-native fixture conventions* above. (Original dated finding kept
   for the resolution trail.)

## Windows (validated — UE 5.8)

**Windows is the validated platform**, and the only one CI runs. All three
gating layers are exercised there: L1 (UBT build of both targets), L2
(`AFunctionalTest` in headless PIE) and L2I (`.uasset` introspection). The
runner selects Windows-correct paths at runtime and the substrate is
clone-and-go once `tools/scripts/bootstrap_substrate.py` has run.

To check the shipped set yourself rather than take a number on trust:
`cb batch-eval --references all` grades every committed reference solution.
Per-task validation status is in [`tasks/CATALOG.md`](../../tasks/CATALOG.md),
which is generated from disk. Full platform notes live in
[`docs/WINDOWS.md`](../../docs/WINDOWS.md).

Windows gotchas worth knowing: cold 5.8 verifies must use a **short
`--workdir`** (e.g. `C:\cb58\wd`) to dodge the 260-char `MAX_PATH` limit, and
on RAM-constrained hosts (≤32 GB) cap UBT parallelism with
`CRAFTBENCH_L1_MAX_PARALLEL=2` (full-parallelism editor PCH compiles exhaust the
commit charge and `cl.exe` fails with `C3859`).

The Windows-specific code paths wired:

1. **L1 UBT via `cmd /c Build.bat`.** `_build_script` in `l1_build.py`
   resolves `Engine\Build\BatchFiles\Build.bat` on Windows (vs the
   `Mac/`/`Linux/` `Build.sh` on the POSIX hosts), and `_platform_arg`
   maps the host to the `Win64` UBT platform token. Because `CreateProcess`
   rejects a bare `.bat` under `shell=False`, the Windows command is wrapped
   as `cmd /c <Build.bat> ...`; macOS/Linux still exec `Build.sh` directly,
   unchanged.
2. **L2 `Win64` editor path + variant-OS detection.** `_editor_binary` in
   `l2_pie.py` returns `Engine\Binaries\Win64\UnrealEditor-Cmd.exe` on
   Windows. The branch matches the host **family** case-insensitively, so a
   Git-Bash / MSYS / Cygwin Python (`MSYS_NT-…`, `MINGW64_NT-…`,
   `CYGWIN_NT-…`) resolves the same `.exe` instead of falling through to the
   unsupported-OS error.
3. **LF pinning via `.gitattributes`.** On a Windows checkout, git's default
   `core.autocrlf=true` rewrites LF → CRLF in tracked text. The root
   `.gitattributes` pins `*.uproject` to `text eol=lf` and marks `*.umap` /
   `*.uasset` as `binary` so the committed UE maps/assets are never
   re-normalized. (Historical: this also protected the per-file hash
   comparisons of the hash-manifest gate, retired 2026-07-16.)
4. **`git` + `tar` on `PATH`.** A fresh Windows clone must apply
   `.gitattributes` (so `git` is required), and some packaging/snapshot flows
   shell out to `tar` (Windows 10 1803+ / 11 ship `tar.exe`). See the
   prerequisites table in `docs/WINDOWS.md`.

**Not yet exercised on Windows** (edge cases the 22/22 pass did not hit): NTFS
case-folding in the `sandbox.py` writable-prefix check, and whether the editor
honors `RequestExit` natively (the marker-kill is platform-agnostic and carries
over regardless). These are corners of the code paths, not the core L1+L2+L2I
path — that is validated.

## Caveats still standing

- **`.gen.cpp` warning back-mapping under `--strict-warnings`.** If
  warnings on agent-edited headers surface only against the generated
  `*.gen.cpp`, `_count_warnings` won't credit them to the agent.
  Untested; extend if/when it bites.
- **L3/L4/L5 layers.** Not yet implemented; the runner short-circuits
  cleanly on tasks that declare only L1+L2. Add each layer when the
  first task in flight requires it. The layer interface (per the planning
  tree's `contracts/substrate-adapter.md` — deleted with the specs tree;
  git history) permits new layer names without a schema change;
  `score-report.schema.md` (same deleted contracts tree) accommodates
  additional layer results in `verdicts[*].layer_results`.

## Maintenance notes

- **Verifier-module integrity = git-HEAD provenance + human review.**
  The hash manifest (`verifier_hashes.json`, exit 3, `--regen-verifier-hashes`)
  was retired 2026-07-16: the runner materializes the graded substrate from
  git HEAD, so on-disk tampering with `Source/CraftBenchTests/` never reaches
  the grade, and human review gates any committed
  change to the verifier module. `pinning.py` records `substrate_revision`
  as the provenance anchor in every report.
- `UE-projects/<name>/AGENT_WRITABLE.json` is the source of truth for
  sandboxing. Adding a new agent-writable path (e.g. a second game
  module) means editing the manifest; do not hard-code path lists in
  the runner.
- The runner deliberately does **not** call any third-party Python
  packages. Adding one (e.g. `pydantic`, `click`) breaks the "drop
  on any CI runner without `pip install`" contract.

# Discrimination matrix — t1-blueprint-event-to-action

Verdicts are from the DETERMINISTIC verifier (no agent, no tokens). Run with
`cb discriminate --task bp/t1-blueprint-event-to-action --wip` until the
fixture, baseline Blueprint, and map binaries are committed.

Design: **L1 + L2 only** (pie-checkpoint-sampling). The fixture resolves the one
placed actor by the `DelayedMoverRoot` tag, applies three asset-surface pins
(asset exists at the required path / placed actor is an instance of it / the
Blueprint chain itself implements a start-or-tick event), then samples the
actor's location at world-time `{0.5, 1.5, 2.5}` s against
`Start = (0, -400, 150)` and `Start + (300, 0, 0)` with a 2-unit tolerance.

Every backticked expected-substring below is a verbatim literal inside ONE
string literal of
`UE-projects/CraftBenchTemplate/Source/CraftBenchTests/Tasks/t1-blueprint-event-to-action/DelayedMoveFunctionalTest.cpp`
(none spans a printf placeholder).

## Requirements table (checklist §7a — the mandatory soundness artifact)

One row per requirement in the agent-visible prompt. `file:line` points at the
named assertion in `DelayedMoveFunctionalTest.cpp` (fixture as authored;
re-check line numbers if the fixture is edited).

| Requirement (prompt) | Asserted | Check / assertion (file:line) | Skipped when | What a submission could get away with |
|---|---|---|---|---|
| Behavior authored inside the editable asset at the required path | **partially** | Pins 1-3: asset loads (`:105`), placed actor `IsA` it (`:118`), BP chain declares own ReceiveBeginPlay/ReceiveTick, ExcludeSuper (`:130`) | unconditional (PrepareTest, before any checkpoint) | Hybrid: a trivial BP event plus the real motion in a C++ edit to the scaffold parent passes the structural pin (stated residual in task.md) |
| Exactly one placed object; not destroyed or replaced | **fully** | Tag count == 1 (`:92`); weak-pointer identity pin re-checked every checkpoint (`:147`) | unconditional / each checkpoint | Nothing — extras fail the count, substitution fails the stale-pin check |
| Stays at its placed position until the 1.0 s delay elapses | **fully** | cp0 at t=0.5: `Dist(Loc, Start) <= 2.0` (`:163`) | only if PrepareTest already FinishTest'd (verdict is already FAIL) | A move landing inside (0.5, 1.0) fires earlier than the stated delay but between samples; bounded by the disclosed 0.5/1.5 bracket |
| Moves exactly +300 world X from its placed position by 1.5 s | **fully** | cp1 at t=1.5: `Dist(Loc, Start+(300,0,0)) <= 2.0` (`:179`); Start is off-origin so absolute (300,0,0) lands ~500 units wrong | prior FAIL only | Smooth interpolation arriving within the window and stopping (accepted residual — observationally equivalent) |
| Never moves again after the single translation | **partially** | cp2 at t=2.5: still `<= 2.0` units from the target (`:193`) | prior FAIL only | Leave-and-return strictly inside (1.5, 2.5) between samples (stated residual; one post-arrival sample, not continuous policing) |
| Do not edit any level or test file | **fully** | Sandbox: `Content/Maps/` + `Source/CraftBenchTests/` deny (exit 4, `AGENT_WRITABLE.json`); grading from git HEAD | unconditional, outside the fixture | Nothing |

No requirement is left as unenforced prose: the one prompt sentence that is
only partially attributable ("entirely inside that asset") is gated by the
structural pin and its residual is stated in the spec rather than silent.

## Per-submission rows

Format is normative: first column = the submission, an **Overall** column, and
an **Expected message** column whose backtick-wrapped literal must appear in
the L2 log (a wrong-reason FAIL — compile error, sandbox reject, SKIPPED —
does not count).

| Submission | Overall | Fails at | Expected message |
|------------|---------|----------|------------------|
| `../reference` | **PASS** | — | BP graph: start event -> 1.0s delay -> single +300 X move; all gates green (L1 both targets, L2 3/3 checkpoints) |
| empty (no overlay -> baseline BP with empty graph) | **FAIL** | L2 PrepareTest pin 3 | `does not itself handle a start-of-gameplay or per-frame event` |

Hypothetical variants (documented, NOT materialized — per the 2026-08-11
amendment, variants are authored only for a hole the requirements table finds;
these rows exist to name which assertion each classic cheat would hit):

| Would-be variant | Overall | Fails at | Expected message |
|------------------|---------|----------|------------------|
| instant-move (no delay; moves at gameplay start) | **FAIL** | L2 cp0 | `must still be at its placed start position` |
| no-move (event wired, delay wired, no move node) | **FAIL** | L2 cp1 | `must have completed its single move to start + (300, 0, 0)` |
| keeps-drifting (moves +300 then keeps moving) | **FAIL** | L2 cp2 | `moved again after its single translation` |
| cpp-only (behavior as C++ BeginPlay on the scaffold; BP untouched) | **FAIL** | L2 PrepareTest pin 3 | `does not itself handle a start-of-gameplay or per-frame event` |
| destroy-respawn (spawns a copy at the target, destroys the original) | **FAIL** | L2 checkpoint | `the tracked actor no longer exists` |

## Calibration — contingencies to resolve on the authoring-lane run

- **Empty-row message contingency.** The expected message for the `empty` row
  assumes the committed baseline `BP_DelayedMover` carries NO event
  implementations (no ReceiveBeginPlay/ReceiveTick stubs on its generated
  class). If the editor's Blueprint factory leaves compiled template/ghost
  event stubs, the empty leg will instead fail at cp1 with
  `must have completed its single move to start + (300, 0, 0)` — still a named
  FAIL, but this row must then be updated from the `cb discriminate --wip`
  evidence, and `aids/author_reference.py` must strip the stubs at baseline
  authoring time.
- **cp0 sample-time margin.** The checkpoint clock is world game-time; cp0
  (scheduled 0.5 s) actually fires at `max(0.5, IsReady->StartTest warmup)`.
  Warmup measured ~0.3 s on t0-sanity; confirm on the reference run that cp0's
  logged `t=` is < 0.9 s (it must sample before the 1.0 s delay fires). If it
  ever crowds 1.0 s, widen the schedule (e.g. delay 1.5 s, cps {0.75, 2.0,
  3.0}) in fixture + prompt + this file together.
- **Reference PASS / empty FAIL** are the automatic non-vacuity legs of
  `cb discriminate`. UPDATE 2026-08-12: map + baseline (39433c2) and the
  MCP-graph-lane reference (09781a8) are committed, and `cb refgate
  bp/t1-blueprint-event-to-action` graded the reference **PASS from git HEAD
  (109 s)**. The empty-FAIL leg rides the next `cb discriminate` run.

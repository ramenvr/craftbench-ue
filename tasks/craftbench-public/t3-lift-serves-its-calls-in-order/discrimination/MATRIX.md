# Discrimination matrix — t3-lift-serves-its-calls-in-order

The self-validation oracle: the reference must PASS, and the empty leg must FAIL
**at the predicted gate, via the named substring**. A wrong-reason FAIL (an L1
build failure, a different gate, `SANDBOX-REJECT` exit 4, `HARNESS-PRECONDITION`)
means the gates are NOT discriminated — fix them, or relabel the task for the
weaker property it actually tests.

## Three parser rules this file is written against

- **One parseable row per label.** `parse_matrix` returns
  `Dict[label -> MatrixRow]`, so a second table repeating a label silently
  overwrites the first. Exactly **one** table below; everything else is prose.
- **A variant cell must contain a `/`.** A row is only classified as a variant
  when `"/" in first` (`discriminate.py:286`), so a bare `fifo-queue` is silently
  DROPPED. This task ships no hand-authored variants (see below), so the point is
  recorded rather than exercised.
- **A backticked substring must (a) contain a space or one of `(),.=` and
  (b) fall inside ONE literal run of the fixture's format string.** Both cells
  below were checked against the source: each is a contiguous span of one string
  literal with no `%` placeholder inside it, ASCII-only.

| Submission | Expected verdict | Expected substring | Which gate, and why it is the one that fires |
|---|---|---|---|
| `../reference` | PASS | `served every call in lift order` | All gates green. The lift opens at [1,2,3] on leg 1 and [3,2,1,3] on leg 2, arrives level every time, holds 3.0 s at each stop, never moves with its doors apart, measures ~200 uu/s on all five trips, carries the rider, and keeps all three signs on the nearest floor and the committed next direction. The literal is the `FinishTest(Succeeded, ...)` text in `EvaluateDeferredGates`. |
| `empty` | FAIL | `NoCallIsEverDropped: a pad was pressed for floor` | The unmodified scaffold compiles (the doors, lamps, pads and signs are all supplied and working), so **L1 is green and the failure is behavioural**. The drive walks the character onto landing 1's call pad at about t=1.3 s; nothing is bound to any pad, so the lamp never lights, and `CheckLatchedLamps` fires 0.5 s later. Predicted t about 1.8 s -- the earliest, cheapest named FAIL in the task. |

## Why the empty leg fails at the LAMP clause and not somewhere else

Worth stating, because it is the one prediction in this file that a reader would
guess differently. Walked in order for the inert scaffold:

- `TheSuppliedMachineryIsStillThere` — passes; nothing is missing.
- `TheNumbersOnTheCarAreNotYoursToRewrite` — passes; nothing rewrites them.
- `TheLandingsAndTheCarStayedWhereTheyWerePut` — passes; nothing moves.
- `TheCarNeverMovesWithItsDoorsOpen` — never armed; the car never moves.
- `TheCarStopsLevelWithTheLandingItServes` / `TheDoorsHoldOpenLongEnoughToGetOut`
  — never armed; the door fraction never leaves 0.
- `TheCarActuallyTravelsAndTakesItsRiderWithIt` (i) — **deliberately not armed**:
  the only outstanding call is floor 1 and the car is already level with landing 1,
  so the progress watchdog is correct to demand nothing.
- `NoCallIsEverDropped` clause B — **fires**, at press + 0.5 s.

If the lamp clause were ever removed, the empty leg would instead die about 27 s
later at the wait-for-doors-open deadline, which routes through the *same* gate
name (`NoCallIsEverDropped: somebody stepped on the pad for floor …`) because the
fixture's own record still holds an unserved press. That is by design: the gate a
deadline is attributed to is derived from whether anything is outstanding, not
fixed per step.

## Gates with no hand-authored variant, and why that is honest

Per the 2026-08-11 owner decision, variants are written for a hole the
requirements table finds, not one per gate. The requirements table in `task.md`
maps every prompt sentence to an assertion with no gaps, so this task ships the
two mandatory legs and no more. What each un-varianted gate would be caught by,
if somebody wants to prove one later — every one of these is a real first-pass
implementation, not a strawman. **Written as a list and not a table on purpose**:
`parse_matrix` reads every pipe-table in this file, so a second one risks a
phantom row (one of these entries contains a `/`, which is exactly the token that
classifies a cell as a variant directory).

- **a press-order (FIFO) queue** → `TheLiftServesWhatIsOnTheWayBeforeItTurnsAround`,
  on the SECOND opening of leg 1: observed floor 3, expected floor 2.
- **nearest-outstanding-call-first** → same gate, on the second opening of **leg 2**:
  it turns round at the pad-3 press and opens at 3 where the answer is 2.
- **`if (State != EState::Idle) return;` in the pad handler** → `NoCallIsEverDropped`:
  the mid-close pad-3 press is discarded and the lift never leaves landing 1.
- **a single `int32 TargetFloor` overwritten by each press** → `NoCallIsEverDropped`
  clause A: leg 1's pad-2 press erases floor 3.
- **`if (Floor == CurrentFloor) return;`** → `NoCallIsEverDropped`: the doors never
  reopen for either leg's opening press.
- **the call lamp cleared in the end-overlap handler** → `NoCallIsEverDropped`
  clause B, at about t = 10 s (the in-car pad-3 press; **not** the landing-1 press —
  see `notes.md` item 6).
- **landing heights cached in `BeginPlay`** → `TheCarStopsLevelWithTheLandingItServes`:
  leg 2's stop at landing 2 is ~800 uu out.
- **even spacing (floor N at N times a constant)** → same gate: 350 uu out on leg 1
  already.
- **the heights read off the committed level while authoring** → same gate: the
  committed floor-2 sill is a decoy 650 uu from the staged one.
- **a fixed trip duration** (`Alpha += Dt` over `TravelSeconds`, then a lerp) →
  `TheCarTravelsAtTheSpeedWrittenOnIt`: one trip time measures a different speed on
  every one of the five trips.
- **snapping the car to its destination in one frame** → same gate, and
  `TheCarNeverMovesWithItsDoorsOpen` if the doors were not shut first.
- **moving only the cage and the leaves** →
  `TheCarActuallyTravelsAndTakesItsRiderWithIt` (ii): the sill is read off
  `Platform`, which is what the rider stands on.
- **teleporting the character to the destination landing** → same clause.
- **`CloseDoors(); StartTravel();` issued together** →
  `TheCarNeverMovesWithItsDoorsOpen`.
- **the hold timed from arrival instead of from fully-open** →
  `TheDoorsHoldOpenLongEnoughToGetOut`: 2.0 s of a 3.0 s hold is eaten by the door
  travel.
- **a lift that starts toward its next call as soon as the doors are open** (serve,
  open, and ease away while the door animation finishes) →
  `TheCarStandsStillLongEnoughToStepOut`, at the first stop it drifts more than 5 uu
  inside the hold. Not caught by `TheCarNeverMovesWithItsDoorsOpen`, which forgives
  1 uu per frame — 60 uu/s at the fixed step, i.e. ~180 uu across a 3 s hold. Added
  after the owner's 2026-08-19 play-test.
- **a submission that tests the supplied door fraction with `>= 1.0f`** → nothing: it
  is CORRECT and the scaffold's accessor now guarantees it. Listed here because it was
  a live trap until 2026-08-19 and it hung the reference itself; see `notes.md`
  § "The door never reached 1.0".
- **the arrow driven from the car's velocity** → `TheSignSaysWhichFloorAndWhichWay`:
  leg 2 parks at landing 1 with landing 3 outstanding, where the truth is UP and
  velocity says none.
- **only the sign at the floor the lift stopped at** → same gate: the other two go
  stale.
- **dragging landing 2's deck to wherever the car is** →
  `TheLandingsAndTheCarStayedWhereTheyWerePut`.
- **`TravelSpeedUuPerSecond` rewritten at play** →
  `TheNumbersOnTheCarAreNotYoursToRewrite`.

## Status

**BOTH ROWS ARE STILL PREDICTIONS, AND THE REFERENCE ROW HAS ONCE BEEN MEASURED
FALSE.** Two PIE runs on 2026-08-19 FAILED the reference at
`NoCallIsEverDropped: a pad was served for floor 1` — the doors physically opened but
`GetDoorOpenFraction()` never returned exactly `1.0f`, so the call was never
discharged. That was a real defect in the SUPPLIED door accessor, not in the scheduler,
and it is fixed (`notes.md` § "The door never reached 1.0"). Nothing has been re-run
since, and the map binary must be **re-authored** first (`TowerRoof` is new). So: the
`empty` row remains an unmeasured prediction, and the `reference` row is a prediction
that has already been wrong once — treat a PASS as unproven until `cb discriminate`
says otherwise.

Three things to read out of the next reference run's `[t3-lift calib]` lines before
believing anything: the frame the lamps go dark after the first opening (the snap), a
`served=` count that climbs past 1, and — new — that no stop trips
`TheCarStandsStillLongEnoughToStepOut`.

The first `cb discriminate --task craftbench-public/t3-lift-serves-its-calls-in-order --wip`
run is expected to need one or two iterations for harness reasons rather than
model reasons; the memory law "the drive manufactures FAILs" applies with force to
a twenty-five-step two-leg drive with eight every-frame gates. The three numbers to
read out of the reference run's `[t3-lift calib]` lines before believing anything
are listed in `notes.md` § "What is still unproven".

**Run it with `--warm-cache`.** The leg workdir is derived from
`runs/discriminate/<set>__<id>-<ts>/<leg>/wd/`, and this task's id is longer than
the plate-door task's, which already exceeded Windows `MAX_PATH` (260) on the cold
path — UBT refuses with exit 6 before compiling anything and every leg comes back
BAD with nothing tested. The warm pool builds in a fixed 85-character path
instead.

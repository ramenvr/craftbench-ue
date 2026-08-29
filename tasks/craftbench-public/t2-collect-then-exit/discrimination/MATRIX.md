# Discrimination matrix — t2-collect-then-exit

**REFERENCE + EMPTY ONLY** (owner directive 2026-08-18). No variant legs. The
discrimination is carried by the nine per-checkpoint named gates plus five
continuous guards: an empty submission fails at the first of them, and each gate is
independently named and greppable. See `docs/TASK-AUTHOR-GUIDE.md` step 7
for the reasoning and for what this deliberately gives up.

Substring law that bit sibling tasks in this set, and applies here: a backticked
substring must contain a space or one of `(),.=` **and** fall inside ONE literal run
of the fixture's format string. A bareword tick is discarded as a parenthetical and
the parser then matches the WHOLE cell (which appears in no log); a phrase spanning a
`%s`/`%d` matches the LOG but is not statically anchorable, which
`test_matrix_substring_oracle` rejects. Two ticked literals per row, ALL-of
semantics, each inside its own run.

| Submission | Overall | Named substring(s) | Why |
| --- | --- | --- | --- |
| `../reference` | PASS | `three relics gathered, the exit opened` | Overlap handlers on the relics and the exit, the count held on the exit, board and lamp driven from it. Measured, all nine checkpoints: `0/3 SEALED lamp=0` with four relics standing → sealed contact at cp1 (`inExit=1`, still dark, still not won) → `1/3` → re-touch at cp3 still `1/3` → `2/3` → second sealed contact at cp5 → `3/3 OPEN lamp=6000` at cp6 → `ESCAPED` at cp7 → still `ESCAPED` at cp8 after leaving and re-entering. Relics on the floor go 4 → 3 → 2 → 1, and that last one is the control the route never visits. |
| `empty` | FAIL | `TallyMatchesWalkIns: the tally face read` + `a blank face reads as nothing at all` | The unmodified scaffold compiles, so L1 is green and the failure is behavioural. Both board faces ship BLANK, so `ReadTally()` cannot parse `<int>/<int>` and returns -1 against a fixture count of 0. Measured at cp0: `taken=0 tally='' status='' lamp=0 relics=4`. Note the -1 is deliberate: it is never GREATER than the fixture's count, so a blank board cannot trip the over-count guard and mask the real reason — it fails on the readout gate, which is the honest one. |

## What carries the discrimination without variants

Nine checkpoints, each with its own named message, and the pairs are chosen so a
partially-correct submission cannot slide through:

- **cp1 and cp5 are the divergent pair.** Both are contacts with a SEALED exit, at
  0 and 2 relics. An exit that stays dark but wins on locked contact passes the
  darkness gate and fails the win gate; an exit that lights early fails the darkness
  gate. Two independent ways to be wrong, two distinct messages.
- **cp3 is the re-touch.** The route steps 300 cm off a gathered relic's spot and
  walks back over it. A submission that counts on overlap without consuming the relic
  reads `2/3` here instead of `1/3`.
- **cp6 separates OPENING from WINNING.** The third relic must open the exit
  (`OPEN`, lamp >= 5000) and must NOT win it. A submission that wins on the third
  pickup fails cp6's second clause.
- **cp7 then cp8 separate WINNING from STAYING WON.** Leaving the exit and walking
  back in must change nothing.
- **Five continuous guards run every frame**, so there is no gap between samples to
  thread: the exit cannot light before the third relic, a win needs an entry the
  fixture agrees happened, the tally can never exceed the fixture's own count, a lit
  lamp cannot go dark and an ESCAPED status cannot un-escape, and the control relic
  must be present and unmoved at every single frame — not merely at checkpoints.

## The one-sided margin, and why it cannot false-FAIL correct work

The fixture's contact radius is 300 cm; the engine's begin-overlap edge fires at
centre-to-centre 120 + 34 = 154 cm (the shipped `RelicVolume` plus `ACharacter`'s
default capsule). So the fixture always registers a contact several frames BEFORE the
engine can. That direction is the safe one: `Taken` is the upper bound the
submission's readouts are checked against, so a legitimate pickup can never make
`ReadTally() > Taken` and can never light the lamp while `Taken` is still 2. The
fixture may count early, never late, and the submission is never asked to match the
fixture's instant.

It cannot fire spuriously either: the centre lane the exit legs walk is 500 cm from
the nearest relic, and no two relics are within 500 cm of each other — both outside
300. The tightest clearance on any leg is the walk from the exit to relic A, which
passes ~400 cm from relic C.

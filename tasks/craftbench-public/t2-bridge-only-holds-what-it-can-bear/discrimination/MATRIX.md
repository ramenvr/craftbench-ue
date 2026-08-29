# Discrimination matrix — t2-bridge-only-holds-what-it-can-bear

**REFERENCE + EMPTY ONLY** (owner directive 2026-08-18). No variant legs.

| Submission | Overall | Named substring(s) | Why |
| --- | --- | --- | --- |
| `../reference` | PASS | `Test Completed. Result={Success}` | Each span answers for itself. Every frame it takes its **own deck's live world bounds**, sums the stamped weight of every `YardLoad` actor and the possessed character whose middle is over that box and whose base is on it, and drives the three supplied switches from that: heave back up only when the count reaches zero, give way when the total exceeds the live rating, otherwise command a sag of total/rating. Nothing in it knows there are two spans, where either of them stands, or what anything weighs. That is exactly why differently-rated spans, per-run numbers, a character who gets heavier mid-round and a deck that ends up two metres lower all cost it nothing. |
| `empty` | FAIL | `TheSagShowsTheWholeLoad: how far a span sags has to show the whole load` | The unmodified scaffold compiles, so L1 is green. The deck moves, sags, gives way and heaves back up on command — nothing commands it. The first measured stand puts the character alone on the WEST span at 0.40 of its rating; the fixture requires a sag of 0.400 within 0.12 and measures 0.000, and fails 2.5 s into that stand. |

## Requirements table

See the full **Requirement-to-assertion map** in `../task.md` — every prompt sentence
is mapped there to the gate that checks it and to the condition under which that gate
is skipped. The two rows worth repeating here, because they are the ones a reader
assumes are unguarded:

| Prompt requirement | Gate | When it does NOT run |
| --- | --- | --- |
| "it must reach each new state within two seconds" | the 2.5 s settle window itself — at 2.5 s after the fixture's truth changed, the deck must ALREADY be in the new state | never |
| "the character is walked on and off both spans, over and over" | `TheYardFinishedItsRounds`, which counts a stand only when the character is standing on the span that stand names | never — it is both the sentinel gate and the early-exit predicate |

## What carries the discrimination without variants

**The thing being measured MOVES because of the measurement.** Occupancy is computed
against a deck whose height is a function of that occupancy, and after a collapse the
deck is 200 cm from where it was staged. A footprint worked out once at start-up is
correct for the first four measured stands and wrong for the fifth: the probe is
looking at an empty patch of air, the span reads empty, and it heaves back up under
the anvil three seconds later. `ItStaysDownWhileSomethingIsOnIt` is the only gate that
sees it, and its message says so in as many words. **That gate is worth the whole
task**, and the honest claim about this task's difficulty is one strong trap plus one
moderate one (a total that only ever goes up, because departures were never wired).

**Every number is drawn per run.** Both ratings, all three crate weights and both of
the character's masses are drawn from a seeded range and stamped into the world
*before any placed actor's `BeginPlay`*. A submission that hard-codes anything is
wrong on the first stand, and there is no window in which a remembered value is the
right one. The seed and the drawn numbers are on one log line, so a FAIL is
reproducible without a re-run.

**The fixture computes from what it wrote, never from a re-read.** This is what makes
`TheCharactersOwnWeightCounts` a real gate rather than an unfailable one: if the
fixture re-read the character's mass, a submission that zeroed it would take the
character out of the fixture's own arithmetic too and the gate would pass vacuously.
Instead the divergence is graded by `TheYardsSetupIsNotYoursToChange`, which pins the
character's mass, every crate's weight, every rating, `FullSagCm` and `GiveWayDropCm`
against the stamped values every frame.

**Nothing is asserted at a boundary.** The occupancy truth has three values —
plainly on, plainly off, and *no opinion* in between — and while anything is in the
band the span's truth is unsettled and no gate fires. Every staged position clears
the inner footprint by at least 90 cm, so a correct submission that draws the line a
few centimetres either side of where the fixture draws it is never punished for it.
The same one-sided logic governs the 0.85 / 1.15 load bands: they narrow where the
fixture asserts, never what it demands.

**The completion gate and the early exit are ONE predicate.** A fixture that finishes
early on a weaker condition than the one its sentinel checks skips the sentinel on
exactly the submissions the sentinel exists to catch. Here `FinishTest(Succeeded)`
and `TheYardFinishedItsRounds` evaluate the same function, and its first clause is
"every stand was sampled" rather than "the drive reached its last waypoint" —
waypoint arrival is a 2D test, and a character that fell through a collision-disabled
deck reaches every waypoint on the floor below.

## Wrong answers this actually catches, honestly ranked

The strong two:

1. **Occupancy against a footprint fixed at start-up.** Passes stands 1–4, dies at
   stand 5 (`ItStaysDownWhileSomethingIsOnIt`). Genuinely what a good engineer writes.
2. **Arrivals wired, departures not.** Dies at stand 6
   (`ItHeavesBackUpOnceNothingIsOnIt`) and again at stand 14
   (`TheSagShowsTheWholeLoad`, which wants 0.00 on both spans).

Then, in descending order of how likely a frontier model is to write them — several
are foreclosed by sentences in the prompt, and are kept as regression checks rather
than counted as evidence of difficulty:

3. **A one-way state machine** that gives way and never recovers —
   `ItHeavesBackUpOnceNothingIsOnIt` (the prompt says it heaves back up).
4. **Reading the character's mass once** — `TheCharactersOwnWeightCounts` at stand 10,
   and nowhere else (the prompt says the numbers change).
5. **Forgetting the character is a load** — `TheSagShowsTheWholeLoad` at stand 2
   (sags 0.000 where 0.400 is wanted) and `ItGivesWayWhenTheTotalGoesOver` at stand 4.
6. **One shared total or one shared rating for both spans** — both gates read **both**
   spans at every settled sample, so the idle span is never unwatched: at stand 9 a
   shared total is the sum of what the two spans are carrying and collapses both.
7. **Testing each item against the rating separately** instead of summing — stand 4,
   where 0.40 and 0.80 of the rating are each under it and 1.20 is not.
8. **Sagging by the heaviest item** — stand 8, where the pair is 0.62 of the rating
   and the heavier crate alone is 0.38.
9. **Counting occupants rather than weighing them** — stand 8 again: two crates on a
   span that is rated for far more (`ItHoldsWhatItIsRatedFor`).
10. **Shoving the cargo off, or rewriting a rating or a weight** —
    `TheYardsSetupIsNotYoursToChange`.
11. **A collision toggle that is never restored** — `TheYardsSetupIsNotYoursToChange`
    (the deck must still block the pawn) and `TheYardFinishedItsRounds` (no stand can
    be sampled if nothing can stand anywhere).

## Not yet measured

Neither the reference nor the empty leg has been graded on this machine: this task was
authored file-only, with no build and no editor, alongside other agents working in the
same tree. **The orchestrator's build is the first execution of any of it.** The
constraint arithmetic behind the per-run draw was checked exhaustively offline (all 24
draws satisfy all twelve claims), and the authoring script's geometry solving and every
one of its refuse-to-save checks were exercised against a mock `unreal` module — but
that is static evidence, not a run.

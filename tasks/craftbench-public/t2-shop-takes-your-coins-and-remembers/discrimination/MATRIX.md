# Discrimination matrix — t2-shop-takes-your-coins-and-remembers

**REFERENCE + EMPTY ONLY** (owner directive 2026-08-18). No variant legs.

| Submission | Overall | Named substring(s) | Why |
| --- | --- | --- | --- |
| `../reference` | PASS | `Test Completed. Result={Success}` | The decision layer lives on a game-instance subsystem, so it outlives the stalls and the board. A stall listens to its own mat, latches so one arrival is one attempt, and asks the keeper. The keeper tests all three conditions before touching anything, then deducts, decrements, hands over, records and repaints. A fresh stall reconciles in its own `BeginPlay`: `Clamp(what it had left + what it was delivered, 0, what it can hold)`, keyed by what it sells. The price is the one thing the record does not hold. |
| `empty` | FAIL | `EachStallChargesItsOwnCurrentPrice: after stepping onto the mat of the stall selling ` | The unmodified scaffold compiles, so L1 is green. `ShowSign` and `ShowCoins` exist and work, and `BeginPlay` paints both honestly — so the yard opens on exactly the staged numbers and the baseline check passes. Nothing is bound to any mat, so step 1 changes nothing: the gate board still reads 240 where the ledger says 210. |

The empty leg's substring is a contiguous span of one source literal in
`MarketDayFunctionalTest.cpp::GradeStep` and stops before the first `%s`.

## The order failures are checked in, and why it is fixed

At a graded sample the coins are compared **first**, then the stall's stock and
"yours", then the other two stalls. That ordering is what makes the empty leg's
named substring deterministic: an empty submission is wrong about all three at
step 1, and without a fixed order the matrix cell would be a coin toss between two
gates.

Refused steps are graded by the reason the day placed them there —
`SoldOutStaysSoldOut` at steps 3 and 8, `YourHandsAreOnlySoBig` at step 10,
`ARefusedSaleCostsNothing` at steps 7 and 12. The *check* is identical in all three
(nothing moved); only the name and the message differ, so each gate is named for
the condition it is the only one isolating.

## Requirements table

See `../task.md` § *Requirement-to-assertion map* — every prompt sentence, the gate
that checks it, and the window in which that gate stands down.

## What carries the discrimination without variants

**Three staged sets, and the level agrees with none of them.** Prices, stocks,
capacities, deliveries and the purse are all staged before any `BeginPlay`, and
`-CraftBenchMarketSeed=N` picks between three complete sets. The committed `.umap`
carries different numbers again, and the authoring script refuses to save a level
whose numbers have drifted into agreeing with the fixture's. Nothing readable off
disk is a correct answer, and no constant is right in more than one set.

**The reopening is arithmetic, not an assignment.** Set 0 reopens on 3 / 2 / 3. The
remembered values were 0 / 1 / 2; delivered-only would be 3 / 1 / 2; what the fresh
stalls arrive holding is 4 / 3 / 3; the uncapped sum would be 3 / 2 / 4.
`PrepareTest` refuses to run a set unless every one of those four is wrong about at
least one stall, so the gate cannot go vacuous when the numbers are next edited.

**Three post-reopening steps are behavioural.** A restore that repaints the signs
and leaves the live state alone shows all the right numbers and then fails step 9
(a stall that had sold out must be able to sell again, because it was delivered
more), step 10 (refused *only* because the restored holdings are at the carry
limit) or step 11 (the restored purse must pay to exactly zero).

**Every refusal in the day has exactly one reason, and the fixture proves it.**
`PrepareTest` re-simulates the set and errors out if any refusal has two reasons —
which is what stops "sold out" and "cannot pay" from being gradeable by the same
accident.

**The route derives itself.** Mat positions are read off the stalls' own box
components, the lane point is a fixed distance out along the counter→mat line, and
the gate is derived from the mean of the lane points. After the stalls are rotated
one place, the same schedule walks to the right places. `PrepareTest` refuses a
route with a waypoint within 150 uu of a counter or 250 uu of a mat it is not
about, or a leg that passes that close to a counter.

## Three hazards this fixture is shaped around

1. **A day written down survives the process.** A correct submission that persists
   to a save slot would, on its *second* run in the same workdir, restore
   yesterday's closing state at step 1 and be failed for it — and the failure would
   read as a model error. The fixture empties the project's save-slot directory
   before anything begins play, and separately checks that the yard opened on the
   staged numbers, reporting a mismatch as an attributed Error naming that cause.
2. **A mirror the agent can write is not a sign.** `LastShownPrice` and friends
   live in `MarketStallActor.cpp`, which the agent edits by design. Every sample
   parses the rendered `FText` and requires the mirror to agree with it, so the
   mirrors are a cross-check and never the evidence.
3. **"Shown equals live" is not a price gate.** A submission that saved the price
   with the stock and wrote both back satisfies it perfectly. Both halves of
   `TheStallsAreTheMarketsToPrice` compare against the number the **fixture**
   staged.

## Not yet run

Neither leg has been executed. Nothing in this repository was built or run while
this task was authored — the orchestrator owns the build. Both cells above are
derived from the sources, not measured, and the substrings are quoted from the
fixture's literals rather than from a log. **Treat this file as a prediction until
`cb discriminate --task t2-shop-takes-your-coins-and-remembers --wip` has been run
once.**

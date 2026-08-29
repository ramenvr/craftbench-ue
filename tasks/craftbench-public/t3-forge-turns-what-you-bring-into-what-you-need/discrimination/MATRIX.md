# Discrimination matrix — t3-forge-turns-what-you-bring-into-what-you-need

**REFERENCE + EMPTY ONLY** (owner directive 2026-08-18). No variant legs.

Rewritten 2026-08-19 for the crafting-minigame redesign (carry cap + two-step
chain). The empty leg's named substring CHANGED — the held-face gate was renamed
from `TheForgeSpendsExactlyTheRecipeAndNothingElse` to
`TheFirstFaceSaysWhatTheForgeIsHolding`, because it now fires at t = 0.5 s of an
untouched run where nothing has been spent and the old wording read as a lie.

| Submission | Overall | Named substring(s) | Why |
| --- | --- | --- | --- |
| `../reference` | PASS | `Test Completed. Result={Success}` | The forge re-queries the heaps and the wall every tick, reads the carry cap off the sign every time it matters, takes only the room it has left and leaves the rest standing, stores the CARVING it read rather than the recipe it parsed, tests containment without mutating the holdings, picks by the carved step, spends exactly the chosen recipe once, and rebuilds both faces from the holdings AND the read set on every change. Nothing in it knows how many heaps or plaques there are, where any of them stand, or what the cap is, which is exactly why the re-post, the re-stock and the re-carve cost it nothing. |
| `empty` | FAIL | `TheFirstFaceSaysWhatTheForgeIsHolding: the first face reads` | The unmodified scaffold compiles, so L1 is green. `ShowReadout`, `EjectProduct` and `TakeUpTo` exist and work; nothing calls any of them. The level ships both faces reading `--`, so at t = 0.5 s the first face reads `--` where `EMPTY` is required, and the run is a named FAIL inside the first second — before the character has reached the first plaque. |

The empty leg's full message reads:

```
TheFirstFaceSaysWhatTheForgeIsHolding: the first face reads '--' and it has to
read 'EMPTY'. The forge spends exactly the units the recipe lists and nothing
else; everything else it is holding stays held (and the face has to read EMPTY,
or one NAME xN entry per kind separated by single spaces in alphabetical order)
```

The quoted MATRIX substring is a contiguous span of ONE source literal
(`ForgeCraftFunctionalTest.cpp`, the `TheFirstFaceSaysWhatTheForgeIsHolding`
branch of `CheckFaces`) and stops before the first `%s`, per the charter's
verbatim-substring rule.

## Requirements table

The full prompt-requirement → gate map lives in `../task.md`
(`## Requirement-to-assertion map`). What follows is what carries the
discrimination when there are no variant legs.

## What carries the discrimination without variants

**Nine locally-reasonable wrong answers, nine distinct named gates.** Each was
simulated against the fixture's own model of the staged walk before the redesign
shipped. `Dn` is the nth delivery; the fixture's own expectation is in
parentheses.

| Wrong answer | First divergence | Gate that names it |
|---|---|---|
| take the whole heap | pad 4 keeps 0 (should keep 1) at trip 2; held `EMBER x5` at D2 (`EMBER x2`) | `YouCarryOnlyWhatTheSignAllows` |
| cache the cap at BeginPlay | the re-stocked pad keeps 0 (should keep 1) after the cap drops 3 → 2 | `YouCarryOnlyWhatTheSignAllows`, cap branch |
| `TSet` containment | D1 sets down `SLAG` from two units (should set down nothing) | `APartialStackIsSpentOnNothing` |
| mutate-then-check | D1 held `EMPTY` (`EMBER x2`) — the holdings were spent testing a recipe that did not fit | `TheFirstFaceSaysWhatTheForgeIsHolding` |
| iterate the whole wall | D5 sets down `BLADE` (should set down nothing — the top step has never been read) | `TheForgeOnlyKnowsTheRecipesYouHaveRead` |
| first recipe that fits | D6 sets down `SLAG` (`BLADE`) — both steps fit and the higher one has to win | `TheForgeMakesTheHighestTierItCan` |
| `while (TryCraft())` | D6 sets down `BLADE` **and** `SLAG`; held `EMPTY` (`EMBER x3`) | `OneThingPerDelivery` |
| store the parsed recipe | D7 sets down `SLAG` from the old material after the first step is re-carved | `TheForgeOnlyKnowsTheRecipesYouHaveRead`, staleness branch |
| cache a pad's material | D7 held `EMBER x5` (`CINDER x2 EMBER x3`) | `TheHallReadsAsItStandsNow` |

**The cap writes its own evidence on the floor.** Every consequence of the carry
cap is a residual standing on a heap, with its own label saying how many are left
— not a number inside an inventory nobody can see. Three heaps end the run
holding a residual (1, 1 and 2 units), and two more at the far end of the aisle
are never approached at all and must be untouched. A take-all submission cannot
produce any of those five numbers.

**Three of a kind makes the first trap fire at the FIRST delivery.** Because every
recipe in this hall is three of the same unit, a set-shaped containment test is
satisfied by one unit and crafts immediately — at D1, holding two. The previous
design had to wait for a four-unit recipe at the third delivery to catch the same
bug.

**Unit count cannot break the tie, so the carved step has to.** Both recipes take
exactly three units. "The biggest recipe" is not an answer here and neither is
"the nearest plaque" — the rule is the step carved on the face a human reads, and
the delivery where both fit is the climax of the walk rather than an arbitrary
tie-break.

**Two face changes with no delivery at all.** The second face has to go from
`NOTHING` to `BLADE` purely because the character walked up to the second plaque,
and back to `NOTHING` purely because the hall re-carved the first one. A forecast
computed only inside the craft path misses both, and each is a separate frame in
the trace.

**The chain is a set that grows.** The forge's own three middle-material outputs
are spawned mid-run onto shelf-stones; the walk goes and fetches all three — cap
exactly 3, so the load is full and the errand cannot be split — and brings them
back as the ingredients for the top step. A heap query hoisted out of the tick
never sees them, and the failure is attributed to `TheForgeCanUseWhatItMade`
rather than to the matcher.

**The empty submission fails before the character has moved 400 uu.** The level
ships both faces reading `--`, so `TheFirstFaceSaysWhatTheForgeIsHolding` fires at
t = 0.5 s while the character is still walking to the first plaque. Nothing about
the rest of the walk is needed to separate empty from reference.

## Three staging hazards this design had to be built around

1. **"The heap is gone" cannot be graded on one flag.**
   `USceneComponent::IsVisible()` consults only the component's own
   `bHiddenInGame` and visible flag; it never looks at the owning actor's
   `bHidden`. A submission that used `AActor::SetActorHiddenInGame(true)` — or
   `Destroy()` — would have satisfied every sentence of the prompt and still been
   read as "the heap keeps standing". `HeapIsGone()` is therefore a disjunction
   over all four mechanisms, `LiveUnits()` reads every one of them as zero, and
   the re-stock SPAWNS a replacement when the previous heap was destroyed.
2. **A residual gate that compares while the character is standing on the heap
   fails correct work.** A submission may measure "close enough" in 3D or off a
   bounds sphere and so fire a frame or two either side of the fixture's flat
   test. The comparison is therefore suspended from the first frame within
   `ReachUu + 60 uu` until 0.5 s after the last one — leniency strictly in the
   direction that can only let a submission take LATE, never let one take a heap
   it never approached.
3. **A precondition that depends on the submission takes a graded run out of the
   denominator.** The previous design staged its chain delivery as a hard
   precondition on the forge's own output having been carried back — and it fired
   on the reference. The two delivery roles that need a product to exist are now
   logged, not attributed; only the three that depend on nothing but the hall stay
   hard.

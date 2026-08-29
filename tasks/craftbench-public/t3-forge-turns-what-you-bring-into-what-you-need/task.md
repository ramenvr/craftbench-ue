---
id: t3-forge-turns-what-you-bring-into-what-you-need
substrate: ThirdPerson
set: craftbench-public
tier: T3
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_ForgeHall :: AForgeCraftFunctionalTest"]
---

# t3-forge-turns-what-you-bring-into-what-you-need

A crafting minigame in a walkable hall. A sign posts how much you can carry at
once; two plaques carve a two-step chain — three of the base material merge into
one of the middle material, three of the middle material merge into the one thing
at the top. Nine base units therefore have to reach the forge, and at a cap of
three they cannot arrive in fewer than four loads. The three middle units the
forge sets down on its own shelf-stones have to be walked out and carried back in
before the top of the chain can be made at all. The cap forces the trips; the
chain forces the errand. Part way through the run the cap is re-posted smaller,
one heap is re-stocked with a material that was not in the hall before, and the
first step of the chain is re-carved to need it.

> **Redesigned 2026-08-19 from owner play-test feedback.** The previous shape —
> four unrelated recipes, eight interchangeable heaps, take-the-whole-heap, and
> "biggest recipe wins, ties by nearest plaque" — was a lookup problem wearing a
> hall: no chain, no reason to make one thing before another, no reason to come
> back. What replaces it is a *plan*: you cannot make the top until you have made
> three of the middle, you cannot make three of the middle in one trip, and you
> cannot deliver three of the middle without going and fetching them. The carry
> cap is a second genuinely-coupled subsystem rather than a rule bolted on: its
> consequence is written on the heaps themselves, per heap, every trip — walk up
> to a heap of four with room for three and it keeps one, standing, with its label
> saying so.

## Primary concept

- `stateful-interaction-station` — an actor accumulating state from the world by
  proximity and resolving it against data it reads from other actors at the
  moment it needs them
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/actor-ticking-in-unreal-engine)

The load-bearing behaviour is **a decision recomputed from the world as it stands
at the instant it is taken**, over data that changes three ways: because the hall
re-stages itself, because the character has walked somewhere new, and because the
forge's own output became an ingredient. The grade never asks *how*: a tick, a
timer poll, or an overlap volume sized from the property all pass identically.

## Composed concepts

- `resource-carry-cap` — a per-pickup budget read live off a placed actor, whose
  consequence is a per-heap residual anybody can see standing in the hall
- `proximity-query-live-set` — a per-frame scan over a set that GROWS mid-run,
  because the forge's own output is spawned into it
- `world-data-read-at-use` — recipes, stock and the cap read off the actors that
  carry them, at the moment they are needed, never gathered into a table
- `text-render-readback` — two `UTextRenderComponent` faces as the graded
  observable, exactly as `t2-collect-then-exit` grades its board
- `multiset-containment` — "holds at least every unit, counts included", which a
  set-shaped test silently passes and a mutate-then-check test silently corrupts

## Prompt given to the agent

> The hall has a forge in the middle, heaps of raw stuff standing in two rows down
> the aisle, two carved plaques hanging further out on either side, the forge's own
> shelf-stones behind it, and a sign beside where you start. Everything happens by
> walking — no key presses anywhere.
>
> **The sign.** The sign says how many units you can be carrying at once. You can
> never be carrying more than that. **The sign is not fixed** — read it at the
> moment you pick something up; a number you remember from when play began will be
> wrong later.
>
> **Heaps.** Each heap says what it is and how many units are in it, and carries
> its own number for how close you have to be before you can take from it. Come
> that close and you pick up **as much of it as you can still carry** — all of it
> when the sign allows, part of it when it does not, and none of it when you are
> already carrying all you can. Whatever you did not take **stays standing**, and
> the heap says how many are left. **Within half a second of you coming that close
> the heap holds exactly what you left standing.** A heap you never came that close
> to must still be standing, untouched, with every unit it started with. What you
> have picked up you carry until you reach the forge, and it comes off your hands
> there.
>
> **Plaques.** Each plaque is carved with one recipe and says which step up it is:
> the units it needs and the single thing they make, written like
> `TIER 1 : ORE ORE ORE -> INGOT`. A recipe can be made when the forge is holding
> at least every unit the recipe lists, counts included — holding more of something
> is fine, holding fewer is not.
>
> **You have to go and read them.** A plaque carries its own number for how close
> you have to stand before you can read it. **The forge can only use a recipe you
> have read.** What you have read stays with you — but only that carving: if a
> plaque is re-carved, what it says is unknown to you again until you go back and
> read it. Standing anywhere else in the hall tells you nothing about it.
>
> **Delivering.** When you get close enough to the forge — the forge carries its
> own number for that — it takes everything you are carrying, all of it at once,
> and adds it to what it was already holding. Each time it takes something it makes
> **at most one thing**. Arriving empty-handed changes nothing.
>
> **Which recipe.** Of the recipes **you have read** that can be made from what the
> forge is now holding, it makes the one carved with the **highest step**.
>
> **What it spends.** It spends exactly the units that recipe lists and nothing
> else; everything else it is holding stays held. If **none** of the recipes you
> have read can be made from what it is holding, it spends nothing and makes
> nothing — what it is holding must come out of that delivery untouched. Two units
> sitting in the forge stay two units.
>
> **One thing at a time.** Having made its one thing, it stops — even when what is
> left over could make something else. It will not make that until something new is
> delivered.
>
> **What it makes.** The thing it makes is set down on the forge's next free
> shelf-stone, and from that moment it is a heap like any other: you can walk up to
> it, carry it back under the same carry cap as anything else, and it can be an
> ingredient in the next step up.
>
> **The two faces.** The forge has two faces and you must keep both true. The first
> shows what the forge is holding: the word `EMPTY` when it holds nothing, otherwise
> one entry per kind written `NAME xN`, entries separated by a single space and
> listed in alphabetical order — `EMBER x2 SLAG x3`. The second shows what it could
> make from what it is holding **right now**, decided by exactly the rule above: the
> name of that one thing, or the word `NOTHING`. Spell names the way the heaps and
> the plaques spell them. **Within half a second of play beginning, and within half
> a second of anything changing either what the forge is holding or what you have
> read, both faces must read the truth** — walking up to a plaque changes what the
> forge could make next without anything being delivered at all, and the second face
> has to keep up. The level ships them both reading `--`, which is neither.
>
> **Nothing in this hall is fixed.** Part way through the run the sign is re-posted
> with a different number, a heap is re-stocked with different stuff, and a plaque
> is re-carved with a different recipe. Read the sign, read the wall and read the
> heaps at the moment you need them; a list you gather once when play begins will be
> wrong for the rest of the run.
>
> **Nothing in this hall is yours to change.** Where the forge, the sign, the heaps,
> the plaques and the shelf-stones stand is fixed. **Do not move any of them at
> all**, do not add any more of them, and never take from a heap you did not walk up
> to. What the plaques say, what the sign says and what the heaps say are the hall's
> to write and not yours to change.
>
> Everything the answer depends on is written in the hall — the reaches, the counts,
> the recipes, the steps, the carry cap. None of it is written here. Write your
> solution in C++ under `Source/ThirdPerson/`. Do not edit the level, any config
> file, or any test file. Keep the forge's two faces and its shelf-stones, and keep
> the settings named in the workspace notes under the names and types they have: the
> hall re-stages itself through them. You may add to them, but not instead of them.

## Workspace state pre-task

**Deliverable root: `Source/ThirdPerson/`** (the agent-writable runtime module on
this substrate). `Source/CraftBenchTests/` is deny-listed and a submission file
under it is a SANDBOX-REJECT (exit 4), not a graded FAIL; so are `Content/Maps/`,
`Content/ThirdPerson/`, `Content/Characters/` and every `Config/` file (no
`config_allow` is declared by this task).

**THE SETTINGS THE HALL RE-STAGES THROUGH.** Part way through the run the hall
rewrites the sign, a plaque and a pad *from outside*, by name, while the level is
playing. These must survive as reflected properties with these names and these
types, on the actors that carry them:

| Property | Type | On |
|---|---|---|
| `CarvedText` | `FString` | the plaque |
| `ReadReachUu` | `float` | the plaque |
| `IngredientId` | `FName` | the heap |
| `UnitsInHeap` | `int32` | the heap |
| `ReachUu` | `float` | the heap |
| `CarryCapUnits` | `int32` | the sign |
| `TakeReachUu` | `float` | the forge |

Rename one, fold two into a struct, or change a type and the hall cannot re-stage
itself. You may add whatever you like alongside them.

Files that **exist** under `Source/ThirdPerson/`:

- The stock UE 5.8 Third Person C++ template sources. No edit needed.
- `Tasks/t3-forge-turns-what-you-bring-into-what-you-need/ForgeStationActor.h` /
  `.cpp` — `AForgeStationActor`, tagged `ForgeStation`. Supplied and working:
  - `Anvil` — a 200 x 200 x 160 solid block, the visible forge. Small on purpose:
    a walker inside the forge's reach never has to touch it.
  - `HeldFace`, `CanMakeFace` — two `UTextRenderComponent`s. **The level ships
    both reading `--`.**
  - `ShelfStones` — ten flat stones behind the forge, named `Shelf00`..`Shelf09`.
  - `UPROPERTY(EditAnywhere) float TakeReachUu`.
  - `UFUNCTION(BlueprintCallable) void ShowReadout(const FString&, const FString&)`
    — THE FIRST SWITCH: writes both faces, verbatim.
  - `UFUNCTION(BlueprintCallable) AIngredientHeapActor* EjectProduct(FName)` — THE
    SECOND SWITCH: sets one unit down on the next free stone as a heap like any
    other. A stone counts free when no heap with units still in it stands on it.
    With every stone taken it stacks on the last one and logs a line; it never
    silently drops a product.
  - **No tick, no BeginPlay, no reference to the character, no proximity code,
    nothing that decides when to throw either switch.**
- `.../IngredientHeapActor.h` / `.cpp` — `AIngredientHeapActor`, tagged
  `IngredientHeap`. A `Heap` pile with **collision disabled** (you can stand in
  it, so no route can ever jam), a `Label` reading `NAME xN`, the three settings
  above, `UFUNCTION(BlueprintCallable) int32 TakeUpTo(int32 MaxUnits)` (hands over
  at most `MaxUnits` of what is standing, clamped both ways, leaves the rest
  standing, returns what it actually handed over),
  `UFUNCTION(BlueprintPure) bool IsEmptied() const`, and a supplied
  `RefreshLabel()`. No tick, no overlap handler, no decision. **There is no
  take-the-whole-heap switch** — the only way to take from a heap is to say how
  much.
- `.../RecipePlaqueActor.h` / `.cpp` — `ARecipePlaqueActor`, tagged
  `RecipePlaque`. A non-colliding `Slab`, a `Carving` text component showing the
  same line a human reads on the wall, `CarvedText`, `ReadReachUu`, and three
  supplied parsers — `UFUNCTION(BlueprintPure) TArray<FName> GetInputs() const`,
  `FName GetOutput() const` and `int32 GetTier() const`. **All three re-parse
  `CarvedText` on every call and cache nothing**, so asking at the moment you need
  the answer costs nothing and is always current. No matching logic of any kind.
- `.../CarrySignActor.h` / `.cpp` — `ACarrySignActor`, tagged `CarrySign`. A
  non-colliding `Post`, a `Notice` text component reading `CARRY AT MOST N`,
  `UPROPERTY(EditAnywhere) int32 CarryCapUnits`, and a supplied `RefreshNotice()`.
  No tick, nothing that counts anything, no decision.
- `Content/Maps/t3-forge-turns-what-you-bring-into-what-you-need/L_ForgeHall.umap`
  — the staged hall, committed binary. World Settings name NO game mode, so the
  level inherits `BP_ThirdPersonGameMode`. What is in it:

  | Element | Placement | Notes |
  |---|---|---|
  | Floor | 8,800 x 4,400, striped every 400 cm, stripes **non-colliding** | |
  | Forge | at the origin, movable | its reach painted as a ring |
  | 8 heaps | two rows down the aisle, on pads, **movable** | each reach painted as a ring; each label says what it is and how many |
  | 2 plaques | one per step of the chain, hung either side | each with its reading circle painted |
  | 1 carry sign | beside the PlayerStart, facing the aisle | posts the cap in letters a player reads |
  | PlayerStart | on the aisle in front of the forge | |
  | Backdrop + two differently sized posts | | a moving camera is distinguishable from a still one |
  | Fixture | one placed `AForgeCraftFunctionalTest` | |

  **The reaches, the counts, the recipes, the steps and the cap are deliberately
  NOT in this section.** They are readable in the hall, on the things themselves —
  and three of them change part way through the run anyway.

- `cameras.json` (the camera-plan lane; not part of this release) — the presentation-only camera plan. Non-gating.

Files that **do not exist**:

- No proximity logic, no carry logic, no matching logic, no readout logic of any
  kind. The empty submission compiles (L1 green) and FAILs L2 within the first
  second, on the two faces still reading `--`.
- No test source in the agent's writable path. `AForgeCraftFunctionalTest` lives
  in the `CraftBenchTests` module the agent can neither read nor modify.

**Where the answer has to land.** All four actors are placed instances in a map
the submission cannot edit, so a new subclass would never be instantiated — and
the heaps, the plaques and the sign answer questions and decide nothing. That
leaves exactly one thing in the hall that can be made to tick.

## Verifier specification

The test runs in PIE from
`Content/Maps/t3-forge-turns-what-you-bring-into-what-you-need/L_ForgeHall.umap`
on the **ThirdPerson** substrate, ticked at a fixed deterministic step
(`-deterministic -FPS=60`). Verification primitive: **pie-checkpoint-sampling**
with an every-frame readback of the two faces, every heap's live unit count, and
everything standing on the shelf-stones, over a fixture-driven walk that is
**derived from the hall's live reaches, never written down**.

**The fixture implements the prompt's rule itself** — multiset containment with
multiplicities, argmax by carved step, over the set of plaques the character has
stood at, under its own model of the carry cap — and compares the submission's
observable output against its own answer. There is no table of expected strings,
so the hall can be re-authored and the fixture follows.

**The walk is the game.** Seven deliveries: a part-load that makes nothing, three
first-step merges, an errand behind the forge that carries the forge's own three
outputs back in, the delivery where both steps fit at once and the higher one has
to win, and one more after the hall re-stages itself. At two points the second
face has to change with **no delivery at all** — once because the character walks
up to the second plaque and reads it, and once because the hall re-carves the
first plaque out from under what was read.

**The hall re-stages ONCE, with the character standing at the forge.** The cap is
re-posted smaller, one pad is re-stocked with a material that was not in the hall
before, and the first step of the chain is re-carved to need that material. That
single re-stage invalidates four different things a submission might have cached —
the cap, a pad's material, a parsed recipe, and a face written only inside the
craft path — and costs one short trip instead of a whole second walk. The
re-stage is done by reflection (`FStrProperty` / `FNameProperty` / `FIntProperty`)
on the agent's own properties and it **un-hides** the pile and the label on the
re-stocked pad, so a pad emptied earlier is genuinely standing again and no
residual gate is pre-satisfied. A pad whose heap the submission **destroyed** is
re-stocked by spawning a fresh one of the same class.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64
        Development" and "ThirdPerson Win64 Development"
```

### L2 — AFunctionalTest behavioral trace

```text
assert: YouCarryOnlyWhatTheSignAllows -- every frame, for every heap and every
        product, the live UnitsInHeap equals the fixture's own model of what
        should be left standing: the staged count minus exactly what the sign's
        CURRENT cap left room to carry. Fires on a heap that keeps too few (took
        more than the cap allows), on one that keeps too many (took less than
        there was room for), and on the re-stocked pad after the cap is
        re-posted smaller, which is where a cap cached at BeginPlay shows up.
        The comparison is suspended while the character is within
        ReachUu + 60 uu and for 0.5 s afterwards, so a submission measuring the
        distance in 3D or off a bounds sphere is never failed for firing a frame
        early

assert: NothingVanishesExceptWhatYouCanCarry -- no heap loses units while the
        character has never been within that heap's own live ReachUu of it, and
        at the sentinel every heap holds exactly its modelled residual. "Gone" is
        a DISJUNCTION -- actor destroyed, actor hidden, the Heap component hidden
        or invisible, or UnitsInHeap at zero -- because the prompt describes an
        outcome and never names a mechanism

assert: NothingInTheHallMoved -- the forge, the sign, every plaque, every heap
        and every shelf-stone is still within 2 uu of where the hall staged it;
        there are no more of any of them than the hall built (re-counted EVERY
        FRAME, so a plaque added mid-run cannot carve a recipe the fixture would
        then grade against); and what the plaques and the sign SAY is still what
        the hall wrote

assert: APartialStackIsSpentOnNothing -- at the delivery where the forge holds
        two of the base material and the first step needs three, nothing is set
        down and the first face still reads two. A set-shaped containment test
        crafts here; a mutate-then-check test has already spent the holdings
        testing a recipe that did not fit

assert: ThreeOfAKindMakesTheNextTier -- at each delivery, exactly the output of
        the highest-step READ recipe whose units the holdings cover appears on a
        shelf-stone within 0.5 s. Three of the base material become one of the
        middle material at three separate deliveries, each with two units to
        spare so the spend is exact and visible; three of the middle material
        become the one thing at the top

assert: TheForgeMakesTheHighestTierItCan -- at the delivery where BOTH steps of
        the chain fit what the forge is holding, the thing set down is the one
        carved with the higher step. First-recipe-that-fits and array order are
        each wrong here, and unit count cannot break it: every recipe in this
        hall takes exactly three units

assert: TheForgeOnlyKnowsTheRecipesYouHaveRead -- the thing set down is never the
        output of a plaque the character has not stood within ReadReachUu of
        since that plaque was last carved. Fires twice over the run: at the
        errand delivery, where everything the top step needs is in the forge and
        the whole wall would give it but the recipe has never been read; and at
        the last delivery, where the first step has been re-carved and a stored
        parsed recipe would still make its old output

assert: TheForgeSpendsExactlyTheUnitsTheRecipeLists / the first face --
        TheFirstFaceSaysWhatTheForgeIsHolding compares the squeezed HeldFace
        against the fixture's own formatted holdings, so content, order and
        format are one comparison. Asserted from t = 0.5 s of play against EMPTY
        and from 0.5 s after every change to the holdings

assert: TheSecondFaceSaysWhatItCouldMakeNext -- CanMakeFace is the output the
        same rule picks over the CURRENT holdings and the CURRENT read set, or
        NOTHING, recomputed EVERY FRAME. It has to change twice with no delivery
        at all: up to the top of the chain when the character reads the second
        plaque, and back to NOTHING when the hall re-carves the first one

assert: OneThingPerDelivery -- at most one new product per delivery, counted
        continuously to the sentinel. The top-of-chain delivery leaves exactly
        three of the base material behind, which the first step could still
        merge: the second face must NAME it and no shelf-stone may HOLD it

assert: TheForgeCanUseWhatItMade -- the walk goes to each of the three
        shelf-stones holding the forge's own middle-material outputs, and each is
        gone within 0.5 s of the character arriving. A heap query hoisted out of
        the tick never sees them, because they were spawned mid-run

assert: TheHallReadsAsItStandsNow -- after the re-stage, if the first face does
        not account for the material the re-stocked pad ACTUALLY holds, the
        failure quotes what that pad used to hold beside what it holds now

assert: TheChainReachedTheTop -- at the sentinel: the hall re-staged, all seven
        deliveries happened, something the top step of the chain makes is
        standing where the forge set it down, and every heap holds exactly its
        modelled residual
```

The checkpoint schedule is 10 s .. 230 s every 10 s (calibration logging only)
and then a **SENTINEL at t = 240 s**, because
`ACraftBenchFunctionalTest::Tick` ends the test the moment the last scheduled
checkpoint is sampled. The real gates are evaluated EVERY FRAME in `Tick`; only
the deferred ones are read at the sentinel.

**The 240 s sentinel is a wall-clock decision, not just a world-clock one.**
`tools/verify-single/layers/l2_pie.py` hard-codes `timeout_seconds = 600.0`
around editor boot + map load + PIE + shutdown, there is no per-task override,
and `run_task.harness_error_reasons()` deliberately keeps exit 124 GRADED — so a
schedule that overruns the wall clock scores the REFERENCE as a task FAIL. The
drive measures **125.4 s of world time** on paper (48,718 uu of walking at the
substrate's 500 uu/s plus 28.0 s of dwell); 240 s leaves ~48% of world-time
headroom, and against the worst wall-to-world rate in the recorded corpus
(`t2-race-clock`, 2.07 wall-seconds per world-second at its max of
n=4) that is ~260 s of wall clock inside a 600 s cap. The redesign is *cheaper*
than the shape it replaces (170.7 s), because the second full leg was traded for
a single short epilogue.

**Staging faults are attributed, not scored — but only where they can only be the
hall's fault.** A hall missing its forge, its sign, its pads or its plaques; a
heap, plaque or sign that does not expose its settings readably; a face that is
not there; a wall that does not carve two different steps of a chain; a walk that
would graze something it never went to or that would stand inside the forge's
reach while carrying; and the three delivery shapes that depend only on the hall
(the part-load, the first-step merges, the epilogue) all end the run as
`HARNESS-PRECONDITION`. **The two delivery shapes that depend on the forge's own
output existing — the errand delivery and the top-of-chain delivery — are checked
SOFTLY and logged, never attributed.** A submission that never made the first step
of the chain has already failed an earlier gate, and turning that into a
precondition would take a graded run out of the denominator. The previous design
of this task shipped a precondition of exactly that shape and it fired on the
reference. **Counts that are too HIGH are graded**, not excused.

## Requirement-to-assertion map

| Prompt requirement | Gate that checks it | When that gate does NOT run |
|---|---|---|
| you can never be carrying more than the sign says | `YouCarryOnlyWhatTheSignAllows` — the per-heap residual, every frame | while the character is within `ReachUu + 60 uu` and for 0.5 s after |
| you pick up as much as you can still carry; the rest stays standing | the same gate, both directions (too few left AND too many left) | as above |
| come up to a heap while full and it is untouched | the same gate, at the heap the walk reaches with a full load | as above |
| the heap holds what you left standing **within half a second** | the same gate's window | never |
| **read the sign at the moment you pick something up** | the same gate, on the pad re-stocked after the cap is re-posted smaller | before the re-stage |
| never take from a heap you did not walk up to | `NothingVanishesExceptWhatYouCanCarry`, every frame | never |
| a heap never approached is still standing with its count | the same gate, at the sentinel | never |
| a recipe needs **at least every unit, counts included** | `ThreeOfAKindMakesTheNextTier` — the fixture's own containment test uses multiplicities | never |
| **the forge can only use a recipe you have read** | `TheForgeOnlyKnowsTheRecipesYouHaveRead` | on deliveries where the read set and the whole wall agree — two deliveries are staged so they cannot |
| a re-carved plaque is unknown until you read it again | the same gate, at the last delivery | never |
| the forge takes everything you carry, within its own reach | every delivery gate keys off the fixture's own first-frame-in-reach | never |
| **the highest step** wins | `TheForgeMakesTheHighestTierItCan` | on deliveries where only one recipe fits — one is staged where both do |
| spends exactly the recipe's units, leftovers stay held | `TheFirstFaceSaysWhatTheForgeIsHolding` | during the half-second settle, and while a handover is in flight |
| nothing fits ⇒ spends nothing, makes nothing | `APartialStackIsSpentOnNothing`, plus the first face | never |
| **at most one thing** per delivery | `OneThingPerDelivery` | never |
| the product is a heap you can carry back in, under the same cap | `TheForgeCanUseWhatItMade`, and the product residual in `YouCarryOnlyWhatTheSignAllows` | never |
| first face: `EMPTY` / `NAME xN`, single spaces, alphabetical | `TheFirstFaceSaysWhatTheForgeIsHolding` compares the squeezed face against the formatted expectation | during the settle |
| second face: what it could make **right now**, or `NOTHING` | `TheSecondFaceSaysWhatItCouldMakeNext`, recomputed every frame | during the settle |
| both true **within half a second of play beginning** | the same two gates, from t = 0.5 s against an empty forge | never |
| both true within half a second of **what you have read** changing | `TheSecondFaceSaysWhatItCouldMakeNext` at the second plaque and at the re-carve | never |
| the hall re-stages itself mid-run | `TheChainReachedTheTop`, plus every epilogue gate | never |
| a list gathered when play begins is wrong later | `TheHallReadsAsItStandsNow` (the pad's material), the cap branch of `YouCarryOnlyWhatTheSignAllows`, and the staleness branch of `TheForgeOnlyKnowsTheRecipesYouHaveRead` | before the re-stage |
| **do not move any of them at all** | `NothingInTheHallMoved`, every frame, to 2 uu | never |
| do not add any more of them | the same gate's per-frame counts, plus `ResolveHall` | never |
| what the plaques and the sign say is not yours to change | the same gate compares the live `CarvedText` and `CarryCapUnits` against what the hall wrote | never |
| the goal: reach the top of the chain | `TheChainReachedTheTop` | never |
| C++ under `Source/ThirdPerson/` | sandbox: a file outside the writable set is exit 4, not a graded FAIL | never |

## Reference solution metadata

- **Files touched:** 1 pair —
  `Source/ThirdPerson/Tasks/t3-forge-turns-what-you-bring-into-what-you-need/ForgeStationActor.{h,cpp}`.
  The heap, the plaque and the sign are untouched.
- **LOC added:** ~280 (about 70 of declaration, about 210 of implementation).
- **Honest senior-dev hours: 8–12.** Where they go: ~2 h on the carry and its cap
  (a live re-query per tick, a live cap read off the sign, room recomputed per
  heap in the same frame so walking into two heaps fills on the first and leaves
  the second standing); ~1 h on the delivery seam and the half-second discipline;
  ~1.5 h on the matcher (containment with multiplicities and **without
  mutation**, argmax by carved step); ~1 h on the spend/produce split; ~1.5 h on
  the two faces, which have to be rebuilt on every state change and not only on a
  craft — including the change that is *only* a walk; and ~2–4 h on the
  interaction that actually costs the day — **the read set**. The natural shape
  (iterate every plaque) is wrong at the errand delivery, the natural fix
  (remember what you read) is wrong at the last delivery unless the remembered
  thing is the CARVING rather than the parsed recipe, and the two failures look
  nothing alike in the log.
- **What it is NOT:** no engine trivia, no withheld constant, no undocumented
  tolerance. Every number the grade uses — each heap's reach and count, each
  plaque's carving and step and read-reach, the forge's reach, the carry cap — is
  written on the thing itself in the hall, and every deadline is written in the
  prompt.

## Anti-gaming notes

1. **Take the whole heap.** *Failure mode*: the shape everyone writes first — walk
   into a heap, take all of it. The scaffold no longer offers a take-all switch,
   but nothing stops a submission from calling `TakeUpTo(UnitsInHeap)`.
   *Defense*: `YouCarryOnlyWhatTheSignAllows`. The walk reaches a heap of four
   with room for three, which must keep one; then a heap of two while already
   full, which must keep both. Three separate heaps end the run holding a residual
   a take-all submission cannot leave.
2. **Cache the cap at BeginPlay.** *Failure mode*: read `CarryCapUnits` once and
   remember it — correct for the whole first phase. *Defense*: the cap is
   re-posted smaller and one pad is re-stocked with strictly more than the new
   cap, so the very next pickup takes one unit too many and the pad is left
   standing empty where it should be left standing with one.
3. **A set instead of a multiset.** *Failure mode*: `TSet<FName>` containment, so
   three-of-a-kind is satisfied by one. *Defense*: `APartialStackIsSpentOnNothing`
   at the first delivery, where the forge holds two of the base material and the
   only read recipe needs three. A set-shaped test crafts on two — and every
   recipe in this hall is three of a kind, so this trap fires at the FIRST
   delivery instead of waiting for a wide recipe.
4. **Mutate-then-check containment.** *Failure mode*: the classic
   `for (Input : Recipe.Inputs) if (Held.Contains(Input)) { Held.Remove(Input); }`
   — by the time a recipe turns out not to fit, the holdings have already been
   spent testing it. *Defense*: `TheFirstFaceSaysWhatTheForgeIsHolding` at the same
   first delivery, where the face must still read two units of the base material.
5. **Reading the whole wall from anywhere.** *Failure mode*: iterate every
   `RecipePlaque` — the shape everyone writes, and the one the prompt forbids in a
   single positive sentence rather than a prohibition. *Defense*:
   `TheForgeOnlyKnowsTheRecipesYouHaveRead` at the errand delivery, where the forge
   is holding all three middle units and the top step has never been read. The walk
   deliberately reads the top step only AFTERWARDS, and the second face has to flip
   the instant it does.
6. **Remembering the recipe instead of the carving.** *Failure mode*: mark a plaque
   known and store its parsed inputs. *Defense*: the first step is re-carved to
   need a material that did not exist before, and the forge is left holding exactly
   three of the OLD material. A stored parsed recipe merges them; the live carving
   does not fit anything. The gate names the re-carved plaque and quotes what it
   says now.
7. **First recipe that fits.** *Failure mode*: return the first match, or the one
   at index 0, or the biggest by unit count. *Defense*:
   `TheForgeMakesTheHighestTierItCan` at the top-of-chain delivery, where both
   steps fit at once. Unit count cannot break it — both recipes take three units —
   so the carved step is the only thing that answers, and it is written on the face
   a human reads.
8. **Making everything it can.** *Failure mode*: `while (TryCraft()) {}` — the
   tidier-looking loop, though the prompt forbids it by name. *Defense*:
   `OneThingPerDelivery` at the top-of-chain delivery, whose leftovers are exactly
   three of the base material and therefore still a valid first-step merge. Counted
   continuously, so a late second product is caught too.
9. **Caching a pad's material.** *Failure mode*: gather `IngredientId` per heap at
   BeginPlay. *Defense*: `TheHallReadsAsItStandsNow` — one pad is re-stocked with a
   material that was not in the hall before, and the first face is compared against
   what the forge was actually handed, quoting the old name beside the new one.
10. **Moving something, or adding to the hall.** *Defense*:
    `NothingInTheHallMoved` compares every staged transform to 2 uu every frame,
    re-counts the forge, the sign and the plaques every frame, and compares the
    live `CarvedText` and `CarryCapUnits` against what the hall wrote — so a
    submission cannot carve itself an easier recipe or post itself a bigger cap.

## Hidden invariants

- **The route is derived, never written down.** Every stop is expressed as a
  factor of the reach of the thing it is about (`0.5x` in), and `PrepareTest`
  refuses to start if any sample of any segment comes within `1.6x` the reach of
  anything the walk did not go to, or within 180 uu of the solid anvil.
  `authoring/author_map.py` runs the identical arithmetic before it will save the
  level, so a layout mistake fails a 3-second authoring run instead of a 6-minute
  graded one.
- **No stop that is not a delivery may lie inside the forge's reach**, and the lane
  that gets behind the forge is swept for the same thing along its whole run. This
  is the check whose absence broke the previous design: a transit stop pushed AT
  the forge stop, dwell 0, while the character was carrying, staged a delivery the
  walk never reached. The lane's offset is SOLVED from the forge's own take reach
  and the shelf-stones' own row offset — outside `450 x 1.3` and inside
  `1250 - 220 x 1.6`, i.e. a 313 uu band whose midpoint the fixture takes — rather
  than chosen; at the old 1000 uu stone row that band was 63 uu wide and a single
  retune of either reach would have closed it.
- **The delivery window is keyed off the measured first frame in reach**, not off
  the dwell. A correct submission delivers as it crosses `TakeReachUu`, roughly
  0.3 s before the character finishes walking in.
- **The face comparison is suspended while a handover is in flight** — within
  `TakeReachUu x 1.4` of the forge with something still carried. A submission is
  free to cross into the reach a frame or two before the fixture's flat test does,
  and for those frames its faces are legitimately ahead of the fixture's model.
- **The residual comparison is suspended while the character is near a heap**, from
  the first frame within `ReachUu + 60 uu` until 0.5 s after the last one. The
  leniency is deliberately in the safe direction: it can only ever let a submission
  take LATE, never let one take a heap it never approached.
- **The errand's destinations are resolved at run time and derived from the wall** —
  the fixture walks to whichever shelf-stones hold products whose name some live
  recipe lists as an ingredient, nearest first, and only on one side of the lane. It
  is not a hard-coded stone, so the gate survives a submission whose shelf order
  differs, and every unfilled leg collapses onto the lane rather than cutting a
  diagonal nobody swept. A target that is not within 200 uu of a shelf-stone is
  refused outright, because `SweepRoute` pre-sweeps the errand to the STONES and a
  target anywhere else would be a walk nobody checked.
- **A product's position and reach are frozen at the frame it appears.** Destroying
  a heap is one of the four legal ways to empty it, so a submission whose pickup
  fires a frame before the fixture's flat test would leave an actor-derived distance
  with nothing to measure against — and the fixture would then fail correct work for
  taking from a heap it never walked up to. Freezing also means a submission cannot
  dodge the errand by moving its own output out of the walk's way: the character
  still stands where the forge set it down, and the heap standing somewhere else
  fails `TheForgeCanUseWhatItMade` by name.
- **There are ten shelf-stones and a correct run sets down four**, never holding
  more than three at once. The margin exists for the over-crafting submission
  `OneThingPerDelivery` targets: `EjectProduct` stacks on the last stone rather than
  dropping a product, so the signal the gate reads cannot vanish exactly when the
  failure gets worse.
- **`PrepareTest` cannot check a delivery's staged shape** — the holdings do not
  exist yet — so each delivery asserts its own role AT the delivery. Only the three
  roles that depend on nothing but the hall are hard preconditions; the two that
  need the forge's own output to exist log a warning and grade normally.

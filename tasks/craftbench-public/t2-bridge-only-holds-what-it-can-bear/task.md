---
id: t2-bridge-only-holds-what-it-can-bear
substrate: ThirdPerson
set: craftbench-public
tier: T2
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_TrestleYard :: ATrestleLoadFunctionalTest"]
---

# t2-bridge-only-holds-what-it-can-bear

Two footbridges rated differently. Each one sags in proportion to the total weight
standing on it, gives way the moment that total goes over its own rating, stays
down while anything is still on the fallen deck, and heaves back up once it is
clear. The character's own weight is part of the total, and it changes mid-round.

**Deliverable surface: C++ under `Source/ThirdPerson/`** — the `cpp` basket by the
2026-08-11 owner decision on baskets. It ships in `craftbench-public/` because that
is the set this batch is authored into.

> **Built against the 2026-08-18 difficulty bar.** The two subsystems that have to
> agree are *occupancy* and *the deck's pose* — and they are coupled both ways: the
> deck sags because of what is standing on it, and what is standing on it has to be
> measured against wherever the deck now is. A footprint worked out once at start-up
> is correct for the first four measured stands and wrong for the fifth, because by
> then the deck is two metres lower and the anvil is down there with it.

## Primary concept

- `moving-platform-load` — an actor deciding its own state from what is standing on
  it, measured against a body that its own decision moves
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/movement-components-in-unreal-engine)

The load-bearing behaviour is **a decision whose input is measured against a thing
the decision itself moves**. The grade never asks *how*: a per-tick overlap query, a
box test against the deck's live bounds, or a sweep all pass identically. What
cannot pass is any answer that fixes the measurement to where the deck started.

## Composed concepts

- `per-instance-configuration` — two spans of the same class answering to their own
  rating, and three crates to their own weight, all read at runtime
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-uproperties)
- `character-as-a-load` — the possessed character's own mass, a stock reflected
  property, counted alongside the crates and changed mid-run by the yard
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/character-movement-component-in-unreal-engine)
- `state-machine-with-a-latch` — hold / give way / stay down while occupied / heave
  back up, re-armable, without oscillation
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/actor-ticking-in-unreal-engine)

## Prompt given to the agent

> The yard has two footbridges. Each is one span with a ramp up at either end, and
> each carries a number: how much weight **it** is rated to hold.
>
> Everything that can stand on a span carries its own weight the same way. Each
> crate says what it weighs, and so does the character the player controls — that
> number is one the stock character already has; nothing has been added for this.
> **None of these numbers is fixed.** The yard stamps fresh ones every time it
> opens, and partway through a round it puts a pack on the character and she gets
> heavier. Read a number when you need it; one you remembered will be out of date.
>
> **Something is standing on a span while it is over the deck and resting on it —
> wherever the deck happens to be at that moment.** Nothing is ever set down
> half-on.
>
> What a span is carrying is everything standing on it, added together. While that
> total is at or under the rating the span holds, and it sags in proportion to how
> much of the rating is in use: dead level with nothing on it, sagged by the full
> amount it can sag at exactly the rating, half that at half. Get the sag right to
> within a tenth of the rating.
>
> The moment the total goes over, the span gives way: **the deck drops to the ground
> and whatever it was carrying rides it down and comes to rest on it.** It stays
> down until nothing at all is left standing on the deck — not merely until the load
> falls back under the rating — and then heaves itself back up, level, and behaves
> as it did before. It must reach each new state within **two seconds**.
>
> The character is walked on and off both spans on foot, over and over. Where things
> stand, what they weigh and what a span is rated for are the yard's, not yours: it
> puts things down, picks them up and moves them about as it pleases. The span's
> body, the sag, the giving way and the heaving back up are all supplied and
> working — nothing decides when to use them. Do not edit the level, any config
> file, or any test file. Write your solution in C++ under `Source/ThirdPerson/`.

## Workspace state pre-task

**Deliverable root: `Source/ThirdPerson/`** (the agent-writable runtime module on
this substrate). `Source/CraftBenchTests/` is deny-listed and a submission file
under it is a SANDBOX-REJECT (exit 4), not a graded FAIL; so are `Content/Maps/`,
`Content/ThirdPerson/`, `Content/Characters/` and every `Config/` file (this task
declares no `config_allow`).

Files that **exist** under `Source/ThirdPerson/`:

- The stock UE 5.8 Third Person C++ template sources. No edit needed.
- `Tasks/t2-bridge-only-holds-what-it-can-bear/BridgeSpanActor.h` / `.cpp` —
  `class THIRDPERSON_API ABridgeSpanActor : public AActor`, tagged `LoadSpan`.
  Supplied:
  - `Anchor` — a bare scene component, **the root**. It is the deck's *resting*
    place and it never moves; the deck slides underneath it.
  - `Deck` — a 900 x 700 x 40 static mesh under the anchor, `BlockAll`, **movable**.
    Movable is load-bearing: somebody standing on a movable primitive is carried
    when it moves, and a non-movable deck would slide out from under them.
  - `StrainLamp` — a point light riding the deck, tinted green-to-red with the sag
    by the supplied code. Presentation only; nothing is graded on it.
  - `UPROPERTY(EditAnywhere, BlueprintReadOnly) float RatedLoadKg` — what **this**
    span is rated to hold.
  - `UPROPERTY(VisibleAnywhere, BlueprintReadOnly) float FullSagCm` — how far the
    deck sits below rest when it is carrying exactly its rating.
  - `UPROPERTY(VisibleAnywhere, BlueprintReadOnly) float GiveWayDropCm` — how far
    the deck drops when the span gives way.
  - **The three switches**, all `UFUNCTION(BlueprintCallable)`:
    `SetSagFraction(float 0..1)`, `GiveWay()`, `HeaveBackUp()`; plus
    `UFUNCTION(BlueprintPure) bool HasGivenWay()` and
    `float GetCommandedSagFraction()`.
  - Its `Tick` **only** moves the deck toward the pose it was last commanded (any
    pose to any pose inside 0.35 s) and tints the lamp. It reads nothing about the
    world, counts nothing and decides nothing: no overlap handler, no reference to
    the character, no call to a switch outside `BeginPlay`. **The decision has to
    land on this class** — both spans are placed instances in a map you cannot edit,
    so a subclass would never be instantiated.
- `Tasks/t2-bridge-only-holds-what-it-can-bear/YardLoadActor.h` / `.cpp` —
  `class THIRDPERSON_API AYardLoadActor : public AActor`, tagged `YardLoad`.
  Supplied: `Body` (a 120 cm cube, the root, movable, `BlockAll`, **not** simulating
  physics) and `UPROPERTY(EditAnywhere, BlueprintReadOnly) float WeightKg`. Its
  `Tick` supplies one piece of physical behaviour that is **not** the graded
  decision: it keeps its feet on whatever is directly beneath it — a downward trace,
  sit when within 2 cm of a surface, otherwise accelerate downward under gravity
  until it lands. It never moves sideways on its own. This is why a crate follows a
  sagging deck down and comes to rest on a fallen one without a submission having to
  do anything about it.
- `Content/Maps/t2-bridge-only-holds-what-it-can-bear/L_TrestleYard.umap` — the
  staged yard, committed binary. World Settings name **NO game mode**, so the level
  inherits `BP_ThirdPersonGameMode` and Enhanced Input survives. What is in it:

  | Element | Placement | Notes |
  |---|---|---|
  | Floor | 7,600 x 5,600, top at Z=0, striped every 400 cm, stripes **non-colliding** | |
  | Two `ABridgeSpanActor`s | 1,800 cm apart, decks 900 x 700 x 40 with the top at Z=+240 at rest | rated differently; both movable |
  | Four approach ramps | 720 of run rising 240 (18.4 degrees), 700 wide, meeting each deck end 20 cm short | walkable; the gap covers the tilted slab's own overhang |
  | Trestle posts | four under each deck | **non-colliding paint** — a solid post would either hold a fallen deck up or block the way off one |
  | Three `AYardLoadActor`s | parked on a bank to the west | different weights |
  | PlayerStart | at the yard's centre | |
  | Backdrop + two landmarks | a back wall and two differently sized posts | a moving camera is distinguishable from a still one |
  | Fixture | one placed `ATrestleLoadFunctionalTest` | |

  **The ratings, the weights and the coordinates are deliberately NOT in this
  section.** They are readable in the level, on the actors — and they are re-stamped
  per run (see *Hidden invariants*).

- `cameras.json` (the camera-plan lane; not part of this release) — the
  presentation-only camera plan. Non-gating.

Files that **do not exist**:

- No load bookkeeping, no state machine, no Blueprint subclass, no level edits. The
  empty submission compiles (L1 green) and FAILs L2 the first time the character
  stands on a span, because the deck does not sag.
- No test source in the agent's writable path. `ATrestleLoadFunctionalTest` lives in
  the `CraftBenchTests` module the agent can neither read nor modify.

## Verifier specification

The test runs in PIE from
`Content/Maps/t2-bridge-only-holds-what-it-can-bear/L_TrestleYard.umap` on the
**ThirdPerson** substrate, ticked at a fixed deterministic step
(`-deterministic -FPS=60`). Verification primitive: **pie-checkpoint-sampling** plus
an every-frame readback of each deck's **world transform** — a visible consequence,
never a private member — over a fixture-driven walk.

**The fixture stamps every number, it does not read one.** Both ratings, all three
crate weights and both sag distances are written into the world in
`FWorldDelegates::OnWorldInitializedActors` — after `PostInitializeComponents` and
**before any placed actor's `BeginPlay`** — and the character's mass is stamped in
`PrepareTest`. Every gate below computes from what the fixture wrote. Three
consequences, all deliberate:

1. **The numbers differ from run to run** (drawn from a seeded range and logged), so
   no constant can be right twice, and there is no window in which a remembered
   number is the right one.
2. **A submission cannot satisfy a gate by editing the number the gate is about.**
   Zeroing the character's mass would take the character out of the fixture's own
   arithmetic too — so instead the divergence is graded, by
   `TheYardsSetupIsNotYoursToChange`.
3. **`FullSagCm` and `GiveWayDropCm` are stamped as well as pinned.** They are the
   scale every up/down and sag verdict is measured in; a submission that shrank the
   give-way drop to 50 cm would otherwise satisfy every gate with a collapse that is
   not a collapse.

**The drive is derived from the level, not written down.** Every waypoint is a
function of where the decks actually are: the character's lane is 200 cm one side of
each deck's centre line and the crate lane 200 cm the other (nearest approach 298 cm
against a 102 cm combined radius); the ramp-foot stands are 800 cm out from a deck
end; and the exits off a fallen deck are **sideways**, because after a collapse the
ramp tops are two metres above the deck and cannot be climbed.

**Every waypoint STANDS.** On 2D arrival within 90 cm the fixture runs that step's
yard action once, then dwells 2–10 s and only then advances. Advancing on arrival
would consume the route in seconds and nothing would ever be measured.

**Nothing is asserted at a boundary.** The fixture's occupancy truth has three
values: plainly on the deck (its middle inside the deck's live footprint inset
60 cm, its base within [deck top − 20, deck top + 250]), plainly off it (outside the
same footprint grown by 150 cm), and — between the two — *no opinion*, during which
the span's truth is treated as unsettled and **no gate fires**. A correct submission
may draw that line a few centimetres either side of where the fixture draws it. No
scripted stand is ever taken in the band: every staged position is at least 90 cm
inside the inner footprint.

**Gates are sampled only when a span's truth has been unchanged for 2.5 s** (the
prompt promises two).

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64
        Development" and "ThirdPerson Win64 Development"
```

### L2 — AFunctionalTest behavioral trace

```text
per span, every frame, once its truth has been settled for 2.5 s and nothing is in
the boundary band:

  Drop      := span actor world Z  -  deck component world Z
  Total     := sum of the fixture's stamped weights of everything the fixture says
               is standing on that span (the character included)
  Down      := Drop >= 0.9 * GiveWayDropCm
  Up        := Drop <= FullSagCm + 2 cm

  if the fixture expects the span DOWN:
      Total >= 1.15 * Rating              -> assert Down
          fail: ItGivesWayWhenTheTotalGoesOver
      else if anything is still on it     -> assert Down
          fail: ItStaysDownWhileSomethingIsOnIt
      else (empty, on its way back up)    -> assert nothing
  else:
      assert Up
          fail: ItHeavesBackUpOnceNothingIsOnIt  (if a recovery is pending)
          fail: ItHoldsWhatItIsRatedFor          (otherwise)
      assert |Drop/FullSagCm - Total/Rating| <= 0.12
          fail: TheSagShowsTheWholeLoad

  On the two scripted EAST stands where the character is the ONLY thing on the span,
  an up/down verdict on EAST is reported as TheCharactersOwnWeightCounts instead, so
  attribution is deterministic.

assert: TheYardsSetupIsNotYoursToChange -- every frame: each span still exists, is
        where the yard put it (2 cm), still reads the RatedLoadKg / FullSagCm /
        GiveWayDropCm the yard stamped (0.5), and its deck still blocks the pawn and
        is visible; each crate still exists, is within 60 cm horizontally of where
        the yard last put it (vertical movement is free -- crates fall) and still
        reads its stamped WeightKg; and the character still reads the mass the yard
        stamped
assert: TheYardFinishedItsRounds -- ONE predicate, evaluated both as the early-exit
        condition and at the sentinel: every scripted stand was sampled (a stand
        counts only when the character was standing where that stand says she is,
        per the fixture's own occupancy truth) AND each span gave way at least once
        AND each span came back up at least once
```

The checkpoint schedule is a calibration line every 10 s (rating, load, item list,
measured sag against expected, drop, expected state, give-way and recovery counts,
per span) plus a **sentinel at t = 520 s**, far past the ~240 s drive, because
`ACraftBenchFunctionalTest::Tick` ends the test the moment the last scheduled
checkpoint is sampled. A healthy run does not wait for it: the fixture calls
`FinishTest(Succeeded)` the moment `TheYardFinishedItsRounds`' predicate is
satisfied — **the same predicate**, so a submission that fails it cannot escape the
sentinel by finishing early.

The 14 scripted stands, in order:

| # | Where | What the span is carrying | Wanted |
|---|---|---|---|
| 1 | yard centre | nothing, both spans | level, sag 0.00 |
| 2 | WEST deck | the character (0.40 of the rating) | holds, sag 0.40 |
| 3 | off WEST | the anvil alone (0.80) | holds, sag 0.80 |
| 4 | WEST deck | anvil + character (1.20) | **gives way** |
| 5 | off the fallen deck | the anvil, on the fallen deck | **stays down** |
| 6 | same, anvil lifted | nothing | **heaves back up** |
| 7 | WEST deck | the character again (0.40) | holds, sag 0.40 — re-armed |
| 8 | off WEST | sack + keg (0.62) | holds, sag 0.62 |
| 9 | EAST deck | the character alone (about 0.70 of EAST) | holds — and WEST still holds 0.62 |
| 10 | EAST deck, packed | the packed character alone (1.35 of EAST) | **gives way** |
| 11 | off the fallen deck | nothing | **heaves back up** |
| 12 | WEST deck | sack + keg + packed character (>= 1.30) | **gives way** |
| 13 | off the fallen deck | sack + keg, on the fallen deck | **stays down** |
| 14 | same, both cleared, then yard centre | nothing, both spans | **heaves back up**, sag 0.00 |

**Staging faults are attributed, not scored — and only two of them.**
the internal design note (not shipped) (executed 2026-08-14, owner-approved): an `::Error`
takes the run out of the denominator, so it may fire only on a condition no
submission can manufacture. Here that is exactly *no world* and *the fixture's own
drawn numbers failing the fixture's own arithmetic* — the fixture picks those
numbers, so nothing a submission does can reach either. **Everything else about the
world is graded**, including a missing span, a missing crate, a property the fixture
cannot stamp and a missing player character: those are all reachable from a
submission's `BeginPlay`, so they FAIL through
`TheYardsSetupIsNotYoursToChange`. The cost of that choice is that a genuine
substrate fault would fail every submission alike — which is what `cb refgate` on
the committed reference is for.

## Requirement-to-assertion map

| Prompt requirement | Gate that checks it | When that gate does NOT run |
|---|---|---|
| each span answers to **its own** rating | `TheSagShowsTheWholeLoad` and `ItHoldsWhatItIsRatedFor`, on **both** spans at every settled sample | during the 2.5 s after that span's truth changes, and while anything is in the boundary band |
| what it carries is everything on it, **added together** | `ItGivesWayWhenTheTotalGoesOver` at stands 4 and 12, where every item is individually under the rating | same |
| holds anything at or under the rating | `ItHoldsWhatItIsRatedFor` (Total <= 0.85 x rating at every scripted hold) | same |
| sag in proportion, to within a tenth | `TheSagShowsTheWholeLoad`, tolerance 0.12 | same |
| the character's weight counts | `TheCharactersOwnWeightCounts` at stands 9 and 10 | same |
| the character's weight **changes** mid-round | the same gate: stand 9 must hold and stand 10 must give way with nothing but the character on the span | same |
| the numbers are not fixed run to run | not a gate but the **staging**: every number is drawn per run and stamped pre-BeginPlay, so a hard-coded constant fails the gates above | never |
| the deck drops and the load rides it down | supplied (`GiveWay` + the crate's own foot-keeping); asserted indirectly by `ItStaysDownWhileSomethingIsOnIt`, which requires the load to still be **on** the fallen deck | same as row 1 |
| stays down while anything is on it | `ItStaysDownWhileSomethingIsOnIt` at stands 5 and 13 | same |
| heaves back up once clear, level | `ItHeavesBackUpOnceNothingIsOnIt` at stands 6, 11 and 14 | same |
| behaves as before afterwards | stand 7 (holds and sags 0.40 again) and stand 12 (gives way again) | same |
| reaches each new state within two seconds | the 2.5 s settle window itself: at 2.5 s after the fixture's truth changed, the deck must already be in the new state | never |
| where things stand / what they weigh / what a span is rated for are not yours | `TheYardsSetupIsNotYoursToChange`, every frame | never |
| the character is walked on and off both spans, over and over | `TheYardFinishedItsRounds` — 14 stands, each countable only with the character standing where the stand says | never (it is the sentinel and the early-exit condition) |
| C++ under `Source/ThirdPerson/` | sandbox: a file outside the writable set is exit 4, not a graded FAIL | never |

## Reference solution metadata

- **Files touched:** 1 —
  `Source/ThirdPerson/Tasks/t2-bridge-only-holds-what-it-can-bear/BridgeSpanActor.{h,cpp}`
  (a `#include` block, two declarations, and two function bodies).
- **LOC:** ~85 added lines of substance (~110 with comments).
- **Shape:** every frame, take the deck's **live** world bounds; sum the stamped
  weight of every `YardLoad` actor and the possessed character whose middle is over
  that box and whose base is on it; if the span has given way, heave back up only
  when the count reaches zero; otherwise give way when the total exceeds the live
  rating, and otherwise command a sag of total/rating.
- **Honest senior-dev hours: 4–6** — the top of T2, not the middle. Where they go:
  ~45 min reading the two scaffolds and the level and working out that weights live
  in two different places (a property on the crate, and a number the stock character
  already carries); ~1.5 h on occupancy that stays correct while the thing it is
  measured against MOVES; ~1 h on the state machine (hold / give way / stay down
  while occupied / heave up) without oscillation; ~1 h debugging the two
  interactions that actually bite — occupancy against a moving deck, and every
  number changing under you; ~30 min making it per-instance across two differently
  rated spans rather than a singleton. The deliverable is small; the cost is that
  four things have to agree.

## Anti-gaming notes

1. **A footprint remembered from start-up.** *Failure mode*: work out the deck's
   footprint once in `BeginPlay` (a bridge's footprint IS fixed, in every mental
   model) and test occupancy against it for ever. *Defense*: correct for stands 1–4;
   at stand 5 the deck is 200 cm lower and the probe is looking at an empty patch of
   air, so the span reads empty and heaves back up under the anvil.
   `ItStaysDownWhileSomethingIsOnIt` names it, and says in the message that the deck
   moved and what counts as standing on it moved with it. **This is the gate the
   task exists for.** The near-neighbour — clearing the occupancy set on give-way
   ("we dropped everything, so we are empty now") — dies at the same gate, and the
   prompt forecloses the reading that would justify it by saying where the load ends
   up.
2. **Listening for arrivals and not departures.** *Failure mode*: add to the total
   when something turns up on the span and never take it off. *Defense*: the yard
   lifts the anvil at stand 6 and clears both crates at stand 14; a total that never
   returns to zero keeps both spans down and fails
   `ItHeavesBackUpOnceNothingIsOnIt`. The same shape also fails
   `TheSagShowsTheWholeLoad` at stand 14, which requires 0.00 on both spans.
3. **A number read once.** *Failure mode*: cache the rating, a crate's weight or the
   character's mass. *Defense*: every number is drawn per run and stamped before any
   `BeginPlay`, so a hard-coded constant is simply wrong; and the character's mass
   changes between stands 9 and 10, which `TheCharactersOwnWeightCounts` measures
   directly — hold at ~0.70 of the rating, give way at 1.35 of it, with nothing else
   on the span either time. That stand pair is the **only** place the cached-mass
   answer dies: every other stand with the packed character on it also has crates on
   the span, so the total is over the rating either way.
4. **Keeping the total down instead of implementing the rule.** *Failure mode*:
   shove or teleport the cargo off the deck; or resolve an overload by writing a
   bigger number into the span's rating, or a zero into a crate's weight or the
   character's mass. *Defense*: `TheYardsSetupIsNotYoursToChange` pins every crate's
   horizontal position to 60 cm of where the yard last put it, and pins
   `RatedLoadKg`, `FullSagCm`, `GiveWayDropCm`, every `WeightKg` and the character's
   mass to what the yard stamped, every frame. Vertical movement is deliberately
   free, because crates are supposed to fall.
5. **Blinding the measurement instead of answering it.** *Failure mode (the one that
   matters)*: implement "the deck drops out from under it" as a collision toggle that
   is never restored, or hide the deck. The character then falls through, walks the
   whole route on the floor below, nothing is ever on any span, and **every load gate
   goes vacuously green** — this is the base-fixture auto-success trap in its purest
   form. *Second shape*: notice that the fixture asserts nothing while something sits
   in its boundary band and try to park something there. *Defense*: three, layered.
   `TheYardsSetupIsNotYoursToChange` checks every frame that the deck still blocks the
   pawn and is visible, and pins every crate to 60 cm of where the yard put it.
   `TheYardFinishedItsRounds` counts a stand only when the character is standing on
   the span that stand names, so a run in which nothing can stand anywhere reaches the
   sentinel with 14 unsampled stands — and a drive stalled by a teleported character
   leaves stands unsampled the same way. The early exit uses **the same predicate**,
   so nothing can finish past it.

## Hidden invariants

- **Every number is drawn per run and re-stamped into the world before the first
  `BeginPlay`,** from a seeded stream whose seed is logged. The west rating is drawn
  in 20 kg steps from 560 to 660; the east rating is 0.56–0.62 of it; the crates are
  0.24, 0.38 and 0.80 of the west rating; the character is 0.40 of it, and 1.35 of
  the *east* rating once packed. Those fractions are what the whole drive rests on —
  the anvil (0.80) and the character (0.40) are each comfortably under the west
  rating and comfortably over it together — and the fixture **re-checks all twelve
  of the claims it is about to make** against the numbers it drew, refusing to run
  (as an `::Error`, unmanufacturable) rather than making a demonstration the draw
  does not support.
- **The deck's height is measured against the span actor's own origin**, which is
  the deck's resting centre and is pinned every frame. Nothing the span *says* about
  itself is trusted: not `HasGivenWay()`, not `GetCommandedSagFraction()`, not any
  private member.
- **The 0.85 / 1.15 sampling bands** narrow where the fixture asserts, never what it
  demands: between them it says nothing, so a correct answer can never round the
  wrong way at a stand.
- **The occupancy band** (inner footprint inset 60 cm, outer grown 150 cm) is a
  one-sided safety margin in the same spirit. Every staged position clears the inner
  box by at least 90 cm, so no reasonable definition of "standing on it" disagrees
  with the fixture at a sampled stand.

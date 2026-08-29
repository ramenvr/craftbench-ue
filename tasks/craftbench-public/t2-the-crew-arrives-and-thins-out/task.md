---
id: t2-the-crew-arrives-and-thins-out
substrate: ThirdPerson
set: craftbench-public
tier: T2
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_CrewDeck :: ACrewMusterFunctionalTest"]
fps_legs: [60, 20]
---

# t2-the-crew-arrives-and-thins-out

A muster deck where walking onto a plate calls a watch of hands aboard **one at a
time**, each taking the lowest free standing spot and wearing a badge number spent
once for the whole night — and walking onto a second plate sends **some** of them
ashore, named not by where they stand but by **when they turned up**. The mate then
re-chalks the board with no announcement, a second watch is called onto exactly the
spots that came free, and part of that one is stood down too.

> **Built against the 2026-08-18 difficulty bar.** Three subsystems that genuinely
> interact — a paced fill that seats by lowest-free, a consumable identity roster, and
> a removal rule addressed by arrival position within the current watch — where each
> one's output is the next one's input. The load-bearing coincidence is deliberate:
> on the first watch, "the second to turn up" and "standing spot number 2" are the
> same hand, so the wrong reading of the slate passes watch 1 completely and only dies
> on watch 2, where the three new hands land on the non-contiguous spots the first
> stand-down freed. Every number is read off the actors and re-chalked twice mid-run,
> so a hard-coded answer is wrong from the first call.

## Primary concept

- `spawning-and-destroying-actors` — Spawning Actors
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/spawning-actors-in-unreal-engine)

The load-bearing behaviour is **a paced runtime spawn whose placement, identity and
later selective destruction are all functions of each other**. The grade never asks
*how*: a `Tick` on a board, a repeating timer, an overlap delegate on a plate — all
pass identically, as long as the deck settles within the half second the prompt
promises.

## Composed concepts

- `actor-lifecycle` — hands are created and destroyed mid-run while everything else on
  the deck is a fixed placed cast; the logic has to live on something already standing
  there and be correct from the first frame
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-actor-lifecycle)
- `ps-timers` — a paced fill that produces one arrival every chalked interval, runs to
  its number whether or not the trigger is still held, and cannot be started twice
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/gameplay-timers-in-unreal-engine)
- `collision-overview` — the only trigger is locomotion onto a floor plate, which
  reports what is standing on it and blocks nothing
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/collision-in-unreal-engine---overview)
- `ps-components` — the graded readout is per-instance: a lamp per standing spot on a
  board, and a readable number over each hand's head
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/components-in-unreal-engine)

**Production pattern.** This is the standard wave/spawn-manager shape every
tower-defense, arena and horde game ships: a paced spawn budget read from data, a fixed
set of spawn anchors filled by a lowest-free rule, a per-instance identity issued from a
pool that is not recycled, and a selective cull addressed by spawn order rather than by
slot. The "two identical managers, only one of which was triggered" arrangement is the
standard regression control for exactly this family.

## Prompt given to the agent

> The deck has two muster boards. Each has its own row of numbered standing spots
> painted on the floor in front of it, its own row of lamps — one lamp per standing
> spot — and its own pair of floor plates: a **call** plate and a **stand-down** plate.
> Every spot starts empty and every lamp starts dark.
>
> **Calling a watch.** When the character the player controls steps onto a board's call
> plate, that board — and only that board — calls for hands. **How many it calls for is
> chalked on the board**, and it is the number chalked there at the moment the plate is
> stepped on. They do not all turn up at once: **they arrive one at a time, the first
> one arrival-gap seconds after the plate was stepped on, and one more every
> arrival-gap seconds after that, until the board has what it called for.** The arrival
> gap is chalked on the board too. Once a call is made it runs to its number whether or
> not anybody is still standing on the plate, and stepping on and off again while a
> call is still running does not start a second one. **Nobody turns up who was not
> called for**, ever.
>
> **Where they stand.** Each hand that turns up takes **the lowest-numbered standing
> spot on that board that is free at that moment**, and stands on it. **A hand never
> moves again for as long as it is aboard** — it does not shuffle up when the spots
> beside it empty.
>
> **Nobody waits in the wings.** A hand is in the world only while it is aboard: it
> comes into being on the spot it takes when it turns up, and when it is sent ashore it
> is gone from the deck altogether. **There is never a hand anywhere — on the deck or
> off it, in sight or out of it — that is not standing on a numbered spot.**
>
> **Badges.** Each hand wears a number where anyone can read it. The numbers come from
> **the board's roster, in the order the roster is written, one number to each hand in
> the order the hands arrive** — each hand taking the first number on the roster that
> has not been issued yet tonight. A number is spent once and is never issued again for
> the rest of the night — not to a later hand on the same board, and not after the deck
> has emptied out.
>
> **The lamps.** A board's lamp is lit exactly while its own standing spot has somebody
> on it, and dark otherwise.
>
> **Standing a watch down.** When the character steps onto a board's stand-down plate,
> that board sends some of its hands ashore. **Which ones is chalked on the board as a
> list of places in the arrival order of the watch it has just called** — read it as
> "the second, the fourth and the fifth to turn up this watch". It is not a list of
> standing-spot numbers and it is not a count. Hands that came aboard on an **earlier**
> watch are not in that arrival order at all and are never sent ashore by it: they stay
> exactly where they are, keeping the badge they were issued, and their lamps stay lit.
> Everybody else from the watch just called stays too. A hand that is sent ashore
> leaves the deck entirely, and its spot is free again.
>
> **The chalk is not fixed for the night.** Between watches the mate wipes the board
> and chalks new numbers — how many to call for, the arrival gap, the roster, and the
> list of who goes. Nothing announces it. **Whatever is chalked at the moment you need
> a number is the number**; one you wrote down earlier will be stale.
>
> **The other board is the other board.** Only the board whose plate was stepped on
> does anything at all. The second board's spots stay empty, its lamps stay dark and
> its roster stays unspent unless somebody steps on its own plates.
>
> The deck has **half a second** to catch up after anything happens.
>
> None of this is one-shot. A board calls a watch, stands part of it down, calls
> another watch onto the spots that came free, and stands part of that one down, as
> many times over as the night calls for it — and the second time round is judged
> exactly like the first.
>
> The deck is not yours to rearrange. Do not move the standing spots, the plates, the
> boards or anybody already aboard, and do not change anything chalked on a board. The
> hands, their badges and the lamps are all built and working: a hand can be brought
> aboard and sent ashore, a badge can be written on one, a lamp can be switched.
> **Nothing decides when to do any of it.** Because the deck itself is fixed, whatever
> does the deciding has to live on something already standing on it — a board, a plate,
> a standing spot, or the character.
>
> Do not edit the level, any config file, or any test file. **Write your solution in
> C++ under `Source/ThirdPerson/`** — that is the only place your work may land.

## Workspace state pre-task

**Deliverable root: `Source/ThirdPerson/`** (the agent-writable runtime module on this
substrate). `Source/CraftBenchTests/` is deny-listed and a submission file under it is
a SANDBOX-REJECT (exit 4), not a graded FAIL; so are `Content/Maps/`,
`Content/ThirdPerson/`, `Content/Characters/` and every `Config/` file (no
`config_allow` is declared by this task).

Files that **exist** under `Source/ThirdPerson/`:

- The stock UE 5.8 Third Person C++ template sources. No edit needed.
- `Tasks/t2-the-crew-arrives-and-thins-out/MusterBoardActor.h` / `.cpp` —
  `class THIRDPERSON_API AMusterBoardActor : public AActor`, tagged `MusterBoard`.
  **A board of chalk and a row of lamps, and nothing else.** Supplied and working:
  - `UPROPERTY(EditAnywhere, BlueprintReadOnly) FName BoardTag` — the name this board
    is known by. Every standing spot and every floor plate on the deck carries the name
    of the board it belongs to.
  - The chalk, all `UPROPERTY(EditAnywhere, BlueprintReadOnly)`: `int32 HandsToCall`,
    `float SecondsBetweenArrivals`, `TArray<int32> RosterCodes`,
    `TArray<int32> SlatePositions`. **Read them off the board at the moment you need
    them; the two boards do not carry the same values and the mate changes them part
    way through the night.**
  - `UFUNCTION(BlueprintCallable) void SetLampLit(int32 SpotNumber, bool)`, plus
    `IsLampLit(int32)` and `GetLampCount()`. The lamp row is numbered the way the
    standing spots are and runs from spot number 1 upward. `SetLampLit` writes a real
    point light's intensity **and** swaps the bulb's material — a material *swap*, not
    a parameter write, because not every prototype material here carries a colour
    parameter and a set that silently does nothing leaves the state invisible while
    looking like it worked. Every lamp is put out in `BeginPlay`.
  - A `Tick` that does one thing: copies the chalk onto the board's own face so a
    person watching can see the mate re-chalk it. **It decides nothing.**
- `Tasks/t2-the-crew-arrives-and-thins-out/CrewBerthActor.h` / `.cpp` —
  `ACrewBerthActor`, tagged `CrewBerth`. A painted, numbered square on the deck.
  Supplied: `UPROPERTY(EditAnywhere, BlueprintReadOnly) FName BoardTag`,
  `int32 SpotNumber`, and `UFUNCTION(BlueprintPure) FVector GetStandLocation() const`
  — exactly where somebody stands when they take this spot. Completely passive; it
  notices nothing. Non-colliding on every channel.
- `Tasks/t2-the-crew-arrives-and-thins-out/CrewPlateActor.h` / `.cpp` —
  `ACrewPlateActor`, tagged `CrewPlate`. A 400 x 400 cm pad with an overlap region as
  its root. Supplied: `UPROPERTY(EditAnywhere, BlueprintReadOnly) FName BoardTag` and
  `bool bIsCallPlate` (true on a board's call plate, false on its stand-down plate);
  the region itself as `PlateVolume`, which reports what enters and leaves and blocks
  nothing; `UFUNCTION(BlueprintPure) bool IsSomebodyStandingHere() const`; and a small
  lamp that rides up while somebody is standing there. **Nothing decides what to do
  about any of that.**
- `Tasks/t2-the-crew-arrives-and-thins-out/CrewHandActor.h` / `.cpp` —
  `ACrewHandActor`, tagged `CrewHand`. A body, a head, and a badge over its head.
  Supplied: `UFUNCTION(BlueprintCallable) void SetBadgeCode(int32)` and
  `UFUNCTION(BlueprintPure) int32 GetBadgeCode() const`, which reads the number back
  off the thing on screen rather than off a private copy — what a hand is *wearing* and
  what it *believes* it is wearing can never disagree. A hand blocks nothing on any
  channel and never moves itself. **Nothing brings one aboard or sends one ashore.**
- `Content/Maps/t2-the-crew-arrives-and-thins-out/L_CrewDeck.umap` — the staged deck,
  committed binary. World Settings name **NO** game mode, so the level inherits
  `BP_ThirdPersonGameMode` and `BP_ThirdPersonPlayerController` (which carries
  `IMC_Default`); this task defines no pawn subclass and no game mode, so a human can
  press Play and walk the deck with WASD. What is in it:

  Two muster stations side by side on one deck, each looking down a lane of its own, the
  near one where you start.

  | Element | Placement | Notes |
  |---|---|---|
  | Floor | 13,000 x 13,000, striped every 400 cm, stripes **non-colliding** | flat; its top face is the deck |
  | Two `AMusterBoardActor`s | one at the far end of each lane, looking down it; the two lanes run parallel, 4,500 cm apart | identical class, different chalk |
  | Twelve `ACrewBerthActor`s | six per board, spot numbers **1..6**, 500 cm apart in a row 800 cm in front of their own board, well clear of the walking lane | painted on the floor; the lamp row and the spot row read the same way along the board |
  | Four `ACrewPlateActor`s | one call plate and one stand-down plate per board, on that board's own lane, 2,000 cm apart | pads oversized so a walk cannot clip a corner, and 10 cm proud of the deck |
  | PlayerStart | on the near board's lane, midway between its two plates | the whole walk is one straight line |
  | Backdrop + landmarks | a low back wall behind each board and two differently sized posts, **non-colliding** | a moving camera is distinguishable from a still one |
  | Fixture | one placed `ACrewMusterFunctionalTest` | |

  **Everything except the floor and the four plate pads is non-colliding on every
  channel**, so nothing on the deck can shove a hand off its spot or get between the
  character and a plate. **The chalk values are deliberately NOT in this section.**
  They are readable in the level, on the boards themselves — and what the committed map
  holds is not what the run is graded against (see *Hidden invariants*).

Files that **do not exist**:

- No call logic, no arrival clock, no spot assignment, no badge issue, no roster
  bookkeeping, no removal rule, no code that lights a lamp or spawns or destroys a
  hand, no Blueprint subclass, no level edits. The empty submission compiles (L1
  green) and FAILs L2 on the first call, because the deck stays empty and dark.
- No test source in the agent's writable path. `ACrewMusterFunctionalTest` lives in the
  `CraftBenchTests` module the agent can neither read nor modify.

## Verifier specification

The test runs in PIE from
`Content/Maps/t2-the-crew-arrives-and-thins-out/L_CrewDeck.umap` on the **ThirdPerson**
substrate, ticked at a fixed deterministic step (`-deterministic -FPS=<rate>`),
**twice**: once at 60 and once at 20 (`fps_legs: [60, 20]`), each in its own PIE
process. The whole task hangs on an arrival cadence measured in seconds, so a tick
counter fitted to 60 Hz must be made to fire at the wrong wall time.

Verification primitive: **pie-checkpoint-sampling** plus an every-frame readback of the
boards' point-light intensities and of the **text displayed on each hand's badge** —
what a reviewer sees — over a fixture-driven walk down one lane, compared against the
fixture's own running model of the whole rule.

### The fixture runs the same rule

Every frame the fixture re-reads **both** boards' four chalked values by name and live,
re-reads every standing spot's `BoardTag` / `SpotNumber` and every plate's
`BoardTag` / `bIsCallPlate`, observes its own overlap of the character's capsule with
each plate volume, and steps its own model: the same latch-on-step call, the same
paced fill, the same lowest-free seating, the same first-unspent-code issue with a
whole-run ledger, and the same arrival-place removal. Every gate compares the deck's
visible state against that model.

The fixture NEVER reads the submission's own bookkeeping. It reads only: which actors
tagged `CrewHand` exist, where they are, what their badges say, and which lamps are
burning.

### The staged schedule (fixture-owned, not what the .umap holds)

The fixture stamps all four chalked values on **both** boards from a pinned schedule,
deterministic per leg. The committed `.umap` deliberately holds different values, so a
submission that read the map offline — or cached the chalk in `BeginPlay`, which fires
before `PrepareTest` — is wrong from the **first** call rather than from the second.

| When | Working board (`PortBoard`) | Twin (`StarboardBoard`) |
|---|---|---|
| in the committed `.umap` | call 4, gap 1.9 s, roster [5,7,9,15], slate [1,2] | call 2, gap 2.9 s, roster [2,3,4], slate [1] |
| `PrepareTest`, before the character walks anywhere | **call 6, gap 2.0 s, roster [41,47,53,59,61,67], slate [2,4,5]** | call 4, gap 3.1 s, roster [11,13,17,19,23], slate [1,2] |
| the watch change (phase 7) | **call 3, gap 2.6 s, roster [41,47,53,59,61,67,71,73,79], slate [1,3]** | call 5, gap 2.2 s, roster [11,13,17,19,23,29,31], slate [2,4] |

Every rule the run turns on is exercised by that schedule, and the arithmetic is closed:

- **Watch 1** fills the empty deck: arrivals 1..6 take spots 1..6 and are badged
  41, 47, 53, 59, 61, 67. Slate `[2,4,5]` sends arrival places 2, 4 and 5 ashore, i.e.
  spots 2, 4 and 5. Survivors: spot 1 = 41, spot 3 = 53, spot 6 = 67; lamps 1, 3, 6.
- **Watch 2** calls 3 into the exactly-3 free spots 2, 4, 5. Arrival 1 takes spot 2,
  arrival 2 takes spot 4, arrival 3 takes spot 5. The roster is re-chalked LONGER, not
  fresh, so the next unspent codes are 71, 73, 79. Slate `[1,3]` sends arrival places
  1 and 3 ashore, i.e. spots **2 and 5** — *not* spots 1 and 3.
- **Final frame**: spot 1 = 41, spot 3 = 53, spot 4 = 73, spot 6 = 67; lamps 1, 3, 4, 6
  burning and 2, 5 dark; the twin board untouched throughout.

The two boards' rosters are disjoint, and both are disjoint from the numbers the
committed map holds, so any code appearing on any badge names exactly which source it
came from.

### The map contract the fixture enforces

Hidden from the agent on purpose — these are the staging preconditions, not behaviour.
`PrepareTest` ends the run as `HARNESS-PRECONDITION` (never a graded FAIL) unless all of
them hold, so the authoring script must hit them and any later edit to the map must keep
them.

| Precondition | Threshold |
|---|---|
| actors tagged `MusterBoard` / `CrewBerth` / `CrewPlate` | exactly 2 / 12 / 4 |
| board names (`BoardTag`) | exactly `PortBoard` (**the working board the drive walks**) and `StarboardBoard` (the twin) |
| standing spots per board, numbered | exactly 6, running **1..6** contiguous — the whole watch-1 coincidence dissolves otherwise |
| plates per board | exactly one with `bIsCallPlate` true and one false |
| working board's two plates, apart | >= 1,200 uu |
| PlayerStart to the midpoint of those two plates | <= 400 uu |
| every twin plate to each of {working call plate, working stand-down plate, their midpoint} | >= 1,500 uu |
| every standing spot to each of those three points | >= 600 uu |

The layout that satisfies them with margin, and the one the authoring script should
build (cm, deck top face at **Z = 0**, every actor placed at **Z = 0** — the plate
scaffold offsets its own pad and region internally):

| Actor | Location | Rotation |
|---|---|---|
| Floor (13,000 x 13,000, top at Z = 0) | centred (-1,000, +2,250) | — |
| `AMusterBoardActor` `BoardTag = PortBoard` | (-3,000, 0) | yaw 0 — lamps and chalk sit on the board's local +X face, looking down its lane |
| `AMusterBoardActor` `BoardTag = StarboardBoard` | (-3,000, +4,500) | yaw 0 |
| `ACrewBerthActor` `PortBoard`, `SpotNumber` k = 1..6 | (-2,200, -1,250 + 500(k-1)) | yaw 0 |
| `ACrewBerthActor` `StarboardBoard`, `SpotNumber` k = 1..6 | (-2,200, +3,250 + 500(k-1)) | yaw 0 |
| `ACrewPlateActor` `PortBoard`, `bIsCallPlate` true / false | (-800, 0) / (+1,200, 0) | yaw 0 |
| `ACrewPlateActor` `StarboardBoard`, `bIsCallPlate` true / false | (-800, +4,500) / (+1,200, +4,500) | yaw 0 |
| PlayerStart | (+200, 0) | yaw 180 (facing the call plate) |
| `ACrewMusterFunctionalTest` | anywhere off the lane | — |

Margins: twin plates 4,500 clear of the lane against a 1,500 floor; the nearest standing
spot 1,422 clear against 600; the working plates 2,000 apart against 1,200; PlayerStart
exactly on the midpoint. Spot numbers ascend in **+Y**, which is the direction the
board's own lamp row runs (`LampGlow0`..`LampGlow5` at local Y = -1,250..+1,250), so the
lamp row and the painted numbers read the same way for a person watching.

The **baseline chalk saved into the `.umap`** must differ from the staged schedule on all
eight values and share no roster code with it — `PortBoard`: call 4, gap 1.9,
roster [5,7,9,15], slate [1,2]; `StarboardBoard`: call 2, gap 2.9, roster [2,3,4],
slate [1]. That is what makes a submission which read the map offline, or cached the
chalk in `BeginPlay`, wrong from the **first** call. All four are `EditAnywhere`, which is
what lets `set_editor_property` write them.

### The drive

Tier-1 trigger throughout (`ADOPTION-REVIEW-2026-08-16` §7.1.3): every trigger is
locomotion onto a plate, driven by the shipping per-frame `AddMovementInput` timeline,
on one straight lane with no turn inside the last 600 uu of any approach. Each plate is
fired **twice** in the run (§7.1.4).

| Phase | Where | Until |
|---|---|---|
| 0 | settle at the quiet spot, midway between the two plates | 3 s (gates off — the character drops in) |
| 1 | stand quiet | 4 s — the baseline: both decks empty, every lamp dark |
| 2 | walk to the **call** plate and rest on it | the fixture's own overlap observation + 1.0 s |
| 3 | the first watch arrives; at contact + 4.5 s the drive steps OFF the pad (700 uu back along the lane), at contact + 7.5 s back ON, and it holds the pad from there | contact + call x gap + guard band + 1.5 s |
| 4 | stand quiet, settled | 3 s |
| 5 | walk to the **stand-down** plate and rest on it | contact + 1.0 s |
| 6 | the stand-down settles; walk back to the quiet spot | 4 s |
| 7 | **the mate re-chalks both boards** | 2 s, with every gate suppressed for 2 s either side |
| 8 | walk to the **call** plate and rest on it | contact + 1.0 s |
| 9 | the second watch arrives; the drive rests on the pad throughout | contact + call x gap + guard band + 1.5 s |
| 10 | stand quiet, settled | 3 s |
| 11 | walk to the **stand-down** plate and rest on it | contact + 1.0 s |
| 12 | the stand-down settles; walk back to the quiet spot | 4 s |
| 13 | the long quiet hold — nothing on the deck may change | 12 s, then the run-level gate |

The off-and-on-again in phase 3 is not decoration: it is the only thing that grades
"once a call is made it runs to its number whether or not anybody is still standing on
the plate, and stepping on and off again does not start a second one". It is timed to
land between two arrivals, never inside a guard band.

**`t_contact` is the fixture's own observation**, never a scheduled time: the phase
does not advance until the fixture has itself seen the capsule inside the plate volume,
and every cadence window is measured from that instant.

### Settle, guard bands and suppression

Nothing is judged on a frame where any of these hold. Each is a **widening** of the
disclosed contract, never a narrowing:

- less than **0.75 s** since the fixture's own model last changed (1.5x the half second
  the prompt promises);
- inside a **guard band** of `max(0.75 s, 0.30 x gap)` either side of an expected
  arrival instant. The floor of 0.75 s is what keeps the band a widening of the
  disclosed half second at every staged gap; `PrepareTest` refuses to start (harness
  error, never a graded FAIL) if any staged gap is below **2.0 s**, which is what keeps
  the judged plateau between two bands at least 0.5 s — ten frames on the 20 Hz leg;
- within **0.75 s** either side of any plate contact or release;
- the fixture is itself re-staging the deck (phase 7, plus 2 s either side).

### The sentinel

The checkpoint schedule is 24 calibration checkpoints every 8 s plus a **SENTINEL at
t = 200 s**, far past the ~80 s the drive models, because
`ACraftBenchFunctionalTest::Tick` ends the test the moment the last scheduled
checkpoint is sampled. The run-level gate is evaluated when the last phase completes
**and** again at the sentinel, whichever comes first, and only then does the fixture
call `FinishTest(Succeeded)`.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64
        Development" and "ThirdPerson Win64 Development"
```

### L2 — AFunctionalTest behavioral trace

**Gate precedence, in the order the fixture evaluates them. A named FAIL is never a race
between two gates, but by two different mechanisms and it is worth being exact about
which:** 5 and 6 are mutually exclusive by construction — 5 is armed exactly while a
call's fill window is open and 6 exactly while it is closed — whereas 4 and 5 CAN both
be armed on the same frame (a call that is arriving at the wrong pace is also, on that
frame, a board holding the wrong set of spots). What makes that deterministic is the
ORDER: 4 is evaluated first and ends the run when it disagrees, so the pace answer is
always named as a pace answer and never as a count.

```text
1  TheDeckIsNotYoursToRearrange   -- every frame, from the first
2  TheQuietBoardStaysQuiet        -- every judged frame, independent channel
3  NobodyArrivesUncalled          -- every judged frame OUTSIDE a call's fill window
4  TheyArriveOneAfterAnother      -- a call's plateaus, from the first plateau at which
                                     at least one of that call's hands is aboard
5  TheDeckFillsToTheCalledNumber  -- a call's fill window, from its first plateau until
                                     the next stand-down contact; suppressed on a frame
                                     where gate 4 was armed and DISAGREED
6  TheRightHandsAreLeftStanding   -- the settled window after each stand-down, until the
                                     next call's first plateau
7  NobodyShufflesAlongTheDeck     -- every judged frame from the first arrival onward
8  TheSurvivorsKeepTheirOwnBadges -- every judged frame from the first arrival onward
9  TheBoardShowsWhoIsAboard       -- ALWAYS LAST, and only on a frame where whichever of
                                     5 or 6 was armed has already agreed
```

Gate 4 is deliberately **disarmed until a call has put at least one hand aboard**: "the
watch is arriving at the wrong pace" is a statement about a watch that is arriving, and
"nobody ever turned up" belongs to gate 5, which is the gate the empty submission must
be named by. Gate 9 is evaluated last, and only where the occupancy question has already
been answered, so a wrong occupancy is always named by its own gate and a right
occupancy with a wrong lamp row is always named here.

```text
assert: TheDeckIsNotYoursToRearrange -- every frame: both boards' HandsToCall,
        SecondsBetweenArrivals, RosterCodes and SlatePositions are exactly what the
        fixture staged for the phase in progress (floats to 0.1%, arrays element-wise
        and in order); every board's, standing spot's and plate's location is within
        2 cm of where the deck put it; every standing spot's SpotNumber and BoardTag
        and every plate's BoardTag and bIsCallPlate are unchanged; and no extra board,
        standing spot or plate actor exists anywhere in the level. LOAD-BEARING, not
        ceremonial: the fixture's own model reads the boards' LIVE chalk, so without
        this a submission that rewrote a dial would make the model agree with whatever
        it did. The message names the property, what was staged and what was found.

assert: TheQuietBoardStaysQuiet -- THE IN-SCENE TWIN, at EVERY judged frame: the second
        board (identical class, its own six standing spots, its own six lamps, its own
        two plates, and its own chalk, never stepped on by the drive) has ZERO hands
        within 200 cm of any of its standing spots, every one of its lamps dark
        (intensity == 0), and not one code of its own roster displayed on any badge
        anywhere in the level. Catches a BeginPlay fill, a level-wide "any plate calls
        every board" hook, and a global singleton that ignores which board was
        triggered. The message names the twin's board name, the offending spot or lamp,
        and the code found.

assert: NobodyArrivesUncalled -- on every judged frame outside a call's fill window
        (before the first call, between a stand-down and the next call, through the 12 s
        hold, and at the sentinel): the total number of actors tagged CrewHand in the
        level has not risen since the previous judged frame, no badge code appears that
        was not already issued, and no hand exists whose XY is further than 120 cm from
        some standing spot. BOTH of those last two clauses are LEVEL-WIDE, and both are
        disclosed: the prompt's "nobody waits in the wings" paragraph states in as many
        words that a hand is in the world only while it is aboard and that there is
        never one anywhere that is not standing on a numbered spot. So a pool of hands
        parked off the deck, hidden or unbadged, is a hand that exists and was not
        called for, and it is named here on the phase-1 baseline. The value is in the
        prompt; only the gate's name is not. 120 cm, not 2 cm: the standing spots are 500 cm apart so it
        cannot confuse two of them and cannot mask any wrong answer, while 2 cm would
        fail a correct submission that nudges a hand for footing
        (craftbench-drive-manufactures-fails: widen only in the safe direction). The
        2 cm figure is kept where it is a DELTA on one actor -- NobodyShufflesAlongTheDeck
        -- and for the deck's own furniture. Catches a respawn-to-refill loop, a repeating timer that
        keeps calling, and a second call self-started by the character stepping off the
        plate. The message names the previous count, the current count and any new code.

assert: TheyArriveOneAfterAnother -- on plateau k of a call (the judged interval between
        the guard bands around expected arrivals k and k+1): exactly k of that call's
        hands are aboard the working board. Judged on both fps legs, so a frame-counted
        cadence fitted at 60 Hz fires at the wrong game time at 20 Hz. The message names
        the elapsed seconds since the plate contact, the board's LIVE arrival gap, the
        count expected and the count seen.

assert: TheDeckFillsToTheCalledNumber -- through a call's fill window: the set of
        occupied standing spots on the working board is exactly {the spots held over
        from earlier watches} union {the lowest-numbered spots that were free, one per
        arrival of this call so far} -- spots 1..6 by the end of watch 1, and precisely
        the vacated 2/4/5 by the end of watch 2 -- and the number aboard at the settle
        after the last expected arrival equals the number chalked at the moment the
        plate was stepped on, plus whoever was already standing there. The count of
        hands ANYWHERE in the level is held to the same number, which is the disclosed
        "nobody waits in the wings" clause; when that is what disagreed the message
        says so rather than printing two identical spot sets. THIS IS THE GATE
        AN EMPTY SUBMISSION FAILS FIRST. The message reads:
          "TheDeckFillsToTheCalledNumber: the board called for 6, 1 should be aboard
           2.75s after the plate, expected spots 1 and found none aboard"

assert: TheRightHandsAreLeftStanding -- at every judged frame of the settled window
        after each stand-down: the standing spots cleared by that stand-down are exactly
        the spots held by the hands whose ARRIVAL PLACES in the watch just called the
        board's slate named, and no hand from an earlier watch is missing. Watch 1
        (six called, slate {2,4,5}) must leave spots 1/3/6. Watch 2 (three called into
        the free spots 2/4/5, slate {1,3}) must clear spots 2 and 5 and leave 1/3/4/6.
        The arrival-order-to-spot map is the one the fixture OBSERVED, not one it
        assumed, so a submission is judged against its own fill. A hand counts as
        still aboard for as long as its actor exists in the world: dropping the
        `CrewHand` tag is not leaving the deck, so the fixture keeps such an actor on
        the spot it arrived on rather than forgetting it, and untag-and-hide is named
        here instead of silently freeing every spot on the board at once. A hand that
        has genuinely entered destruction is forgotten on the same frame, so a correct
        submission pays nothing for this. The message names the slate as read, the
        observed arrival-order-to-spot map, the spots it expected to be cleared, the
        spots actually cleared, and -- when they differ -- how many hands exist anywhere
        against how many should be left standing.

assert: NobodyShufflesAlongTheDeck -- at every judged frame, for every living hand: its
        XY is within 2 cm of the standing spot it took on arrival, and it is still on
        that same spot -- including across both stand-downs, when the spots either side
        of it empty. Kills any implementation that compacts the row, re-seats survivors,
        or re-parents them to a rebuilt list. The message names the badge code, the spot
        it arrived on and where it is now.

assert: TheSurvivorsKeepTheirOwnBadges -- at every judged frame from the first arrival:
        every living hand still DISPLAYS the exact badge code it was issued when it
        arrived; no two living hands display the same code; and across the WHOLE run no
        code from either board's roster is ever issued twice -- the fixture keeps the
        full issue ledger, so a second watch that restarts the roster is caught even
        though the duplicate's twin is still alive. AND THE ORDER, not merely the set:
        at the instant a hand's code is entered in the ledger, that code must equal the
        FIRST entry of the board's live roster the ledger does not already hold. This is
        the clause that makes "the numbers come from the board's roster, in the order the
        roster is written ... each hand taking the first number on the roster that has
        not been issued yet" a checked requirement rather than a stated one: membership
        plus uniqueness alone cannot tell a correct issue from an unspent pool popped
        from the wrong end, or one held in an unordered set and drained in hash order,
        and both of those are ordinary UE code. It is asserted against the arrival the
        fixture OBSERVED, so a wrong SEATING rule is still named by the fill gate and
        never by this one. The final frame's required badge map is therefore a joint
        function of both watches and is genuinely enforced: spot1=41, spot3=53,
        spot4=73, spot6=67. The message names the offending spot, the arrival place, the
        code it shows, the roster as read, which of its codes are already spent, and the
        code that was due.

assert: TheBoardShowsWhoIsAboard -- THE VISIBLE READOUT, graded so it is load-bearing:
        on the working board AND on the twin, the lamp for spot k is burning (its point
        light's intensity > 0) if and only if standing spot k is occupied. Read from the
        light, never from a flag. The message names the board, the spots occupied and
        the lamps found burning.

assert: TheDeckThinnedOutTwice -- run-level, at drive completion or the sentinel: the
        working board rose from empty to a full watch at least twice AND was thinned by
        a stand-down at least twice in between, with the second round judged by the same
        gates as the first. A one-shot latch can only do it once.
```

**Staging faults are attributed, not scored.** Any of these ends the run as
`HARNESS-PRECONDITION`, never as a model failure: wrong actor counts; a board, standing
spot or plate that does not expose its properties readably; a staged arrival gap below
the 2.0 s floor; a staged call for more hands than that board has free spots at that
moment; a staged slate entry greater than that watch's call, or less than 1; a staged
roster shorter than the total number of hands the night will ever call for; the two
boards' rosters overlapping each other or the committed map's; **a watch-1 schedule
short enough that phase 3's step-back onto the call plate would land at or after the end
of the fill** (see below); a drive phase that overruns its derived deadline; or the
character failing to reach a plate.

**Why that step-back clause is not bookkeeping.** The prompt draws a line the fixture
draws too: stepping on and off again *while a call is still running* starts no second
call — which means stepping on again once the watch is full legitimately **does**. The
fixture keeps its fill window open from the call plate's contact all the way to the next
stand-down, which is wider than "while a call is running", so a re-contact after the
fill had completed would judge a correct submission's fresh call against a model
expecting nobody new. It cannot happen on the staged schedule (the step-back is at 7.5 s
against a fill that runs to 12.0 s), and the constants that make it true are asserted
against the schedule at `PrepareTest` — because the step timings are constants and the
schedule is data, so shrinking watch 1 would otherwise cross that line silently and
manufacture a FAIL on a correct answer.

**A harness exit can never launder a FAIL.** Before any deadline or sentinel overrun is
written off as a staging fault, `TheDeckIsNotYoursToRearrange` and
`TheQuietBoardStaysQuiet` are re-checked **unconditionally** — a submission that moved a
plate or rewrote a dial could otherwise make a phase unreachable and be paid for it with
a non-graded exit.

## Requirement-to-assertion map

| Prompt requirement | Gate that checks it | When that gate does NOT run |
| --- | --- | --- |
| stepping on a board's call plate calls for hands | `TheDeckFillsToTheCalledNumber` | before the first plate contact |
| how many is the number chalked **at the moment the plate is stepped on** | `TheDeckFillsToTheCalledNumber` (the count clause), against the value staged for that phase | outside a fill window |
| they arrive **one at a time**, first at one gap, then one every gap | `TheyArriveOneAfterAnother`, on both fps legs | inside the guard bands, and until at least one of the call's hands is aboard (gate 5 owns that case) |
| the call runs to its number whether or not anyone is on the plate | the drive steps off mid-fill in phase 3; the same two gates keep asserting through it | never |
| stepping on and off again does not start a second call | `NobodyArrivesUncalled` (no extra hand appears after the call's last expected arrival) and `TheDeckFillsToTheCalledNumber` (the count would exceed the call) | never |
| **nobody turns up who was not called for** | `NobodyArrivesUncalled` | inside a fill window, where gate 4/5 own the count |
| each hand takes the **lowest-numbered free** spot | `TheDeckFillsToTheCalledNumber`, as a set, at every plateau and at the settle | outside a fill window |
| **a hand never moves again** | `NobodyShufflesAlongTheDeck`, every judged frame | before the first arrival |
| badges come from the roster, in written order, first unspent one first | `TheSurvivorsKeepTheirOwnBadges` (the issue-ORDER clause: at the moment a code enters the ledger it must equal the first roster entry the ledger does not already hold) | before the first arrival |
| **a number is spent once for the whole night** | `TheSurvivorsKeepTheirOwnBadges` (the whole-run ledger clause, which is why the roster is re-chalked LONGER rather than fresh) | as above |
| a lamp is lit exactly while its own spot is occupied | `TheBoardShowsWhoIsAboard`, on both boards | only on a frame where the armed occupancy gate already failed |
| the stand-down slate names **places in the arrival order of the watch just called** | `TheRightHandsAreLeftStanding` — and watch 2 is the leg that separates it from a spot-number reading, because watch 1's two readings coincide by construction | outside the settled window after a stand-down |
| earlier-watch hands are never sent ashore by it, and keep their badges | `TheRightHandsAreLeftStanding` (the no-earlier-watch-hand-missing clause) + `TheSurvivorsKeepTheirOwnBadges` | as above |
| a hand sent ashore leaves the deck and frees its spot | `TheRightHandsAreLeftStanding` + `TheDeckFillsToTheCalledNumber` on watch 2, which can only fill 2/4/5 if they were genuinely freed. Leaving means the actor is gone, not that it stopped answering: an actor that still exists keeps holding its spot | as above |
| **a hand is in the world only while it is aboard**, and there is never one anywhere that is not on a numbered spot | `NobodyArrivesUncalled` (the level-wide count, and the no-hand-off-a-spot clause) + the level-wide count clause of `TheDeckFillsToTheCalledNumber` and `TheRightHandsAreLeftStanding` | the count clause stands down inside a fill window, where gate 5 owns it |
| the chalk changes and must be read at the point of use | the whole schedule: watch 2 differs in all four values, and the committed map differs from both | never |
| **only the board whose plate was stepped on does anything** | `TheQuietBoardStaysQuiet`, at every judged frame | never |
| the deck settles within **half a second** | the 0.75 s settle and the 0.75 s guard-band floor, both 1.5x it | never |
| it is not one-shot | `TheDeckThinnedOutTwice` | judged at drive completion or the sentinel; a run that fails a per-frame gate earlier never reaches it, which is the more useful message |
| do not move anything or change anything chalked | `TheDeckIsNotYoursToRearrange`, every frame | never |
| C++ under `Source/ThirdPerson/` | sandbox: a file outside the writable set is exit 4, not a graded FAIL | never |

## Reference solution metadata

- **Files touched**: 2 —
  `Source/ThirdPerson/Tasks/t2-the-crew-arrives-and-thins-out/MusterBoardActor.h` and
  `.cpp`. The other three supplied pairs are byte-identical to the scaffold; the board
  is the host because everything on the deck is a placed instance in a map the agent
  cannot edit, so a brand new class would never be instantiated.
- **LOC**: ~230 added (about 70 of them comment), on top of the supplied board.
- **Senior-dev hours**: **3–5**, the middle of T2. The code is not large; the hours go
  into judgment, not typing:
  1. ~45 min on the fill: an edge-triggered latch that cannot re-arm mid-call, a clock
     that produces one arrival per chalked gap read live, and a lowest-free seat lookup
     over spots resolved by the board's own name.
  2. ~60 min on the removal rule. Recognising that the slate indexes the **arrival
     order** and not the spots is reading comprehension — the prompt says so — but the
     first implementation that comes to hand walks the slate over a live array and
     removes as it goes, and that is wrong in a way that compiles, reads correctly and
     sends the right *number* of hands ashore.
  3. ~45 min on identity: an issue ledger that survives the re-chalk, and the
     realisation that the re-chalked roster keeps the spent numbers, so "the first one
     on the roster" is not the same as "the first one not yet issued".
  4. ~45 min on the reading discipline and the two-board scoping: every chalked value
     read at the point of use, every piece of furniture matched by the board name it
     carries, and nothing done to the board nobody stepped on.
  5. ~45 min proving the second watch by hand — which spots come free, which arrival
     place lands on which of them, and which badge each survivor ends up wearing.
- **Why not T3**: no new subsystems, no assets, no editor work, no engine spelunking.
  It is one actor's worth of gameplay code that has to be exactly right in three
  interacting places.

## Anti-gaming notes

1. **Walking the slate over a live array and removing as you go.** *Failure mode*: the
   single most natural first implementation, and the owner's named wrong answer —
   `for (Place : Slate) { Crew[Place-1]->Destroy(); Crew.RemoveAt(Place-1); }`. The list
   shifts under the loop, so on watch 1 (slate {2,4,5}) it sends arrival places 2 and 5
   ashore and then either runs past the end or takes place 6, leaving spots 1/3/4/6
   instead of 1/3/6. It compiles, reads right at a glance and sends the right *number*
   of hands ashore, so every surface check passes. *Defense*:
   `TheRightHandsAreLeftStanding` on the **first** stand-down, whose message prints the
   slate as read, the observed arrival-order-to-spot map and the spots it expected to be
   cleared. The correct answers — iterate the slate descending, or resolve every place
   to a body before destroying any of them — are one thought away, which is the bar.
2. **Reading the slate as standing-spot numbers.** *Failure mode*: the coupling trap,
   and the thing that separates a frontier model that gets watch 1 right. On watch 1 the
   two readings are **identical** — the deck starts empty, so arrival place k lands on
   spot k — so this passes watch 1 completely. *Defense*: watch 2's three hands land on
   the vacated spots 2/4/5, so arrival place 1 is spot 2 and place 3 is spot 5; a slate
   of {1,3} therefore means clear spots 2 and 5, not 1 and 3.
   `TheRightHandsAreLeftStanding` FAILs on the second stand-down, and
   `TheSurvivorsKeepTheirOwnBadges` falls with it, because the final badge map
   (spot 4 must show 73) is a joint function of the fill order and the removal
   selection.
3. **Turning the whole watch up in one loop on the frame the plate is stepped on.**
   *Failure mode*: the cheapest way to satisfy a count. Every survivor, badge and lamp
   check then passes. *Defense*: `TheDeckFillsToTheCalledNumber` in the fill window's
   **first** judged window — roughly 0.75 s to 1.25 s after the plate, before the first
   arrival is due at all — where the model expects nobody aboard and finds the whole
   watch. Named by the fill gate and NOT by `TheyArriveOneAfterAnother`, which is
   deliberately disarmed while the expected count is still zero (§*Gate precedence*):
   "the watch is arriving at the wrong pace" is a statement about a watch that is
   arriving. The cadence gate owns the neighbouring answer — a fill that genuinely
   arrives one at a time but at the wrong interval, e.g. one paced off the gap cached at
   the first call, which dies on watch 2 because the gate reads the board's live gap
   rather than a constant. Both are judged on both fps legs.
4. **Restarting the roster from the top on the second call.** *Failure mode*: the
   obvious reading of "the numbers come from the board's roster, in the order the roster
   is written" once the mate has re-chalked it. *Defense*: the re-chalked roster KEEPS
   the spent numbers and appends three more, so restarting re-issues 41/47/53 — codes
   that watch-1 survivors are still visibly wearing. `TheSurvivorsKeepTheirOwnBadges`
   carries a whole-run issue ledger, not a per-watch uniqueness check, so both the live
   duplicate and the re-issue itself are named.
5. **Recycling the badges of the hands that went ashore.** *Failure mode*: a
   free-list, which is the *right* answer in most pooling code and the wrong one here.
   *Defense*: the same ledger clause. 47, 59 and 61 leave the deck at the first
   stand-down and must never appear again; the prompt says so in as many words ("not
   after the deck has emptied out").
6. **Reading the chalk once at `BeginPlay` and caching it.** *Failure mode*: the obvious
   optimisation. *Defense*: `BeginPlay` fires on placed actors **before** `PrepareTest`,
   and the committed map holds different values from the staged schedule, so a cached
   read is wrong from the FIRST call, not the second. All four values change again at
   the watch change.
7. **Doing it to every board, or to "the" board found by a level-wide search.**
   *Failure mode*: a singleton, or a plate that broadcasts. *Defense*:
   `TheQuietBoardStaysQuiet` is gauged at every judged frame — zero hands, every lamp
   dark, not one of its own roster codes anywhere — and the twin's chalk differs from
   the working board's, so a submission that grabbed the wrong board's numbers also
   trips the fill and cadence gates.
8. **Compacting the row, or re-seating survivors so the spots stay contiguous.**
   *Failure mode*: a tidy-up that reads as good housekeeping. *Defense*:
   `NobodyShufflesAlongTheDeck` pins every living hand to within 2 cm of the spot it
   arrived on, at every judged frame, and `TheRightHandsAreLeftStanding` would then find
   the wrong spots free.
9. **Modelling everything correctly and never touching a lamp or a badge.** *Failure
   mode*: getting the state right and forgetting the output. *Defense*: nothing private
   is ever graded. The fixture reads the point lights' intensity and the text on each
   badge; the board deliberately carries no "current watch" property for a submission to
   set and be credited for.
10. **Taking the badge from the wrong end of the unspent pool.** *Failure mode*: the
   obvious shape once a submission has built a working set of not-yet-issued codes —
   `TArray<int32> Avail; for (int32 C : RosterCodes) { if (!Spent.Contains(C)) Avail.Add(C); } Code = Avail.Pop();`
   — or, just as ordinary, holding the pool as a `TSet<int32>` and taking
   `*Set.CreateIterator()`, whose order is hash order and not roster order. Every
   surface property survives: every code is on the live roster, no two are worn at once
   and none is ever re-issued, so the ledger, the uniqueness clause and the membership
   clause are all green and the deck LOOKS right. *Defense*: the issue-ORDER clause of
   `TheSurvivorsKeepTheirOwnBadges` — at the instant a code enters the night's ledger it
   must equal the first entry of the board's live roster the ledger does not already
   hold. Fires on watch 1's FIRST arrival (67 where 41 was due), and the message prints
   the roster, the codes already spent and the code that was due. Added 2026-08-19 after
   an adversarial review found this gate checked the SET and not the ORDER while both
   `task.md` and the matrix claimed otherwise.
11. **Sending a hand ashore by making it stop answering rather than by destroying it.**
   *Failure mode*: `Hand->Tags.Remove(FName("CrewHand")); Hand->SetActorHiddenInGame(true);`
   — nobody moves, nobody is destroyed, and the one requirement whose only evidence is
   an actor's continued existence quietly evaporates. It is the single lever that turns
   every occupancy-derived gate off at once, because everything the fixture knows about
   who is aboard flows from that tag. *Defense*: the fixture forgets a tracked hand only
   when its actor is genuinely gone (invalid, or entered destruction). One that still
   exists keeps holding the spot it arrived on, so the stand-down gate reports the spots
   as still held and names the trick in its message. A correctly destroyed hand fails
   `IsValid` on the same frame, so this costs a correct submission nothing.

## Hidden invariants

- **The committed `.umap` is not the graded input.** All eight chalked values are
  re-stamped by `PrepareTest` before the character has walked anywhere, and re-stamped
  again at the watch change. Reading the map offline yields four numbers that are wrong
  on the first call.
- **The fixture's arrival-order-to-spot map is OBSERVED, never assumed.** A submission
  is judged against its own fill order, so `TheRightHandsAreLeftStanding` is a statement
  about the removal rule alone — which is precisely what makes the wrong seating rule
  fail at `TheDeckFillsToTheCalledNumber` and the wrong slate reading fail here, each
  named by its own gate.
- **The issue ledger spans the whole run and both watches, and it checks ORDER as well
  as membership.** It is never compared to the submission's own bookkeeping — a
  submission may represent the roster however it likes; only what is displayed over a
  hand's head is read. What is read is checked against the board's live roster IN
  WRITTEN ORDER at the instant each code is first seen, which is what makes the final
  badge map (spot 4 showing 73, not 71) an enforced joint function of the fill order and
  the removal selection rather than a claim.
- **Leaving the deck means the actor is gone.** A hand that stops answering to its own
  name while still standing there has not been sent ashore; the fixture keeps it on its
  spot. The prompt states the same contract from the other side — a hand is in the world
  only while it is aboard — so nothing is scored here that an agent cannot read.
- **The twin board's roster is disjoint from the working board's, and both are disjoint
  from the numbers the committed map holds.** Any badge code therefore names exactly
  which source produced it, which is what lets `TheQuietBoardStaysQuiet` assert "not one
  code of its own roster was issued to anything anywhere" rather than merely "the twin's
  spots are empty".
- **`fps_legs: [60, 20]` runs the whole drive twice**, in two PIE processes. A fill
  paced by counting ticks fires the arrivals at the wrong wall time at 20 Hz and
  diverges inside the first call.
- **The guard band has a floor, not just a ratio.** `max(0.75 s, 0.30 x gap)` plus a
  refusal to start below a 2.0 s gap keeps the band a widening of the disclosed half
  second at every staged cadence while leaving a judged plateau of at least ten frames
  on the 20 Hz leg. A pure ratio would have narrowed the disclosed contract at the
  shortest gap, which is a false FAIL, not a hard task.

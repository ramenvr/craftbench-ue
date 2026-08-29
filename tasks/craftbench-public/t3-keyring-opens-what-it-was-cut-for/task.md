---
id: t3-keyring-opens-what-it-was-cut-for
substrate: ThirdPerson
set: craftbench-public
tier: T3
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_KeyYard :: AKeyringFunctionalTest"]
---

# t3-keyring-opens-what-it-was-cut-for

Keys taken off stands in a walled yard each carry a category. Each bay opens only
for somebody standing at it who holds **every** category that bay asks for; a key
is never used up; an opened bay never shuts again — and the ring has to survive
the yard retiring the character mid-shift and wiping the readout board at the same
moment.

Five independent places to be subtly wrong, each of them wrong in a way that works
perfectly for the first half of the run: where the ring lives, whether a key is
spent when it is used, whether a bay is latched or polled, whether the demand is
all-of or any-of, and whether anything cached the character.

`deliverable_root`: `Source/ThirdPerson/` — see the first line of *Workspace state
pre-task*. The front-matter key of that name is **rejected by the parser**
(`tools/verify-single/spec.py::_KNOWN_KEYS`), so per the set's README the path is
stated twice in agent-visible prose instead: in the prompt block and in the first
line of *Workspace state pre-task*. Those two H2s are exactly
`tools/run-agent/prompt_extract.py::ALLOWED_SECTIONS`.

## Primary concept

- `subsystem-lifetime-and-ownership` — Programming Subsystems
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/programming-subsystems-in-unreal-engine)

The load-bearing question is **where state that outlives the pawn is allowed to
live, and what has to be re-resolved when the pawn changes**. The grade never asks
*how*: a world subsystem, a game-instance subsystem, the player controller, the
player state, a level-resident prop or a save slot all pass identically. What does
not pass is the character, and the run is built so that the difference only shows
up after eighty seconds of otherwise perfect behaviour.

## Composed concepts

- `overlap-and-proximity` — proximity resolved per prop against **that** prop's own
  radius, read off the prop, in both directions
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/collision-in-unreal-engine)
- `latching-state` — a door that opens once and is never re-evaluated, as against
  one driven from a per-frame predicate
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/gameplay-framework-in-unreal-engine)
- `pawn-possession-lifecycle` — the pawn is destroyed and the controller possesses a
  freshly spawned one; anything that cached the pawn is holding a stale pointer
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/player-controllers-in-unreal-engine)
- `in-world-readout` — an ordered list rendered into the level as text a person can
  read, which is also what the verifier reads
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/text-render-component-in-unreal-engine)

**Production pattern.** This is the ordinary shape of a *key/lock inventory* in an
immersive-sim or Metroidvania: keys are non-consumable capability flags, doors test
a required set against them, unlocked doors latch, and the flags live on a
run-scoped owner rather than on the avatar so death or a body swap does not
confiscate progress. Publicly documented instances: Epic's own Lyra keeps
match-scoped state on the game state / player state rather than the pawn
(https://dev.epicgames.com/documentation/en-us/unreal-engine/lyra-sample-game-in-unreal-engine),
and the engine's Common User / subsystem guidance is explicit that per-session state
belongs on a subsystem, not on an actor that can be destroyed
(https://dev.epicgames.com/documentation/en-us/unreal-engine/programming-subsystems-in-unreal-engine).

**How the concepts interact, and where a fix in one breaks another.** There is
exactly one place a first-pass fix genuinely fights itself, and it is the one this
task is built around. The board is wiped by the yard at the shift change and
nothing announces it, so the natural repair is "redraw the board from inside the
pickup handler" — which is correct for every pickup and leaves the board blank for
the whole second half, because no pickup happens at the swap. The natural repair
for *that* is "when the body changes, rebuild the yard from the ring" — which, done
literally, recomputes every bay from scratch for a body that has personally stood
at none of them and closes the ones the retired body opened, breaking *open is
forever*. Getting both right at once means separating three things that a first
pass tends to fuse: the ring (grows, never shrinks), the bays (latched, never
recomputed) and the board (a pure function of the ring, refreshed whenever the
board and the ring disagree).

## Prompt given to the agent

> The yard is a walled plaza. Down the middle of it stand six **bays** — a frame
> with a solid panel across it. Behind the last bay in the row there is a **walled
> corner**, and that bay is the only way into it; inside the corner stand one more
> bay and one more key stand. Along the south side stand two **key stands**, and
> three more stand away on the far side of the bay row. By the gate there is a
> **board**.
>
> Every key is cut for exactly one **category**, and that category is written on the
> key. Read it off the key: the yard re-cuts all six of its keys before you arrive,
> and the six names are never the same twice. Every bay is painted with the category
> it will open for, and exactly one bay is painted with **two** categories — it
> wants a key for each of them.
>
> Each stand and each bay has its own **mat** painted on the floor around it, and how
> far that mat reaches from the middle is written on the stand or bay it belongs to.
> Reach is measured **on the ground**, ignoring how tall anybody is. Stand mats and
> bay mats are not the same size, so read each one off the thing it belongs to.
>
> What has to happen:
>
> **Taking a key.** While the character the player controls is standing inside a
> stand's own mat, that stand's key goes onto the ring: it leaves the stand and the
> stand's lamp goes out. Standing there longer does not put the same key on the ring
> a second time. A stand nobody has stood at keeps its key — it is not yours until
> somebody walks to it.
>
> **The board.** The board shows what is on the ring: the categories, separated by
> commas, **in the order they were picked up**. An empty ring reads `--`.
>
> **Opening a bay.** While the character is standing inside a bay's own mat and the
> ring holds **every** category that bay is painted with, that bay opens and its
> panel slides aside. A bay painted with a category the ring does not hold stays
> shut. A bay nobody has stood at stays shut, whatever is on the ring.
>
> **A key is never used up.** A key opens every bay painted with its category —
> however many such bays there are, in whatever order you reach them, however many
> times you come back to one.
>
> **Open is forever.** A bay that has opened stays open: when the character walks off
> its mat, for the rest of the shift, and through the shift change below. Nothing
> shuts a bay again.
>
> **The shift change.** Part way through, the yard changes shift on you. The
> character you were driving is retired and a **fresh body** takes over at the gate,
> and at the same moment the board is **wiped blank**. The ring belongs to the shift,
> not to the body. After the change the board has to show the same ring again, every
> bay that was open has to still be open, and the yard has to keep working for the
> new body: it can still walk onto a stand and take a key, and the bay painted with
> two categories has to open once the ring holds both — even though one of those two
> keys was picked up by the body that is now gone.
>
> Everything has half a second to catch up after whatever it depends on changes.
>
> The props are supplied and working: a stand can hand its key over, a bay's panel
> can slide aside (which also takes the panel out of the way so a body can walk
> through the frame), and the board can be told what to show. Nothing in them decides
> *when* any of that should happen — that is the whole of the task. **The property
> names, the component tags and the numbers the yard wrote on those props are part of
> the contract**: leave them as they are, and add whatever you like on top. Where the
> props stand, and what they are painted with, is not yours to change: do not move,
> hide or destroy any of them, and open a bay by opening it rather than by getting
> its panel out of the way some other way. You may not add anything to the level —
> the props already standing in the yard are all there is. Do not edit the level, any
> config file, or any test file. Write your solution in C++ under
> `Source/ThirdPerson/`.

## Workspace state pre-task

**Deliverable root: `Source/ThirdPerson/`.** That is the agent-writable module on
this project; a file written under `Source/CraftBenchTemplate/` or under
`Source/CraftBenchTests/` is a SANDBOX-REJECT (exit 4), not a graded FAIL. So are
`Content/Maps/`, `Content/ThirdPerson/`, `Content/Characters/` and every `Config/`
file (no `config_allow` is declared by this task).

Files that **exist** under `Source/ThirdPerson/`:

- The stock UE 5.8 Third Person C++ template sources. No edit needed.
- `Tasks/t3-keyring-opens-what-it-was-cut-for/KeyringYardProps.h` / `.cpp` — three
  actor classes, all of them props with no decisions in them:

  | Class | Actor tag | What is supplied |
  |---|---|---|
  | `AKeyStandActor` | `Keyring_Stand` | A post, a key mesh floating over it (component tag `Key`), and a lamp lit while the key is still there. `UPROPERTY(EditAnywhere, BlueprintReadOnly) FName KeyCategory` — **what that one key is cut for**. `UPROPERTY float MatRadiusUu` — how far this stand's mat reaches. `UFUNCTION SetKeyTaken(bool)`, which hides the key mesh and puts the lamp out, and is **idempotent**. `UFUNCTION IsKeyTaken()`. |
  | `ADoorBayActor` | `Keyring_Bay` | A frame with two posts and a panel across it (component tag `Panel`, `BlockAll` while shut), plus a lamp that is red while shut and green once open. `UPROPERTY FName WantsCategory`, `UPROPERTY FName AlsoWantsCategory` (**`NAME_None` on six of the seven**), `UPROPERTY float MatRadiusUu`, `UPROPERTY float SlideUu`. `UFUNCTION SetOpen(bool)` slides the panel `SlideUu` along the frame's local X, **drops the panel's collision so a body can walk through the frame**, and swaps the lamp; it **sets** the panel's pose rather than nudging it, so calling it every frame is harmless. `UFUNCTION IsOpen()`. |
  | `ARingBoardActor` | `Keyring_Board` | A slab with an in-world text face (component tag `Sign`), shipping blank — it reads `--`. `UFUNCTION ShowRing(const TArray<FName>&)` joins what it is handed with `, ` and renders an empty array as `--`. It does **not** sort and does **not** de-duplicate: it shows exactly what it is handed. `UFUNCTION CurrentReadout()` returns whatever the face reads right now. |

  **None of the three ticks, has a timer, has an overlap handler, or holds any
  reference to the character.** The whole decision is the agent's, **and it has to
  land on these classes or on something that comes up with the world itself**: every
  prop is a placed instance in a map that cannot be edited, so a subclass would never
  be instantiated.

- `Content/Maps/t3-keyring-opens-what-it-was-cut-for/L_KeyYard.umap` — the staged
  yard, committed binary. World Settings name **no** game mode, so the level inherits
  `BP_ThirdPersonGameMode`. What is in it:

  | Element | Placement | Notes |
  |---|---|---|
  | Floor | 15,600 x 8,800, striped every 400 cm, stripes **non-colliding** | |
  | Six `ADoorBayActor`s | in one row down the middle, 1,800 cm apart | free-standing frames; you can walk between them |
  | One more `ADoorBayActor` | inside the walled corner behind the last bay in the row | |
  | Two `AKeyStandActor`s | on the south side | |
  | Three more `AKeyStandActor`s | away on the far side of the bay row | |
  | One more `AKeyStandActor` | inside the walled corner | |
  | Mats | one painted disc per prop, at **that prop's own** radius, non-colliding | stand mats and bay mats are visibly different sizes |
  | Walls | a perimeter fence, plus the walled corner whose only doorway is the last bay's frame | |
  | `PlayerStart` | exactly one, at the gate, on the lane the yard musters on | |
  | Board | one `ARingBoardActor` beside the gate | |
  | Fixture | one placed `AKeyringFunctionalTest` | |

  **The prop coordinates and the category assignment are deliberately NOT in this
  section.** They are readable in the level, on the props — and the categories are
  re-cut before any of them begins play, so a value copied out of the map is wrong by
  the time it matters.

- `cameras.json` (the camera-plan lane; not part of this release) — the
  presentation-only camera plan. Non-gating.

Files that **do not exist**:

- No ring, no proximity logic, no pickup handling, no bay logic, no board writes, no
  Blueprint subclass, no level edits. The empty submission compiles (L1 green) and
  FAILs L2 the first time the character stands on a key stand's mat.
- No test source in the agent's writable path. `AKeyringFunctionalTest` lives in the
  `CraftBenchTests` module the agent can neither read nor modify.

## Verifier specification

The test runs in PIE from
`Content/Maps/t3-keyring-opens-what-it-was-cut-for/L_KeyYard.umap` on the
**ThirdPerson** substrate, ticked at a fixed deterministic step
(`-deterministic -FPS=60`). Verification primitives: **pie-state-probe** (per-frame
readback of every prop's visible state) driven by the shipping per-frame
`AddMovementInput` walk, plus **pie-checkpoint-sampling** for the calibration log and
the sentinel.

**Where the gates live.** Dwells are 3.0 s with a 1.5 s settle floor, i.e. a 1.5 s
gradeable window — far shorter than any sane checkpoint period. **Every gate
therefore runs in `Tick`**: the continuous ones on every frame, the dwell ones on the
first frame past the settle floor at their own stop. `OnCheckpoint` does exactly two
things: it writes the calibration line, and at the **sentinel** — the last scheduled
checkpoint, far past the drive, because `ACraftBenchFunctionalTest` declares SUCCESS
the moment the last checkpoint is crossed — it evaluates the deferred whole-shift
assertions.

**The yard re-cuts itself before any `BeginPlay`.** From
`FWorldDelegates::OnWorldInitializedActors` (broadcast at the end of
`UWorld::InitializeActorsForPlay`, before `UWorld::BeginPlay` dispatches anything),
the fixture draws six distinct category names from a twelve-name pool using an
`FRandomStream`, writes them onto the six stands, and derives every bay's demand from
a **role table**, never from where the bay stands. The seed is logged
(`[t3-keyring recut] seed=…`) and can be pinned with `-KeyYardSeed=N` for
reproduction. **Prop positions never move**, so travel times and therefore the
discrimination stops are identical run to run; only the labels vary.

**The route is computed from the LIVE props, never written down.** Every bay stop is
0.65x that bay's own `MatRadiusUu` south of it; every stand stop is 0.50x that
stand's own `MatRadiusUu` on the side the drive comes from; transit runs along a lane
derived as `bay-row-Y − 2.4 x the widest bay mat`, and the way into the walled corner
is `0.7 x the widest bay mat` past the doorway. The muster mark is the PlayerStart
projected onto that lane.

**Readbacks are visible consequences, never flags.**

- `KeyTaken(stand)` = the key mesh is hidden in game **and** the lamp's intensity is
  0. A bool flipped without either changing reads *not taken* — and *not taken* is
  the safe direction, because only the accusing half of a gate fires on a stand that
  reads taken.
- `BayOpen(bay)` = the panel component's relative location has moved at least 0.9x
  `SlideUu` from the pose the fixture recorded **before any BeginPlay**. A flag set
  without the panel moving reads shut; so does a hidden panel, a re-collided panel
  and a panel slid back. Anything short of a full slide reads *shut*, which is again
  the safe direction: a submission part-way through its own animation is judged 1.5 s
  into a 3.0 s stand.
- `Board` = the text face's `Text`, trimmed, split on commas, each token trimmed, and
  compared case-insensitively. `--` and an empty face both read as an empty ring.

**Two models of "has been near", and why they are different numbers.** The fixture's
own ring is built from the **strict** model — the character inside a stand's actual
`MatRadiusUu` — and that is what every positive gate and the board comparison use.
Every *accusing* gate instead uses a **generous** model at 1.5x the prop's own
radius, so a submission whose reach is slightly wide is never failed for being early.
`PrepareTest` refuses to start unless the route keeps **2.0x** clear of every prop it
has not yet stood on, at stops *and* at 48 sampled points along every leg — one
number for the route, one for the gate, and 2.0 > 1.5 so no accusing gate is vacuous.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64
        Development" and "ThirdPerson Win64 Development"
```

### L2 — AFunctionalTest behavioral trace

The drive walks nineteen stops, standing 3.0 s at each (4.0 s at the two shift-change
stops) and grading 1.5 s in — three times the half-second the prompt discloses.

```text
STOPS (all positions derived from the live props):
  1  MUSTER, at the gate            board reads '--'; nothing open; nothing taken
  2  BAY 1 mat, ring empty          shut
  3  STAND I  -> take key A         key gone + lamp dark; board reads 'A'
  4  BAY 1 mat                      OPEN
  5  BAY 2 mat (also wants A)       OPEN -- the key was not spent on bay 1
  6  BAY 3 mat (wants Z)            shut -- Z is on a stand nobody visits
  7  STAND II -> take key B         key gone; board reads 'A, B' IN PICKUP ORDER
  8  BAY 4 mat (wants B)            OPEN
  9  RELIEF MARK, 4.0 s dwell       at the END of the dwell, THE SHIFT CHANGE:
                                    (a) the fixture writes '--' straight onto the
                                        text face -- no agent-facing call, so no
                                        refresh can be clobbered by it;
                                    (b) PC->GetPawn()->Destroy();
                                    (c) GameMode->RestartPlayerAtTransform(PC,
                                        the PlayerStart's transform).
                                    Then it waits up to 5 s for a NEW character on
                                    the controller; no new body is HARNESS.
 10  MUSTER, 4.0 s dwell            board reads 'A, B' again
 11  BAY 5 mat (wants A AND C)      shut -- the ring holds A, not C
 12  BAY 6 mat (wants B; never      OPEN, for a body that never touched that key
     opened before the swap)
     ...then straight THROUGH bay 6's frame into the walled corner
 13  BAY 7 mat (wants C)            shut -- C is not held yet
 14  STAND III -> take key C        key gone; board reads 'A, B, C'
 15  BAY 7 mat                      OPEN
     ...back out through bay 6
 16  BAY 5 mat                      OPEN -- A from the retired body, C from the new
 17  BAY 3 mat                      still shut, long after everything
 18  BAY 1 mat                      still open, ~150 s and one body later
 19  MUSTER                         board reads 'A, B, C'
 SENTINEL (t = clamp(1.6 x the measured drive + 30 s, 300 s, 420 s))

CONTINUOUS, every frame:

assert: ADoorThatOpenedStaysOpen -- once a bay has read open it may never read
        shut again, through walking off its mat, through the rest of the drive
        and across the shift change
        -> "bay N opened at t=X and its panel is back across the frame at t=Y --
            expected a bay that opened to stay open, found it shut again"

assert: ADoorAnswersOnlyToTheKeysItAsksFor (accusing half) -- no bay may read
        open unless (a) EVERY category it is painted with is in the generous
        held-model and (b) somebody has been within 1.5x its own mat radius
        -> "bay N is painted with 'C' and the shift has not been to the stand
            that carries it -- expected this bay shut, found it open"
        -> "bay N is open and nobody has stood anywhere near its mat --
            expected a bay nobody has stood at to stay shut, found it open"

assert: OnlyTheKeysYouWentToAreGone (accusing half) -- a stand may not read its
        key taken unless somebody has been within 1.5x THAT stand's own mat
        radius; the three far stands are never within 2,000 uu of any route point
        -> "stand N is empty and nobody has walked anywhere near its mat --
            expected a stand nobody has stood at to keep its key, found it gone"

assert: TheYardStagedThisAndItIsNotYoursToChange -- every prop still exists, is
        still within 2 uu of where the yard staged it, still exposes its
        readouts, and no panel has travelled more than 1.3x its own SlideUu
        (bounded ABOVE as well as below, so a panel driven by an accumulating
        nudge is named here instead of vanishing out of the level and failing
        somewhere unreadable)

AT A SETTLED DWELL (1.5 s into the stand):

assert: TheBoardShowsWhatIsOnTheRing        stops 1, 3, 7, 19
        -> "expected %d category name(s) on the board, found %d"
        -> "expected the categories in pickup order, found another order"
assert: OnlyTheKeysYouWentToAreGone         stops 3, 7 (positive half)
        -> "expected 1 key gone from that stand, found 0"
assert: ADoorAnswersOnlyToTheKeysItAsksFor  stops 2, 6, 11, 13, 17 (shut half)
                                            stops 4, 8, 15 (open half)
        -> "expected this bay shut, found it open" / "expected this bay open,
            found it shut"
assert: AKeyOpensEveryDoorItWasCutFor       stop 5
        -> "'A' already opened bay 1 and bay 2 is painted with it too --
            expected this bay open too, found it shut"
assert: TheRingOutlivesTheBody              stops 10, 12
        -> "expected the ring back on the board after the change, found none"
        -> "expected this bay open for the fresh body, found it shut"
assert: TheNewBodyPicksUpWhereTheOldOneLeftOff   stops 14, 16
        -> "expected that stand's key on the ring, found it still on the stand"
        -> "the fresh body picked one up, found %d of them"
        -> "expected the bay that asks for two to open, found it shut"

Every anchor above is a CONTIGUOUS span of ONE source string literal with no
format placeholder inside it, checked against the fixture source after the
last edit. The messages are wrapped for that constraint first and for line
length second, which is why a few source lines run long.

AT THE SENTINEL:

assert: TheYardRanTheWholeShift -- the drive reached stop 19, the shift change
        really produced a NEW character object distinct from the retired one,
        and every prop is still present and still staged to 2 uu
        -> "expected the whole shift walked, found it stopped short"

WATCHDOG (per leg, 3x the straight-line walking time plus 25 s), SPLIT by cause:
        if a bay's shut panel is across the leg the drive is stuck on ->
        GRADED FAIL "expected a bay that opened to let the shift through, found
        it shut"; otherwise HARNESS-PRECONDITION, because a character snagged on
        level geometry is the yard's fault and not the model's.
```

**Every gate is a premise-checked gate.** Each dwell gate first asserts the state the
fixture itself built — that the ring really does (or really does not) hold what the
stop assumes, that the bay it calls "the second of its kind" really does have an
earlier bay of that key open, that the far bay really is holding one key from each
side of the shift change. If any of those is false the drive is not walking the route
the gate was written for, and the run ends as `HARNESS-PRECONDITION`, never as a model
failure. A negative result is worth exactly what the state behind it is worth.

**Staging faults versus behaviour faults, and why the split matters.** A prop
**missing from the level** is `HARNESS-PRECONDITION` (attributed, unscored) — the map
is not the agent's to edit, so its absence can only be the yard's own doing. A prop
**present but no longer carrying the contract** — a renamed or retyped
`KeyCategory` / `WantsCategory` / `AlsoWantsCategory` / `MatRadiusUu` / `SlideUu`, a
stripped `Key` / `Panel` / `Sign` component tag, or a mat radius or slide the agent
has changed — is a **graded FAIL** through
`ThePropsStillCarryWhatTheYardWroteOnThem`. The prop classes live in the
agent-writable module; routing an agent edit to a non-graded verdict would hand every
submission a way out of the denominator that needs no correct code at all.

**Other preconditions asserted at `PrepareTest`, all unscored:** exactly six stands,
seven bays and one board; six *distinct* categories; exactly one bay with a second
category; at least one bay asking for a category no visited stand carries; **exactly
one `APlayerStart`** (`ChoosePlayerStart_Implementation` picks with `FMath::RandRange`
among unoccupied starts, so a second start would move the fresh body on some runs and
change every downstream travel time); a game mode with a `DefaultPawnClass`; the
classification of the yard into six row bays plus one corner bay, two south stands
plus one corner stand plus three far stands, being unambiguous; and the whole
geometry audit below.

**The geometry audit, and why it exists.** `ACharacter`'s capsule is
`InitCapsuleSize(42, 96)`, so `GetActorLocation()` sits 96 uu above the floor and the
most natural line anybody writes — `FVector::Dist(Character, Prop) <= MatRadiusUu` —
reads 96 uu longer than the flat distance. `PrepareTest` therefore refuses to start
unless, for every stop, the WORST point the drive is allowed to settle at
(stop + a 45 uu arrival tolerance) is inside **0.75x** of the target's radius under
**both** the 2D and the 3D reading, and unless the arrival tolerance is at most 0.15x
of that radius. With the shipped mats (stands 400 uu, bays 760 uu) the worst 3D
readings are 263 uu against 300 and 547 uu against 570. It also refuses unless a bay
stop stands further out than a *stand* mat is wide, so a submission that reads one
prop's number and uses it on the other kind is caught by a bay that will not open
rather than passing by luck.

## Requirement-to-assertion map

| Prompt requirement | Assertion | Fires at | Skipped when |
|---|---|---|---|
| standing inside a stand's own mat puts that key on the ring | `OnlyTheKeysYouWentToAreGone` (positive) | stops 3, 7 | never — the drive always reaches stop 3 |
| standing longer does not add it twice | `TheBoardShowsWhatIsOnTheRing` count clause | stops 3, 7, 19 | never |
| a stand nobody stood at keeps its key | `OnlyTheKeysYouWentToAreGone` (accusing) | every frame | never |
| the board shows the ring, comma-separated, in pickup order | `TheBoardShowsWhatIsOnTheRing` | stops 1, 3, 7, 19 | never |
| an empty ring reads `--` | `TheBoardShowsWhatIsOnTheRing` | stop 1 | never |
| a bay opens for somebody standing at it holding **every** category | `ADoorAnswersOnlyToTheKeysItAsksFor` (open half) | stops 4, 8, 15 | never |
| a bay asking for a category the ring lacks stays shut | same gate (shut half) | stops 2, 6, 11, 13, 17 | never |
| a bay nobody has stood at stays shut | same gate, clause (b) | every frame | never |
| a key is never used up | `AKeyOpensEveryDoorItWasCutFor` | stop 5 | never |
| open is forever | `ADoorThatOpenedStaysOpen` | every frame + stop 18 | never |
| the ring belongs to the shift, not the body | `TheRingOutlivesTheBody` | stops 10, 12 | only if the swap produced no fresh body (HARNESS) |
| the board shows the same ring after the wipe | `TheRingOutlivesTheBody` (a) | stop 10 | as above |
| the yard keeps working for the new body | `TheNewBodyPicksUpWhereTheOldOneLeftOff` | stops 14, 15, 16 | as above |
| the two-category bay opens on one key from each side | `TheNewBodyPicksUpWhereTheOldOneLeftOff` | stop 16 | as above |
| do not move, hide or destroy a prop | `TheYardStagedThisAndItIsNotYoursToChange` | every frame | never |
| open a bay by opening it | panel-displacement readback + the >1.3x over-travel bound | every frame | never |
| keep the supplied names, tags and numbers | `ThePropsStillCarryWhatTheYardWroteOnThem` | `PrepareTest` | never |
| half a second to catch up | every dwell gate is sampled at 1.5 s, 3x the budget | all dwell stops | never |

**Constant denominator.** The L2 verdict is a single all-or-nothing
`AFunctionalTest` outcome with no k/N partial score, so no submission can improve a
ratio by making a check unreachable; and the sentinel independently refuses a run
that stopped short of stop 19, so an early exit cannot be traded for a clean verdict.

## Reference solution metadata

- LOC range: 150–230 (a ring store that outlives the pawn; per-stand proximity
  against that stand's own radius with a once-only guard; per-bay proximity with an
  all-of check over two category slots and a latch; a board refresh driven from the
  ring and re-driven whenever the board disagrees with it; and nothing anywhere that
  caches the character)
- Files touched: 2 new (`KeyringShiftSubsystem.{h,cpp}`), 0 edits to the three
  supplied prop classes — the committed reference changes nothing the yard supplied
- Senior-dev hours: **6–10**, honestly. Roughly 1 h reading the three prop classes,
  the mats and the yard to work out what is actually being asked; 1.5 h choosing and
  wiring a ring store that outlives the pawn and threading it through three prop
  classes that must not know about each other; 1 h pickup; 1.5 h bays (per-bay reach,
  all-of over two slots, latch-once, and getting "nobody has stood here yet" right);
  0.5 h the board including the second refresh path; 1 h making nothing cache the
  pawn; then 2–4 h of iteration, which is where the subtle bugs actually get found.
  **The iteration term is not portable across arms** — `claude-p` has no editor and
  pays none of it — so the tier is claimed on VOLUME and on the number of independent
  places to be wrong, not on the round-trip cost. Nothing here is obscure: every API
  involved is first-year UE.

## Anti-gaming notes

1. **The ring lives on the character.** *Failure mode*: the obvious domain model —
   "the character carries the keys". *Defense*: the yard retires that body at stop 9
   and `TheRingOutlivesTheBody` reads a blank board at stop 10 and a shut bay at
   stop 12. This is the entry an ordinary, competent first pass most often earns.
2. **Something caches the character in `BeginPlay`.** *Failure mode*: a level-side
   manager (or a prop) that stores `UGameplayStatics::GetPlayerCharacter(this, 0)`
   once and never re-resolves — a completely ordinary structure that works perfectly
   for the whole first half and then goes silently dead. *Defense*:
   `TheNewBodyPicksUpWhereTheOldOneLeftOff` at stop 14, where the fresh body stands on
   stand III's mat and nothing happens.
3. **The key is consumed by the first bay it opens.** *Failure mode*: the ring
   modelled as a pool of spendable keys (`Ring.Remove(Cat); Bay->SetOpen(true);`), or
   a per-key `bUsed`. *Defense*: `AKeyOpensEveryDoorItWasCutFor` at stop 5, which is
   deliberately the very next bay after the first one opens and comes **before** the
   board is next sampled, so the bug fails at its own literal instead of showing up as
   a board mismatch.
4. **A bay driven from a per-frame predicate.** *Failure mode*:
   `Bay->SetOpen(SomebodyOnTheMatCarriesIt())` every tick, or an overlap begin/end
   pair — the shape polling naturally takes. *Defense*: `ADoorThatOpenedStaysOpen`
   runs every frame and fires about a second after stop 4, when the character walks
   off. The same gate catches the second-order version: recomputing every bay from
   scratch when the fresh body takes over.
5. **`ContainsAny` instead of `ContainsAll` on the two-category bay.** *Failure mode*:
   a one-word slip that reads correct. *Defense*: stop 11 stands on that bay's mat
   holding exactly one of its two categories; the accusing half of
   `ADoorAnswersOnlyToTheKeysItAsksFor` also runs every frame, so there is no interval
   between samples to hide in.
6. **The board written with only the key just picked up.** *Failure mode*:
   `ShowRing({JustPickedUp})` inside the pickup handler. *Defense*:
   `TheBoardShowsWhatIsOnTheRing` at stop 7, where the board reads one category and
   the ring holds two — `expected 2 category name(s) on the board, found 1`.
7. **The board refreshed only from inside the pickup handler.** *Failure mode*: the
   ring survives the swap perfectly and the board never redraws, because no pickup
   happens at the swap. *Defense*: `TheRingOutlivesTheBody` at stop 10. This is the
   entry that makes the task interact rather than merely accumulate: the obvious fix
   for it breaks *open is forever*, and vice versa.
8. **No once-only guard on pickup.** *Failure mode*: the category is appended on every
   frame the character is inside the mat. The supplied board neither sorts nor
   de-duplicates, so the face reads `Copper, Copper, Copper, …`. *Defense*:
   `TheBoardShowsWhatIsOnTheRing` at stop 3 — `expected 1 category name(s) on the
   board, found <however many frames the character stood there>`, since the fixture
   expects one and the board is showing hundreds.
9. **Opening a bay by hiding, destroying or teleporting the panel.** *Failure mode*:
   getting the panel out of the way instead of opening the bay — which the prompt
   forbids in as many words. *Defense*: open is read as the panel's displacement from
   the pose recorded before any `BeginPlay`, bounded **both** ways; a hidden or
   re-collided panel reads shut; a destroyed panel or a moved prop is named by
   `TheYardStagedThisAndItIsNotYoursToChange`; and the walled corner is only reachable
   through a bay whose collision has actually been dropped.
10. **Any hard-coded category name, ordering, or canned board string.** *Failure
    mode*: reading the map once and baking the answer. *Defense*: the yard re-cuts all
    six categories from a seeded shuffle of a twelve-name pool **before any actor's
    `BeginPlay`**, and every bay's demand is derived from that re-cut. Nothing that
    could be copied out of the committed map is still true at run time.
11. **Renaming a property or stripping a component tag to leave the denominator.**
    *Failure mode*: the prop classes are agent-writable, so an edit there could turn a
    run non-graded. *Defense*: prop **missing from the level** is HARNESS; prop
    **present but no longer carrying the contract** is a graded FAIL through
    `ThePropsStillCarryWhatTheYardWroteOnThem`, and the prompt says the names, tags and
    numbers are part of the contract.

**One honest hole, stated rather than papered over.** A submission that reads a
*bay's* `MatRadiusUu` and uses it as the *stand's* reach is **not caught**. It would
widen every stand's reach from 400 uu to 760 uu, and the route never brings the
character between 400 and 760 uu of a stand it is not visiting — the three far stands
are 1,400 uu clear of everything, and the generous accusing model at 600 uu would
shield anything closer anyway. Building a stop into that 160 uu band would put a
correct answer within one drive wobble of a false FAIL, which the repo has been bitten
by before, so the hole is left open deliberately. The *reverse* mistake — using a
stand's number on a bay — **is** caught: bay stops stand 494 uu out, further than a
stand mat is wide, and `PrepareTest` refuses to run a yard where that stops being
true.

## Hidden invariants

- **Every number the grade compares a submission against is disclosed**: the mat
  radii are on the props and the prompt says twice to read them off, the categories
  are on the keys, the half-second settle budget is in the prompt, and the two
  category slots are on the bay. The numbers that are fixture-side are **all
  leniency** — the 0.65x/0.50x stop factors, the 45 uu arrival tolerance, the 1.5x
  generous accusing model, the 1.5 s settle floor against a disclosed 0.5 s, and the
  0.9x-of-a-slide open threshold. Each can only ever make a correct submission pass
  more easily. What is otherwise hidden is *when* and *where*: the nineteen stops,
  the lane, and which stand's category the never-visited bay is painted with.
- **The re-cut lands before any `BeginPlay`.** An agent that reads a key's category
  once in `BeginPlay` reads the final value and is never punished for not re-reading.
  The randomisation exists to defeat a baked answer, not to require a subscription.
- **The two "has been near" models are deliberately different numbers.** The strict
  model (1.0x) builds the fixture's own ring; the generous model (1.5x) is the only
  thing an accusing gate is allowed to use. The route is held 2.0x clear of anything
  it has not reached, so the accusing gates have 0.5x of daylight and none of them is
  vacuous — the number the route guarantees and the number the gate accuses at are
  written down together in the fixture, for exactly the reason they must never drift.
- **The shift change is ordered blank-then-swap, deliberately.** The board is wiped
  *before* the pawn is destroyed, so no refresh a submission performs can be
  overwritten by the yard's own wipe, and a submission that never redraws has nowhere
  to hide.
- **The fixture never calls an agent-facing function.** It writes `--` straight onto
  the text component and reads the panel's relative location, the key mesh's
  hidden-in-game bit and the lamp's intensity. `SetKeyTaken`, `SetOpen` and `ShowRing`
  are the agent's to call; the grade only ever observes what they did.
- **The only route through the walled corner is a bay whose collision actually
  dropped.** That makes *open* physically load-bearing rather than merely readable: a
  body has to pass through the frame. If it does not, the watchdog names the bay and
  the failure is graded; if no shut panel is on the blocked leg, the same watchdog
  reports a HARNESS fault instead, because a character snagged on level geometry is
  the yard's problem and not the model's.

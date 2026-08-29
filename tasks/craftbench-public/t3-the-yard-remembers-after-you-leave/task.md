---
id: t3-the-yard-remembers-after-you-leave
substrate: ThirdPerson
set: craftbench-public
tier: T3
capability_bucket: Architecture & Systems
category: gameplay
layers: [L1, L2]
fixtures: ["L_MemoryYard :: AMemoryYardFunctionalTest"]
randomization: [staged-worths, staged-day-shape, prop-slots]
---

# t3-the-yard-remembers-after-you-leave

A walled yard of five numbered posts, three lamp-marked pads and a counter board.
Walking into a post takes it and banks the number it was showing; standing on a
pad moves the burning lamp. Walk out of the gate and the whole yard is carried
away and rebuilt **brand new, with the posts renumbered and everything moved**,
and it has to come back knowing exactly what was taken, exactly what was banked
and exactly which pad the runner was marked on. That happens **three times in
every run**, and each time something different has happened to the written record
while the yard was shut: once **nothing**; once the record has been **put back the
way it stood earlier in the day**, so the yard has to reopen on a state it has
long since walked past; and once it has been **thrown away**, so the yard has to
open as if it had never been visited. Which of the three comes first, second and
third **is not the same from run to run**. A far yard across the wall is torn down
and rebuilt with it and must come back untouched.

> **Built against the 2026-08-18 difficulty bar.** Two subsystems that genuinely
> interact — what gets written into the record, and what the yard is allowed to
> re-derive when it opens — and getting either one right while getting the other
> wrong fails a *named* gate. Two locally-reasonable wrong answers, both written
> down explicitly: **(a)** keep the yard's state in something that outlives the
> props, write a save file too, and restore from the warm copy because it is right
> there — dies on `ColdReopenForgetsEverything`; **(b)** the same thing one step
> more careful — keep the state warm but *clear it whenever the record is missing*,
> so the file is a token and memory is the truth — which passes every gate about
> the record's *presence* and dies on `PutBackRecordRulesTheYard`, because putting
> the earlier bytes back changes the record's **content** without changing whether
> it exists, and only a yard that reads what is written can follow it backwards.
> The load-bearing numbers are read off the world and **restaged three times inside
> every run**, and which staged day runs is taken **from the clock**, so a total
> recomputed from the posts, a number copied out of this file, and a count of how
> many times the yard has been rebuilt are all wrong.
>
> This is the deliberate complement of the shipped `t2-shop-takes-your-coins-and-
> remembers`, whose spec says outright that a save slot, a game-instance
> subsystem, a world subsystem or a file all pass identically. This is the one
> place in the tree where they do not, because the record is taken away — and,
> once, quietly rewound — mid-run.

## Primary concept

- `saving-and-loading-your-game` — Saving and Loading Your Game
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/saving-and-loading-your-game-in-unreal-engine)

The load-bearing behaviour is **making a durable record the actual source of
truth, not a copy of one** — deciding what belongs in it (identities *and*
amounts, never a count and never a sum that can be recomputed), writing it
somewhere that outlives both the props and any object standing beside them, and
re-deriving the whole yard from it every time the yard opens, such that deleting
it genuinely returns the yard to its never-visited state. The grade never asks
*how* the file is written, and never opens it.

## Composed concepts

- `actor-lifecycle` — a fresh actor spawned into a world that has already begun
  play, and what its `BeginPlay` can and cannot know
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-actor-lifecycle)
- `collision-overview` — trigger volumes that notice a walking character, and
  what happens when the walker comes back a second time
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/collision-in-unreal-engine---overview)
- `programming-subsystems` — somewhere for the coordination to live that outlives
  the props, without becoming the memory itself
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/programming-subsystems-in-unreal-engine)
- `ps-strings` — the readouts a person actually reads, and what is graded
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/string-handling-in-unreal-engine)

The production pattern is the ordinary one Epic's own save-game guide describes
and that every shipped checkpoint/autosave feature reproduces: a level's
collectable state and the player's resume point are persisted to a slot,
re-applied to freshly streamed-in actors, and a deleted or absent slot yields a
new game rather than a corrupt one. Nothing here is invented — what is measured
is whether the four pieces agree with each other when the slot goes away.

## Prompt given to the agent

> **Deliverable root: `Source/ThirdPerson/`.** Write your solution in C++ under
> `Source/ThirdPerson/`. Do not edit any level, any config file, or any test file.
>
> The near yard has five posts standing on the floor and three pads set into it.
> Every post carries a whole number between **3 and 17** painted above it — what
> that post is worth — with its own name beside the number. A counter board by the
> gate shows one number: everything banked in that yard so far. In a yard nobody
> has ever visited it reads **0**.
>
> Walking into a post takes it. A taken post is gone from the yard — the pillar and
> its number both, and a person can walk straight over the patch of ground it stood
> on — and the counter board rises by exactly the number that post was showing at
> the moment it was taken. That is what was banked, and nothing that happens to that
> post's number afterwards changes it. A post that is already gone is worth nothing
> at all: walking back through the ground it stood on must not move the counter
> board.
>
> The three pads are the runner's marks. Each pad has a lamp, and a number painted
> on it saying whether it is the first, the second or the third. Exactly one lamp in
> the yard is burning at any moment: the one on the pad most recently stood on.
> Before anybody has stood on a pad, the burning lamp is the first pad's.
>
> Walk out through the gate and the yard shuts behind you: the posts, the pads and
> the counter board are all carried away. Walk back in and the yard opens again, and
> what opens is brand new — new posts, new pads, a new board, new numbers painted
> over the posts, all of it standing somewhere different, and none of it knowing
> anything about the day you have had. This happens **three times** in a day. The
> yard shuts and reopens by itself; that part is not yours to build. Within **one
> second** of each opening, all three of these have to be true:
>
> - exactly the posts the day says are gone are gone again, and the rest are
>   standing and takeable;
> - the counter board reads the total that was banked — **not** the sum of the new
>   numbers now painted over those posts;
> - the runner is standing within **150 cm** of the pad the day says the mark is on,
>   that pad's lamp is burning, and the other two are dark.
>
> From there the yard carries on exactly as before: taking a standing post banks the
> number **now** painted over it, and standing on another pad moves the burning lamp
> to that pad.
>
> What "the day says" means is the next paragraph, and it is not always the day you
> just had.
>
> Because the yard itself is carried away, the yard's memory cannot live in it.
> Write it down on disk, in the folder the project keeps its saved games in.
>
> Three things happen to that written record while the yard is shut, one at each of
> the three openings, and you are told all three.
>
> - **Some days nothing at all is done to it**, and the yard comes back exactly as
>   it stood when you walked out.
> - **Some days it is thrown away.** When the yard opens and the record is gone,
>   the yard opens **as if it had never been visited**: all five posts standing,
>   the counter board reading 0, and the runner standing within **150 cm** of the
>   first pad with only that pad's lamp burning. The yard is live again from there,
>   so taking a post banks the number now painted over it exactly as on the first
>   day.
> - **Some days it is put back the way it stood earlier.** A copy of the written
>   record is taken a moment after the counter board first rises — so keep the
>   record up to date as the day goes, not only when the yard shuts — and on some
>   days that copy is put back in its place while the yard is shut. When the yard
>   then opens, it opens on exactly what that copy says and on nothing else: only
>   the post that had been taken by then is gone and the other four are standing
>   and takeable, the counter board reads only what had been banked by then, and
>   the runner stands within **150 cm** of the pad whose lamp was burning at that
>   moment with only that lamp lit — no matter how much more was taken, banked or
>   stood on afterwards. The yard is live from there too.
>
> Each of the three happens exactly once in a day, and **which one comes first,
> second and third changes from day to day** — so read the record rather than
> counting the openings.
>
> Across the wall there is a far yard: three more posts and a counter board of its
> own. It is a separate yard. Nothing done in the near yard belongs to it — its
> board reads 0 and all three of its posts stand until somebody walks into them —
> and it is carried away and put back together with the near yard just the same.
>
> The five posts, the three pads and the two counter boards are the yard's own, and
> the yard always has exactly those: never add one, never take one out of the world,
> never rename one. A post that has been taken is still one of the yard's five — it
> is simply not standing any more, and the patch of ground it stood on is still
> there to walk over.
>
> Each post carries its own name, its own number and the yard it belongs to; each
> pad carries its own name, its place in the order and its yard; each board carries
> its yard. Read them off the thing you are actually dealing with. The five posts
> are not set alike, and the yard repaints its numbers and moves everything about
> every time it opens, so where something stands says nothing about which one it is.
>
> The counter boards, the numbers over the posts, whether a post is standing, and
> the pad lamps are the yard's own displays, and the calls that write them are
> supplied and working: hand them your numbers and leave their wording alone.
> Everything that is judged is something a person standing in the yard can read off
> a board, a painted number, a lamp or an empty patch of ground.
>
> Keep the runner walkable throughout — do not disable input, do not take the
> controls away, do not stop them moving — apart from setting them down on the pad
> the yard puts them back on.

## Workspace state pre-task

**Deliverable root: `Source/ThirdPerson/`** (the agent-writable runtime module on
this substrate). `Source/CraftBenchTests/` is deny-listed and a submission file
under it is a SANDBOX-REJECT (exit 4), not a graded FAIL; so are `Content/Maps/`,
`Content/ThirdPerson/`, `Content/Characters/`, `Content/Input/`,
`Content/LevelPrototyping/`, `Plugins/` and every `Config/` file (no
`config_allow` is declared by this task).

Files that **exist** under `Source/ThirdPerson/`:

- The stock UE 5.8 Third Person C++ template sources. No edit needed, though
  `AThirdPersonCharacter` is writable if a solution wants to live there.
- `Tasks/t3-the-yard-remembers-after-you-leave/MemoryPostActor.h` / `.cpp` —
  `class THIRDPERSON_API AMemoryPostActor : public AActor`, tagged `MemoryPost`.
  The actor's origin sits **on the floor** and its root is a bare, unscaled scene
  component, so every size below is the size it says it is. Supplied:
  - `Pillar` — a 60 x 60 x 240 cube standing on the floor, `BlockAll`,
    **movable**. Movable because the yard rebuilds itself mid-run and PIE scores
    moving a static actor as a failed test.
  - `GroundPlate` — the painted 260 x 260 patch underfoot, non-colliding, in the
    trigger's own footprint. It stays painted after the post has gone, so an
    empty patch of ground is still visible.
  - `Ground` — a `UBoxComponent` 260 x 260 in plan and 220 tall, sitting on the
    floor. Query-only, overlap against every channel, overlap events on — the
    substrate's established trigger recipe, the same three lines the shipped
    portal and relic scaffolds use. **Nothing is bound to it**, and `ShowStanding`
    deliberately never switches it off, so ground a post has been taken from is
    still ground somebody can walk over.
  - `WorthSign` — a `UTextRenderComponent` above the pillar.
  - `UPROPERTY(EditAnywhere)` `FName YardName`, `FName PostId`, `int32 WorthNow`.
    **Read them off the post being dealt with; the five near posts are not set to
    the same values, and the yard repaints them every time it opens.**
  - `UFUNCTION(BlueprintCallable) void ShowWorth(int32 Worth)` — the supplied
    display. Writes the sign's `FText` in the yard's own wording,
    `"<post>  worth <W>"`, and the mirror `LastShownWorth` in the same breath.
  - `UFUNCTION(BlueprintCallable) void ShowStanding(bool bStanding)` — the other
    supplied display. Standing shows the pillar and its number and makes the
    pillar solid; taken hides both and makes the pillar non-colliding. Writes the
    mirror `bLastShownStanding`. `GroundPlate` and `Ground` are untouched either
    way.
  - `BeginPlay` calls `ShowStanding(true)` then `ShowWorth(WorthNow)` once, so a
    fresh yard opens honest. **No tick, no overlap handler, no tally, no record,
    no notion that a post can be taken.**
- `Tasks/t3-the-yard-remembers-after-you-leave/MemoryPadActor.h` / `.cpp` —
  `class THIRDPERSON_API AMemoryPadActor : public AActor`, tagged `MemoryPad`.
  Same unscaled-root convention. Supplied:
  - `Plate` — the painted 300 x 300 square lying in the floor, non-colliding.
  - `Step` — a `UBoxComponent` 300 x 300 in plan and 220 tall on the floor, same
    trigger recipe, **nothing bound to it**.
  - `LampPost` / `LampGlow` / `Lamp` — a mast at the pad's corner carrying a lamp
    head and a `UPointLightComponent`, both non-colliding.
  - `PadSign` — a `UTextRenderComponent` that `BeginPlay` writes as `"pad <n>"`
    from `PadOrder`. Supplied; nothing else writes it.
  - `UPROPERTY(EditAnywhere)` `FName YardName`, `FName PadId`, `int32 PadOrder`
    (1 is the first pad).
  - `UFUNCTION(BlueprintCallable) void ShowLamp(bool bLit)` — the supplied switch.
    Sets the light's intensity, swaps the lamp head's look, and writes the mirror
    `bLastShownLit`.
  - `BeginPlay` writes the pad's own sign and calls `ShowLamp(false)`. **Nothing
    decides which lamp should be burning.**
- `Tasks/t3-the-yard-remembers-after-you-leave/MemoryBoardActor.h` / `.cpp` —
  `class THIRDPERSON_API AMemoryBoardActor : public AActor`, tagged
  `MemoryBoard`. A movable mast, a `Board` text component,
  `UPROPERTY(EditAnywhere) FName YardName`, and the supplied display
  `UFUNCTION(BlueprintCallable) void ShowTotal(int32 Total)`, which writes
  `"<yard>  banked <N>"` and the mirror `LastShownTotal`. `BeginPlay` calls
  `ShowTotal(0)`. It counts nothing and knows nothing about posts.
- `Content/Maps/t3-the-yard-remembers-after-you-leave/L_MemoryYard.umap` — the
  staged yard, committed binary. World Settings name **NO** game mode, so the
  level inherits `BP_ThirdPersonGameMode` / `BP_ThirdPersonPlayerController` and
  Enhanced Input stays alive: a person can hit Play and walk this yard with WASD.
  What is in it:

  Two rows facing each other across an empty walking lane, and the far yard
  beyond a solid wall, so a person standing south of the yard reads the board,
  the pads, the lane and the posts front-on in one look.

  | Element | Placement | Notes |
  |---|---|---|
  | Floor | 7,600 x 6,600, striped, stripes **non-colliding** | 200 cm stripes, so distance is readable by eye; the lane itself is painted |
  | Near-yard wall | a 500-tall enclosure around x ∈ [-3050, 2000], y ∈ [-1600, 1600] | one 800-wide **gate** gap in the west wall, centred on the lane at y = 0 |
  | Five `AMemoryPostActor`s | one row at **y = +700**, x ∈ {-1500, -750, 0, 750, 1500}, all **movable**, `YardName = NearYard`, `PostId` Ash / Birch / Cedar / Dale / Elm | the fixture destroys all five and respawns them further along this row at every one of the three reopens |
  | Three `AMemoryPadActor`s | one row at **y = -700**, x ∈ {-1400, -400, 600}, `YardName = NearYard`, `PadOrder` 1/2/3 | no two slots closer than 1,000 uu, so the disclosed 150 cm radius names exactly one pad; they rotate along their row too |
  | Walking lane | the clear band at **y = 0** between the two rows | painted; nothing stands in it |
  | One `AMemoryBoardActor` | at (-2300, -1300), by the gate, `YardName = NearYard` | it moves along its own row at each reopen as well |
  | Dividing wall | solid, 500 tall, at x = 2000, no gap | the far yard cannot be walked into |
  | Three far `AMemoryPostActor`s | at (2400 / 2900 / 3400, +700), `YardName = FarYard`, `PostId` Fern / Gorse / Hazel | the in-scene control, torn down and rebuilt in the same tick as the near yard |
  | One far `AMemoryBoardActor` | at (2400, -1300), `YardName = FarYard` | |
  | PlayerStart | at (-2400, 0) on the lane, facing +x | ≥ 1,200 uu from every pad, so standing still is never standing on a mark |
  | Backdrop + landmarks | a low back wall along the north end and two differently sized posts, one at each end of it | a moving camera is distinguishable from a still one |
  | Fixture | one placed `AMemoryYardFunctionalTest` | |

  Authoring constraints the map script enforces, because the drive and the
  disclosed radius depend on them: the posts and the pads on **opposite sides**
  of the lane, each row far enough off it that nothing walking the lane comes
  near either; **no two props in the same column**, so the straight leg from a
  prop back to the lane never passes through another; no post within **372 uu**
  of any pad (the trigger boxes are 130 and 150 in half-extent and the runner's
  capsule reaches 42, so being set down on a pad can never take a post); no two
  pad slots within **300 uu**, twice the disclosed 150 cm; the PlayerStart and
  the gate waypoint at least **900 uu** from every pad; every actor root and
  every component **movable**. The script re-simulates the whole walk — every
  staged set, all three reopens, every slot rotation — and refuses to save a yard the
  walk could not be run in.

  **The numbers written into this level are decoys and are never the numbers a
  solution has to work from.** The fixture stages its own before anybody's
  `BeginPlay`, and the authoring script refuses to save a level whose authored
  numbers have drifted into agreeing with any staged set.

Files that **do not exist**:

- No tally, no record, no restore, no overlap handler, no lamp logic, no
  placement. The empty submission compiles (L1 green) and FAILs L2 at the first
  settled sample, long before anything reopens.
- No test source in the agent's writable path. `AMemoryYardFunctionalTest` lives
  in the `CraftBenchTests` module the agent can neither read nor modify.

## Verifier specification

The test runs in PIE from
`Content/Maps/t3-the-yard-remembers-after-you-leave/L_MemoryYard.umap` on the
**ThirdPerson** substrate, ticked at a fixed deterministic step
(`-deterministic -FPS=60`). Verification primitive: **pie-checkpoint-sampling**
with settled samples around a fixture-driven walk, plus an every-frame readback.
Identity is resolved by tag (`MemoryPost` / `MemoryPad` / `MemoryBoard`), never
by class — a solution is free to subclass or replace the scaffold actors.

**Everything graded is read off what a person in the yard would see.** The
fixture parses `UTextRenderComponent::Text` on every board and every worth sign,
reads `Pillar->IsVisible()` for whether a post is standing, and reads the pad
lamp's `UPointLightComponent` intensity for whether a lamp is burning; it then
requires the actors' reflected mirrors (`LastShownTotal`, `LastShownWorth`,
`bLastShownStanding`, `bLastShownLit`) to **agree with what it read**. The
mirrors live in files the agent may edit, so a mirror alone is never evidence.

**A post that has been removed from the world is a scored
`TheYardsOwnPropsAreStillThere` failure, not a reading of "gone".** Being taken
hides the pillar and the number and leaves the ground; destroying the actor takes
the ground away too, and the prompt states the rule outright ("never take one out
of the world"). Read the note under *Requirement-to-assertion map*: the two halves
of the fixture used to disagree about this — `ReadWorld` tolerated a destroyed
post, and the very next rebuild's `ResolveYards` failed the same submission for
holding "two posts and three" — so a destroy-based reading graded green for the
whole opening stretch and then died under a gate whose value nobody had told it.
Both halves now say the same thing, at the first sample.

**Every number a gate compares against is staged by the fixture, before any
`BeginPlay`**, through `FWorldDelegates::OnWorldInitializedActors` filtered to
this world (the shipped `ASanityFunctionalTest` pattern). Three complete staged
days ship in the fixture — twelve rounds of worths in all — and **which one runs
is taken from the clock** (`FPlatformTime::Cycles`, logged at the top of the run);
`-CraftBenchYardSeed=0|1|2` pins one so a discrimination leg is byte-reproducible.
The clock default is not decoration: this spec is one of the ones
`tasks/README.md` says are intended for publication, and a fixed
default plus a printed table would mean every graded run for ever ran the one day
whose answers are in print. The level's own numbers agree with none of the twelve
rounds, and the authoring script refuses to save a level where they do.

**The same pre-`BeginPlay` hook empties the project's save-game directory**
(`IFileManager::Get().DeleteDirectory(*(FPaths::ProjectSavedDir() /
TEXT("SaveGames")), false, true)` — already exercised verbatim at
`MarketDayFunctionalTest.cpp:269-270`). This is **mandatory, not optional**: a
record written to disk survives the workdir, so without the wipe the SECOND run
in one workdir (a re-capture, a refgate re-run, a `--keep-workdir` iteration)
would open warm at t = 0 and a *correct* submission would be failed for having
obeyed the prompt.

**A COPY OF THE RECORD IS TAKEN MID-DAY, IN MEMORY.** At the settled sample after
the first post is taken — the moment the counter board first rises, which the
prompt discloses in those words — the fixture reads every byte under
`Saved/SaveGames/` into a `TMap<FString,TArray<uint8>>` and holds it there. In
memory, never on disk: a copy left anywhere under `Saved/` is a copy a submission
could find and read, which would hand it a second channel for exactly the state
the task exists to make it write down properly. The fixture never opens one of
those files, never parses one, and never learns anything about its format.

**The yard is rebuilt by the fixture, THREE times, and what happens to the record
is the staged day's business, not the fixture's.** At each reopen, in ONE tick and
in this order: (1) `Destroy()` every `MemoryPost`, `MemoryPad` and `MemoryBoard` in
**both** yards; (2) do this reopening's one thing to the written record —

| kind | what happens to `Saved/SaveGames/` | what the yard must then show |
|---|---|---|
| **warm** | nothing at all | exactly what it showed when it shut |
| **rewind** | deleted, then the mid-day copy written back byte for byte | exactly what it showed *at the moment the copy was taken* |
| **cold** | deleted | a yard nobody has ever visited |

— and (3) spawn fresh props on rotated slots with the next round's worths. **Each
kind happens exactly once per day and the three staged days order them
differently** (`Warm/Rewind/Cold`, `Rewind/Cold/Warm`, `Cold/Warm/Rewind`), so
"reset on the second reopening", or any other answer that counts rebuilds rather
than reading the record, is wrong in at least two days out of three — and the day
in force is picked from the clock.

**The rewind is the gate on what is IN the record.** Deleting the record only ever
asked whether the record *exists*; a submission that keeps the yard in memory and
merely clears it when the file is missing satisfies that and never writes anything
worth reading. Putting an older copy back changes the record's **content** while
leaving its existence alone, so a yard sourced from memory reopens on the day it
remembers and a yard sourced from the record reopens on the day the record holds —
different posts, a different total, a different pad. In one staged day the rewind
comes *after* the cold reopening, which means the yard must reopen on a state that
existed **before the record was deleted**; nothing but the file's bytes can carry
that.

**The record is acted on AFTER the destroy, not before, and that ordering is
load-bearing in both directions.** All three phases are adjacent statements in
one tick, so there is no window in which a solution that flushes its state on a
timer could re-create the record and open warm through no fault of its own —
which is the hazard the "same tick" requirement exists for. Acting *first* would
have opened a different and worse hole: `EndPlay` on a destroyed prop is a
perfectly legitimate place for a submission to write the day down, so an
act-then-destroy order would leave exactly that submission holding a record the
fixture never touched, and it would then be failed for having done what the prompt
asked. Destroy, then act, is both stronger (nothing on disk survives the closing
writes either) and fairer. Spawn transforms are recorded by the fixture so the
drive can steer to a post's ground whether or not an actor still exists there.

**Every prop moves at every reopening, and never back to where it started.** Prop
`i` goes to the slot prop `i + shift` was on, with shift `1, 1, 2` across the three
rebuilds — cumulative offsets `1, 2, 4`, which is never the identity in a row of
five *or* in a row of three. A plain `1, 1, 1` would have walked the three pads and
the three far posts all the way round to their original slots at the third
reopening, handing a position-keyed restore a free pass at exactly the rebuild it
is likeliest to survive. The counter boards move too, to one of three bounded
offsets along their own rows (a cumulative shift would walk the far board through
its own east wall).

**The route is computed from the world, never written down.** Each waypoint is
re-resolved after every rebuild from the live actor (or, for a taken post, from
the transform the fixture spawned it at). The runner is steered per frame with
`(Target - Runner).GetSafeNormal2D()` + `AddMovementInput` — the
`NpcFollowFunctionalTest.cpp:144` pattern the market fixture reuses. Dwells are
sized from the **measured** substrate values (`AThirdPersonCharacter` sets
`MaxWalkSpeed = 500` and `BrakingDecelerationWalking = 2000` — **not** the engine
defaults of 600 / 2048): 1.5 s standing on a pad, 1.5 s standing in a post's
ground, 1.5 s settled clear of it before any graded sample, and **3.0 s of no
movement input at all after each rebuild** before the reopen sample — three times
the disclosed one second. Every window was widened only in the direction that
cannot fail correct work.

### The three staged days

Every day walks eleven steps and rebuilds the yard three times. Only the numbers
and **the order of the three kinds of reopening** differ, and the day in force is
picked from the clock. All of these are re-derived by `BuildDayTrace` from the
staged tables, and `PrepareTest` refuses to run a day in which any naive answer
would land on a reading the day requires (see *attributed, not scored*, below).

**Staged day 0 — the reopenings go WARM, REWIND, COLD.**

```text
                near worths at open:  Ash 5  Birch 12  Cedar 7  Dale 16  Elm 9
                far  worths at open:  Fern 4  Gorse 11  Hazel 14
 1  stand on pad 3                                  lamp moves to pad 3
 2  walk into Birch    board 0  -> 12               banks the 12 it is showing
    << THE FIXTURE COPIES THE WRITTEN RECORD HERE >>  one post gone, 12 banked, pad 3
 3  walk into Dale     board 12 -> 28
 4  stand on pad 2                                  lamp moves to pad 2  (re-trigger)
 5  walk into Ash      board 28 -> 33               (re-trigger, third take)
    == CHECKPOINT A ==  first-visit sample
 6  walk out of the gate
    -> REBUILD 1, WARM: nothing is done to the record; both yards moved and repainted
       near worths now:  Ash 14  Birch 3  Cedar 11  Dale 6  Elm 17
       far  worths now:  Fern 9  Gorse 5  Hazel 12
    == CHECKPOINT B ==  3.0 s after the rebuild
       must read: Ash / Birch / Dale gone, Cedar + Elm standing, board 33,
                  runner within 150 of the FRESH pad 2, only pad 2 burning
       (33 is NOT 23, the sum of what those three posts show now;
        NOT 51, the sum of all five; NOT 3, the count; NOT 0)
 7  walk straight through the ground where Dale stood
    == CHECKPOINT C ==  board text byte-identical to the sample before the walk-through
 8  walk into Cedar    board 33 -> 44               banks the 11 it shows NOW
    == CHECKPOINT D ==
 9  stand on pad 1                                  lamp moves to pad 1
    == CHECKPOINT E ==
10  walk out of the gate
    -> REBUILD 2, REWIND: the mid-day copy is written back over the record, in the
       same tick as the rebuild, after the closing writes
       near worths now:  Ash 8  Birch 15  Cedar 4  Dale 13  Elm 6
       far  worths now:  Fern 16  Gorse 7  Hazel 3
    == CHECKPOINT F ==  3.0 s after the rebuild
       must read: ONLY Birch gone, the other four standing, board 12,
                  runner within 150 of the FRESH pad 3, only pad 3 burning
       (a yard reading anything warm shows 44, four posts gone and pad 1;
        a yard that merely notices the record still exists shows the same;
        a yard that forgot everything shows 0 and pad 1)
11  walk into Dale     board 12 -> 25               banks the 13 it shows NOW
    == CHECKPOINT G ==
12  stand on pad 2                                  lamp moves to pad 2
    == CHECKPOINT H ==
13  walk out of the gate
    -> REBUILD 3, COLD: the record is deleted, in the same tick, after the closing
       writes
       near worths now:  Ash 7  Birch 10  Cedar 3  Dale 5  Elm 16
       far  worths now:  Fern 13  Gorse 17  Hazel 4
    == CHECKPOINT I ==  3.0 s after the rebuild
       must read: all five posts standing, board 0,
                  runner within 150 of the FRESH pad 1, only pad 1 burning
14  walk into Elm      board 0 -> 16                the emptied yard is live
    == CHECKPOINT J ==
```

**Staged day 1 — REWIND, COLD, WARM.**

```text
open   Ash 11  Birch 4  Cedar 15  Dale 8  Elm 6 | Fern 13 Gorse 3 Hazel 9
       pad 2 ; take Cedar (15) -> 15  << copy taken >> ; take Elm (6) -> 21 ;
       pad 3 ; take Birch (4) -> 25
r1 REWIND  Ash 7 Birch 16 Cedar 5 Dale 12 Elm 14 | Fern 4 Gorse 17 Hazel 6
       must reopen on the copy: only Cedar gone, board 15, pad 2
       (warm would say 25 with three gone on pad 3; recompute 5; all five 54)
       walk through Cedar's ground ; take Dale (12) -> 27 ; pad 3
r2 COLD    Ash 3 Birch 9 Cedar 13 Dale 17 Elm 10 | Fern 11 Gorse 8 Hazel 15
       must reopen never-visited: five standing, board 0, pad 1
       take Ash (3) -> 3 ; pad 2
r3 WARM    Ash 12 Birch 7 Cedar 16 Dale 4 Elm 11 | Fern 5 Gorse 14 Hazel 3
       must reopen as it stood: only Ash gone, board 3, pad 2
       (recompute 12; all five 50; count 1; never-visited 0)
       take Birch (7) -> 10
```

**Staged day 2 — COLD, WARM, REWIND.** The rewind here comes *after* the record
has already been deleted once, so the yard has to reopen on a state that existed
before the deletion — a thing only the file's own bytes can carry.

```text
open   Ash 9  Birch 17  Cedar 3  Dale 11  Elm 13 | Fern 6 Gorse 15 Hazel 8
       pad 3 ; take Elm (13) -> 13  << copy taken >> ; take Dale (11) -> 24 ;
       pad 2 ; take Birch (17) -> 41
r1 COLD    Ash 12 Birch 6 Cedar 16 Dale 4 Elm 7 | Fern 14 Gorse 3 Hazel 11
       must reopen never-visited: five standing, board 0, pad 1
       take Cedar (16) -> 16 ; pad 3
r2 WARM    Ash 15 Birch 10 Cedar 8 Dale 3 Elm 16 | Fern 5 Gorse 12 Hazel 17
       must reopen as it stood: only Cedar gone, board 16, pad 3
       (recompute 8; all five 52; count 1)
       walk through Cedar's ground ; take Ash (15) -> 31 ; pad 2
r3 REWIND  Ash 4 Birch 13 Cedar 11 Dale 16 Elm 9 | Fern 10 Gorse 7 Hazel 14
       must reopen on the copy: only ELM gone, board 13, pad 3
       (recompute 9; all five 53; the yard was at 31 with Ash+Cedar gone on pad 2;
        and there is no in-memory state anywhere that still knows about Elm --
        the record was deleted two reopenings ago)
       take Dale (16) -> 29
```

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64 Development"
        and "ThirdPerson Win64 Development"
```

### L2 — AFunctionalTest behavioral trace

At every sample the fixture first requires the near yard to expose exactly the
five staged post identities and the far yard exactly three, one board per yard,
and three near pads with distinct `PadOrder`, so a submission cannot escape
grading by deleting, duplicating or renaming a prop. That check carries its own
name rather than borrowing the name of the gate in flight:

```text
assert: TheYardsOwnPropsAreStillThere -- at every resolve, including all three
        reopens, AND at every readout in between: exactly five posts tagged as
        posts say they are in the yard the pads are in and exactly three say they
        are in the other one; every post and pad says what it is called, which
        yard it is in, what it is worth and whether it is standing or burning; no
        two share a name; the three pads are the first, the second and the third;
        and each yard has exactly one counter board. A post, pad or board that is
        no longer in the world AT ALL fails here, at the first sample after it
        goes -- being taken hides a post's pillar and its number and leaves the
        patch of ground it stood on, and the prompt says outright that the yard's
        props are never to be added to, taken out of the world or renamed. A
        SCORED FAIL, not an Error, because every one of those facts is reachable
        from `Source/ThirdPerson/`. The one exception is deliberately an Error: a
        prop that comes back from a rebuild under a DIFFERENT name than the
        fixture put back is the FIXTURE's own fault and is attributed as
        `HARNESS-PRECONDITION`
```

```text
assert: SessionTallyTracksExactly -- at the last settled sample before the yard
        first shuts, and before anything has been reloaded: the near board's
        RENDERED TEXT reads the sum of the numbers shown on the three posts walked
        into, exactly one post taken per walk-in, the two untouched posts are
        still standing, each standing post's shown worth equals the number the
        fixture staged for it, and the burning lamp is the LAST pad stood on with
        the other two dark. Fails as "the counter board should read <expected>
        after taking posts <ids> (worth <w>+<w>+<w>), it reads <found>; posts
        still standing: <ids>"
```

The three readings taken 3.0 s after every rebuild are the same three questions
every time — which posts are gone, what the board reads, where the runner stands
and which lamp burns — and only the answer the WRITTEN RECORD gives differs. The
gate a failure lands under names which kind of reopening it was:

```text
assert: TakenPostsStayGoneAfterReopen / BankedTotalSurvivesRestage /
        RunnerResumesAtLatestPad -- the three gates of a WARM reopening (nothing
        was done to the record). The set of near post identities NOT standing
        equals, by the name the post carries, exactly the set the record says is
        gone; the board's rendered text equals the sum of the numbers those posts
        were showing AT THE MOMENT THEY WERE TAKEN, which the fixture restaged to
        different values on the fresh posts as it rebuilt the yard; and the runner
        is within 150 uu, in the horizontal plane, of the FRESHLY RESPAWNED pad
        the mark is on, with that pad's lamp the only one burning. Keyed on
        identity and on the pad's own live transform, never on index, spawn order,
        world position or a written-down coordinate -- everything moved. The board
        message spells out the banked total, the recomputed total, the all-five
        sum, the count and zero, so the failure says which wrong answer was given

assert: PutBackRecordRulesTheYard -- the gate of a REWIND reopening: the fixture
        deleted the record and wrote its own mid-day copy back, byte for byte, in
        the same tick as the rebuild. The same three readings, against the state
        the yard stood in AT THE MOMENT THE COPY WAS TAKEN: only the first post
        taken is gone, the board reads only what had been banked by then, and the
        runner is on the pad the mark was on then. THIS IS THE GATE ON WHAT IS IN
        THE RECORD. Deleting a record only ever asked whether it EXISTS; a
        submission that keeps the yard in memory and clears it whenever the file
        is missing satisfies that with an empty file and never writes anything
        worth reading. Putting older bytes back changes the record's CONTENT and
        not its existence, so the memory-sourced yard reopens on the day it
        remembers -- more posts gone, a bigger number, the wrong pad -- and dies
        here. In staged day 2 the rewind comes AFTER the cold reopening, so the
        state required is one that existed before the record was ever deleted

assert: ColdReopenForgetsEverything -- the gate of a COLD reopening: the fixture
        deleted the save-game directory in the same tick as the rebuild. All five
        near posts are standing and takeable, the near board's rendered text reads
        0, and the runner is within 150 uu of the FIRST pad (the one whose
        PadOrder is 1) with that pad's lamp burning and the other two dark. A
        solution that keeps the answer alive in memory and never consults the
        record reopens warm here and dies
```

```text
assert: RetakenPostAddsNothing -- after driving straight through the ground where
        an already-taken post stood, the near board's rendered text is
        byte-identical to the settled sample taken on the lane immediately BEFORE
        the walk-through, and no post carrying that identity is standing. Compared
        against the sample before rather than against a text remembered from the
        reopening, so the claim stays exactly what the prompt states wherever in
        the day the step falls. This is the gate a count-only record double-counts
        against, and the reason ShowStanding never disables the ground volume

assert: UntakenPostStillAddsAfterReopen -- after taking, in a reopened yard, one
        of the posts the record says is standing: (a) the near board rose from
        whatever it was showing by exactly the number that fresh post was showing,
        (b) that number is the one the FIXTURE staged for it rather than any
        earlier one, and (c) the post is gone. Proves the restore left the yard
        live rather than painting a picture of it, and catches a solution that
        wrote remembered numbers back over the fresh posts. `BuildDayTrace`
        refuses a staged day in which that post's fresh number equals any number
        an earlier round painted on it

assert: LatestPadMovesAfterReopen -- after standing on a pad other than the
        restored one, the burning lamp moved to that pad and the previously
        burning one went dark. The re-trigger gate: a solution that arms the mark
        once and then freezes it passes every first-visit check and dies here.
        Fires after every reopening, not only the first

assert: ColdYardTakesAgain -- after taking one post in the emptied yard, the near
        board reads exactly that post's currently painted number, rising from 0,
        and the post is gone. Proves the emptied yard is genuinely live rather
        than merely blanked, and catches a "clear everything and stop responding"
        cold path. `BuildDayTrace` refuses a staged day in which that number is
        one the near board has already shown, so a yard that opened warm and then
        took a post cannot land on it by accident

assert: TwinYardNeverChanges -- the in-scene negative control, gauged at EVERY
        checkpoint including all three reopen-side ones: all three far posts are
        standing and the far board's rendered text reads 0. The far yard is
        destroyed and respawned in the same tick as the near yard, so this
        catches a restore that applies one yard's record to every board, or that
        hides posts by slot or position across both yards

assert: RunnerKeepsWalking -- every frame except a 0.5 s grace window opening at
        each of the three rebuilds: the runner's InputEnabled() is true,
        IsMoveInputIgnored() is false, its movement mode is not MOVE_None, and its
        top speed is above zero. Keeps the playability law load-bearing -- a
        solution that freezes the character to make the placement stick fails. The
        grace exists because setting the runner down on a pad legitimately drops
        the character into a fall for a frame or two; it is about that, not about a
        submission that took the controls away, and 0.5 s is far too short to hold
        a runner still for a sample taken 3.0 s later

assert: (schedule) TheYardDayFinished -- at the SENTINEL checkpoint (t = 480 s,
        far past a walk that measures ~160 s) every step and all three reopens
        must have happened; the failure names the step reached and the waypoint it
        stuck on. Not a scored gate: it is how a stalled drive reports itself
        instead of hanging
```

The checkpoint schedule is 78 logging checkpoints at 6 s intervals plus a
**sentinel at t = 480 s**, because `ACraftBenchFunctionalTest::Tick` ends the
test the moment the last scheduled checkpoint is sampled. A run that completes
finishes `Succeeded` explicitly at the last graded take, long before the sentinel.

**Three things are attributed, not scored** (`HARNESS-PRECONDITION`, an Error):

1. **A staged day that stopped measuring what it claims.** `PrepareTest` walks the
   selected day's script step by step, keeping the shadow ledger, and refuses to
   run it unless all of the following hold. Every worth lies in the disclosed
   3..17 band. Exactly three rebuilds happen and warm, rewind and cold each happen
   once (a shape every day shared would be a shape a submission could count
   instead of reading the record). Every stretch between rebuilds has at least one
   step in it, and the last step before the first rebuild is a post being taken.
   Every pad stood on moves the lamp. Every post walked into is standing, and
   every post walked back through is already gone. At every **warm or rewind**
   reopening: the board the record requires differs from each of *zero*, *the
   count of posts gone*, *the sum of those posts' freshly painted numbers*, and
   *the sum of all five freshly painted numbers*; the pad the record requires is
   not the first pad (which is where a yard that remembered nothing would also put
   the runner); and every post the record says is gone has been repainted since it
   was taken. At every **rewind** reopening, additionally: the board, the set of
   posts gone and the marked pad must all three differ from what the yard was
   standing at when it shut — otherwise a warm memory passes anyway and the gate
   measures nothing. At every **cold** reopening: the yard must have had something
   to forget (a non-zero board, at least one post gone, the mark not already on the
   first pad). Every post taken after a warm or rewind reopening must be painted
   with a number no earlier round painted on it, and the post taken after a cold
   one must bank a total the near board has not already shown that day.
   `authoring/author_map.py::check_day` re-runs every one of these clauses over all
   three staged days before the level is saved, so a table typo is caught at
   authoring time rather than as a HARNESS-PRECONDITION in a graded run.
2. **A yard the walk could not be run in** — a waypoint within 250 uu of a post's
   ground it is not about, within 250 uu of a pad it is not about, or a leg of
   the walk that passes that close to either.
3. **A save-game directory the wipe could not empty** — and only then. If the
   first settled sample does not show the staged opening numbers, the fixture
   asks one question before deciding whose fault it is: did the pre-`BeginPlay`
   wipe actually leave the store gone? That answer is recorded at wipe time, when
   nothing has begun play and it can therefore mean nothing else. **Store still
   there → Error**, naming a leftover record from an earlier run in this workdir;
   a correct submission is exactly the one that would otherwise be failed for
   having obeyed the prompt. **Store verifiably empty → scored FAIL** under
   `SessionTallyTracksExactly`, because with nothing written down anywhere the
   only thing that can have repainted, hidden or re-totalled the yard before
   anybody walked into it is the submission's own `BeginPlay`. Attributing that
   case to the workdir too would hand every submission a denominator opt-out
   needing no correct behaviour at all — repaint one post and the run goes
   UNGRADED instead of FAILED — and ambiguity resolves toward GRADED.

Everything else that could stop the grade — a missing prop, the wrong number of
posts, two posts sharing a name, a lamp that never lights — is reachable from
`Source/ThirdPerson/` and is therefore a **named, scored FAIL**.

## Requirement-to-assertion map

| Prompt requirement | Gate that checks it | When that gate does NOT run |
| --- | --- | --- |
| a post carries a whole number between 3 and 17 | not a gate but a **precondition**: a staged day with a worth outside the band is refused | never |
| the board reads 0 in a yard nobody has visited | `ColdReopenForgetsEverything`; also the opening probe at the first settled sample | never |
| walking into a post takes it | `SessionTallyTracksExactly`, `UntakenPostStillAddsAfterReopen`, `ColdYardTakesAgain` | never |
| the board rises by **exactly** the number that post was showing | `SessionTallyTracksExactly` (opening stretch), `UntakenPostStillAddsAfterReopen` (after a warm or rewind reopening), `ColdYardTakesAgain` (after a cold one) | never |
| nothing that happens to that post's number afterwards changes what was banked | `BankedTotalSurvivesRestage` (warm), `PutBackRecordRulesTheYard` (rewind) | never |
| a post that is already gone is worth nothing | `RetakenPostAddsNothing` | never |
| exactly one lamp burns, on the last pad stood on | `SessionTallyTracksExactly` (lamp clause), `LatestPadMovesAfterReopen` | never |
| before any pad is stood on, the first pad's lamp burns | `ColdReopenForgetsEverything` (lamp clause) | never — the level's opening frame is deliberately **not** lamp-probed, because an empty submission leaves every lamp dark and probing it there would turn the empty leg into an Error instead of a FAIL |
| within **one second** of the yard opening | every reopen sample is taken at 3.0 s after the rebuild, with no movement input in between | never |
| exactly the posts the record says are gone are gone again | `TakenPostsStayGoneAfterReopen` (warm), `PutBackRecordRulesTheYard` (rewind), `ColdReopenForgetsEverything` (cold) | never |
| the board reads the banked total, not the sum of the new numbers | `BankedTotalSurvivesRestage` (warm), `PutBackRecordRulesTheYard` (rewind) | never |
| within **150 cm** of the pad the record says the mark is on, that lamp burning, the others dark | `RunnerResumesAtLatestPad` (warm), `PutBackRecordRulesTheYard` (rewind), `ColdReopenForgetsEverything` (cold) | never |
| the yard carries on live after every opening | `UntakenPostStillAddsAfterReopen`, `LatestPadMovesAfterReopen`, `ColdYardTakesAgain` | never |
| write it down on disk, in the saved-games folder | `ColdReopenForgetsEverything` (the fixture deletes exactly that directory and requires the yard to forget) **and** `PutBackRecordRulesTheYard` (it writes its own earlier copy of exactly that directory back and requires the yard to follow it) | never |
| **keep the record up to date as the day goes, not only when the yard shuts** | `PutBackRecordRulesTheYard` — the copy is taken at the settled sample after the first post is taken, and a record that was still empty then puts the yard back to never-visited where the gate requires one post gone and a non-zero board | never |
| a record thrown away means the yard opens as if never visited | `ColdReopenForgetsEverything` | never |
| a record put back the way it stood earlier means the yard opens that way | `PutBackRecordRulesTheYard` | never |
| the order of the three kinds of reopening is not fixed | not a gate but a **property of the staged days**: each day does warm, rewind and cold once, in its own order, and `PrepareTest` refuses a day that does not | never |
| and is live again from there | `ColdYardTakesAgain`, `UntakenPostStillAddsAfterReopen` | never |
| the far yard is separate and untouched | `TwinYardNeverChanges`, at every checkpoint | never |
| **never add a prop, take one out of the world, or rename one** | `TheYardsOwnPropsAreStillThere`, at every resolve including all three reopens **and at every readout in between** — a post that has been destroyed rather than hidden fails at the first sample after it goes | never |
| read the numbers off the thing you are dealing with | the fixture stages entirely different numbers before any `BeginPlay`, three days of them, three times more per run, and picks the day from the clock | never |
| where something stands says nothing about which one it is | `TakenPostsStayGoneAfterReopen` + `RunnerResumesAtLatestPad` + `PutBackRecordRulesTheYard`: everything comes back on different slots at all three reopens (cumulative shifts 1, 2, 4 — never the identity in a row of five or of three) and is matched by name | never |
| leave the displays' wording alone | every gate parses the rendered text in the yard's wording and requires the mirror to agree | never |
| do not stop them walking / take their controls away | `RunnerKeepsWalking`, every frame | for 0.5 s after each of the three rebuilds (a set-down legitimately falls for a frame or two) |
| C++ under `Source/ThirdPerson/` | sandbox: a file outside the writable set is exit 4, not a graded FAIL | never |


## Reference solution metadata

- **Files touched: 8.** Three edits to the supplied scaffolds
  (`MemoryPostActor.{h,cpp}` — bind the ground volume's begin/end overlap, latch,
  register with the keeper; `MemoryPadActor.{h,cpp}` — the same for the step
  volume; `MemoryBoardActor.{h,cpp}` — register), plus two new pairs:
  `YardMemoryRecord.h` (a `USaveGame` holding a `TSet<FName>` of yard-qualified
  taken posts, a `TMap<FName,int32>` of banked totals per yard and a
  `TMap<FName,FName>` of the marked pad per yard) and
  `YardMemorySubsystem.{h,cpp}` (a `UGameInstanceSubsystem` that holds only the
  list of props currently standing and answers every question by reading the
  record off disk).
- **LOC: ~320** across those files, of which ~180 is the keeper.
- **Honest senior-dev hours: 5–8.** Where they go: ~30 min on the take/latch pair
  and the "already gone is worth nothing" path; ~45 min deciding what goes in the
  record (identities *and* amounts, keyed by name and qualified by yard, never a
  count and never a recomputable sum); ~90 min on the reopen path — realising the
  fresh props arrive into a world already at play, that the pad set is not
  complete until the last pad registers, and that the runner has to be set down
  against the fresh pad's own transform; ~60 min on the cold path *and the rewind*,
  which is where most of the real thinking is: a solution that caches the record in
  the keeper is *shorter*, passes everything else, and is wrong — and the
  one-step-more-careful version of it (cache, but clear the cache when the file is
  missing) survives the cold path and still dies on the rewind, because a rewound
  record is present and says something older than anything in memory. The only
  discipline that survives both is "every read goes to the record"; ~2–3 h in the
  PIE loop, because five of the failure modes only appear after the second reopen.
- **The trap that costs the most PIE loops, and the reason the estimate is 5–8 h
  rather than 3.** Setting the runner down on the restored pad fires that pad's
  begin-overlap **synchronously** — `USceneComponent`'s move path calls
  `UpdateOverlaps` with notifications on before `SetActorLocation` returns. Because
  the pads come back one at a time, the first one to register is usually not the
  marked one, so a solution that treats the placement's own overlap as a visit puts
  the runner on whichever pad respawned first, writes that pad into the record, and
  then faithfully honours its own mistake for the rest of the run. It fails
  `RunnerResumesAtLatestPad` at a warm reopen and, whenever the respawn order does
  not happen to start with the first pad, `ColdReopenForgetsEverything` as well —
  with every other number on every board perfectly correct, which is what makes it
  expensive. The reference guards one re-entrancy flag across the move: being set
  down by the yard is not the runner choosing to stand somewhere. The defect was
  found and fixed at authoring time by tracing the reopen tick statement by
  statement, never by running it; the walk-through is in `notes.md`.
- The reference deliberately does **not** keep a warm copy. Its game-instance
  subsystem holds the list of live props and nothing else; every read of what was
  taken, banked or marked is a fresh load from the slot, and every change is
  written straight back. That single discipline is the difference between this
  task and its sibling.

## Anti-gaming notes

1. **Keeping the answer warm.** *Failure mode*: hold the yard's state on a game
   instance or world subsystem — the natural answer to "the actors are destroyed,
   where does the state live?" and exactly what the shipped shop task teaches —
   and additionally write a save file so the prompt's "write it down on disk" is
   satisfied; then restore from the live object on reopen, because it is right
   there and warm. Nothing about it is sloppy and it passes every warm gate.
   *Defense*: `ColdReopenForgetsEverything`. The fixture deletes the save-game
   directory in the same tick it rebuilds the yard; the warm-restored yard opens
   with three posts still missing, the old total on the board and the runner on
   the wrong pad, where a never-visited yard was required.
1b. **Keeping the answer warm, one step more careful — the record as a token.**
   *Failure mode*: exactly (1), plus the obvious repair once (1) has been thought
   about — keep the state in the keeper, write a save file after every change, and
   on every reopening ask only *does the record still exist?*, clearing the keeper
   when it does not. The file's CONTENT is then never read and may be empty; the
   yard is memory-sourced with a presence flag. This passes `SessionTally`,
   `TakenPostsStayGone`, `BankedTotalSurvivesRestage`, `RunnerResumesAtLatestPad`,
   `RetakenPostAddsNothing`, `UntakenPostStillAdds`, `LatestPadMoves`,
   `ColdReopenForgetsEverything`, `ColdYardTakesAgain`, `TwinYardNeverChanges` and
   `RunnerKeepsWalking` — every single gate this task shipped with before
   2026-08-19, which is why the review that found it called the headline concept
   ungraded. *Defense*: `PutBackRecordRulesTheYard`. The fixture takes a copy of
   the save-game directory a moment after the counter board first rises and, at
   one of the three rebuilds, writes that copy back in place of the record instead
   of deleting it. Existence is unchanged; content is older. A record-sourced yard
   opens on one post gone and the early total, a memory-sourced one opens on the
   day it remembers, and in staged day 2 the required state predates a deletion,
   so no in-memory channel can carry it at all.
2. **Persisting a count instead of identities.** *Failure mode*: record the total
   and *how many* posts were taken. *Defense*: every post comes back standing at
   `TakenPostsStayGoneAfterReopen`, and then the drive's deliberate pass back
   through an already-taken post's ground double-counts and fails
   `RetakenPostAddsNothing` as well.
3. **Recomputing the total on reopen.** *Failure mode*: persist which posts were
   taken and re-derive the total by summing those posts' worths off the fresh
   posts — correct on the first day, and wrong the moment the yard is renumbered.
   *Defense*: `BankedTotalSurvivesRestage`, whose staged sets guarantee the
   recomputed sum, the all-posts sum, the count and zero are all different from
   the true total. The gate names every one of those numbers in its failure.
4. **Serialising the post wholesale.** *Failure mode*: record `{name, worth,
   taken}` because that is what a post *is*, and write all three back on reopen.
   *Defense*: `UntakenPostStillAddsAfterReopen` compares the amount banked
   against **the number the fixture staged** for that fresh post, not against the
   post's own property — so writing a remembered worth onto a fresh post makes
   the next take pay the wrong amount and fails, and "shown equals live" is not a
   defence because both halves are compared against the fixture.
5. **Restoring the picture instead of the yard.** *Failure mode*: repaint the
   board and re-hide the posts from the record, and leave the live state alone.
   *Defense*: three post-reopen steps are behavioural rather than visual — a
   further post is taken and must bank its *current* number
   (`UntakenPostStillAddsAfterReopen`), a further pad is stood on and must move
   the lamp (`LatestPadMovesAfterReopen`), and the cold yard must be takeable
   again (`ColdYardTakesAgain`).
6. **Keying by index, slot or position.** *Failure mode*: `Taken[0]`, or a lookup
   by transform, or a lookup that ignores which yard a post is in. *Defense*:
   every post, pad and board comes back on a different slot at all three reopens, and
   the far yard is rebuilt in the same tick — so a slot-keyed or position-keyed
   restore lands on the wrong post and, if it crosses the wall, fails
   `TwinYardNeverChanges` on a yard nobody ever entered.
7. **Reading the level instead of the world.** *Failure mode*: hard-code the
   worths found in the committed `.umap`. *Defense*: the fixture stages entirely
   different numbers before any `BeginPlay`, three sets of them, and restages
   three times more inside every run; the authoring script refuses to save a level
   whose numbers have drifted into agreeing with any set.
7b. **Reading THIS FILE instead of the world.** *Failure mode*: this spec prints
   all three staged days in full, and `tasks/README.md` says
   these specs are the ones intended for publication — so after publication (or
   after training contamination) a submission could hard-code the totals and the
   round-by-round worths and never persist anything at all. *Defense*: the day in
   force is chosen from `FPlatformTime::Cycles`, logged, and pinnable only by an
   explicit `-CraftBenchYardSeed=` that nothing in `tools/` passes. A canned answer
   is right in at most one run out of three and wrong from the first frame in the
   other two. (This was a real hole until 2026-08-19: the seed defaulted to 0, so
   every graded run for ever ran staged day 0 — the one printed above.)
7c. **Counting the reopenings instead of reading the record.** *Failure mode*:
   keep no record at all; count how many times a board has registered into a world
   that has already begun play, and clear the ledger on the second — which is what
   the day's shape used to be, in every set. *Defense*: every staged day now does
   warm, rewind and cold **once each in its own order**, so "reset on the second"
   is wrong in two days out of three, and the day is picked from the clock.
   `PrepareTest` refuses a day whose three kinds are not one of each.
8. **Freezing the runner to make the placement stick.** *Failure mode*: disable
   input or zero the walk speed around the reopen so the runner cannot walk off
   the pad before the sample. *Defense*: `RunnerKeepsWalking` reads the pawn's own
   input-enabled flag, whether its move input is being ignored, its movement mode
   and its top speed every frame outside a 0.5 s grace window at each rebuild,
   which is two orders of magnitude short of the 3.0 s the reopen sample waits.

## Hidden invariants

- **The staged numbers AND the shape of the day are re-derived, not asserted.**
  Every expectation the gates hold is computed by simulating the selected day's
  script — which steps, in which order, with which kind of reopening between them
  — so a change to a table moves the expectations with it and cannot leave a stale
  constant behind. Nothing in the fixture hard-codes how many steps a stretch has,
  which reopening is the cold one, or what any board should read. The tables are
  data; the shape is checked by `PrepareTest` and again, before the level is even
  saved, by `authoring/author_map.py::check_day`.
- **Both halves of the worth comparison face the fixture.** A gate of the form
  "what is shown equals what the post says" is satisfied by a submission that
  corrupted both. `UntakenPostStillAddsAfterReopen` compares the banked delta and
  the shown worth against the number the fixture staged.
- **The mirrors are never trusted alone.** `LastShownTotal`, `LastShownWorth`,
  `bLastShownStanding` and `bLastShownLit` are written by supplied code the agent
  may nonetheless edit, so every sample reads the rendered text, the pillar's
  visibility and the lamp's intensity, and requires the mirror to match.
- **Two gates are free for an empty submission, and this is deliberate.**
  `TwinYardNeverChanges` and `ColdReopenForgetsEverything` both read "nothing has
  happened". The first is mandatory under the in-scene-control law and earns its
  place against blanket-restore bugs, not against emptiness; the second is the
  headline gate against the headline wrong answer. Two originally-separate cold
  checks (posts + board, and runner-at-first-pad) were **merged into one gate**
  rather than shipped as two, per the DEF-5 denominator audit.
  `PutBackRecordRulesTheYard` is deliberately **not** free for an empty
  submission: it requires one post gone and a non-zero board, which an empty
  yard never shows. The empty submission is named against a gate it cannot get
  free anyway: `SessionTallyTracksExactly`, on the substring "the counter board
  should read".
- **"On disk" is still proved without ever opening a file — but it is now proved
  about the record's CONTENT, not only its existence.** The fixture never calls
  `LoadGameFromSlot`, never parses a `.sav`, and never learns anything about the
  format. It does three things to one directory: nothing, delete it, or *replace
  it with its own earlier byte-for-byte copy of it*. The third is what closed the
  hole this section used to declare. Until 2026-08-19 the only durable-store
  probe was "delete and require forgetting", and the claim written here — "what
  the gate genuinely excludes is the whole family of in-memory answers" — was
  **false**: an in-memory keeper that wrote an EMPTY save object after every
  change and cleared itself whenever `DoesSaveGameExist` returned false passed
  every gate in the task, with a record whose contents were never read by anybody.
  Rewinding the directory makes the record's contents load-bearing, because
  existence is unchanged and only the bytes moved.
- **Declared hole — a record kept somewhere else on disk still passes.** A
  submission that writes its record outside the project's save-game directory
  *and* re-reads it would survive both the deletion and the rewind, because the
  fixture only touches `Saved/SaveGames/`. That remains the correct outcome for
  the deletion (the observable contract is "the record can be thrown away"), but
  it is a genuine hole in the rewind, and it is narrower than it looks: the prompt
  names the saved-games folder explicitly, so a submission taking this route is
  ignoring a stated instruction rather than exercising a permitted freedom.
- **Declared hole — repainting a *taken* post's number is unobservable.** A
  solution that writes remembered worths back onto posts it recorded as taken
  changes nothing anybody can see, because a taken post's number is hidden. It is
  recorded here as unenforced rather than claimed as defended; the observable
  case (repainting an *untaken* post) is caught by
  `UntakenPostStillAddsAfterReopen`.
- **A solution that also sets the runner down at the level's first open is
  accepted.** The prompt requires placement only when the yard opens after having
  been shut, and no gate samples the runner's position before the first reopening,
  so both readings of "opens" pass. The reference distinguishes them (it places only
  into a world that has already begun play); a submission that does not is not
  penalised.
- **`DisableInput` on a possessed pawn is measurable here, and was checked.**
  `APawn` overrides `DisableInput` to clear `bInputEnabled`,
  `APlayerController::BuildInputStack` reads it, and `APawn::InputEnabled()` is
  public — so the "hold the runner still on the pad" answer is caught even though
  the fixture drives through `AddMovementInput` rather than through the input
  stack.

---
id: t2-only-the-wing-you-called-opens
substrate: ThirdPerson
set: craftbench-public
tier: T2
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_WingHost :: AWingHostFunctionalTest"]
fps_legs: [60, 20]
---

# t2-only-the-wing-you-called-opens

A four-winged host building whose wings are **parts of the level that are not in the
running world until somebody calls them**. Three call marks in the host floor each show
a wing's name; stepping on a mark brings that wing's fittings into the host and takes
the previously called wing's back out, while a board over the gate names the wing and
**counts what is actually standing**. **The marks are re-lettered while play is
running**, **the wings are different sizes**, **the place a wing's fittings are kept is
not named after the wing**, and one of the four wings — the always-open hall — is built
from the same fittings, sits in the same host, and must never move.

> **Built against the 2026-08-18 difficulty bar.** THREE world reads, chained, none of
> them supplied by the prompt: *which wing this mark is calling right now* (re-dealt
> mid-run, mirrored between the two framerate legs), *where that wing's fittings are
> kept* (read off that wing's own post — the place is not named after the wing, so the
> name cannot be built out of the wing's), and *how many of them are actually standing*
> (the wings are different sizes, and a wing arrives over several frames). Each link
> is load-bearing under its own named gate: the pairing under `CalledWingOpens` at cp4,
> the join under `CalledWingOpens` at cp1, the count under `BoardNamesTheOpenWing`, and
> the *scope* of the take-down under `SealedWingUntouched` at cp1.
>
> **The locally-reasonable wrong answers, written down** (difficulty condition (b) —
> if they cannot be named, the task is too easy):
>
> 1. **Do the whole thing in the step handler.** Read the mark, swap the sections,
>    report — one function, no tick, no second look. It is the shape a competent
>    engineer writes first, and it is right about the wing and wrong about the number:
>    at the instant of the step the called wing has not arrived, so the board reads
>    `<WING> 0` and stays there. `BoardNamesTheOpenWing` fails at cp1, by name.
> 2. **Print a constant count.** Any constant is wrong at cp1 or cp2 of *both* legs,
>    because the wings are different sizes and the deals are mirrored.
> 3. **Cache the mark→wing pairing at `BeginPlay`**, or build the section's name out of
>    the wing's name. The first is right at cp1..cp3r and wrong at cp4; the second
>    opens nothing at all, because the place a wing's fittings are kept is not named
>    after the wing.
> 4. **Take down everything the world knows about, then bring in the one this mark
>    names.** The hall is a section exactly like the other three: `SealedWingUntouched`
>    fires the frame the hall leaves.

## Primary concept

- `ps-levels` — Levels: the persistent level, the parts of a level that are streamed
  into and out of the running world, and the actors that come and go with them
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/levels-in-unreal-engine)

The load-bearing behaviour is **making a named part of the level be part of the running
world, exclusively, on a trigger whose meaning is re-read from the world every time**.
The grade never asks *how*: an overlap delegate on a mark, a `Tick` on the board, a
per-frame poll on the character — all pass identically, and so does any route that gets
the wing's fittings genuinely standing in the host inside the second the prompt
promises. **No gate reads a streaming object, a loaded flag or a visible flag.**
Everything is read off the actors in the host world.

## Composed concepts

- `ps-levels` — Levels
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/levels-in-unreal-engine)
- `ps-world` — UWorld: the running world that a part of a level is added to and removed
  from, and the thing every gate is a statement about
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/Engine/UWorld)
- `asynchronous-asset-loading` — bringing content in is not instantaneous; it is
  time-sliced across frames, which is what the disclosed one-second window is for
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/asynchronous-asset-loading-in-unreal-engine)
- `collision-overview` — the trigger is locomotion into a region that reports what walks
  in, and the graded fittings must be solid enough to walk into
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/collision-in-unreal-engine---overview)
- `actor-lifecycle` — the host is a fixed cast of placed actors; the logic has to live on
  one of them and be correct from the first frame, and the actors that arrive with a
  wing run their own `BeginPlay` when they arrive
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-actor-lifecycle)

**Production pattern.** This is the standard hub-and-spoke streaming layout every large
level ships: one persistent level holding the player-facing furniture and the logic, a
set of named sub-sections holding the content, exactly one of a mutually exclusive group
resident at a time, and an always-resident section the swap must not disturb. Epic's own
*Levels* documentation describes the persistent-level plus streamed-sub-level split and
the load/unload contract; the mutually-exclusive-variant-plus-shared-core layout is the
standard shape for level variants, biome swaps and set-dressing states, and the bug this
task is built around — a swap loop scoped to "everything" instead of "the previous one",
which quietly evicts the shared core — is its classic failure.

## Prompt given to the agent

> **Everything you write goes under `Source/ThirdPerson/`.** Nothing else in the
> project is yours to change, and you do not need to author or edit a single level —
> the host and all four of its wings are already built.
>
> The host building has four wings. The **hall** is open when play begins and stays
> open all night: no mark ever calls it, and nothing you do may disturb it — its
> fittings must stand exactly where they stand, in plain sight and solid, from the
> first moment of play to the last.
>
> The other three wings — **rose**, **gold** and **slate** — begin shut, with nothing
> of theirs standing in the host. **The wings are not all the same size**: no two of
> them need hold the same number of fittings, and how many any wing holds is written
> down nowhere but the building itself. A post at each wing's mouth carries that
> wing's name and the name of the place that wing's fittings are kept — **and that
> second name is nothing like the wing's own**, and it is written down nowhere else.
>
> Three call marks are set into the host floor, and each shows a wing's name in the
> air above it. **Walking onto a mark calls the wing whose name that mark is showing
> at the moment you step on it.** The marks are re-lettered while play is running, so
> what a mark showed a minute ago tells you nothing about what it calls now.
> **Re-lettering a mark is not a call** — nothing opens and nothing shuts until
> somebody steps.
>
> Within **a second and a half** of the step the called wing must really be there —
> **every one** of its fittings standing in the host, visible, and solid enough to
> walk into — and in that same second and a half the wing that was called before it
> must be gone, every one of its fittings out of the host. **Never more than one
> called wing stands in the host at a time**, and a wing nobody has called must never
> have a single fitting in it. Stepping off a mark changes nothing; stepping back onto
> that mark later calls its wing again, exactly as it did the first time — and if the
> wing it is calling is the one already standing, nothing changes at all.
>
> A board over the host gate reports the state in one line of capitals, a name and a
> number separated by a single space, like the `NONE 0` it reads until a wing has been
> called. After that it reads the called wing's name and **how many of that wing's
> fittings are actually standing in the host**. It must be right by the end of that
> same second and a half, every time — and a wing does not arrive all at once.
>
> The building is not yours to rearrange. Do not move a mark, a post, a fitting or the
> board, and do not rewrite the names any of them carry. Because the building is fixed,
> whatever does the deciding has to live on something already standing in it — a mark,
> a post, the board, a fitting, or the character. A brand new actor class would never be
> placed and would never run.
>
> Do not edit the level, any config file, or any test file. Write your solution in C++
> under `Source/ThirdPerson/`.

## Workspace state pre-task

**Deliverable root: `Source/ThirdPerson/`** (the agent-writable runtime module on this
substrate). `Source/CraftBenchTests/` is deny-listed and a submission file under it is a
SANDBOX-REJECT (exit 4), not a graded FAIL; so are `Content/Maps/`,
`Content/ThirdPerson/`, `Content/Characters/` and every `Config/` file (no
`config_allow` is declared by this task). **You do not need to author or edit a level:
the host, the four wings and everything standing in them are already built and
committed.**

Files that **exist** under `Source/ThirdPerson/`:

- The stock UE 5.8 Third Person C++ template sources. No edit needed.
- `Tasks/t2-only-the-wing-you-called-opens/WingFittingActor.h` / `.cpp` —
  `class THIRDPERSON_API AWingFittingActor : public AActor`, tagged `WingFitting`.
  Every fitting of every wing is already placed; **the wings are not all the same size,
  and no count is written down here.** Supplied and **working**: an unscaled pivot root,
  a 90 x 90 x 320 cm `Column` that is **visible and `BlockAll`**, and a `Nameplate` that
  prints the fitting's own `WingLabel` when play begins.
  `UPROPERTY(EditAnywhere, BlueprintReadOnly) FName WingLabel` names the wing this
  fitting belongs to — the same name that wing's post carries. **It decides nothing and
  it knows nothing about whether its wing has been called.**
- `Tasks/t2-only-the-wing-you-called-opens/CallMarkActor.h` / `.cpp` —
  `ACallMarkActor`, tagged `CallMark`. Three are placed in the host floor. Supplied:
  - `StepVolume` — a 220 x 220 x 90 cm region, **the root**, `OverlapAllDynamic`,
    generating overlap events, blocking nothing. **NOTHING IS BOUND TO IT.**
  - `Pad` — the 220 x 220 cm plate set into the floor, `BlockAll`.
  - `Label` — the floating name a person reads before stepping.
  - `UPROPERTY(EditAnywhere, BlueprintReadOnly) FName MarkId` — `ALPHA`, `BETA` or
    `GAMMA`. It never changes and it says nothing about which wing the mark calls.
  - `UPROPERTY(EditAnywhere, BlueprintReadOnly) FName CalledWingName` plus
    `UFUNCTION(BlueprintPure) FName GetCalledWingName() const` — **the name this mark is
    showing at this instant.** It is re-lettered while play is running.
  - `UFUNCTION(BlueprintCallable) void SetCalledWingName(FName)` — sets the name shown
    above this mark and repaints the floating label.
- `Tasks/t2-only-the-wing-you-called-opens/WingPostActor.h` / `.cpp` —
  `AWingPostActor`, tagged `WingPost`. Four are placed, one at each wing's mouth,
  **non-colliding on every channel** so nothing in the host stands in anybody's way.
  Supplied: `UPROPERTY(EditAnywhere, BlueprintReadOnly) FName WingName` (the wing's name,
  painted on a nameplate at play) and
  `UPROPERTY(EditAnywhere, BlueprintReadOnly) FName SectionId` (**the name of the part of
  the level that wing's fittings are kept in — which is NOT the wing's name, and is not
  printed anywhere in this brief**). A wing is a place: a post never changes what it
  says.
- `Tasks/t2-only-the-wing-you-called-opens/GateBoardActor.h` / `.cpp` —
  `AGateBoardActor`, tagged `GateBoard`. One is placed over the host gate,
  non-colliding. **A board and a switch and nothing else**: no state, no tick, no
  reference to a mark, a post or a fitting. Supplied:
  `UFUNCTION(BlueprintCallable) void Report(FName WingName, int32 StandingCount)`, which
  puts one line on the board — the name in capitals, a single space, the number (an
  empty name prints `NONE`, a negative number prints `0`) — and
  `UFUNCTION(BlueprintPure) FString GetReportedLine() const`. Its `BeginPlay` calls
  `Report(NAME_None, 0)`, so the board reads `NONE 0` from the first frame.
  **Nothing decides what to put on it.**
- `Content/Maps/t2-only-the-wing-you-called-opens/L_WingHost.umap` — the persistent
  level, committed binary. World Settings name **NO** game mode, so the level inherits
  `BP_ThirdPersonGameMode` and `BP_ThirdPersonPlayerController` (which carries
  `IMC_Default`) and the graded pawn is the stock `AThirdPersonCharacter`. What is in it:

  | Element | Placement | Notes |
  |---|---|---|
  | Host floor | 6,000 x 6,000, striped every 300 cm, stripes **non-colliding** | speed and distance readable by eye |
  | `PlayerStart` | on that floor, clear of every mark, facing the gate | |
  | Three `ACallMarkActor`s | `ALPHA`, `BETA`, `GAMMA`, spaced across the host floor | set into the floor |
  | Four `AWingPostActor`s | one at each wing mouth, **non-colliding** | `HALL` / `ROSE` / `GOLD` / `SLATE` |
  | One `AGateBoardActor` | over the gate, **non-colliding**, in the same frame as the marks | reads `NONE 0` at play |
  | Backdrop | a low back wall and two differently sized landmarks, **non-colliding** | a moving camera is distinguishable from a still one |
  | Fixture | one placed `AWingHostFunctionalTest` | |
  | Four streamed sections | one per wing, **named below only as "the place that wing's fittings are kept"** | see below |

- Four more committed binaries in the same folder — the four wings, each holding **that
  wing's own `AWingFittingActor`s and nothing else**, standing at its own wing's mouth
  inside the host. The hall's begins **in** the running world; the other three begin
  **out** of it. **Their names are not printed here and they are not the wings' names**:
  each wing's own post carries the name of the place its fittings are kept, and that is
  the only place the join is written down.
- `cameras.json` (the camera-plan lane; not part of this release) — the presentation-only
  camera plan, framing the gate board and all four wing mouths. Non-gating.

**Three things are not written down anywhere you can read them, and all three have to
come out of the running world:**

1. **Which mark calls which wing.** The names the three marks show when play begins are
   staged by the level, and they are re-lettered while play is running.
2. **Where a wing's fittings are kept.** Each post's `WingName` / `SectionId` pair is
   stable and readable at play; the second half of it is nothing like the first, so it
   cannot be derived from a wing's name.
3. **How many fittings a wing holds.** The wings are different sizes and no count
   appears in this brief; the board has to report how many are actually standing.

Files that **do not exist**:

- No overlap binding, no wing bookkeeping, no code that brings a part of the level into
  the running world or takes it back out, no code that calls `Report`, no Blueprint
  subclass, no level edits. The empty submission compiles (L1 green) and FAILs L2 at the
  first step, because no called wing ever arrives in the host.
- No test source in the agent's writable path. `AWingHostFunctionalTest` lives in the
  `CraftBenchTests` module the agent can neither read nor modify.

## Verifier specification

The test runs in PIE from
`Content/Maps/t2-only-the-wing-you-called-opens/L_WingHost.umap` on the **ThirdPerson**
substrate, ticked at a fixed deterministic step (`-deterministic -FPS=<rate>`),
**twice**: once at 60 and once at 20 (`fps_legs: [60, 20]`), each in its own PIE
process. The two legs run **mirrored deals** (below), so they are not a repeat of each
other — they are two different questions under the same rule.

Verification primitive: **pie-checkpoint-sampling** plus an every-gauge-point readback of
(a) the exact multiset of `AWingFittingActor`s present in the host world, identified by the
per-instance tags baked into the committed wing packages, (b) each present fitting's
hidden-in-game flag and collision-query state, (c) the hall fittings' world transforms,
and (d) the gate board's **rendered text** — over a fixture-driven walk between the
marks.

### What identifies a fitting, and why it is not a property

`AWingFittingActor` lives in the agent-writable module, so **no `UPROPERTY` on it may
decide anything the fixture grades** — `WingLabel` is a supplied read for the *agent* and
the fixture never reads it. Identity is the per-instance `Tags` baked into the four
committed wing packages: `Fitting.HALL.1` … `Fitting.HALL.3`, `Fitting.ROSE.1` …,
`Fitting.GOLD.1` …, `Fitting.SLATE.1` … . The expected identity list — **seventeen tags,
3 / 4 / 6 / 4 across hall / rose / gold / slate**, and for the hall the three world
positions of the shared layout table — is held in the verifier-owned
fixture under `Source/CraftBenchTests/Tasks/t2-only-the-wing-you-called-opens/`, graded
from git HEAD. A tag added in the agent-writable constructor lands on **every**
fitting at once and fails `OnlyCalledWingPresent` immediately, so the obvious tamper is
self-defeating.

### Why the sizes and the join are what they are

`kWingFittings = {3, 4, 6, 4}` and `kSectionIds = {L_WingVault, L_WingLoft, L_WingKeep,
L_WingSpur}` are the two facts that keep the readout and the join load-bearing, and both
were added on 2026-08-19 after adversarial review found the earlier shape too easy:

- **Uniform three-per-wing made the board a constant.** Every gauge point sampled at the
  close of the settle window saw exactly three standing, so `Report(W, 3)` — a literal
  copied out of the prompt — satisfied the readout gate everywhere, and "count what is
  actually standing" was unobservable *by construction*. With mixed sizes any constant
  is wrong at cp1 or cp2 of **both** legs, and the count taken at the instant of the
  step is wrong at every gauge point (the wing has not arrived yet).
- **`L_Wing<WING>` made the post decorative.** `UGameplayStatics::GetStreamingLevel`
  suffix-matches case-insensitively, so `FName(*(TEXT("L_Wing") + Wing.ToString()))`
  resolved without a single world read. The section names are now unrelated to the wing
  names and are printed nowhere the agent can read, so the join exists only on the post.
- **Honest limit.** Both facts are *static* properties of committed binaries. An agent
  with shell access can, at a cost, recover them by grepping the `.umap` files for the
  baked `Fitting.<WING>.<N>` strings. That is more work than reading the world and is
  the same class of thing as anti-gaming note 6 — deliberately not special-cased. The
  fact that genuinely **varies per run** remains the mark→wing pairing, which is
  fixture-side, re-dealt mid-run and mirrored between the legs.

### The deal, and why no constant can satisfy it

The mark→wing pairing is the load-bearing fact and it is not knowable statically.
`PrepareTest` deals the three labels by calling each mark's supplied
`SetCalledWingName(FName)` — which also repaints the floating label a human reads — from
a table that lives in the verifier-owned fixture. **`GAMMA` always carries `SLATE`**, and
`GAMMA` is never stepped on, so no correct submission is ever asked to open slate.

| Leg | Deal 1 (from `PrepareTest`) | Deal 2 (re-dealt mid-run) |
|---|---|---|
| 60 Hz | ALPHA→ROSE · BETA→GOLD · GAMMA→SLATE | ALPHA→GOLD · BETA→ROSE · GAMMA→SLATE |
| 20 Hz | ALPHA→GOLD · BETA→ROSE · GAMMA→SLATE | ALPHA→ROSE · BETA→GOLD · GAMMA→SLATE |

The deal index is derived from the leg's **fixed delta time** (the runner's `-FPS`),
never from wall clock and never from randomness — same input, same deal, every run. Two
consequences, and both are the point:

1. **A hard-coded pairing is wrong at cp1 in one of the two legs**, and both legs must
   pass. It is not wrong on average; it is wrong with certainty.
2. **A pairing cached at `BeginPlay` is right at cp1, cp2, cp3 and cp3r and wrong at cp4
   and cp5**, because the same physical plate demands a different wing after the
   re-deal.
3. **The mirror carries the COUNT as well as the name.** The wings hold 3 / 4 / 6 / 4
   fittings (hall / rose / gold / slate), so cp1 wants rose's four on the fast leg and
   gold's six on the slow one, and cp2 wants the other. Any **constant** count is
   therefore wrong at cp1 or cp2 of **both** legs, and a count read at the instant of
   the step is wrong at every gauge point, because the wing has not arrived yet.

The level stages the 60 Hz leg's Deal 1 on the marks, so a human who simply presses Play
— with no fixture running — walks into a coherent, labelled building.

### The drive

Tier-1 trigger throughout (adoption review §7.1.3): **locomotion into a thing**. The
character is driven along the host floor onto a mark by the shipping per-frame
`AddMovementInput` timeline — the same path a human drives with WASD. No key press is
ever synthesised, and no behaviour is invoked by calling into the submission.

| Step | What the drive does | Gauge point |
|---|---|---|
| — | stand at `PlayerStart`, clear of every mark | **cp0** — the explicit reported baseline |
| 1 | walk onto `ALPHA` | **cp1** — 1.5 s of world game-time after the step lands |
| 2 | walk off, then onto `BETA` | **cp2** |
| 3 | walk off, then onto `ALPHA` again | **cp3** — the RE-TRIGGER: same mark, same deal, and the gates demand the **same** measured outcome as cp1 |
| — | the drive walks clear of every mark; the fixture **re-letters the marks** (Deal 2) and the floating labels visibly change | **cp3r** — 1.5 s after the re-lettering, with the character standing on nothing. The expectation is **unchanged from cp3**: re-lettering is not a call |
| 4 | walk onto `ALPHA` a third time — now showing a different wing | **cp4** |
| 5 | walk off, then onto `BETA` | **cp5** |
| 6 | walk off `BETA` onto the clear ground below it, then straight back onto `BETA` — which has **not** been re-lettered since cp5, so the step calls the wing that is already standing | **cp6** — the expectation is **unchanged from cp5**: re-stepping a mark that is already calling the standing wing changes nothing. It is the only gauge point at which a take-down and a bring-in issued against one shared handle can present, because every other step in the drive is a change of wing |

`GAMMA` is never stepped on, and `ALPHA` is stepped on three times and `BETA` three
times. **Every gauge point after a step is derived from the event,
not from a wall-clock schedule**: the settle window opens when the step lands, so a leg
that walks the same distance in a different number of frames cannot shift a gate off its
subject. The re-deal likewise fires **after cp3 has been sampled and while the character
overlaps no mark**, never on a clock, so there is no race between a re-letter and a step.

The checkpoint schedule handed to `SetCheckpointSchedule` is a dense calibration grid
plus a **SENTINEL** far past the modelled drive, because
`ACraftBenchFunctionalTest::Tick` ends the test the moment the last scheduled checkpoint
is sampled. The run-level completion is evaluated when the last drive phase completes
**and** again at the sentinel, whichever comes first, and only then does the fixture call
`FinishTest(Succeeded)`. Both numbers are **measured at Gate 10 on both legs**, not
guessed; the drive is short (five short walks) and must fit inside the 600 s per-leg L2
wall clock with room to spare.

### Settle and suppression

Nothing is judged on a frame where any of these hold. Each is a **widening** of the
disclosed contract, never a narrowing:

- less than **1.5 s** of world game-time since the step landed (the window the prompt
  discloses — a gate is evaluated at its close, not during it). It was 1.0 s until
  2026-08-19; adversarial review pointed out that 1.0 s is exactly **20 world ticks**
  on the `-FPS=20` leg, in which a full `UWorld::RemoveFromWorld` of the outgoing wing
  **and** a full `UWorld::AddToWorld` of the incoming one must both finish — both are
  time-sliced by the engine, and `UWorld::Levels` (what the fixture's `TActorIterator`
  walks) is only touched at the start of the making-visible pass and the end of the
  making-invisible one. The number was widened **in the prompt and in the fixture
  together**, in the only safe direction, and it is **still unmeasured**: Gate 10 must
  measure the real cost of a swap on the 20 Hz leg before any model result from this
  task is trusted;
- the fixture is itself re-lettering the marks (a 0.5 s window around the re-deal),
  throughout which the character overlaps no mark;
- the character is in transit and no step has landed since the last gauge point — the
  gates are gauged at cp0…cp6 and cp3r and nowhere else, so nothing is scored on a
  transit frame.

**Widening is safe in exactly one direction here.** The negative gates
(`OnlyCalledWingPresent`, `SealedWingUntouched`) are sampled at the same gauge points, so
moving a gauge point later does not weaken them, and none of the wrong answers this task
is built to catch fails on *speed* — they fail on identity, scope or the number. If the
20 Hz leg measurably needs longer than 1.5 s to settle a swap, **widen the number IN THE
PROMPT again** and re-measure the walk — never widen the fixture's window past a number
the agent was given.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64 Development"
        and "ThirdPerson Win64 Development"
```

### L2 — AFunctionalTest behavioral trace

**Gate precedence, in the order the fixture evaluates them.** At most one of 1–3 fires on
any gauge point, so a named FAIL is never a race between two of them; 4 and 5 are
independent channels and run last.

```text
1  CalledWingOpens          -- cp1..cp6 and cp3r
2  OnlyCalledWingPresent    -- cp0..cp6 and cp3r
3  SealedWingUntouched      -- cp0..cp6 and cp3r  (IN-SCENE NEGATIVE CONTROL)
4  OpenWingIsSolidAndSeen   -- cp0..cp6 and cp3r, after 1..3 have agreed
5  BoardNamesTheOpenWing    -- cp0..cp6 and cp3r, ALWAYS LAST  (VISIBLE READOUT)
```

```text
assert: CalledWingOpens -- at every gauge point after the first step, EVERY ONE of
        the fittings of the wing whose name the stepped mark was displaying AT THE
        MOMENT OF THE STEP is present in the host world, by tag. How many that is
        comes from the fixture's own per-wing table (3 / 4 / 6 / 4), which is why a
        submission that opens the right wing but only part of it fails here. The
        expectation
        comes from the fixture's OWN deal table, not from reading the mark back at
        the step -- by construction those are the same name, and
        SealedWingUntouched proves they still are, so a submission that re-letters
        a mark to suit itself diverges here instead of agreeing with itself. At
        cp3r the expectation is the wing called at cp3, UNCHANGED: re-lettering a
        mark calls nothing, so a submission that re-reads on a label change and
        swaps without a step dies here. At cp6 the expectation is cp5's, UNCHANGED:
        the mark was not re-lettered between them, so the step calls the wing that
        is already standing and nothing may change. Message names the mark, the
        wing it was showing at the step, and how many of that wing's fittings stand:
          "CalledWingOpens: mark ALPHA showed ROSE at the step; 0 of 4 ROSE
           fittings stand in the host at cp1"

assert: OnlyCalledWingPresent -- at EVERY gauge point the multiset of fittings
        present in the host world equals exactly the hall's three plus (from cp1
        onward) ALL of the currently-called wing's -- four for rose, six for gold.
        No fitting of any other wing,
        no duplicate of any fitting, and at cp0 nothing but the hall. This gate
        owns three separate wrong answers at once: load-without-unload (six
        called fittings at cp2), open-everything, and any SLATE fitting ever
        appearing -- GAMMA is never stepped on, so a slate fitting in the host is
        a wing nobody called. The never-called-wing check is FOLDED IN here rather
        than scored separately: it is entailed, and DEF-5 forbids the padding.
        Message names the gauge point, the tags that should be standing and the
        tags that are.

assert: SealedWingUntouched -- IN-SCENE NEGATIVE CONTROL, gauged at EVERY gauge
        point including cp0, and clause (a) additionally EVERY FRAME once cp0 has
        been sampled (see below). Two clauses, both disclosed ("nothing you do may
        disturb it" / "the building is not yours to rearrange"):
          (a) THE HALL. Its three fittings (the hall is the one wing whose size the
              fixture names, because its three positions are the graded control) are
              present, not hidden in game,
              collision-query-enabled and pawn-blocking, and within 1 cm of the
              LAYOUT TABLE the fixture and the map authoring script share -- not of
              a transform recorded at cp0, because cp0 is already downstream of the
              submission. This is a MATCHED TWIN in the same scene, not a temporal
              before/after -- the hall is built from the same fitting class, stands
              in the same host, is streamed exactly like the other three, and is
              indistinguishable from a callable wing to any "clear everything, then
              load the target" loop. It is the gate the owner's named wrong answer
              dies on, and it fires at cp1, the first step:
                "SealedWingUntouched: hall fitting HALL.1 absent from the host at
                 cp1 (no mark ever calls the hall and nothing may disturb it)"
              Clause (a) is ALSO evaluated on every frame once cp0 has been
              sampled, before the drive advances. That is the only thing that
              catches a hall taken out and put back INSIDE a settle window, which
              every checkpoint-only sample would miss; it can only ever catch a
              wrong answer, because a correct one never touches the hall at all.
          (b) THE HOST'S FIXED FURNITURE. The three marks, four posts and one
              board are all still present, each within 2 uu of where the level put
              it, and each still carrying the name the level gave it: MarkId on
              the marks, WingName and SectionId on the posts. The marks' CURRENT
              label is excluded from (b) and checked separately against the
              fixture's own deal -- the fixture re-letters the marks, and only the
              fixture may. This clause is what stops a submission rewriting the
              furniture to suit its own model, and it is GRADED rather than
              attributed for exactly the reason below.

assert: OpenWingIsSolidAndSeen -- at every gauge point, every present called-wing
        fitting is NOT hidden in game and has query collision enabled. This is the
        observable-spoofing ban (adoption review §5.1 rule 3): it fabricates the
        graded signal to put tag-carrying invisible or non-colliding stand-ins in
        the host, and it also catches a wing brought in without ever being made
        part of the running world, in whichever of the two ways that presents.
        Message names the fitting, the gauge point, and which of the two failed.

assert: BoardNamesTheOpenWing -- VISIBLE READOUT, and load-bearing in BOTH halves:
        at every gauge point the gate board's RENDERED TEXT equals exactly the
        EXPECTED line -- "NONE 0" at cp0, and "<EXPECTEDWING> <THAT WING'S OWN
        COUNT>" at cp1..cp6 and cp3r, where the expected wing is derived from the
        stepped mark's label AT THE STEP, never from what the submission actually
        opened, and the count is that wing's size in the fixture's own table
        (3 / 4 / 6 / 4). Asserting against the expected value rather than the
        submission's own belief keeps this independent of CalledWingOpens: an
        implementation that opens the wrong wing and reports it consistently still
        fails here. THE NUMBER IS NOT A LITERAL THE AGENT CAN COPY: no count
        appears in the prompt, the wings are different sizes, and the deals are
        mirrored, so a constant is wrong at cp1 or cp2 of both legs and the count
        taken at the instant of the step is wrong everywhere. Read from the text
        component, never from a flag. Message names the expected line and the line
        found:
          "BoardNamesTheOpenWing: the board should read 'GOLD 6' at cp2 and it
           reads 'GOLD 3'"
```

**Staging faults are attributed, not scored — and the list is drawn so that a submission
cannot reach it.** This is the load-bearing rule, not boilerplate: `BeginPlay` fires on
every placed actor *before* `PrepareTest` runs, so "whatever the world looked like when
the fixture first opened its eyes" is **already downstream of the submission** and can
never be the baseline for an attributed fault.

The line is drawn by asking one question of every check: **is the fixture's own expected
value satisfiable by any world?**

- **Attributed (`HARNESS-PRECONDITION`) — authoring faults only**, i.e. the fixture's
  table cannot be satisfied at all: no world; no possessed player character; a level that
  cannot be driven by hand (the unplayable-input check, read by property name — a level
  naming its own game mode drops both halves of Enhanced Input and would otherwise grade
  byte-identically while being uncontrollable); a `SectionId` in the fixture's table that
  names no section the persistent level declares; two of the four sections declaring the
  same package; and **a wing section that is not independently loadable AND unloadable** —
  in particular a hall section the world refuses to take out, which would make
  `SealedWingUntouched` an unfailable dead gate and the whole coupling a permissive fake.
  Every one of these is a property of the committed `.umap` set or of the substrate,
  checked against the fixture's git-HEAD table, and no C++ a submission can write changes
  any of them.
- **Graded — everything else.** A wrong actor count, a moved or renamed mark, post or
  board, a mark whose label is not what the fixture last dealt it, a missing hall fitting
  — all of these are things a submission *can* cause, so all of them are
  `SealedWingUntouched` (or `OnlyCalledWingPresent`) FAILs with a named message, never an
  attributed exit. **A staging exit that a submission can trigger is a denominator
  opt-out that costs the model nothing to buy.** **The per-instance fitting tags are
  GRADED for exactly this reason**, and deliberately so: three of the four wings are out
  of the world when `PrepareTest` runs, so their tags are not observable until after the
  submission has had its turn, and an attributed exit keyed on them would be one a
  submission could buy. A missing or duplicated tag therefore fails
  `OnlyCalledWingPresent` / `SealedWingUntouched` by name, and the *authoring*-fault gate
  for tags lives where it can be submission-proof: the map authoring script refuses to
  save a level whose seventeen per-instance tags do not read back after a load from disk.
- **Drive-side exits** (a phase overrunning its derived deadline, a step that never
  lands) stay attributed, because the drive is the fixture's own and a slow walk is not a
  model failure — but see the next paragraph.

**A harness exit can never launder a FAIL.** Before any deadline or sentinel overrun is
written off, `OnlyCalledWingPresent` and `SealedWingUntouched` are re-checked
**unconditionally** at the last gauge point that was reached — those two are the gates a
submission can trip while also stalling the drive (a fitting standing where it should not
be is solid, and solid things block a walk), so that path is closed explicitly rather
than by luck.

## Requirement-to-assertion map

| Prompt requirement | Gate that checks it | When that gate does NOT run |
| --- | --- | --- |
| the hall is open when play begins and stays open all night | `SealedWingUntouched` clause (a), every gauge point including cp0 **and every frame after cp0** | never |
| its fittings stand exactly where they stand, in plain sight and solid | `SealedWingUntouched` (transform within 1 cm, not hidden, query collision on) | never |
| rose, gold and slate begin shut, with nothing of theirs in the host | `OnlyCalledWingPresent` at cp0 — the explicit reported baseline | never |
| **the wings are not all the same size, and no count is written down** | `CalledWingOpens` (all of the called wing's fittings, 3 / 4 / 6 / 4 from the fixture's table), `OnlyCalledWingPresent` (exact multiset, duplicates included) and the number in `BoardNamesTheOpenWing` | never |
| **the place a wing's fittings are kept is named on its post and is nothing like the wing's name** | `CalledWingOpens` at cp1 — a section name built out of the wing's name resolves nothing and no fitting arrives | never |
| walking onto a mark calls the wing that mark is showing **at that moment** | `CalledWingOpens`, cp1..cp6, against the label read at the step | at cp0, where nothing has been called |
| the marks are re-lettered and the pairing must be re-read | `CalledWingOpens` at cp4 and cp5, where a `BeginPlay`-cached pairing names the wrong wing; and the mirrored 60/20 Hz deals, where a hard-coded pairing is wrong at cp1 | never |
| **re-lettering is not a call** | `CalledWingOpens` + `OnlyCalledWingPresent` at cp3r, whose expectation is cp3's unchanged | outside cp3r |
| within a second and a half the called wing is really there — **every one** of its fittings, visible, solid | `CalledWingOpens` (all present) and `OpenWingIsSolidAndSeen` (visible, solid), gauged at the close of the disclosed window | at cp0 |
| in that same second and a half the previously called wing is gone | `OnlyCalledWingPresent` (exact multiset) at cp2..cp6 | at cp0 and cp1, where there is no previous wing |
| never more than one called wing at a time | `OnlyCalledWingPresent` | never |
| a wing nobody has called never has a fitting in the host | `OnlyCalledWingPresent` — folded in, not scored separately (DEF-5) | never |
| stepping off a mark changes nothing | the gauge points straddle every walk-off; the multiset at cp2 is measured after the character has left `ALPHA` | never |
| stepping back onto a mark calls its wing again, exactly as the first time | `CalledWingOpens` + `OnlyCalledWingPresent` at cp3 vs cp1 — same mark, same deal, same demanded outcome (the §7.1.4 re-trigger) | outside cp3 |
| **if the wing a re-stepped mark is calling is the one already standing, nothing changes at all** | `CalledWingOpens` + `OnlyCalledWingPresent` at cp6, whose expectation is cp5's unchanged — the only place a take-down and a bring-in sharing one handle can present | outside cp6 |
| the board reads `NONE 0` until a wing is called | `BoardNamesTheOpenWing` at cp0 | never |
| after that, the called wing's name and how many of **that wing's** fittings are actually standing, one line of capitals, one space | `BoardNamesTheOpenWing`, exact string equality against the EXPECTED line — the name from the mark's label at the step, the number from that wing's own size | never |
| the board must be right by the end of that same second and a half, and a wing does not arrive all at once | `BoardNamesTheOpenWing` at every gauge point: a board written once at the instant of the step still reads `<WING> 0` there | never |
| do not move a mark, a post, a fitting or the board, and do not rewrite the names they carry | `SealedWingUntouched` clause (b), every gauge point: presence, within 2 uu of where the level put it, and the name it was given. Graded, never attributed — an attributed exit a submission can trigger is a free way out of the denominator | never |
| C++ under `Source/ThirdPerson/` | sandbox: a file outside the writable set is exit 4, not a graded FAIL | never |

## Reference solution metadata

- **Files touched**: 2 —
  `Source/ThirdPerson/Tasks/t2-only-the-wing-you-called-opens/GateBoardActor.h` and
  `.cpp`. The other three supplied pairs are byte-identical to the scaffold.
- **LOC**: ~150 added (about 55 of them comment), on top of the supplied board.
- **Senior-dev hours**: **2.5–4**, the lower-middle of T2. The code is small; the hours
  go into judgment, not typing:
  1. ~40 min working out that a wing is a **named part of the level** that has to be made
     part of the running world, and finding the join — a post's `SectionId` — that turns
     a wing's name into that name. Nothing in the prompt says the word; the world does,
     and **only** the world does: the place is not named after the wing, so the join
     cannot be guessed, concatenated or copied out of the brief.
  2. ~50 min on the scope decision, which is the whole task: exclusivity has to be scoped
     to **the wing that was called before**, not to everything the world knows about. The
     natural loop clears the world; the hall is in the world; the prompt says the hall
     must not be disturbed. Getting the swap perfectly right and the scope wrong is a
     graded FAIL, and it is the first thing most people write.
  3. ~40 min on the reading discipline: the mark's label must be read **at the step**,
     not cached, and the wing's section resolved from the post at the point of use. A
     cache is right three times out of five and there is no warning.
  4. ~45 min wiring the readout honestly. This is a **graded** number, not a literal: the
     wings are different sizes and no count appears in the prompt, so it has to be
     counted from the world — and a wing arrives over several frames, so the count taken
     in the step handler is the count of a wing that is not there yet. The board has to
     keep following the world until the disclosed window closes.
- **Why not T3**: no new subsystems, no assets, no editor work, no engine spelunking. It
  is one small actor's worth of gameplay code that has to be exactly right in three
  interacting places.

## Anti-gaming notes

1. **Clear every section the world knows about, then bring in the one this mark names.**
   *Failure mode*: THE locally-reasonable wrong answer, and the one a competent UE
   engineer writes first — it is the natural shape (enumerate, clear all, load target),
   it needs no memory of which wing was open, and it passes a surface reading of the
   prompt. *Defense*: the hall is a section like the others and is already in the world
   at cp0, so the first step evicts it and `SealedWingUntouched` fires at cp1 by name.
   This is the coupling doing its work: the streaming can be perfect and the *scope*
   still wrong.
2. **Bring the named wing in and never take the previous one out.** *Failure mode*: the
   cheaper cousin — it reads correct at every surface (the called wing is always there,
   visible, solid, and the board is right). *Defense*: `OnlyCalledWingPresent` at cp2,
   with six called fittings where three are allowed, naming both tag sets.
3. **Cache the mark→wing pairing at `BeginPlay`.** *Failure mode*: the obvious
   optimisation, and it is *right* at cp1, cp2, cp3 and cp3r. *Defense*: the fixture
   re-letters the marks mid-run, so the plate that opened rose three times now shows
   gold; `CalledWingOpens` fires at cp4, naming the mark, what it showed at the step, and
   what stands. The mirrored 60/20 Hz deals close the same axis against a *hard-coded*
   pairing at cp1 as well.
4. **React to the label change instead of to the step.** *Failure mode*: a plausible
   reading of "read the mark, never assume a pairing" — poll the label and swap whenever
   it moves. *Defense*: cp3r is gauged 1.5 s after the re-lettering with the character
   standing on nothing, and its expectation is cp3's unchanged. The prompt says
   re-lettering is not a call, in as many words.
5. **Order the take-down and the bring-in as two latent actions sharing one handle.**
   *Failure mode*: an ordinary slip — two latent calls issued with the same identifying
   handle, so one of them is silently discarded and never completes. *Defense*:
   `OnlyCalledWingPresent` or `CalledWingOpens` at whichever gauge point the collision
   bites, naming exactly which tags are standing that should not be, or missing that
   should be. **cp6 exists for the worst case of this**: the drive steps off `BETA` and
   straight back onto it without a re-letter in between, so the take-down and the
   bring-in name the *same* section — the one step at which the two calls cannot be
   told apart by their arguments. Every other step in the drive is a change of wing,
   where a discarded call still leaves the two sections distinguishable and the slip can
   hide.
6. **Spawn look-alike fittings instead of bringing the wing in.** *Failure mode*:
   fabricating the graded signal. *Defense*: identity is the per-instance tags baked into
   the committed wing packages together with, for the hall, the positions in the shared
   layout table; and `OpenWingIsSolidAndSeen` refuses invisible or non-colliding stand-ins.
   Labelled honestly: a spawner that reproduced all seventeen exact tags at exact transforms and
   destroyed them on cue would be *observably byte-identical* and is therefore not
   special-cased into a hard FAIL (§5.1 rule 3) — it is simply a great deal more work
   than the answer, and none of it can be derived from anything in the writable tree.
7. **Set a correct internal state and never move any content.** *Failure mode*: modelling
   the swap and forgetting the world. *Defense*: nothing private is ever graded. Every
   gate is a statement about actors standing in the host world and about the text on the
   board; the supplied board deliberately carries no state of its own.
8. **Write the board in the step handler and never look again.** *Failure mode*: THE
   locally-reasonable wrong answer, and the minimal shape a competent engineer writes:
   one function on the overlap that reads the mark, swaps the sections and reports. It
   is right about the wing and wrong about the number — at the instant of the step the
   called wing has not arrived, so an honest count reads **zero** and the board says
   `<WING> 0` for the rest of the run. *Defense*: `BoardNamesTheOpenWing` at cp1, naming
   the expected line and the line found. The prompt discloses both halves of this in as
   many words — the board "must be right by the end of that same second and a half,
   every time", and "a wing does not arrive all at once" — so nothing here is a
   sub-second transient being graded: the gauge point is at the CLOSE of the disclosed
   window, and a board that has caught up by then passes however it got there.
9. **Print a constant count — `<WING> 3`, or whatever the first wing turned out to
   hold.** *Failure mode*: treating the number as a literal rather than as an
   observation. *Defense*: the wings hold 3 / 4 / 6 / 4 fittings and the two legs deal
   the marks mirrored, so cp1 wants rose's four on one leg and gold's six on the other.
   **Any** constant is wrong at cp1 or cp2 of **both** legs, and both must pass. This is
   the finding that closed the 2026-08-19 review: with three fittings in every wing the
   readout carried no information the prompt had not already supplied.
10. **Build the section's name out of the wing's name.** *Failure mode*: assuming the
   naming convention that every other level in the world seems to follow. *Defense*: the
   place a wing's fittings are kept is not named after the wing, and the names appear
   nowhere in the brief; the join exists only on the post. A guessed name resolves
   nothing, no fitting arrives, and `CalledWingOpens` fires at cp1. (Before 2026-08-19
   the sections were `L_Wing<WING>` and `UGameplayStatics::GetStreamingLevel`'s
   case-insensitive suffix match made the post decorative.)
11. **Re-letter the marks yourself, or move a post so the join comes out easier.**
   *Failure mode*: anti-gaming rather than a plausible first pass — pin every mark to one
   wing and the pairing problem disappears. *Defense*: `CalledWingOpens` takes its
   expectation from the fixture's own deal table and never reads the mark back, so a
   rewritten label makes the submission disagree with the grade instead of with itself;
   and `SealedWingUntouched` clause (b) names the moved or renamed piece of furniture at
   the very next gauge point. Neither routes to an attributed exit — a submission must
   never be able to buy its way out of the denominator by breaking the staging.
12. **Edit the fixture, or write outside the module.** *Failure mode*: the standard two.
   *Defense*: `CraftBenchTests` is graded from git HEAD and review-gated on commit, so an
   on-disk edit never reaches the grade; a submission file outside `Source/ThirdPerson/`
   is exit-4 SANDBOX-REJECT, which is a scope breach and not a graded 0.

## Hidden invariants

- **`WingLabel` is a read for the agent and never for the fixture.** It lives on an
  agent-writable class, so a submission is free to rewrite it — and doing so changes
  nothing about the grade, because identity is the per-instance tag baked into the
  committed wing package. The board's number is likewise graded against the called
  wing's EXPECTED size, not against whatever the submission counted — so a submission
  that rewrites `WingLabel` to make its own counting easier still has to arrive at the
  right number.
- **The wings are different sizes, and that is what makes the readout load-bearing.**
  3 / 4 / 6 / 4 across hall / rose / gold / slate. Nothing in the prompt says a number,
  and the mirrored deals mean the required count differs between the two legs at the
  same gauge point. Both halves of the board line therefore carry information: the name
  is the pairing read, the number is the arrival read.
- **A static world fact is still a world fact.** The per-wing sizes and the wing→section
  join do not change between runs; an agent with shell access could in principle recover
  both by grepping the committed `.umap` binaries for the baked `Fitting.<WING>.<N>`
  strings. That is deliberately not special-cased (same reasoning as anti-gaming note 6):
  it is strictly more work than reading the world, and the fact that genuinely **varies
  per run** — the mark→wing pairing — is fixture-side and cannot be recovered from any
  committed byte.
- **No gate ever reads a streaming object, a loaded flag or a visible flag.** The two
  corpus checks that did (`NamedSectionLoaded`, `NamedSectionVisible`) were rewritten as
  world-content observables per DEF-1 — grading them would police the route and would
  also punish a legitimate non-streaming implementation that got the fittings genuinely
  standing in the host. Everything is read off the host world's actors.
- **A section brought in but never made part of the running world yields ZERO tagged
  actors**, so `CalledWingOpens` catches it; a section whose actors arrive hidden or
  non-colliding yields the wrong kind of actor, so `OpenWingIsSolidAndSeen` catches it.
  The design is correct either way, and `notes.md` records which of the two the engine
  actually does here once the map batch has run.
- **The fixture grades against what it DEALT, never against what it reads back.** The
  mark's live label and the fixture's deal table are the same fact right up until a
  submission writes one of them, and the moment they part company the deal table is the
  one that counts. This is what keeps the load-bearing world-read honest: the agent has
  to read the world, and cannot make the world agree with a shortcut.
- **cp6 is the same-mark re-step, and its expectation is cp5's unchanged.** `BETA` is not
  re-lettered between them, so the step calls the wing that is already standing and the
  prompt's "nothing changes at all" is a measured statement. It is the only gauge point
  at which a take-down and a bring-in issued against one shared handle name the same
  section, which is the only way that slip can present.
- **`GAMMA` always carries `SLATE`, in both deals of both legs.** Slate therefore exists
  only ever as a never-called wing, which is what makes "a wing nobody has called must
  never have a fitting in the host" a *measured* statement rather than a slogan — and it
  is why no correct submission is ever asked to open it.
- **`fps_legs: [60, 20]` runs the whole drive twice with MIRRORED deals**, in two PIE
  processes. This is not a repeat: it is the axis that makes a constant answer wrong at
  the very first gauge point, and it closes the "learn the pairing from a previous run's
  captured log" route at zero extra cost, since both legs already run.
- **The empty submission's first violation is the MISSION gate, by construction.** The
  supplied board ships already displaying `NONE 0`, so cp0 passes cleanly as the
  explicitly reported baseline (§5.1 item 6) and the first failure is `CalledWingOpens`
  at cp1. Without that shipped default an empty submission would die first at cp0 on a
  blank board — a true failure, but a much weaker signal about what the task measures.
  The board gate keeps full teeth from cp1 onward, where it must have changed.
- **Dead-gate audit (§5.1 item 4).** An empty submission passes `OnlyCalledWingPresent`,
  `SealedWingUntouched`, `OpenWingIsSolidAndSeen` and `BoardNamesTheOpenWing`-at-cp0 for
  free. That is what negative-control and baseline assertions are *for*, and it costs
  nothing: the verdict is all-gates-must-pass with no partial credit, and per §5.3 the
  corpus's k/N score is discarded, so there is no denominator to inflate.

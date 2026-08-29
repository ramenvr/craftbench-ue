---
id: t3-your-last-life-ends-the-run
substrate: ThirdPerson
set: craftbench-public
tier: T3
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_LifeRun :: ALifeRunTerminalFunctionalTest"]
fps_legs: [60, 20]
---

# t3-your-last-life-ends-the-run

Three runners on one floor, each with a finite budget of lives painted on its own
marker, a patch of crumbling ground that spends one life per crossing, and a
finish disc that spends none but only opens to a runner still holding at least
the number painted on the disc itself. Two questions, and **they are shaped
differently** — which is the whole task:

- **Which crossing is the last one**, and what happens on that one crossing,
  which is *not* what happens on every other one: the runner is **not** sent
  home, its row goes dark, its word latches, and from then on nothing in the
  level can move it or change it again.
- **When the goal opens.** The ground is a *moment*: it costs on the step that
  carries a runner onto it and never again while it stands there. The finish is a
  *condition*: standing on it holding enough wins — and that can become true
  **with nobody moving at all**, because the disc's own number came down or the
  runner's board went up. Both numbers are painted on the world and both are
  re-painted mid-run, with nothing to announce either.

> **Built against the 2026-08-18 difficulty bar.** Three subsystems that
> genuinely interact across actor boundaries — a ledger derived live from a board
> that moves, an admission rule on a *second* moving world number that the ledger
> feeds, and a terminal latch that both decide and that then gates the ground,
> the finish and the board back — so A-right/B-wrong FAILs a named gate in every
> direction. The locally-reasonable wrong answers are **code-shape errors, not
> comprehension errors**: modelling the finish the way the prompt says to model
> the ground (an event, not a standing condition) passes every arrival check and
> never wins a run; measuring the goal against the *board* instead of against
> what is *left* is let straight through on the first arrival; and `>` where the
> prompt says *at least* loses the 60 Hz leg alone. Each is written down in
> **Anti-gaming notes** and each is caught by a different named gate. Every
> load-bearing number is read off the world, staged differently per framerate
> leg, and re-painted mid-run, so no constant survives the first judged frame.

## Primary concept

- `game-mode-and-game-state` — the rules of a run and the state of a run: a life
  budget, a terminal win/lose answer, and who owns each
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/game-mode-and-game-state-in-unreal-engine)

The load-bearing behaviour is **a per-participant terminal state machine fed by a
ledger that is derived, not counted** — and the lesson the grade turns on is
*whose* state it is. The grade never asks *how*: a `Tick` on the runner, a timer,
a component, a director actor, or state parked on the level's own rules object
all pass identically, **provided each runner's answer is its own**. That proviso
is the task: the tutorial shape for "lives and game over" is one counter and one
flag for the level, and this level holds three runs at once.

## Composed concepts

| Concept | Why it is load-bearing here |
|---|---|
| `game-mode-and-game-state` (https://dev.epicgames.com/documentation/en-us/unreal-engine/game-mode-and-game-state-in-unreal-engine) | Primary. A life budget and a mutually-exclusive, permanent win/lose answer — held **per runner**, in a level whose obvious owner of "the run" is shared. |
| `actor-lifecycle` (https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-actor-lifecycle) | Two runners are placed and one is spawned when play begins; the lamps and the word must be right **from the first frame of play**, not from the first death. The markers exist before any of them. |
| `ps-uproperties` (https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-uproperties) | The life budget is a property **on the marker** and what the goal asks for is a property **on the finish**, both re-written while the run is going, on two different actors. Anything that reads either once is wrong from the first re-paint. |
| `collision-overview` (https://dev.epicgames.com/documentation/en-us/unreal-engine/collision-in-unreal-engine---overview) | Both triggers are locomotion into a query-only volume, and **the two have opposite temporal shapes**: the crumbling ground is an **edge** (entering costs one life once, however long the runner then stands in it) while the finish is a **standing condition** (it opens whenever the runner on it is holding enough, including on a frame nothing was walked onto). The natural implementation writes both as overlap events and loses the win leg. |
| `movement-components` (https://dev.epicgames.com/documentation/en-us/unreal-engine/movement-components-in-unreal-engine) | A runner with lives left is put back on its own marker and then **let go of** — no snap-back, no second teleport — while the runner that ran out is left exactly where it fell. |
| `ps-timers` (https://dev.epicgames.com/documentation/en-us/unreal-engine/gameplay-timers-in-unreal-engine) | Every deadline in the prompt is wall time (1 s to come back, half a second for everything else) and the fixture runs at 60 Hz and 20 Hz, so a frame count fires at the wrong moment on one of the two legs. |

**Production pattern.** This is the arcade *lives-and-continues* loop with an
exclusive terminal: a finite stock of lives, a hazard that spends exactly one per
contact, a respawn while stock remains, a **game over on the spend that empties
it**, and a goal that ends the run the other way — first outcome wins and latches.
Two public, verifiable instances of the composition:

1. Epic's own **Lyra Starter Game** — publicly documented and shipped with UE 5
   (https://dev.epicgames.com/documentation/en-us/unreal-engine/lyra-sample-game-in-unreal-engine)
   — keeps per-participant elimination/respawn bookkeeping on that participant's
   own state object and the match-wide phase separately, which is exactly the
   ownership split this task grades; a single shared counter is the specific
   thing that architecture exists to avoid.
2. Epic's own **Game Mode and Game State** documentation (cited above) states the
   division in as many words: rules and score/lives that belong to *the match* on
   the shared object, and per-player state on the player's own. The failure this
   task is shaped to catch is putting a **per-player** budget on the **shared**
   object, which the same page warns against.

**How the three interact, and where a fix in one breaks another.** The ledger
feeds the latch (the ledger's answer at the moment of a death is what decides
whether that death was the last one) **and it feeds the goal's admission rule**
(the ledger's answer at every moment a runner stands on the disc is what decides
whether the disc is open to it); the latch feeds *back* over the ground, the
finish and both boards (an ended run's ground spends nothing and returns nobody,
an ended run's finish does nothing, an ended run's re-painted marker changes
nothing). Four wrong answers, four named gates, four different diagnoses:

- ledger right, latch wrong → a runner keeps coming back past zero —
  `TheLastLifeEndsTheRun`;
- latch right, ledger wrong (a countdown latched at the start) → the run ends at
  the wrong crossing — `TheBoardIsReadWhenItMatters`, and then
  `TheLastLifeEndsTheRun` at the wrong one, **and** the win leg is let through or
  held out at the wrong instant — `TheGoalOnlyOpensToWhatItAsksFor`;
- ledger and latch right, the goal modelled as an **event** rather than a standing
  condition → the win-leg runner stands on the disc while the disc comes down to
  what it is holding and nothing happens, because no overlap fired —
  `ReachingTheGoalWinsAndSpendsNothing`;
- all three right but owned at the level rather than the runner → a runner nothing
  ever touched goes dark — `TheBystanderIsUntouched`.

## Prompt given to the agent

> Three runners stand at the near end of one long striped floor, each on its own
> painted marker disc. Part way down the floor there is a patch of crumbling
> ground the width of the lane; past it, at the far end, a wide finish disc.
> Distances here are measured **flat along the floor** — how tall anybody is has
> nothing to do with any of it.
>
> **Whose marker is whose.** When the run opens, each runner is standing on its
> own marker. The disc under a runner's feet at that moment is **that runner's
> own marker for the rest of the run**, wherever the runner later ends up
> standing.
>
> **Lives.** A number is painted on each runner's own marker — the lives that
> runner starts the run with. It is never more than six and never less than one,
> and the three runners are not painted the same. A runner's remaining lives is
> always **the number currently painted on its own marker, minus the number of
> times the crumbling ground has claimed it, and never less than zero**. Six
> lamps float in a row above each runner and they are the only place remaining
> lives are shown: exactly that many lit, counted from one end of the row, and
> the rest dark. The lamps start dark and nothing lights them — getting every row
> right from the first moment of play is part of the work.
>
> **A marker can be re-painted while that run is still going, and nothing
> announces it.** Whatever a marker says at the moment you need its number is the
> number: re-painting changes at once how many of that runner's lamps are lit,
> and it changes which death is that runner's last one. **Re-painting never
> claims anybody**: only the crumbling ground ever takes a life, and only the
> finish disc ever wins a run.
>
> **Deaths.** Walking onto the crumbling ground claims a runner. It is a moment,
> not a length of time: walking on costs one life once, however long the runner
> then stands there; stepping off and walking on again costs another.
>
> - If that runner still has lives left afterwards, it is back standing on **its
>   own** marker within **1 second**, and from then on it is free to walk away —
>   nothing may pull it back. Standing "on" a marker means within **120 cm** of
>   that marker's centre.
> - If that death leaves it with **no lives left**, that run is over and lost.
>   Nobody comes back for it: the runner is **left standing where the ground
>   claimed it** — within **150 cm** of that spot — and **nothing of yours ever
>   moves it from there again** (nor holds it there — see *a runner is always a
>   body that can be walked*, below); and within **1 second** every one of its
>   lamps is dark and its word reads lost.
>
> **The finish.** A number is painted on the finish disc too — how many lives a
> runner has to still be holding for the disc to let it through. A runner
> standing on the disc while holding **at least** that many wins that run, within
> **half a second**. A runner standing on it holding **fewer** is not through and
> nothing happens to it at all: it is simply still running, and it may stand
> there as long as it likes. Anywhere on the painted disc counts as being on it.
> **Winning spends nothing**: that runner's lamp row stays lit exactly as it was
> on the step before it won.
>
> **The disc's number is re-painted while runs are going too, and nothing
> announces that either.** It can go up or it can come down. So what the disc
> asks is not *did you step on* — it is *are you holding enough right now*, and
> that is a question with an answer at every moment a runner is standing there.
> If either number moves while a runner stands on the disc and leaves that runner
> holding enough, **that runner has won** — within half a second, and without
> anything having to be walked onto again. And a runner holding enough is
> measured against the lives it has **left**, never against the number painted on
> its marker.
>
> **A run that has ended stays ended.** Won or lost, that runner's lamps and its
> word never change again, whatever happens afterwards — walking onto the
> crumbling ground again costs it nothing and never moves it, walking onto the
> finish disc again does nothing whether or not it is holding enough, and
> re-painting its marker or the disc's number does nothing. A run is won or lost,
> never both, and whichever came first is the one that stands.
>
> **A runner is always a body that can be walked.** Putting a runner back on its
> own marker after a death is the one and only time anything of yours moves a
> runner. Apart from that one move, nothing of yours may hold a runner where it
> is, pin it down, or put it back where it was — not while its run is going, and
> not after its run has ended either. An ended run is never **moved by you**
> again; it is not **nailed down**. If something else walks that body somewhere
> later, it goes, it stays where it is left, and its run is still over exactly as
> it was.
>
> **What each runner reads.** A word floats above each runner beside its lamps.
> It reads `RUNNING` while that run is going, `WON` once that runner has
> finished, and `LOST` once that runner has run out. It starts reading none of
> the three — setting it right from the first moment of play is part of the work.
> It is read by taking the first run of letters in the text, so `LOST` and
> `LOST!` both read as lost.
>
> **Each runner keeps its own.** A runner's lives, its lamp row and its word
> belong to that runner alone. One runner dying, running out or finishing must
> never change another runner's lamps, another runner's word, or move another
> runner: a runner that nothing ever touches stays within **40 cm** of its own
> marker, keeps lit exactly the lamps **its own marker** calls for, and is still
> reading `RUNNING` when every other run is over. Nobody is ever replaced
> either — the three runners standing on the markers when the run opens are the
> same three that are standing in the level when it is over.
>
> **Half a second** is all the time any of this has to catch up after anything
> changes.
>
> None of it is one-shot. The crumbling ground claims runners many times over in
> a single run and the finish disc is walked onto more than once, and both must
> behave the same way the second, third and fourth time as they did the first.
>
> The floor is not yours to rearrange. Do not move the runners, their markers,
> the crumbling ground or the finish disc, and do not re-paint any of the numbers
> yourself — not a marker's, and not the finish's. Keep the markings the level
> put on the things already standing in it, too: they are how the level tells one
> thing from another, and a runner, marker, patch or disc that loses its marking
> stops being one of the level's. Everything a run needs in order to *show* its
> state is already built and working: each runner has a lamp row you can set and
> a floating word you can set. Nothing decides when to set either of them. Because the floor
> itself is fixed, whatever does the deciding has to live on something already
> standing in it — a runner, a marker, the ground, the finish, or the level's own
> rules.
>
> Write your solution in C++ under `Source/ThirdPerson/` — the project's gameplay
> module and the only place a submission is read from; work written anywhere else
> is not graded. Do not edit the level, any config file, or any test file.

## Workspace state pre-task

**Deliverable root: `Source/ThirdPerson/`** (the agent-writable runtime module on
this substrate). `Source/CraftBenchTests/` is deny-listed and a submission file
under it is a SANDBOX-REJECT (exit 4), not a graded FAIL; so are `Content/Maps/`,
`Content/ThirdPerson/`, `Content/Characters/` and every `Config/` file (no
`config_allow` is declared by this task). There is deliberately no
`deliverable_root:` front-matter key — it is not in
`tools/verify-single/spec.py::_KNOWN_KEYS` and a spec carrying one would fail to
parse — so the root is stated here and in the prompt instead.

Files that **exist** under `Source/ThirdPerson/`:

- The stock UE 5.8 Third Person C++ template sources. No edit needed.
- **Every one of the five supplied classes tags itself in its constructor**
  (`LifeRunner`, `LifeMarker`, `CrumbleGround`, `FinishDisc`), and the two placed
  runners carry a second tag each, authored in the level. Those tags are how the
  level tells one thing from another. **Keep them**: a rewrite that drops one
  takes that actor out of the level's reckoning, and the level notices.
- `Tasks/t3-your-last-life-ends-the-run/LifeRunnerCharacter.h` / `.cpp` —
  `class THIRDPERSON_API ALifeRunnerCharacter : public AThirdPersonCharacter`,
  tagged `LifeRunner`. Concrete (the stock template character is abstract and
  unspawnable). Supplied and **working**:
  - a mannequin body and its animation from the read-only `/Game/Characters/`
    pool, and the four stock input actions loaded in the constructor, so a person
    pressing Play gets something they can actually walk around with;
  - `LampBulbs` / `LampGlows` — a row of **six** lamps floating over the head,
    all dark;
  - `UFUNCTION(BlueprintCallable) void SetLitCount(int32)` — lights the first
    `Count` lamps of the row and puts the rest out, changing the glow **and** the
    bulb's look in one call so what a person sees and what the row says can never
    disagree. Values outside `0..6` are pulled back into range;
  - `UFUNCTION(BlueprintPure) int32 GetLitCount() const` — counted off the lamps
    themselves;
  - `WordText` — the word floating beside the row, authored as the placeholder
    `-`; `SetStateWord(const FString&)` / `GetStateWord()`.
  - **There is deliberately no "lives remaining" property anywhere on this
    class**, and nothing calls either switch. The lamp row is the only place a
    runner's remaining lives is ever shown, so there is no ungraded number a
    submission can set instead of doing the work.
- `Tasks/t3-your-last-life-ends-the-run/LifeMarkerActor.h` / `.cpp` —
  `ALifeMarkerActor`, tagged `LifeMarker`. A flat 300 cm disc with the number
  painted on it. Supplied:
  `UPROPERTY(EditAnywhere, BlueprintReadWrite) int32 PaintedLives`, and a `Tick`
  that keeps the painted number and `PaintedLives` the same thing at all times.
  **Read it; it is not yours to write.** The three placed markers are not painted
  the same.
- `Tasks/t3-your-last-life-ends-the-run/CrumbleGroundActor.h` / `.cpp` —
  `ACrumbleGroundActor`, tagged `CrumbleGround`. A flat patch with
  `PatchVolume`, a query-only box that overlaps everything and blocks nothing, so
  a runner walks straight over it and is never pushed or stopped by it. **It does
  nothing about what it notices.**
- `Tasks/t3-your-last-life-ends-the-run/FinishDiscActor.h` / `.cpp` —
  `AFinishDiscActor`, tagged `FinishDisc`. A wide painted disc with
  `UPROPERTY(EditAnywhere) float DiscRadiusUu` — how far out from the centre
  counts as standing on it, and the width the disc is drawn at — plus a
  query-only `DiscVolume` of the same reach, and
  `UPROPERTY(EditAnywhere, BlueprintReadWrite) int32 DemandedLives` — the number
  painted on the disc's face, with a `Tick` that keeps the painted number and
  `DemandedLives` the same thing at all times. **Read it; it is not yours to
  write.** **It does nothing about what it notices.**
- `Tasks/t3-your-last-life-ends-the-run/LifeRunGameMode.h` / `.cpp` — a game mode
  whose constructor sets `DefaultPawnClass = ALifeRunnerCharacter::StaticClass()`
  and re-states `PlayerControllerClass` as the template's
  `BP_ThirdPersonPlayerController` (which is what carries `IMC_Default`). The
  map's world settings select it, so play begins with one runner spawned and
  possessed on its own marker — the same runner a person drives with WASD and the
  same one the verifier drives.

The staged scene,
`Content/Maps/t3-your-last-life-ends-the-run/L_LifeRun.umap` (committed binary;
the agent does not author maps):

| Element | Placement | Notes |
|---|---|---|
| Floor | 9,600 x 5,600 cm, top face at Z = 0, striped every 400 cm of length | stripes **non-colliding**, so distance and speed read by eye |
| Three markers | `ALifeMarkerActor` at (800, -1100), (800, 0), (800, +1100) | one per lane, 1,100 cm apart; **non-colliding** |
| PlayerStart | on the first marker, facing down the floor | the spawned runner arrives standing on its own marker |
| Two placed runners | `ALifeRunnerCharacter` on the other two markers | told apart by per-instance actor tags authored **in the map**, never in a constructor |
| Crumbling ground | `ACrumbleGroundActor` at (3600, 0); patch 800 cm along the floor x 3,000 cm across it | spans every lane, so no runner can walk past it |
| Finish disc | `AFinishDiscActor` at (7600, 0), `DiscRadiusUu` and `DemandedLives` authored | 2,800 cm clear of the crumbling ground; the number on its face is re-staged per leg |
| Backdrop + landmarks | a low back wall and two differently sized posts, **non-colliding** | a moving camera is distinguishable from a still one |
| Fixture | one placed `ALifeRunTerminalFunctionalTest` | |

**No painted number appears in this section or in the prompt.** The three markers
and the finish carry numbers authored in the level, they are readable on the
discs themselves, and they are not the numbers the run is graded against — see
*Verifier specification*. Everything except the floor is non-colliding, so nothing in the
level can push a runner anywhere.

Files that **do not exist**:

- No life ledger, no death, no return, no terminal state, nothing that decides
  whether the finish is open to a runner, no code that lights a lamp or writes a
  word, no Blueprint subclass, no level edits. The empty submission compiles
  (L1 green) and FAILs L2 at the **first judged frame**,
  because every lamp row is dark while every marker says lamps should be lit, and
  every word still reads its placeholder.
- No test source in the agent's writable path. `ALifeRunTerminalFunctionalTest`
  lives in the `CraftBenchTests` module the agent can neither read nor modify.

## Verifier specification

The test runs in PIE from
`Content/Maps/t3-your-last-life-ends-the-run/L_LifeRun.umap` on the
**ThirdPerson** substrate, ticked at a fixed deterministic step
(`-deterministic -FPS=<rate>`), **twice**: once at 60 and once at 20
(`fps_legs: [60, 20]`), each in its own PIE process. Every deadline in the prompt
is wall time and the shortest is half a second, so a frame count fitted to 60 Hz
fires at the wrong moment at 20 Hz.

Verification primitive: **pie-checkpoint-sampling** plus an every-frame readback
of each runner's **lamp glows** and **word text** — what a reviewer sees — over a
fixture-driven walk, compared against the fixture's own running model of the whole
rule. Movement is the shipping per-frame `AddMovementInput` timeline (Tier 1 of
the standard input driver; 37 shipping ThirdPerson fixtures already use it, and
`MudWadeFunctionalTest` already drives **two** characters from one fixture).

### What the fixture reads, and what it never reads

- **Lit count** is counted off the runner's six `UPointLightComponent`s named
  `Lamp0..Lamp5`, as *intensity > 0* — never `GetLitCount()`, which lives on a
  class the submission may rewrite, and never any flag.
- **The word** is the `UTextRenderComponent` named `WordText`, compared as the
  **first run of letters** in its string, ASCII-only and case-insensitively
  (a widening of the disclosed contract, never a narrowing).
- **The painted numbers** are `PaintedLives` read off each marker and
  `DemandedLives` read off the finish, both by reflection (`FIntProperty` by
  name), live, every frame — and both written the same way when the fixture
  re-paints, so an overridden setter cannot intercept the staging.
- **Nothing private is ever read.** The fixture has no access to any tally, latch
  or countdown a submission keeps, and does not want one: every gate is a
  statement about lamps, words and positions.

### The fixture runs the same rule

Every frame the fixture re-reads all three markers' painted numbers **and the
finish's own number** live and steps its own model per runner: deaths counted by
**its own** geometric edge detection (the runner's capsule centre crossing the
patch box expanded by the capsule radius in the plane — the earliest instant any
part of the runner is over the patch), a remaining count of
`max(0, painted - deaths)`, and the same terminal rule — including the goal's
admission rule, which is evaluated as a **standing condition** (`on the disc AND
remaining >= what the disc asks for`) and never as an arrival edge. The arrival
edge is still counted, because that is what a conflicting event is counted from.
Every gate compares the level's visible state against that model.

**Why the two models cannot drift apart.** (1) The predicate is disclosed in full
and measured flat. (2) Every crossing is walked **head-on and deep**: the drive
stages 400 cm clear of the patch face it is approaching and then walks at the
patch's own centre line, 400 cm inside — so the boundary is crossed once, briskly,
and no frame of sampling order can add or drop a crossing. (3) The fixture arms at
the EARLIEST of the two honest entry models (the box grown by one capsule radius)
so it can never notice a crossing later than a submission does, and it keeps
driving until the capsule centre is inside the PLAIN box so it can never notice one
earlier either — which matters, because the character coasts only ~28 cm after
input is released, less than the 42 cm capsule radius, so a drive that let go at
the grown box would leave a point-in-box answer standing outside the patch, never
claimed at all. (4) A still-running runner within **160 cm** OUTSIDE
either trigger's edge is not judged at all — the band in which the two models
legitimately disagree is about 42 cm of travel, ~0.09 s at the template's walk. The
band is one-sided on purpose: once the capsule centre is inside, every honest answer
agrees it is inside, so banding the inside too would only hide a runner LEFT LYING IN
THE PATCH — the one submission `WhileLivesRemainYouComeBackToYourMarker` exists to
name. (5) `PrepareTest`
refuses to start unless every marker, the patch and the disc clear each other by a
real margin, and unless every phase of the drive's route has floor under it,
nothing blocking it, and no non-crossing segment that walks back onto the patch.

### Per-leg staging — the load-bearing numbers are NOT in the map

`PrepareTest` re-paints all three markers to that leg's values before the drive
starts, and re-paints two of them again mid-run. The leg is selected from the
run's own framerate (the `-FPS=<rate>` the runner always passes, with the world's
fixed timestep as the fallback; >= 40 is the 60 Hz leg, 10..39 the 20 Hz one, and
anything else is a named staging fault rather than a guess), so the two PIE
processes run different numbers; a submission cannot mine the answer out of the
committed `.umap`, and a hard-coded life count is wrong on at least two of the
three runners from the first judged frame.

| | 60 Hz leg | 20 Hz leg |
|---|---|---|
| **A** — the loss leg (the spawned, possessed runner) | painted **3**, re-painted **up** to **4** after its first crossing | painted **2**, re-painted **up** to **4** after its first crossing |
| A's lit row, crossing by crossing | 3 · (d1) 2 · (re-paint) 3 · (d2) 2 · (d3) 1 · (d4) **0 = LOST** | 2 · (d1) 1 · (re-paint) 3 · (d2) 2 · (d3) 1 · (d4) **0 = LOST** |
| **B** — the win leg (placed) | painted **5**, re-painted **down** to **3** after its first crossing | painted **6**, re-painted **down** to **5** after its first crossing |
| B's lit row, crossing by crossing | 5 · (d1) 4 · (re-paint) 2 · (d2) **1, and it reaches the finish holding 1** | 6 · (d1) 5 · (re-paint) 4 · (d2) **3, and it reaches the finish holding 3** |
| **The finish's own number** | asks **3**, re-painted **up** to **5** while B stands on it, then **down** to **1** | asks **5**, re-painted **up** to **6** while B stands on it, then **down** to **2** |
| B's two arrivals and its win | arrives holding 1 against 3 — **not through**; still 1 against 5 — **not through**; the disc comes down to 1 — **WON with 1 lit, standing still** | arrives holding 3 against 5 — **not through**; still 3 against 6 — **not through**; the disc comes down to 2 — **WON with 3 lit, standing still** |
| **C** — the bystander (placed, never driven, never re-painted) | painted **6**, six lamps lit all run | painted **3**, three lamps lit all run |
| Both ended markers, re-painted a last time (must change nothing) | A's -> 1, B's -> 2 | A's -> 6, B's -> 1 |

No two markers ever read the same number at any instant on either leg
(60 Hz: 3/5/6 -> 4/5/6 -> 4/3/6 -> 1/2/6; 20 Hz: 2/6/3 -> 4/6/3 -> 4/5/3 ->
6/1/3). A countdown latched at the start of play ends A's run **one crossing
early** on the 60 Hz leg and **two crossings early** on the 20 Hz leg, and thinks
B still has spare lives it does not have.

**Three properties of the finish's staging, each of them load-bearing and each
enforced by `ValidateStagingTable` rather than trusted.** (1) B **arrives short**
on both legs and stays short across the first re-paint, so the standing-win is
the only way the win leg can ever be won and a leg that skipped it FAILs as a
staging fault, not as the submission. (2) What the disc asks for on arrival is
**exactly the number painted on B's own marker** on both legs (3 against a board
of 3; 5 against a board of 5), so a submission that compares the disc against the
*board* rather than against what the runner has *left* is let straight through on
the first arrival and is named for it. (3) The last move lands **exactly on** what
B is holding at 60 Hz (1 against 1) and **strictly below** it at 20 Hz (2 against
3), so `>` where the prompt says *at least* wins the 20 Hz leg and loses the 60 Hz
one — a framerate-split verdict that reads as an off-by-one and is one.

**Safety rules on every re-stage, so it can never manufacture a false FAIL.** The
finish's own number is written by the same reflection path and under the same
quiet window as a marker's, and it is never moved anywhere near a death or a
crossing — both of its moves land while the win-leg runner is standing still on
the disc, minutes after its last crossing. A
marker is never re-painted to a value at or below the deaths that runner has
already suffered (the prompt promises a re-paint never claims anybody, so the
fixture never creates the ambiguous case); no re-paint lands within 0.75 s of that
runner's own death or terminal event; every value stays inside 1..6 and the three
markers never read the same number at any instant; and **every gate on every runner
is suppressed for 0.6 s** from the moment a re-paint phase opens and again for
0.6 s from the write itself (the drive holds every runner still for at least 2.2 s
before a re-paint phase opens, so no re-paint can land near a death) — a widening of
the disclosed half-second settle, never a narrowing.

### What the map must stage (the fixture's contract with the level)

Everything here is checked in `PrepareTest` and reported as a
`HARNESS-PRECONDITION`, so the map author gets a named fault rather than a
mysterious FAIL. Nothing in this list is disclosed to the agent, because nothing in
it is the agent's to satisfy.

- Three `ALifeMarkerActor`s tagged `LifeMarker`, at least 480 cm apart, each at
  least 600 cm clear of the patch. The fixture sorts them by **Y ascending** and
  calls them near / middle / far.
- Three `ALifeRunnerCharacter`s tagged `LifeRunner`, each standing within 200 cm of
  a **different** marker when play begins. One of them is the player's — the map's
  world settings select `ALifeRunGameMode` and its `PlayerStart` sits on a marker.
  The other two are placed and told apart by **per-instance actor tags authored in
  the map**: `RunnerLaneB` (the win leg, driven) and `RunnerLaneC` (the bystander,
  never driven). Per-instance, never in a constructor — the t1-spikes precedent.
- **The player's marker must be an OUTER lane.** The off-lane crossing spot is
  derived, and it must be at least 400 cm nearer another runner's marker than the
  player's own; a player in the middle lane cannot satisfy that and the fixture says
  so by name.
- One `ACrumbleGroundActor` tagged `CrumbleGround`, its `PatchVolume` **unscaled and
  square to the floor**, reaching a runner's standing height, and spanning every
  lane (each runner's |lane Y - patch Y| + capsule radius inside the patch's Y
  half-extent).
- One `AFinishDiscActor` tagged `FinishDisc` exposing `DiscRadiusUu > 100` and a
  readable `DemandedLives`, at least 600 cm clear of the patch. The drive's
  step-off spot (`DiscRadiusUu + 400 cm` back along X from the centre) must have
  floor under it and be clear of the patch, or stepping off and back on is not a
  second arrival.
- Floor under every step of the drive's route — including a **bypass corridor
  500 cm outside the patch's Y face**, from the near side to the far side, so the
  win leg can reach the finish without crossing the hazard — and nothing but the
  floor colliding anywhere a runner walks.

The task folder also carries `cameras.json` (the camera-plan lane; not part of this release) — six `pose` shots computed from the
layout above, each framing more than one runner's lamp row (a single row proves
nothing: one shared counter for the level produces a picture of one row that looks
just as correct). Presentation-only, never gating, and never shown to the agent.

### The drive

**Adaptive, not a fixed route.** Every waiting phase is *"stay here until MY model
says X"*, never *"stay here for T seconds"*. The two driven runners are driven **in
sequence, never at the same time**, so a gate window always names one runner.

Every walking phase's deadline is derived from the MEASURED route length and the
MEASURED `GetMaxSpeed()` (2.5x the ideal plus 12 s), never from a written number of
seconds. `N` below is the crossing on which the staging says A runs out — the
staging table's own `RepaintA`, which is **4** on both legs — so the number of
crossings the drive stages is derived from the table rather than written down, and
the final tally FAILs as a staging fault (never as the submission's) if the two
ever disagree.

| Phase | Who | What | Until |
|---|---|---|---|
| 0 | — | nothing is driven; the spawned runner settles on its marker | 2.0 s (gates off) |
| 1-3 (xN) | A | line up 400 cm clear of the near face, walk to the patch's centre line, stand | each crossing k, then 2.2 s past it (3.2 s on the last one) |
| — | | odd k on **its own lane**, even k at the **off-lane spot** — a derived Y inside the patch whose nearest marker is another runner's, by at least 400 cm | |
| after k=1 | fixture | **re-paint A's marker up** | 0.6 s quiet, write, 2.2 s hold |
| next | B | line up, walk onto the patch, stand | crossing 1, then 2.2 s |
| then | fixture | **re-paint B's marker down** | 0.6 s quiet, write, 2.2 s hold |
| then | B | line up again, walk onto the patch, stand | crossing 2, then 2.2 s |
| then | B | walk **around** the patch (a corridor 500 cm outside its Y face) to the finish disc, then stand — **holding less than the disc asks for, so nothing happens** | on the disc, then 2.8 s |
| then | fixture | **re-paint the finish's own number UP** (B is still short: moving a number opens nothing by itself) | 0.6 s quiet, write, 2.2 s hold, then 2.8 s |
| then | B | step off the disc (400 cm outside its reach) and walk back onto it — the **second** arrival, still short | on the disc, then 2.8 s |
| then | fixture | **re-paint the finish's own number DOWN**, below what B is holding | 0.6 s quiet, write, 2.2 s hold |
| — | | **B wins here, standing still, with no arrival to hang it on** | then 2.6 s |
| then | A | walk out of the patch 400 cm clear, back into it, stand | crossing N+1 (spends nothing), then 2.6 s |
| then | A | walk out the far side and onto the finish disc, stand | on the disc, then 2.6 s |
| then | B | walk from the disc back to the far side and onto the patch, stand | crossing (spends nothing), then 2.6 s |
| then | B | walk back onto the finish disc, stand | on the disc a **second** time, then 2.6 s |
| then | fixture | **re-paint both ended markers** a last time | 0.6 s quiet, write, 2.2 s each |
| last | — | the run-level gate | — |

A's phases give the crumbling ground **four** spending crossings on one runner, in
two matched pairs (own lane / off lane), so a one-shot latch and a route-specific
answer both die. B's give it two more on a second runner. The closing phases walk
both ended runners back over both triggers and move both their boards. The finish
disc is walked onto **four** times by two runners, and B's win happens on none of
them: it happens on a frame in which B did not move and nothing was entered.
`FinalGrade` refuses to grade a run in which the finish's own number did not move
twice, or in which B was never judged standing on the disc short of it on at
least two frames — a leg that skipped that is ours, not the submission's.

**B goes AROUND the patch to the finish, never through it.** A third crossing
there would spend a life the win leg does not have and would make the win
arithmetically unreachable — the defect the approved design's own drive table
carried. `ValidateRoutes` enforces it for every phase: no non-crossing segment may
walk back onto the patch.

The checkpoint schedule is a calibration checkpoint every **5 s** (96 of them, 5 s
to 480 s) plus a **SENTINEL at t = 500 s**, far past the ~200 s the drive models,
because `ACraftBenchFunctionalTest::Tick` ends the test the moment the last
scheduled checkpoint is sampled. Checkpoints only LOG: every gate runs per frame.
The run-level gate is evaluated when the last phase completes **and** again at the
sentinel, whichever comes first, and only then does the fixture call
`FinishTest(Succeeded)`.

### Settle and suppression

Nothing is judged on a frame where any of these hold for the runner in question.
Each is a **widening** of the disclosed contract, never a narrowing:

- less than **0.75 s** since that runner's model last changed (1.5x the half
  second the prompt promises);
- while the fixture is re-staging the level — **0.6 s** from the moment a re-paint
  phase opens and **0.6 s** from the write itself, so no runner is ever judged on a
  frame in which the fixture moved its number;
- while a **still-running** runner is within **160 cm** OUTSIDE the crumbling
  ground's or the finish disc's edge — the only band in which an overlap-driven
  answer and a point-in-box answer legitimately disagree (~42 cm of travel). It is
  one-sided: the moment the capsule centre is INSIDE a trigger, every honest answer
  agrees it is inside and the 0.75 s settle already covers the lag, so the inside is
  judged. Banding it as well would make a runner left lying in the patch (it comes to
  rest ~36–53 cm inside the near face) permanently unjudgeable, and that is exactly
  the submission `WhileLivesRemainYouComeBackToYourMarker` is written to name. The
  band is dropped altogether once a run has ended, because a frozen readout cannot be
  moved by an entry model;
- while that runner is being teleported *by the fixture* (never happens — the
  fixture only ever walks).

Every disclosed deadline is also gauged **0.35 s late**: the come-back rule is
measured at crossing + **1.35 s** (disclosed 1 s) and every half-second rule from
**0.85 s** (disclosed 0.5 s), so an answer that uses the whole of its allowance is
never failed for being late.

### The sequenced return window

`WhileLivesRemainYouComeBackToYourMarker` measures just past the disclosed
deadline: it samples from **crossing + 1.35 s** and requires the runner to be
within 120 cm of its own marker, measured flat. Its window stays armed to
crossing + **1.8 s**, and the drive holds the runner still for 2.2 s, so the gate
never races the drive. From +1.35 s a **no-second-teleport** watch runs until that
runner's next crossing: the per-frame displacement must stay inside what walking
can produce (2x the measured max walk speed x dt, plus 30 cm), so a snap-back is
caught as a jump even while the drive is walking the runner away. The same watch is
what holds the lost runner in place for the rest of the run, and it runs even on
frames every other gate is suppressed on — a submission MOVING a runner is not
something an entry-model disagreement can excuse.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64
        Development" and "ThirdPerson Win64 Development"
```

### L2 — AFunctionalTest behavioral trace

**Gate precedence, in the order the fixture evaluates them.** At most one of 2-6
is armed for a given runner on a given frame, so a named FAIL is never a race
between two of them; 7 and 8 are the everywhere-else gates and 9 is an independent
channel that always runs last.

```text
1  TheRunIsNotYoursToRewire           -- every frame, every runner, from the first
2  TheLastLifeEndsTheRun              -- the run-ending crossing .. +2.5 s (the row
                                        and the word gauged from +1.35 s), plus the
                                        stay-put watch for the rest of the run
3  WhileLivesRemainYouComeBackToYourMarker -- each non-final crossing .. +1.8 s
                                        (gauged from +1.35 s), plus the
                                        no-second-teleport watch after it
4  EachDeathSpendsExactlyOneLife      -- the same window, a DIFFERENT channel (lamps
                                        rather than position); both run, and it
                                        covers the whole dwell in the patch
5  TheBoardIsReadWhenItMatters        -- each mid-run re-paint .. +1.8 s (gauged
                                        from +0.85 s)
6  ReachingTheGoalWinsAndSpendsNothing-- the frame the goal OPENED to the win-leg
                                        runner .. +1.8 s (gauged from +0.85 s)
6b TheGoalOnlyOpensToWhatItAsksFor    -- every judged frame a still-running runner
                                        stands on the disc holding less than the
                                        disc asks for
7  ARunThatEndedNeverChangesAgain     -- from a runner's terminal event onward, over
                                        every conflicting event driven at it
8  TheRunReadsWhatItIs                -- everywhere else, per runner
9  TheBystanderIsUntouched            -- every judged frame, ALWAYS LAST
10 BothRunsEndedTheirOwnWay           -- run level, at drive completion or the
                                        sentinel, whichever comes first.
                                        CORROBORATIVE -- see Hidden invariants
11 ARunnerIsAlwaysFreeToWalk          -- only on a walking phase that overran, and
                                        only after every display gate has agreed
```

Gates 3 and 4 are **different channels** on the same window (position vs lamps)
and both run; gate 2 owns the run-ending crossing outright and disarms 3 and 4 for
that runner in its window. `TheBystanderIsUntouched` runs last, and only once
whichever gate was armed has already agreed, for the same reason the alarm task's
pace gate does: a submission that teleports a runner onto the bystander's marker
must be named by the **return** gate, not by the bystander gate it also trips,
while a submission whose loss leg is perfectly correct and whose ownership is
shared has nothing else armed and is named by the bystander gate — which is the
diagnosis that matters.

```text
assert: TheRunIsNotYoursToRewire -- every frame: each marker's PaintedLives is
        exactly what the fixture last staged; each marker, the crumbling patch
        and the finish disc are within 2 uu of where the level put them and
        DiscRadiusUu is unchanged; exactly three un-destroyed actors tagged
        LifeRunner exist and they are the same three object identities resolved
        at t=0 (nobody was replaced); and each of them still carries six lamp
        components and its word component. ANTI-TAMPER, NOT DISCRIMINATION: this
        is the ONE gate an empty submission passes, and it must never be counted
        as a scoring point a do-nothing answer earns.

assert: TheLastLifeEndsTheRun -- at the crossing that leaves a runner with no
        lives remaining (the fixture's model: the marker's LIVE painted number
        minus deaths suffered, floored at zero), then within 1.0 s: that runner's
        lit lamp count is 0, its word reads LOST, and it has NOT been sent home
        -- it is within 150 cm of the spot the ground claimed it, and stays
        there until the drive itself walks it away, after which nothing of the
        submission's ever moves it (no per-frame jump beyond walking). THE
        OFF-BY-ONE GATE: an answer that spends the life on the RETURN rather
        than on the DEATH either latches LOST with one lamp still lit, or runs
        the return branch on the run-ending death and puts the runner back on
        its marker still reading RUNNING -- both are named here. The message
        names the marker's painted number, the deaths suffered, the lit count
        found, the word found and the distance from the claiming spot.

assert: EachDeathSpendsExactlyOneLife -- across every geometrically-detected
        crossing into the crumbling ground while that run is going, the runner's
        lit lamp count drops by exactly one and by nothing else: standing in the
        patch does not drain further, stepping off and walking on again costs
        another one, and the count never goes below zero. Fires at least FOUR
        times on the loss-leg runner and TWICE on the win-leg runner, and the
        second firing must measure the same as the first. The message names the
        crossing index, the lit count before and after, and the elapsed dwell.

assert: TheBoardIsReadWhenItMatters -- after the fixture re-paints a
        still-running runner's marker mid-run, within 0.5 s that runner's lit
        lamp count equals the NEW painted number minus the deaths it has already
        suffered (floored at zero), its word still reads RUNNING (a re-paint
        alone never ends a run), and its next crossing is its last one exactly
        when the new number says so -- not one crossing earlier or later. THE
        CACHED-COUNTDOWN KILLER: a value latched at start of play is wrong from
        the re-paint onward, in BOTH directions (A's marker goes up, B's goes
        down). The message names the old and new painted numbers, the deaths
        suffered, and the lit count found.

assert: WhileLivesRemainYouComeBackToYourMarker -- every crossing that leaves
        lives remaining puts that runner within 120 cm of its OWN marker's
        centre, measured flat, at 1.0 s after the crossing -- its own, not
        another runner's, which is why one of the two matched crossing spots is
        deliberately nearer a DIFFERENT runner's marker than its own. From
        1.0 s onward the drive walks it away and it must stay away: no
        snap-back, no second teleport. Gauged on at least two non-final
        crossings per driven runner. The message names the runner, its own
        marker, the marker it was actually nearest to, and the distance.

assert: TheGoalOnlyOpensToWhatItAsksFor -- on every judged frame a still-running
        runner is standing on the finish disc holding FEWER lives than the number
        currently painted on the disc, nothing has happened to it: its lit lamp
        count still equals its own live remaining count and its word still reads
        RUNNING. Gauged on at least TWO separate arrivals by the win-leg runner,
        and across a mid-stand re-paint of the disc's number UPWARD. THE
        WALKED-ON-SO-YOU-WIN KILLER, and the READ-THE-BOARD-NOT-WHAT-IS-LEFT
        killer: the disc asks for exactly the number painted on that runner's own
        marker at that moment on BOTH legs, so an answer that compares the disc
        against the board is let through the instant it steps on. The message
        names what the runner is holding, its marker's painted number, its
        deaths, what the disc is asking for, the lit count found and the word
        found.

assert: ReachingTheGoalWinsAndSpendsNothing -- at the moment the win-leg runner
        is standing on the finish disc with its run still going and is holding at
        least what the disc asks for -- which on both legs is the moment the
        DISC'S OWN NUMBER comes down to it, with the runner standing still and no
        arrival to hang it on -- then within 0.5 s its word reads WON, and its
        lit lamp count is IDENTICAL to the frame before the goal opened --
        winning spends nothing and lights nothing. It still reads WON at every
        later checkpoint. THE EVENT-SHAPED-GOAL KILLER: an answer that decides the
        finish on the step that carried a runner onto it, the way the crumbling
        ground is decided, has no event on that frame and never wins the run at
        all; and an answer using a strict `>` where the level says AT LEAST loses
        the 60 Hz leg, where the disc comes down to exactly what the runner holds.
        The message names the lit count before and after, what the disc came down
        to, and the word found.

assert: ARunThatEndedNeverChangesAgain -- after either terminal event, that
        runner's lit lamp count and word are unchanged for the rest of the run
        through three driven conflicting events, on BOTH terminal kinds: the
        lost runner is walked out of and back into the crumbling ground (no
        spend) and then onto the finish disc (stays LOST, never WON -- and on the
        60 Hz leg it is standing there holding zero against a disc asking for 1,
        so nothing may open to it either way); the won
        runner is walked back into the crumbling ground (no spend, stays WON)
        and onto the finish disc a second time (no change); and the fixture
        re-paints both ended markers (no change). Neither runner is moved by
        anything but the drive. Win and loss are never both set on one runner:
        the word is exactly one of the three at all times. The message names the
        conflicting event, the runner's frozen values and the values found.

assert: ARunnerIsAlwaysFreeToWalk -- a walking phase of the drive ran past its
        DERIVED deadline and the runner it was pushing every frame moved less
        than 150 cm, on floor the route was traced for, with nothing in the level
        able to block it. That is a submission holding a body in place -- pinning
        a runner to its marker, immobilising its movement, or re-asserting a
        position every frame after its run has ended -- which the level says in
        as many words nothing of yours may do. Checked only AFTER every display
        gate has been re-run unconditionally, so a stalled drive is a graded FAIL
        rather than an uncredited HARNESS-PRECONDITION. The message names the
        phase, how long it was pushed for, how far it moved and what its run
        reads.

assert: TheRunReadsWhatItIs -- the everywhere-else gate, on every judged frame
        not owned by a window above: for each of the three runners the lit lamp
        count equals the fixture's own live model (its marker's CURRENT painted
        number minus its deaths, floored at zero, frozen once its run ended) and
        its word's first run of letters equals the model's state. Read from the
        lamps' actual glow and the text component's string, never from a flag.
        THIS IS THE GATE THE EMPTY SUBMISSION DIES ON, at the first judged
        frame. The message names, per runner, its marker's painted number, the
        deaths suffered, the lit count found and the word found.

assert: TheBystanderIsUntouched -- IN-SCENE NEGATIVE CONTROL, evaluated on EVERY
        judged frame including inside every other gate's window and after both
        terminal events: the third runner -- same class, same lamp row, same
        word, its own marker, never driven anywhere, its marker never re-painted
        -- has exactly its own painted number of lamps lit, reads RUNNING, and
        is within 40 cm of its own marker's centre. This is the gate that
        catches one shared counter or one shared run state for the level. The
        message names the bystander's painted number, the lit count found, the
        word found and the distance from its marker.

assert: BothRunsEndedTheirOwnWay -- run-level, at drive completion or the
        sentinel, READ OFF THE LEVEL and never off the fixture's own model:
        exactly one runner is reading LOST with every lamp dark, exactly one is
        reading WON with the lamps it won with, and the third is reading RUNNING
        with the lamps its own board calls for; the LOST one never read WON at
        any frame and the WON one never read LOST. CORROBORATIVE, NOT PRIMARY:
        any runner showing the wrong word has already been named by a per-frame
        gate long before this line, so this must be discounted in a k/N exactly
        like the anti-tamper gate. The model half of the same question -- did the
        DRIVE put one runner out and win another at all -- is checked first and
        reported as a HARNESS-PRECONDITION, because nothing a submission does can
        move the fixture's own model and a drive that did not happen is ours.
```

**Staging faults are attributed, not scored.** Any of these ends the run as a
`HARNESS-PRECONDITION` (`FinishTest(Error, ...)`), never as a model failure:
the world's fixed timestep is neither leg's; wrong actor counts (three runners,
three markers, one patch, one disc); the level's own rules did not put a runner
under the player's control when play began; the two placed runners are not told
apart by the per-instance marks the level authors; **the level cannot be played by
hand** (the pawn has nothing bound to one of the four input actions, or the game
mode's controller applies no mapping context — Hard Rule #8, asserted by property
name); a runner that is not visibly represented (no skeletal mesh assigned), which
would grade clean and show a reviewer nothing; a runner, marker, patch or disc that
does not expose its numbers or components readably; a marker whose staged value
would fall outside 1..6, would tie another marker at any instant, or would leave a
runner on zero from a re-paint alone; a staged goal number that the win-leg runner
already meets on arrival, that is above that runner's own board (which would let
the read-the-board answer escape), that never comes down to what it is holding, or
that does not really move; markers closer together than 4x the 120 cm
"on a marker" tolerance; a patch that is scaled or turned off square, that does not
reach a runner's standing height, that does not span every lane, or that is within
600 cm of any marker or of the finish disc; nowhere on the patch being at least
400 cm nearer another runner's marker than the loss-leg runner's own (which would
make the ownership rule measure nothing); a drive route with no floor under it,
something blocking it, or a non-crossing segment that walks back onto the patch; a
drive waypoint the runner cannot reach inside a derived deadline; or a run whose
own tallies came up short — fewer than four spending crossings on the loss leg or
two on the win leg, a total crossing count that disagrees with the staging table,
fewer than three conflicting events driven at either ended run, fewer than two
finish-disc arrivals by the win-leg runner, fewer than two moves of the finish's
own number, or fewer than two judged frames on which the win-leg runner stood on
the disc holding less than the disc asked for. A leg that never happened proves
nothing, so it is named as ours rather than passed.

**A harness exit can never launder a FAIL.** Before any deadline or sentinel
overrun is written off as a staging fault, `TheRunIsNotYoursToRewire` and
`TheRunReadsWhatItIs` are re-checked **unconditionally** — a submission that
parks a runner, moves a marker or pulls a runner back is exactly what makes a
phase overrun, so a rewired level must be a FAIL and not an uncredited harness
exit.

## Requirement-to-assertion map

| Prompt requirement | Gate that checks it | When that gate does NOT run |
| --- | --- | --- |
| the disc a runner stands on when the run opens is its own for the whole run | `WhileLivesRemainYouComeBackToYourMarker`, whose diagonal crossing spot is nearer a different runner's marker than the runner's own | outside a non-final crossing window; the same fact is checked indirectly everywhere else through the painted number the model reads from that marker |
| remaining lives = the number **currently** painted, minus deaths, floored at zero | `TheRunReadsWhatItIs` every judged frame, and `TheBoardIsReadWhenItMatters` across every re-paint | frames the settle rule suppresses |
| the painted number is never above six or below one, and the three differ | not a gate but a **staging rule**: the fixture refuses to stage a value that would break it | never |
| exactly that many lamps lit, counted from one end, the rest dark | `TheRunReadsWhatItIs` reads the lit COUNT off the glows; the *from one end* half is structural — the supplied switch lights the first `Count` lamps, so any answer using it satisfies it by construction | a submission that lights lamps some other way is graded on the count alone |
| the lamps start dark and nothing lights them | `TheRunReadsWhatItIs` at the first judged frame — the empty-submission failure of record | never |
| a re-paint changes the row at once and never claims anybody | `TheBoardIsReadWhenItMatters` (which requires the word to still read RUNNING across every mid-run marker re-paint) | outside a re-paint window |
| a re-paint changes which death is the last one | `TheBoardIsReadWhenItMatters` (the next-crossing clause) and `TheLastLifeEndsTheRun` firing at the right crossing | as above |
| a death is a moment, not a length of time | `EachDeathSpendsExactlyOneLife` (the dwell clause and the step-off-step-on clause) | frames the settle rule suppresses |
| with lives left: back on **its own** marker within 1 s, then let go | `WhileLivesRemainYouComeBackToYourMarker` | outside a non-final crossing window |
| with no lives left: not sent home, left where it fell, all lamps dark, word LOST, within 1 s | `TheLastLifeEndsTheRun` | outside the run-ending window; the frozen state is then owned by `ARunThatEndedNeverChangesAgain` and `TheRunReadsWhatItIs` |
| standing on the finish holding at least what it asks for wins within half a second, and spends nothing | `ReachingTheGoalWinsAndSpendsNothing` | outside the 1.8 s window from the frame the goal opened |
| standing on the finish holding fewer does nothing at all | `TheGoalOnlyOpensToWhatItAsksFor`, on at least two separate arrivals | frames the settle rule suppresses, and once that run has ended |
| the disc's number is re-painted mid-run, and a runner already standing there wins the moment it leaves them holding enough | `ReachingTheGoalWinsAndSpendsNothing`, whose window opens on that very frame — there is no arrival on it | never; a submission that has no answer on that frame simply never wins the leg |
| "holding enough" is measured against lives LEFT, never against the marker's painted number | `TheGoalOnlyOpensToWhatItAsksFor`, whose staging makes the disc ask for exactly the board's number at that instant on both legs | as above |
| a runner is always a body that can be walked; nothing of yours holds it in place | `ARunnerIsAlwaysFreeToWalk` | when no walking phase overran — i.e. whenever the submission did not pin anybody |
| an ended run never changes again, whatever happens | `ARunThatEndedNeverChangesAgain`, over three driven conflicting events on both terminal kinds | before either terminal event |
| won or lost, never both, first one stands | `ARunThatEndedNeverChangesAgain` per frame and `BothRunsEndedTheirOwnWay` at run level | a run that fails a per-frame gate earlier never reaches the run-level one, which is the more useful message |
| the word reads RUNNING / WON / LOST, first run of letters | every gate that reads a word; `TheRunReadsWhatItIs` everywhere else | frames the settle rule suppresses |
| each runner keeps its own; an untouched runner is unchanged | `TheBystanderIsUntouched`, at every checkpoint including inside every other window | never |
| nobody is ever replaced | `TheRunIsNotYoursToRewire` (same three object identities, un-destroyed) | never |
| everything settles within half a second | the 0.75 s suppression window, which is 1.5x it | never |
| none of it is one-shot | `EachDeathSpendsExactlyOneLife` (>= 4 and >= 2 crossings, matched pairs), the four finish-disc arrivals, and `TheGoalOnlyOpensToWhatItAsksFor` across two separate short arrivals | never |
| do not move anything, do not re-paint a marker or the finish's number yourself | `TheRunIsNotYoursToRewire`, every frame, over all three markers AND the disc's own number | never |
| keep the markings the level put on things | `TheRunIsNotYoursToRewire` (three actors still carry `LifeRunner`; the resolution path names it as a FAIL rather than a harness exit when three characters exist and fewer than three are marked) | never |
| C++ under `Source/ThirdPerson/` | sandbox: a file outside the writable set is exit 4, not a graded FAIL | never |

## Reference solution metadata

- **Files touched**: 2 —
  `Source/ThirdPerson/Tasks/t3-your-last-life-ends-the-run/LifeRunnerCharacter.h`
  and `.cpp`. The other four supplied pairs are untouched and are not shipped in
  `reference/` at all. The whole answer lands on the runner, which is the shape
  the ownership requirement pushes toward — but nothing grades where it lands.
- **LOC**: ~290 added (about 90 of them comment) on top of the supplied class —
  ~250 lines in the `.cpp` and ~45 in the `.h`, measured against the scaffold.
- **Senior-dev hours**: **8-12**, the lower half of T3. The code is not large; the
  hours go into getting four things right at once, each of which has a natural
  first implementation that is wrong:
  1. ~2 h working out that remaining lives is a **derivation from a moving
     board**, not a counter — and that the derivation has to be re-evaluated at
     the moment of a death, not only when drawing the lamps.
  2. ~2 h on the terminal rule's exact boundary: the life is spent on the
     **death**, the "was that the last one?" question is asked immediately
     afterwards, and the run-ending death takes a *different branch* from every
     other death. The natural first implementation decrements inside the respawn
     path, which reads perfectly and is off by one.
  2b. ~2 h on the **shape** of the second trigger, which is the part that has no
     natural first implementation at all. The level says the ground is a moment
     and the goal is a standing question, and the two live in the same tick: the
     ground must be edge-detected and the goal must be re-asked on frames where
     nothing happened, because the only frame on which the win leg is ever won is
     a frame on which the runner did not move and nothing was entered. Writing
     the goal the way the ground is written — one overlap handler apiece — reads
     as consistent, symmetrical code and never wins a run.
  3. ~2 h on the latch feeding back: an ended run must make the ground, the
     finish and the board all inert for that runner, which is three separate
     early-outs a first pass adds one at a time as each gate names it.
  4. ~2 h on ownership: three instances of one class, each with its own marker
     resolved once and never re-resolved, and nothing shared. Plus the reading
     discipline — the marker is read at the point of use, every time.
  5. ~1-2 h wiring the two readouts so they are correct from the first frame of
     play rather than from the first event, and confirming the whole thing twice
     over at two framerates.
- **Why T3**: four subsystems that gate each other in both directions, across
  three actor classes, three independent participants in one scene, **two**
  load-bearing values that change under the solution while it runs (on two
  different actors), two triggers with deliberately opposite temporal shapes, and
  a terminal rule whose off-by-one is invisible to every surface check. It is not
  T2 because getting any one of the four right in isolation is easy and gets you
  a named FAIL on one of the other three.

## Anti-gaming notes

> **The three answers this task is actually shaped to catch are 1a, 1b and 1c —
> code-shape and boundary errors, not comprehension errors.** Producing any of
> them takes no misreading of the level at all: they are what careful, symmetrical
> code looks like when the two triggers are written the same way, when "enough"
> is measured against the nearest number to hand, and when *at least* is typed as
> `>`. The rest of this list is the older set, kept because each still names a
> real defence.

1a. **Write the finish the way the level tells you to write the ground.** *Failure
   mode*: **the headline trap.** The level says in as many words that the
   crumbling ground is *a moment, not a length of time* — so it is edge-detected,
   and every implementation does that correctly. The finish is then written the
   same way, because in the same file, in the same tick, symmetry is the obvious
   virtue: on entering the disc, check whether this runner is holding enough and
   win if it is. It passes **every** arrival check: the win-leg runner arrives
   short and correctly does not win, twice. *Defense*: the only frame on which
   that runner is ever holding enough is a frame on which **it did not move and
   entered nothing** — the disc's own number comes down to it while it stands
   still. An edge-shaped answer has no event to hang the win on, never wins the
   leg, and is named by `ReachingTheGoalWinsAndSpendsNothing`, whose window opens
   on exactly that frame. There is no route around it: the drive never walks that
   runner onto the disc while it is holding enough.
1b. **Measure "holding enough" against the board rather than against what is
   left.** *Failure mode*: the marker's painted number is the number *right
   there*, one dereference away, and the difference only shows once a runner has
   died. *Defense*: on **both** legs the disc asks, at the moment of the win-leg
   runner's first arrival, for exactly the number painted on that runner's own
   marker (3 against a board of 3 at 60 Hz; 5 against a board of 5 at 20 Hz), so
   this answer opens the goal the instant the runner steps on — two deaths early,
   with the wrong lamp count frozen. `TheGoalOnlyOpensToWhatItAsksFor` fires on
   the first judged frame of that stand and prints both numbers side by side.
   `ValidateStagingTable` refuses a table in which that coincidence does not hold,
   so the discriminator can never quietly stop discriminating.
1c. **`>` where the level says *at least*.** *Failure mode*: a one-character
   boundary slip in a correct implementation. *Defense*: the disc's last move
   lands **exactly on** what the win-leg runner is holding at 60 Hz and strictly
   below it at 20 Hz, so this answer PASSES the 20 Hz leg and FAILs the 60 Hz one
   — `ReachingTheGoalWinsAndSpendsNothing`. A split verdict across the two legs is
   the signature, and it is the honest one.
1. **Spend the life on the RETURN, not on the death.** *Failure mode*: the
   single most natural first implementation and the owner's named wrong answer.
   At start of play the runner caches `LivesRemaining = PaintedNumber` and lights
   that many lamps; on contact it calls its respawn path, and the respawn path is
   what decrements: `if (LivesRemaining > 0) { --LivesRemaining; SetLamps(...);
   TeleportToMarker(); } else { State = Lost; }`. It compiles, reads perfectly,
   and satisfies every surface check — lives start right, each death costs one,
   non-final deaths return you to your marker, the row comes down one at a time.
   *Defense*: it is wrong in two measured places. The run-ending death still runs
   the return branch, so the runner is standing on its marker with zero lamps lit
   and still reading RUNNING and the loss only latches on the NEXT contact —
   `TheLastLifeEndsTheRun` FAILs on both of its clauses. And the cached countdown
   ignores the mid-run re-paint entirely — `TheBoardIsReadWhenItMatters`.
2. **One run for the level.** *Failure mode*: the tutorial answer. Lives and the
   won/lost state go on the one object that owns "the run" for the whole level
   rather than on each runner, so three runners share a counter and a latch. It
   passes the entire loss leg and the entire win leg **in isolation**. *Defense*:
   `TheBystanderIsUntouched` fires at the first death (the untouched third
   runner's row dims with the loss-leg runner's) and again at the first terminal
   event (its word flips), and it is evaluated at every checkpoint including
   inside every other gate's window so it cannot be stepped around.
3. **Read the painted number once, at BeginPlay.** *Failure mode*: the obvious
   optimisation, and the same bug as (1)'s second half even when the ledger is
   otherwise right. *Defense*: two mid-run re-paints in opposite directions, and
   per-leg staging so the number is not in the map either.
   `TheBoardIsReadWhenItMatters` names both.
4. **Re-decide which marker is "yours" at the moment of death.** *Failure mode*:
   a reasonable-looking "send them to the nearest marker", which is right for
   every death taken on a runner's own lane. *Defense*: one of the two matched
   crossing spots is deliberately nearer a **different** runner's marker, and the
   prompt states in as many words that ownership is fixed when the run opens.
   `WhileLivesRemainYouComeBackToYourMarker` names the marker it went to.
5. **A one-shot latch on the ground or the finish.** *Failure mode*: "handle the
   contact" wired as a first-time-only event, which passes every single-event
   check. *Defense*: the ground spends four times on one runner and twice on
   another, in two matched pairs; the finish disc is arrived at **four** times by
   two runners and the win leg's two SHORT arrivals must measure the same as each
   other; `EachDeathSpendsExactlyOneLife` requires the second firing to
   measure the same as the first, and `TheGoalOnlyOpensToWhatItAsksFor` requires
   it of both short arrivals.
6. **Drain while standing in the patch, or count the dwell.** *Failure mode*: an
   overlap handler that fires per frame, or a hazard modelled as damage over
   time. *Defense*: the drive stops pushing the moment the runner is inside the
   patch and then holds it there for **2.2 s** after every crossing (3.2 s after the
   run-ending one, 2.6 s after each conflicting one);
   `EachDeathSpendsExactlyOneLife` requires exactly one lamp of change across the
   whole dwell — a correct answer that returns the runner home mid-dwell is fine,
   and a per-frame drain is not.
7. **Set a correct internal state and never touch a lamp or a word.**
   *Failure mode*: modelling the run and forgetting the output. *Defense*:
   nothing private is ever graded — the fixture reads the point lights' intensity
   and the text component's string, the class deliberately carries no "lives
   remaining" property, and `GetLitCount()` (which a submission could rewrite) is
   never consulted.
8. **Respawn by destroying and re-spawning the runner.** *Failure mode*: the
   engine-idiomatic "restart the player", which loses the death tally with the
   old instance and would let a fresh runner start over at full lamps.
   *Defense*: the prompt states nobody is ever replaced, and
   `TheRunIsNotYoursToRewire` pins the three runner object identities from t=0.
9. **Park a runner outside the patch, or move a marker under it.**
   *Failure mode*: anti-gaming rather than a plausible first pass — making an
   inconvenient crossing unreachable. *Defense*: `TheRunIsNotYoursToRewire`
   compares every staged number and every placement every frame, and a phase that
   overruns re-checks it unconditionally before any harness exit.
10. **Nail the ended runner down.** *Failure mode*: a prompt-literal reading of
   *left standing where the ground claimed it* implemented as immobilisation —
   `DisableMovement()`, a `StopMovementImmediately()` every frame while the run is
   lost, or re-asserting the claim spot each tick. It is green on **every** display
   gate. *Defense*: this used to be the worst verdict this task could produce — the
   level walks that same body off the patch and onto the finish afterwards, the
   phase would overrun, and the run would exit as a non-graded
   `HARNESS-PRECONDITION` **with every display gate green**, i.e. attributed to us
   on a day the model was never judged. It is now (a) **disclosed** — the prompt
   says a runner is always a body that can be walked, that the one and only move
   of yours is the return, and that an ended run is never moved *by you* rather
   than nailed down — and (b) **graded**: `ARunnerIsAlwaysFreeToWalk` names it as
   a FAIL, after every display gate has been re-run unconditionally.

## Hidden invariants

- **The lit count is never compared to anything the submission exposes.** The
  fixture's model integer is never read out of the submission (it could not be),
  so every gate is a statement about lamps, words and positions. A submission may
  represent its ledger however it likes.
- **The fixture's own model of "whose marker" is fixed at t = 0**, exactly as the
  prompt promises, and is never re-derived. That is what lets the diagonal
  crossing spot be a discriminator rather than an ambiguity.
- **The re-paint is written by reflection, not through a setter.** A submission
  that overrode the marker's refresh could otherwise intercept the staging, and
  the anti-tamper gate would then read back the value the submission chose.
- **`fps_legs: [60, 20]` runs the whole drive twice with DIFFERENT staged
  numbers**, in two PIE processes. A frame-count deadline fires at the wrong wall
  time on one of them, and a life count — or a goal number — mined from the
  committed `.umap` is wrong on both. The map is authored painting 4/2/5 on the
  markers and 4 on the finish, and `author_map.py` refuses to save if any authored
  number is a value either leg ever stages.
- **The `>=` boundary is deliberately split across the two legs.** The disc's last
  move lands on exactly what the win-leg runner holds at 60 Hz and strictly below
  it at 20 Hz. A leg-split verdict on this task is a real off-by-one in the
  submission, not framerate flakiness — read the two legs together before
  suspecting the harness.
- **`BothRunsEndedTheirOwnWay` is CORROBORATIVE and must be discounted in a k/N**,
  alongside the anti-tamper gate. It reads the three runners' own words and lamps
  off the level rather than the fixture's model, so it is a statement about the
  submission — but any runner showing the wrong word has already been named by a
  per-frame gate, so it can only ever confirm. The question of whether the DRIVE
  happened at all is checked separately, first, and reported as a
  HARNESS-PRECONDITION, because nothing a submission does can move the fixture's
  own model.
- **`TheRunIsNotYoursToRewire` is the ONE gate an empty submission passes.** It
  is anti-tamper, not discrimination, and must be excluded from any k/N presented
  as a discrimination score — this is the DEF-5 dead-gate defect the adoption
  review found at 3/6 on the parent corpus row `t2-lives-system`. Every other gate
  above fails on an empty delivery, and `TheRunReadsWhatItIs` fails at the first
  judged frame.

---
id: t3-gate-and-door-cpp
substrate: ThirdPerson
set: cpp
tier: T3
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_OldDoorYard :: AOldDoorYardFunctionalTest"]
fps_legs: [60, 20]
---

# t3-gate-and-door

A brownfield task. The yard ships with **one rule already running and already
correct**: while any single body — a person or a crate — rests on a floor pad, the
door that pad answers for is open. That rule is what makes the old door at the north
end work, and it has to keep working, measured in exactly the band it is measured in
before the agent touches anything.

The agent's job is **two new gates** in the west wall, which need a rule that wants a
different answer out of the same question: two named crates and *only* those two, the
pair of names re-cut mid-shift without announcement, and two lamps per gate reporting
per name slot. The pad class, the barrier class and the occupancy question are shared
by all four barriers. Narrowing the shared question fixes the gates and kills the old
door; leaving it alone keeps the old door and gets the gates wrong.

The two gates stand over **the same two patches of floor** — their pads are painted one
over the other — and they are cut for **different pairs**, re-cut on different
schedules. So they see the same three crates at the same instants and still have to
disagree: through most of the run one is open while the other is shut, and at the last
re-cut, with nothing in the yard moving at all, one must come down while the other goes
up. Nothing about the layout can tell the two gates apart; only what is written on each
of them can.

> **Built against the 2026-08-18 difficulty bar, and hardened 2026-08-19 against two
> adversarial reviews.** Subsystems that genuinely interact through a shared seam and
> want different answers out of it, with a **named gate on each side** of the coupling
> — `TheOldDoorStillOpensInsideItsBand` fails the answer that narrows occupancy,
> `TheRunnerIsNotACrate` fails the answer that reuses it, and
> `TheSecondGateAnswersToItsOwnPair` fails every answer written for *the* gate rather
> than for *a barrier that is cut for names*. Locally-reasonable wrong answers on each
> side that compile, read beautifully and satisfy most of the surface (see *Anti-gaming
> notes* 1, 2, 10 and 11). And the load-bearing fact — the ordered pair of crate names
> each gate is currently cut for — is read off the world, written down nowhere, and
> **re-cut three times per gate**: once by the fixture before the first judged frame
> (so neither pair saved in the level is the pair its gate grades against, and a
> hard-coded answer is wrong from frame one) and twice mid-run, the second of those
> with nothing in the yard moving at all.
>
> **What the review changed, and why it is not a riddle.** The first cut of this task
> announced its own traps: the prompt said in as many words that a person on a pad is
> not a crate, that the shared pad rule is what makes the old door work, that names and
> not positions are what is being asked about, and that the answer must be re-read at
> the point of use — one sentence per anti-gaming note, in the order the fixture checks
> them. Every one of those facts is still fully *entailed* by the contract the prompt
> states ("open exactly while … and shut the rest of the time"), so no gate has an
> undisclosed value; what is gone is the pre-mortem. The scaffold likewise shipped the
> branch predicate already written, a three-item to-do list and the reading discipline
> as an imperative; those are gone too. Difficulty here is coupling, never concealment
> — a gate still fails only for behaviour the prompt asks for in plain words.

`deliverable_root`: `Source/ThirdPerson/` — see the first line of *Workspace state
pre-task*. The front-matter key of that name is **rejected by the parser**
(`tools/verify-single/spec.py::_KNOWN_KEYS`), so per the set's README the path is
stated twice in agent-visible prose instead: in the prompt block and in the first line
of *Workspace state pre-task*. Those two H2s are exactly
`tools/run-agent/prompt_extract.py::ALLOWED_SECTIONS`.

## Primary concept

- `ps-actors` — Actors
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/actors-in-unreal-engine)

The load-bearing behaviour is **one shared actor class whose placed instances must
behave differently from each other, each decided from data carried on that instance and
re-read every time it is needed**. Four of the yard's barriers are instances of the same
class: two must keep the behaviour they shipped with, and two must each acquire a new
one that is *not the same as the other's*. The grade never asks *how*: the decision may
live on a barrier, on a pad, on a crate, on a lamp or on the character, and a per-frame
tick, a repeating timer and an event-plus-poll hybrid all pass identically, as long as
the yard settles inside the 1.20 s the prompt promises.

The second gate is what makes "per instance" load-bearing rather than decorative. It
shares the pads, the crates and the class with the first, so nothing observable
separates them except the pair of names written on each — and it is gauged on every
judged frame, so an answer that finds *the* gate once, or keeps the rule anywhere the
two gates share, is named the first time their answers diverge.

## Composed concepts

- `actor-lifecycle` — the pair of names each gate is cut for is rewritten three times,
  the first before the drive starts and after every `BeginPlay` has run, so anything
  read once at the start of play is a copy of the wrong answer for the whole run
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-actor-lifecycle)
- `collision-overview` — "resting on a pad" is resolved per pad against **that** pad's
  own radius and its own level, for bodies of two very different shapes, and the
  crates are shoved by ordinary blocking contact with a walking character
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/collision-in-unreal-engine---overview)
- `ps-components` — every graded readout is a component read off the thing itself:
  each panel's own live pose, and each of the four lamps' own light
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/components-in-unreal-engine)
- `movement-components` — the only trigger in the task is locomotion; a crate reaches a
  pad because a character with a movement component walked into it
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/movement-components-in-unreal-engine)

**Production pattern.** This is the ordinary shape of *adding a puzzle to a level that
already has one*. Epic's own free sample projects ship exactly this pair: a generic
pressure-plate → door chain used all over a level, and one door that needs a
special-cased condition
(https://dev.epicgames.com/documentation/en-us/unreal-engine/sample-game-projects-in-unreal-engine
— the Stack-O-Bot sample, which is where this task's corpus row was originally set).
The wider pattern — extend a shipped gameplay system for one new case without
regressing its existing consumers — is what Epic's Lyra documentation describes as the
normal way to work in a project that already exists
(https://dev.epicgames.com/documentation/en-us/unreal-engine/lyra-sample-game-in-unreal-engine).
The specific move the task grades — *the specialisation belongs to the consumer that
needs it, not to the shared primitive every other consumer depends on* — is the single
most common way a real feature addition breaks a shipped level.

**How the concepts interact, and where a fix in one breaks another.** There are two
places a first-pass fix genuinely fights itself, and the whole task is built around
them.

*The shared question.* The pads answer one question — *who is resting on me* — and the
answer counts people and crates alike, because the old door is opened by a person and
by nothing else. A gate needs the same pads to yield an answer that counts crates,
counts them by name, and counts a person for nothing. Doing that where occupancy is
computed is one line, is what the requirement literally asks for, produces gates that
are correct in every respect — and the old door never opens again. Doing it by
aggregating the shipped answer differently (all pads instead of any pad) keeps the old
door perfect and lets a person standing on a gate pad, or a crate the gate is not cut
for, swing a gate wide. The only way through is to decide that the narrowing belongs to
the **gate's own question** and not to the yard's pads.

*The shared instance.* Both gates are the same class, over the same pads, watching the
same crates, and they must disagree — so every part of the answer has to be reached
through *this* barrier: its pair, its pads, its lamps. A rule kept anywhere the two
gates share (a static, a singleton, a level-wide aggregator, a "the gate" resolved once
at `BeginPlay`) is right for one of them and wrong for the other, and the lamps make
the same point one dwell earlier: with the near crate alone at home, the same crate
lights the arch gate's **first** lamp and the second gate's **second**.

## Prompt given to the agent

> The deliverable is C++ source under `Source/ThirdPerson/` — the writable gameplay
> module on this project. Nothing you write may live anywhere else.
>
> **The yard as you find it.** An old door stands at the north end of the yard with a
> floor pad in front of it. It works, and it has worked for years: while somebody is
> standing on that pad the old door is open, and the rest of the time it is shut.
> Thirty metres east there is a second door with its own pad that nobody ever goes
> near. Both doors start shut.
>
> **Standing on a pad** means the middle of your solid body being within **100 cm** of
> the pad's centre, measured flat with height ignored, with the bottom of that body
> down on the pad's own level rather than up in the air. That is true of a person and
> it is equally true of a crate, and the yard has never cared which.
>
> **How the yard behaves today, before you touch it.** One rule runs every pad in the
> yard: while any single body — a person or a crate — is resting on a pad, whatever
> barrier that pad answers for is open, and otherwise it is shut. That one rule is what
> makes the old door work, and **the old door's behaviour has to survive whatever you
> do.**
>
> **The old door is judged exactly the way it is judged today, and that does not
> change.**
>
> - Within **1.20 s** of somebody stepping onto its pad, its panel must be at least
>   **80 degrees** from the pose it starts play in.
> - Within **1.20 s** of the last person stepping off, it must be back within
>   **10 degrees** of that pose.
> - It travels: its panel never moves faster than **720 degrees per second** or
>   **3000 cm per second**, in either direction.
> - It does this every time, not once — as many times as anyone walks on and off it,
>   including after the work below has been built and used.
>
> **What you are here to build. There are TWO new gates hung in the west wall.** Each
> of them has two floor pads of its own, and three crates sit on rails in the yard. A
> crate slides along its own rail between two hard stops when somebody shoves it, and
> one of those stops parks it on a pad. Two of the rails feed a far pad from opposite
> sides, so only one crate at a time can be parked there. **The two gates' pads are
> painted on the same two patches of floor**: a crate parked on one gate's pad is
> resting on the other gate's pad as well, and both gates are looking at the same three
> crates at every moment of the day.
>
> Every crate has a name written on it. **Each gate is cut for two of those names, and
> the two names a gate is cut for are written on that gate**, first and second. **The
> two gates are cut for different pairs, and neither gate's pair tells you anything
> about the other's.** A gate must be open exactly while a crate carrying the first of
> *its* two names and a crate carrying the second of *its* two names are both resting
> on *its* pads, and shut the rest of the time. Either of a gate's two names may be
> resting on either of that gate's two pads. Open and shut are measured for a gate
> exactly as they are for the old door: at least **80 degrees** from its play-start
> pose, or back within **10 degrees** of it, reached within **1.20 s** of whatever
> changed, and never travelling faster than **720 degrees per second** or **3000 cm per
> second**.
>
> When a crate a gate is cut for is shoved off one of that gate's pads the gate must
> shut again, and when it is shoved back on while the other one is still home the gate
> must open again — for either of the two, any number of times, in either order.
>
> **Each gate carries two lamps**, one for each of the two names *that* gate is cut
> for, in that order: a gate's first lamp stands for its first name and its second lamp
> for its second. A lamp is lit exactly while a crate carrying its own gate's name for
> its own slot is resting on one of its own gate's pads, and dark otherwise. They start
> dark. The lamps are the only way anybody outside can tell which crate a gate thinks
> it is holding, so a lamp has to be right within the same **1.20 s**.
>
> **What a gate is cut for is not fixed for the day.** The foreman re-cuts the names
> without announcing anything, and he does it whether or not a crate happens to be
> sitting on a pad at the time — including when nothing else in the yard is moving at
> all. He re-cuts each gate on its own account; he may put a different name in either
> slot, and he may put the same names back in a different order. A gate and its lamps
> have the same **1.20 s** to be right after a re-cut as after anything else. The names
> on the crates and the names on a gate are readable off the things themselves; they
> are written down nowhere else.
>
> **Nothing else in the yard may change.** No other barrier may move: the second door's
> panel must stay within **10 degrees** of its play-start pose from the first frame to
> the last. Do not move a pad, a crate, a rail, a door or a gate, and do not rewrite any
> number or name the yard came with, or the barrier a pad answers for — the foreman's
> re-cut is his to make, not yours. Everything needed to *show* what happens is already
> built and working: each barrier travels its own panel when it is told whether it
> should be open, each lamp has a switch, and each crate slides on its rail when it is
> shoved.
>
> All the times above are wall-clock seconds and must hold whatever the frame rate. Do
> not edit the level, any config file, or any test file. Write your solution in C++
> under `Source/ThirdPerson/`.

## Workspace state pre-task

**Deliverable root: `Source/ThirdPerson/`** (the agent-writable runtime module on this
substrate). `Source/CraftBenchTests/` is deny-listed and a submission file under it is
a SANDBOX-REJECT (exit 4), not a graded FAIL; so are `Content/Maps/`,
`Content/ThirdPerson/`, `Content/Characters/`, `Content/LevelPrototyping/` and every
`Config/` file (no `config_allow` is declared by this task).

Files that **exist** under `Source/ThirdPerson/`:

- The stock UE 5.8 Third Person C++ template sources. No edit needed.
- `Tasks/t3-gate-and-door-cpp/YardBarrierActor.h` / `.cpp` —
  `class THIRDPERSON_API AYardBarrierActor : public AActor`, tagged `YardBarrier`.
  **Both doors in the yard and both new gates are instances of this one class.**
  Supplied and **working**:
  - `Frame` (the root, never moves), two posts and a lintel; `Hinge`, a bare pivot
    carrying nothing but the panel; `Panel`, the 380 x 500 cm part a person watches
    swing, solid and movable.
  - `AngleReadout` — a floating number printing how far the panel has turned from its
    play-start pose, computed from the panel's **own live pose** so the two can never
    disagree. `CutPlate` — a second floating line printing the pair of names this
    barrier is cut for, computed the same way. Both are presentation; nothing reads
    them back.
  - `UPROPERTY(EditAnywhere, BlueprintReadOnly) float OpenAngleDeg`,
    `float TravelRateDegPerSec` — this barrier's own numbers.
  - `UPROPERTY(EditAnywhere, BlueprintReadWrite) FName CutForFirstName`,
    `FName CutForSecondName` — **what this barrier is cut for, in that order.** Re-cut
    during play, without announcement.
  - `GetPadsAnsweringForMe()` and `GetMyLamps()` — the yard's wiring, worked out once
    when play begins from what each pad and lamp says it belongs to. `GetMyLamps()`
    returns them in whatever order the level hands them over.
  - `SetCommandedOpen(bool)` — an override anyone may call from anywhere: the most
    recent call within a frame is what the barrier holds for that frame, and with no
    call the yard's own rule decides. **The barrier never asks who called it.**
  - `virtual bool ShouldBeOpen() const` — **THE RULE THAT ALREADY RUNS**, and the same
    rule for every barrier in the yard: open while any single body is resting on any
    pad that answers for this barrier.
  - A `Tick` that resolves those two, sweeps the panel toward the pose it should be
    holding at `TravelRateDegPerSec` and no faster, and keeps both readouts honest.
  - No reference to a crate's name and no reference to a lamp's switch.
- `Tasks/t3-gate-and-door-cpp/YardPadActor.h` / `.cpp` —
  `AYardPadActor`, tagged `YardPad`. A painted 240 x 240 cm mat flat with the floor,
  non-colliding, walked over and slid over. Supplied and **working**:
  `UPROPERTY(EditAnywhere, BlueprintReadOnly) float ContactRadiusUu`,
  `float GroundedBandUu`;
  `UPROPERTY(EditInstanceOnly, BlueprintReadOnly) AActor* AnsweredBarrier` — **set per
  placed pad; each pad belongs to its own barrier and it is not the pad's to change**;
  and the question the pad has always answered —
  `IsBodyResting(const AActor*)`, `GetRestingBodies(TArray<AActor*>&)`,
  `HasAnyRestingBody()`, which count **people and crates alike**. A marker rides up
  while something is resting here; nothing reads it back.
- `Tasks/t3-gate-and-door-cpp/YardCrateActor.h` / `.cpp` —
  `AYardCrateActor`, tagged `YardCrate`. A solid 120 cm box on a rail. Supplied and
  **working**: `UPROPERTY(EditAnywhere, BlueprintReadOnly) FName CrateName`,
  `float RailLengthUu`, `float ShoveSpeedUu`, `float ShoveReachUu`; `GetRailAnchor()`,
  `GetRailAxis()`, `GetRailParamUu()`; a floating `NamePlate` printing the crate's own
  name; and a `Tick` that runs the crate along its own rail toward whichever hard stop
  somebody is walking it toward, at its own speed, stopping dead at either end and
  never leaving the segment or changing height. It also stops **one footprint short of
  another crate** standing in its way, so two crates whose rails share a stop can only
  take it one at a time. It reads what a body is **asking** to
  do rather than how fast it is managing to move, because a crate you are leaning on
  brings your speed to nothing while you are still walking into it. **It has never
  heard of a pad, a door or a gate.**
- `Tasks/t3-gate-and-door-cpp/GateLampActor.h` / `.cpp` —
  `AGateLampActor`, tagged `GateLamp`. A bracket, a bulb and a point light. Supplied:
  `UPROPERTY(EditAnywhere, BlueprintReadOnly) int32 NameSlot` (0 for the first of its
  own gate's two names, 1 for the second) and a floating plate printing which;
  `UPROPERTY(EditInstanceOnly, BlueprintReadOnly) AActor* LampBarrier`; the switch
  `UFUNCTION(BlueprintCallable) void SetLit(bool)` — which sets the light's intensity
  **and** swaps the bulb's material, a material *swap* rather than a parameter write
  because not every prototype material here carries a colour parameter and a write that
  silently does nothing leaves the state invisible while looking like it worked; and
  `UFUNCTION(BlueprintPure) bool IsLit() const`, read off the light. **Starts dark.
  Nothing throws it.**
- `Content/Maps/L_OldDoorYard.umap` — the
  staged yard, committed binary. World Settings name **no** game mode, so the level
  inherits `BP_ThirdPersonGameMode` and its controller, character and input mappings —
  pressing Play gives a visible, animated, drivable body with no per-task wiring at
  all. What is in it:

  | Element | Placement | Notes |
  |---|---|---|
  | Floor | 9,000 x 9,000 cm, striped every 400 cm, stripes **non-colliding** | speed and distance readable by eye |
  | Old door + its pad | north end, pad 300 cm in front of the panel | cut for nothing |
  | The door nobody goes near + its pad | 3,000 cm east, identical in every property | cut for nothing; the drive never approaches it |
  | The arch gate | west wall | cut for an ordered pair of names |
  | Its two pads | one 700 cm east of the arch gate, one 800 cm south of that | both answer for the arch gate |
  | The second gate | the same wall, 2,100 cm further west | cut for a **different** ordered pair |
  | Its two pads | **the same two patches of floor**, painted over the arch gate's and 3 cm proud | both answer for the second gate |
  | Four `AGateLampActor`s | two on each gate's frame, slots 0 and 1 | start dark |
  | Three `AYardCrateActor`s | one rail feeds the near pad; two feed the far pad **from opposite sides** | each parks its crate on the pad centre at one stop, 900 cm off at the other |
  | PlayerStart | on the floor, south of the old door's pad, facing it | |
  | Backdrop + landmarks | a low back wall and two differently sized posts, **non-colliding** | a moving camera is distinguishable from a still one |
  | Test harness | one placed test-harness actor | lives in a module the agent can neither read nor modify |

  **The three crates' names, the pairs the two gates start cut for, the pads' radii,
  the barriers' travel rates and the rails' lengths are deliberately NOT in this
  section.** They are readable in the level, on the things themselves.

- `cameras.json` (the camera-plan lane; not part of this release) —
  the presentation-only camera plan, outside the project tree and outside anything the
  agent writes. Non-gating.

Files that **do not exist**:

- No code anywhere that knows what a crate is called, that treats one barrier
  differently from another, or that throws a lamp's switch. No Blueprint subclass, no
  level edits. The empty submission compiles (L1 green) and FAILs L2 the first time a
  crate is shoved onto a gate pad, because the yard ships deliberately
  **over-permissive**: the supplied one-body-per-pad rule already swings both gates
  wide open on the first crate. Note this is a consequence of the two facts the prompt
  states — the rule that runs every pad today, and what a gate must do — and not a
  hint given on top of them; the prompt no longer says it out loud.
- No test source in the agent's writable path. The test harness lives in a separate
  module the agent can neither read nor modify.

## Verifier specification

The test runs in PIE from
`Content/Maps/L_OldDoorYard.umap` on the
**ThirdPerson** substrate, ticked at a fixed deterministic step
(`-deterministic -FPS=<rate>`), **twice**: once at 60 and once at 20
(`fps_legs: [60, 20]`), each in its own PIE process. Every deadline in the task is a
wall-clock second, so a tick counter fitted to 60 Hz is made to fire at the wrong wall
time.

Verification primitive: **pie-checkpoint-sampling** plus an every-frame readback of
four barriers' **panel poses** and four lamps' **light intensity** — what a reviewer
sees — over a fixture-driven walk, compared against the fixture's own running model of
the whole rule.

### The fixture runs the same rule

Every frame the fixture re-reads, live and by property name: each of the **six** pads'
centre, `ContactRadiusUu`, `GroundedBandUu` and `AnsweredBarrier`; each of the **four**
barriers' `OpenAngleDeg`, `TravelRateDegPerSec`, `CutForFirstName` and
`CutForSecondName`; each crate's `CrateName`, `RailLengthUu` and live transform; each
of the **four** lamps' `NameSlot` and `LampBarrier`. It then steps its own model: the
**same** resting predicate (the middle of a body's colliding bounds within the pad's own
`ContactRadiusUu` of the pad centre measured flat, and the base of those bounds within
`GroundedBandUu` of the pad's own level), the same any-body rule for a barrier cut for
nothing, and the same both-names-home rule for a barrier cut for a pair — **applied per
barrier, from that barrier's own pads and that barrier's own two names**. Every gate
compares the yard's visible state against that model.

The model is written once and runs four times, which is the point: the fixture has no
notion of "the gate" either. A lamp's expectation is
`NamedCrateHome(its own barrier, that barrier's name in its own slot)`, so the two
gates' slot-0 lamps stand for different names at the same instant.

**The fixture never calls the submission's code.** It re-implements the disclosed
resting predicate from live transforms rather than calling `AYardPadActor`'s copy of
it, because that copy is in the agent's writable module: a submission that widened it
would otherwise make the model agree with itself. `TheYardIsNotYoursToRewire` pins both
radii, so the two can only disagree if a submission changed a number the prompt tells
it not to change.

### Why the two models cannot drift apart

1. **The predicate is disclosed in full** — flat, from the pad's centre, bounded by a
   number written on the pad, with the base of the body on the pad's own level. There
   is no measurement origin to guess.
2. **Every crate stop is deep inside or far outside its pad.** The parking stop puts a
   crate's centre within 10 uu of the pad centre against a 100 uu radius; the other
   stop is 900 uu away. A crate crosses the boundary in one clean pass at a fixed
   220 uu/s and is never left grazing it.
3. **Every judged dwell is entered by a crate that has come to a hard stop**, so the
   model's state is constant for the whole dwell rather than being sampled mid-motion.
4. `PrepareTest` refuses to start unless every crate's parking stop lands inside its
   pad's own radius by a factor of at least 5, unless the other stop is outside it by
   at least 5, and unless the two rails that feed the contested pad approach it from
   opposite sides (their axes' dot product < -0.8), so parking one physically excludes
   the other.

### The drive

**Adaptive, not a fixed route.** Every shove is *"push until this crate's rail
parameter is at the stop"*, never *"push for T seconds"*; every walk is *"until
arrival"*; every dwell is a wall-clock hold **after** the state it is testing has
settled. The character is the PIE-supplied pawn
(`UGameplayStatics::GetPlayerPawn(World, 0)`), driven through the shipping per-frame
`AddMovementInput` timeline — the same path a human drives with WASD (Tier 1 of the
standard input driver convention; no key press is ever injected).

Twenty phases. Dwells are 3.5 s so that at least 1.7 s of every dwell survives the
settle suppression below.

| Phase | What the character does | What it is for |
|---|---|---|
| — | *(`PrepareTest`, before any judged frame: the fixture re-cuts the gate)* | **RE-CUT #0** — the pair the drive below assumes is written by the fixture, over a different pair saved in the level. Nothing the submission can read holds the graded pair |
| 0 | walk to the old door's pad | arrival (gates off — the character may spawn anywhere) |
| 1 | stand on it, then step off | **old-door cycle 1** — reported as the explicit checkpoint-0/1 baseline pair |
| 2 | stand on it, then step off | **old-door cycle 2** — the second half of the baseline |
| 3 | walk west; shove crate A home on the near pad | first single-crate dwell — gate shut, lamp 0 lit, lamp 1 dark. **THE EMPTY SUBMISSION DIES HERE** |
| 4 | shove crate B home on the far pad from the east | both home — gate open within 1.20 s, both lamps lit |
| 5 | shove B off; shove crate C home on the far pad from the west | B leaving shuts the gate; **C is not a name the gate is cut for**, so it stays shut and lamp 1 stays dark |
| 6 | shove C off; shove B home again | the far crate's re-add re-opens the gate |
| 7 | shove A off; stand on the now-empty near pad, B still home | **the runner is not a crate** — 3.5 s with a person squarely on a gate pad |
| 8 | step off; shove A home | the near crate's re-add re-opens the gate |
| 9 | walk east; stand on the old pad, then step off | **old-door cycle 3** — after the gate has been opened, re-shut and re-opened. **W2 DIES HERE** |
| 10 | walk west; shove B off, shove A off | both gate pads empty, gate shut |
| 11 | *(the fixture re-cuts the gate)* | **RE-CUT #1**, both pads empty. Gates suppressed 1.5 s |
| 12 | shove B home on the far pad | B is now cut for **nothing** — gate shut, **both** lamps dark |
| 13 | shove B off; shove A home on the near pad | A is now the **second** name — gate shut, **lamp 1** lit, lamp 0 dark |
| 14 | shove C home on the far pad from the west | C is now the **first** name — gate open, both lamps lit |
| 15 | shove A off; stand on the empty near pad, C still home | **the runner is not a crate**, second instance |
| 16 | step off; shove A home | gate opens again, both lamps lit |
| 17 | *(the fixture re-cuts the gate)* | **RE-CUT #2, with nothing moving.** Suppressed 1.5 s, then judged |
| 18 | walk east; stand on the old pad, then step off | **old-door cycle 4** — after every re-cut |
| 19 | — | the run-level gate |

**The second gate, over the same phases.** It is cut for its own pair and never named
in the table above, because the drive does nothing for it: it watches the same crates
land on the same patches of floor and has to reach a different answer. Traced against
the same steps, with the crates that are home in brackets:

| Phase | What is home | The arch gate | The second gate |
|---|---|---|---|
| 3 | near crate | shut, its slot-0 lamp lit | shut, its **slot-1** lamp lit — the same crate, the other slot |
| 4 | near + east | **open** | shut |
| 5(b) | near + west | shut | **open** |
| 6(b) | near + east | **open** | shut |
| 7 | east, runner on the near pad | shut | shut |
| 8-9 | near + east | **open** | shut |
| 12 | east | shut, both lamps dark | shut, its slot-1 lamp lit |
| 13 | near | shut, its **slot-1** lamp lit | shut, its **slot-0** lamp lit |
| 14 | near + west | **open** | shut |
| 16 | near + west | **open** | shut |
| 17 | near + west, **nothing moving** | must come **DOWN** | must come **UP** |
| 18 | near + west | shut | open |

**The three re-cuts.** None is announced and none moves anything. Each writes BOTH
gates, to different pairs.

- **Re-cut #0** (in `PrepareTest`, before the first judged frame and before the drive
  starts): the fixture writes the pair the whole phase table assumes,
  *(A's name, B's name)*, over whatever the committed level was saved holding — and the
  level is deliberately saved holding a **different** pair, *(C's name, A's name)*.
  **This is what makes a hard-coded answer wrong from the first frame rather than from
  phase 12.** The only place the pair is legible before the run is the level, and the
  level's pair is not the pair the run grades; the fixture's is, and the fixture is in a
  module the submission can neither read nor modify. A correct answer never notices,
  because a correct answer reads the pair off the gate at the moment it needs it — which
  is exactly what the prompt promises and the only thing being asked for. Note the
  order: PIE fires `BeginPlay` on every placed actor **before** `PrepareTest`, so an
  answer that snapshots the pair in `BeginPlay` holds the level's pair, not the graded
  one, and dies at phase 3 on the lamps and at phase 4 on the panel.
  **The level's saved pair must itself be playable by hand** (see the
  HARNESS-PRECONDITION list: every pair the gate is later required to OPEN under must
  include the near-pad crate's name, because the two far-rail crates contest one pad and
  can never be home together — re-cut #2's pair is the deliberate exception, and the
  reason the gate must come down there).
- **Re-cut #1** (phase 11, both patches of floor empty, both gates shut): the arch
  gate's pair goes from *(A's name, B's name)* to *(C's name, A's name)*, and the
  second gate's from *(C's name, A's name)* to *(A's name, B's name)* — **they swap**.
  Three separate answers die on it. An answer that read the pair when play began keeps opening for
  A + B. An answer that identified the crates **positionally** — "the near pad's crate
  is the first name, the far pad's is the second" — now lights the wrong lamp at every
  dwell in phases 12-16, because the first name is on the FAR pad and the second on the
  NEAR one. And an answer that cached which crate objects matched keeps ignoring C.
- **Re-cut #2** (phase 17, **nothing moving**: A home on the near patch, C home on the
  far patch, the arch gate open with both its lamps lit, the second gate shut with its
  slot-0 lamp lit): the arch gate's pair goes from *(C, A)* to *(C, B)* — which this
  layout can never satisfy, because B and C contest one pad — and the second gate's
  from *(A, B)* to *(C, A)*, which the crates already standing there DO satisfy. No
  actor changes position, no overlap begins or ends, no contact state changes — only
  the writing on the two gates. Within 1.20 s **the arch gate must be back within 10
  degrees of shut with its lamp 1 dark and lamp 0 still lit, and the second gate must
  be at least 80 degrees open with both of its lamps lit.** Two barriers of one class
  over one patch of floor moving in opposite directions with nothing in the world
  having moved: this is the single most discriminating moment in the run, and it is
  unreachable for any implementation driven purely off overlap edges, for any
  implementation that caches, and for any implementation that decided once which
  barrier was "the gate".

### Settle and suppression

Nothing is judged on a frame where any of these hold. Each is a **widening** of the
disclosed contract, never a narrowing:

- less than **1.80 s** since the fixture's own model last changed anywhere in the yard
  (1.5x the 1.20 s the prompt promises), which is `kSettleS` inside `Suppressed()`;
- inside the **1.5 s** window around each re-cut;
- while the fixture is re-staging, or before phase 0 has arrived.

The first of those was **published and not wired** in the first cut of this fixture —
`kSettleS` and `LastModelChangeAt` were both computed every frame and never read, so
the judge and the spec disagreed about which frames were judged. It is wired now. It is
a cushion on TOP of the per-barrier and per-lamp clocks (`BandVerdict` already allows
each barrier `kBandS + kBandGraceS` = 1.40 s from its OWN last model change, and each
lamp carries the same allowance on its own clock), never a substitute for them; every
dwell is 3.5 s, so at least 1.7 s of each dwell is still judged.

`TheYardIsNotYoursToRewire`'s check on `CutForFirstName` / `CutForSecondName` is the
one thing suspended across the two mid-run re-cut windows, because the fixture is the
one writing them. Re-cut #0 needs no window: it lands in `PrepareTest`, before the first
judged frame, and it is what the check compares against for the rest of the run — the
pair the level was saved holding is never the expected value.

### The sentinel

The checkpoint schedule is **110** calibration checkpoints every 8 s plus a **SENTINEL
at t = 900 s** of world time, because `ACraftBenchFunctionalTest::Tick` ends the test
the moment the last scheduled checkpoint is sampled — an entry beyond the drive is the
only thing that stops the run declaring success before the last phase. The run-level
gate is evaluated when the last phase completes **and** again at the sentinel,
whichever comes first, and only then does the fixture call `FinishTest(Succeeded)`.

**900 s is deliberately generous and is NOT a model of the drive.** The first cut
carried 420 s against a hand-modelled "~215 s", and the model was low by roughly a
factor of two once the step table was counted properly: `StageDrive` builds 16 shove
triples plus 11 standalone walks plus 2 stands = 27 walking steps and 27 dwells, so
hold time alone is ~98 s, push time ~66 s, and the routed walking (two lanes at x=380
and x=-1180, crossings at y=0 and y=-3240, stations 260 uu off each rail end) is
~69,000 uu ≈ 138 s at the template's 500 uu/s before any taper — landing at ~340-400 s.
A drive that overran 420 s would have graded a **correct** reference as a staging
Error. The sentinel is WORLD time, not wall time: under `-deterministic -FPS=<rate>` the
engine advances a fixed step per frame and runs frames as fast as it can, and a run that
finishes normally never reaches the sentinel at all — so raising it costs a passing leg
nothing. **It stays at 900 until the orchestrator reads the measured completion time out
of the `[t3-olddooryard] run complete at t=` line on both legs and re-tightens it to
about 1.5x the larger measurement.**

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64 Development"
        and "ThirdPerson Win64 Development"
```

### L2 — AFunctionalTest behavioral trace

**Gate precedence, in the order the fixture evaluates them. Exactly one of 4-8 is armed
on any judged frame, so a named FAIL is never a race between two of them. 3 and 9 judge
DIFFERENT barriers from 4-8 and from each other, so neither can ever contend with
them.**

```text
1  TheYardIsNotYoursToRewire       -- every judged frame, and on every frame from the
                                     first; all four barriers, six pads, three crates,
                                     four lamps
2  TheDoorNobodyTouchesNeverMoves  -- every frame from the first, and again at every
                                     calibration checkpoint
3  TheOldDoorStillOpensInsideItsBand         -- EVERY judged frame (its subject is the
                                               OLD DOOR; its model is shut everywhere
                                               outside phases 1, 2, 9 and 18, so those
                                               are where it can distinguish anything)
4  TheRunnerIsNotACrate                      -- phases 7 and 15
5  TheGateAnswersToWhatItIsCutForRightNow    -- phases 12-14 and 17
6  TheGateShutsWhenACrateLeavesAndOpensWhenItComesBack -- phases 5(a), 6, 7(a), 8, 15(a), 16
7  TheGateStaysShutUntilBothItsCratesAreHome -- every other judged frame the arch gate's
                                               model says SHUT
8  TheGateOpensWhenBothItsCratesAreHome      -- every other judged frame the arch gate's
                                               model says OPEN
9  TheSecondGateAnswersToItsOwnPair -- EVERY judged frame, from the second gate's own
                                       model. Runs AFTER 4-8 so that at the first
                                       single-crate dwell an over-permissive answer is
                                       named by the arch gate's own gate
10 TheGateLampsNameTheCratesItHolds -- INDEPENDENT CHANNEL, every judged frame, ALL FOUR
                                       lamps, ALWAYS LAST, and only once whichever of
                                       3..9 was armed has already agreed
11 TheGateRoseAgainAfterEveryRecut  -- once, at drive completion or the sentinel; both
                                       gates
```

The lamp gate runs last and only on a frame where every panel gate already agreed, which
gets both halves: a wrong panel is always named by a panel gate, and a right panel with
wrong lamps is always named by the lamp gate.

```text
assert: TheYardIsNotYoursToRewire -- every frame: each pad's centre (2 uu),
        ContactRadiusUu, GroundedBandUu and AnsweredBarrier; each barrier's
        OpenAngleDeg, TravelRateDegPerSec and play-start panel yaw; each crate's
        CrateName, RailLengthUu, ShoveSpeedUu and rail anchor + axis; each lamp's
        NameSlot and LampBarrier; and the gate's CutForFirstName / CutForSecondName
        are exactly what the yard staged for the phase in progress (floats to 0.1%,
        positions to 2 uu, names exactly). ALSO: every crate's live location is
        within 2 uu of the segment between its own two rail stops. Load-bearing
        rather than ceremonial -- the fixture's model reads LIVE transforms and LIVE
        names, so without it a submission that teleported a crate onto a pad, or
        rewrote the gate's names to match what it had hard-coded, would make the
        model agree with itself. The two names are compared against WHAT THE FIXTURE
        ITSELF LAST WROTE (re-cut #0 in PrepareTest, then each mid-run re-cut), never
        against what the level holds, and the name clause is suspended only inside the
        two mid-run fixture-owned re-cut windows.

assert: TheDoorNobodyTouchesNeverMoves -- every frame from the first to the last:
        the twin door's panel is within 10 deg of its play-start pose. The twin is a
        matched instance of the same class with a matched pad 3000 cm east, and the
        drive never goes within 2000 uu of it. Catches any level-wide answer (open
        every barrier when the two-crate condition holds, drive all barriers from one
        aggregator, iterate every actor of the class) and any answer that binds the
        new rule to the CLASS rather than to the one barrier that is cut for names.

assert: TheOldDoorStillOpensInsideItsBand -- THE HEADLINE PRESERVATION GATE, measured
        identically before and after the agent's work. Four cycles: two BEFORE the
        character ever touches a crate (reported as the explicit checkpoint-0/1
        baseline pair), one AFTER the gate has been opened, re-shut and re-opened, and
        one AFTER the second re-cut. In every cycle the old door's panel must reach
        >= 80 deg from its play-start pose within 1.20 s of the character's body
        entering the old pad's own ContactRadiusUu, must return to within 10 deg of
        that pose within 1.20 s of it leaving, and its panel component must never
        exceed 720 deg/s or 3000 cm/s in either direction on any judged frame. The
        message names the cycle index, the elapsed seconds, the angle reached and the
        two baseline cycles' own numbers, so a regression is reported against a
        measurement from the same run rather than against a constant.

assert: TheRunnerIsNotACrate -- at phases 7 and 15 the character stands squarely on an
        EMPTY gate pad (its body within that pad's own ContactRadiusUu of the centre,
        grounded) while exactly one correctly-named crate is home on the other gate
        pad, for 3.5 s. The arch gate's panel must stay within 10 deg of shut and the
        lamp for the ABSENT name must stay dark. This is the gate that catches the
        single most likely submission -- reusing the supplied any-body pad occupancy
        and requiring only that both of the gate's pads report occupied. It is judged
        through the SAME BandVerdict arithmetic as every other panel gate, measured
        from the gate's own last model change: the first cut compared the panel angle
        RAW against a 1.50 s window measured from the CHARACTER'S ARRIVAL, so it was
        the only panel gate in the fixture with no reference to the gate's own clock
        and none of the 0.20 s frame-ordering grace the others carry. It survived only
        because the step table always precedes it with a 3.5 s dwell, i.e. it was
        correct by accident of staging rather than by construction. The arm window is
        now 2.00 s -- above kBandS + kBandGraceS -- and is a floor, not the contract. The message names which pad the character is standing on,
        which crate is home, and what the gate is cut for right now.

assert: TheGateAnswersToWhatItIsCutForRightNow -- through the aftermath of all three
        re-cuts. Re-cut #0 lands in PrepareTest, so its aftermath is the WHOLE RUN: the
        pair the level was saved holding is not the pair the run grades, and any answer
        that read the pair from the level or snapshotted it in BeginPlay is wrong from
        the first judged frame -- it lights lamp 1 for A at phase 3 where lamp 0 is
        wanted, and leaves the gate shut at phase 4 where it must be open.
        After re-cut #1: parking B leaves the gate shut with BOTH lamps dark;
        parking A leaves it shut with LAMP 1 lit and lamp 0 dark; parking C alongside A
        opens it with both lamps lit. After re-cut #2, with no actor in the yard having
        changed position: the gate returns to within 10 deg of shut and lamp 1 goes
        dark while lamp 0 stays lit, both within 1.20 s. The message names the pair the
        gate was cut for before the re-cut, the pair it is cut for now, which crates are
        home, and what the yard is showing.

assert: TheGateShutsWhenACrateLeavesAndOpensWhenItComesBack -- from a fresh both-home
        state the drive shoves the FAR crate off (the gate must be within 10 deg of
        shut within 1.20 s of it leaving the pad's radius), shoves it back on (>= 80 deg
        within 1.20 s), then does the same independently with the NEAR crate; and the
        whole remove/re-add pair is driven a SECOND time later in the run, after the
        first re-cut, with a different crate holding the far pad. A one-shot latch, an
        open-on-overlap-enter with no leave handling, and an any-two-bodies counter all
        die here.

assert: TheGateStaysShutUntilBothItsCratesAreHome -- armed through every zero-crate,
        single-crate and wrong-crate dwell not owned by a gate above: the gate's panel
        is within 10 deg of its play-start pose. Covers zero crates, either name alone,
        and the identity case the corpus never had (the third crate, whose name the gate
        is not cut for, parked on the contested far pad). THIS IS THE GATE THE EMPTY
        SUBMISSION DIES ON, at phase 3.

assert: TheGateOpensWhenBothItsCratesAreHome -- on every judged frame where a crate
        carrying the gate's currently-written first name and a crate carrying its
        currently-written second name are both resting on one of its two pads, the
        gate's panel must be >= 80 deg from its play-start pose, reached within 1.20 s
        of the second crate parking, without exceeding the travel-rate caps. Judged at
        four separate both-home episodes across the run and across every re-cut.

assert: TheGateLampsNameTheCratesItHolds -- INDEPENDENT CHANNEL, on every judged frame,
        ALL FOUR LAMPS, always evaluated LAST: a lamp is lit exactly while a crate
        carrying the name written RIGHT NOW in that lamp's own slot ON ITS OWN GATE
        rests on one of THAT gate's pads -- read off each lamp's own light (visible,
        not hidden, intensity > 0), never off a flag. Independent of the panel: a
        submission can raise a gate correctly and never light a lamp, or light both
        whenever a gate is open, which fails at every single-crate dwell where exactly
        one lamp must burn. And independent PER GATE: at phase 3 the near crate alone
        is home and it lights the ARCH gate's slot-0 lamp and the SECOND gate's slot-1
        lamp, so an answer that collects the level's lamps and indexes them globally,
        or that drives all four from one computed state, is named here one dwell before
        any panel disagrees. The message names each lamp, its gate, the name written in
        its slot right now, which crates are resting on that gate's own pads, and which
        lamps are burning.

assert: TheSecondGateAnswersToItsOwnPair -- THE IN-SCENE CONTROL ON THE SIDE THE
        SUBMISSION ACTUALLY BUILDS, armed on every judged frame. The second gate is a
        matched instance of the same class as the arch gate, its two pads are painted
        over the arch gate's two pads (same centres to within 2 uu, same radius, same
        band, 3 cm proud so the mats do not z-fight), it watches the same three crates,
        and it is cut for a DIFFERENT ordered pair, re-cut on its own schedule. So
        nothing about the layout can separate the two gates: only what is written on
        each of them can. Its panel is judged through the same BandVerdict as the arch
        gate's, from its own model and its own last change. Traced against the step
        table it disagrees with the arch gate at four separate dwells -- at phase 4 the
        arch gate is OPEN and it is SHUT; at phase 5 with the west crate home the arch
        gate is SHUT and it is OPEN; at phase 14 the arch gate is OPEN and it is SHUT;
        and at phase 17, with NO ACTOR IN THE YARD MOVING, the arch gate must come DOWN
        while it comes UP. Every answer written for "the gate" rather than for "a
        barrier that is cut for names" dies here: a TActorIterator that finds the first
        barrier carrying names, a rule kept in a static or a singleton, a level-wide
        aggregator, a "which crates are home" cached once for the yard. The message
        names both gates' pairs at that instant.

assert: TheGateRoseAgainAfterEveryRecut -- run-level, and it now covers BOTH gates.
        The arch gate reached >= 80 deg at least once before re-cut #1, at least once
        between the two re-cuts, and returned to within 10 deg of shut in between each
        pair. The second gate rose before re-cut #1 (at phase 5, while the arch gate
        was shut), came home again, and rose AFTER re-cut #2 -- on the same frames the
        arch gate was coming down, with nothing in the yard moving. A gate that latches
        open can only rise once; a gate that recomputes only on an overlap edge never
        moves at all when nothing has moved; and one answer written for THE gate can
        never do both of those at once.
```

**Staging faults are attributed, and the route is real but narrower than the label.**
The first cut of this spec claimed the `HARNESS-PRECONDITION:` prefix ends a run as a
non-graded verdict. The PREFIX does nothing — `grep -rn "HARNESS-PRECONDITION" tools/
--include=*.py` returns only `tests/test_verdict_taxonomy.py`. What actually routes is
the RESULT ENUM: `layers/l2_pie.py::_harness_precondition` matches the engine's own
`FinishTest TestResult=Error.` emission, and `run_task.py` predicate (4c) routes that
out of the graded denominator to **exit 7 HARNESS-ERROR** — but only when
`tests_run == 0`, i.e. when no Passed/Failed/Skipped result was banked alongside it.
Every staging exit here is a terminal `FinishTest(EFunctionalTestResult::Error, ...)`
with no graded result before it, so the route does apply.

**That route carries an invariant this fixture must honour** (`run_task.py` (4c),
the internal design note (not shipped)): *any `::Error` whose guard reads an agent-writable
input is a denominator opt-out.* Several of the exits below are drive-dependent, and a
submission can influence the drive — so before any deadline or sentinel overrun is
written off, `PreservationStillHolds` re-checks `TheOldDoorStillOpensInsideItsBand`,
`TheDoorNobodyTouchesNeverMoves` and `TheYardIsNotYoursToRewire` **unconditionally**, and
a jammed or rewired yard is reported as the graded FAIL it is. The residual risk is a
submission that stalls the drive while leaving those three intact; the defence against
that is that the sentinel is now far past the measured drive rather than close to it,
so a stall has to be real. **The orchestrator must add this fixture's `::Error` sites to
the internal design note (not shipped) when it lands.**

The staging exits: wrong actor counts (4 barriers, 6 pads, 3 crates, 4 lamps); the two
gates' pads not painted on one patch of floor (centres more than 2 uu apart, or
mismatched radius or band); either door shipping cut for a pair; the two gates shipping
cut for the same pair, or graded against the same pair; a barrier, pad, crate or lamp that does not expose its
numbers readably; the gate not cut for two distinct names that are two of the three
crates' names; **any pair the drive later requires the gate to OPEN under that does not
include the NEAR-pad crate's name** — that is the pair saved in the level (so a human can
play the yard by hand), the pair `PrepareTest` writes, and re-cut #1's — because the two
far-rail crates contest a single pad and can never be home at the same time, so such a
pair makes the gate unopenable and the task unwinnable through no fault of the
submission. **Re-cut #2's pair is the deliberate exception**: it names the two far-rail
crates precisely so the layout cannot satisfy it, which is why the gate must come down
and stay down with nothing in the yard moving, and the drive never asks it to open again.
Also: two crates carrying the same name; a crate whose parking stop is not
deep inside EITHER of the co-located pads' radii or whose other stop is not far outside
them; the two rails feeding the contested pad not opposing each other; the near rail
and the contested rails closer than two lane widths apart; a barrier whose disclosed
travel rate cannot clear 80 degrees inside 1.20 s with 2x margin; the twin door not
matching the old door on every staged number; a route that comes within 2,000 uu of the
twin pair; a lamp bolted to something that is not one of the two gates, or a gate not
carrying exactly one slot-0 and one slot-1 lamp; anything blocking the walking route;
or a phase that overruns its derived deadline.

## Requirement-to-assertion map

| Prompt requirement | Gate that checks it | When that gate does NOT run |
| --- | --- | --- |
| the old door opens within 1.20 s of somebody standing on its pad, and shuts within 1.20 s of the last person leaving | `TheOldDoorStillOpensInsideItsBand` | **never** — it is armed on every judged frame. Its subject is the old door, whose model is shut everywhere outside phases 1, 2, 9 and 18, so those are the only phases where it can DISTINGUISH anything; but a submission that swings the old door at, say, phase 5 is named by it there. (The first cut of this table said "outside phases 1, 2, 9, 18", which described a gate the fixture does not have.) |
| the old door does it **every** time, not once, including after the gates are built and used | same gate, four cycles, two of them after the agent's work is exercised | as above |
| the panel never travels faster than 720 deg/s or 3000 cm/s | same gate, on every judged frame of every cycle, and the same clause inside `TheGateOpensWhenBothItsCratesAreHome` for the gate | frames the settle rule suppresses |
| standing on a pad = middle of the body within 100 cm of the centre, flat, base on the pad's level | the fixture's model uses exactly that predicate, re-implemented from live transforms; `TheYardIsNotYoursToRewire` pins both radii so it cannot be widened underneath | never |
| a person or a crate both count for the pads | `TheOldDoorStillOpensInsideItsBand` (a person must count) and `TheGateStaysShutUntilBothItsCratesAreHome` (a crate must count, at phase 3) | as above |
| a gate is open exactly while crates carrying **both** of ITS two names are home | `TheGateOpensWhenBothItsCratesAreHome` and `TheGateStaysShutUntilBothItsCratesAreHome` for the arch gate; `TheSecondGateAnswersToItsOwnPair` for the other | frames a windowed gate above owns (arch only) |
| the **two gates are cut for different pairs** and neither's pair says anything about the other's | `TheSecondGateAnswersToItsOwnPair`, on every judged frame, at four dwells where the two gates' correct panels differ; and `TheGateLampsNameTheCratesItHolds` at phases 3 and 13, where one crate lights opposite slots on the two gates | never |
| either name may be on either of THAT gate's pads | `TheGateAnswersToWhatItIsCutForRightNow` at phases 13-14, where the first name is on the FAR pad and the second on the NEAR one, plus the lamp gate throughout | outside phases 12-14 |
| a crate the gate is not cut for is not enough | `TheGateStaysShutUntilBothItsCratesAreHome` at phase 5 (C on the contested pad) and phase 12 (B after re-cut #1) | outside those dwells |
| a person on a gate pad never counts toward anything | `TheRunnerIsNotACrate` | outside phases 7 and 15 |
| shoving a crate off shuts the gate; shoving it back on re-opens it; either crate, any number of times | `TheGateShutsWhenACrateLeavesAndOpensWhenItComesBack`, both crates, twice | outside phases 5-8 and 15-16 |
| each gate carries two lamps, one per name **in that order**, lit exactly while a crate carrying that gate's name for that slot is home on that gate's pads, dark otherwise, starting dark, right within 1.20 s | `TheGateLampsNameTheCratesItHolds`, every judged frame, all four lamps, each against its own gate, read from the light | only on a frame where a panel gate already failed |
| the pairs are re-cut without announcement, each gate on its own, including with nothing moving | `TheGateAnswersToWhatItIsCutForRightNow` for the arch gate (all three re-cuts: #0 in `PrepareTest`, so from the first judged frame, then #1 and #2), `TheSecondGateAnswersToItsOwnPair` for the other, and `TheGateRoseAgainAfterEveryRecut` for both at run level | never, once the drive has arrived: re-cut #0 arms it for the whole run, and phases 12-14 and 17 are where the transitions are |
| the second door's panel stays within 10 deg from the first frame to the last | `TheDoorNobodyTouchesNeverMoves` | never |
| do not move a pad, crate, rail, door or gate, and do not rewrite any number or name, or the barrier a pad answers for | `TheYardIsNotYoursToRewire`, every frame, all four barriers and six pads, including "each crate is on its own rail" and "both doors are still cut for nothing" | only the four name slots on the two gates, only inside the fixture-owned re-cut windows |
| all times are wall-clock and hold whatever the frame rate | `fps_legs: [60, 20]` runs the whole drive twice in two PIE processes | never |
| C++ under `Source/ThirdPerson/` | sandbox: a file outside the writable set is exit 4, not a graded FAIL | never |

## Reference solution metadata

- **Files touched**: 2 —
  `Source/ThirdPerson/Tasks/t3-gate-and-door-cpp/YardBarrierActor.h`
  and `.cpp`. The other three supplied pairs are **byte-identical to the scaffold**,
  and that is the point of the task: the correct change is small and lands in exactly
  one place, and the most natural wrong changes are the same size and land in the wrong
  one.
- **LOC**: **135 added / 17 removed** against the scaffold, measured with `diff -u`
  (57 added in the header, 78 in the source; the removals are the rewrapped
  `ShouldBeOpen` body). Of the additions about **62 lines are code** — one branch in
  `ShouldBeOpen`, the predicate that decides which branch a barrier takes, one
  name-lookup helper, one slot accessor and one lamp loop — and the rest is comment.
  **The reference is unchanged by the second gate**, which is the strongest evidence
  available at authoring time that the second gate is coupling and not a riddle: an
  answer written per instance, from the instance's own data, is already right for N
  gates, and only an answer that decided there was one gate has to be rewritten.
- **Senior-dev hours**: **5–8**, the lower half of T3. The hours are not typing:
  1. ~1 h reading the yard and working out that the pad's occupancy question is
     *shared*, that the old door is its only other consumer, and that nobody ever puts
     a crate on the old door's pad. This is the whole task and it is invisible until
     you look for the old door's other consumer — the prompt says the old door must
     keep working, but not that the obvious fix is what breaks it.
  2. ~1 h deciding where the narrowing goes. Both wrong answers are one line and both
     look better than the right one.
  3. ~1.5 h on identity: names off the crates rather than positions or object
     pointers, an ordered pair rather than a set, and either name allowed on either
     pad.
  4. ~1 h on the lamps as a per-slot channel independent of the panel, in slot order.
  5. ~1.5 h on the reading discipline: every name re-read at the point of use, which
     only shows up when a pair is re-cut with nothing moving, and which rules out both
     the BeginPlay cache and the overlap-edge design. Nothing in the scaffold now says
     to do this — the first cut of the scaffold carried "read them at the moment you
     need them" as an imperative comment, which handed over the entire defence.
  6. ~1 h on the fact that there are TWO gates over one patch of floor: finding that
     every part of the answer has to be reached through *this* barrier, and that a
     single computed "which crates are home" is right for one gate and wrong for the
     other one dwell later.
  7. ~1 h verifying the old door still lands inside its band after all of it.
- **Why T3 rather than T2**: the tier here is carried by the *coupling*, not the
  volume. Two subsystems share a class and a question and want opposite answers from
  it; a named gate sits on each side; and the load-bearing work is **not breaking**
  code that already works, which no single-mechanism task can ask for. See `notes.md`
  for the honest counter-argument on LOC.

## Anti-gaming notes

> **On disclosure.** Every defence below rests on a contract the prompt states in
> positive form — "a gate must be open exactly while a crate carrying the first of its
> two names and a crate carrying the second of its two names are both resting on its
> pads, and shut the rest of the time", plus the rule the yard runs today. It does NOT
> rest on the prompt naming the failure. The first cut of this spec had a sentence in
> the agent-visible prompt for almost every note below — that a person is not a crate,
> that names and not positions are the question, that the answer must be re-read at the
> point of use — which made the whole pre-mortem a transcription exercise. Those
> sentences are gone; the values they carried are still entailed by the contract, which
> is what keeps every gate disclosed.

1. **"A barrier is open while ALL of the pads that answer for it are occupied."**
   *Failure mode*: THE MOST LIKELY SUBMISSION. A one-line generalisation of the rule
   already shipping (today: while ANY pad that answers for it is occupied). It
   compiles, it reads beautifully, it keeps the old door working perfectly (one pad, so
   all-of-one == any-of-one), and it turns the gate from an OR into an AND, which is
   90% of the stated requirement. *Defense*: it reuses the supplied occupancy, which
   counts ANY resting body, so it opens the gate when the character stands on one gate
   pad while one crate is home — `TheRunnerIsNotACrate` at phase 7 — and when the third,
   un-named crate is parked on the contested far pad —
   `TheGateStaysShutUntilBothItsCratesAreHome` at phase 5. It also never lights a lamp:
   `TheGateLampsNameTheCratesItHolds`. Note that it PASSES the headline preservation
   gate; it is the "subsystem A right, subsystem B wrong" half of the coupling.
2. **"The new requirement is about crates, so a pad is occupied when a crate is resting
   on it."** *Failure mode*: THE BROWNFIELD FAILURE THE TASK IS NAMED FOR. The agent
   narrows the shared occupancy test in the one place occupancy is computed, then adds
   name matching and the two-of-two aggregation on top. The gate then behaves
   perfectly — shut for zero, for either alone, for the un-named crate and for a person
   on a pad; open for both; re-shutting and re-opening correctly; lamps correct;
   re-cuts honoured — and **every gate about the new behaviour passes.** *Defense*: the
   old door never opens again, because nobody ever puts a crate on its pad.
   `TheOldDoorStillOpensInsideItsBand` fails at cycle 3, the first cycle after the
   agent's work is exercised, with the two baseline cycles recorded earlier in the same
   run showing the same door meeting the band before the change. This is the
   "subsystem B right, subsystem A wrong" half.
3. **Reading the pair a gate is cut for once when play begins and caching it** — or
   worse, reading it out of the level in the editor and hard-coding it. *Failure mode*:
   the obvious optimisation, and the natural reading of "the gate is cut for two names".
   *Defense*: three things, in the order they bite. (a) `BeginPlay` fires on every placed
   actor **before** `PrepareTest`, and `PrepareTest` is where the fixture writes the pair
   the run is graded against — over a *different* pair saved in the level — so a
   BeginPlay snapshot and a level-read hard-code hold the same wrong pair and are wrong
   from the **first judged frame**: the lamps disagree at phase 3 and the panel at
   phase 4. (b) The pair is then re-cut twice more mid-run with nothing announcing it, so
   a cache refreshed once, or on some event, still fails
   `TheGateAnswersToWhatItIsCutForRightNow`. (c) The lamps fail one dwell earlier than the
   panel in both cases, which is exactly what the lamp channel is for.
4. **Recomputing only inside overlap begin/end handlers.** *Failure mode*: both
   idiomatic and cheaper than a tick, and correct for every crate movement in the run.
   *Defense*: re-cut #2 changes the answer with **no actor moving**, no overlap
   beginning or ending and no contact state changing. `TheGateAnswersToWhatItIsCutForRightNow`
   owns that moment, and `TheGateRoseAgainAfterEveryRecut` names the same failure at
   run level.
5. **Identifying the crates positionally** — "the crate on the near pad is the first
   name, the one on the far pad is the second" — or by object pointer rather than by
   name. *Failure mode*: perfectly correct until the pair changes, and much easier than
   a name lookup. *Defense*: re-cut #1 puts the arch gate's FIRST name on the far pad
   and its SECOND on the near one. The panel is unaffected (both are still home), so
   this is caught by `TheGateLampsNameTheCratesItHolds` at phases 13-14 — which is why
   the lamp channel is graded rather than cosmetic. The two gates sharpen it further:
   at phase 13 one crate on one pad must light the arch gate's slot-1 lamp and the
   second gate's slot-0 lamp at the same instant, so no rule about WHERE a crate is
   standing can produce both.
6. **Latching the gate open on the first both-home moment.** *Failure mode*: the most
   common wrong implementation in the source corpus. *Defense*:
   `TheGateShutsWhenACrateLeavesAndOpensWhenItComesBack` drives four independent
   remove/re-add pairs across two crates and two re-cuts, and the re-trigger convention
   means no single firing can carry the run.
7. **Setting a correct internal flag and never touching a panel or a lamp.** *Failure
   mode*: modelling the state and forgetting the output. *Defense*: nothing private is
   ever graded — the fixture reads the four panels' live poses and the four lamps'
   light intensity. The barrier deliberately exposes no "is open" property of its own, only a
   panel that a person watches swing.
8. **Driving the gate by moving a crate, or by parking one on a pad from code.**
   *Failure mode*: anti-gaming rather than a plausible first pass, but the fixture's
   model reads LIVE transforms, so a teleported crate would make the model agree with
   itself. *Defense*: `TheYardIsNotYoursToRewire` checks every crate's live location
   against the segment between its own two rail stops, every frame, and pins every
   staged number and name.
9. **Making the new rule apply to the barrier CLASS rather than to the barriers that
   are cut for names.** *Failure mode*: an aggregator that iterates every barrier in the
   level and drives them all from the two-crate condition — which happens to leave the
   old door correct in the frames the old door is not being used. *Defense*:
   `TheDoorNobodyTouchesNeverMoves` is gauged from the first frame to the last on a
   matched twin 3,000 cm away that the drive never approaches;
   `TheOldDoorStillOpensInsideItsBand` catches the old door in cycles 3 and 4; and
   `TheSecondGateAnswersToItsOwnPair` catches it at phase 4, where two barriers of the
   same class over the same pads must disagree.

10. **Solving it for THE gate.** *Failure mode*: **the most likely wrong answer in the
    hardened version of this task, and it is entirely reasonable** — locate the gate
    once (a `TActorIterator` for the barrier that carries names, the barrier that owns
    the lamps, the first one found, a tag, a pointer cached in `BeginPlay`), compute
    "are both of its crates home", and drive that one barrier and its two lamps.
    Everything about it is correct for the arch gate; it compiles, it reads well, and
    it passes phases 0-4 outright. *Defense*: there are two gates in the wall, both cut
    for names, both carrying lamps, over the same two patches of floor.
    `TheSecondGateAnswersToItsOwnPair` names it at phase 5, where the second gate must
    open while the arch gate is shut, and again at phase 17, where one must fall while
    the other rises with nothing in the yard moving.
    `TheGateLampsNameTheCratesItHolds` names it one dwell earlier still, at phase 3,
    where two of the four lamps are never thrown. `TheGateRoseAgainAfterEveryRecut`
    names it at run level. **Note what this note is NOT:** the prompt says plainly that
    there are two gates, that each is cut for its own pair, and that neither pair says
    anything about the other's, so this is not a hidden second subject — it is the
    ordinary cost of writing a rule for an instance instead of for a singleton.

11. **One computed answer, shared by both gates and by all four lamps.** *Failure mode*:
    the tidy version of the same mistake — work out once per frame which crates are
    resting on the two patches of floor, then hand that one answer to both gates and
    index the level's four lamps 0..3, or light each gate's lamps from whether that gate
    is open. The crate list is genuinely shared (the pads ARE co-located), so the first
    half is even correct; what is not is treating the PAIRS as shared. *Defense*: at
    phase 3 the same near crate must light the arch gate's slot-0 lamp and the second
    gate's slot-1 lamp, and at phase 13 the reverse — so a global slot index is wrong in
    both directions, and lamps driven off "is my gate open" are wrong at every
    single-crate dwell. `TheGateLampsNameTheCratesItHolds` reads each lamp against the
    name written in ITS OWN slot on ITS OWN gate.

## Hidden invariants

- **The submission's own state is never read; only its consequences are.** The
  fixture's model of what the gate should be doing is never compared against anything
  inside the submission, because it could not be. Every gate is a statement about a
  panel pose and a lamp's light. A submission is free to represent the rule however it
  likes, and to put it on a barrier, a pad, a crate, a lamp or the character.
- **The fixture re-implements the resting predicate rather than calling the pad's.**
  `AYardPadActor::IsBodyResting` lives in the agent's writable module; a submission that
  widened it would otherwise move the model with it. The fixture reads the pad's
  `ContactRadiusUu` and `GroundedBandUu` live (so a re-staged yard moves the drive with
  it) but applies them itself.
- **`GroundedBandUu` is a disclosed literal in prose but not in figures.** The prompt
  says "down on the pad's own level rather than up in the air"; the number is on the
  pad and pinned by `TheYardIsNotYoursToRewire`. It can only ever matter for an airborne
  body, and the drive never produces one — every judged body is a crate on the floor or
  a character standing still. Stated here rather than papered over.
- **The preservation gate is FREE for the empty submission**, and so are the twin
  control and the integrity gate. That is the nature of a preservation gate and it is
  not a dead gate: two plausible real submissions fail it (anti-gaming note 2, and any
  answer that reroutes the shared barrier through the new rule). The empty submission
  still dies at a named gate at phase 3, and it dies on a **wrong-open** rather than a
  never-open — an always-shut stub cannot pass, because phases 4, 6, 8, 14 and 16
  require the arch gate to be open and phases 5, 17 and 18 require the second gate to
  be. Do not add a synthetic requirement to make the preservation gate fail for empty;
  that would be manufacturing difficulty.

- **The old door's side of the coupling is PRESERVATION, and preservation means not
  typing anything.** An adversarial review called this out: the correct diff is purely
  additive, so "getting subsystem A right" costs the agent nothing but restraint. That
  is recorded rather than papered over, because it is what the production pattern
  actually is — a shipped consumer of a shared primitive keeps working precisely by not
  being touched, and the task's job is to make touching it the attractive option. It is
  attractive here: narrowing the pad's occupancy is one line, is what the requirement
  literally asks for, and produces gates that are correct in every respect. The second
  gate was added in the same review because it puts a named gate on the side the agent
  DOES type, which the twin door (cut for nothing, never approached) could never do.

- **The second gate cost the drive nothing.** It adds no step, no dwell and no walking
  — it is judged passively on frames the drive was already producing, exactly like the
  twin door. That is deliberate: the run's wall-clock was already the top risk on this
  task, and discrimination that costs seconds is discrimination that gets cut later.
- **The load-bearing fact is never legible to the submission, and it changes three
  times — for each of two gates.** The three crate names are staged into the committed
  `L_OldDoorYard.umap`; the **pairs the two gates are cut for are not** — the level is
  saved holding one pair per gate and the fixture writes different ones in
  `PrepareTest`, before the first judged frame and after every `BeginPlay` has run. So the only pair a submission could read ahead of time is the
  wrong one, and a hard-coded or BeginPlay-cached answer is wrong from the first judged
  frame rather than from the middle of the run. Two further re-cuts then move it again
  mid-run. Stated precisely, because it is the difference between this task and the
  design it was built from, which had the graded pair baked into the map: what is
  constant across reps is the *sequence* of pairs, not any pair a submission can see. No
  `randomization:` key is declared, because declaring one would claim a per-process
  shuffle the fixture does not perform — the discrimination is in the re-staging, not in
  a seed.
- **`fps_legs: [60, 20]` runs the whole drive twice**, in two PIE processes, each with
  its own wall-clock budget. Every deadline in the task is in wall-clock seconds, so a
  tick counter fitted to 60 Hz misses by 3x at 20 Hz.
- **The supplied travel clears the band by 2.7x, on purpose.** 90 degrees at
  180 deg/s reaches 80 degrees in 0.444 s against a 1.20 s deadline, and the panel's own
  origin moves at ~600 cm/s against a 3000 cm/s cap. The band is a contract on the
  SUBMISSION's decision latency, never a race against the supplied animation, which is
  what keeps a correct answer from failing on a slow frame.

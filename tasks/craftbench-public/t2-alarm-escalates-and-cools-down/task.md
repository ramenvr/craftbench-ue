---
id: t2-alarm-escalates-and-cools-down
substrate: ThirdPerson
set: craftbench-public
tier: T2
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_AlarmYard :: AAlarmEscalationFunctionalTest"]
fps_legs: [60, 20]
---

# t2-alarm-escalates-and-cools-down

A yard alarm with three settings whose **raise numbers and drop numbers are
deliberately different**, so the same sighting count means *watching* on the way
up and *hunting* on the way down. It is fed by two guards whose eyes are not the
same, and it is read out through the floodlights that burn and the pace the
guards walk — **and the floodlights feed back into the guards' eyes**, so the
readout is also an input.

> **Built against the 2026-08-18 difficulty bar.** Two subsystems that genuinely
> interact (a lit floodlight lengthens the reach of the guard walking the round
> it covers, so a bug in the lamp loop changes the sighting count, which changes
> the setting, which changes the lamps); a locally-reasonable wrong answer that
> a named gate catches (one threshold ladder, `stage = f(count)`, which compiles
> and reads right and cannot report two different settings at the same count);
> and every load-bearing number read from the world at runtime, two of them
> changed mid-run by the fixture so no cached constant survives.

## Primary concept

- `ai-perception` — an agent deciding what it can see from its own settings, and
  a system reacting to that decision
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/ai-perception-in-unreal-engine)

The load-bearing behaviour is **a hysteretic state machine driven by a debounced
per-instance perception pass, whose own output changes what the perception pass
sees**. The grade never asks *how*: a `Tick` on the panel, a `Tick` on a guard,
a repeating timer on the character — all pass identically, as long as the yard
settles within the half second the prompt promises.

## Composed concepts

- `actor-lifecycle` — the yard is a fixed cast of placed actors; the logic has to
  live on one of them and be correct from the first frame
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-actor-lifecycle)
- `ps-timers` — a quiet clock that is reset by an event, fires repeatedly, and
  re-arms after it has run out
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/gameplay-timers-in-unreal-engine)
- `ai-components` — per-instance sight settings read off the thing that owns them
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/ai-components-in-unreal-engine)
- `movement-components` — the graded readout includes the pace two patrolling
  actors walk at, each scaled from its own base
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/movement-components-in-unreal-engine)

**Production pattern.** This is the standard stealth-game alarm: a per-guard
sight cone, an awareness meter with separate escalate/de-escalate thresholds so
the state does not chatter at the edge of detection, a decay timer, and a
world-visible response. It is the shape described in Epic's own AI Perception
documentation combined with the hysteresis every shipped stealth game uses; the
floodlight-extends-reach clause is the standard "light level affects detection"
rule from the same genre.

## Prompt given to the agent

> The yard is watched. Two guards walk their rounds all night, and a panel by the
> gate decides how worried the yard is. It has three settings — **calm**,
> **watching**, **hunting**. It begins calm, with nothing counted.
>
> **What a guard can see.** A guard notices the character the player controls
> when they are inside its own reach *and* inside its own view width of whatever
> direction it is facing at that moment. Those two numbers belong to the guard —
> they are set on it, and the arc it covers is painted on the floor around its
> round, so you can see the difference. **The two guards are not set to the same
> numbers.** Measure from where the guard is standing to where the character is
> standing; the yard is flat and **height plays no part**, so ignore it. Exactly
> at the edge of the reach, or exactly at the edge of the view width, still
> counts as noticed. There is **nothing in the yard to hide behind** — no wall,
> post, floodlight or panel ever blocks a guard's view of anything.
>
> **Sightings.** The panel counts sightings. One sighting is the moment the yard
> goes from *nobody* being able to see the character to *somebody* being able to.
> It is a moment, not a length of time. The panel never remembers more sightings
> than the number on its dial; once the count is at that number, further
> sightings add nothing. Every so many seconds with nobody in sight — again, a
> number on the dial — it forgets one sighting, and then another after the same
> again, and so on down to nothing; being seen at all puts that clock straight
> back to zero.
>
> **The settings.** The panel goes **up** a setting the moment the count reaches
> that setting's raise number, and **down** a setting the moment the count falls
> to that setting's drop number. It comes down the same way it went up: one
> setting at a time, as the count falls. **The raise numbers and the drop numbers
> are deliberately not the same.** There is a band of counts in between where the
> panel does not move at all, and inside that band the yard's setting depends on
> which way it got there — the same count can mean watching if you are climbing
> and hunting if you are cooling off. That gap is the whole point of it: a yard
> that works its setting out from the count alone will flap up and down while
> somebody loiters at the edge of a guard's view.
>
> **What the yard shows.** Every setting changes what the yard looks like, and
> those changes are the only thing anyone can see from outside.
>
> - **The floodlights.** Each one carries the setting it burns from. A floodlight
>   is lit exactly while the panel is at its own setting or higher, and dark
>   otherwise. They are not arranged in any tidy order and there is not one per
>   setting — read each light for itself. They start dark, and the calmest
>   setting is not "all of them dark".
> - **The rounds.** Each guard walks at its own base pace multiplied by the
>   panel's scale for the current setting. The two base paces are different, and
>   the scales are on the panel. The guards never chase anybody; they only walk
>   their rounds faster.
>
> **The floodlights are not only a readout.** Some of them throw their light down
> a round, and each of those carries how much further it lets somebody see and
> which round it covers. **While such a floodlight is burning, the guard walking
> the round it covers has that much added to its reach** — so what the yard shows
> changes what the yard notices. What a guard can see at any instant is settled
> by the floodlights as they stand at that instant, before anything changes them.
>
> The yard has **half a second** to catch up after anything changes.
>
> None of this is one-shot. After the panel has come all the way back down to
> calm it must be able to do the whole thing again, as many times as the night
> calls for it.
>
> **The dials are not fixed for the night.** When the watch changes, the sergeant
> swaps which guard walks which round and re-sets some of the dials. Nothing
> announces it. **Whatever the panel reads at the moment you need a number is the
> number**, and whichever guard is on a round is the one whose eyes matter there.
>
> The yard is not yours to rearrange. Do not move the guards, the posts, the
> floodlights or the panel, and do not change any of the numbers written on them
> — a guard's reach, its view width, its base pace, a floodlight's setting or its
> reach bonus, or any dial on the board. Everything the yard needs in order to
> *show* its state is already built and working: each floodlight has a switch,
> each guard has a pace you can set and walks its round by itself. Nothing
> decides when to throw any of it. Because the yard itself is fixed, whatever
> does the deciding has to live on something already standing in it — the panel,
> a guard, a floodlight, or the character.
>
> Do not edit the level, any config file, or any test file. Write your solution
> in C++ under `Source/ThirdPerson/`.

## Workspace state pre-task

**Deliverable root: `Source/ThirdPerson/`** (the agent-writable runtime module on
this substrate). `Source/CraftBenchTests/` is deny-listed and a submission file
under it is a SANDBOX-REJECT (exit 4), not a graded FAIL; so are
`Content/Maps/`, `Content/ThirdPerson/`, `Content/Characters/` and every
`Config/` file (no `config_allow` is declared by this task).

Files that **exist** under `Source/ThirdPerson/`:

- The stock UE 5.8 Third Person C++ template sources. No edit needed.
- `Tasks/t2-alarm-escalates-and-cools-down/WatchGuardActor.h` / `.cpp` —
  `class THIRDPERSON_API AWatchGuardActor : public AActor`, tagged `WatchGuard`.
  Supplied and **working**:
  - `Hull` — a 70 x 180 cm capsule, **the root**, `BlockAll`, movable; plus a
    body mesh and a nose cone so the facing reads at a glance. (A capsule root,
    not the mesh: a mesh made root and offset upward leaves collision half-buried
    in the floor and refuses every swept move.)
  - `UPROPERTY(EditAnywhere, BlueprintReadOnly) float SightRangeUu`,
    `float SightHalfAngleDeg`, `float BasePatrolSpeedUu`,
    `FName RoundTag` — **read them off the guard; the two guards in the yard are
    not set to the same values.**
  - `UPROPERTY(EditAnywhere, BlueprintReadWrite) float PatrolSpeedUuPerSec` —
    **the one that is yours to set.** Initialised to `BasePatrolSpeedUu` in
    `BeginPlay`.
  - A `Tick` that paces the guard between the two posts carrying its own
    `RoundTag` at whatever `PatrolSpeedUuPerSec` currently says, never
    overshooting, always facing the way it moves, and re-finding its posts if
    `RoundTag` changes under its feet.
  - **No perception, no reference to the character, no reference to the panel,
    and it never writes its own speed.**
- `Tasks/t2-alarm-escalates-and-cools-down/YardLampActor.h` / `.cpp` —
  `AYardLampActor`, tagged `YardLamp`. A mast with a point light. Supplied:
  `UPROPERTY(EditAnywhere, BlueprintReadOnly) int32 LitFromStage`,
  `float ReachBonusUu`, `FName CoversRoundTag`; the switch
  `UFUNCTION(BlueprintCallable) void SetLit(bool)` (which sets the light's
  intensity **and** swaps the mast's material — a material *swap*, not a
  parameter write, because not every prototype material here carries a colour
  parameter and a set that silently does nothing leaves the state invisible while
  looking like it worked); and `UFUNCTION(BlueprintPure) bool IsLit() const`.
  Starts dark. **Nothing decides when to throw it.**
- `Tasks/t2-alarm-escalates-and-cools-down/YardAlarmActor.h` / `.cpp` —
  `AYardAlarmActor`, tagged `YardAlarm`. **A board of dials and nothing else**:
  no setting, no count, no tick, no reference to a guard or a floodlight. Its
  `UPROPERTY(EditAnywhere, BlueprintReadOnly)` dials are
  `SightingsToRaiseWatch`, `SightingsToRaiseHunt`, `SightingsToDropWatch`,
  `SightingsToDropCalm`, `MaxSightingsRemembered`, `QuietSecondsPerStepDown`,
  `PatrolScaleWhenCalm`, `PatrolScaleWhenWatching`, `PatrolScaleWhenHunting`. It
  deliberately carries **no readout of its own**: the floodlights and the guards'
  pace *are* the readout, so there is no ungraded switch a submission can call
  instead of doing the work.
- `Tasks/t2-alarm-escalates-and-cools-down/YardPostActor.h` / `.cpp` —
  `AYardPostActor`. Four of them mark the two rounds; each carries the tag its
  round is known by. Non-colliding on every channel.
- `Content/Maps/t2-alarm-escalates-and-cools-down/L_AlarmYard.umap` — the staged
  yard, committed binary. World Settings name NO game mode, so the level inherits
  `BP_ThirdPersonGameMode`. What is in it:

  | Element | Placement | Notes |
  |---|---|---|
  | Floor | 10,200 x 10,200, striped every 400 cm, stripes **non-colliding** | |
  | Two rounds | parallel, 1,400 cm long, 6,000 cm apart, four posts | painted on the floor |
  | Two `AWatchGuardActor`s | one per round, **movable** | they trade rounds part way through |
  | Six `AYardLampActor`s | around the yard, **non-colliding** | not in any tidy order |
  | One `AYardAlarmActor` | by the gate, **non-colliding** | |
  | Sight arcs | each guard's own wedge and its widest-offset line painted on the floor | the level is honest about what it is asking |
  | PlayerStart | at the quiet end of the lane | |
  | Backdrop + landmarks | a low back wall and two differently sized posts, **non-colliding** | a moving camera is distinguishable from a still one |
  | Fixture | one placed `AAlarmEscalationFunctionalTest` | |

  **Everything except the floor and the two guards is non-colliding on every
  channel**, so nothing in the yard blocks a sightline. **The guards' numbers,
  the floodlights' numbers and the panel's dials are deliberately NOT in this
  section.** They are readable in the level, on the things themselves.

- `cameras.json` (the camera-plan lane; not part of this release) — the
  presentation-only camera plan. Non-gating.

Files that **do not exist**:

- No perception of any kind, no sighting counter, no quiet clock, no setting, no
  code that lights a floodlight or writes a guard's pace, no Blueprint subclass,
  no level edits. The empty submission compiles (L1 green) and FAILs L2 on the
  first standing phase, because the yard begins calm and calm is **not** every
  floodlight dark.
- No test source in the agent's writable path. `AAlarmEscalationFunctionalTest`
  lives in the `CraftBenchTests` module the agent can neither read nor modify.

## Verifier specification

The test runs in PIE from
`Content/Maps/t2-alarm-escalates-and-cools-down/L_AlarmYard.umap` on the
**ThirdPerson** substrate, ticked at a fixed deterministic step
(`-deterministic -FPS=<rate>`), **twice**: once at 60 and once at 20
(`fps_legs: [60, 20]`), each in its own PIE process. The whole task hangs on a
five-second quiet clock, so a tick counter fitted to 60 Hz must be made to fire
at the wrong wall time.

Verification primitive: **pie-checkpoint-sampling** plus an every-frame readback
of the floodlights' **light intensity** and the guards' **`PatrolSpeedUuPerSec`**
— what a reviewer sees — over a fixture-driven walk, compared against the
fixture's own running model of the whole rule.

### The fixture runs the same rule

Every frame the fixture re-reads each guard's four numbers, each floodlight's
three numbers and all nine dials **by name, live**, and steps its own model:
the same cone predicate, the same edge-counted sightings with the same clamp, the
same quiet clock, the same two-table state machine, and the same
floodlight-extends-reach rule (against the floodlight set **its own** setting
implies, never against what the submission lit). Every gate compares the yard's
visible state against that model.

### Why the two counters cannot drift apart

This is the load-bearing design decision and the spec states it plainly.

1. **The predicate is disclosed in full** — flat, guard location to character
   location, inclusive at both edges. There is no measurement origin to guess.
2. **The count saturates at both ends**, and every phase of the drive ends at one
   of them (the panel's cap, or zero). Saturation is a re-sync: two counters that
   both clamp arrive at the same integer regardless of what happened before, so a
   divergence cannot outlive the phase it started in.
3. **Every transit is routed out through the quiet spot along one lane**, never
   spot to spot. On the first watch the covering guard is geometrically blind to
   that entire lane, so the only cone boundary the walk crosses is crossed
   head-on at the very end.
4. `PrepareTest` refuses to start unless every dwell spot clears its covering
   guard's cone by a real margin at **every** phase of that guard's round and at
   **every** setting, and unless the cone edge lets go of the target either well
   inside the round (a transverse crossing) or not at all before the guard turns
   (a clean 180-degree flip). Letting go a few uu short of a post is the one
   shape where a frame of sampling order could add or drop a sighting.

### The drive

**Adaptive, not a fixed route.** Every standing phase is *"stay here until MY
model says X"*, never *"stay here for T seconds"* — which is what makes it immune
to the feedback loop (raising the setting speeds the guards up, which changes how
often their cones sweep the character, which changes how fast the count climbs).

**Three places, all derived from the round and the guards' own numbers, never
written down.** The perpendicular offsets are `0.55 x` the narrower guard's cone
limit (the *close-in* spot, plainly inside both guards' reach) and the geometric
mean of "the narrow guard cannot reach here even fully lit" and "the wide guard
reaches comfortably past here" (the *split* spot, which means opposite things to
the two guards). The *quiet* spot is the first point on the same lane that is
`1.35 x` the largest reach in the yard away from **both** rounds. The along-track
positions are chosen by scanning for the one that maximises the worst sighting
window and gap across all three settings.

| Phase | Where | Until |
|---|---|---|
| 0 | walk to the quiet spot | arrival (gates off — the character may spawn anywhere) |
| 1 | stand, quiet | 8 s |
| 2 | walk to the close-in spot, along the lane then in | arrival |
| 3 | stand, close-in | the model's count reaches the cap, held 1.5 s |
| 4–5 | walk out and stand, quiet | the model's count reaches zero, held 8 s |
| 6–7 | walk to the split spot and stand | 32 s |
| 8–9 | walk out and stand, quiet | 6 s |
| 10 | **the watch changes** | 4 s |
| 11 | stand, quiet | 10 s |
| 12–13 | walk to the split spot and stand | 8 raw sightings past the cap, held 4 s |
| 14–15 | walk out and stand, quiet | the model's count reaches zero, held 10 s |
| 16 | stand, quiet | 8 s, then the run-level gate |

**The watch change** (phase 10, at calm, so no dial change can jolt the setting):
the two guards trade `RoundTag` and are teleported onto their new rounds' near
posts; the sergeant raises `SightingsToRaiseWatch` by one and multiplies
`PatrolScaleWhenHunting` by 1.1667. Every gate is suppressed for 2 s around it.

**Phase 3 leaves promptly** (1.5 s past the cap, against a hunting lap of 5.6 s)
on purpose: standing longer would let an *unclamped* counter climb past the cap
in the first watch, and then the first-watch cooldown — which the step-down and
deadband gates own — would name the failure that the cap gate in the second watch
exists to name.

### Settle and suppression

Nothing is judged on a frame where any of these hold. Each is a **widening** of
the disclosed contract, never a narrowing:

- less than **0.75 s** since the fixture's own model last changed (1.5x the half
  second the prompt promises);
- the model is within 0.4 s of its next forget tick (which is exactly
  predictable, so a submission that steps down a frame *early* is covered as well
  as one that lags);
- any guard's verdict is **marginal** — within 3 degrees of its own view width
  while inside 1.06x its reach, or within 6% of its own reach while inside its
  view width plus 3 degrees. (Both halves, not either: a guard whose facing
  sweeps past its own view width while the character is four times its reach away
  is not marginal about anything.)
- the fixture itself is re-staging the yard.

### The sentinel

The checkpoint schedule is 49 calibration checkpoints every 8 s plus a
**SENTINEL at t = 400 s**, far past the ~280 s the drive models, because
`ACraftBenchFunctionalTest::Tick` ends the test the moment the last scheduled
checkpoint is sampled. The run-level gate is evaluated when the last phase
completes **and** again at the sentinel, whichever comes first, and only then
does the fixture call `FinishTest(Succeeded)`.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64
        Development" and "ThirdPerson Win64 Development"
```

### L2 — AFunctionalTest behavioral trace

**Gate precedence, in the order the fixture evaluates them. Exactly one of 2-6 is
armed on any judged frame, so a named FAIL is never a race between two of them.**

```text
1  TheYardIsNotYoursToRewire      -- every frame, from the first
2  EachGuardSeesWithItsOwnEyes    -- phases 7 and 13 (the split spot, both watches)
3  TheAlarmStopsCountingAtTheCap  -- phases 14-15 (the whole second-watch cooldown)
4  TheYardRemembersWhichWayItCame -- count strictly inside a deadband, 2/3 not armed
5  TheAlarmComesDownOneStepAtATime-- phases 4-5 (the first-watch cooldown), outside
                                     the deadbands
6  TheYardShowsTheRightStage      -- everywhere else; exactly one of 2..6 runs
7  TheGuardsSpeedUpWithTheAlarm   -- every judged frame, ALWAYS LAST, and only once
                                     whichever of 2..6 was armed has already agreed
8  TheAlarmRoseAgainOnTheNewWatch -- once, at drive completion or the sentinel
```

`TheYardShowsTheRightStage` is suppressed inside every windowed gate's window: it
asserts the same fact from a different angle and would otherwise shadow every
named message. **The pace gate is not suppressed, because it is a genuinely
separate channel** — suppressing it would leave the raised hunting scale on the
second watch ungraded, since every frame the yard is hunting there falls inside
another gate's window. Running it LAST, and only on a frame where the lamps have
already been agreed, gets both: a wrong setting is always named by the windowed
gate, and a right setting with a wrong pace is always named by the pace gate.

```text
assert: TheYardIsNotYoursToRewire -- every frame: each guard's SightRangeUu,
        SightHalfAngleDeg, BasePatrolSpeedUu and RoundTag, each floodlight's
        LitFromStage / ReachBonusUu / CoversRoundTag, and all nine dials are
        exactly what the yard staged for the leg in progress (floats to 0.1%);
        each post is within 2 uu of where the yard put it; and EACH GUARD IS ON
        ITS OWN ROUND -- its location is within 60 uu of the segment between its
        own two posts. The last clause is load-bearing rather than ceremonial:
        the fixture's model reads the guards' LIVE transforms, so without it a
        submission that parked a guard on the character would make the model
        agree the yard should be hunting and every other window would become
        unreachable -- a do-nothing pass.

assert: EachGuardSeesWithItsOwnEyes -- at the split spot, which is walked in
        BOTH watches with a DIFFERENT guard covering that round: the yard shows
        the model's setting. The split spot is 1.6x beyond the narrow guard's
        widest possible offset even with every floodlight burning, and 0.63x of
        the wide guard's, so the identical spot is definitively invisible on the
        first watch and comfortably visible on the second. The message names the
        covering guard's own two numbers and the offset it cannot (or can)
        hold, AND the other guard's, so the diagnosis is in the verdict.

assert: TheYardRemembersWhichWayItCame -- every frame the model's count is
        strictly inside a deadband (> the drop number and < the raise number
        that bracket it). The yard's setting must equal the model's, which is a
        MEMORY: on the map's dials the model holds hunting on the way down at
        counts 4 and 3 and holds watching at count 1, while it reads only
        watching / only calm at the same counts on the way up. The message
        names the count, both bracketing numbers, and which way the count got
        there.

assert: TheAlarmComesDownOneStepAtATime -- through the FIRST watch's cooldown,
        outside the deadbands: at count 5 the yard must still be hunting, at
        count 2 it must be watching and not calm, at count 0 it must be calm.
        The message names the elapsed quiet seconds, the panel's current
        QuietSecondsPerStepDown, the model's count and the setting it implies.

assert: TheAlarmStopsCountingAtTheCap -- through the SECOND watch's cooldown,
        which the drive deliberately enters over-exposed: it stands in the open
        until the model has counted EIGHT raw sightings on that watch while its
        remembered count saturates at the panel's cap of five. The yard must
        therefore be calm 25 s into the quiet, not 40 s. This gate owns that
        whole window and the two above are disarmed inside it, so the missing
        clamp is named by the gate that exists for it.

assert: TheGuardsSpeedUpWithTheAlarm -- INDEPENDENT CHANNEL, on every judged
        frame and always evaluated LAST: for each guard, PatrolSpeedUuPerSec ==
        that guard's own BasePatrolSpeedUu x the panel's CURRENT scale for the
        model's setting, within 1%. The message names the guard, its own base,
        the panel's current scale, the product, and what was found. This is the
        gate that catches a hunting scale cached at BeginPlay, because the
        sergeant raises it on the second watch.

assert: TheYardShowsTheRightStage -- the set of lit floodlights is exactly
        {floodlights whose own LitFromStage <= the model's setting}. Read from
        each floodlight's point light (visible, not hidden, intensity > 0),
        never from a flag. The message names the model's setting and count, the
        floodlights that should be burning with their own setting numbers, and
        the ones actually burning.

assert: TheAlarmRoseAgainOnTheNewWatch -- run-level: the yard rose from calm at
        least once on each watch AND came all the way back to calm in between.
        An alarm that latches can only rise once; a quiet clock armed once and
        never re-armed never returns to calm, so the second rise never happens.
```

**Staging faults are attributed, not scored.** Any of these ends the run as
`HARNESS-PRECONDITION`, never as a model failure: wrong actor counts; a guard,
floodlight or panel that does not expose its numbers readably; dials that do not
describe a machine which can hold a setting (a raise number at or below its own
drop number), or a band narrower than the fixture can stand inside; the two
guards' widest-offset limits less than 2x apart; the two base paces within 20
uu/s of each other; floodlights whose settings run in order along their names; no
floodlight throwing light down a round (the two halves would not touch); no
along-track position on the lane that gives every required sighting window at
least 2.0 s and every gap at least 2.0 s **at every setting on the watch in
progress** — including after the sergeant makes the hunting scale faster; a route
that comes within 1.25x of the far guard's reach; anything in the yard blocking a
guard's line to the route (probed by tracing from each guard at nine phases of
its round to a dozen points along the route); or a phase that overruns its
derived deadline.

**A harness exit can never launder a FAIL.** Before any deadline or sentinel
overrun is written off as a staging fault, `TheGuardsSpeedUpWithTheAlarm` and
`TheYardIsNotYoursToRewire` are re-checked **unconditionally** — the pace a
submission writes decides how often a cone sweeps the character, and therefore
whether phases ever complete, so a mis-paced yard must be a FAIL and not an
uncredited harness exit.

## Requirement-to-assertion map

| Prompt requirement | Gate that checks it | When that gate does NOT run |
| --- | --- | --- |
| a guard notices inside **its own** reach and **its own** view width | `EachGuardSeesWithItsOwnEyes` at the split spot, both watches | outside phases 7 and 13; the same fact is checked indirectly everywhere else through the count the model derives from it |
| the two guards are not set alike | not a gate but a **precondition**: the fixture refuses to start if their widest-offset limits are within 2x, or their base paces within 20 uu/s | never |
| measured flat, guard to character, inclusive at both edges | the fixture's model uses exactly that predicate; any other one produces a different count and diverges | never |
| one sighting is an **edge**, not a length of time | the model counts edges; a continuous meter climbs on a different schedule and shows the wrong setting | frames the settle rule suppresses |
| the count never exceeds the panel's cap | `TheAlarmStopsCountingAtTheCap` | outside phases 14-15 |
| every quiet window forgets one sighting, **then another** | `TheAlarmComesDownOneStepAtATime` | outside phases 4-5, and inside the deadbands (which gate 4 owns) |
| being seen puts the quiet clock back to zero | the model does it; a submission that does not diverges during every climb | frames the settle rule suppresses |
| raise numbers and drop numbers are different; the band between them remembers | `TheYardRemembersWhichWayItCame` | when the count is outside both deadbands |
| one setting at a time, in both directions | `TheAlarmComesDownOneStepAtATime` (down) and `TheYardShowsTheRightStage` (up) | as above |
| a floodlight is lit exactly while the panel is at its own setting or higher | `TheYardShowsTheRightStage`, every frame, per floodlight, read from the light | inside a windowed gate's window, where that gate asserts the same fact |
| each guard walks at **its own** base pace x the panel's scale | `TheGuardsSpeedUpWithTheAlarm`, within 1%, on every judged frame | only on a frame where a windowed gate already failed |
| a burning floodlight lengthens the covered round's guard's reach | not a separate gate: it enters the model's own reach, so a submission that ignores it counts different sightings and fails whichever gate is armed. The fixture refuses to start if no floodlight carries a bonus | never |
| settles within **half a second** | the 0.75 s suppression window, which is 1.5x it | never |
| it can do the whole thing again | `TheAlarmRoseAgainOnTheNewWatch` | judged at drive completion or the sentinel; a run that fails a per-frame gate earlier never reaches it, which is the more useful message |
| the dials change and must be read at the point of use | `TheGuardsSpeedUpWithTheAlarm` (hunting scale x1.1667 on the second watch) and the count trajectory (raise-watch +1) | as above |
| do not move the guards or change any number on them | `TheYardIsNotYoursToRewire`, every frame, including "on its own round" | never |
| C++ under `Source/ThirdPerson/` | sandbox: a file outside the writable set is exit 4, not a graded FAIL | never |

## Reference solution metadata

- **Files touched**: 2 — `Source/ThirdPerson/Tasks/t2-alarm-escalates-and-cools-down/YardAlarmActor.h`
  and `.cpp`. The other three supplied pairs are byte-identical to the scaffold.
- **LOC**: ~175 added (about 60 of them comment), on top of the supplied board.
- **Senior-dev hours**: **3–4**, which is the **lower half of T2**. The code is
  not large; the hours go into judgment, not typing:
  1. ~45 min working out that the setting has to be **remembered state** rather
     than a function of the count, and that the raise set and the drop set are
     two different tables. The prompt says so, so this is reading comprehension
     plus care — not a discovery — but the natural first implementation is one
     threshold ladder, and it compiles and looks right.
  2. ~45 min on the counter's exact semantics: sightings are edges not seconds,
     the clamp, and a quiet clock that resets on being seen at all and then steps
     **repeatedly** rather than once.
  3. ~45 min wiring two responses off one setting and getting them **per
     instance** (each floodlight's own setting number, each guard's own base
     pace) instead of by index or by one flat value.
  4. ~45 min on the reading discipline plus the feedback loop: the dials and the
     guards' numbers must be read at the point of use, and the floodlights feed
     back into the reach, which forces an explicit decision about the order of
     the five steps inside one tick.
- **Why not T3**: no new subsystems, no assets, no editor work, no engine
  spelunking. It is one tick's worth of gameplay code that has to be exactly
  right in four interacting places.

## Anti-gaming notes

1. **One threshold ladder for both directions** (`stage = count >= 5 ? hunting :
   count >= 2 ? watching : calm`). *Failure mode*: the single most natural first
   implementation, and the owner's named wrong answer. *Defense*: it is a pure
   function of the count, so it cannot report two different settings at count 4.
   `TheYardRemembersWhichWayItCame` stands the drive inside both deadbands from
   both directions, and the fixture asserts at the end that both were entered.
2. **Cooling down by clearing the alarm after one quiet window, or by
   decrementing the SETTING on the quiet timer.** *Failure mode*: the two most
   natural readings of "cools back down, one stage at a time". *Defense*: at 5 s
   into the first watch's cooldown the model is still hunting with a count of 4 —
   `TheYardRemembersWhichWayItCame` catches both there, and
   `TheAlarmComesDownOneStepAtATime` catches the "drops all at once at the drop
   number" and "never drops" variants at counts 2 and 0 in the same phase.
3. **A sighting counter with no clamp.** *Failure mode*: an ordinary missing
   clamp. *Defense*: `TheAlarmStopsCountingAtTheCap` owns the whole second-watch
   cooldown, which the drive deliberately enters over-exposed (eight raw
   sightings against a cap of five). The unclamped answer needs 40 s of quiet
   where the model needs 25 and is still hunting when the model is watching. The
   first watch is deliberately **not** over-exposed, so this variant behaves
   identically to a correct one there and cannot die at the wrong gate.
4. **Sight as range only, one hard-coded cone, or one guard's numbers used for
   both.** *Failure mode*: all three are ordinary first passes. *Defense*: the
   split spot is walked in both watches with different eyes on it. Range-only or
   too-wide escalates a yard the model says is calm on the first watch;
   too-narrow leaves the yard calm while the model climbs to hunting on the
   second. No single cone survives both, and
   `EachGuardSeesWithItsOwnEyes` names the covering guard's own numbers.
5. **Reading the dials or the guards' numbers once at `BeginPlay` and caching
   them.** *Failure mode*: the obvious optimisation. *Defense*: the sergeant
   raises `SightingsToRaiseWatch` and the hunting scale mid-run, and the guards
   trade rounds. A cached hunting scale fails `TheGuardsSpeedUpWithTheAlarm` the
   moment the second watch reaches hunting; a cached raise number climbs a
   setting early and fails whichever gate is armed.
6. **Lighting the first N floodlights, or N floodlights, for setting N.**
   *Failure mode*: pattern-matching on the word "three settings". *Defense*: the
   yard's `LitFromStage` values are 1, 2, 0, 2, 1, 1 in name order, so the
   correct lit counts are 1 / 4 / 6 and neither index order nor a count matches.
   The fixture refuses to start on a yard whose settings run in order, or whose
   per-setting counts are 1 / 2 / 3.
7. **Setting a correct internal enum and never touching a floodlight or a
   pace.** *Failure mode*: modelling the state and forgetting the output.
   *Defense*: nothing private is ever graded — the fixture reads the point
   lights' intensity and the guards' `PatrolSpeedUuPerSec`. The panel deliberately
   carries no readout of its own.
8. **Writing `BasePatrolSpeedUu` instead of `PatrolSpeedUuPerSec`.** *Failure
   mode*: two similarly named floats on the same actor; an ordinary slip.
   *Defense*: `TheYardIsNotYoursToRewire` compares every staged number every
   frame and its message names the property that IS yours to write.
9. **Moving a guard, or parking one on the character.** *Failure mode*: forcing a
   permanent sighting, or removing an inconvenient one. *Defense*: this is
   anti-gaming rather than a plausible first pass, and it is why
   `TheYardIsNotYoursToRewire` checks that each guard is within 60 uu of the
   segment between its own two posts. Relying on the sight gate instead would not
   work: the model reads the guards' LIVE transforms and would agree with the
   parked guard.

## Hidden invariants

- **The count is never compared directly; only its consequences are.** The
  fixture's model integer is never read out of the submission (it could not be),
  so every gate is a statement about lights and paces. A submission is free to
  represent the count however it likes.
- **The model's reach uses the floodlight set the model's OWN setting implies**,
  never what the submission lit. A submission whose floodlights are wrong
  computes a different reach, counts different sightings and diverges — which is
  the interaction working, not an accident.
- **The quiet clock keeps its remainder.** The model subtracts one step from the
  clock per forget rather than zeroing it. Nothing observable depends on the
  difference (the clock is zeroed by any sighting), and the 0.75 s suppression
  covers the sub-frame offset either way.
- **`fps_legs: [60, 20]` runs the whole drive twice**, in two PIE processes, each
  with its own wall-clock budget. A tick counter fitted to 60 Hz fires the forget
  step at the wrong wall time at 20 Hz and diverges within one cooldown.
- **The `L_AlarmYard` geometry is solved, not written down**, in both the fixture
  and the authoring script, from the same closed form (the widest offset at which
  a guard walking a straight round can ever hold a stationary target is
  `reach x sin(view width)`). Both refuse their job if the solve does not come
  out, so a re-authored yard with different guards either moves the drive with it
  or fails loudly.

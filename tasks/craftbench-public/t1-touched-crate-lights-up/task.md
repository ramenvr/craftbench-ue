---
id: t1-touched-crate-lights-up
substrate: ThirdPerson
set: craftbench-public
tier: T1
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_CrateBay :: ACrateHighlightFunctionalTest"]
---

# t1-touched-crate-lights-up

Walk up to a crate and it lights up; walk away and it goes out; walk back and it
lights again. Two crates, looking the same and built from the same class — and
**they do not notice from the same distance**. One hard-coded reach is wrong
about one of them wherever the character stands between the two.

Imported from the Startup Eval corpus row `t1-custom-depth-stencil-outline`
(provenance and every deviation: `notes.md`). Renamed because
`custom-depth-stencil` puts the mechanism in the agent-visible path, and the
mechanism is not the point.

> **Built against the 2026-08-18 difficulty bar.** The corpus row is one
> proximity check with a highlight on the end of it. What makes this version
> measure something is that the reach is **per-crate, readable, and different**,
> that the crates **swap places** between the two legs, and that the highlight
> has to **re-arm** — each crate lights on at least two separate approaches.

## Primary concept

- `per-instance-highlight` — an actor reacting to proximity with its own settings
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/using-a-custom-depth-pass-in-unreal-engine)

The load-bearing behaviour is **an actor answering for itself from its own
configuration**, in both directions, repeatedly. The grade never asks *how*: an
overlap volume sized from the property, a distance check in `Tick`, or a timer
poll all pass identically.

## Prompt given to the agent

> The bay has two crates. They are the same kind of thing and they look the same,
> and each one carries one number: how close somebody has to be before **that**
> crate notices them. **The two numbers are not the same**, and each crate's is
> painted on the floor around it so you can see the difference.
>
> Make a crate light up while the character the player controls is within its own
> reach, and go out again when they are not. It must settle to the right state
> within **half a second** of a change, and it must light up **again** every time
> the character comes back — not once.
>
> The bay rearranges itself part way through: the two crates **swap places**. A
> crate that lights up because of where it is standing rather than because of how
> far away somebody is will light the wrong one after that.
>
> Where the crates stand is not yours to change. The crate's body, its lamp and
> the switch that lights or clears it are all supplied and working. Nothing
> decides when to throw that switch. Do not edit the level, any config file, or
> any test file. Write your solution in C++ under `Source/ThirdPerson/`.

## Workspace state pre-task

**Deliverable root: `Source/ThirdPerson/`** (the agent-writable runtime module on
this substrate). `Source/CraftBenchTests/` is deny-listed and a submission file
under it is a SANDBOX-REJECT (exit 4), not a graded FAIL; so are
`Content/Maps/`, `Content/ThirdPerson/`, `Content/Characters/` and every
`Config/` file (no `config_allow` is declared by this task).

Files that **exist** under `Source/ThirdPerson/`:

- The stock UE 5.8 Third Person C++ template sources. No edit needed.
- `Tasks/t1-touched-crate-lights-up/HighlightCrateActor.h` / `.cpp` —
  `class THIRDPERSON_API AHighlightCrateActor : public AActor`, tagged
  `HighlightCrate`. Supplied:
  - `Body` — a 160 cm cube, **the root**, `BlockAll`, movable. The actor stands
    with the mesh's centre at its location, so the bay places it at half its
    height and it sits on the floor.
  - `Lamp` — a `UPointLightComponent` just above the crate, off at intensity 0.
  - `UPROPERTY(EditAnywhere, BlueprintReadOnly) float NoticeRadiusUu` — **read it
    off the crate; the two crates in the bay are not set to the same value.**
  - `UFUNCTION(BlueprintCallable) void SetHighlighted(bool)` — the supplied
    switch: sets the lamp's intensity and swaps the body's material between a
    plain and a lit look. (A material **swap**, not a parameter write: not every
    prototype material in this substrate carries a colour parameter, and a set
    that silently does nothing leaves the state invisible while looking like it
    worked.)
  - `UFUNCTION(BlueprintPure) bool IsHighlighted() const`.
  - **No tick, no timer, no overlap handler, no reference to the character, no
    call to `SetHighlighted` outside `BeginPlay`.** The whole decision is the
    agent's, **and it has to land on this class**: both crates are placed
    instances in a map you cannot edit, so a subclass would never be
    instantiated.
- `Content/Maps/t1-touched-crate-lights-up/L_CrateBay.umap` — the staged bay,
  committed binary. World Settings name NO game mode, so the level inherits
  `BP_ThirdPersonGameMode`. What is in it:

  | Element | Placement | Notes |
  |---|---|---|
  | Floor | 8,200 x 3,200, striped every 400 cm, stripes **non-colliding** | |
  | Two `AHighlightCrateActor`s | 1,600 cm apart, both **movable** | the fixture swaps them, and PIE scores moving a static actor as a failed test |
  | Reach rings | one painted ring per crate, at that crate's own radius, **non-colliding** | the two circles are visibly different sizes — the level is honest about what it is asking |
  | PlayerStart | at the near end | |
  | Backdrop + landmarks | a low back wall and two differently sized posts | a moving camera is distinguishable from a still one |
  | Fixture | one placed `ACrateHighlightFunctionalTest` | |

  **The crates' coordinates and their two radii are deliberately NOT in this
  section.** They are readable in the level, on the crates.

- `cameras.json` (the camera-plan lane; not part of this release) — the presentation-only
  camera plan. Non-gating.

Files that **do not exist**:

- No proximity logic of any kind, no Blueprint subclass, no level edits. The
  empty submission compiles (L1 green) and FAILs L2 the first time the character
  stands inside a crate's reach.
- No test source in the agent's writable path. `ACrateHighlightFunctionalTest`
  lives in the `CraftBenchTests` module the agent can neither read nor modify.

## Verifier specification

The test runs in PIE from
`Content/Maps/t1-touched-crate-lights-up/L_CrateBay.umap` on the **ThirdPerson**
substrate, ticked at a fixed deterministic step (`-deterministic -FPS=60`).
Verification primitive: **pie-checkpoint-sampling** with an every-frame readback
of each crate's **lamp intensity** — what a reviewer sees — over a fixture-driven
walk.

**The route is computed from the crates, not written down.** Each stop is a
multiple of the radius of the crate it is about — 0.7x in, 1.5x out, 5x away —
offset into a lane to one side so the walk never passes through a crate, which
is solid. `PrepareTest` refuses to start if any stop is within 20% of a crate's
radius (where a correct answer could round either way), if any stop is closer
than 130 uu to a crate's centre, or if any leg of the walk passes that close.

**The bay is walked TWICE and the crates swap places between the legs.** Because
the route is recomputed from their live positions, the same schedule lights a
different crate the second time round.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64
        Development" and "ThirdPerson Win64 Development"
```

### L2 — AFunctionalTest behavioral trace

```text
assert: EachCrateLightsForItsOwnReach -- every frame, half a second after the
        truth about that crate last changed: lit if and only if the character
        is within THAT crate's NoticeRadiusUu. The failure message names the
        crate, both radii, and the distance
assert: ACrateLightsUpAgainWhenYouComeBack -- each crate lit on at least two
        separate occasions across the two legs
assert: TheCratesWereNotMoved -- each crate is still where the bay put it for
        the leg in progress, to 2 uu
assert: TheYardRanBothLegs -- the second leg happened, so the crates really did
        swap places
```

The checkpoint schedule carries a **sentinel at t = 220 s**, far past the two
legs, because `ACraftBenchFunctionalTest::Tick` ends the test the moment the
last scheduled checkpoint is sampled.

**Staging faults are attributed, not scored.** A bay without exactly two tagged
crates, a crate that does not expose `NoticeRadiusUu` readably, a crate with no
lamp, **two crates whose radii are less than 100 uu apart** (one hard-coded reach
would be right about both and the task would measure nothing), or a route that
would jam the character all end the run as `HARNESS-PRECONDITION`, never as a
model failure.

## Anti-gaming notes

1. **One hard-coded reach.** *Failure mode*: pick a radius — 300, or whatever the
   first crate reads — and use it for both. *Defense*: the two crates notice from
   260 uu and 520 uu, and the route stops at 0.7x and 1.5x of **each** crate's
   own radius. A single number is wrong at two of the six stops per leg, and the
   failure message says *"the other crate notices from 520 uu — one reach does
   not fit both"*. The fixture refuses to start at all if the two radii are
   within 100 uu of each other, so the gate can never be vacuous.
2. **Lighting once and staying lit.** *Failure mode*: highlight on the first
   approach and never clear — the shape an overlap-begin handler with no
   overlap-end takes. *Defense*: the same per-frame gate fails the moment the
   character walks out of reach and the crate is still lit, and
   `ACrateLightsUpAgainWhenYouComeBack` separately requires at least two distinct
   spells per crate. The route walks up to the near crate, away, and back again
   on every leg.
3. **Keying on which crate it is.** *Failure mode*: light the left-hand crate, or
   the one at a remembered position, or crate index 0. *Defense*: the crates
   **swap places** between the legs and the route is recomputed from their live
   positions, so a position-keyed answer lights the wrong one for the whole of
   leg 2 and fails with the distance in the message.
4. **Moving the crates instead.** *Failure mode*: shove a crate to where the
   character is, or park both on top of the player. *Defense*:
   `TheCratesWereNotMoved` compares each crate against the transform the bay
   staged for the leg, to 2 uu, every frame.
5. **Setting the flag without lighting anything.** *Failure mode*: set
   `bHighlighted` directly and never touch the lamp. *Defense*: the fixture reads
   the **lamp's intensity**, and treats a hidden lamp as dark. A flag saying the
   crate noticed you is not the crate lighting up.

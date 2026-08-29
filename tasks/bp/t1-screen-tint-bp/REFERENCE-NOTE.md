# Reference recipe — `t1-screen-tint-bp`

There is no script lane for Blueprint **graph** authoring in this repo (no
`BlueprintEditorLibrary` / `K2Node` precedent anywhere in `tools/` or `tasks/`),
so this asset is built in an attended editor session. This file is precise to the
node and the pin so it can be rebuilt without re-deriving the design.

Everything here is checked against the read-only C++ that ships with the task:
`UE-projects/ThirdPerson/Source/ThirdPerson/Tasks/t1-screen-tint-cpp/ScreenTintActor.h`.

## What the Blueprint author can actually reach

| member | specifier | so a Blueprint can |
|---|---|---|
| `RestVignette` | `EditDefaultsOnly, BlueprintReadWrite` | read it |
| `FullVignette` | `EditDefaultsOnly, BlueprintReadWrite` | read it |
| `SuppliedFringe` | `EditDefaultsOnly, BlueprintReadWrite` | read it — and must NOT write it |
| `CurrentVignette()` | `UFUNCTION(BlueprintPure)` | read back what the effect is now |
| `SetVignette(float)` | `UFUNCTION(BlueprintCallable)` | set the effect |
| `AActor` | `Blueprintable` (Actor.h:281) | subclass it |
| `bCanEverTick` | supplied `true` (2026-08-20) | have Event Tick fire at all |

`SetVignette` is the ONLY write path. Do not reach for
`PostProcessComponent -> Settings` and set the struct: that is how
`TheOtherSettingIsUntouched` fails, because the struct carries the supplied fringe
too and a whole-struct write clobbers it. This is the single most likely slip on
this surface and it is worth stating twice.

## The asset

One Blueprint. Nothing else.

- **Path**: `/Game/Tasks/t1-screen-tint-bp/BP_TintScreen`
- **Parent class**: `ScreenTintActor`
- **Class defaults**: leave every inherited value alone. In particular do not
  touch `RestVignette`, `FullVignette` or `SuppliedFringe` — the level's placed
  instance carries the numbers this run is graded against, and the fixture spawns
  this Blueprint AT that instance's transform, so the defaults must not fight it.

The folder name matters: `SpawnGradedBlueprintIfPresent` filters the asset
registry to `/Game/Tasks` recursively and takes the single Blueprint deriving from
the placed class. A second such Blueprint anywhere under `/Game/Tasks` is
`HARNESS-PRECONDITION`, not a verdict, so ship exactly one.

## The graph — `Event Tick`

Nine nodes. Read the ratio, clamp it, lerp, set.

```
[Event Tick]
   |
   v
[Get Player Character]  (Player Index 0)
   |  Return Value ------------------> [Is Valid]  ---(Is Not Valid)--> (nothing)
   |                                        |
   |                                   (Is Valid)
   v                                        v
[GetVelocity]  <-- target = the character   |
   |  Return Value (Vector)                 |
   v                                        |
[VectorLength]                              |
   |  Return Value (float) = SPEED          |
   |                                        |
[Get Character Movement] <-- target = the character
   |  Return Value (CharacterMovementComponent)
   v
[Get Max Walk Speed]   (variable get off that component)
   |  float = TOP
   v
[float / float]   A = SPEED, B = TOP
   |
   v
[Clamp (float)]   Value = the quotient, Min = 0.0, Max = 1.0
   |  = RATIO
   v
[Lerp (float)]    A = RestVignette (variable get, self)
                  B = FullVignette (variable get, self)
                  Alpha = RATIO
   |
   v
[SetVignette]     target = self, NewVignette = the lerp result
```

Pin-level notes, each of which is a way to get it subtly wrong:

1. **`VectorLength`, not `VectorLength2D`.** The C++ leg grades
   `GetVelocity().Size()`. On flat ground they agree; on the ramp they do not, and
   the fixture's own cross-check against ground covered is what would catch the
   difference. Match the graded quantity.
2. **`Get Max Walk Speed` every tick, never cached.** The fixture re-writes
   `MaxWalkSpeed` to 0.52x between the two legs. A `Get` promoted to a variable in
   `BeginPlay` is right for leg 1 and wrong for leg 2 — that is the whole
   anti-hard-coding design, and it is the mistake this graph is shaped to avoid.
3. **Guard the divide.** `TOP` is never 0 on this map, but a divide-by-zero in
   Blueprint yields `+inf` and `Clamp` returns `Max`, i.e. a full-bright screen
   while standing still — a silent wrong answer rather than an error. Either
   branch on `TOP > 0` or use `SafeDivide`. The C++ reference guards it; so does
   this.
4. **`Clamp` before `Lerp`, not after.** Blueprint's `Lerp` does not clamp its
   alpha, so an unclamped ratio above 1 (possible for a frame on the ramp, since
   velocity can briefly exceed `MaxWalkSpeed`) drives the effect past
   `FullVignette` and out of the 0.12 window.
5. **Read `RestVignette` / `FullVignette` off `self`, not typed in.** They are
   `EditDefaultsOnly` on the placed instance and the prompt never states their
   values. Typing 0.0 and 0.9 would pass today and break the moment the map is
   re-staged — and it is exactly the "wrote down a number instead of reading it"
   failure the anti-gaming notes name.
6. **Do not call `SetVignette` outside Tick.** `BeginPlay` painting is harmless
   but pointless; a Timer is worse, because it decouples the update from the frame
   the fixture samples on and can drift outside the 0.4 s settle window.

## Saving it out

Author it in the substrate project so the class is resolvable, then copy the
`.uasset` into the task folder — the reference tree mirrors the deliverable root:

```
tasks/bp/t1-screen-tint-bp/reference/
  Content/Tasks/t1-screen-tint-bp/BP_TintScreen.uasset
```

## After it exists

1. `cb discriminate --task t1-screen-tint-bp` — reference must
   PASS, empty must FAIL. Empty here means no Blueprint at all, in which case the
   fixture finds nothing to spawn, grades the placed C++ scaffold (which does
   nothing), and fails `TintTracksHowFastYouAreMoving` at the first settled
   window.
2. Re-discriminate `t1-screen-tint-cpp` as well. The two legs share
   one fixture; a change that fixes this leg and breaks that one is a net loss and
   the only way to see it is to grade both.
3. The owner has to PLAY it (2026-08-18 directive). Same map as the C++ leg, so
   the play project already carries it.

**Nothing in this file has been run.** It is derived from the C++ reference and
the engine headers, and every number in it is disclosed in the prompt or read off
the world. The first graded run is what makes any of it true.

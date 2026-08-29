# Reference recipe — `t1-mud-wade-bp`

There is no script lane for Blueprint **graph** authoring in this repo (no
`BlueprintEditorLibrary` / `K2Node` precedent anywhere under `tools/` or `tasks/`),
so this asset is built by hand in an attended editor session. This file is precise
to the node and the pin so it can be rebuilt without re-deriving the design.

Everything here is checked against the read-only sources that ship with the pair:

- `UE-projects/ThirdPerson/Source/ThirdPerson/Tasks/t1-mud-wade-cpp/MudHeroCharacter.h`
  and `.cpp` (the class this Blueprint derives from);
- `UE-projects/ThirdPerson/Source/ThirdPerson/Tasks/t1-mud-wade-cpp/MudPatchActor.cpp`
  (the patch's actual collision geometry);
- `UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/t1-mud-wade-cpp/MudWadeFunctionalTest.cpp`
  (the grader — the authority on every band and on how the pose read works);
- `UE-projects/ThirdPerson/Source/CraftBenchTests/CraftBenchFunctionalTest.cpp`
  (`SwapAllForGradedBlueprintRepossessing`, the surface lane);
- the UE 5.8 engine headers cited inline.

**MEASURED 2026-08-23.** The reference asset now exists and both legs of the pair
discriminate (reference PASS / empty FAIL, `substrate=HEAD`). What was built
differs from the recipe below in three ways — see *WHAT WAS ACTUALLY BUILT* near
the end before following any node list here literally. Read `task.md`'s *NOT YET MEASURED* section before trusting
any of it — **three** open blockers are recorded there, and the first of them is a
gate on benching this leg at all: per-task staging deletes
`Content/Tasks/t1-mud-wade/` (the supplied clip) and
`Source/ThirdPerson/Tasks/t1-mud-wade-cpp/` (the parent
class) from every agent-visible tree, so a live drive cannot see either while the
grading path still can. Building THIS asset is unaffected — an attended editor
session works in the live project, which is not staged — but a measured run
scheduled before that lands measures the harness, not the model.

---

## READ THIS FIRST: the one route the grader can see

The prompt says "the motion driving its body is a visibly different one … genuinely
driving the pose". The grader answers that question in
`AMudWadeFunctionalTest::WadeDrivesPose` by asking the MESH, and it can only see
two things:

```cpp
Mesh->GetSingleNodeInstance()->GetAnimationAsset()->GetName().Contains("A_MudWade")
Mesh->GetAnimInstance()->GetCurrentActiveMontage()->GetName().Contains("A_MudWade")
```

So the routes that register are **(a) playing the clip on the mesh directly**,
which puts the mesh into single-node mode, or **(b) an active montage whose asset
name carries `A_MudWade`**. A state added to an Animation Blueprint's state
machine, a blend driven by a bool, a linked animation layer or a cached-pose swap
does **NOT** register, however visibly it changes the pose on screen. That is a
property of the shared fixture, identical on both legs of the pair, and it is the
single most likely way a correct intent scores as a failure here.

This recipe therefore uses route (a): `Play Animation` on the inherited `Mesh`.
Route (b) is legal but needs a montage asset whose name contains `A_MudWade`, which
is extra work for no gain.

## What the Blueprint author can actually reach

Checked specifier by specifier. `BlueprintReadWrite` / `BlueprintReadOnly` /
`BlueprintCallable` / `BlueprintPure` are reachable; a bare `virtual` or a bare
`UPROPERTY()` is not.

| member | where | specifier | so a Blueprint can |
|---|---|---|---|
| `WadeMotion` | `MudHeroCharacter.h` | `EditAnywhere, BlueprintReadWrite` | read it, write it, and set its DEFAULT in Class Defaults — **its shipped value is null, see trap 2** |
| `NormalTopSpeed` | `MudHeroCharacter.h` | `EditAnywhere, BlueprintReadWrite` | read it (500) |
| `Mesh` | `Character.h:351` | `VisibleAnywhere, BlueprintReadOnly` | get the skeletal mesh component |
| `CharacterMovement` | `Character.h:355` | `VisibleAnywhere, BlueprintReadOnly` | get the movement component |
| `MaxWalkSpeed` | `CharacterMovementComponent.h:274` | `EditAnywhere, BlueprintReadWrite` | read AND write the walking speed |
| `AnimClass` | `SkeletalMeshComponent.h:394` | `EditAnywhere, BlueprintReadOnly` | READ the animation blueprint class as a **property getter** (`Get Anim Class`) |
| `SetAnimInstanceClass` | `SkeletalMeshComponent.h:1095` | `UFUNCTION(BlueprintCallable)` | put an animation blueprint class back |
| `PlayAnimation` | `SkeletalMeshComponent.h:1258` | `UFUNCTION(BlueprintCallable)` | play a clip on the mesh (single-node mode) |
| `GetAnimInstance` | `SkeletalMeshComponent.h:1111` | `UFUNCTION(BlueprintCallable)` | reach the anim instance (not needed here) |
| `GetActorBounds` | `Actor.h:1610` | `UFUNCTION(BlueprintCallable)` | read the patch's world bounds |
| `GetAllActorsWithTag` | `GameplayStatics.h:115` | `UFUNCTION(BlueprintCallable)` | find the patch by TAG |
| `PrimaryActorTick.bCanEverTick` | `Pawn.cpp:50` | supplied `true` by `APawn` | have `Event Tick` fire at all |
| `PatchVolume` | `MudPatchActor.h` | `VisibleAnywhere, BlueprintReadOnly` | reachable, but reaching it needs a cast to the patch class — do not; use the tag + bounds |
| `GetSingleNodeInstance` | `SkeletalMeshComponent.h:1539` | **not a UFUNCTION** | **NOT reachable** — only the grader calls it |

**Nothing this behaviour needs is unreachable from Blueprint.** Both halves of the
answer (write the walking speed, change what drives the pose) and both halves of
the observation (find the tagged patch, read its bounds) are exposed, and `Event
Tick` is supplied twice over: `APawn`'s constructor sets `bCanEverTick = true`
(`Pawn.cpp:50`), and independently the Blueprint compiler force-enables it for any
Blueprint with a *connected* Event Tick
(`FKismetCompilerContext::SetCanEverTick`, `KismetCompiler.cpp:5504`, gated on
`bCanBlueprintsTickByDefault`, which `BaseEngine.ini:319` sets true). This leg is
not unwinnable the way the tint pair's was before its scaffold was given a tick.

The one real limitation is the grader's pose read, above — a GRADER limitation, not
a reachability one, and it is why this recipe leads with it.

## The asset

**One Blueprint. Nothing else.** No new animation asset, no montage, no animation
blueprint, no second Blueprint of any kind anywhere under `/Game/Tasks`.

- **Path**: `/Game/Tasks/t1-mud-wade-bp/BP_MudWader`
- **Parent class**: `MudHeroCharacter` (Blueprint Class → search "MudHeroCharacter")
- **Must NOT be abstract**, and must stay a subclass of `MudHeroCharacter` — see
  traps 15 and 16.

### Class Defaults — change exactly one thing

| property | set to | why |
|---|---|---|
| `Mud > Wade Motion` | `/Game/Tasks/t1-mud-wade/A_MudWade` | the inherited value is **null** (trap 2) |

Leave everything else alone: `Normal Top Speed` (500), the Mesh component's
Skeletal Mesh Asset and Anim Class, the four inherited input actions, the tags, and
the whole Character Movement block. Both figures in the level are instances of this
one class, so every default you touch reaches the control as well, and the control
gate is what catches it (trap 17).

### Blueprint variables

| name | type | default | purpose |
|---|---|---|---|
| `OrdinaryWalkClass` | `Anim Instance` — **Class Reference** | none | the animation blueprint the figure walks with, recorded at BeginPlay |
| `OrdinaryTopSpeed` | `Float` | `0.0` | the walking speed the figure arrives with, recorded at BeginPlay |
| `IsWading` | `Boolean` | `false` | the edge-trigger latch |

None of these need to be instance-editable or exposed.

## The graph — `Event BeginPlay`

Five nodes. Record what "ordinary" is, so leaving the mud puts back exactly that
rather than a guess.

```
[Event BeginPlay]
   | exec
   v
[SET OrdinaryWalkClass]
   value <-- [Get Anim Class] <-- target = [Mesh]        (component variable get, self)
   | exec
   v
[SET OrdinaryTopSpeed]
   value <-- [Get Max Walk Speed] <-- target = [Character Movement]
   | exec
   v
   (end)
```

- `Get Anim Class` is the **property getter** on the Mesh pin (blue variable node),
  not a function call. `USkeletalMeshComponent::GetAnimClass()` exists but is
  `UFUNCTION(BlueprintInternalUseOnly)` (`SkeletalMeshComponent.h:1088`), so it is
  hidden from the palette; the `AnimClass` property is `BlueprintReadOnly`
  (`:394`), which is what gives you the getter. Drag off the `Mesh` pin and type
  "Anim Class".
- BeginPlay **does** fire on this Blueprint: the fixture's surface swap SPAWNS it
  into a world that has already begun play, so `SpawnActor` runs BeginPlay
  immediately. Recording here is therefore safe, and it is the only place that is
  (trap 6).

## The graph — `Event Tick`

Six nodes plus one function call. Edge-triggered: it acts on the frame the
membership CHANGES, never every frame.

```
[Event Tick]
   | exec
   v
[Is On Mud]                       (function call on self; see below)
   | exec                On Mud (bool) ----+
   v                                       |
[Branch]  Condition <---------------------+
   |
   +-- True  --> [Branch]  Condition = [Get IsWading]
   |                |
   |                +-- True  --> (nothing: already wading)
   |                +-- False --> [Enter Mud]        (function call on self)
   |
   +-- False --> [Branch]  Condition = [Get IsWading]
                    |
                    +-- True  --> [Leave Mud]        (function call on self)
                    +-- False --> (nothing: already walking)
```

`Delta Seconds` is unused. Do not add a timer, an interval, or a
`Set Actor Tick Interval` — the grader samples per frame and both transition
windows are half a second (trap 3's cousin: anything that decouples the update from
the frame can drift outside them).

## The function — `Is On Mud` → `Boolean`

Not pure: `Get All Actors With Tag` is `BlueprintCallable`, so this function has
exec pins. Local variable `Found` (Boolean, default false).

```
[Is On Mud  (entry)]
   | exec
   v
[Get All Actors With Tag]
   Actor Tag  = MudPatch          (literal Name)
   Out Actors ------------------> [For Each Loop] (array pin)
   | exec ---------------------->  same node
                                   |
                                   Loop Body
                                   |
                                   v
                        [Get Actor Bounds]
                          Target                     = Array Element
                          Only Colliding Components  = TRUE
                          Include From Child Actors  = false
                          Origin --------> A of [Vector - Vector]
                          Box Extent ----> (used below)
                                   |
                                   v
                        [Vector - Vector]  A = [Get Actor Location] (self)
                                           B = Origin
                          Return Value --> [Break Vector] -> X, Y
                                   |
                                   v
                        [Abs (float)] X   -->  A of [<= (float)] ;  B = BoxExtent.X
                        [Abs (float)] Y   -->  A of [<= (float)] ;  B = BoxExtent.Y
                                   |
                                   v
                        [AND (boolean)]  --> [Branch]
                                                 True  -> [SET Found = true] -> [Break] (the loop's Break pin)
                                                 False -> (next iteration)
   Completed
   |
   v
[Return Node]  Return Value = [Get Found]
```

- **`Only Colliding Components` must be TRUE.** The patch actor's visual slab is
  `NoCollision`; its `PatchVolume` box is `QueryOnly` with `SetBoxExtent(200,200,120)`
  and a relative scale that cancels the mesh's, so the colliding bounds are the
  400 cm x 400 cm of mud the grader measures. `false` folds in every
  non-colliding component instead — on today's staging the X/Y agree, so this is
  robustness rather than a live bug, but the grader iterates `UBoxComponent`s and
  matching it exactly is free.
- **Test X and Y only.** `AMudWadeFunctionalTest::OnMud` compares
  `|Local.X| <= Ext.X && |Local.Y| <= Ext.Y` and ignores Z. Adding a Z test with
  the capsule centre happens to pass today; adding one against a *visual* extent
  (4 cm tall) never fires at all.
- The grader's membership test is the actor's 2D **centre** inside the box. This
  node graph reproduces that, which is why the entering and leaving instants line
  up with the windows the grader opens. Do not substitute overlap events (trap 10).
- Break the loop on the first hit. There is exactly one `MudPatch` today; the tag
  lookup is what makes that a fact about the level rather than an assumption
  (trap 13).

## The function — `Enter Mud`

```
[Enter Mud  (entry)]
   | exec
   v
[SET Max Walk Speed]                     target = [Character Movement]
   value <-- [float * float]  A = [Get OrdinaryTopSpeed], B = 0.4
   | exec
   v
[Play Animation]                         target = [Mesh]
   New Anim To Play = [Get Wade Motion]  (the inherited property)
   Looping          = TRUE
   | exec
   v
[SET IsWading = true]
```

## The function — `Leave Mud`

```
[Leave Mud  (entry)]
   | exec
   v
[SET Max Walk Speed]                     target = [Character Movement]
   value <-- [Get OrdinaryTopSpeed]
   | exec
   v
[Set Anim Instance Class]                target = [Mesh]
   New Class = [Get OrdinaryWalkClass]
   | exec
   v
[SET IsWading = false]
```

`Set Anim Instance Class` returns the mesh to `AnimationBlueprint` mode, which
clears the single-node instance — which is exactly what makes the grader's
`WadeDrivesPose` read false again.

---

## Every way to get this subtly wrong

Each of these is derived from the C++ reference's own comments, the C++ leg's
anti-gaming notes, the grader source, or an engine specifier.

1. **Solving it inside an Animation Blueprint.** A state machine state, a blend by
   bool, a linked layer, a cached-pose swap. *Why it fails*: the grader reads only
   the single-node player's asset and the active montage
   (`MudWadeFunctionalTest.cpp::WadeDrivesPose`), so a pose that is visibly the
   wade still reads as "not wading" and `TheWadeMotionDrivesThePose` fires the
   moment the speed gate passes. This is the loudest trap on the task.
2. **Using the inherited `Wade Motion` without setting it.** *Why it fails*: the
   scaffold resolves it with
   `ConstructorHelpers::FObjectFinder(TEXT("/Game/Tasks/t1-mud-wade-cpp/A_MudWade"))`
   and the clip has only ever existed at the **un-suffixed**
   `/Game/Tasks/t1-mud-wade/A_MudWade`, so the finder
   fails and the property arrives **null**. `Play Animation` with a null asset
   silently does nothing — no error, no warning, and the figure slows down while
   the ordinary walk keeps driving the pose, which reads as "the wade was not
   driving" rather than as a missing asset. Set the default in Class Defaults (or
   use your own variable) pointing at the un-suffixed path.
3. **Calling `Play Animation` every Tick.** *Why it fails*: it re-enters the
   animation at time 0 on every frame, so the figure freezes on the wade's first
   pose. The grader still reads "wading" (the asset is right), so this passes L2
   and looks broken to the human who plays it — the worst combination. Edge-trigger
   it, exactly as the C++ reference does with its `bWading` latch.
4. **Calling `Set Anim Instance Class` every Tick.** *Why it fails*: same shape in
   the other direction — the anim instance is re-initialised every frame, so the
   ordinary walk resets to its first pose and never plays. Edge-trigger it too.
5. **Restoring a GUESSED animation blueprint.** Picking `ABP_Unarmed` by hand
   because that is what the scaffold's constructor happens to assign. *Why it
   fails*: it is right today and wrong the moment the scaffold changes, and it is
   the "wrote a number down instead of reading it" failure the C++ leg's
   anti-gaming notes name. Read `Get Anim Class` off the Mesh and put back exactly
   that.
6. **Recording the ordinary animation blueprint too late.** Reading it in
   `Enter Mud` records it after your own writes have begun; reading it on Tick
   eventually records whatever you last set, so the figure never returns to the
   walk and `TheOrdinaryWalkReturnsOffThePatch` fires. BeginPlay is the only safe
   place, and it does run (the surface swap spawns this Blueprint into a world that
   has already begun play).
7. **Changing the Mesh's Anim Class in the Components panel or Class Defaults**
   instead of at runtime. *Why it fails*: that changes the ORDINARY walk, for both
   figures, permanently — and the grader's clean-ground gates are what the graded
   figure is measured against before any mud is touched.
8. **Hard-coding 200, or 500.** *Why it fails*: the grader's clean-ground
   reference is measured on the run and separately checked against 400-600, so a
   submission that quietly changes what "normal" is fails
   `WalksAtItsNormalTopSpeed` rather than the wade gate. Read `Max Walk Speed` at
   BeginPlay and use `* 0.4` of it; the prompt discloses both numbers, but reading
   them is what survives a re-staging.
9. **Moving the figure yourself** — `Set Actor Location`, `Add Actor World Offset`,
   `Set Velocity`, a launch, a timeline. *Why it fails*: speed is measured from
   ground actually covered per frame and smoothed, so a hand-moved figure fights
   the character movement component and has to hold 30-50% continuously across the
   whole crossing and 85-115% continuously after it, not at a sample. Writing
   `MaxWalkSpeed` is one node and is what the level asks for.
10. **Overlap events instead of a per-frame bounds read.** *Why it fails*, twice
    over: a Character has more than one colliding component, so
    `ActorBeginOverlap` / `ActorEndOverlap` fire once per component PAIR — an End
    can arrive while another component is still inside the patch, un-wading the
    figure in the middle of the mud; and an overlap begins when the capsule EDGE
    touches — 42 cm early, the capsule radius the substrate's playable character
    sets (`ThirdPersonCharacter.cpp:18`, `InitCapsuleSize(42, 96)`) — while the
    grader's membership test is the actor's 2D CENTRE, so you are reacting to a
    different boundary from the one being graded. Read the bounds every frame.
11. **`Get Actor Bounds` with `Only Colliding Components` = false.** See the note
    on the function above: it stops matching the grader's own box the moment the
    patch gains any non-colliding decoration.
12. **Adding a Z test against the visual slab.** The slab is 4 cm tall; a
    capsule-centre-vs-slab Z test never fires and the figure never wades. The
    grader ignores Z; so should you.
13. **Finding the patch by class, label, or a hard-coded coordinate range.** *Why
    it fails*: the C++ leg's anti-gaming note 4 is aimed squarely at this — the
    control figure's patrol deliberately spans the same X band in a lane with no
    mud, so a coordinate fit slows or wades the control and fails
    `TheCleanLaneFigureIsUntouched` at the first frame it is judged. Resolve by the
    `MudPatch` tag.
14. **Shipping more than one candidate Blueprint.** *Why it fails*:
    `ResolveGradedBlueprintClass` scans **all of `/Game/Tasks` recursively** and
    raises `HARNESS-PRECONDITION` on two or more **non-abstract** subclasses of the
    placed class rather than picking one — a non-verdict, not a FAIL, so the run is
    wasted. No `BP_MudWader_v2`, no experiment parked in a sibling task folder.
    *Precisely*: the abstract skip happens BEFORE the ambiguity check
    (`CraftBenchFunctionalTest.cpp:682-696`), so an abstract intermediate beside
    one concrete Blueprint resolves to exactly one class and grades normally. The
    L2I leg counts the RESOLVABLE set only, for that reason — an earlier cut
    counted raw candidates and would have FAILed that submission on a run the
    harness graded correctly. Still ship exactly one Blueprint; the point is that
    the grader and the fixture now agree on what "one" means.
15. **Marking the Blueprint abstract.** *Why it fails silently*: the resolver skips
    `CLASS_Abstract` candidates, so if EVERY candidate is abstract it returns
    `nullptr` — "no Blueprint delivered" — and the run grades the untouched C++
    scaffold, reporting a complete behavioural FAIL that looks exactly like a
    submission that did nothing. The L2I leg's `answer_is_instantiable` names that
    case, and a candidate whose abstract flag cannot be READ fails it rather than
    being guessed either way.
16. **Reparenting to the wrong class, or to a non-pawn.** A Blueprint child of
    `ThirdPersonCharacter` (or of `Character`) is not a subclass of the PLACED
    class, so no swap happens and the C++ scaffold is graded. A stand-in that is
    not a pawn cannot be re-possessed and
    `SwapAllForGradedBlueprintRepossessing` reports a precondition — every drive
    input would otherwise go nowhere and read as "never moved".
17. **Adding the control's instance tag to the class.** The control is
    distinguished from the graded figure only by an instance tag the swap copies
    over. Add that tag to the class and BOTH figures read as the control, the
    graded figure is never found, and the fixture reports a staging precondition.
    Adding `MudHero` is harmless (`AddUnique`); adding the control's tag is not.

## Saving it out

Author it inside the substrate project so the parent class resolves, then copy the
`.uasset` into the task folder — the reference tree mirrors the deliverable root:

```
tasks/bp/t1-mud-wade-bp/reference/
  Content/Tasks/t1-mud-wade-bp/BP_MudWader.uasset
```

Nothing else belongs in `reference/`. In particular do **not** copy
`A_MudWade.uasset` in: it is supplied content that already ships in the substrate,
and a reference that carries the graded task's supplied assets is how a reference
starts passing for the wrong reason.

## WHAT WAS ACTUALLY BUILT (2026-08-23) — three deviations from the recipe above

The asset now on disk is `reference/Content/Tasks/t1-mud-wade-bp/BP_MudWader.uasset`.
Its BEHAVIOUR is the recipe's; its SHAPE differs in three ways, all verified by
reading the graph back with `get_asset_graph` rather than trusting the authoring
tool's own report — which claimed success on a graph that was wrong.

**1. No function graphs.** The available MCP toolset cannot create one, so
`Is On Mud` is INLINED into Tick and `Enter Mud` / `Leave Mud` are CUSTOM EVENTS
called from Tick. The inlined test needs somewhere to put its answer, so there is
an extra member bool `OnMud`, and Tick's FIRST node sets it false — verified,
because an `OnMud` that only ever gets set true would latch and the figure could
never leave the mud. Nothing grades graph shape: L2 drives behaviour, and the L2I
checks are folder/one-candidate/instantiable/in-declared-folder/no-native-subclass/
no-cpp-folder.

**2. `OrdinaryWalkClass` does not exist, and nothing is recorded at BeginPlay.**
The recipe stores the ordinary anim class at BeginPlay and restores it in
`Leave Mud`. The authoring tool could only produce an OBJECT reference
(`UAnimInstance*`, not `TSubclassOf<UAnimInstance>`) — it has no variable-typing
tool, `edit_blueprint` was unavailable, and `Blueprint.NewVariables` is not
exposed to Python, so the type could not be corrected either way. Its first cut
stored `Mesh->GetAnimInstance()` and restored via `GetObjectClass`, which is trap
6's shape: this Blueprint is SPAWNED into an already-running world by the surface
swap, so a null anim instance at BeginPlay would leave the variable null forever,
`GetObjectClass(null)` is null, and `SetAnimInstanceClass(null)` leaves the mesh
with no anim class — the ordinary walk never returns.

So the variable was deleted and `Leave Mud` now reads the Mesh component's own
`AnimClass` property AT RESTORE TIME and feeds it straight into
`Set Anim Instance Class`. **The premise was checked, not assumed:** `AnimClass`
is a component DEFAULT (`ABP_Unarmed_C`, on the native parent as well as here)
and nothing in this Blueprint ever writes it — `Play Animation` switches the
animation MODE and replaces the script instance but does not touch `AnimClass`.
This is strictly more robust than the recipe's route (no lifecycle dependency,
nothing to record too late) and it still satisfies trap 5, because the class is
READ from the component rather than named by hand. BeginPlay is therefore now a
single `SET OrdinaryTopSpeed` from `Max Walk Speed`.

**3. The generated ubergraph function is still named
`ExecuteUbergraph_BP_MudWader_S`.** Cosmetic, and it records a real hazard worth
keeping. `execute_unreal_python` AUTO-UNDOES a failed script — and that undo
DELETED the `.uasset` that had already been written and left the package flagged
"marked as deleted in editor", after which `OBJ SAVEPACKAGE` aborted before
serialisation on **thirteen** consecutive attempts with no `LogSavePackage` line
at all. `save_loaded_asset` returned False, and `compile_blueprint` reported
`saved: false, save_skipped_not_dirty: false`. The recovery was to duplicate into
a fresh package, prove the duplicate on disk with `os.path.isfile`, delete the
poisoned original, and rename the duplicate into place; the `_S` suffix is baked
into the compiled ubergraph name from that duplicate.

**Two lessons for the next asset.** `does_asset_exist` and `save_loaded_asset`
answer about the in-memory ASSET REGISTRY, so verify a save with
`os.path.isfile`/`getsize` on the concrete path — the grader materialises from
git, and an asset that exists only in the editor does not exist. And never let a
mutating script raise: the auto-undo is more destructive than the failure it is
cleaning up.

## After it exists

1. `cb discriminate --task t1-mud-wade-bp` — reference
   must PASS, empty must FAIL. **Empty** here means no Blueprint at all: the
   resolver finds nothing to swap, the run grades the placed C++ scaffold (which
   does nothing about the mud), and the expected named failure is
   `WadesSlowlyThroughTheMud: on the patch the figure measured …
   (100%, and the level asks for 30-50%)`.
2. Re-discriminate `t1-mud-wade-cpp` on the same tree.
   The two legs share one fixture; a change that fixes this leg and breaks that one
   is a net loss and grading both is the only way to see it. **The C++ leg used to FAIL here and no
   longer does:** its reference's `FObjectFinder` was repointed at the un-suffixed
   path on 2026-08-23 and it now discriminates. The SCAFFOLD's finder stays dead —
   that is trap 2, dead identically on both legs. Measured on `substrate=HEAD`.
3. Check the L2I leg reports 6/6 (`t1_mud_wade_bp.py`).
   The check names are `deliverable_folder_has_assets`,
   `exactly_one_blueprint_answer`, `answer_is_instantiable`,
   `answer_is_in_the_declared_folder`, `no_native_subclass_delivered` and
   `no_cpp_task_folder_for_this_leg` — a constant denominator of 6 on every
   submission, including an empty one.
4. The owner has to PLAY it (2026-08-18 directive). Same map as the C++ leg, so the
   play project already carries it. Watch specifically for the frozen-pose
   symptom of traps 3 and 4 — L2 cannot see it and a reviewer sees nothing else.
5. Do not `cb refgate` until the tree is clean: an uncertifiable gate is a full
   re-grade that caches nothing (owner, 2026-08-17).

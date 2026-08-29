---
id: t1-third-person-chase-camera
substrate: ThirdPerson
set: bp
tier: T1
capability_bucket: Gameplay Programming
category: other
layers: [L1, L2I]
introspect: [third_person_chase_camera.py]
---

# t1-third-person-chase-camera

An `L2I` asset-deliverable task in the shape the pilot
`t1-hero-blueprint-copy-with-flashlight` established: a committed baseline
`.uasset` under `Content/Tasks/<task-id>/` that the agent edits **in place**,
one verifier-owned introspect script asserting named structural checks, no map,
no fixture C++, no scaffold actor.

### Provenance and deliberate divergences from the source row

Imported from an earlier internal task list (not shipped): a camera row that
was never implemented there. The source row's
**Verification** and **Verification Method** cells are both EMPTY — no
acceptance criteria were ever authored for this row, so every check below is
new work derived from the Instruction text, not a transcription.

Five deliberate divergences, each recorded so the source row and the task can be
reconciled:

1. **Id.** The source row's `t10-` is a row index; this repo's `t<N>-` is a tier.
   Re-tiered to `T1`. The slug also had to move off the source row's name: the id
   appears in the agent-visible content path `Content/Tasks/<id>/`, and
   `spring-arm` is a **component type name**, which Hard Rule #2 forbids in
   anything the agent reads. The slug names the outcome (a third-person chase
   view), not the part that produces it.
2. **Start state.** The source row says *"Character with basic 1st person camera and
   WASD/mouse controls"*. Neither substrate provides that, and the `ThirdPerson`
   substrate provides its **opposite** — see *The start-state conflict* below.
   Resolved by shipping a purpose-built, camera-boom-free baseline character
   under `Content/Tasks/<task-id>/`.
3. **Content path.** The source row's sibling rows name `/Game/EvalTemplate/`, which
   **does not exist anywhere in the repo**; re-pathed to the repo convention
   `/Game/Tasks/<task-id>/`, which is agent-writable and fairness-pruned per
   task.
4. **Lag speed: 4, not the source row's 10.** `CameraLagSpeed = 10.f` is the
   **engine default** —
   `Engine/Source/Runtime/Engine/Private/GameFramework/SpringArmComponent.cpp:40`.
   The row's "lag speed of 10" therefore passes for free on any boom the agent
   adds and never touches: a dead gate with zero discriminating power. See *The
   dead-gate audit*.
5. **"Camera off control rotation" is graded only because the baseline turns it
   ON.** `UCameraComponent::bUsePawnControlRotation` is also `false` by default
   (`Engine/Source/Runtime/Engine/Private/Camera/CameraComponent.cpp:94`), so
   asserting `false` on a freshly added camera would be a second dead gate. The
   baseline ships `FollowCamera` as a first-person head camera **with that flag
   true**, which is both the authentic first-person setup the source row describes
   and what makes the assertion real: the cheapest wrong answer — re-home the
   camera and leave its own steering on — now fails a named check.

### The start-state conflict, and how it is resolved

The declared start state matches **neither** substrate as written, and the
mismatch is worse than absence on `ThirdPerson`:

- `CraftBenchTemplate` ships no character at all.
- `ThirdPerson` ships the **finished answer**. `Content/ThirdPerson/`,
  `Content/Characters/` and the C++ class `AThirdPersonCharacter`
  (`UE-projects/ThirdPerson/Source/ThirdPerson/ThirdPersonCharacter.cpp:38-47`)
  already construct a component literally named `CameraBoom` on the root at
  `TargetArmLength = 400` with `bUsePawnControlRotation = true`, plus a
  `FollowCamera` attached to its far end with `bUsePawnControlRotation = false`.
  The two Content paths are deny-listed, but the **C++ base class is not** —
  `Source/ThirdPerson/` is agent-writable — so a submission could obtain most of
  the asked-for rig by re-basing the character rather than building anything.

Resolution: ship a **purpose-built baseline character** at
`Content/Tasks/t1-third-person-chase-camera/BP_Scout`, derived from the plain
engine walking-character class (**not** from the substrate's third-person one),
carrying a head-mounted first-person viewpoint and **no boom of any kind**. That
reproduces the source row's declared start state faithfully inside an agent-writable
folder. The free-rig shortcut is then closed by an explicit named check —
`boom_authored_on_this_asset` — and disclosed to the agent in the prompt, so it
is a stated constraint rather than a trap. Property-by-property build spec:
`notes.md` §1.

### The dead-gate audit

Every numeric and boolean this row asserts, checked against
`USpringArmComponent`'s constructor
(`SpringArmComponent.cpp:18-46`) and `UCameraComponent`'s
(`CameraComponent.cpp:74-97`) in UE 5.8:

| row asserts | engine default | verdict |
|---|---|---|
| `TargetArmLength == 400` | `300.0f` (`SpringArmComponent.cpp:32`) | **live** — kept |
| socket offset up `75` | `SocketOffset` unset ⇒ `(0,0,0)` | **live** — kept |
| boom `bUsePawnControlRotation == true` | `false` (`:26`) | **live** — kept |
| `bEnableCameraLag == true` | unset ⇒ `false` | **live** — kept |
| `CameraLagSpeed == 10` | **`10.f` (`:40`)** | **DEAD** — changed to `4` |
| camera `bUsePawnControlRotation == false` | **`false` (`CameraComponent.cpp:94`)** | **DEAD as written** — made live by the baseline setting it `true` |

Two of the row's six graded values were dead gates; without this pass the task
would have reported 6 checks while grading 4. Uninitialized `UPROPERTY` bitfields
(`bEnableCameraLag`, `bEnableCameraRotationLag`, `bDrawDebugLagMarkers`) are
zero-filled with the rest of the UObject, so "not assigned in the constructor"
means `false`, not "unspecified".

> **Note on the behavior-only rule (Hard Rule #2).** Like the pilot and
> `t0-sanity-bp-log-on-beginplay`, this task names the concrete deliverable
> asset path and the two subobject names the verifier keys on (`CameraBoom`,
> `FollowCamera`) — the standard, precedented exception for asset-deliverable
> tasks whose whole point *is* producing a specific asset. Everything else in
> the prompt stays behavior-only: the two component **type** names never
> appear, no property name appears, and no editor operation is named.

## Primary concept

- `ps-components` — Components
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/components-in-unreal-engine)

The load-bearing capability is composing a **component hierarchy** inside an
existing Blueprint class asset: adding a new part at a specific attachment
point, re-homing an existing part onto it, and configuring both away from their
engine defaults so the assembly produces the asked-for behavior. `ps-bp-class`
(Blueprint Class,
https://dev.epicgames.com/documentation/en-us/unreal-engine/blueprint-class-assets-in-unreal-engine)
is adjacent — the deliverable is a Blueprint class asset — but the graded
difficulty is the hierarchy edit, not the class itself.

## Prompt given to the agent

> This project ships one playable character asset at
> `Content/Tasks/t1-third-person-chase-camera/BP_Scout`. Today the player looks
> out through `FollowCamera`, which is bolted straight to the character's own
> collision body at head height and swings around with the mouse — a
> first-person view.
>
> Convert that character to a third-person chase view. Keep the same asset and
> the same underlying figure: the new parts must be added to `BP_Scout` itself,
> so do **not** rebuild it on top of some other ready-made third-person
> character that already comes with a chase rig.
>
> Add a new part named `CameraBoom`: a rigid pole that hangs off the character's
> collision body, holds its far end **400** units away from the character, lifts
> that far end **75** units straight up with no sideways shift, points itself
> wherever the player is looking rather than wherever the character's body
> happens to be facing, and eases its own motion so it trails the character
> instead of snapping to it — with that trailing tuned to a catch-up rate of
> **4**.
>
> Then move `FollowCamera` so that it rides on the far end of `CameraBoom`
> instead of on the collision body, and stop `FollowCamera` from swinging with
> the mouse on its own: from here on `CameraBoom` does the aiming and the camera
> just looks along it.
>
> `BP_Scout` must compile cleanly and be saved.

## Workspace state pre-task

Substrate content that **exists** under
`Content/Tasks/t1-third-person-chase-camera/`:

- `BP_Scout.uasset` — a Blueprint class asset built on the engine's plain
  walking-figure type. It therefore already owns, by inheritance, a capsule
  collision body that is its root and an animated humanoid body part; the
  submission neither adds nor replaces those. On top of that it carries exactly
  one authored part:
  - `FollowCamera` — the player's viewpoint, attached directly to the inherited
    collision body, raised to head height, and configured to swing with the
    player's look input on its own. There is **no** boom or pole of any kind in
    the asset.

  It is compiled and saved, and ships with the project as committed content.
  `Content/Tasks/<task-id>/` is the agent-writable Content carve-out of the
  `ThirdPerson` substrate (`UE-projects/ThirdPerson/AGENT_WRITABLE.json`) and is
  where this task's content belongs; fairness isolation keeps this task's folder
  while hiding every other task's.

Files that **do not exist** (nothing here is created from nothing — the
deliverable is the edited baseline):

- none. The submission re-delivers
  `Content/Tasks/t1-third-person-chase-camera/BP_Scout.uasset` with the changes
  applied.

Out of scope / not needed:

- No movement, look or jump input bindings are wired on `BP_Scout`, and none are
  graded — the whole deliverable is how the asset's parts hang together and how
  they are configured.
- No C++ is required or expected. No level, no placed actor, no functional
  test. `Content/Maps/`, `Config/`, `Content/Characters/`, `Content/ThirdPerson/`
  and `Content/Input/` are deny-listed — the agent neither can nor needs to
  touch them.

## Verifier specification

Layer choice: this task grades via **L1 + L2I**. Every graded property is a
static property of a saved `.uasset` (which subobjects exist, what type each
one is, where each attaches, who authored it, and four scalars), so it is read
by verifier-owned editor-Python reflection over the submitted asset — not by
rendering, ticking, or a PIE world. L2 is deliberately **not** declared: there
is nothing to observe over time, and a fixture would need a map and a placed
actor this task has no use for. This is also why the source row's own *Issues* cell
("Does this need vision to test if camera is positioned well?") answers **no**:
arm length, offset and attachment are numbers and pointers in the asset, and the
source row's own follow-up ("Can likely do with just looking at positions") is what
this layer does.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64 Development"
        and "ThirdPerson Win64 Development" (short-circuits on first failure)
```

The submission is content-only, so L1 is a precondition (the project and its
Asset Registry must load cleanly), never a correctness signal.

### L2I — Structural assertion

The verifier-owned script
`tools/verify-single/introspect/third_person_chase_camera.py` runs headless via
`UnrealEditor-Cmd -ExecutePythonScript=` under `-nullrhi`, read-only, and prints
one `CRAFTBENCH-INTROSPECT-JSON` verdict block. It emits **exactly 14 named
checks on every leg** (a constant denominator, so the per-check
`tests_passed/tests_run` the registry already records is comparable across
submissions). PASS requires all 14:

```text
character_asset_exists            /Game/Tasks/<id>/BP_Scout resolves
boom_component_exists             a subobject named "CameraBoom" exists
boom_is_spring_arm                that subobject's template is a boom component
                                  (SpringArmComponent or a subclass)
boom_authored_on_this_asset       the boom is neither inherited nor native --
                                  it was added to THIS asset, not obtained by
                                  re-basing onto a class that already has one
boom_attached_to_character_root   its attach parent is the INHERITED collision
                                  capsule: named "CapsuleComponent"/
                                  "CollisionCylinder" AND a CapsuleComponent AND
                                  inherited/native rather than submission-authored
boom_arm_length_400               its arm length == 400 (+/-0.5); default is 300
boom_socket_offset_up_75          its END offset == (0,0,75) (+/-0.5 per axis);
                                  default is (0,0,0). TargetOffset is recorded
                                  in the detail but is NOT the graded property
boom_uses_control_rotation        it follows the player's control rotation
                                  (True); default is False
boom_camera_lag_enabled           its positional trailing is on (True);
                                  default is False
boom_camera_lag_speed_4           its catch-up rate == 4 (+/-0.01);
                                  ** default is 10 -- see the dead-gate audit **
camera_component_exists           a subobject named "FollowCamera" exists AND is
                                  a viewpoint component
camera_attached_to_boom           its attach parent is the CameraBoom subobject:
                                  named "CameraBoom" AND a boom component AND
                                  the same object the boom check resolved
camera_off_control_rotation       the camera does NOT follow control rotation
                                  (False). Live only because the baseline
                                  ships this True
character_compiles_up_to_date     BP_Scout loads with an up-to-date compile
                                  status (BS_UpToDate / ...WithWarnings)
```

**Read routes** (each one either confirmed live on UE 5.8.0-55116800 for the
pilot, plan §10, or resolved from engine source; none is guessed):

- *asset existence* — `unreal.EditorAssetLibrary.does_asset_exist`.
- *component walk* — `unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)`.
  It is an **engine** subsystem: `get_editor_subsystem` raises
  `TypeError: Cannot nativize`. Then
  `SubobjectDataBlueprintFunctionLibrary.get_data / get_variable_name /
  get_parent_handle / get_object`.
- *attach parent* — `get_parent_handle` on the subobject's data.
  `FSubobjectData::GetVariableName` returns the SCS node's variable name for
  authored components and the anchoring property name for native inherited ones,
  which is why the inherited capsule is accepted under **either** its property
  name `CapsuleComponent` (`Character.h:360`) or its native object name
  `CollisionCylinder` (`Character.cpp:34`). **The name is necessary, never
  sufficient** — see the anti-gaming notes.
- *authorship* — `IsInheritedComponent` / `IsNativeComponent`
  (`SubobjectDataBlueprintFunctionLibrary.h:113-117`), both `BlueprintCallable`.
- *scalars* — `get_editor_property` on the component template for
  `target_arm_length`, `socket_offset`, `use_pawn_control_rotation`,
  `enable_camera_lag`, `camera_lag_speed`. All five are
  `EditAnywhere, BlueprintReadWrite` on `USpringArmComponent`
  (`SpringArmComponent.h:24-101`), so all five clear the Python-readability
  test (`CPF_Edit|CPF_BlueprintVisible|CPF_BlueprintAssignable`,
  `PropertyAccessUtil.cpp:425-433`). The script tries both the pythonized and
  the raw spelling of each and never invents a value.
- *compile status* — `UBlueprint::Status` is
  `UPROPERTY(transient, BlueprintReadOnly)`, so what is read is the compile
  state produced by loading the submitted asset, which is the property worth
  gating.

**What is deliberately NOT graded, and why.** The row says the camera attaches
"to the end of that spring arm". The *end* is expressed by the attach **socket**
(`USpringArmComponent::SocketName == "SpringEndpoint"`,
`SpringArmComponent.cpp:16`), and that value has **no reflection read route**:
`USCS_Node::AttachToName`, `USCS_Node::ParentComponentOrVariableName` and
`UBlueprint::SimpleConstructionScript` are all bare `UPROPERTY()` with no
`CPF_Edit|CPF_BlueprintVisible` flag, `USceneComponent::AttachSocketName` is
reflection-denied, and `SubobjectDataBlueprintFunctionLibrary` exposes no socket
accessor at all (all 25 of its `UFUNCTION`s enumerated). The gradeable half is
the attach **parent**, which is what `camera_attached_to_boom` asserts. This is
recorded rather than silently dropped, because a future harness change (an SCS
read via C++, or a transient spawn plus `GetAttachSocketName` on the constructed
instance) would make it gradeable.

**Identity is by pre-declared content path and pre-declared subobject name,
never by class.** The asset path and the two names (`CameraBoom`,
`FollowCamera`) are fixed by the spec and stated in the prompt; the agent may
subclass a component type, reach the outcome through the editor or through
Python, and none of that is penalized.

**Score granularity.** `registry.py:340-346` sets `tests_run`/`tests_passed`
from the per-check counts, so `report.json` already carries `x/14` for this
task. That number is **reported, not gating** — `overall` stays
`all(status == "pass")` (plan §3.2). The denominator is constant at 14 on every
leg, including a missing asset, so a submission cannot improve its reported
ratio by making checks unreachable.

## Reference solution metadata

- LOC range: **0** lines of code. The deliverable is one edited `.uasset`.
- Files touched: 0 created, 1 modified
  (`Content/Tasks/t1-third-person-chase-camera/BP_Scout.uasset`).
- Senior-dev hours: 0.2-0.4 (one component added at a specific attach point,
  one component re-parented, five property edits, compile and save).

## Anti-gaming notes

1. **Rig obtained by re-basing, not by building.** *Failure mode*: instead of
   assembling anything, the agent points `BP_Scout` at a base class that already
   ships the whole chase rig. The substrate makes this the single cheapest wrong
   answer — `AThirdPersonCharacter`
   (`Source/ThirdPerson/ThirdPersonCharacter.cpp:38-47`, in the agent-writable
   module) constructs a `CameraBoom` on the root at arm length `400` with
   `bUsePawnControlRotation = true` and a `FollowCamera` on its far end, so a
   one-click re-base would satisfy most of the checklist without the agent
   composing a hierarchy. *Defense*: `boom_authored_on_this_asset`
   (`BOOM_NOT_AUTHORED_ON_ASSET`) requires the boom subobject to report
   **neither** `IsInheritedComponent` nor `IsNativeComponent` — a boom that
   arrived with the base class is both. The constraint is stated in the prompt,
   so this gates a shortcut, not a surprise. An unreadable authorship probe
   fails through a **different** token (`BOOM_AUTHORSHIP_READ_ERROR`), so an API
   break can never be credited as this failure.
2. **Boom hung wherever the cursor was.** *Failure mode*: a newly added
   component parents to whatever happened to be selected, so the boom lands on
   the animated mesh (making the view swim with the walk cycle) or on the camera
   itself. *Defense*: `boom_attached_to_character_root`
   (`BOOM_ATTACH_PARENT_WRONG`) resolves the boom's *parent handle* and requires
   the inherited collision capsule. Name alone would be gamed by any component
   the agent simply *called* `CapsuleComponent`, so the check additionally
   requires that parent to be a capsule collision component **and** to be
   inherited/native rather than authored by the submission.
3. **Right name, wrong thing.** *Failure mode*: the agent adds a plain
   positioning node named `CameraBoom`, parks the camera 400 units behind it by
   hand, and calls it done — the hierarchy looks right in the outliner and the
   camera is even in roughly the right place, but nothing springs, trails or
   collides. *Defense*: `boom_is_spring_arm` (`BOOM_NOT_SPRING_ARM`) demands a
   positive `isinstance` against the boom component type, and
   `camera_attached_to_boom` independently requires the camera's parent to be
   that same boom object — so a decoy second component named `CameraBoom`
   satisfies neither.
4. **Everything left at engine defaults.** *Failure mode*: the boom is added and
   never configured, which under the source row's own numbers would still have
   scored — `CameraLagSpeed`'s default **is** the row's requested `10`
   (`SpringArmComponent.cpp:40`), and the camera's `bUsePawnControlRotation`
   default **is** the row's requested `false` (`CameraComponent.cpp:94`).
   *Defense*: all four boom settings are pinned to non-defaults
   (`BOOM_ARM_LENGTH_WRONG`, `BOOM_SOCKET_OFFSET_WRONG`,
   `BOOM_NOT_ON_CONTROL_ROTATION`, `BOOM_CAMERA_LAG_DISABLED`,
   `BOOM_LAG_SPEED_WRONG`), with the lag speed deliberately moved off `10`; and
   the camera flag is graded only because the **baseline** ships it `true`, so
   the "leave it alone" answer fails.
5. **Camera re-homed but still steering itself.** *Failure mode*: the agent
   drags `FollowCamera` under the boom and stops there. Both the boom and the
   camera then consume the player's look input, the rotation is applied twice,
   and the view is wrong in exactly the way the row's last clause is guarding
   against. *Defense*: `camera_off_control_rotation`
   (`CAMERA_STILL_ON_CONTROL_ROTATION`) reads the flag off the submitted camera
   template and requires a positive read of `False`; an unreadable property
   fails through `CAMERA_CONTROL_ROTATION_READ_ERROR` instead, never as "off".
   Prose claiming success cannot satisfy any of these — the verdict is read only
   from the submitted bytes.

## Hidden invariants

- **The empty submission is not vacuous here.** Because the deliverable is an
  edit of a committed baseline rather than a new file, an empty submission is
  graded against the baseline itself: `character_asset_exists`,
  `camera_component_exists` and `character_compiles_up_to_date` PASS (`3/14`)
  and everything else fails, starting at `boom_component_exists`. The reported
  ratio therefore has a meaningful floor, and "did nothing" is distinguishable
  from "did something wrong" by *which* checks failed.
- `boom_authored_on_this_asset` is not implied by any behavior the player could
  observe — a re-based character with the same numbers looks identical in game.
  It is a **process** constraint, which is why it is stated outright in the
  prompt rather than left implicit, and why its failure token is disjoint from
  every other check's.
- The two attachment checks are evaluated **independently**: a submission that
  hangs the boom in the wrong place but correctly re-homes the camera onto it
  fails exactly one of them, so the matrix can tell the two mistakes apart.

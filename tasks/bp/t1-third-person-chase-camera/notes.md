# t1-third-person-chase-camera — implementor notes + asset build spec

Text half authored 2026-07-27 (no editor, no build, no live Unreal touched).
**The binary half is not done.** This file is the contract the editor track
builds against: everything below is stated property-by-property so the assets
can be authored without re-deriving anything from the spec.

## Provenance

- Source: an earlier internal task list (not shipped) — a camera row that was
  never implemented there.
- The source row's **Verification** and **Verification Method** cells are both
  EMPTY. Unlike the pilot, there was no acceptance checklist to transcribe or
  audit — the 14 named checks were derived from the Instruction text and then
  audited against engine defaults from scratch.
- The source row's **Issues** note: *"Need a bunch of starting assets / Does this need
  vision to test if camera is positioned well? Can likely do with just looking
  at positions."* Both are answered by the design: the starting asset is §1
  below, and no vision is needed — every graded fact is a scalar or a pointer
  in the saved asset (FR-020d).
- Substrate `ThirdPerson` is the owner's choice for the imported set. Here the
  choice is **not** free: this substrate ships the finished answer (see §0), so
  the baseline and one extra named check exist specifically to neutralize it.
  The measured cost is also real — a ThirdPerson L1 leg measured **172 s vs
  131 s** on `CraftBenchTemplate` because there is no warm slot for it on this
  box (plan §6).

## §0 The start-state conflict (read this before authoring anything)

The source row's declared start state — *"Character with basic 1st person camera and
WASD/mouse controls"* — matches neither substrate:

| substrate | what it actually ships | verdict |
|---|---|---|
| `CraftBenchTemplate` | no character at all | start state absent |
| `ThirdPerson` | `AThirdPersonCharacter` + `BP_ThirdPersonCharacter`: a **third-person spring-arm rig, already built** | start state *inverted* |

`UE-projects/ThirdPerson/Source/ThirdPerson/ThirdPersonCharacter.cpp:38-47`:

```cpp
CameraBoom = CreateDefaultSubobject<USpringArmComponent>(TEXT("CameraBoom"));
CameraBoom->SetupAttachment(RootComponent);
CameraBoom->TargetArmLength = 400.0f;
CameraBoom->bUsePawnControlRotation = true;
FollowCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("FollowCamera"));
FollowCamera->SetupAttachment(CameraBoom, USpringArmComponent::SocketName);
FollowCamera->bUsePawnControlRotation = false;
```

That is *literally* the row's deliverable, down to both subobject names and the
arm length, and while `Content/ThirdPerson/` and `Content/Characters/` are
deny-listed, **`Source/ThirdPerson/` is agent-writable** — so the C++ base class
is reachable and a submission could obtain the rig by re-basing.

**Decision (this row):** ship a purpose-built, boom-free baseline character
under `Content/Tasks/<task-id>/` (§1), derived from the **plain engine**
walking-character class, and close the re-basing shortcut with one explicit
named check (`boom_authored_on_this_asset`) that is **disclosed in the prompt**.

Three alternatives were considered and rejected:

1. *Move the task to `CraftBenchTemplate`.* Dodges the contamination but throws
   away the walking character the row's whole premise rests on, and the baseline
   would then have to invent one anyway.
2. *Deny-list `Source/ThirdPerson/`.* Substrate-wide change for one row; breaks
   every other ThirdPerson task's writable module.
3. *Grade only the five settings and ignore where the rig came from.* Leaves an
   `11/14` free ride (see `discrimination/rig-inherited-from-template-character/`).

## §0.1 Dead-gate audit (mandatory pass; two hits)

Checked against `<UE-root>/Engine/Source`:

| row asserts | engine default | source | verdict |
|---|---|---|---|
| `TargetArmLength == 400` | `300.0f` | `Runtime/Engine/Private/GameFramework/SpringArmComponent.cpp:32` | live |
| socket offset up `75` | `SocketOffset` never assigned in the ctor ⇒ zero-filled `(0,0,0)` | `SpringArmComponent.cpp:18-46`, decl at `SpringArmComponent.h:29` | live |
| boom `bUsePawnControlRotation == true` | `false` | `SpringArmComponent.cpp:26` | live |
| `bEnableCameraLag == true` | never assigned in the ctor ⇒ `false` | decl at `SpringArmComponent.h:76` | live |
| **`CameraLagSpeed == 10`** | **`10.f`** | **`SpringArmComponent.cpp:40`** | **DEAD → changed to `4`** |
| **camera `bUsePawnControlRotation == false`** | **`false`** | **`Runtime/Engine/Private/Camera/CameraComponent.cpp:94`** | **DEAD as written → made live by the baseline** |

Two of six. Without this pass the task would have advertised 6 graded settings
while grading 4, and the `boom-left-at-engine-defaults` variant would have
scored a free check for a boom it never configured.

Adjacent defaults worth knowing, none of them asserted here: `bDoCollisionTest`
`true`, `ProbeSize` `12`, `ProbeChannel` `ECC_Camera`, `bInheritPitch/Yaw/Roll`
all `true`, `CameraRotationLagSpeed` `10`, `bUseCameraLagSubstepping` `true`
(`SpringArmComponent.cpp:24-45`). Every one of those would be a dead gate if a
future revision of this row tried to assert it at its default.

**Reverting the lag speed to the source row's 10** (if a human overrules the audit)
is a four-place edit: `EXPECTED_LAG_SPEED` in the introspect script, the check
id `boom_camera_lag_speed_4`, the number in the prompt and in the Verifier
specification, and this table. It also silently destroys the
`boom-left-at-engine-defaults` variant's secondary failure — do not do it
without re-reading that variant's README.

## §0.2 One thing the row asks for that CANNOT be graded

"a camera component attached to **the end** of that spring arm". The *end* is
the attach socket `USpringArmComponent::SocketName == "SpringEndpoint"`
(`SpringArmComponent.cpp:16`), and no reflection route reaches it:

- `USCS_Node::AttachToName`, `USCS_Node::ParentComponentOrVariableName` and
  `UBlueprint::SimpleConstructionScript` are bare `UPROPERTY()` with no
  `CPF_Edit | CPF_BlueprintVisible | CPF_BlueprintAssignable`, so they are
  denied by `PropertyAccessUtil.cpp:425-433` (the same rule that denies
  `USkeleton::Sockets`; plan §12.1);
- `USceneComponent::AttachSocketName` is denied for the same reason, and the
  `GetAttachSocketName` UFUNCTION reads the *template*, which is unattached at
  rest;
- `SubobjectDataBlueprintFunctionLibrary` exposes **no** socket accessor (all
  25 of its `UFUNCTION`s were enumerated at
  `Editor/SubobjectDataInterface/Public/SubobjectDataBlueprintFunctionLibrary.h`).

So the task grades the attach **parent** and says so in the spec. A submission
that parents the camera to the boom's origin instead of its endpoint passes.
Cost of closing it later: a transient `spawn_actor_from_class` +
`GetAttachSocketName` on the constructed instance (the R6 route), which needs a
world — available under `-nullrhi -ExecutePythonScript` per plan §12.1, but
unproven.

---

## 1. BASELINE asset (ships in the substrate, committed, agent-writable)

**Path on disk:**
`UE-projects/ThirdPerson/Content/Tasks/t1-third-person-chase-camera/BP_Scout.uasset`
**Content path:** `/Game/Tasks/t1-third-person-chase-camera/BP_Scout`

| property | required value | why the verifier cares |
|---|---|---|
| asset type | Blueprint Class | — |
| parent class | **engine `Character`** — NOT `ThirdPersonCharacter`, NOT any subclass of it | this is the whole point of §0. If the baseline inherits a boom, `boom_authored_on_this_asset` can never pass and the task is unsolvable |
| inherited root | the Character's own capsule (`CapsuleComponent` / native `CollisionCylinder`) | `boom_attached_to_character_root` requires the boom's parent to be this, and to report inherited/native |
| inherited mesh | the Character's `Mesh` / native `CharacterMesh0` | not asserted; it exists so `boom-hung-on-the-mesh` has a plausible wrong parent to use. A skeletal mesh **asset** is optional and ungraded — leaving it unset is fine and avoids a reference into deny-listed `Content/Characters/` |
| component 1 | `CameraComponent`, **variable name exactly `FollowCamera`** (case-sensitive), attached **directly to the inherited capsule**, relative location `(0, 0, 64)` (head height) | `camera_component_exists` matches on the name and requires an `isinstance` against the viewpoint type. The attach parent being the capsule is what makes `camera_attached_to_boom` FAIL on the empty leg |
| component 1 setting | **`bUsePawnControlRotation = TRUE`** | **load-bearing, and the single most important line in this file.** The engine default is `false` (`CameraComponent.cpp:94`), so if the baseline leaves it default the `camera_off_control_rotation` check grades nothing and the `camera-still-steering-itself` variant is unauthorable. Setting it `true` is also the authentic first-person setup the source row's start state describes |
| boom | **none** — no `SpringArmComponent` of any kind, under any name | `boom_component_exists` must fail on the empty leg |
| other components | none | keeps the `names=` detail short and the walk unambiguous |
| input bindings | none, deliberately | the source row says "WASD/mouse controls"; the substrate's input assets live in deny-listed `Content/Input/` and nothing about input is graded. The spec's *Workspace state* says so explicitly rather than promising controls that are not there |
| compile / save | compiled clean, saved, not dirty | `character_compiles_up_to_date` |

Also create the folder itself:
`Content/Tasks/t1-third-person-chase-camera/` must exist in the substrate even
though only one asset lives in it.

### Verify these two reads in the editor's Python console before committing

```python
import unreal
bp = unreal.EditorAssetLibrary.load_asset('/Game/Tasks/t1-third-person-chase-camera/BP_Scout')
ss = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)   # ENGINE, not editor
hs = ss.gather_subobject_data_for_blueprint(bp)
L  = unreal.SubobjectDataBlueprintFunctionLibrary
for h in hs:
    d = L.get_data(h)
    print(L.get_variable_name(d), L.get_object(d), L.is_inherited_component(d),
          L.is_native_component(d), L.is_root_component(d))
cam = ...  # the FollowCamera template from the walk
print(cam.get_editor_property('use_pawn_control_rotation'))  # must print True
```

If `use_pawn_control_rotation` is not the spelling that resolves, record the
spelling that does — the script already tries
`use_pawn_control_rotation` / `b_use_pawn_control_rotation` /
`bUsePawnControlRotation` in that order, so any of the three is fine, but only
an editor settles which one UE 5.8 actually exposes.

### Three work-loss hazards for whoever authors this (plan §9.7)

- Fairness isolation physically **moves** an untracked `Content/Tasks/<id>/` out
  of the substrate the next time a *different* task is driven. Commit the
  baseline as soon as it exists.
- `run_task` grades from **git HEAD**, so an uncommitted baseline is invisible
  to a normal grade (use `--substrate-from-live` / `cb discriminate --wip`
  while iterating).
- `_CB_EDITOR_MARKER = "craftbench"` means an in-repo authoring editor is
  classified CraftBench-owned: `cb down` / `cb eval` / `cb view` will kill it
  unwarned. And launch via `launch_unreal_project` (its argv carries
  `-unattended`, which gates Live Coding OFF); an attended editor makes every
  UBT build on this box fail exit 6 in ~13 s.

---

## 2. REFERENCE solution

**Path on disk:**
`tasks/bp/t1-third-person-chase-camera/reference/Content/Tasks/t1-third-person-chase-camera/BP_Scout.uasset`

The reference overlay carries **only** the edited `BP_Scout.uasset` — the same
single file at every leg. `apply_submission` is a copy-only overlay with no
wipe, so a leg that ships nothing is graded against the substrate's own
baseline.

Build it by opening the baseline and then:

| step | required end state | check it satisfies |
|---|---|---|
| 1 | asset still named `BP_Scout`, still parented to engine `Character`, still in the same folder | `character_asset_exists` |
| 2 | new `SpringArmComponent`, **variable name exactly `CameraBoom`**, added to THIS Blueprint's own component list | `boom_component_exists`, `boom_is_spring_arm`, `boom_authored_on_this_asset` |
| 3 | `CameraBoom`'s attach parent is the **inherited capsule** (`CapsuleComponent` / `CollisionCylinder`), i.e. the actor root | `boom_attached_to_character_root` |
| 4 | `CameraBoom.TargetArmLength = 400.0` (tol +/-0.5) | `boom_arm_length_400` |
| 5 | `CameraBoom.SocketOffset = (0.0, 0.0, 75.0)` (tol +/-0.5 per axis). **`TargetOffset` stays `(0,0,0)`** — the row's "offset up by 75" is at the far END of the arm, which is `SocketOffset`; `TargetOffset` is the offset at the *start* (`SpringArmComponent.h:28-33`) | `boom_socket_offset_up_75` |
| 6 | `CameraBoom.bUsePawnControlRotation = true` | `boom_uses_control_rotation` |
| 7 | `CameraBoom.bEnableCameraLag = true` | `boom_camera_lag_enabled` |
| 8 | `CameraBoom.CameraLagSpeed = 4.0` (tol +/-0.01) — **not 10; see §0.1** | `boom_camera_lag_speed_4` |
| 9 | `FollowCamera` re-parented so its attach parent is `CameraBoom`. Attaching at the boom's `SpringEndpoint` socket is correct and recommended, but is NOT graded (§0.2) | `camera_attached_to_boom` |
| 10 | `FollowCamera.bUsePawnControlRotation = **false**` (it was `true` in the baseline) | `camera_off_control_rotation` |
| 11 | `FollowCamera`'s relative location may be left at `(0,0,0)` once it rides the boom | — |
| 12 | compiled clean, saved | `character_compiles_up_to_date` |

Expected reference verdict: **L2I `14/14`, overall PASS.**

### Two gotchas to check by hand

- **Re-parenting `FollowCamera` may keep its old relative location.** The
  editor preserves world transform on some re-parent paths, leaving the camera
  at `(0, 0, 64)` relative to the boom. Nothing in the verdict cares, but it
  makes a review capture look wrong; zero it.
- **Do not create the boom by re-basing.** If at any point you reparent
  `BP_Scout` to `ThirdPersonCharacter` "just to see", the boom becomes native
  and the reference itself will FAIL `boom_authored_on_this_asset`. That is the
  check working, not a bug.

---

## 3. Discrimination variants

Five variant `.uasset`s, one per anti-gaming note, specified in
`discrimination/MATRIX.md` and in each variant folder's
`README-MISSING-ASSETS.md`. Each is exactly ONE deviation from the reference
(or from the baseline where the README says so), so the matrix can attribute
each FAIL to one gate:

| variant | one deviation | named failure |
|---|---|---|
| `rig-inherited-from-template-character/` | reparented to the substrate's third-person C++ character; nothing authored | `BOOM_NOT_AUTHORED_ON_ASSET inherited=` |
| `boom-hung-on-the-mesh/` | boom's parent is the animated mesh, not the capsule | `BOOM_ATTACH_PARENT_WRONG parent=` |
| `boom-is-a-plain-scene-component/` | `CameraBoom` is a bare positioning node | `BOOM_NOT_SPRING_ARM class=` |
| `boom-left-at-engine-defaults/` | real boom, none of the five settings touched | `BOOM_ARM_LENGTH_WRONG value=` |
| `camera-still-steering-itself/` | camera left on control rotation | `CAMERA_STILL_ON_CONTROL_ROTATION value=` |

---

## 4. Pre-flight before the first graded leg

Three blockers that are not about the assets at all:

1. **`tools/verify-single/tests/test_verdict_taxonomy.py:79`**
   (`test_every_shipping_spec_declares_only_landable_gating_layers`) globs
   `tasks/*/*/task.md` and asserts every spec's layers are exactly
   `("L1","L2")`. It is **already red** for the pilot; this task does not add a
   new blocker, but it does not clear one either. Per plan §9.1 the fix is to
   replace the equality with a landability assertion **and** demonstrate that an
   L2I task really does produce an `L2I` key in `layers_out`.
2. **Registry bookkeeping (plan §9.2/§12.3).** `cb lint --all` runs
   `inventory.py`, which needs a `tasks/CATALOG.md` row for this id plus the
   hard-coded task-count claims bumped (the repo conventions, `tasks/CATALOG.md` x2, the
   the two authoring-skill files (under `.claude/`, not shipped)). Map-less task ⇒ **7** edits, not 8.
   The cost is **shared** across the rows landing in this batch — do one
   reconciliation pass for all of them, not one per row.
3. **`registry.py:342` turns an L2I `error` into a graded FAIL** (plan §13.2).
   With L2I firing, a typo in a verifier-owned grader scores the *model*. Not
   introduced by this row, but it applies to it.

## 5. Reproducing the offline oracle

Proof that every MATRIX substring is a literal this script prints was produced
with a throwaway harness modelled on the pilot's committed one,
`tools/verify-single/tests/test_introspect_hero_blueprint.py`. It is not
committed with this row (the row's deliverable list is text + one grader), but
it is cheap to rebuild: copy that file, swap the fake component classes for
`SpringArmComponent` / `CameraComponent` / `CapsuleComponent`, and give the fake
`unreal` module an `is_root_component` predicate and a `Vector`-shaped object
with `.x/.y/.z`. The six leg builders are:

| leg | fake world |
|---|---|
| `reference` | boom authored on the capsule, spring-arm type, `400` / `(0,0,75)` / `True` / `True` / `4.0`; camera on the boom, `use_pawn_control_rotation=False` |
| `empty` | baseline only: camera on the capsule with `use_pawn_control_rotation=True`, no boom |
| `rig-inherited-from-template-character` | boom + camera both `inherited=True native=True`; `400`, `(0,0,0)`, `True`, `False`, `10.0` |
| `boom-hung-on-the-mesh` | reference, but the boom's parent subobject is the inherited mesh |
| `boom-is-a-plain-scene-component` | `CameraBoom` is a `SceneComponent` with none of the five properties |
| `boom-left-at-engine-defaults` | real boom, `300` / `(0,0,0)` / `False` / `False` / `10.0` |
| `camera-still-steering-itself` | reference, but camera `use_pawn_control_rotation=True` |

Run each through `main()` with stdout captured, parse with the real
`layers.l2_introspect.parse_introspect_verdict`, and join against the real
`aura_rig.discriminate.parse_matrix`. Assert: 14 checks on **every** leg, the
reference at `14/14`, and each negative leg's MATRIX substring present in the
detail of the *predicted* check.

## 6. Calibration record

- [ ] Baseline `BP_Scout.uasset` authored + committed (incl. the `true` camera
      flag from §1 — confirm the read before committing).
- [ ] Reference `BP_Scout.uasset` authored; L2I reads **14/14**.
- [ ] `use_pawn_control_rotation` / `enable_camera_lag` / `socket_offset` /
      `camera_lag_speed` / `target_arm_length` confirmed readable via
      `get_editor_property` from headless Python under `-nullrhi`, and the
      resolving spelling of each recorded here.
- [ ] `is_inherited_component` / `is_native_component` / `is_root_component`
      confirmed to return the expected values for (a) the inherited capsule and
      (b) an SCS-authored boom. `boom_authored_on_this_asset` is the load-bearing
      anti-gaming check and it cannot degrade gracefully — if these reads are
      unavailable it fails through `BOOM_AUTHORSHIP_READ_ERROR` on **every**
      leg, including the reference, which is a loud failure by design.
- [ ] Discrimination executed: reference PASS, empty + 5 variants FAIL, each via
      its MATRIX substring.
- [ ] **Measured L2I leg wall-clock recorded here.** Still unanswered across the
      whole set (plan §1/§6).

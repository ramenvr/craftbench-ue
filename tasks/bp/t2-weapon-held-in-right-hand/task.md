---
id: t2-weapon-held-in-right-hand
substrate: ThirdPerson
set: bp
tier: T2
capability_bucket: Gameplay Programming
category: other
layers: [L1, L2I]
introspect: [weapon_held_in_right_hand.py]
---

# t2-weapon-held-in-right-hand

The second `L2I` task in the repo, built in the shape
`t1-hero-blueprint-copy-with-flashlight` established: committed baseline
`.uasset`s -> the agent edits them in place -> **one** verifier-owned introspect
script asserts named structural checks. No map, no fixture C++, no scaffold
actor.

### Provenance and deliberate divergences from the source row

Imported from an earlier internal task list (not shipped): a socket-and-
attachment row that was never implemented there. Its
*Issues* note: "Need a bunch of starting assets" — which is what §1 of
`notes.md` specifies, property by property.

Five deliberate divergences, each recorded so the source row and the task can be
reconciled:

1. **Id.** The source row's `t5-` is a row index; this repo's `t<N>-` is a tier
   (the set-provenance note (internal, not shipped)). Re-tiered to `T2` — three coordinated edits
   across two asset families, which is more than a single-concept T1 — and
   re-slugged to the observable outcome so the agent-visible content path
   `Content/Tasks/<id>/` does not spell out the editor operation.
2. **Content paths.** The source row's `/Game/EvalTemplate/BP_EvalChar` **does not
   exist anywhere in the repo** (the only occurrence of that string is the
   source list), and a flat `/Game/EvalTemplate/` is outside every writable
   prefix of both substrates. Re-pathed to the repo convention
   `/Game/Tasks/<task-id>/`, which is agent-writable and fairness-pruned per
   task. The asset *name* `BP_EvalChar` is kept verbatim from the row.
3. **The baseline rig is a DUPLICATE, and the source row mis-names it.**
   `/Game/Characters/` is deny-listed in `UE-projects/ThirdPerson/AGENT_WRITABLE.json`,
   so an agent that added the attachment point to the stock mannequin would be
   SANDBOX-REJECTed at exit 4 through no fault of its own. The baseline is
   therefore a duplicated mesh + skeleton pair under `Content/Tasks/<id>/`.
   While cutting them, note that the source row's "the Epic UE5 mannequin
   `SK_Mannequin` at `/Game/Characters/Mannequins/Meshes/`" is wrong about the
   asset type: in this substrate `SK_Mannequin.uasset` is the **`Skeleton`**
   asset, and the skeletal *meshes* are `SKM_Manny_Simple` / `SKM_Quinn_Simple`
   (both referencing `SK_Mannequin` as their skeleton — read out of the package
   headers, 2026-07-27). The duplicate pair is cut from `SKM_Manny_Simple` +
   `SK_Mannequin`. Bone `hand_r` is present in `SK_Mannequin`.
4. **The row's "identity relative location/rotation" clause is a DEAD GATE and
   is not scored as a check of its own.** `USkeletalMeshSocket` declares
   `FVector RelativeLocation = FVector::ZeroVector;` and
   `FRotator RelativeRotation = FRotator::ZeroRotator;`
   (`Engine/Source/Runtime/Engine/Classes/Engine/SkeletalMeshSocket.h:30-34`),
   so a freshly created socket already satisfies it and the assertion cannot
   fail for any agent that simply did not touch the transform. It is kept —
   folded in as its own low-discrimination check with its reasoning recorded —
   because one real authoring route *does* violate it
   (`USkeletalMeshSocket::InitializeSocketFromLocation` writes `BoneName`,
   `RelativeLocation` **and** `RelativeRotation` from a world position), but no
   discrimination variant is authored for it and it must not be counted as
   discriminating power. Full audit in `notes.md` §0.
5. **`does_socket_exist` is refused as a read route.** The row's verification
   text does not name it, but it is the obvious API and it is broken for this
   purpose: `USkinnedMeshComponent::DoesSocketExist` delegates to
   `GetSocketBoneName`, which falls back to a **bone** lookup when no socket
   matches (`SkinnedMeshComponent.cpp:3709-3739`), so it returns `True` on a
   mesh with **zero sockets authored** for any bone name. This verifier uses
   `USkinnedAsset::FindSocket`, which has no such fallback. See anti-gaming
   note #1.

> **Note on the behavior-only rule (Hard Rule #2).** Like
> `t1-hero-blueprint-copy-with-flashlight` and `t0-sanity-bp-log-on-beginplay`,
> this task names the concrete deliverable asset paths and the three
> verifier-key names (`WeaponSocket`, `hand_r`, `Weapon`). That is the
> standard, precedented exception for asset-deliverable tasks whose whole point
> *is* producing specific named asset content — the names ARE the observable,
> and naming them lets the verifier load one asset directly instead of scanning
> content. Everything else in the prompt stays behavior-only: no class name, no
> component type name, and no editor operation name (the prompt says
> "attachment point", never "socket asset"; "non-animated part", never "static
> mesh component"; and it never says "add a socket", "Skeleton Tree",
> "Components panel" or "SCS").

## Primary concept

- `ps-components` — Components
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/components-in-unreal-engine)

The load-bearing capability is composing a new subobject into an **inherited**
component hierarchy at a **named** attachment point that the agent must first
author on a different asset. `characters`
(https://dev.epicgames.com/documentation/en-us/unreal-engine/characters-in-unreal-engine)
is the adjacent concept the inherited-mesh half exercises.

Recorded gap: `tools/coverage/concepts.csv` has **no** concept for skeletal-mesh
sockets or for skeleton assets (checked 2026-07-27 across `concept_id` and
`concept_name`), so the socket-authoring half of this row is filed under its
consumer, `ps-components`, rather than under a concept of its own.

## Prompt given to the agent

> This project ships a walking figure at
> `Content/Tasks/t2-weapon-held-in-right-hand/BP_EvalChar`. Its animated body
> is driven by `SKM_EvalChar` and the joint hierarchy `SK_EvalChar_Skeleton`,
> both in that same folder. The figure currently carries nothing.
>
> Prepare the figure to hold a weapon:
>
> 1. On the joint hierarchy the figure's animated body uses, add an attachment
>    point named exactly `WeaponSocket`, anchored to the right-hand joint
>    `hand_r` and sitting exactly on that joint — no positional offset and no
>    angular offset.
> 2. Give `BP_EvalChar` a new non-animated part named exactly `Weapon` that
>    displays the engine's basic cube shape (`/Engine/BasicShapes/Cube`).
> 3. Mount `Weapon` on the figure's animated body **at the `WeaponSocket`
>    attachment point**, so that once the figure is placed in a level and
>    animates, the cube rides in its right hand rather than sitting at the
>    figure's feet or floating at its origin.
>
> Everything you change must be compiled and saved. All of the content this
> task concerns lives under `Content/Tasks/t2-weapon-held-in-right-hand/`;
> nothing outside that folder may be modified.

## Workspace state pre-task

Substrate content that **exists** under
`Content/Tasks/t2-weapon-held-in-right-hand/` (committed, saved, and
agent-writable — `Content/Tasks/<task-id>/` is the `ThirdPerson` substrate's
agent-writable Content carve-out, `UE-projects/ThirdPerson/AGENT_WRITABLE.json`;
fairness isolation keeps this task's folder while hiding every other task's):

- `SK_EvalChar_Skeleton.uasset` — the joint hierarchy, a task-local duplicate
  of the stock mannequin's. It contains the right-hand joint `hand_r`. It
  carries **no** attachment points beyond whatever the stock hierarchy already
  ships, and in particular nothing named `WeaponSocket`.
- `SKM_EvalChar.uasset` — the animated body mesh, a task-local duplicate of the
  stock mannequin body, bound to `SK_EvalChar_Skeleton`. It carries no
  attachment points of its own.
- `BP_EvalChar.uasset` — a walking, player-controllable figure whose inherited
  animated body part renders `SKM_EvalChar`. It is compiled and saved, and it
  owns no part named `Weapon`.

Files that **do not exist** (the agent must produce the change):

- nothing new needs to be created as a file; all three deliverables are edits
  to the three assets above.

Out of scope / not needed:

- No C++ is required or expected. No level, no placed actor, no functional
  test: the whole deliverable is asset content. `Content/Maps/`, `Config/`,
  `Content/Characters/`, `Content/ThirdPerson/` and `Content/Input/` are
  deny-listed — the agent neither can nor needs to touch them, and the stock
  mannequin under `Content/Characters/` is deliberately **not** the asset this
  task is about.

## Verifier specification

Layer choice: this task grades via **L1 + L2I**. Nine of the ten graded
properties are static properties of saved `.uasset`s (does a named attachment
point exist, which joint is it anchored to, what transform does it carry, which
subobjects exist, what type and mesh one of them has, where it attaches), read
by verifier-owned editor-Python reflection over the submitted assets — not by
rendering, ticking, or a PIE world. L2 is deliberately **not** declared: there
is nothing to observe over time, and a fixture would need a map and a placed
actor this task has no use for.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64 Development"
        and "ThirdPerson Win64 Development" (short-circuits on first failure)
```

The submission is content-only, so L1 is a precondition (the project and its
Asset Registry must load cleanly), never a correctness signal.

### L2I — Structural assertion

The verifier-owned script
`tools/verify-single/introspect/weapon_held_in_right_hand.py` runs headless via
`UnrealEditor-Cmd -ExecutePythonScript=` under `-nullrhi`, and prints one
`CRAFTBENCH-INTROSPECT-JSON` verdict block. It emits **exactly 10 named checks
on every leg** (a constant denominator, so the per-check `tests_passed/tests_run`
the registry already records is comparable across submissions). PASS requires
all 10:

```text
weapon_socket_exists                    SKM_EvalChar resolves an attachment point
                                        named "WeaponSocket"
weapon_socket_on_hand_r                 that point's BoneName == "hand_r"
weapon_socket_offset_is_identity        its RelativeLocation and RelativeRotation
                                        are both zero (+/-1e-3)  [LOW DISCRIMINATION
                                        — asserts an engine default; see #4 above]
char_mesh_uses_task_skeletal_mesh       BP_EvalChar's inherited animated mesh still
                                        renders /Game/Tasks/<id>/SKM_EvalChar
char_has_weapon_component               a subobject named "Weapon" exists on
                                        BP_EvalChar
weapon_is_static_mesh_component         that subobject is a non-animated mesh part
weapon_shows_engine_cube                its mesh asset is /Engine/BasicShapes/Cube
weapon_attach_parent_is_character_mesh  its attach parent is the INHERITED animated
                                        body part: named "Mesh"/"CharacterMesh0" AND
                                        a skeletal mesh component AND inherited/native
                                        rather than authored by the submission
weapon_attach_socket_is_weapon_socket   on a constructed instance, that component
                                        reports AttachSocketName == "WeaponSocket"
char_bp_compiles_up_to_date             BP_EvalChar loads with an up-to-date compile
                                        status (BS_UpToDate / ...WithWarnings)
```

**Read routes** (every one answered from UE 5.8 engine source at
`<UE-root>/Engine/Source`; the Python-visibility rule is
`PropertyAccessUtil.cpp:425-433` — `CPF_Edit | CPF_BlueprintVisible |
CPF_BlueprintAssignable`):

- *the attachment point* — `USkinnedAsset::FindSocket` is a
  `UFUNCTION(BlueprintCallable)` (`SkinnedAsset.h:156-159`), `USkeletalMesh`
  overrides it (`SkeletalMesh.h:2658`), and `USkeletalMesh::FindSocketAndIndex`
  searches the **mesh's** own sockets first and then falls through to the
  **skeleton's** (`SkeletalMesh.cpp:5238-5266`). One call therefore accepts a
  point authored on either asset, which is the right acceptance set: both are
  legitimate ways to satisfy the prompt and both put the point on the figure.
  `USkeleton::Sockets` itself carries **no** reflection flag and is unreadable
  (plan §12.1); this script never touches it.
- *its fields* — `USkeletalMeshSocket::SocketName` / `BoneName` are
  `VisibleAnywhere + BlueprintReadOnly`; `RelativeLocation` / `RelativeRotation`
  are `EditAnywhere + BlueprintReadOnly` (`SkeletalMeshSocket.h:24-34`). All
  four are readable.
- *component walk* — `unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)`.
  It is an **engine** subsystem: `get_editor_subsystem` raises
  `TypeError: Cannot nativize`. Then
  `SubobjectDataBlueprintFunctionLibrary.get_data / get_variable_name /
  get_parent_handle / get_object / is_inherited_component / is_native_component`.
- *the Weapon's mesh* — `UStaticMeshComponent::StaticMesh` is
  `EditAnywhere + BlueprintReadOnly` (`StaticMeshComponent.h:132`).
- *the figure's mesh* — the `GetSkeletalMeshAsset` / `GetSkinnedAsset`
  `BlueprintPure` UFUNCTIONs (`SkeletalMeshComponent.h:374`,
  `SkinnedMeshComponent.h:1222`); the underlying `SkinnedAsset` member is
  private and the legacy `SkeletalMesh` member is deprecated.
- *attach parent* — `get_parent_handle` on the `Weapon` subobject's data. The
  name is necessary, never sufficient: the check additionally requires the
  parent's template to be a `SkeletalMeshComponent` **and** to report
  `IsInheritedComponent`/`IsNativeComponent`, which is what stops a
  submission-authored component merely *named* `Mesh` from satisfying
  anti-gaming note #3. The `AttachParent`/`AttachSocketName` UPROPERTIES are
  reflection-denied (`SceneComponent.h:107-113`, `UPROPERTY(ReplicatedUsing=…)`
  with no Edit/BlueprintVisible flag).

### The one check that needs a live world — `weapon_attach_socket_is_weapon_socket`

This is the single check in the task that is **not** a static asset read, and
the spec records it explicitly because the plan (§12.1) asks for it. For an
SCS-authored component the attachment *socket* lives on the SCS node, and it is
unreachable from Python at three independent levels:

1. `USCS_Node::AttachToName` is a bare `UPROPERTY()` (`SCS_Node.h:42-44`) — no
   `Edit`/`BlueprintVisible` flag, so reflection denies it;
2. `UBlueprint::SimpleConstructionScript` is also a bare `UPROPERTY()`
   (`Blueprint.h:536-538`), so the node graph cannot even be reached to try;
3. `FSubobjectData::GetSocketFName()` exists (`SubobjectData.h:181`) but has
   **no** wrapper in `USubobjectDataBlueprintFunctionLibrary`, so it is not a
   UFUNCTION and is invisible to Python.

And the component *template* is deliberately no help: `FSubobjectData::SetupAttachment`
writes `NAME_None` into the template's `AttachSocketName`
(`SubobjectData.cpp:672-692`). The value only materializes when
`USCS_Node::ExecuteNodeOnActor` runs `AttachToComponent(parent, rules, AttachToName)`
on a **constructed** actor.

So the check constructs the generated class **once, transiently**, reads
`USceneComponent::GetAttachSocketName()` (a `UFUNCTION(BlueprintCallable)`,
`SceneComponent.h:703-705`) off the constructed `Weapon`, and destroys the actor
in a `finally`. This is legal for an L2I script: a live editor world is
guaranteed, because `EditorPythonExecuter` refuses to start an
`-ExecutePythonScript` payload until `GWorld`, `GEngine` and `GEditor` are up
and the asset registry has settled (plan §12.1). The world is never saved by the
verifier, so the introspect layer's READ-ONLY rule is honoured with respect to
every asset and package. The spawn is attempted with `bTransient=true` first
(`EditorActorSubsystem.h:227`) and falls back to the 3-argument spelling.

**This is the one route in the task that engine source cannot fully settle**, and
`notes.md` §5 carries it as the calibration item: it is proven from source that
no static route exists and that a world is available, but the spawn itself has
not been executed under `-nullrhi -ExecutePythonScript`. If it turns out to be
unreachable, the honest fallback is to **delete this check and re-declare the
task at 9 checks**, relabelling it for the weaker property it then tests
("mounted on the animated body", not "mounted at the named point") — and to
delete the `weapon-on-mesh-no-socket` variant with it, since that variant exists
only to exercise this check. Do **not** let the check silently pass.

Also note: `AttachToComponent` performs **no** socket-existence validation
(`SceneComponent.cpp:2311-2440`), so `weapon_socket_exists` and
`weapon_attach_socket_is_weapon_socket` are genuinely independent — a submission
can satisfy either without the other, which is what makes the
`bone-name-instead-of-socket` variant land on a distinct token.

**Identity is by pre-declared content path and pre-declared name, never by
class.** The three asset paths and the three names (`WeaponSocket`, `hand_r`,
`Weapon`) are fixed by the spec and stated in the prompt; the agent may reach
the outcome through the editor, through editor-Python, or by rebuilding
`BP_EvalChar` from scratch, and none of that is penalized.

**Why `saved` is not a separate check.** The source row asks for saved,
non-dirty assets. Dirtiness is not observable to this layer and does not need to
be: the runner grades a file overlay materialized onto a clean substrate, so
unsaved editor state never reaches the grader at all — an unsaved edit presents
as the *baseline* bytes and fails the content checks. The compile half is
asserted directly off the freshly loaded asset.

**Score granularity.** `registry.py:340-346` sets `tests_run`/`tests_passed`
from the per-check counts, so `report.json` already carries `x/10` for this
task. That number is **reported, not gating** — `overall` stays
`all(status == "pass")` (plan §3.2).

## Reference solution metadata

- LOC range: **0** lines of code. The deliverable is three edited `.uasset`s
  (one of which — the skeleton — may be untouched if the agent authors the
  attachment point on the mesh instead).
- Files touched: 0 created, 2-3 modified
  (`Content/Tasks/t2-weapon-held-in-right-hand/{SK_EvalChar_Skeleton,SKM_EvalChar,BP_EvalChar}.uasset`).
- Senior-dev hours: 0.3-0.6 (one attachment point on a joint, one part added to
  a Blueprint with a mesh assigned, one attach-to-named-point edit, compile and
  save — plus confirming the point really landed on `hand_r` and not on the
  selected joint).

## Anti-gaming notes

1. **Attachment point never authored — the joint name used instead.** *Failure
   mode*: the agent skips the first deliverable entirely and mounts `Weapon`
   directly on the joint `hand_r`, which the engine accepts as an attachment
   target and which *looks* correct in the viewport. A verifier that reached for
   the obvious API would be fooled: `does_socket_exist("hand_r")` returns `True`
   on a mesh with zero sockets, because `DoesSocketExist` delegates to
   `GetSocketBoneName`, which falls back to a bone lookup
   (`SkinnedMeshComponent.cpp:3709-3739`). *Defense*: this verifier never calls
   `does_socket_exist`. `weapon_socket_exists` uses `FindSocket`, which searches
   only real sockets (mesh, then skeleton) and has no bone fallback
   (`WEAPONSOCKET_NOT_FOUND`), and `weapon_attach_socket_is_weapon_socket`
   independently reports the constructed component's actual socket name
   (`WEAPON_ATTACH_SOCKET_WRONG socket=hand_r`), so the shortcut is named
   twice, by two unrelated reads.
2. **Attachment point authored on the wrong joint.** *Failure mode*: the agent
   creates `WeaponSocket` on whatever joint happened to be selected — `root`,
   `pelvis`, or the *left* hand — so the cube is present, named right, mounted
   right, and in the wrong place. *Defense*: `weapon_socket_on_hand_r` reads the
   point's `BoneName` and requires `hand_r` exactly
   (`WEAPONSOCKET_BONE_WRONG bone=`). Name-and-existence alone would pass this
   submission.
3. **Part hung wherever the editor put it.** *Failure mode*: a newly added part
   parents to whatever is selected, which in a character Blueprint is normally
   the capsule root — so `Weapon` exists, shows a cube, and never moves with the
   hand. *Defense*: `weapon_attach_parent_is_character_mesh` resolves the
   subobject's *parent handle* and requires the INHERITED animated mesh
   (`WEAPON_ATTACH_PARENT_WRONG parent=`). The name match alone would be gamed by
   any component the agent simply *called* `Mesh`, so the check also requires
   that parent to be a skeletal mesh component **and** to be inherited/native
   rather than authored by the submission — a component added to
   `BP_EvalChar`'s own construction script is neither, whatever it is named.
4. **Mounted on the body but not at the point.** *Failure mode*: the agent
   authors the attachment point correctly and parents `Weapon` under the
   animated mesh, but never binds it to the point — so the cube tracks the
   mesh's origin at the figure's feet instead of the hand. Every static check
   passes. *Defense*: `weapon_attach_socket_is_weapon_socket` constructs the
   class once and reads the real `AttachSocketName`
   (`WEAPON_ATTACH_SOCKET_WRONG socket=None`), which is the only observable that
   distinguishes "under the mesh" from "at the named point".
5. **Part present but empty, or the figure re-pointed at other content.**
   *Failure mode*: the agent adds a correctly named, correctly attached part and
   never assigns a mesh to it (nothing is visible), or authors the attachment
   point on the graded asset and then swaps the figure's animated body to a
   different mesh so the point is not on the thing that renders. *Defense*:
   `weapon_is_static_mesh_component` (`WEAPON_NOT_STATIC_MESH class=`) and
   `weapon_shows_engine_cube` (`WEAPON_MESH_NOT_CUBE mesh=`) require a real
   non-animated part showing `/Engine/BasicShapes/Cube`, and
   `char_mesh_uses_task_skeletal_mesh` (`CHAR_MESH_ASSET_WRONG asset=`) pins the
   figure to the asset the socket checks actually read. Prose claiming success
   cannot satisfy any of them — the verdict is read only from the submitted
   bytes.

## Hidden invariants

- The three socket checks read `SKM_EvalChar` **directly by path**, not by
  following `BP_EvalChar`'s mesh reference. That ordering is deliberate: it
  means an agent cannot satisfy them by pointing the figure at some other
  already-socketed mesh, and the complementary
  `char_mesh_uses_task_skeletal_mesh` closes the reverse hole (socket authored
  on the graded asset, figure pointed elsewhere). The two together are what make
  "the attachment point is on the thing the figure actually renders" a graded
  fact rather than an assumption.
- `weapon_socket_offset_is_identity` is scored but is **not** counted as
  discriminating power anywhere in this task: it asserts an engine default
  (divergence #4). No variant exercises it and no anti-gaming note cites it.
  Anyone reading `9/10` on this task should check *which* nine.
- The check denominator is fixed at 10 on every leg, including the empty
  submission and including a submission that deleted `BP_EvalChar`. A submission
  cannot improve its reported `tests_passed/tests_run` by making checks
  unreachable — the crash-shaped "fewer checks ran, so the ratio looks better"
  path is closed by construction.
- Because the baseline ships all three assets, the empty submission is **not**
  a 0/10: `char_mesh_uses_task_skeletal_mesh` and `char_bp_compiles_up_to_date`
  pass on the untouched baseline (`2/10`). That is correct, and it is why the
  empty leg's named substring is a socket token rather than an asset-missing
  one.

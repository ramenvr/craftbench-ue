# t2-weapon-held-in-right-hand — implementor notes + asset build spec

Text half authored 2026-07-27 (no editor, no build, no `.uasset` touched).
**The binary half is not done.** (2026-07-29: now it is — see the §2
"what actually shipped" note and the §5 calibration record.) This file is the
contract the editor track builds against: everything below is stated
property-by-property so the assets can be authored without re-deriving
anything from the spec.

## Provenance

- Source: an earlier internal task list (not shipped) — a socket-and-
  attachment row that was never implemented there. Its Issues note: "Need a
  bunch of starting assets".
- Disposition: the import plan originally declared the row "has no static
  route" and prescribed a transient spawn for the *socket* read; that was
  later **retracted** from engine source. This task follows the retraction:
  the socket read is static (`FindSocket`), and a world is needed for exactly
  one check (§5 below).
- Substrate `ThirdPerson` is the owner's choice for the imported set, and here it
  is also load-bearing: the row's start state is the UE5 mannequin, which only
  this substrate ships. Cost to record: a ThirdPerson L1 leg measured **172 s
  vs 131 s** on `CraftBenchTemplate` because there is no warm slot for it on
  this box (plan §6).

---

## 0. DEAD-GATE AUDIT of the source row (mandatory pass; plan §12.6)

Every numeric and every "must equal" the source row's Verification cell asserts,
checked against the UE 5.8 engine default in `<UE-root>/Engine/Source`.

| source-row assertion | engine default | verdict |
|---|---|---|
| socket `RelativeLocation` is identity | `FVector RelativeLocation = FVector::ZeroVector;` — `Engine/Classes/Engine/SkeletalMeshSocket.h:30-31` | **DEAD GATE.** A newly created socket already satisfies it |
| socket `RelativeRotation` is identity | `FRotator RelativeRotation = FRotator::ZeroRotator;` — `SkeletalMeshSocket.h:33-34` | **DEAD GATE.** Same |
| socket `SocketName == "WeaponSocket"` | ctor leaves `SocketName` as `NAME_None`; the editor names a new socket `<Bone>Socket` (e.g. `hand_rSocket`), not `WeaponSocket` | LIVE |
| socket `BoneName == "hand_r"` | `NAME_None` by default; the editor sets it to the *selected* joint | LIVE — and it is the row's sharpest check |
| `Weapon` is a `StaticMeshComponent` | n/a — the component does not exist in the baseline | LIVE |
| `Weapon`'s mesh is the engine cube | `UStaticMeshComponent::StaticMesh` defaults to **null** (`StaticMeshComponent.h:131-133`, no initializer) | LIVE — "null" is a real, common failure |
| attach parent is the `Mesh` component | a new SCS part parents to the current selection, normally the capsule root | LIVE |
| `AttachSocketName == "WeaponSocket"` | `NAME_None`, and `FSubobjectData::SetupAttachment` actively writes `NAME_None` into the template (`SubobjectData.cpp:672-692`) | LIVE |

Two of the row's eight assertions are dead. They are **not** dropped (see the
spec's divergence #4) but they are folded into a single
`weapon_socket_offset_is_identity` check that is labelled low-discrimination in
the spec, in the MATRIX and here, and no discrimination variant is authored for
it. The one authoring route that *does* violate it is
`USkeletalMeshSocket::InitializeSocketFromLocation`, which writes `BoneName`,
`RelativeLocation` and `RelativeRotation` together from a world position
(`SkeletalMeshSocket.h:53-55`).

A ninth would-be assertion, `does_socket_exist`, is **refused outright** — it is
the row's obvious API and it grades nothing (`SkinnedMeshComponent.cpp:3709-3739`
falls back to a bone lookup). It is written up as anti-gaming note #1 instead of
being used as a check.

---

## 1. BASELINE assets (ship in the substrate, committed, agent-writable)

All three live at
`UE-projects/ThirdPerson/Content/Tasks/t2-weapon-held-in-right-hand/`, i.e.
content paths `/Game/Tasks/t2-weapon-held-in-right-hand/<name>`.

### Why duplicates at all

`Content/Characters/` is in the ThirdPerson substrate's **deny** list
(`UE-projects/ThirdPerson/AGENT_WRITABLE.json`). Adding the attachment point to
the stock `/Game/Characters/Mannequins/Meshes/SK_Mannequin` would put a denied
path in the submission and score **SANDBOX-REJECT exit 4** — a wrong-reason
failure that looks like an agent error. The whole rig therefore has to be
duplicated into the writable carve-out.

### Correction to the source row before you start

Read out of the package headers in this checkout on 2026-07-27:

| stock asset | actual class | references |
|---|---|---|
| `/Game/Characters/Mannequins/Meshes/SK_Mannequin` | **`Skeleton`** | — |
| `/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple` | `SkeletalMesh` | Skeleton `SK_Mannequin`, PhysicsAsset `/Game/Characters/Mannequins/Rigs/PA_Mannequin` |
| `/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple` | `SkeletalMesh` | same pair |

So the source row's "the mannequin `SK_Mannequin`" is the **skeleton**, not the mesh.
Bone `hand_r` is present in `SK_Mannequin` (verified by name-table scan; `root`,
`pelvis`, `hand_l`, `hand_r`, `ik_hand_r` all present).

### 1a. `SK_EvalChar_Skeleton` — the joint hierarchy

| property | required value | why the verifier cares |
|---|---|---|
| asset type | `Skeleton` | — |
| source | `EditorAssetLibrary.duplicate_asset("/Game/Characters/Mannequins/Meshes/SK_Mannequin", "/Game/Tasks/t2-weapon-held-in-right-hand/SK_EvalChar_Skeleton")` | — |
| bone `hand_r` | present (inherited from the duplicate) | `weapon_socket_on_hand_r` compares against the literal string `hand_r`; if the duplicate ever renames bones the task breaks |
| sockets | **none named `WeaponSocket`** | `weapon_socket_exists` must FAIL on the baseline. Check the duplicate: the stock UE5 mannequin skeleton ships a small number of sockets — **enumerate them and confirm none is called `WeaponSocket`** before committing |
| saved | yes | — |

### 1b. `SKM_EvalChar` — the animated body mesh

| property | required value | why the verifier cares |
|---|---|---|
| asset type | `SkeletalMesh` | `weapon_socket_exists` calls `find_socket` on **this** asset |
| source | duplicate of `/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple` | — |
| `Skeleton` | **re-pointed to `/Game/Tasks/t2-weapon-held-in-right-hand/SK_EvalChar_Skeleton`** — `skm.set_editor_property("skeleton", dup_skel)`. The property is `VisibleAnywhere` with a `BlueprintSetter` (`SkeletalMesh.h:734-737`), so this is a supported write | **load-bearing**: if the duplicate still points at the stock `SK_Mannequin`, an agent that authors the point "on the skeleton" writes a denied path and gets exit 4 |
| `PhysicsAsset` | leave pointing at the stock `/Game/Characters/Mannequins/Rigs/PA_Mannequin` | not graded; a read-only reference into a deny-listed folder is fine — `deny` governs submission WRITES, not references |
| materials | leave pointing at the stock mannequin materials | not graded, same reasoning |
| sockets | **none named `WeaponSocket`** | same as 1a |
| saved | yes | — |

### 1c. `BP_EvalChar` — the figure

Name kept verbatim from the source row.

| property | required value | why the verifier cares |
|---|---|---|
| asset type | Blueprint Class | — |
| parent class | engine `Character` | supplies the inherited `Mesh` / `CharacterMesh0` skeletal mesh component that `weapon_attach_parent_is_character_mesh` requires to be **inherited or native**. Any `Character` subclass also works, but ship plain `Character` |
| inherited `Mesh` component: `SkeletalMeshAsset` | `/Game/Tasks/t2-weapon-held-in-right-hand/SKM_EvalChar` | `char_mesh_uses_task_skeletal_mesh` compares `get_skeletal_mesh_asset().get_path_name().split(".")[0]` against that exact string |
| inherited `Mesh` transform | the stock third-person values (`RelativeLocation (0,0,-89)`, `RelativeRotation (0,0,-90)`) so the figure stands in its capsule | **not graded** — cosmetic, but it makes any human inspection legible |
| AnimClass on `Mesh` | leave unset, or point at the stock `ABP_Manny` | **not graded.** If you set it, note that `ABP_Manny` lives under the deny-listed `Content/Characters/` — again fine as a *reference* |
| components named `Weapon` | **none** | `char_has_weapon_component` must FAIL on the baseline |
| compile / save | compiled clean, saved, not dirty | `char_bp_compiles_up_to_date` must PASS on the baseline (the empty leg scores `2/10`, and this is one of the two) |

Also create the folder itself:
`Content/Tasks/t2-weapon-held-in-right-hand/` must exist in the substrate.

### Three work-loss hazards for whoever authors these (plan §9.7)

- Fairness isolation physically **moves** an untracked `Content/Tasks/<id>/` out
  of the substrate the next time a *different* task is driven. Commit the
  baselines as soon as they exist.
- `run_task` grades from **git HEAD**, so an uncommitted baseline is invisible
  to a normal grade (use `--substrate-from-live` / `cb discriminate --wip` while
  iterating).
- `_CB_EDITOR_MARKER = "craftbench"` means an in-repo authoring editor is
  classified CraftBench-owned: `cb down` / `cb eval` / `cb view` will kill it
  unwarned. And launch via `launch_unreal_project` (its argv carries
  `-unattended`, which gates Live Coding OFF); an attended editor makes every
  UBT build on this box fail exit 6 in ~13 s.

---

## 2. REFERENCE solution

**Paths on disk**, under
`tasks/bp/t2-weapon-held-in-right-hand/reference/Content/Tasks/t2-weapon-held-in-right-hand/`:

- `SK_EvalChar_Skeleton.uasset` **or** `SKM_EvalChar.uasset` (whichever asset
  the attachment point was authored on — resolved 2026-07-29: the MESH; see
  the dated note below), and
- `BP_EvalChar.uasset`.

`apply_submission` is a copy-only overlay with no wipe, so any asset the
reference does **not** carry falls through from the substrate baseline
untouched. Ship the smallest set that expresses the change.

| step | required end state | check it satisfies |
|---|---|---|
| 1 | a socket named exactly `WeaponSocket` exists, reachable from `SKM_EvalChar.find_socket("WeaponSocket")`. Authoring it **on the skeleton** (`SK_EvalChar_Skeleton`) is the canonical route and is what the prompt describes; authoring it on the mesh also passes, because `USkeletalMesh::FindSocketAndIndex` searches mesh sockets and then falls through to the skeleton's (`SkeletalMesh.cpp:5238-5266`). Pick the skeleton for the reference | `weapon_socket_exists` |
| 2 | that socket's `BoneName` is exactly `hand_r` | `weapon_socket_on_hand_r` |
| 3 | its `RelativeLocation` and `RelativeRotation` are both zero (they are by default — do not touch them) | `weapon_socket_offset_is_identity` |
| 4 | `BP_EvalChar`'s inherited `Mesh` still renders `SKM_EvalChar` | `char_mesh_uses_task_skeletal_mesh` |
| 5 | new `StaticMeshComponent`, **variable name exactly `Weapon`** (case-sensitive) | `char_has_weapon_component`, `weapon_is_static_mesh_component` |
| 6 | `Weapon.StaticMesh` = `/Engine/BasicShapes/Cube` | `weapon_shows_engine_cube` |
| 7 | `Weapon`'s SCS parent is the **inherited** `Mesh` (native name `CharacterMesh0`), not the capsule root and not a new component of your own | `weapon_attach_parent_is_character_mesh` |
| 8 | `Weapon`'s SCS node `AttachToName` is `WeaponSocket` — in the editor, drag `Weapon` onto the socket under `Mesh` in the Components panel, or set the socket field in its details | `weapon_attach_socket_is_weapon_socket` |
| 9 | `BP_EvalChar` compiled clean and saved | `char_bp_compiles_up_to_date` |

Expected reference verdict: **L2I `10/10`, overall PASS.**

### 2026-07-29 — what actually shipped: the socket lives on the MESH

The canonical route in step 1 ("pick the skeleton") turned out to be **closed
to stock UE 5.8 Python**: nothing scriptable appends to `USkeleton::Sockets`,
while `USkeletalMesh.AddSocket` is `BlueprintCallable`. The attachment point
was therefore authored as a **mesh-level socket on `SKM_EvalChar`** — the
alternative step 1 itself already sanctions ("authoring it on the mesh also
passes", via the `FindSocketAndIndex` mesh-then-skeleton fallthrough). Same
graded surface; only the canonical-route *preference* is overridden, by
tooling reach rather than by choice. Exact call chain: §5, authoring route
facts.

Consequences for what ships where:

- The reference carries exactly **two** files: `SKM_EvalChar.uasset` +
  `BP_EvalChar.uasset`. No skeleton asset ships — `apply_submission` is
  copy-only (above), so `SK_EvalChar_Skeleton` falls through from the
  substrate baseline untouched.
- Four of the five variant `README-MISSING-ASSETS.md`s (`socket-on-wrong-bone`,
  `weapon-on-mesh-no-socket`, `weapon-on-capsule-root`,
  `weapon-without-cube-mesh`) list `SK_EvalChar_Skeleton.uasset` under
  "Asset(s) to author here". Those lists are satisfied by `SKM_EvalChar.uasset`
  instead — same fallthrough, same checks. In particular the
  `socket-on-wrong-bone` deviation (the socket's `BoneName`) lives in that
  variant's `SKM_EvalChar.uasset`, not in any skeleton asset.

### Two authoring gotchas to check by hand

- **Step 8 is the one that silently no-ops.** Setting the *component template's*
  socket field is not the same edit as setting the SCS node's `AttachToName`;
  `FSubobjectData::SetupAttachment` will actively clear the template's
  `AttachSocketName` to `NAME_None` (`SubobjectData.cpp:672-692`). After saving,
  re-open the Blueprint and confirm `Weapon` is nested under the socket in the
  Components tree, not merely under `Mesh`.
- **Step 1 vs the duplicate's own sockets.** If the stock mannequin skeleton
  already ships a socket on `hand_r` under some other name, that is harmless —
  the check keys on the *name* `WeaponSocket`. But if it ships one *named*
  `WeaponSocket`, the baseline is already passing check 1 and the task is void.
  Enumerate and confirm (§1a).

---

## 3. Discrimination variants

Five variant overlays, one per anti-gaming note, specified in
`discrimination/MATRIX.md` and in each variant folder's
`README-MISSING-ASSETS.md`. Each is the reference with exactly ONE deviation, so
the matrix can attribute the FAIL to one gate.

---

## 4. Pre-flight before the first graded leg

1. **`tools/verify-single/tests/test_verdict_taxonomy.py:79`**
   (`test_every_shipping_spec_declares_only_landable_gating_layers`) globs
   `tasks/*/*/task.md` and asserts every spec's layers are exactly
   `("L1","L2")`. It already fails because of the pilot; this spec is the second
   task in the same boat. Per plan §9.1 the fix is to replace the equality with
   a landability assertion **and** demonstrate that an `L1+L2I` task really does
   produce an `L2I` key in `layers_out`. Deliberately **not** done here — it is
   a verdict-taxonomy change and wants its own review, and it is shared work
   with the pilot, not per-task work.
2. **Registry bookkeeping (plan §9.2 / §12.3).** `cb lint --all` runs
   `inventory.py`, which needs a `tasks/CATALOG.md` row for this id plus the six
   hard-coded task-count claims bumped (the repo conventions, `tasks/CATALOG.md` x2,
   the verifier-building skill (under `.claude/`, not shipped) x2,
   the task-authoring skill (under `.claude/`, not shipped)). **7, not 8** — this task
   ships no `.umap`, so `inventory-maps-count` does not fire. The cost is
   *shared* with any other task landing in the same reconciliation pass; do them
   in one pass (`cb lint` names each stale count) rather than stacking
   drift. Not done here, because doing it per-task in parallel branches is how
   the counts get double-bumped.
3. **`registry.py:342` turns an L2I `error` into a graded FAIL** (plan §13.2).
   With two L2I tasks now on the branch, a typo in a verifier-owned grader
   scores the *model*. Shared defect; flagged, not fixed here.

## 5. Calibration record

- [x] `SK_EvalChar_Skeleton.uasset` + `SKM_EvalChar.uasset` + `BP_EvalChar.uasset`
      authored and committed; the duplicated mesh confirmed to point at the
      duplicated skeleton.
      **2026-07-29 — all three baseline assets authored** (interactive MCP
      editor session). "Committed" is this row's landing commit, still pending
      as of this entry — every grade below therefore ran
      `cb discriminate --wip` against the live tree. The mesh-to-skeleton
      re-point held: the baseline decodes to 2/10, not the 1/10 of a failed
      re-point (next box).
- [x] Baseline verdict confirmed **2/10** (only `char_mesh_uses_task_skeletal_mesh`
      and `char_bp_compiles_up_to_date` green). A baseline scoring 3/10 means the
      stock skeleton already ships a `WeaponSocket`; a baseline scoring 1/10
      means the mesh re-point in §1b did not take.
      **2026-07-29 — exactly 2/10, twice**: once on initial authoring, once
      post-reset. Neither failure decode fired.
- [x] Reference authored; L2I reads **10/10**.
      **2026-07-29 — 10/10.** The live-world check's detail is in the next box.
- [x] **THE calibration item — `weapon_attach_socket_is_weapon_socket` under
      `-nullrhi`.** Everything else in this task is settled from engine source;
      this one is not. What is *proven*: no static route exists (three
      independent reflection denials, spec §"The one check that needs a live
      world"), and a live editor world is guaranteed under
      `-ExecutePythonScript` (`EditorPythonExecuter`, plan §12.1). What is
      *unproven*: that `EditorActorSubsystem.spawn_actor_from_class` +
      `get_components_by_class` + `get_attach_socket_name()` actually round-trip
      the SCS socket name under `-nullrhi` in this harness. Plan §10.1 records
      the spawn route as confirmed on a *live headless* editor, which is
      encouraging but is not the same launch. **Run the reference first**: if it
      reads 9/10 with `WEAPON_SPAWN_*` in the detail, the route is dead.
      Fallback, in preference order:
      (a) fix the call shape (the 4-arg `bTransient` overload is tried first,
          then the 3-arg spelling — check which one the log names);
      (b) drop the check, re-declare the task at **9** checks, delete the
          `weapon-on-mesh-no-socket` variant, and relabel the task for the
          weaker property ("mounted on the animated body", not "at the named
          point") in the spec, the MATRIX and anti-gaming note #4. Do **not**
          leave a check that cannot fail.
      **2026-07-29 — SETTLED: the spawn route works.** The reference's
      transient-spawn read came back `WEAPON_ATTACH_SOCKET_OK
      socket=WeaponSocket` inside the 10/10. Launch-shape caveat, recorded
      because the launch WAS the open question: authoring ran in an interactive
      MCP editor session, so that first green read is from a live attended
      editor, not the harness launch — but the `-nullrhi` variant of the same
      read then passed inside `cb discriminate`'s legs, which is the harness
      launch. And the check is ALIVE, not merely green: the
      `weapon-on-mesh-no-socket` oracle leg read **9/10** failing ONLY
      `weapon_attach_socket_is_weapon_socket`, with `socket=None` in the
      detail. Neither fallback fired — no call-shape fix (a), no
      re-declaration to 9 checks (b).
- [x] Discrimination executed: reference PASS, empty + 5 variants FAIL, each via
      its MATRIX substring.
      **2026-07-29 — `cb discriminate --wip` = YES, 7/7 legs.**
- [ ] **Measured L2I leg wall-clock recorded here**, alongside the pilot's — the
      "does an L2I leg cost ~131 s like an L2 leg?" question (plan §1/§6) is
      still unanswered, and this task's transient spawn is the first L2I check
      that does real work in the world. Still OPEN as of the 2026-07-29
      calibration pass — no number recorded yet.

### Authoring route facts, 2026-07-29 (recorded so nobody re-derives them)

How the assets above were actually produced, including the two places where
the text of this file prescribes a route the 5.8 Python surface refuses
(§1b's `set_editor_property` spelling; §2's socket-on-the-skeleton route):

- **Skeleton re-point (§1b): plain attribute assignment.** `skm.skeleton = skel`
  is the write that goes through. `set_skeleton()` does not exist on the 5.8
  Python `SkeletalMesh`, and `skm.set_editor_property("skeleton", ...)` — the
  spelling §1b prescribes — **refuses**. §1b's conclusion stands (the write is
  supported, and it took — see the 2/10 decode above); only its spelling is
  superseded.
- **Socket creation (§2, mesh route): four-call chain.**
  `new_object(SkeletalMeshSocket, outer=mesh)`, then `add_socket`, then
  `set_socket_parent` to put it on `hand_r`, then
  `SkeletalMeshEditorSubsystem.rename_socket` to `WeaponSocket`. Nothing
  scriptable appends to `USkeleton::Sockets`, which is why the socket lives on
  the mesh at all (§2's 2026-07-29 note).
- **SCS `AttachToName` (§2 step 8): no stock-Python route.** It was set (the
  reference) and cleared (variant authoring) via the Aura `bp_agent` MCP lane.
  Consistent with the §2 gotcha: this is the field
  `FSubobjectData::SetupAttachment` actively clears, and stock Python never
  reaches it.

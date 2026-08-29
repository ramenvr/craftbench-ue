# Discrimination matrix — t2-weapon-held-in-right-hand

The self-validation oracle: the reference solution must PASS and every gaming
variant + the empty leg must FAIL **at the predicted check, via the named
substring**. A wrong-reason FAIL (L1 build failure, a different check, a
`0`-check/`error` L2I verdict, SANDBOX-REJECT exit 4) means the verifier is NOT
discriminated — fix it, or relabel the task for the weaker property it actually
tests.

> **STATUS: RUN AND DISCRIMINATED — 2026-07-29.** `cb discriminate --wip` =
> YES **7/7 legs**: reference PASS (L2I 10/10) and all six negative legs FAIL
> credited at their named assertions. Every `.uasset` this file once listed as
> missing is authored and committed. Full record + citations in **Status** at
> the bottom of this file.

## Three parser traps this matrix is written against

- **ONE parseable row per label.** `discriminate.parse_matrix` returns
  `Dict[label -> MatrixRow]` (`discriminate.py:227`), so a *second* table that
  repeats a variant label silently **overwrites** the first — and because a
  table without a "substring"/"message" header column yields an empty message,
  the overwrite lands a blank substring tuple and the leg can never be
  credited. This file therefore has **exactly one table with variant rows**;
  every secondary/derived observation lives in prose below it, where no `|`
  row can re-register a label. (The defect that motivated this rule blanked 4
  of 6 negative legs on the pilot, 2026-07-27.)
- **Every "Expected substring" cell is a backtick-wrapped literal that
  CONTAINS A SPACE.** `_extract_substrings` (`discriminate.py:195-218`) keeps a
  backticked span only when it is "substantive" — contains a space or one of
  `(),.=` — otherwise it falls through to a last-resort branch that returns the
  cell *with its backticks still attached*, which can never match log text. A
  bare `SCREAMING_SNAKE` check id has neither a space nor that punctuation, so
  it hits the broken branch. Pairing the token with the fixed prefix of the
  text that follows it in the script (`... /Game/Tasks/`, `... bone=`,
  `... parent=`, `... socket=None`, `... socket=hand_r`, `... mesh=`) makes the
  cell substantive **and** keeps it a verbatim substring of the printed
  `detail`. This works whether or not the last-resort branch is ever fixed in
  code.
- **The "Expected substring" header is the only column `parse_matrix` reads for
  substrings** (it picks the first header cell containing "message" or
  "substring"). The "Also fails" column deliberately does NOT contain either
  word, so its backticked tokens are never harvested as expectations.

## Two L2I traps this matrix is written against

- **The substring is matched against the raw `detail` string as printed inside
  the `CRAFTBENCH-INTROSPECT-JSON` block** — not against the layer's
  `<script>:<check>: FAIL - ...` note rendering. Every "Expected substring"
  cell below is a literal token emitted by
  `tools/verify-single/introspect/weapon_held_in_right_hand.py`.
- **Exactly ONE introspect script per task.** `registry.py` keeps only
  `li_last_log`, so a substring printed by an *earlier* script could never be
  credited. This task declares one script, and must keep declaring one.

**ASCII rule:** every expected substring is ASCII-only. The UE log's UTF-8
bytes are read back as cp1252, so a non-ASCII character in a detail string
becomes mojibake and the grep misses — a correct FAIL then misclassifies as
wrong-reason (live incident, `t2-homing-projectile`, 2026-07-21). The whole
introspect script is ASCII by construction.

**Error tokens are distinct from failure tokens.** Every exception path in the
script emits a `*_READ_ERROR` / `*_PROBE_ERROR` / `*_WALK_ERROR` /
`*_FIND_ERROR` / `*_UNAVAILABLE` / `*_FAILED` / `*_ABORTED` token that appears
in **no** matrix row. So a broken UE API name — including a dead transient
spawn — can never be credited as a variant's named failure; it shows up as an
uncredited FAIL, which is the signal you want. Asserted by
`tools/verify-single/tests/test_introspect_weapon_socket.py::TestErrorTokensAreDisjointFromMatrix`.

## Layout (folder-local; agent-writable prefixes only — a stray root file -> SANDBOX-REJECT exit 4)

- `../reference/Content/Tasks/t2-weapon-held-in-right-hand/…` — the one correct
  solution. The `ThirdPerson` substrate's agent-writable Content carve-out is
  `Content/Tasks/`, so the overlay mirrors that path exactly, including the
  per-task segment.
- `<variant>/Content/Tasks/t2-weapon-held-in-right-hand/…` — one dir per
  anti-gaming note, sibling to this MATRIX.md.
- empty leg — run IMPLICITLY by `cb discriminate` (it creates a throwaway empty
  dir; nothing to author). Its row documents the expected first-gate failure.

Note the asymmetry that makes the empty leg meaningful here: the substrate
ships all three baseline assets, so an empty submission still has a loadable,
compiled `BP_EvalChar` rendering the task's own mesh. Two checks therefore PASS
on the empty leg (`2/10`), which is correct — the figure really is intact, it
just carries nothing.

## Matrix

**This is the only table in this file that carries variant rows.** Do not add a
second one — see the first parser trap above.

| Submission | Overall | Fails at (check id) | Expected substring | Also fails (recorded, not matched) | Anti-gaming note |
|---|---|---|---|---|---|
| `../reference` | PASS | — | all 10 checks green (10/10) | — | — |
| empty | FAIL | `weapon_socket_exists` | `WEAPONSOCKET_NOT_FOUND /Game/Tasks/` | the other 2 socket checks fan out on the same root cause, and all 5 weapon checks fail on `WEAPON_COMPONENT_MISSING names=`; the 2 baseline checks PASS (`2/10`) | #1 / FR-017 |
| `socket-on-wrong-bone/` | FAIL | `weapon_socket_on_hand_r` | `WEAPONSOCKET_BONE_WRONG bone=` | — | #2 point on the wrong joint |
| `weapon-on-capsule-root/` | FAIL | `weapon_attach_parent_is_character_mesh` | `WEAPON_ATTACH_PARENT_WRONG parent=` | `weapon_attach_socket_is_weapon_socket` | #3 part hung wherever the editor put it |
| `weapon-on-mesh-no-socket/` | FAIL | `weapon_attach_socket_is_weapon_socket` | `WEAPON_ATTACH_SOCKET_WRONG socket=None` | — | #4 mounted on the body, not at the point |
| `bone-name-instead-of-socket/` | FAIL | `weapon_attach_socket_is_weapon_socket` | `WEAPON_ATTACH_SOCKET_WRONG socket=hand_r` | all 3 socket checks | #1 joint name used instead of an attachment point |
| `weapon-without-cube-mesh/` | FAIL | `weapon_shows_engine_cube` | `WEAPON_MESH_NOT_CUBE mesh=` | — | #5 part present but empty |

Why each "Also fails" entry is expected and does **not** make the
discrimination muddy (prose on purpose — a table here would re-register the
labels and blank their substrings):

- empty also fails everything except `char_mesh_uses_task_skeletal_mesh` and
  `char_bp_compiles_up_to_date`, which pass because the baseline really is
  intact. `2/10` is the expected empty score and is worth asserting: a `0/10`
  empty leg means the baseline assets are missing or broken, not that the
  submission is.
- `weapon-on-capsule-root/` also fails
  `weapon_attach_socket_is_weapon_socket` (`WEAPON_ATTACH_SOCKET_WRONG socket=None`):
  a part parented to the capsule carries no socket name either. Two independent
  checks catching one defect is deliberate — the primary token is the
  attach-parent one because that is the fact the variant actually deviates on.
- `bone-name-instead-of-socket/` also fails all three socket checks
  (`WEAPONSOCKET_NOT_FOUND /Game/Tasks/`), because it never authors the
  attachment point at all. Its **primary** token is deliberately the
  constructed-instance one (`socket=hand_r`), because that is what distinguishes
  this gaming shape from a plain empty submission: it is the only leg where the
  part is present, mounted on the animated mesh, and bound to a *bone* instead
  of to the named point. Crediting it on `WEAPONSOCKET_NOT_FOUND` would have
  made it indistinguishable from the empty leg and proved nothing.
- `weapon-on-mesh-no-socket/` fails **exactly one** check. That is the point of
  the leg: it is the only submission in the set that every static read accepts,
  so it is the direct oracle for whether the transient-spawn route works at all
  (`notes.md` §5).

Coverage note (bounded, argued from the named checks rather than run as
separate submissions):

- A submission that authors the attachment point **on the mesh** instead of on
  the joint hierarchy is an ACCEPTED solution, not a variant —
  `USkeletalMesh::FindSocketAndIndex` searches mesh sockets first and then the
  skeleton's (`SkeletalMesh.cpp:5238-5266`), and both placements put the point
  on the figure. Deliberate acceptance, recorded in the spec.
- A submission that authors the point correctly but re-points the figure at a
  different animated mesh dies at `char_mesh_uses_task_skeletal_mesh`
  (`CHAR_MESH_ASSET_WRONG asset=`). No variant is authored for it because the
  same defect class is already exercised by `weapon-without-cube-mesh/`, and
  because producing it requires an edit no plausible agent makes by accident.
- A submission that adds a component merely *named* `Mesh` and hangs `Weapon`
  off that dies at `weapon_attach_parent_is_character_mesh`, on the
  `skeletal=`/`inherited=` conjuncts rather than on `name_ok=`. Covered by the
  offline oracle test rather than by a sixth `.uasset` variant.
- A submission that leaves `BP_EvalChar` uncompiled dies at
  `char_bp_compiles_up_to_date` (`CHAR_NOT_UP_TO_DATE`); no variant is authored
  for it because producing that state deliberately requires hand-editing a
  `.uasset`'s transient compile state, which is not reliably authorable.
- **No variant exercises `weapon_socket_offset_is_identity`, on purpose.** It
  asserts the UE 5.8 engine default (`SkeletalMeshSocket.h:30-34`), so it has
  no discriminating power and a variant for it would be theatre. It is scored,
  labelled low-discrimination in the spec, and audited in `notes.md` §0.

## What was missing (discharged 2026-07-29 — kept as the asset inventory)

**Every asset below is now authored and committed** (landed 2026-07-29,
`c210813`): the three baselines in the substrate, plus 11 tracked `.uasset`s
across `../reference/` and all five variant folders. The per-folder
`README-MISSING-ASSETS.md` placeholders were deleted in that same landing,
exactly as this section required. The table stays as the inventory of what
each folder carries; the surviving property-level spec is `../notes.md`
(§1 baselines, §2 reference, §3 variants).

| # | Where | What it must be |
|---|---|---|
| 0 | substrate baseline, three assets | `SK_EvalChar_Skeleton`, `SKM_EvalChar`, `BP_EvalChar` under `UE-projects/ThirdPerson/Content/Tasks/t2-weapon-held-in-right-hand/`. `notes.md` §1 |
| 1 | reference overlay | the socket-bearing asset + `BP_EvalChar`. `notes.md` §2 |
| 2 | variant `socket-on-wrong-bone` | authored + committed; property spec `../notes.md` §3 (its README, now deleted, carried the same spec) |
| 3 | variant `weapon-on-capsule-root` | authored + committed; property spec `../notes.md` §3 (its README, now deleted, carried the same spec) |
| 4 | variant `weapon-on-mesh-no-socket` | authored + committed; property spec `../notes.md` §3 (its README, now deleted, carried the same spec) |
| 5 | variant `bone-name-instead-of-socket` | authored + committed; property spec `../notes.md` §3 (its README, now deleted, carried the same spec) |
| 6 | variant `weapon-without-cube-mesh` | authored + committed; property spec `../notes.md` §3 (its README, now deleted, carried the same spec) |

Does every variant also need an unmodified copy of the baselines? **No** —
deliberately not. `apply_submission` is a copy-only overlay with no wipe, so any
asset a submission does not carry is simply the substrate's own committed
baseline. Each variant overlays only the assets it changes.

## How to run (deterministic verifier, no agent, no tokens)

```sh
cb discriminate --task bp/t2-weapon-held-in-right-hand
```

Per-leg fallback while iterating on one variant (a short `--workdir` dodges
Windows MAX_PATH; use the `py` launcher — this box's `py -3.12` does not
resolve):

```sh
UE='<UE-root>'
py tools/verify-single/run_task.py \
    --task tasks/bp/t2-weapon-held-in-right-hand/task.md \
    --submission tasks/bp/t2-weapon-held-in-right-hand/discrimination/weapon-on-mesh-no-socket \
    --ue-root "$UE" --workdir C:\cb\wd\kv6var       # expect exit 1
```

Then open the workdir's `report.json` and the `L2I` log it names, find the
`CRAFTBENCH-INTROSPECT-JSON-START` block, and confirm the failing check's raw
`detail` contains this table's "Expected substring" cell.

**L2I graders are read from the LIVE working tree** (`registry.py:312` resolves
`introspect_root = _VERIFY / "introspect"`), unlike L2 fixtures which come from
git HEAD. So iterating on `weapon_held_in_right_hand.py` needs no commit — but
the `.uasset` files DO need committing before a non-`--wip` grade sees them
(`run_task` materializes the substrate from git HEAD).

## Status

- Authored 2026-07-27 from the spec, text-only track — at that point no leg
  had run in UE and no `.uasset` existed. Both were true when written; both
  are discharged below. (This block sat stale for two days against the dated validation table's
  VALIDATED row; resolved 2026-08-16 —
  an internal working note (not shipped) Q18: the dated validation table is right,
  VALIDATED is the operative status.)
- **Sweep RUN 2026-07-29** (recorded in the dated validation table (internal, not shipped)):
  `cb discriminate --wip` = **YES 7/7 legs** — reference **PASS (L2I 10/10)**,
  including THE calibration item from `../notes.md` §5: the live-world
  `weapon_attach_socket_is_weapon_socket` transient-spawn read round-tripped
  the SCS socket name under `-nullrhi`, so the task ships at 10 checks, not 9.
  empty + `bone-name-instead-of-socket` + `socket-on-wrong-bone` +
  `weapon-on-capsule-root` + `weapon-on-mesh-no-socket` +
  `weapon-without-cube-mesh` all FAIL, each credited at its NAMED assertion.
- **The asset caveat is discharged:** the three baselines are committed in the
  substrate under
  `UE-projects/ThirdPerson/Content/Tasks/t2-weapon-held-in-right-hand/`, and
  11 `.uasset`s are tracked under this task's `reference/` + five variant
  folders (landed 2026-07-29, `c210813`, with the per-folder
  `README-MISSING-ASSETS.md` placeholders deleted as required).
- **Re-confirmed 2026-07-31** on an idle box, after a contaminated
  certification batch first reported `discriminated: NO`: re-run = **YES 7/7
  cold** (an internal eval report (not shipped) §4 I4).
- The offline LOGIC oracle stands as before: every one of the six negative
  legs parses out of this file with a **non-empty, backtick-free** substring,
  and every substring is proven to be a literal the introspect script actually
  prints — simulated offline against a fake `unreal` module and joined through
  the REAL `discriminate.parse_matrix` + the REAL `layers/l2_introspect`
  parser by `tools/verify-single/tests/test_introspect_weapon_socket.py`.

## Requirements table (checklist §7, the mandatory soundness artifact)

This task is `layers: [L1, L2I]` — there is **no L2 fixture and no
`FinishTest` literal anywhere in it**. Every UPPERCASE backticked token in the
gate and skip columns below is a contiguous span of a `detail` string printed
by the ONE verifier-owned grader,
`tools/verify-single/introspect/weapon_held_in_right_hand.py` (front-matter
`introspect:` list), inside its `CRAFTBENCH-INTROSPECT-JSON` block; the check
id is the durable join key. Backticked API/asset/citation names (e.g.
`FindSocket`, `DoesSocketExist`, `FindSocketAndIndex`, `isinstance`,
`AttachToComponent`, `GetAttachSocketName()`, `bVisible=false`,
`SK_EvalChar_Skeleton`, `SkeletalMeshSocket.h:30-34`, `BS_UpToDateWithWarnings`)
are explanatory only — sourced from the grader's code/docstrings or from
`task.md` — and never appear in any emitted `detail`. L1 (UBT builds `ThirdPersonEditor` + `ThirdPerson`,
both exit 0) is a load-cleanly precondition on this content-only task, never a
correctness signal. Path-containment is enforced by
`tools/verify-single/sandbox.py` against
`UE-projects/ThirdPerson/AGENT_WRITABLE.json` (exit 4), not by any check.

| # | Prompt requirement | Asserted | Enforcing gate — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | an attachment point named exactly `WeaponSocket` exists on the figure's rig ("on the joint hierarchy the figure's animated body uses") | fully for name+existence; the ON-THE-SKELETON placement is deliberately relaxed | `weapon_socket_exists` — `WEAPONSOCKET_NOT_FOUND /Game/Tasks/` (read via `FindSocket` on `SKM_EvalChar`, never `DoesSocketExist` — the bone-fallback hole is anti-gaming note #1) | the task mesh asset is missing or unloadable — all three socket checks fan out on `TASK_MESH_ASSET_MISSING /Game/Tasks/` / `TASK_MESH_LOAD_FAILED ` instead | authoring the socket on `SKM_EvalChar` (the mesh) instead of `SK_EvalChar_Skeleton` — ACCEPTED by design: `FindSocketAndIndex` searches mesh sockets then the skeleton's, and both placements put the point on the figure (recorded acceptance, spec + MATRIX coverage note) |
| 2 | the point is anchored to the right-hand joint `hand_r` | fully | `weapon_socket_on_hand_r` — `WEAPONSOCKET_BONE_WRONG bone=` (exact string compare of the socket's `BoneName`) | row 1's root cause fans out first (mesh missing / socket never found share one token) | nothing — the bone name is matched exactly; wrong-joint sockets (`root`, `pelvis`, left hand) all die here |
| 3 | the point sits exactly on the joint — no positional and no angular offset | fully, tol ±1e-3 — but LOW DISCRIMINATION: it asserts the UE 5.8 engine default (`SkeletalMeshSocket.h:30-34`) | `weapon_socket_offset_is_identity` — `WEAPONSOCKET_OFFSET_NOT_IDENTITY loc=` | row 1's root cause fans out first | any agent that simply never touches the transform passes for free (freshly created socket = identity); sub-1e-3 offsets are inside the disclosed tolerance. Scored, but counted as zero discriminating power (spec divergence #4) |
| 4 | the figure's animated body keeps rendering the task mesh `SKM_EvalChar` (the prompt's premise; closes the socket-on-graded-asset-but-figure-repointed hole) | fully | `char_mesh_uses_task_skeletal_mesh` — `CHAR_MESH_ASSET_WRONG asset=` (path compare of the inherited mesh component's `GetSkeletalMeshAsset`) | `BP_EvalChar` deleted/unloadable — all seven char-side checks fan out on `CHAR_ASSET_MISSING /Game/Tasks/`; a broken subobject walk lands `CHAR_MESH_READ_ERROR raised ` instead | subclassing the mesh component type — deliberately tolerated (`isinstance`); anything else on the asset pointer fails |
| 5 | `BP_EvalChar` owns a new part named exactly `Weapon` | fully | `char_has_weapon_component` — `WEAPON_COMPONENT_MISSING names=` (SubobjectData walk, matched by pre-declared name) | row 4's `CHAR_ASSET_MISSING` fanout; walk failure lands `WEAPON_WALK_ERROR raised ` | nothing on the name — it is matched exactly against the subobject display name |
| 6 | the part is non-animated ("non-animated part" = a static-mesh component) | fully | `weapon_is_static_mesh_component` — `WEAPON_NOT_STATIC_MESH class=` | rows 4–5 fan out first (`Weapon` missing re-uses `WEAPON_COMPONENT_MISSING names=` on this check) | any `StaticMeshComponent` SUBCLASS — deliberately tolerated (`isinstance`, identity-by-name-never-class law) |
| 7 | the part displays the engine's basic cube (`/Engine/BasicShapes/Cube`) | partially — the `StaticMesh` POINTER is asserted; "displays" is not | `weapon_shows_engine_cube` — `WEAPON_MESH_NOT_CUBE mesh=` (path compare of the component's `StaticMesh` property) | rows 4–5 fan out first | visibility, material, and scale are never read: a cube with `bVisible=false`, zero scale, or a fully transparent material passes — the pointer is right, nothing "displays" |
| 8 | `Weapon` is mounted on the figure's ANIMATED BODY (the inherited mesh, not the capsule root or a decoy) | fully — three independent conjuncts: parent name in (`Mesh`/`CharacterMesh0`) AND parent is a skeletal-mesh component AND parent is inherited/native | `weapon_attach_parent_is_character_mesh` — `WEAPON_ATTACH_PARENT_WRONG parent=` (SubobjectData parent handle; the template's `AttachParent` is null at rest) | rows 4–5 fan out first; an unevaluable type probe routes to `WEAPON_ATTACH_TYPE_PROBE_ERROR ` (harness event, never credited) | nothing named-only: a submission-authored component merely *called* `Mesh` fails the skeletal/inherited conjuncts (anti-gaming note #3) |
| 9 | ...mounted **at the `WeaponSocket` attachment point** (not loose under the mesh, not bound to the bare bone) | fully, via ONE transient spawn — the SCS socket name is statically unreachable at three levels, so the generated class is constructed once and `GetAttachSocketName()` is read off the live component | `weapon_attach_socket_is_weapon_socket` — `WEAPON_ATTACH_SOCKET_WRONG socket=` (prints `socket=None` for under-the-mesh, `socket=hand_r` for bone-instead-of-socket) | rows 4–5 fan out first; every spawn/read fault owns a distinct uncredited token (`WEAPON_SPAWN_CLASS_UNAVAILABLE `, `WEAPON_SPAWN_UNAVAILABLE `, `WEAPON_SPAWN_FAILED `, `WEAPON_INSTANCE_COMPONENT_MISSING names=`, `WEAPON_ATTACH_SOCKET_READ_ERROR raised `) — a dead probe can never pass or be credited | nothing on the binding itself — `AttachToComponent` does no socket validation, so the bone-name shortcut is caught here with `socket=hand_r`. Calibration caveat: the transient spawn under `-nullrhi` is the task's one unproven route (`notes.md` §5); if unreachable the honest fallback is 9 checks + relabel, never a silent pass |
| 10 | everything changed is **compiled** | fully for the one compilable deliverable (`BP_EvalChar`; skeleton/mesh assets have no compile status) | `char_bp_compiles_up_to_date` — `CHAR_NOT_UP_TO_DATE status=` (freshly loaded asset's `Status` must contain `UP_TO_DATE`) | row 4's `CHAR_ASSET_MISSING` fanout | `BS_UpToDateWithWarnings` is accepted (substring match on `UP_TO_DATE`) — compile warnings are free |
| 11 | everything changed is **saved** | fully, by the substrate model — not a check | not a gate: the runner grades a FILE overlay materialized onto a clean substrate, so unsaved editor state never reaches the grader; an unsaved edit presents as the baseline bytes and dies at rows 1/5/7/9 | unconditional | nothing — dirtiness is unobservable and unnecessary by construction (spec, "Why `saved` is not a separate check") |
| 12 | nothing outside `Content/Tasks/t2-weapon-held-in-right-hand/` may be modified | partially — enforced at SUBSTRATE granularity, not task granularity | not a check: `sandbox.py` vs `AGENT_WRITABLE.json` — deny-prefix hit or allowlist miss = SANDBOX-REJECT exit 4 (protected content: `Content/Maps/`, `Content/Characters/`, `Content/ThirdPerson/`, `Content/Input/`, `Source/CraftBenchTests/` all deny) | unconditional (runs before any layer) | stray files under OTHER agent-writable prefixes are accepted and ungraded: C++ under `Source/ThirdPerson/`, assets under `Content/Blueprints/` / `Content/Abilities/` / `Content/Generated_*/`, other `Content/Tasks/<id>/` folders, and `config_allow`-conformant edits to the two `config_writable` inis — the prompt's folder clause is narrower than the sandbox that enforces it |
| 13 | the OUTCOME: once placed in a level and animating, the cube rides in the right hand — not at the figure's feet, not floating at its origin | **NOT ASSERTED** at runtime — no L2/PIE leg exists (`layers: [L1, L2I]`); graded only via the structural proxies in rows 1, 2, 8, 9 | none — the grader's one construction (row 9) reads a single socket name off a freshly constructed actor and destroys it; nothing ever ticks, animates, or samples a world-space position | n/a | a `Weapon` component bound at `WeaponSocket` but carrying its OWN large relative offset (never read — 10 m from the hand passes 10/10), a zero-scale or hidden cube (row 7), or construction-script / anim-BP / tick logic that re-attaches or moves the cube after construction — every one passes all 10 checks while visibly failing the prompt's outcome sentence |

Fan-out grammar (so a reviewer can read a raw verdict block without the
script open): the three socket checks share one root-cause token when the mesh
or socket is unreachable; the seven char checks share `CHAR_ASSET_MISSING `
when `BP_EvalChar` is gone; a missing `Weapon` re-stamps
`WEAPON_COMPONENT_MISSING names=` onto rows 6–9. Every exception path owns a
`*_READ_ERROR` / `*_FIND_ERROR` / `*_PROBE_ERROR` / `*_WALK_ERROR` /
`*_UNAVAILABLE` / `*_ABORTED` token that appears in no matrix row and can
never be credited (asserted over the full suffix set
`_ERROR`/`_ABORTED`/`_UNAVAILABLE`/`_EMPTY`/`_FAILED`/`_NOT_EVALUATED` by
`tests/test_introspect_weapon_socket.py::TestErrorTokensAreDisjointFromMatrix`).
The denominator is a constant 10 on every leg, so no submission improves its
ratio by making checks unreachable.

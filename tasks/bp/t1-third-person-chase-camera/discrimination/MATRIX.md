# Discrimination matrix — t1-third-person-chase-camera

The self-validation oracle: the reference solution must PASS and every gaming
variant + the empty leg must FAIL **at the predicted check, via the named
substring**. A wrong-reason FAIL (L1 build failure, a different check, a
`0`-check/`error` L2I verdict, SANDBOX-REJECT exit 4) means the verifier is NOT
discriminated — fix it, or relabel the task for the weaker property it actually
tests.

> **STATUS: NOT RUNNABLE YET.** Every leg of this matrix needs a binary
> `.uasset` that does not exist on disk. The rows, the expected substrings and
> the per-variant asset specs below are complete and authored; the bytes are
> not. See **What is missing** and `../notes.md`.

## Three parser traps this matrix is written against

- **ONE parseable row per label.** `discriminate.parse_matrix` returns
  `Dict[label -> MatrixRow]` (`discriminate.py:227`), so a *second* table that
  repeats a variant label silently **overwrites** the first — and because a
  table without a "substring"/"message" header column yields an empty message,
  the overwrite lands a blank substring tuple and the leg can never be
  credited. This file therefore has **exactly one table with variant rows**;
  every secondary/derived observation lives in prose below it, where no `|`
  row can re-register a label. (The defect was reproduced and fixed on the
  pilot, 2026-07-27; 4 of its 6 negative legs had been blanked this way.)
- **Every "Expected substring" cell is a backtick-wrapped literal that
  CONTAINS A SPACE.** `_extract_substrings` (`discriminate.py:195-218`) keeps a
  backticked span only when it is "substantive" — contains a space or one of
  `(),.=` — otherwise it falls through to a last-resort branch that returns the
  cell *with its backticks still attached*, which can never match log text. A
  bare `SCREAMING_SNAKE` check id has neither, so it hits the broken branch.
  Pairing the token with the fixed prefix of the text that follows it in the
  script (`... names=`, `... inherited=`, `... parent=`, `... class=`,
  `... value=`) makes the cell substantive **and** keeps it a verbatim
  substring of the printed `detail`. This works whether or not the last-resort
  branch is ever fixed in code.
- **The reference row's message cell is never parsed for substrings.**
  `parse_matrix` returns `()` for any `PASS` row on purpose, so the prose in
  that cell cannot seed a spurious expectation.

## Two L2I traps this matrix is written against

- **The substring is matched against the raw `detail` string as printed inside
  the `CRAFTBENCH-INTROSPECT-JSON` block** — not against the layer's
  `<script>:<check>: FAIL - ...` note rendering. Every "Expected substring"
  cell below is a literal token emitted by
  `tools/verify-single/introspect/third_person_chase_camera.py`.
- **Exactly ONE introspect script per task.** `registry.py` keeps only
  `li_last_log`, so a substring printed by an *earlier* script could never be
  credited. This task declares one script, and must keep declaring one.

**ASCII rule:** every expected substring is ASCII-only. The UE log's UTF-8
bytes are read back as cp1252, so a non-ASCII character in a detail string
becomes mojibake and the grep misses — a correct FAIL then misclassifies as
wrong-reason (live incident, `t2-homing-projectile`, 2026-07-21). The whole
introspect script is ASCII by construction.

**Error tokens are distinct from failure tokens.** Every exception path in the
script emits a `*_READ_ERROR` / `*_WALK_ERROR` / `*_PROBE_ERROR` /
`*_ABORTED` / `CHECK_NOT_EVALUATED` token that appears in **no** matrix row. So
a broken UE API name can never be credited as a variant's named failure — it
shows up as an uncredited FAIL, which is the signal you want. Two places where
this distinction is load-bearing rather than decorative:

- an unreadable authorship probe emits `BOOM_AUTHORSHIP_READ_ERROR`, **not**
  `BOOM_NOT_AUTHORED_ON_ASSET`, so an API break cannot be scored as
  variant 1's defence firing;
- an unreadable camera flag emits `CAMERA_CONTROL_ROTATION_READ_ERROR`, **not**
  a pass — the one negative-shaped check in the task fails closed.

**The empty leg's token is a POSITIVE claim, and it did not used to be.**
Fixed 2026-07-27 (cross-row review). Every check past `character_asset_exists`
is a NAME LOOKUP over the subobject walk, and the walk used to skip a subobject
whose `FSubobjectData` would not resolve, or whose display name read back
blank, and carry on. `_names_of` then filtered the blanks out — so a build in
which `get_variable_name` AND `get_object` had both broken emitted
`BOOM_COMPONENT_MISSING names=[]`, which is exactly the empty leg's credited
substring. A pure API break would have been scored as the empty submission's
named failure. Two changes close it, and the row's substring moved with them:

- `_components` now RAISES `SUBOBJECT_NAMES_UNREADABLE unresolved=.. unnamed=..`
  on any unresolvable or unnameable subobject, so it never returns a partially
  read walk. That surfaces as `BOOM_WALK_ERROR raised ...`, an error token no
  row claims.
- the absence details are rendered through `_absent`, which appends
  `searched=<N>`: a positive record that N subobjects were walked *and every
  one of them was named*. The matrix therefore joins on
  `BOOM_COMPONENT_MISSING searched=`, not on `... names=`, and that substring
  is unproducible without a complete walk.

Both halves are executed in the offline oracle
(`tools/verify-single/tests/test_introspect_chase_camera.py::TestEmptyLegTokenIsUnambiguous`),
including the pre-fix reproduction.

## Layout (folder-local; agent-writable prefixes only — a stray root file -> SANDBOX-REJECT exit 4)

- `../reference/Content/Tasks/t1-third-person-chase-camera/BP_Scout.uasset` —
  the one correct solution. The `ThirdPerson` substrate's agent-writable Content
  carve-out is `Content/Tasks/`, so the overlay mirrors that path exactly,
  including the per-task segment.
- `<variant>/Content/Tasks/t1-third-person-chase-camera/BP_Scout.uasset` — one
  dir per anti-gaming note, sibling to this MATRIX.md.
- empty leg — run IMPLICITLY by `cb discriminate` (it creates a throwaway empty
  dir; nothing to author). Its row documents the expected first-gate failure.

**Every leg of this task overlays the SAME single file.** Unlike the pilot,
where the deliverable was a new asset beside an untouched baseline, here the
deliverable *is* the baseline, edited. `apply_submission` is a copy-only
overlay, so a leg that ships no `.uasset` is graded against the substrate's own
committed `BP_Scout` — which is exactly what makes the empty leg meaningful:
the asset loads, the camera is there, the boom is not.

## Matrix

**This is the only table in this file that carries variant rows.** Do not add a
second one — see the first parser trap above.

| Submission | Overall | Fails at (check id) | Expected substring | Also fails (recorded, not matched) | Anti-gaming note |
|---|---|---|---|---|---|
| `../reference` | PASS | — | all 14 checks green (14/14) | — | — |
| empty | FAIL | `boom_component_exists` | `BOOM_COMPONENT_MISSING searched=` | the 8 boom-dependent checks fan out on the same root cause; `camera_attached_to_boom` and `camera_off_control_rotation` fail on their own (`3/14`) | #1 / FR-017 |
| `rig-inherited-from-template-character/` | FAIL | `boom_authored_on_this_asset` | `BOOM_NOT_AUTHORED_ON_ASSET inherited=` | `boom_socket_offset_up_75`, `boom_camera_lag_enabled`, `boom_camera_lag_speed_4` | #1 rig obtained by re-basing |
| `boom-hung-on-the-mesh/` | FAIL | `boom_attached_to_character_root` | `BOOM_ATTACH_PARENT_WRONG parent=` | — | #2 boom hung wherever the cursor was |
| `boom-is-a-plain-scene-component/` | FAIL | `boom_is_spring_arm` | `BOOM_NOT_SPRING_ARM class=` | `camera_attached_to_boom`, plus five `*_READ_ERROR` scalar checks | #3 right name, wrong thing |
| `boom-left-at-engine-defaults/` | FAIL | `boom_arm_length_400` | `BOOM_ARM_LENGTH_WRONG value=` | `boom_socket_offset_up_75`, `boom_uses_control_rotation`, `boom_camera_lag_enabled`, `boom_camera_lag_speed_4` | #4 everything left at engine defaults |
| `camera-still-steering-itself/` | FAIL | `camera_off_control_rotation` | `CAMERA_STILL_ON_CONTROL_ROTATION value=` | — | #5 camera re-homed but still steering |

Why each "Also fails" entry is expected and does **not** make the
discrimination muddy (prose on purpose — a table here would re-register the
labels and blank their substrings):

- **empty** — the baseline falls through, so `character_asset_exists`,
  `camera_component_exists` and `character_compiles_up_to_date` PASS. That
  `3/14` floor is correct and deliberate: it is the score of "changed nothing",
  and it is what the reported `tests_passed/tests_run` is measured against.
- **`rig-inherited-from-template-character/`** also fails the three settings the
  substrate's own C++ base does not set — `SocketOffset` stays `(0,0,0)`,
  `bEnableCameraLag` stays `false`, `CameraLagSpeed` stays the engine's `10`.
  It *passes* arm length, control rotation and both attachment checks, which is
  precisely the point: it scores `10/14` *with* the authorship check, and
  without that check it would score `11/14` for doing none of the work.
- **`boom-is-a-plain-scene-component/`** fails five scalar checks through
  `BOOM_ARM_LENGTH_READ_ERROR` / `BOOM_SOCKET_OFFSET_READ_ERROR` /
  `BOOM_CONTROL_ROTATION_READ_ERROR` / `BOOM_CAMERA_LAG_READ_ERROR` /
  `BOOM_LAG_SPEED_READ_ERROR`, because a plain positioning node has none of
  those properties. Those are **error** tokens by design and none of them is a
  matrix row, so they are visible-but-uncredited — the intended signal.
- **`boom-left-at-engine-defaults/`** fails four further settings
  (`BOOM_SOCKET_OFFSET_WRONG value=`, `BOOM_NOT_ON_CONTROL_ROTATION value=`,
  `BOOM_CAMERA_LAG_DISABLED value=`, `BOOM_LAG_SPEED_WRONG value=`). Note the
  last one only fires because this task moved the required lag speed off the
  source row's `10`, which is the engine default (`SpringArmComponent.cpp:40`).

Coverage note (bounded, argued from the named checks rather than run as
separate submissions):

- A submission that puts the boom in the right place and sets four of the five
  settings dies at whichever single setting it missed; each of the five owns a
  distinct token, so the partial-credit ratio and the failing token together
  identify it without a dedicated variant.
- A submission that adds a **second** decoy component named `CameraBoom`
  alongside a correct one cannot pass `camera_attached_to_boom`: that check
  compares the camera's parent object path against the boom subobject the walk
  resolved, so the two must be the same object.
- A submission left in an uncompiled state dies at
  `character_compiles_up_to_date` (`CHARACTER_NOT_UP_TO_DATE`); no variant is
  authored for it because producing that state deliberately requires
  hand-editing a `.uasset`'s transient compile state, which is not reliably
  authorable.
- **Not gradeable, so not a variant:** a camera attached to the boom's *origin*
  rather than its endpoint socket. The socket name has no reflection read route
  (see the spec's "What is deliberately NOT graded"), so this matrix does not
  pretend to catch it.

## What is missing (this matrix cannot run until these exist)

**I cannot author `.uasset` binaries from a text-only track.** Six binaries are
needed, all of them the same file at different paths. Each variant folder holds
a `README-MISSING-ASSETS.md` at the exact path the `.uasset` must occupy,
describing property-by-property what to author; **delete that README in the same
commit that lands the real asset.** The full property-level spec for the
baseline and the reference is `../notes.md`.

| # | Path | What it must be |
|---|---|---|
| 0 | `UE-projects/ThirdPerson/Content/Tasks/t1-third-person-chase-camera/BP_Scout.uasset` | the **baseline** shipped in the substrate (not a submission). `notes.md` §1 |
| 1 | `../reference/Content/Tasks/.../BP_Scout.uasset` | the **reference**. `notes.md` §2 |
| 2 | `rig-inherited-from-template-character/Content/Tasks/.../BP_Scout.uasset` | variant. See that folder's README |
| 3 | `boom-hung-on-the-mesh/Content/Tasks/.../BP_Scout.uasset` | variant |
| 4 | `boom-is-a-plain-scene-component/Content/Tasks/.../BP_Scout.uasset` | variant |
| 5 | `boom-left-at-engine-defaults/Content/Tasks/.../BP_Scout.uasset` | variant |
| 6 | `camera-still-steering-itself/Content/Tasks/.../BP_Scout.uasset` | variant |

## How to run (deterministic verifier, no agent, no tokens)

```sh
cb discriminate --task bp/t1-third-person-chase-camera
```

Per-leg fallback while iterating on one variant (a short `--workdir` dodges
Windows MAX_PATH; use the `py` launcher — this box's `py -3.12` does not
resolve):

```sh
UE='<UE-root>'
py tools/verify-single/run_task.py \
    --task tasks/bp/t1-third-person-chase-camera/task.md \
    --submission tasks/bp/t1-third-person-chase-camera/discrimination/boom-hung-on-the-mesh \
    --ue-root "$UE" --workdir C:\cb\wd\kv11var       # expect exit 1
```

Then open the workdir's `report.json` and the `L2I` log it names, find the
`CRAFTBENCH-INTROSPECT-JSON-START` block, and confirm the failing check's raw
`detail` contains this table's "Expected substring" cell.

**L2I graders are read from the LIVE working tree** (`registry.py:312` resolves
`introspect_root = _VERIFY / "introspect"`), unlike L2 fixtures which come from
git HEAD. So iterating on `third_person_chase_camera.py` needs no commit — but
the `.uasset` files DO need committing before a non-`--wip` grade sees them
(`run_task` materializes the substrate from git HEAD).

## Status

- Authored 2026-07-27 from the spec, text-only track. **Never executed against
  a real editor** — no leg has run in UE, because no `.uasset` exists yet.
- Every one of the six negative legs parses out of this file with a
  **non-empty, backtick-free** substring through the REAL
  `aura_rig.discriminate.parse_matrix`, and every substring was proven to be a
  literal the introspect script actually prints by simulating each leg against
  a fake `unreal` module and reading the result back through the REAL
  `layers/l2_introspect.parse_introspect_verdict`. That is the LOGIC oracle,
  not an engine oracle: it cannot confirm a UE API *name*.
- **Still missing, in order:** (1) the six `.uasset` binaries above — nothing
  here can run in UE without them; (2) a live-editor confirmation of the UE
  API names the offline fake cannot check (`is_inherited_component`,
  `is_native_component`, `is_root_component`, and which spelling of
  `use_pawn_control_rotation` / `enable_camera_lag` / `socket_offset` /
  `status` `get_editor_property` resolves — the script tries several spellings
  each, but only an editor settles it); (3) the `discriminate.py` last-resort
  backtick strip — this file no longer *depends* on it, but every future L2I
  MATRIX will hit the same trap until it lands.
- Blocked additionally on `tools/verify-single/tests/test_verdict_taxonomy.py:79`
  (`test_every_shipping_spec_declares_only_landable_gating_layers`), which
  asserts every spec on disk is exactly `("L1","L2")` and therefore already
  fails for the pilot. Plan §9.1 assigns replacing that equality with a
  landability assertion to Phase 1; this task inherits that blocker rather than
  adding a new one.

## Requirements table (checklist §7, the mandatory soundness artifact)

This task declares `layers: [L1, L2I]` — there is no L2 fixture. Every backticked
span below is verbatim-greppable in the verifier-owned grader
`tools/verify-single/introspect/third_person_chase_camera.py` (14 named checks,
constant denominator on every leg), EXCEPT that rows marked **(composed)** name a
bare token constant the grader joins to runtime detail via `%`-formatting at emit
time: the asset-missing fan-out is `"%s %s" % (ASSET_MISSING_TOKEN, ASSET_CHARACTER)`
(line 749), the two component-absent details go through `_absent`'s format
`%s searched=%d names=%s wanted=%s` (line 422), and the two attach-failure details
are `"BOOM_ATTACH_PARENT_WRONG %s" % report` / `"CAMERA_ATTACH_PARENT_WRONG %s" % report`
(lines 854/912) where the report string begins `parent=%s` (lines 567/632) — so
spans like `BOOM_COMPONENT_MISSING searched=` exist only in the emitted detail,
never as one source literal. The graded asset path is itself
composed: `/Game/Tasks/%s/BP_Scout` `% TASK_ID` (line 98). The L1 row's gate is
the runner's dual-target UBT build, which has no fixture literal. Check ids are
the durable join keys; every `*_READ_ERROR` / `*_PROBE_ERROR` / `*_WALK_ERROR`
token is a distinct FAIL-closed error path, never credited as the graded failure.

| # | Prompt requirement | Asserted | Enforcing gate — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | the deliverable is the SAME asset in the SAME place (`Content/Tasks/t1-third-person-chase-camera/BP_Scout`) | fully, path-pinned | `character_asset_exists` — `CHARACTER_ASSET_MISSING` (composed: joined to the asset path at emit time; the grader keys on the pre-declared path built from `/Game/Tasks/%s/BP_Scout` with `TASK_ID = "t1-third-person-chase-camera"` — a BP_Scout authored anywhere else is simply never read) | unconditional (first check; on FAIL the token fans out to all 13 remaining checks) | nothing on placement — but the untouched BASELINE passes this row too (the deliberate 3/14 empty-leg floor), so this gate alone proves nothing was done |
| 2 | the project still loads and builds (precondition for any grade) | fully | L1 — UnrealBuildTool exits 0 for BOTH `ThirdPersonEditor Win64 Development` and `ThirdPerson Win64 Development` (short-circuits on first failure; no verbatim literal — L1 is the runner's build layer, not a fixture) | never (gating layer; an L1 FAIL skips L2I entirely) | everything — the submission is content-only, so L1 is a precondition, never a correctness signal |
| 3 | add a new part named `CameraBoom` | fully | `boom_component_exists` — `BOOM_COMPONENT_MISSING` (composed via `_absent`, whose `searched=%d` suffix is a positive record that the subobject walk resolved and named every subobject; a broken walk emits `BOOM_WALK_ERROR raised ` instead, which credits nothing) | asset missing (row 1 root cause fans out) | a decoy component merely NAMED `CameraBoom` passes this row alone — and then dies at rows 4/6 (type + attach are independent) |
| 4 | the new part is genuinely a boom ("a rigid pole ... eases its own motion") | fully, by type | `boom_is_spring_arm` — `BOOM_NOT_SPRING_ARM class=` (positive `isinstance` against SpringArmComponent; subclasses accepted by design) | boom absent / walk error (row 3 fan-out); an unevaluable probe fails via `BOOM_TYPE_PROBE_ERROR` instead | a SpringArm SUBCLASS that overrides its runtime behavior arbitrarily — the check is static; no PIE leg ever observes the pole actually springing or trailing (deliberate layer choice) |
| 5 | the rig is BUILT on this asset, not obtained by re-basing onto a ready-made third-person character | fully | `boom_authored_on_this_asset` — `BOOM_NOT_AUTHORED_ON_ASSET inherited=` (the boom must report neither IsInheritedComponent nor IsNativeComponent; an unreadable probe fails via the distinct `BOOM_AUTHORSHIP_READ_ERROR`) | boom absent / walk error (row 3 fan-out) | re-basing onto a boom-FREE third class and then authoring the boom there — the authorship check only sees the boom itself (see row 7's hole for what else that opens) |
| 6 | the boom hangs off the character's collision body | fully, three independent facts | `boom_attached_to_character_root` — `BOOM_ATTACH_PARENT_WRONG` (composed: joined to a report string that begins `parent=%s`; parent handle must resolve to a subobject named `CapsuleComponent` or `CollisionCylinder` AND be an actual CapsuleComponent AND be inherited/native — a scene component the submission renamed dies on fact 2) | boom absent / walk error (row 3 fan-out); an unevaluable capsule type probe fails via `BOOM_ATTACH_TYPE_PROBE_ERROR` | nothing significant; the is-root corroboration gates only when readable, so a correct submission cannot be failed by a missing accessor |
| 7 | keep "the same underlying figure" — the inherited animated humanoid body survives | **NOT ASSERTED** (capsule half only: row 6 demands the capsule parent be inherited/native; the MESH has no check) | none — `_parent_tags` records `ParentClass=` / `NativeParentClass=` inside the `BOOM_AUTHORED_OK` / `BOOM_NOT_AUTHORED_ON_ASSET` details, but no check ever COMPARES them | n/a | delete or replace the inherited humanoid mesh, or re-base `BP_Scout` onto any boom-free character class — every one of the 14 checks still passes; the "same figure" clause is graded only capsule-deep |
| 8 | the boom holds its far end **400** units away | fully | `boom_arm_length_400` — `BOOM_ARM_LENGTH_WRONG value=` (TargetArmLength == 400 ±0.5; engine default is 300, so an untouched boom fails) | boom absent / walk error (row 3 fan-out); unreadable property fails via `BOOM_ARM_LENGTH_READ_ERROR` | nothing — the ±0.5 tolerance is sub-perceptual |
| 9 | far end lifted **75** units straight up "with no sideways shift" | partially — SocketOffset only | `boom_socket_offset_up_75` — `BOOM_SOCKET_OFFSET_WRONG value=` (SocketOffset == (0,0,75) ±0.5 per axis, so X/Y sideways components ARE gated on this property; default (0,0,0)) | boom absent / walk error (row 3 fan-out); unreadable fails via `BOOM_SOCKET_OFFSET_READ_ERROR` | a nonzero **TargetOffset** — the boom's SECOND displacement knob, which also shifts the camera (sideways included). It is read into the detail (`target_offset=`) for diagnosis but never gated, so a submission can satisfy (0,0,75) on SocketOffset and still displace the view arbitrarily |
| 10 | the boom points wherever the player is looking, not where the body faces | fully, as a flag | `boom_uses_control_rotation` — `BOOM_NOT_ON_CONTROL_ROTATION value=` (bUsePawnControlRotation must read True; default False) | boom absent / walk error (row 3 fan-out); unreadable fails via `BOOM_CONTROL_ROTATION_READ_ERROR` | nothing at the asset level — but no input is ever injected (no L2), so "points where the player looks" is graded as the flag, never as observed rotation |
| 11 | the boom eases its motion so it trails instead of snapping | fully, as a flag | `boom_camera_lag_enabled` — `BOOM_CAMERA_LAG_DISABLED value=` (bEnableCameraLag must read True; default False) | boom absent / walk error (row 3 fan-out); unreadable fails via `BOOM_CAMERA_LAG_READ_ERROR` | rotation lag (bEnableCameraRotationLag) left off — only POSITIONAL lag is named by the prompt and gated; and the trailing is never observed in motion (static flag read) |
| 12 | trailing tuned to a catch-up rate of **4** | fully | `boom_camera_lag_speed_4` — `BOOM_LAG_SPEED_WRONG value=` (CameraLagSpeed == 4 ±0.01 — deliberately NOT the source row's 10, which is the engine default and would be a dead gate) | boom absent / walk error (row 3 fan-out); unreadable fails via `BOOM_LAG_SPEED_READ_ERROR` | nothing — the value is a non-default and the tolerance is tight |
| 13 | `FollowCamera` survives the edit and remains the viewpoint part | fully, name + type | `camera_component_exists` — `CAMERA_COMPONENT_MISSING` (composed via `_absent`, same `searched=%d` positive-walk record as row 3) when absent; `CAMERA_NOT_A_VIEWPOINT class=` when the name is worn by a non-camera | asset missing (row 1's `CHARACTER_ASSET_MISSING` root cause fans out); a broken subobject walk fails via `CAMERA_WALK_ERROR raised ` instead | adding a SECOND camera that is the actually-active view target — activation/auto-activate is never graded, so "the player looks out through FollowCamera" is enforced structurally, not at runtime |
| 14 | `FollowCamera` moved to ride on `CameraBoom` | fully — parent name + parent-is-a-boom + same-object identity | `camera_attached_to_boom` — `CAMERA_ATTACH_PARENT_WRONG` (composed: joined to a report string that begins `parent=%s`; parent must be NAMED CameraBoom, BE a SpringArmComponent, and be path-identical to the boom row 3 resolved — a decoy second `CameraBoom` fails the identity clause) | camera absent / not a viewpoint (row 13 fan-out); unevaluable probe fails via `CAMERA_ATTACH_TYPE_PROBE_ERROR` | attachment at the wrong POINT on the boom — see row 15 |
| 15 | ...specifically on the boom's **far end** (the endpoint socket) | **NOT ASSERTED** | none — the attach SOCKET name has no reflection read route in UE 5.8 (`USCS_Node::AttachToName` / `AttachSocketName` are reflection-denied bare UPROPERTYs; documented in the spec's "What is deliberately NOT graded") | n/a | attach the camera to the boom's ORIGIN instead of its `SpringEndpoint` socket — the parent checks all pass while the camera sits 400 units from the intended frame, inside the character |
| 16 | the camera stops swinging with the mouse on its own | fully, fail-closed | `camera_off_control_rotation` — `CAMERA_STILL_ON_CONTROL_ROTATION value=` (demands a POSITIVE read of False; the baseline ships True, so "leave it alone" fails; an unreadable property fails via `CAMERA_CONTROL_ROTATION_READ_ERROR`, never as "off") | camera absent / not a viewpoint (row 13 fan-out) | nothing — this is the one negative-shaped check and it fails closed |
| 17 | `BP_Scout` must compile cleanly | fully, warnings tolerated | `character_compiles_up_to_date` — `CHARACTER_NOT_UP_TO_DATE status=` (compile status after loading the submitted asset must contain UP_TO_DATE — BS_UpToDate or BS_UpToDateWithWarnings both pass) | asset missing (row 1 fan-out); unreadable status fails via `CHARACTER_COMPILE_READ_ERROR` | compile WARNINGS — "cleanly" is graded as "up to date", not "warning-free" |
| 18 | ...and be saved | fully, by the substrate model (not a named check) | not a gate — the verdict is read exclusively from the submitted `.uasset` bytes overlaid onto a clean substrate; an unsaved edit never leaves the editor session that made it, so it grades as the untouched baseline (empty-leg shape, dies at row 3) | unconditional | nothing |

Holes found (every NOT ASSERTED / partial row, restated as the standardization-plan doctrine requires — these escalate, they are not papered over):

- **Row 15 (NOT ASSERTED):** the camera-on-the-far-END half of the attachment has no gate — a camera on the boom's origin passes all 14 checks. Known and recorded in the spec (no reflection route to the socket name); becomes gradeable only via a future C++ SCS read or a transient-spawn probe.
- **Row 7 (NOT ASSERTED):** "the same underlying figure" is enforced only one capsule deep. The animated mesh can be deleted or replaced, and a re-base onto any boom-FREE class passes every check — parent-class registry tags are recorded in details but never compared.
- **Row 9 (partial):** `TargetOffset` is unconstrained — the second displacement knob can move the view sideways while `SocketOffset` reads a perfect (0,0,75).
- **Row 13 (residual):** nothing asserts `FollowCamera` is the active/only viewpoint — a second, self-steering camera could be the live view.
- **Rows 4/10/11 (accepted by layer choice):** all behavior clauses are graded as static template values; no PIE leg ever observes the boom springing, trailing, or following look input, so a SpringArm subclass with overridden runtime behavior is invisible to the grader.

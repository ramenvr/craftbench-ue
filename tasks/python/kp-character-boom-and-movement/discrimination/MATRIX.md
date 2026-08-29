# Discrimination matrix — kp-character-boom-and-movement

The self-validation oracle: the reference must PASS and every negative leg must
FAIL **at the predicted check, via the named substring**.

One hand-authored variant ships, and it is the reason this row exists in its
current shape. The requirements table found the hole directly: the project's
shipped player character already satisfies the *structural* half of the prompt,
so without a leg that proves the movement values discriminate, the row would
have been graded on something a single `duplicate_asset` call provides.

## Parser traps this matrix is written against

- **NO cell may reach PAST a runtime placeholder into the value.** Every
  expected substring stops at the `=` before an interpolated value
  (`CHARRIG_MOVEMENT_STILL_STOCK fields=`), because the grader formats those
  tails with `%s`. A longer cell would depend on the runtime value and could
  turn a *correct* FAIL into a wrong-reason FAIL.
- **ONE parseable row per label.** `parse_matrix` keys rows by first cell and
  LAST ROW WINS. This file has exactly one table with submission rows; the
  requirements table's first cells are integers and its columns name neither
  "substring" nor "message", so it is skipped.
- **Every "Expected substring" cell is a backtick-wrapped literal containing a
  space or `=`.**
- **Error tokens are distinct from failure tokens.** `CHARRIG_LOAD_ERROR`,
  `CHARRIG_SUBSYSTEM_ERROR`, `CHARRIG_HIERARCHY_READ_ERROR`,
  `CHARRIG_CDO_READ_ERROR` and `CHARRIG_NO_UNREAL` appear in no row below.

## Layout (folder-local; agent-writable prefixes only)

- `../reference/Content/Tasks/<id>/BP_TaskChar.uasset` — a Character-derived
  Blueprint with `TaskBoom` on the root, `TaskCam` under the arm, and
  900 / 700 / 1024. **6/6.**
- `duplicate-the-stock-character/Content/Tasks/<id>/BP_TaskChar.uasset` — the
  shipped `BP_ThirdPersonCharacter`, duplicated under the required name and
  otherwise untouched. Authored 2026-08-14 by `../authoring/author_all_assets.py`.
- empty leg — run IMPLICITLY by `cb discriminate`. This task ships no baseline,
  so the graded state is genuinely empty: **0/6**.

## Requirements table (checklist §7, the mandatory soundness artifact)

| # | Prompt requirement | Asserted | Enforcing check — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | a Blueprint at that exact path | fully | C1 `blueprint_present` — `CHARRIG_BP_ABSENT path=` | unconditional | nothing |
| 2 | built on the standard walking-character base | fully | C2 `derives_from_character` — `CHARRIG_WRONG_PARENT ` | skipped only when C1 fails | which walking-character subclass — deliberate |
| 3 | `TaskBoom`, an arm at the root | fully | C3 `boom_component_present` — `CHARRIG_BOOM_MISSING wanted=` / `CHARRIG_BOOM_WRONG_CLASS wanted=` / `CHARRIG_BOOM_WRONG_PARENT expected=` | skipped only when C1 fails | the arm's own length/offset — deliberate, the prompt does not constrain them |
| 4 | `TaskCam`, a camera attached **to the arm** | fully | C4 `camera_parented_to_boom` — `CHARRIG_CAMERA_WRONG_PARENT expected=` | as above | the camera's own transform |
| 5 | walk 900 / jump 700 / acceleration 1024 | fully | C5 `movement_values_exact` — `CHARRIG_MOVEMENT_WRONG ` | skipped only when the class defaults cannot be read | every other movement property — deliberate, the prompt names three |
| 6 | "a character that still moves with stock tuning has not been tuned" | fully | C6 `movement_untouched_defaults_absent` — `CHARRIG_MOVEMENT_STILL_STOCK fields=` | as above | nothing — this is the row's discriminating claim |
| 7 | saved and compiled | fully | no separate check by design — the runner grades a file overlay, so an unsaved asset presents as no file and fails C1; an uncompiled one has no readable class defaults and fails C2/C5 | unconditional | nothing |

**The hole this table found, and what was done about it.** Rows 3–4 are the
prompt's structural half, and the shipped `BP_ThirdPersonCharacter` **already
satisfies their shape** — it has an arm-and-camera rig. So a duplicate of it
would have passed a task graded only on rows 1–4. That is why rows 5–6 exist as
exact-value checks against numbers the shipped character does not use, and why
`duplicate-the-stock-character` is a hand-authored leg rather than a table entry.

Row 3 was marked **partially** in the first draft, honestly: the check was a
name-stem lookup, so a component of the wrong type named `TaskBoom` satisfied
it — and anti-gaming note 3 claimed a defense the grader did not have. Caught in
review 2026-08-14; C3 now asserts the type and the root attachment too, so the
row is fully asserted and the note is true. The lesson worth keeping: the
requirements table is only a check while it is written against the CODE rather
than against the intent.

## Matrix

**This is the only table in this file that carries variant rows.**

| Submission | Overall | Fails at (check id) | Expected substring | Also fails (recorded, not matched) | Anti-gaming note |
|---|---|---|---|---|---|
| `../reference` | PASS | — | all 6 checks green (6/6) | — | — |
| empty | FAIL | `blueprint_present` | `CHARRIG_BP_ABSENT path=` | every other check — 0/6, each reporting `CHARRIG_UNCHECKABLE` | FR-017 |
| `tuned-but-wrong-values/` | FAIL | `movement_values_exact` | `CHARRIG_MOVEMENT_WRONG ` | — (no other check failed) | **MEASURED 5/6 in the authoring boot, self-graded by the real grader; harvested only because it isolates that one check.** **the leg that separates C5 from C6.** Hierarchy correct, walk 900 and jump 700 both matching the requirement, acceleration 1500 — wrong (1024 required) but NOT stock (2048), so `movement_untouched_defaults_absent` PASSES (measured). Before this leg C5 was never any leg's first failure: if it regressed to always-pass, `duplicate-the-stock-character/` would still fail at C6 and the package would look unchanged. |
| `duplicate-the-stock-character/` | FAIL | `movement_untouched_defaults_absent` | `CHARRIG_MOVEMENT_STILL_STOCK fields=` | `movement_values_exact` (`CHARRIG_MOVEMENT_WRONG` — 500/500/2048 against 900/700/1024), plus `boom_component_present` and `camera_parented_to_boom` (its components are named `CameraBoom`/`FollowCamera`, so the stem lookup misses). C1–C2 PASS — **2/6** | #1 duplicate-the-shipped-character |

**Why that leg is the row.** Measured at authoring time on 2026-08-14: the
shipped character reports `max_walk_speed=500.0`, `jump_z_velocity=500.0`,
`max_acceleration=2048.0` and components `CameraBoom` / `FollowCamera`. Against
the required 900 / 700 / 1024 and `TaskBoom` / `TaskCam`, every one of those is
a miss. Had this task asked for the stock values — or graded
`OrientRotationToMovement`, which the shipped character already sets `True` —
the duplicate would have passed and the row would have been vacuous.

## How to run (deterministic verifier, no agent, no tokens)

```sh
cb discriminate --task python/kp-character-boom-and-movement
```

No `--wip`: the committed tree must discriminate.

## Status

**VALIDATED 2026-08-14** (Windows, UE 5.8.1). Both committed-tree runs are in:

- `cb refgate python/kp-character-boom-and-movement` — **PASS 6/6**, 149s,
  certified.
- `cb discriminate` with NO `--wip` — **discriminated YES, 3/3 legs at their
  named checks**: reference PASS, empty 0/6, `duplicate-the-stock-character` 2/6.

The dated row is in the dated validation table (internal, not shipped), which is the status authority.

TWO GRADER DEFECTS WERE CAUGHT BEFORE THIS ROW EVER GRADED A SUBMISSION, and
both are worth knowing because the offline oracle passed through both of them:

1. **`camera_parented_to_boom` could never pass.** The first grader resolved a
   component's parent by stringifying a UE struct handle. `GetParentHandle` is a
   void-with-out-param UFUNCTION, so Python builds a FRESH wrapper, and UE's
   struct `__str__` embeds that wrapper's own address — every lookup missed, so
   the task was UNWINNABLE and every conforming submission would have scored
   5/6. Fixed by dereferencing the handle, the route the shipping graders use.
2. **The root check false-FAILed the reference.** The parentless row in the
   subobject walk is the CLASS DEFAULT OBJECT, not the scene root; `ACharacter`'s
   real root is its capsule, so the boom reports `CollisionCylinder`. The first
   real editor run said
   `CHARRIG_BOOM_WRONG_PARENT expected=Default__BP_TaskChar_C got=CollisionCylinder`.
   Now both spellings of "at the root" are accepted, because rejecting either
   would be a false FAIL on a legitimate answer.

The oracle was green before and after each fix, because its fake models the
component tree as a flat parent-name map with no CDO/root distinction. **That is
why the editor run is not optional** — a fake cannot discover a fact about the
engine that its author did not already know.

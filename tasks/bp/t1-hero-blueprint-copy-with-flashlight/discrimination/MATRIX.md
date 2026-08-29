# Discrimination matrix — t1-hero-blueprint-copy-with-flashlight

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
  row can re-register a label. (Reproduced and fixed 2026-07-27; 4 of 6
  negative legs were blanked this way.)
- **Every "Expected substring" cell is a backtick-wrapped literal that
  CONTAINS A SPACE.** `_extract_substrings` (`discriminate.py:195-218`) keeps a
  backticked span only when it is "substantive" — contains a space or one of
  `(),.=` — otherwise it falls through to a last-resort branch that returns the
  cell *with its backticks still attached*, which can never match log text. A
  bare `SCREAMING_SNAKE` check id has neither a space nor that punctuation, so
  it hits the broken branch. Pairing the token with the fixed prefix of the
  text that follows it in the script (`... /Game/Tasks/`, `... ParentClass=`,
  `... names=`, `... class=`, `... parent=`) makes the cell substantive **and**
  keeps it a verbatim substring of the printed `detail`. This works whether or
  not the last-resort branch is ever fixed in code.

## Two L2I traps this matrix is written against

- **The substring is matched against the raw `detail` string as printed inside
  the `CRAFTBENCH-INTROSPECT-JSON` block** — not against the layer's
  `<script>:<check>: FAIL - ...` note rendering. Every "Expected substring"
  cell below is a literal token emitted by
  `tools/verify-single/introspect/hero_blueprint_copy_with_flashlight.py`.
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
`*_CDO_UNAVAILABLE` / `*_ABORTED` token that appears in **no** matrix row. So a
broken UE API name can never be credited as a variant's named failure — it
shows up as an uncredited FAIL, which is the signal you want. Asserted by
`tools/verify-single/tests/test_introspect_hero_blueprint.py::
TestErrorTokensAreDisjointFromMatrix`.

## Layout (folder-local; agent-writable prefixes only — a stray root file -> SANDBOX-REJECT exit 4)

- `../reference/Content/Tasks/t1-hero-blueprint-copy-with-flashlight/…` — the
  one correct solution. The `ThirdPerson` substrate's agent-writable Content
  carve-out is `Content/Tasks/`, so the overlay mirrors that path exactly,
  including the per-task segment.
- `<variant>/Content/Tasks/t1-hero-blueprint-copy-with-flashlight/…` — one dir
  per anti-gaming note, sibling to this MATRIX.md.
- empty leg — run IMPLICITLY by `cb discriminate` (it creates a throwaway empty
  dir; nothing to author). Its row documents the expected first-gate failure.

Note the asymmetry that makes the empty leg meaningful here: the substrate
ships `BP_Source.uasset`, so an empty submission still has a *loadable*
`BP_Source` and a *missing* `BP_Hero`. The two `source_*` checks therefore PASS
on the empty leg (`3/13`), which is correct — the baseline really is untouched.

## Matrix

**This is the only table in this file that carries variant rows.** Do not add a
second one — see the first parser trap above.

| Submission | Overall | Fails at (check id) | Expected substring | Also fails (recorded, not matched) | Anti-gaming note |
|---|---|---|---|---|---|
| `../reference` | PASS | — | all 13 checks green (13/13) | — | — |
| empty | FAIL | `hero_asset_exists` | `HERO_ASSET_MISSING /Game/Tasks/` | the 9 other `hero_*` checks fan out on the same root cause; all three `source_*` checks PASS (`3/13`) | #1 / FR-017 |
| `copy-without-character-base/` | FAIL | `hero_parent_is_character` | `HERO_PARENT_NOT_CHARACTER ParentClass=` | `hero_flashlight_attach_parent_is_mesh` | #1 copy never made walkable |
| `flashlight-on-root/` | FAIL | `hero_flashlight_attach_parent_is_mesh` | `HERO_FLASHLIGHT_ATTACH_PARENT_WRONG parent=` | — | #2 light hung anywhere convenient |
| `edited-source-in-place/` | FAIL | `source_unchanged_not_character` | `SOURCE_PARENT_CHANGED ParentClass=` | `source_has_no_flashlight` | #3 original mutated |
| `hero-missing-body-and-health/` | FAIL | `hero_retains_body_component` | `HERO_BODY_COMPONENT_MISSING names=` | `hero_retains_health_100` | #4 copy gutted / rebuilt from blank |
| `default-brightness-point-light/` | FAIL | `hero_flashlight_is_cone_light` | `HERO_FLASHLIGHT_NOT_CONE class=` | `hero_flashlight_intensity_12000` | #5 default-shaped light |

Why each "Also fails" entry is expected and does **not** make the
discrimination muddy (prose on purpose — a table here would re-register the
labels and blank their substrings):

- `copy-without-character-base/` also fails
  `hero_flashlight_attach_parent_is_mesh`
  (`HERO_FLASHLIGHT_ATTACH_PARENT_WRONG parent=`): an inert object owns no
  inherited animated mesh, so the light cannot be on one. Two independent
  checks catching the same defect is deliberate (spec anti-gaming #1).
- `edited-source-in-place/` also fails `source_has_no_flashlight`
  (`SOURCE_HAS_FLASHLIGHT names=`): the variant reparents **and** lights the
  source, so both source-side checks fire.
- `hero-missing-body-and-health/` also fails `hero_retains_health_100`
  (`HERO_HEALTH_NOT_100 value=`): the same "rebuilt from blank" defect drops
  both carried-over facts.
- `default-brightness-point-light/` also fails
  `hero_flashlight_intensity_12000` (`HERO_FLASHLIGHT_INTENSITY_WRONG value=`):
  the engine default is `5000` (`LocalLightComponent.cpp:13`), so an untouched
  light fails the brightness check too.

Coverage note (bounded, argued from the named checks rather than run as
separate submissions):

- A hero built **from a blank walking-character asset** that *does* re-add
  `Body` and `Health = 100` is an ACCEPTED solution, not a variant — it
  satisfies every observable at strictly more cost (spec anti-gaming #4).
- A hero whose light is correctly attached but left at the engine's default
  brightness dies at `hero_flashlight_intensity_12000`
  (`HERO_FLASHLIGHT_INTENSITY_WRONG`), the same gate
  `default-brightness-point-light/` exercises as its secondary failure.
- A hero left in an uncompiled state dies at `hero_compiles_up_to_date`
  (`HERO_NOT_UP_TO_DATE`); no variant is authored for it because producing that
  state deliberately requires hand-editing a `.uasset`'s transient compile
  state, which is not reliably authorable.

## What is missing (this matrix cannot run until these exist)

**I cannot author `.uasset` binaries from a text-only track.** Six binaries are
needed. Each variant folder holds a `README-MISSING-ASSETS.md` at the exact
path the `.uasset` must occupy, describing property-by-property what to author;
**delete that README in the same commit that lands the real asset.** The full
property-level spec for the baseline and the reference is `../notes.md`.

| # | Path | What it must be |
|---|---|---|
| 0 | `UE-projects/ThirdPerson/Content/Tasks/t1-hero-blueprint-copy-with-flashlight/BP_Source.uasset` | the **baseline** shipped in the substrate (not a submission). `notes.md` §1 |
| 1 | `../reference/Content/Tasks/…/BP_Hero.uasset` | the **reference**. `notes.md` §2 |
| 2 | `copy-without-character-base/Content/Tasks/…/BP_Hero.uasset` | variant. See that folder's README |
| 3 | `flashlight-on-root/Content/Tasks/…/BP_Hero.uasset` | variant |
| 4 | `edited-source-in-place/Content/Tasks/…/{BP_Source,BP_Hero}.uasset` | variant — **two** assets (this is the only leg that overlays `BP_Source`) |
| 5 | `hero-missing-body-and-health/Content/Tasks/…/BP_Hero.uasset` | variant |
| 6 | `default-brightness-point-light/Content/Tasks/…/BP_Hero.uasset` | variant |

Every variant except #4 must ALSO ship an unmodified copy of the baseline
`BP_Source.uasset`? **No** — deliberately not. `apply_submission` is a
copy-only overlay with no wipe, so any asset a submission does not carry is
simply the substrate's own committed baseline. Only the variant that must
*change* `BP_Source` overlays it.

## How to run (deterministic verifier, no agent, no tokens)

```sh
cb discriminate --task bp/t1-hero-blueprint-copy-with-flashlight
```

Per-leg fallback while iterating on one variant (a short `--workdir` dodges
Windows MAX_PATH; use the `py` launcher — this box's `py -3.12` does not
resolve):

```sh
UE='<UE-root>'
py tools/verify-single/run_task.py \
    --task tasks/bp/t1-hero-blueprint-copy-with-flashlight/task.md \
    --submission tasks/bp/t1-hero-blueprint-copy-with-flashlight/discrimination/flashlight-on-root \
    --ue-root "$UE" --workdir C:\cb\wd\kv5var       # expect exit 1
```

Then open the workdir's `report.json` and the `L2I` log it names, find the
`CRAFTBENCH-INTROSPECT-JSON-START` block, and confirm the failing check's raw
`detail` contains this table's "Expected substring" cell.

**L2I graders are read from the LIVE working tree** (`registry.py:312` resolves
`introspect_root = _VERIFY / "introspect"`), unlike L2 fixtures which come from
git HEAD. So iterating on `hero_blueprint_copy_with_flashlight.py` needs no
commit — but the `.uasset` files DO need committing before a non-`--wip` grade
sees them (`run_task` materializes the substrate from git HEAD).

## Status

- Authored 2026-07-27 from the spec, text-only track. **Never executed against
  a real editor** — no leg has run in UE, because no `.uasset` exists yet.
- **Round-2 fixes landed 2026-07-27** (plan §13.1/§13.2, track F1). Every one of
  the six negative legs now parses out of this file with a **non-empty,
  backtick-free** substring, and every substring is proven to be a literal the
  introspect script actually prints — simulated offline against a fake
  `unreal` module and joined through the REAL
  `discriminate.parse_matrix` + the REAL `layers/l2_introspect` parser by
  `tools/verify-single/tests/test_introspect_hero_blueprint.py` (13 tests; 11
  of them were RED against the pre-fix files). That is the LOGIC oracle, not
  an engine oracle.
- **Still missing, in order:** (1) the six `.uasset` binaries below — nothing
  here can run in UE without them; (2) a live-editor confirmation of the UE
  API names the offline fake cannot check (`is_inherited_component`,
  `is_native_component`, `get_attach_parent`, and which spelling of
  `Health`/`Mesh`/`intensity`/`status` `get_editor_property` resolves — the
  script now tries both spellings, but only an editor settles it); (3) the
  `discriminate.py` last-resort backtick strip (track F2) — this file no
  longer *depends* on it, but every future L2I MATRIX will hit the same trap
  until it lands.
- Blocked additionally on `tools/verify-single/tests/test_verdict_taxonomy.py:79`
  (`test_every_shipping_spec_declares_only_landable_gating_layers`), which
  asserts every spec on disk is exactly `("L1","L2")` and therefore fails as
  soon as this spec exists. Plan §9.1 assigns replacing that equality with a
  landability assertion to Phase 1.

## Requirements table (checklist §7, the mandatory soundness artifact)

Layers are `[L1, L2I]` — there is no L2 fixture; every enforcing gate below is a
named check emitted by the verifier-owned grader
`tools/verify-single/introspect/hero_blueprint_copy_with_flashlight.py`, and on
every ENFORCING-gate row the backticked spans in the gate column are
verbatim-greppable in that grader's source; the two non-gate rows quote the spec
instead — row 6's `[L1, L2I]` is task.md front matter (line 8) and row 16's
`saved` sits inside the quoted task.md heading "Why `saved` is not a separate
check" (line 237), neither appearing in the grader.
Most failing details are contiguous source literals; rows marked **(composed)**
name gates whose detail is runtime-assembled by `%`-interpolation — the bare
token literal is formatted together with an interpolated tail (`"%s %s" %
(HERO_MISSING_TOKEN, ASSET_HERO)` at line 578, `"... %s" % _parent_tags(...)` at
lines 606/765, `"... %s" % report` at line 707 where the report string begins
`parent=` at line 508) — so for those rows only the token stem is backticked;
the emitted detail still carries the joined span the matrix above joins on. L1
(UBT exits 0
for both ThirdPerson targets) is a precondition only — the submission is
content-only, so L1 carries no correctness token; the 13-check L2I denominator is
constant on every leg, so "skipped" below means "the check reports the fan-out
root-cause token instead of its own", never "the check vanished".

| # | Prompt requirement | Asserted | Enforcing gate — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | a second asset named `BP_Hero` exists in that same folder (`Content/Tasks/t1-hero-blueprint-copy-with-flashlight/`) | fully | `hero_asset_exists` — `HERO_ASSET_MISSING` (composed; the `/Game/Tasks/` tail is interpolated from `ASSET_HERO`) | unconditional (first hero-side gate); a raised existence probe emits `HERO_ASSET_PROBE_ERROR ` instead — an error token no matrix row credits | nothing on placement — the pre-declared content path IS the lookup key, so a `BP_Hero` authored anywhere else simply reads as missing |
| 2 | `BP_Hero` begins as an exact copy of `BP_Source` | partially — operationalized as exactly the two carried facts of rows 3–4 | rows 3–4 (`HERO_BODY_COMPONENT_MISSING names=` / `HERO_HEALTH_NOT_100 value=`) | as rows 3–4 | building `BP_Hero` from a blank and re-adding `Body` + `Health = 100` is an ACCEPTED solution (spec anti-gaming #4, deliberate); no other byte of the baseline need be carried across |
| 3 | the copy still carries a part named `Body` | fully, by NAME only | `hero_retains_body_component` — `HERO_BODY_COMPONENT_MISSING names=` | `BP_Hero` absent (detail fans out to the composed `HERO_ASSET_MISSING` root cause); a broken subobject walk emits `HERO_BODY_WALK_ERROR raised ` (error token, never credited) | `Body` may be ANY component class with any mesh, parented anywhere in the hierarchy — the cube shape, engine-primitive mesh and under-root placement of the baseline are not re-checked |
| 4 | the copy still reports `Health` as 100 | fully (float, +/-0.01) | `hero_retains_health_100` — `HERO_HEALTH_NOT_100 value=` | `BP_Hero` absent (fan-out); an unreadable property emits `HERO_HEALTH_READ_ERROR raised ` | only the reflected default value is read — the variable's category, editability and blueprint-visibility are free |
| 5 | `BP_Hero` is a fully walking, player-controllable figure — structural operationalization: its generated class is the engine walking-character class or a subclass | structurally (class-ancestry proxy; the spec argues this IS the graded property) | `hero_parent_is_character` — `HERO_PARENT_NOT_CHARACTER` (composed; the `ParentClass=` tail is interpolated by `_parent_tags()`) | `BP_Hero` absent (fan-out); an unloadable generated class emits `HERO_PARENT_CDO_UNAVAILABLE ` (error token); a raised parent read emits `HERO_PARENT_READ_ERROR raised ` (error token, never credited) | any `Character` subclass passes, including the substrate's own — deliberate (spec: "Why the parent check accepts subclasses"); the behavioral residue is row 6 |
| 6 | placed in a level and possessed it actually walks, jumps and collides (standard humanoid locomotion at runtime) | **partially** (closed 2026-08-19 to the extent a structural layer can) | `hero_locomotion_intact` — `HERO_LOCOMOTION_DISABLED walk= jump= collision=`; an unreadable movement component or capsule FAILS via the same token or `HERO_LOCOMOTION_READ_ERROR raised ` (fail-closed: unreadable is not evidence the ability is present) | row 1 fan-out (`BP_Hero` absent) | **still not asserted:** nothing observes the hero MOVE — `layers: [L1, L2I]`, no PIE world runs, so this is a defaults read and not a locomotion test. What it now rejects is every way the ability is switched OFF while the class still derives from `ACharacter`: movement component absent, `MaxWalkSpeed` 0, `JumpZVelocity` 0, or the capsule set to `NoCollision` — the exact crippled-`Character` submission that used to score full marks. The bounds are FLOORS (>= 1.0), not target values: the prompt names no speeds, so no number the agent was never given is asserted |
| 7 | it gains the animated humanoid body part such a figure comes with | indirectly — only as row 10's demand that the Flashlight's attach parent be the INHERITED (`is_inherited_component`/`is_native_component`) `SkeletalMeshComponent` named `Mesh`/`CharacterMesh0` | `hero_flashlight_attach_parent_is_mesh` — `HERO_FLASHLIGHT_ATTACH_PARENT_WRONG` (composed; the `parent=` tail heads `_attach_parent_report`'s interpolated report) (row 10's gate; there is no standalone hero-has-mesh check) | the `Flashlight` subobject is absent — the fact goes entirely unchecked (fan-out `HERO_FLASHLIGHT_MISSING names=`, the submission is already failing there) | the mesh COMPONENT's existence/type/inheritedness is gated, but no skeletal-mesh ASSET or animation blueprint need be assigned — an empty, invisible, never-animating mesh component satisfies it ("animated humanoid" is never verified) |
| 8 | a light named `Flashlight` exists on `BP_Hero` | fully, by NAME | `hero_has_flashlight_component` — `HERO_FLASHLIGHT_MISSING names=` | `BP_Hero` absent (fan-out); broken walk emits `HERO_FLASHLIGHT_WALK_ERROR raised ` | existence is name-only here; that it is a LIGHT at all is row 9's job — a non-light component named `Flashlight` passes this row and dies at row 9 |
| 9 | the light is cone-shaped (a beam, not an omni glow) | fully, fail-closed | `hero_flashlight_is_cone_light` — `HERO_FLASHLIGHT_NOT_CONE class=` | `BP_Hero` absent (fan-out to the composed `HERO_ASSET_MISSING` root cause) or `Flashlight` absent (fan-out); both probes broken emits `HERO_FLASHLIGHT_CONE_TYPE_PROBE_ERROR class=` (error token); a raised cone read emits `HERO_FLASHLIGHT_CONE_READ_ERROR raised ` (error token, never credited) | any spot-light subclass, or any component whose readable outer cone angle sits in (0, 90] — cone width, color and attenuation radius are free |
| 10 | mounted directly beneath the inherited animated body part — not beneath the root and not beneath the cube `Body` | fully — three independent positive facts: parent name in {`Mesh`, `CharacterMesh0`} AND parent is a `SkeletalMeshComponent` AND parent is inherited/native (an agent-authored impostor named `CharacterMesh0` is none of these); two corroborating reads can only ADD a failure | `hero_flashlight_attach_parent_is_mesh` — `HERO_FLASHLIGHT_ATTACH_PARENT_WRONG` (composed; `parent=` heads the interpolated report) | `BP_Hero` absent (fan-out to the composed `HERO_ASSET_MISSING` root cause) or `Flashlight` absent (fan-out); an unevaluable type probe emits `HERO_FLASHLIGHT_ATTACH_TYPE_PROBE_ERROR ` (harness token, never credited); a raised attach read emits `HERO_FLASHLIGHT_ATTACH_READ_ERROR raised ` (error token, never credited) | socket choice, relative transform and beam DIRECTION are free — a flashlight aimed backwards or up passes; "the beam follows the body as it animates" is inferred from attachment alone, never observed |
| 11 | its brightness is set to 12000 | fully (+/-0.5; deliberately non-default — engine default is 5000) | `hero_flashlight_intensity_12000` — `HERO_FLASHLIGHT_INTENSITY_WRONG value=` | `BP_Hero` absent (fan-out to the composed `HERO_ASSET_MISSING` root cause) or `Flashlight` absent (fan-out); unreadable property emits `HERO_FLASHLIGHT_INTENSITY_READ_ERROR raised ` | intensity UNITS are unchecked — 12000 unitless vs 12000 candela are very different beams and both pass; every other light property is free |
| 12 | `BP_Source` is still inert (was not itself made the walking figure) | fully for the named property | `source_unchanged_not_character` — `SOURCE_PARENT_CHANGED` (composed; the `ParentClass=` tail is interpolated by `_parent_tags()`) | never — runs even when `BP_Hero` is missing entirely; a deleted/missing `BP_Source` fails with `SOURCE_ASSET_MISSING ` (alternate uncreditable token — the check still reports); an unloadable source class emits `SOURCE_PARENT_CDO_UNAVAILABLE ` (fail-closed error token, not a pass); a raised source read emits `SOURCE_PARENT_READ_ERROR raised ` (error token, never credited) | reparenting `BP_Source` to any NON-Character class (`Pawn`, another actor type) passes — only Character-ancestry counts as "changed" |
| 13 | `BP_Source` still carries no light | partially — the gate keys on the NAME `Flashlight` only | `source_has_no_flashlight` — `SOURCE_HAS_FLASHLIGHT names=` | never — runs independently of `BP_Hero`; a deleted/missing `BP_Source` fails with `SOURCE_ASSET_MISSING ` (alternate uncreditable token — the check still reports); a broken/empty subobject walk RAISES and emits `SOURCE_WALK_ERROR raised ` (fail-closed — an empty walk is never scored as "no light found") | a light added to `BP_Source` under any other name (`Torch`, `Spot`, …) passes — "no light of any kind" is asserted as "no subobject named Flashlight" |
| 14 | `BP_Source` must be unchanged in every OTHER respect (its `Body`, its `Health = 100`) | **partially** (closed 2026-08-19) | `source_retains_body_and_health` — `SOURCE_BODY_MISSING` / `SOURCE_HEALTH_CHANGED value= expected=`; a broken walk or an unreadable `Health` FAILS via `SOURCE_BASELINE_READ_ERROR raised ` (fail-closed — this is a negative claim, so unreadable must never score as "unchanged") | never — the `source_*` checks run whether or not `BP_Hero` exists | the prompt ships `BP_Source` as "an inert thing with a cube body part named `Body` and a numeric value named `Health` set to 100" and requires it "unchanged when you are done". Sampling was two properties (parent class, no light), so an overlaid `BP_Source` with `Health` rewritten or `Body` deleted passed both. Those two facts are now asserted on the ORIGINAL as well as the copy, at zero extra asset loads — the walk and the CDO are the ones `source_has_no_flashlight` already did. **Residual:** "every OTHER respect" is still not a byte comparison — junk components added to `BP_Source` are invisible, and only these two named facts are sampled |
| 15 | `BP_Hero` must compile cleanly | fully, warnings tolerated | `hero_compiles_up_to_date` — `HERO_NOT_UP_TO_DATE status=` | `BP_Hero` absent (fan-out); unreadable status emits `HERO_COMPILE_READ_ERROR raised ` | `BS_UpToDateWithWarnings` passes (the gate substring-matches `UP_TO_DATE` on the status read off the freshly loaded asset) — "cleanly" tolerates warnings, disclosed in the spec |
| 16 | both assets must be saved | fully, by the substrate model | not a gate — the runner overlays committed file bytes onto a clean substrate, so unsaved editor state never reaches the grader; an unsaved edit presents as the baseline bytes and fails the content checks above (spec: "Why `saved` is not a separate check") | unconditional | nothing |

Holes found by this table (escalation, not paper-over — checklist §7 doctrine):

- **Row 6 (NOT ASSERTED):** the runtime half of "fully walking,
  player-controllable" has no gate at any layer — a locomotion-crippled
  `Character` subclass grades a clean PASS. Closing it would take an L2 leg the
  spec deliberately declined ("there is nothing to observe over time"); the
  spec's own operationalization is row 5, but the prompt promises behavior the
  verifier never watches.
- **Row 14 (NOT ASSERTED):** "`BP_Source` must be unchanged" is sampled at
  exactly two properties. Cheap close: re-assert `Body` and `Health == 100` on
  `BP_Source` with the same reads the hero side already uses (two more checks,
  denominator 13) — the read routes are already proven.
- **Rows 7/13 (partial, recorded here for the record):** "animated humanoid"
  never verifies a skeletal-mesh asset or anim BP is assigned, and the
  source-side "no light" gate is name-keyed — both are one-read extensions of
  existing checks if the owner wants them.

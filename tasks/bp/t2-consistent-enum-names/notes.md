# t2-consistent-enum-names — implementor notes + decision record

Authored from the **rename-lane design** (an internal design note, not
shipped; the enabling `allow_redirectors` verifier flag landed at `f221cf0`).
This change-set is the **text half
only**: spec, grader, offline oracle, matrix, authoring script + runner. The
**binary half** (the committed BASELINE — four misnamed enums + two
referencing Blueprints in the substrate — plus the reference and two
variant `.uasset` sets) is authored by the `authoring/` script in a later
headless boot; nothing here has run against a live editor yet, and §5 is
the calibration record for the leg that will.

## Provenance

- Source: an earlier internal task list (not shipped) — an asset-naming row.
  The design note records the source row's Verification-cell checks 1 and 3
  (old-asset absence; zero-redirector cleanup) as **unimplementable for ANY
  overlay-based harness** — divergences recorded here, not silently taken.
- Disposition history: the import plan held the row at "still needs overlay
  deletion"; the design REFUTED the redirector-signature
  hypothesis from engine source, replaced it with the tri-state closure,
  narrowed O2 to genuinely deletion-shaped rows, and shipped the
  `allow_redirectors` flag as the entire harness change. Owner decisions
  D8 (substrate) and D9 (landing cadence) govern this import.

---

## 0. DECISION RECORD (every baked-in choice, with the alternative it beat)

1. **Id `t2-consistent-enum-names`.** The design pencilled
   `t2-enum-naming-refactor`; "refactor" names the OPERATION and the id is
   agent-visible in the content path (the imported set's README id law: name the
   outcome, not the operation — the same law that renamed the source row's
   `enhanced-input` id). The chosen slug names the end state: the folder's
   enum names are consistent with the convention. Substring/prefix
   collision scan run 2026-07-30 against all **26** shipping ids (folder
   names under `tasks/*/`) and every `tasks/CATALOG.md` row, both
   directions: **no collision**, and no shipping id is a substring of it.
   Parallel-author hazard noted (three other rows are being authored in
   disjoint paths this same day): the slug's `consistent-enum` stem is
   distinctive enough that an accidental collision is implausible; the scan
   must be RE-RUN at commit time per blockb-triage's own instruction.
   *Alternatives rejected*: `t2-enum-naming-refactor` (operation leak),
   `t2-asset-naming-audit` (faithful to the source row, but "audit" misdescribes a
   mutation task and collides conceptually with the R12-R14 answer lane).
   Residual tension recorded: "enum-names" says the task touches enum
   NAMING — unavoidable (the prompt's whole subject is the convention) and
   route-free (it names WHAT is true after, not how, and no class/tool).
2. **Tier T2.** Multi-asset coordination (four renames whose correctness is
   defined by two OTHER assets' references surviving) + one system concept
   (reference-preserving rename semantics). More than a T1 single-asset
   edit (dawn-fog), less than a cross-family T3; matches the weapon row's
   T2 shape. The design doc itself proposed `t2-`.
3. **Substrate `ThirdPerson`.** Owner decision **D8** (plan §3.1b names R4
   explicitly: "all Block-B rows + R4 on ThirdPerson"). Content-only task;
   the shared L1 leg and set convention win.
4. **Baseline enums ship with FACTORY-DEFAULT enumerators** (baked
   decision (a) of the authoring instruction). Stock Python cannot author
   enumerator content — spike-facts §E: `EnumFactory`/`create_asset`
   PROVEN, but **no** enumerator read/write surface exists (no
   UserDefinedEnumLibrary, no EnumEditorLibrary) — and the design's
   anti-gaming entry 5 already accepts enumerator content as ungraded. The
   distinct-enumerators nicety is DROPPED. *Alternative recorded, deferred*:
   authoring enumerators through the Aura MCP `edit_enumeration` lane
   (would need the AuraSandbox promotion step; grading must stay MCP-free
   regardless, so the check would still be unbuildable — which is why
   deferral is honest rather than lazy).
5. **BP-variable authoring route is probe-first** (baked decision (b)).
   The graded fact is only the BP -> enum HARD DEPENDENCY, so the script
   verifies every attempt by that exact fact (registry `get_dependencies`
   after compile+save **and a forced rescan** — see decision #16) instead of
   trusting any API's return value. Probed route:
   `BlueprintEditorLibrary.add_member_variable` with an `EdGraphPinType`
   built for pin category `"byte"` then `"enum"` (BP enum variables are
   byte-category pins with the enum as sub-category object).
   **RESOLVED 2026-07-30 (§5, spike 3): the route is STOCK PYTHON — the
   Aura MCP `bp_agent` fallback is NOT needed and is no longer recorded as
   this row's path.** What was unproven was never `add_member_variable`; it
   was how to BUILD the pin. `unreal.EdGraphPinType()` constructs, but its
   properties are **protected**, so `set_editor_property("pin_category", …)`
   raises `Failed to find property` / `is protected and cannot be set` —
   that is what the first script died on. The pin is built by **text import**
   on the struct instead (`pin.import_text('(PinCategory="byte",
   PinSubCategoryObject="/Game/…/E_Kind.E_Kind")')`). The two-candidate loop
   and `RENLANE-BPVAR-ROUTE-UNAVAILABLE` stay, with a narrowed meaning: the
   abort now says the *proven* route regressed, not that it is unknown.
6. **The tri-state closure is the graded signature** (the design's central
   correction — its own VERDICT refutes the original "old path must be a
   redirector" hypothesis from engine source). C5-C8 accept EITHER a
   redirector with the exact expected target OR a zero-referencer orphan;
   C9-C10 close the loop through verified redirectors only; C11 pins the
   folder set. Every lazy/cheap-wrong state fails at least one leg in BOTH
   mechanical outcome lanes. *Alternative rejected*: grading "old file
   absent" — inexpressible under the copy-only overlay (O2), which
   unconditionally resurrects committed baseline files.
7. **The grader loads NOTHING** — every fact is a registry read. The
   contract's binding rule for `allow_redirectors` graders only forbids
   loading through ALLOWED OLD paths, but complying by construction (no
   `load_asset` anywhere) removes the whole class of follow-the-redirector
   hazards and needs no reviewer judgment call. *Alternative rejected*:
   class-checking new paths via registry then loading them for extra
   asserts — nothing loadable is graded here, so the load would be dead
   surface area.
8. **Dead-gate audit** (house law; mirrored in the task spec): every check
   is LIVE — the committed baseline grades exactly **0/11** (pinned
   in-process by the authoring script AND offline by the fake oracle; the
   baseline is the empty leg's graded state). No check equals a default or
   pre-existing state. Honest coverage GAP, recorded (**amended 2026-07-30,
   §5 RESOLVED-NEGATIVE (c)**): the redirector arm of C5-C8 has **no live
   coverage in either direction** — the residue is not manufacturable
   headless (three dead routes), so the planned `redirector-wrong-target/`
   FAIL leg was retired unauthored and the `laneb-redirector-pass` PASS
   calibration shares the same dead route. Both directions are pinned by the
   offline oracle on the REAL grader
   (`test_lane_b_correct_redirector_passes`,
   `test_wrong_target_redirector_fails_by_name`) and by nothing else. The
   orphan arm is live-covered by the reference itself.
9. **C11 counts PACKAGES, not AssetData entries.** Registry queries can
   return same-package duplicate entries (the `SKEL_<Name>_C` correction,
   spike-facts §C / 2026-07-30 corpus boot); the folder inventory collapses
   to a package-name set before comparing. Consumers must never count raw
   entries.
10. **Probe-failure taxonomy: CONSERVATIVE** (uncredited-`*_PROBE_ERROR`
    house law; pixel-formats decision precedent). The script's
    `UNCREDITED_TOKENS` tuple enumerates every verifier-side failure token
    — including `ENUM_OLD_ASSETDATA_UNAVAILABLE`, which marks a state
    (nothing at an old path) that NO agent action can cause under the
    copy-only overlay, so crediting it would credit a harness surprise.
    The offline oracle asserts the tuple is disjoint from every MATRIX
    substring.
11. **DestinationObject tag parse is tolerant, and the exact 5.8 shape is
    an authoring-boot deliverable** (design open question). Parse accepts
    the `Class'/Game/Path.Name'` export form and a bare object path; a
    surprise shape routes to `ENUM_OLD_TAG_UNPARSEABLE` (uncredited), and
    the authoring script prints the RAW tag text
    (`RENLANE-CAL tag-shape ...`) from the first manufactured redirector so
    the parse can be tightened from evidence, not guesswork. A CHAINED
    redirector needs no special case: its one-hop tag equals the
    intermediate and fails the exact-target compare.
12. **Variant selection: 2 committed legs** (+ implicit empty + reference =
    4 legs). The design §4 set was three; `redirector-wrong-target` was
    **retired unauthored 2026-07-30** (§5 RESOLVED-NEGATIVE (c): the residue
    is not manufacturable headless, so the leg could never be authored).
    What ships: `duplicate-not-rename` (the closure's reason to exist —
    copies pass every names-only check) and `one-left-behind` (partial
    laziness; hits the ItemRarity lane on four named checks). NOT spent as
    folders, pinned offline instead: **both directions of the redirector
    branch** (Lane B correct-target PASSES; wrong-target FAILS by name —
    this is now the ONLY coverage of that branch), chained redirector,
    forged/garbage tag, wrong-class impostor, folder junk (all argued in the
    MATRIX coverage note). The cost, stated plainly: the `allow_redirectors`
    flag no longer gets an end-to-end exercise from a real submission on
    this row; the flag keeps its own harness unit tests
    (`test_asset_integrity.py::TestAllowRedirectorsFlag`).
13. **The wrong-target variant's decoy lives at the task ROOT**
    (`DecoyEnum`, not inside `Enums/`), so C11 stays green and the leg
    fails on exactly two named checks — the sharpest possible leg. The
    manufacture ORDER (three clean renames FIRST, then chmod + decoy
    rename) prevents a later fixup-resave from rewriting BP_RefA's
    WeaponType import and muddying the expected vector (the resave
    ambiguity the design flagged).
14. **Prompt: convention + two worked examples on NON-task names; the new
    names are NEVER stated.** Deriving `E_WeaponType`/`E_AmmoKind`/
    `E_DamageType`/`E_ItemRarity` is the agent's job; the
    `enum_fire_mode -> E_FireMode` example pins the drop-the-redundant-word
    rule for `enum_DamageType` (the design's cross-model ambiguity
    question — to be confirmed in the calibration bench with a concrete
    before/after example, per the memory note on task-goal phrasing). The
    four OLD names + folder + the two BP names ride the precedented
    named-asset exception with the justification paragraph in the spec.
    The prompt is SILENT on redirectors (leaving one: unachievable on
    demand; cleaning one: ungradable; the tri-state tolerates both).
15. **`allow_redirectors` front matter uses the task-scoped form the flag
    enforces**: exactly the four old packages, all under
    `/Game/Tasks/<id>/` (spec.py rejects anything else with exit 2). The
    new paths are deliberately NOT listed — a redirector parked at a new
    path still dies `REDIRECTOR_SUBMITTED` in the preamble, which is part
    of anti-gaming entry 2's defense.
16. **The forced registry rescan lives in the AUTHORING script, NOT in the
    grader** (2026-07-30, from the live fact in §5: dependency and referencer
    edges are **scan-time, not save-time**). The authoring script's `grade()`
    calls `rescan()` as its first statement, so no in-process grade can
    forget it, and `_rename` rescans before reading an old path's
    disposition. The grader
    (`tools/verify-single/introspect/consistent_enum_names.py`) deliberately
    carries **no** `scan_paths_synchronous`.
    *Why not add a defensive one there too* (the tempting symmetric move):
    on the real lane the submission is overlaid BEFORE the editor boots, so
    the startup scan has already built every edge the grader reads — the
    rescan would buy exactly nothing, while a `force_rescan=True` inside the
    verdict path is a new mutation of verifier state on the one code path
    that must never manufacture a false negative, plus a new probe-failure
    surface needing its own `UNCREDITED_TOKENS` entry. The only lane that
    needs the rescan is in-process authoring-time grading, and that lane's
    caller owns it unconditionally. The decision is pinned both ways by
    `test_introspect_consistent_enum_names.py`:
    `test_grader_carries_no_forced_rescan` (nobody adds one to the grader
    without re-reading this entry) and
    `TestAuthoringScriptRoutes::test_grade_rescans_before_every_in_process_grade`
    (nobody removes it from the caller). *Alternative rejected*: teaching the
    grader to rescan and dropping it from the authoring script — that puts a
    write-shaped call in the verdict path to serve a non-graded consumer.
    Also confirmed while resolving this: the grader passing a default
    `unreal.AssetRegistryDependencyOptions()` is **CORRECT and must not
    change** — its defaults already carry
    `bIncludeSoftPackageReferences=True` + `bIncludeHardPackageReferences=True`
    (`export_text` confirmed live), and a shipped Blueprint returns its full
    dependency set under every flag combination; the options object was never
    the reason a freshly-authored Blueprint read zero edges.

---

## 1. BASELINE assets (committed substrate content; authored by phase 1)

**Paths on disk (to be authored by `authoring/run_author_all_assets.sh` —
NOT yet on disk in this change-set):**

`UE-projects/ThirdPerson/Content/Tasks/t2-consistent-enum-names/`

| file | content |
|---|---|
| `Enums/WeaponType.uasset` | UserDefinedEnum, factory-default enumerators |
| `Enums/E_ammo_kind.uasset` | UserDefinedEnum, factory-default enumerators |
| `Enums/enum_DamageType.uasset` | UserDefinedEnum, factory-default enumerators |
| `Enums/ItemRarity.uasset` | UserDefinedEnum, factory-default enumerators |
| `BP_RefA.uasset` | Actor Blueprint; variables `WeaponKind` (typed WeaponType), `AmmoKind` (typed E_ammo_kind) |
| `BP_RefB.uasset` | Actor Blueprint; variables `DamageKind` (typed enum_DamageType), `RarityKind` (typed ItemRarity) |

Baseline-design law from the design doc, honoured: **no source/target pair
differs only by case** (Windows case-insensitive FS + the rename manager's
case-only branch would collapse old/new into one file), and the baseline
carries **no soft references and no native-CDO references** to the enums
(keeps the rename manager's soft-path fixup and `:796` branch inert). The
BP variable names carry no graded meaning — only the hard dependency does.

The baseline **is** the empty leg's graded state and reads exactly **0/11**.

## 2. REFERENCE solution

Lane A (the stock outcome, per engine source): all four enums renamed via
reference-fixing rename; both BPs resaved importing the new packages; old
files DELETED — so the reference overlay ships **6 files** (4 new enums + 2
BPs) and NO old-path files. In the graded workdir the baseline old enums
resurrect as ORPHANS with zero referencers — the tri-state's orphan branch,
part of the expected PASS.

Expected reference verdict: **L2I `11/11`, overall PASS** — asserted
in-process by the authoring script (after overlay simulation) before it
ships a single file.

## 3. Discrimination variants

Two variant overlays + the implicit empty leg, specified in
`discrimination/MATRIX.md` (a third, `redirector-wrong-target/`, was retired
unauthored 2026-07-30 — §5 RESOLVED-NEGATIVE (c)). **The folder tree is the
variant-count authority** (playbook trap); until the binary half lands the
authority is the MATRIX table + the authoring script's leg list, which the
offline suite cross-checks.

| variant | the one deviation | expected named fail |
|---|---|---|
| `duplicate-not-rename/` | 4 fresh correctly-named enums; BPs untouched | `BP_DEP_OLD_NAME_LIVE_BP_RefA old=` (+ 4x still-referenced, BP_RefB) — 5/11 |
| `one-left-behind/` | 3 renamed; `ItemRarity` untouched | `ENUM_NEW_MISSING_E_ItemRarity path=` (+ its old path, BP_RefB, inventory) — 7/11 |

## 4. Pre-flight before the first graded leg

1. **Registry reconciliation is deliberately NOT in this change-set** (per
   the authoring instruction: CATALOG row, count claims, the imported set's README
   row-map — all after validation, batched by the owner).
2. **Binary half**: run `authoring/run_author_all_assets.sh` (one headless
   boot; every state graded in-process; substrate ends holding EXACTLY the
   committed baseline). Then commit baseline + legs, then
   `cb discriminate --wip --task bp/t2-consistent-enum-names` (4 legs),
   then the git-HEAD certification re-run after the commit.
3. **The baseline must be COMMITTED before any non-`--wip` grade**: the
   runner materializes the substrate from git HEAD, so an uncommitted
   baseline means the graded workdir has NO old-path files and C5-C8 would
   hit the uncredited `ENUM_OLD_ASSETDATA_UNAVAILABLE` lane (plan §11
   "commit baselines as soon as they exist" — fairness isolation also moves
   untracked `Content/Tasks/<id>/` aside on later drives of OTHER tasks).
4. **`status_gen.py::classify_tasks` quirk** (the imported set's README): it probes for
   `t2_consistent_enum_names.py` while the grader is
   `consistent_enum_names.py` — harmless once the dated validation row exists.

## 5. Calibration record — the authoring-spike checklist

Everything below is what the offline oracle structurally CANNOT prove;
assume one 5.8 surprise until the reference leg passes (every prior imported
row surfaced exactly one live-contact defect — the `str(FGuid)` /
underscore-fold / DataAssetFactory precedents). The authoring script probes
each item and aborts with a named `RENLANE-*` token rather than shipping
doubtful bytes.

### RESOLVED 2026-07-30 — the two live facts the first authoring boot died on

**(a) `RENLANE-BPVAR-ROUTE-UNAVAILABLE` ("EdGraphPinType pin_category not
settable") — RESOLVED. Blueprint member variables ARE authorable from stock
Python; no MCP lane, and nothing here is impossible.** Live-proven on UE 5.8
at `<UE-root>` (spike 3). `unreal.EdGraphPinType()` constructs fine, but its
properties are **protected**: `set_editor_property("pin_category", …)` raises
`Failed to find property` / `is protected and cannot be set` — that single
call, not the variable API, is what aborted the boot. The working route is
**text import on the struct**:

```python
pin = unreal.EdGraphPinType()
pin.import_text('(PinCategory="bool")')                                # bool
pin.import_text('(PinCategory="byte",PinSubCategoryObject='
                '"/Game/Tasks/<id>/Enums/E_Kind.E_Kind")')             # UDE
unreal.BlueprintEditorLibrary.add_member_variable(bp, "VarName", pin)  # True
```

Note the object-path form: `<package path>.<asset name>` — the **doubled
leaf**, quoted. Verified: `pin.export_text()` reads back
`PinSubCategoryObject="/Script/Engine.UserDefinedEnum'/Game/…/E_Kind.E_Kind'"`
(so a failure to resolve is visible immediately, which is how
`author_all_assets.py::_pin_type` rejects a bad candidate), and
`BlueprintEditorLibrary.get_member_variable_type(bp, "VarName")` harvests the
same pin back off the SAVED Blueprint. Related API confirmed to exist:
`list_member_variable_names`, `get_member_variable_type`,
`change_member_variable_type`, `set_blueprint_variable_instance_editable`,
`remove_unused_variables`. **Any note in this row claiming this needs the
Aura MCP `bp_agent`/`edit_blueprint` lane, or is unachievable headless, is
superseded by this entry** (decision #5 amended in place).

**(b) Dependency edges are SCAN-time, not save-time — every in-process grade
must rescan first.** Live-proven the same day (spikes 4-6). A Blueprint
created AND saved in the same editor session reports **zero** dependencies
(not even `/Script/Engine`) and its referenced enum reports **zero**
referencers, even after `BlueprintEditorLibrary.compile_blueprint` +
`save_asset`. `AssetRegistryDependencyOptions()` is **not** the cause: its
defaults already carry `bIncludeSoftPackageReferences=True` and
`bIncludeHardPackageReferences=True` (`export_text` confirmed), and a shipped
Blueprint returns its 14 deps under every flag combination. The fix:

```python
ar.scan_paths_synchronous(["/Game/Tasks/<id>"], force_rescan=True)
ar.wait_for_completion()
```

After that rescan the enum dependency appears (deps n=1 carrying the enum
package) and the enum's referencers list carries the Blueprint. A REAL grade
is unaffected — submissions are overlaid before the editor boots, so the
edges exist at the startup scan — so this bites only in-process
authoring-time grading, which is exactly what this script does. Wired
accordingly: `rescan()` is the first statement of the authoring script's
`grade()` (un-forgettable), `_rename` rescans before reading an old path's
class/`DestinationObject` tag, `_add_enum_variable` rescans between
compile+save and the dependency read, and the first such read prints the
before/after evidence as `RENLANE-CAL dependency edges are SCAN-time: …`.
A rescan that cannot run is the named abort `RENLANE-RESCAN-UNAVAILABLE` /
`RENLANE-RESCAN-FAILED` — without it no in-process grade means anything.
The GRADER deliberately does not rescan: decision #16 records why, and both
directions are pinned by tests.

### RESOLVED-NEGATIVE 2026-07-30 — the redirector residue is NOT manufacturable headless

**(c) Lane A is CONFIRMED live; the redirector branch of the tri-state has
no live route on this box. Four facts, all from today's authoring boot and
its follow-up probe:**

1. **Lane A confirmed live.** The stock rename lane
   (`EditorAssetLibrary.rename_asset`) with LOADABLE Blueprint referencers
   always fixes the referencers up in memory, resaves them, and **DELETES**
   the old package — `RENLANE-CAL rename ...: old_registered=False
   new_registered=True`, and the registry class at the old path reads
   `None`. **No redirector remains.** This is exactly what the O2 design's
   engine-source reading predicted (`FAssetRenameManager` sets
   `bCreateRedirector` only on fixup-FAILURE conditions), so the design's
   central claim is now live-proven rather than inferred. It also closes the
   old "Lane A referencer fixup live-proven" checklist item.
2. **The chmod read-only-referencer route is DEAD.** Making the referencing
   Blueprint files read-only, expecting `DetectReadOnlyPackages` to force
   `bCreateRedirector`, does not fire headless — the boot aborted with its
   own named token `RENLANE-REDIRECTOR-NOT-CREATED`. (This is the abort
   working as designed: it refused to ship doubtful bytes.)
3. **The unloaded-map-referencer route is DEAD, and the reason is
   structural, not incidental.** The design's other cited route assumed an
   unloaded MAP in the enum's referencer set. A follow-up probe built one: a
   level containing a placed instance of the referencing Blueprint. It
   references the **BLUEPRINT, not the enum** (`level_refs_enum=False`), so
   the enum's referencer set never contains the map, the fixup never has an
   unloadable referencer to fail on, and the rename fixed up and deleted
   cleanly again. Any future attempt must get a map to reference the ENUM
   directly (e.g. a level-blueprint variable or a map-level asset typed to
   it) — the placed-actor shape can never work.
4. **Python cannot construct a redirector directly.**
   `UObjectRedirector::DestinationObject` is a plain unreflected C++ member,
   so there is no `set_editor_property`/factory route to forge one either.

**Consequence — branch (a) of the tri-state is OFFLINE-ONLY.** The
`redirector-wrong-target/` discrimination leg was retired **unauthored**
(the folder was never created) and the row ships **4 legs**: reference +
empty + `duplicate-not-rename/` + `one-left-behind/`. The
`laneb-redirector-pass` calibration phase shares the dead chmod route and so
provides no live coverage either. The grader is **unchanged** — both tri-
state branches, the constant 11-check denominator and the redirector tokens
all stay, because a real agent (source control enabled, a genuinely unloaded
map referencer, or a partially-failing fixup) can still produce the residue
and a grader that dropped the branch would fail a correct submission. Its
logic is pinned by the offline oracle in both directions
(`TestTriStateContract::test_lane_b_correct_redirector_passes` and
`::test_wrong_target_redirector_fails_by_name`), and the
`allow_redirectors` flag's own behavior by
`tools/verify-single/tests/test_asset_integrity.py::TestAllowRedirectorsFlag`.
**This is an open coverage gap in this row's matrix, honestly recorded, not
a closed question**: the authoring script keeps both redirector legs, the
`_rename(..., expect_redirector=True)` capability and the
`RENLANE-REDIRECTOR-NOT-CREATED` abort behind `RENLANE_TRY_REDIRECTOR=1` so
a future engine/SCC configuration can re-attempt the manufacture.

### RESOLVED 2026-07-30 — the TOMBSTONE LAW, and why this row's authoring lane is multi-boot

**This is a reusable authoring-lane law for ANY rename-shaped row, not a
quirk of this task.** It is what the first end-to-end boot died on (the
reference leg graded 8/11 in-process while its files were all present on
disk), and diagnosing it turned up a *second*, more dangerous defect hiding
behind it.

**(d) In-session package DELETE is a one-way door: the registry then lies
about that path in BOTH directions for the rest of the boot.** Deleting a
package in a session — which is exactly what `rename_asset`'s Lane A fixup
does to the old package — leaves the asset registry permanently inconsistent
for that path:

| read surface | after the in-session delete |
|---|---|
| `get_assets_by_path(<folder>)` | **DROPS** the package — forever |
| `get_asset_by_object_path(<old>)` | returns the **STALE pre-delete AssetData**, forever |
| `does_asset_exist(<old>)` | **True**, forever |

Copying the baseline file back at the old path does **not** undo it. Every
resurrection route was tried in a throwaway probe boot and **all failed** to
restore by-path visibility:

- `scan_paths_synchronous([<Enums folder>], force_rescan=True)`
- `scan_paths_synchronous([<task root>], force_rescan=True)`
- the same with `ignore_deny_list_scan_filters=True`
- `scan_files_synchronous([<the exact .uasset file paths>], force_rescan=True)`
- `scan_modified_asset_files([<the exact file paths>])`

each followed by `wait_for_completion()`. **No call restores it.** (Contrast
with fact (b) above: a force-rescan *does* pick up newly CREATED and RESAVED
files. The tombstone is specific to a path the session has deleted.)

The dangerous half is the second row of that table. A grader reading the old
path through `get_asset_by_object_path` gets `class=UserDefinedEnum,
referencers=[]` — which is **exactly the shape of a passing orphan** in this
row's tri-state — so an in-process grade after a rename does not merely
fail spuriously, it **FALSE-PASSES C5–C8 while false-failing C11**. The
8/11 that started this investigation was three real-looking failures sitting
on top of four fake passes. An in-process "overlay simulation" after a
rename is therefore not a weak signal, it is a *misleading* one, and it has
been deleted from the authoring script rather than patched.

**(e) Same-boot multi-leg authoring silently CORRUPTS the shipped bytes.**
Found only because (d) forced a cold-boot check of the harvested files. A
rename leg run *after* an earlier leg's file-level baseline restore renames
against stale loaded objects: the referencer fixup writes Blueprints with
**no enum dependency at all**. The shipped `BP_RefA.uasset` carried `deps=[]`
and `BP_RefB.uasset` carried one of its two — bytes that look fine on disk,
copy fine, and grade **9/11 in a cold boot** with two BP_DEP_UNRESOLVED
failures. In a FRESH boot the identical four renames produce the correct
`BP_RefA=[E_AmmoKind, E_WeaponType]`, `BP_RefB=[E_DamageType, E_ItemRarity]`.
This is the "in-editor state proves too sticky for same-boot restore"
escape-hatch condition the script anticipated before first live contact —
confirmed, and now the default rather than the fallback.

**The fix — the authoring lane is now ONE PHASE PER BOOT** (`RENLANE_PHASE`,
driven by `run_author_all_assets.sh`), and the leg vector is taken in the
REAL graded lane instead of a simulation of it:

1. `baseline` — author + stash the baseline; pin the empty leg 0/11
   (trustworthy: the boot has deleted nothing).
2. `author <leg>` — a FRESH boot on the restored baseline: preflight 0/11,
   mutate, harvest the deliverable into `authoring/.staged/<leg>/`, restore
   the substrate file-level and byte-compare it. **No vector is taken here**
   — per (d), none could be trusted.
3. `verify <leg>` — the runner materializes stashed baseline + a copy-only
   overlay of `.staged/<leg>/` **on disk, before the boot**, so this editor's
   first scan sees every package and no tombstone exists anywhere in the
   session. This is not a simulation of the graded lane, it *is* the graded
   lane (the runner does byte-for-byte the same thing to a workdir). The
   phase asserts the on-disk inventory, grades with **no rescan and no
   mutation**, asserts the exact expected vector + substrings, and only then
   **PROMOTES** `.staged/<leg>/` into `reference/` or `discrimination/<leg>/`.

Doubtful bytes therefore never reach the shipped tree at all: staging is the
refuse-to-ship boundary, and the assertion that opens it is made against the
true graded state. The empty leg gets a verify boot too (no overlay), which
makes it a cold certification of the committed BASELINE bytes.

**Generalization for the next rename-shaped row:** never grade a mutating
leg in the boot that mutated it, and never trust a same-boot restore to
un-mutate the editor. Author in one boot, harvest to staging, grade in a
cold boot whose state was materialized file-level before it started. If a
row's authoring script contains the words "simulate the overlay", it is
measuring the wrong thing.

### Still open (the authoring boot answers these)

- [x] **EnumFactory route re-confirms** on ThirdPerson (spike-proven on
      CraftBenchTemplate: spike-facts §E). Confirmed 2026-07-30: the
      baseline boot created all four UDEs and both Blueprints.
- [x] **Which pin category the enum variables land on** — **`"byte"`**, the
      first candidate, on all four variables; `"enum"` was never reached.
      `export_text` reads back
      `PinSubCategoryObject="/Script/Engine.UserDefinedEnum'/Game/…'"` and
      the hard dependency appears after the forced rescan.
- [ ] **The DestinationObject tag text shape pinned** from
      `RENLANE-CAL tag-shape DestinationObject raw=...` (design open
      question). Tighten `_parse_export_target` if the real shape is
      neither the quoted export form nor a bare object path. **NOTE
      2026-07-30: this now has NO live route at all** — the print only fires
      on a manufactured redirector, and the manufacture is dead (see the
      RESOLVED-NEGATIVE entry below). The tolerant parse stays; the shape
      stays unpinned, and any surprise routes to the uncredited
      `ENUM_OLD_TAG_UNPARSEABLE`, never to a graded semantic failure.
- [x] **Overlay simulation matches the real graded overlay** — **REFUTED and
      RETIRED**; superseded by the tombstone law above. In-session overlay
      simulation cannot reproduce the graded state at all (the restored old
      files never come back to `get_assets_by_path`, and the stale AssetData
      that survives fakes a PASSING orphan). The simulation is gone; the leg
      vector is now taken in a cold `verify` boot whose state was
      materialized file-level before it started. There, the resurrected old
      files DO register as zero-referencer orphans and the reference leg
      reads **11/11**.
- [x] **Same-boot baseline restore holds** — **REFUTED.** The file-level
      restore is byte-perfect, but the *editor* does not un-mutate: the next
      rename leg renames against stale loaded objects and ships Blueprints
      with no enum dependency (fact (e) above). The anticipated
      one-leg-per-boot fallback is now the default architecture, not a
      fallback.
- [x] **Empty + both variants FAIL at their MATRIX substrings** — done
      2026-07-30: `cb discriminate --task bp/t2-consistent-enum-names
      --wip --warm-cache` reports **discriminated: YES**, 4/4 legs
      (reference PASS; empty, `duplicate-not-rename/`, `one-left-behind/`
      each FAIL at its named substring), exit 0. **Still to do: the git-HEAD
      certification re-run** (no `--wip`) once the baseline + the 15 leg
      `.uasset`s are committed.

      Two non-asset traps this run cost a full 15-minute cycle each, both
      worth knowing before the next row's first discriminate:

      1. **A second table in MATRIX.md blanks the legs it names.** Adding a
         cold-boot-results table to the Status section re-registered
         `duplicate-not-rename/` and `one-left-behind/` with no "substring"
         column, so `parse_matrix` overwrote their expectations with an
         empty tuple and both legs came back `FAIL(no-named-assertion)`
         while the assets were perfect. This is *literally* parser trap #1
         at the top of that file. The 10-second check that would have caught
         it, and that is cheaper than any run:

             py -3.13 -c "import sys;sys.path.insert(0,'tools/run-agent');\
             from aura_rig import discriminate as D;from pathlib import Path;\
             print(D.parse_matrix(Path('<MATRIX.md>').read_text('utf-8')))"

         Every row must come back with a NON-EMPTY substrings tuple.
      2. **Do not run anything heavy beside a discriminate.** A first
         attempt returned `FAIL(skipped)` on three of four legs — L1 build
         failures, not grading failures — because the offline test suite was
         running alongside it. That is the documented per-`cl.exe` PCH
         ceiling (`CRAFTBENCH_L1_MAX_PARALLEL`, machine-characterisation
         §2), and it presents as "no discrimination", i.e. as a defect in
         the task rather than in the box. Re-run idle before believing a
         `discriminated: NO`.
- [ ] Measured L2I leg wall-clock recorded here (expected near the set's
      lower bound: registry reads only, no asset loads, no spawn).

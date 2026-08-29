---
id: t2-consistent-enum-names
substrate: ThirdPerson
set: bp
tier: T2
capability_bucket: Asset Management
category: other
layers: [L1, L2I]
introspect: [consistent_enum_names.py]
allow_redirectors: [/Game/Tasks/t2-consistent-enum-names/Enums/WeaponType, /Game/Tasks/t2-consistent-enum-names/Enums/E_ammo_kind, /Game/Tasks/t2-consistent-enum-names/Enums/enum_DamageType, /Game/Tasks/t2-consistent-enum-names/Enums/ItemRarity]
---

# t2-consistent-enum-names

> **Salvage provenance (2026-08-12).** This row was authored 2026-07-30 on
> an internal authoring branch, a branch that was never merged and is now
> abandoned; it reached `tasks/bp/` through the eval-import salvage wave, on
> owner instruction. Two things follow that a reader should not have to
> reconstruct. **(1)** The id is unchanged on purpose: the content path
> `/Game/Tasks/t2-consistent-enum-names/` is serialized inside all 15
> committed `.uasset` binaries, so re-slugging the task would silently
> invalidate the reference and both variants. **(2)** Landing it re-adds a
> path under a tree that commit `ff1756d` had deliberately untracked (it
> also added a `.gitignore` guard, which covers authoring scratch only and
> is untouched here) — that untracking was the correct fix for an
> accidental resurrection, and this is a deliberate one. The verifier
> feature it depends on, `allow_redirectors`, was re-applied by hand onto
> today's verifier rather than cherry-picked; its original form was
> `f221cf0` on the dead branch. Everything below is as authored, except the
> `set:` key, the folder path, and one MATRIX cell cut at a runtime
> placeholder (recorded in `discrimination/MATRIX.md`'s first parser trap).

**The rename lane**: the first task whose deliverable is a **reference-
preserving asset rename**, graded as a **tri-state closure** over asset-
registry state, and the first consumer of the verifier's default-closed
`allow_redirectors` integrity-preamble exception. The
committed baseline ships four **misnamed** enumeration assets under
`Content/Tasks/t2-consistent-enum-names/Enums/` plus two Blueprints whose
variables are typed to them; the agent brings the four names to the
project's convention with everything still working. One verifier-owned
introspect script asserts the closure through **registry reads only** — it
never loads a single asset (the binding contract rule for `allow_redirectors`
graders).

### Provenance and deliberate divergences from the source row

Imported from an earlier internal task list (not shipped): an asset-naming row
from its named-editor-workflow group. The full design history is an internal
design note (not shipped); divergences recorded per its §6:

1. **"None of the old names exist as real assets" -> CUT.** Inexpressible
   under the copy-only overlay (plan O2): a clean UE 5.8 rename DELETES the
   old package (`AssetRenameManager.cpp:2029-2036`) and the overlay then
   RESURRECTS the committed baseline enum at the old path in the graded
   workdir. Replaced by the behaviorally-equivalent "old name is not
   load-bearing" tri-state (checks C5-C8): the old path is EITHER a
   redirector forwarding exactly to its new package OR an orphan with zero
   registry referencers. The old files coming back as orphans is a
   **designed-for state**, not a bug.
2. **"Zero ObjectRedirectors remain" -> INVERTED-AND-SCOPED.** Redirector
   cleanup is ungradable for the same O2 reason (a deleted redirector cannot
   be distinguished from a never-created one) — and a clean rename of this
   baseline leaves none anyway (engine-source proof in the design VERDICT:
   `bCreateRedirector` fires only on fixup-failure conditions this baseline
   avoids). What IS graded: any redirector present at an old path must
   forward EXACTLY one hop to the expected new package. Scope is the task
   folder only (plan §10.3: 544 engine-side redirectors exist; a
   project-wide zero could never pass).
3. **"Recompiling assets produce no compile errors" -> not graded at v1**
   (no proven headless BP-compile-status read; candidate spike noted in the
   design's open questions). C9-C10's dependency closure is the graded
   stand-in.
4. **`/Game/EvalTemplate` -> `Content/Tasks/t2-consistent-enum-names/`**
   per repo convention (the source row path exists nowhere in the repo).
5. **Id.** The design doc pencilled `t2-enum-naming-refactor`; "refactor"
   names the OPERATION and the id is agent-visible in the content path
   (the imported set's README id law: name the outcome, not the operation). Re-slugged to
   the outcome: after the task, the folder's enum names are CONSISTENT.
   Collision scan run 2026-07-30 against all 26 shipping ids and every
   `tasks/CATALOG.md` row, both directions: no collision (notes.md
   decision #1).
6. **Substrate `ThirdPerson`** per owner decision **D8** (plan §3.1b: R4 on
   ThirdPerson; imported-set convention).
7. **The redirector-residue variant -> DESIGNED BUT UNMANUFACTURABLE
   (recorded 2026-07-30; an open COVERAGE GAP, not a closed question).**
   The design called for a `redirector-wrong-target/` discrimination leg to
   exercise branch (a) of the C5-C8 tri-state end-to-end. The authoring boot
   proved headless UE 5.8 cannot produce a redirector residue on this box:
   (i) `rename_asset` with LOADABLE Blueprint referencers always takes Lane
   A — fixup in memory, referencers resaved, old package DELETED, no
   redirector (`old_registered=False new_registered=True`), which CONFIRMS
   the design's engine-source prediction that `bCreateRedirector` fires only
   on fixup-FAILURE conditions; (ii) the read-only-referencer trick does not
   reach `DetectReadOnlyPackages` headless (named abort
   `RENLANE-REDIRECTOR-NOT-CREATED`); (iii) the unloaded-map referencer
   route fails at its premise — a level holding a placed instance of the
   referencing Blueprint references the BLUEPRINT, not the enum, so the
   enum's referencer set never includes an unloaded map. Python cannot
   construct one directly either (`UObjectRedirector::DestinationObject` is
   an unreflected C++ member). The variant was therefore retired unauthored
   and the row ships 4 legs (reference + empty + `duplicate-not-rename/` +
   `one-left-behind/`); the tri-state's redirector branch is covered by the
   OFFLINE oracle only
   (`test_introspect_consistent_enum_names.py::TestTriStateContract`, both
   directions: correct target passes, wrong target fails by name).
   **`allow_redirectors` STAYS in the front matter.** It is the correct
   DEFENSIVE declaration: a legitimate agent rename — with source control
   enabled, a genuinely unloaded map referencer, or a partially-failing
   fixup — can still ship that state, and the flag is what lets it reach the
   grader instead of dying `REDIRECTOR_SUBMITTED` in the integrity preamble.
   The flag's own behavior is pinned by the harness unit tests
   (`tools/verify-single/tests/test_asset_integrity.py::TestAllowRedirectorsFlag`),
   independently of this task's matrix. What is honestly LOST is live
   end-to-end coverage of the flag-plus-grader path on a real submission;
   that gap re-opens the moment a route to manufacture the residue is found
   (the authoring script keeps the capability behind
   `RENLANE_TRY_REDIRECTOR=1`).

> **Note on the behavior-only rule (Hard Rule #2).** The prompt names the
> four existing enumeration asset names (`WeaponType`, `E_ammo_kind`,
> `enum_DamageType`, `ItemRarity`), the two referencing assets (`BP_RefA`,
> `BP_RefB`) and their folder. That is the standard, precedented named-asset
> exception for tasks whose whole point *is* transforming specific named
> asset content — the names ARE the observable being fixed, and naming them
> lets the verifier grade a hard-coded mapping instead of parsing the
> convention at grade time (weapon-task style; this paragraph is the
> per-spec justification). Everything else stays behavior-only: the prompt
> never names a class (`UserDefinedEnum`, `ObjectRedirector`), a tool
> route, the asset registry, or the word "redirector" — and it is
> deliberately **silent on redirectors** (leaving one is unachievable on
> demand, cleaning one up is ungradable; the tri-state tolerates both
> mechanical outcomes of a correct rename).

## Primary concept

- `asset-management` — renaming/reorganizing project assets with referential
  integrity (redirectors, reference fixup)
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/redirectors-in-unreal-engine)

The load-bearing capability is performing a **reference-preserving rename**:
deriving convention-correct names from a stated convention plus worked
examples, applying them to live assets, and leaving every consumer working —
the everyday hygiene operation the source row's "asset naming audit" is about.
Adjacent in-scope concepts: `blueprints` (the two referencing assets are
Blueprint variables typed to the enums). The concept naming here is
documentation for humans; none of these names appear in the prompt.

## Prompt given to the agent

> This project names its enumeration assets by one convention: the name
> starts with `E_` followed by the meaning in PascalCase — capitalized words
> run together, with no separators between words, and no words that merely
> restate that the asset is an enumeration. Two examples of fixes from
> elsewhere in the studio: an asset named `loot_table_kind` becomes
> `E_LootTableKind`, and one named `enum_fire_mode` becomes `E_FireMode`.
>
> The folder `Content/Tasks/t2-consistent-enum-names/Enums/` holds four
> enumeration assets that predate the convention: `WeaponType`,
> `E_ammo_kind`, `enum_DamageType`, and `ItemRarity`. Two other assets in
> this project — `BP_RefA` and `BP_RefB`, directly under
> `Content/Tasks/t2-consistent-enum-names/` — have variables typed to these
> enumerations.
>
> Bring the four enumeration assets into line with the convention: after
> your change each of the four lives in that same `Enums/` folder under its
> convention-correct name, and everything that used these enumerations
> keeps working — `BP_RefA` and `BP_RefB` must end up with their variables
> typed to the convention-named enumerations, without losing or changing
> what those variables mean. Do not add anything else to that folder, and
> save everything you touched.

## Workspace state pre-task

Substrate content that **exists** (the committed baseline this task ships;
all authored with stock factory content):

- `Content/Tasks/t2-consistent-enum-names/Enums/WeaponType.uasset` —
  enumeration asset (misnamed: no `E_` prefix).
- `Content/Tasks/t2-consistent-enum-names/Enums/E_ammo_kind.uasset` —
  enumeration asset (misnamed: snake_case).
- `Content/Tasks/t2-consistent-enum-names/Enums/enum_DamageType.uasset` —
  enumeration asset (misnamed: redundant leading word, no `E_` prefix).
- `Content/Tasks/t2-consistent-enum-names/Enums/ItemRarity.uasset` —
  enumeration asset (misnamed: no `E_` prefix).
- `Content/Tasks/t2-consistent-enum-names/BP_RefA.uasset` — Blueprint with
  two variables, typed to the first two enumerations above.
- `Content/Tasks/t2-consistent-enum-names/BP_RefB.uasset` — Blueprint with
  two variables, typed to the last two enumerations above.

Files that **do not exist** (the correct end state produces them):

- `Content/Tasks/t2-consistent-enum-names/Enums/E_WeaponType.uasset`
- `Content/Tasks/t2-consistent-enum-names/Enums/E_AmmoKind.uasset`
- `Content/Tasks/t2-consistent-enum-names/Enums/E_DamageType.uasset`
- `Content/Tasks/t2-consistent-enum-names/Enums/E_ItemRarity.uasset`

Out of scope / not needed:

- No C++, no level, no placed actor, no functional test, no config edit.
  The enumerations' MEMBER content is stock and is not part of the task;
  nothing needs to consume the Blueprints at runtime. `Content/Tasks/` is
  the `ThirdPerson` substrate's agent-writable Content carve-out
  (`UE-projects/ThirdPerson/AGENT_WRITABLE.json`).

## Verifier specification

Layer choice: **L1 + L2I**. Every graded property is a static registry-level
property of the submitted/overlaid assets (existence, asset class, one
registry tag, dependency/referencer edges, folder membership), read by
verifier-owned editor-Python. No PIE, no live world — the rename's
correctness IS its registry closure.

The spec front matter declares **`allow_redirectors`** naming exactly the
four OLD packages (task-scoped form enforced by `spec.py`; entries outside
`/Game/Tasks/t2-consistent-enum-names/` are an exit-2 spec error). This
narrows ONLY the integrity preamble's redirector rejection at those four
paths: a legitimate rename whose referencer fixup was blocked ships a
redirector at an old path (Lane B), which must not grade
`REDIRECTOR_SUBMITTED` against a correct submission. A redirector anywhere
else in the submission still fails the preamble.

**The binding grader rule** (`INTROSPECT_CONTRACT.md`, allow_redirectors
section): allowed old paths are read ONLY through registry `AssetData`
(`asset_class_path`, `get_tag_value("DestinationObject")`,
`get_referencers`) — never `load_asset`/`load_object` (which silently
follows the redirector and grades its TARGET). This task's grader complies
by construction: it calls `load_asset` on **nothing** — new paths included,
every fact is a registry read.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64 Development"
        and "ThirdPerson Win64 Development" (short-circuits on first failure)
```

The submission is content-only, so L1 is a precondition (the project and its
Asset Registry must load cleanly), never a correctness signal.

### L2I — Structural assertion (the tri-state closure)

The verifier-owned script
`tools/verify-single/introspect/consistent_enum_names.py` runs headless via
`UnrealEditor-Cmd -ExecutePythonScript=` under `-nullrhi`, read-only, and
prints one `CRAFTBENCH-INTROSPECT-JSON` verdict block. It emits **exactly 11
named checks on every leg** (constant denominator). The old->new mapping is
hard-coded: `WeaponType -> E_WeaponType`, `E_ammo_kind -> E_AmmoKind`,
`enum_DamageType -> E_DamageType`, `ItemRarity -> E_ItemRarity`. PASS
requires all 11:

```text
new_asset_weapon_type       C1  /Game/Tasks/<id>/Enums/E_WeaponType exists in
                                the registry AND its class is the enumeration
                                asset class  [LIVE - absent at baseline]
new_asset_ammo_kind         C2  likewise E_AmmoKind
new_asset_damage_type       C3  likewise E_DamageType
new_asset_item_rarity       C4  likewise E_ItemRarity
old_path_retired_weapon_type C5 the OLD path /Game/Tasks/<id>/Enums/WeaponType
                                is no longer load-bearing: EITHER a redirector
                                whose DestinationObject registry tag == exactly
                                the expected new package, OR a real enumeration
                                asset with ZERO registry referencers (the
                                overlay-resurrected orphan)  [LIVE - at
                                baseline the old enum has live referencers]
old_path_retired_ammo_kind   C6 likewise E_ammo_kind
old_path_retired_damage_type C7 likewise enum_DamageType
old_path_retired_item_rarity C8 likewise ItemRarity
refs_resolved_bp_ref_a       C9 BP_RefA exists, is a Blueprint, and its
                                registry dependency set - after substituting
                                each allowed old package through its
                                C5-C8-VERIFIED redirector target - covers
                                {E_WeaponType, E_AmmoKind} and contains no old
                                package that is not a verified redirector
                                [LIVE - at baseline the deps are the old pkgs]
refs_resolved_bp_ref_b      C10 likewise BP_RefB against
                                {E_DamageType, E_ItemRarity}
folder_inventory            C11 the Enums folder holds EXACTLY the 8 expected
                                packages (4 new + 4 old in either disposition),
                                collapsed to a package-name set - nothing else
                                [LIVE - baseline holds only 4]
```

**Why a tri-state (the design's central finding).** UE 5.8's rename manager
loads every loadable referencing package, fixes references in memory,
resaves them, and DELETES the old package — no redirector — in exactly this
baseline's conditions (2 loadable BP referencers, no SCC, no maps, no
collections). The copy-only overlay then resurrects the committed baseline
enum at the old path as an **orphan**. A UI-driven or fixup-blocked rename
instead leaves a **redirector** at the old path. Both are mechanical
outcomes of the same correct action, neither is achievable-on-demand from
the other lane, so C5-C8 accept both — and every lazy or cheap-wrong state
(untouched baseline, duplicate-instead-of-rename, wrong-target forwarding,
left-behind enum) fails at least one leg of the closure.

**Read routes** (all engine-source-verified headless-viable in the design
VERDICT, and marshaling live-proven in `spike-facts-2026-07-30.md` §D):
registry handle via `AssetRegistryHelpers.get_asset_registry` (+ defensive
`wait_for_completion`); per-path `AssetData` via `get_asset_by_object_path`
(5.8 `SoftObjectPath` coercion handled); class via `asset_class_path`
(legacy `asset_class` fallback); the `DestinationObject` tag via
`asset_data.get_tag_value` (live-proven: plain `str`, `None` when absent),
written by `UObjectRedirector::GetAssetRegistryTags`
(`ObjectRedirector.cpp:63-78`) and NOT AR-filtered
(`AssetRegistryInterface.cpp:65-121`); dependency/referencer edges via
`get_dependencies`/`get_referencers` with `AssetRegistryDependencyOptions`
(live-proven: plain Array); folder membership via `get_assets_by_path`
collapsed to a **package-name set** (the `SKEL_<Name>_C` same-package
duplicate lesson, 2026-07-30). The exact 5.8 text shape of the
DestinationObject tag is a design open question: the parse is tolerant
(quoted `Class'/Game/Path.Name'` export form or bare object path), the
authoring boot pins the real shape (`RENLANE-CAL` print), and any surprise
routes to an uncredited `ENUM_OLD_TAG_*` token — never a graded semantic
failure.

**Dead-gate audit** (house law; full record in `notes.md` decision #8):
every check is LIVE against the lazy state — the committed baseline itself
grades a genuine **0/11** (new assets absent, old paths still referenced,
BP deps on old packages, folder inventory incomplete). No check equals a
default or baseline state. The one honestly-recorded coverage gap
(divergence 7, 2026-07-30): the redirector arm of C5-C8 has **no live
coverage at all, in either direction** — the residue state is not
manufacturable headless on this box (three dead routes), so both its PASS
side (Lane B, correct target) and its FAIL side (wrong target) are pinned
by the offline oracle on the real grader and by nothing else. The orphan arm
is live-covered by the reference itself.

**Ungraded by design, recorded honestly:** enumerator CONTENT. Stock
editor-Python has no UserDefinedEnum enumerator read/write surface
(spike-facts §E: no UserDefinedEnumLibrary, no EnumEditorLibrary; the
DisplayNameMap UPROPERTY is unreflected), so the baseline ships
factory-default enumerators and no check reads member lists. Anti-gaming
entry 5 records the accepted residual this creates. The distinct-enumerator
nicety is dropped (alternative — the Aura MCP `edit_enumeration` lane —
recorded and deferred; grading stays MCP-free).

**Identity is by pre-declared content path and pre-declared name.** The
mapping is fixed by the committed baseline and stated as convention + worked
examples in the prompt; the agent may work through the editor UI, editor
scripting, or any tool lane, and none of that is visible or graded.

**Why `saved` is not a separate check.** The runner grades a file overlay
materialized onto a clean substrate; an unsaved rename presents as no new
file and fails its `new_asset_*` check.

**Score granularity.** `report.json` carries `x/11` for this task
(`tests_passed/tests_run` from the per-check counts). Reported, not gating.

## Reference solution metadata

- LOC range: **0** lines of code. The deliverable is four renamed assets +
  two resaved referencing Blueprints.
- Files touched: 4 renamed (old file gone, new file created), 2 resaved.
- Senior-dev hours: 0.3-0.8 (derive four names from the convention, rename
  with reference fixup, verify the two Blueprints still resolve — the real
  work is not breaking the references and getting `enum_DamageType ->
  E_DamageType` right, dropping the redundant word per the
  `enum_fire_mode -> E_FireMode` example).

## Anti-gaming notes

1. **Duplicate-instead-of-rename.** *Failure mode*: the agent creates four
   fresh convention-named enums and leaves everything referencing the old
   ones — the four new files exist and a names-only verifier passes it.
   *Defense*: C5-C8's orphan branch requires ZERO referencers on every old
   path (`ENUM_OLD_STILL_REFERENCED_*`), and C9-C10 require the BPs'
   dependency sets to land on the new packages
   (`BP_DEP_OLD_NAME_LIVE_*`). Variant `duplicate-not-rename/`.
2. **Hand-rolled forwarding (redirector forgery).** *Failure mode*: the
   agent byte-crafts or copies a redirector to an allowed old path to
   smuggle a non-renamed state through the tolerated lane. *Defense*:
   **forgery does not help** — C5-C8 accept a redirector only when its
   one-hop DestinationObject tag equals EXACTLY the expected new package
   (`ENUM_OLD_REDIRECT_WRONG_TARGET_*`; chains fail because the one-hop tag
   equals the intermediate), C1-C4 still demand the real new enum exist,
   and C9-C10 still demand the BPs resolve onto it — so a redirector that
   satisfies the closure is indistinguishable from having performed the
   rename, and one that does not fails by name. The grader never loads
   through old paths, so a forged redirector cannot steer what gets graded;
   a redirector at any NON-allowed path (including the new paths) is
   rejected by the integrity preamble (`REDIRECTOR_SUBMITTED`) before the
   grader runs. *Coverage note*: a forged redirector whose tag is missing
   or unparseable falls to uncredited conservative `ENUM_OLD_TAG_*` tokens
   — a graded FAIL either way. *No variant folder*: the residue state is
   unmanufacturable headless (divergence 7), so this defense is pinned by
   the offline oracle on the real grader, both directions.
3. **Junk in the audited folder.** *Failure mode*: extra copies, chained
   rename intermediates, `E_WeaponType_1`, or hedge assets pile up in
   `Enums/` so that some name matches anything a verifier greps for.
   *Defense*: C11 is an exact package-set inventory
   (`ENUM_FOLDER_UNEXPECTED_ASSET`) — the folder holds the 8 expected
   packages and nothing else.
4. **Renaming or re-pointing the Blueprints instead of fixing the enums.**
   *Failure mode*: the agent renames BP_RefA/BP_RefB, or re-types their
   variables to engine enums or assets outside the task folder, so no old
   reference remains to catch. *Defense*: C9-C10 pin BP existence at their
   exact packages (`BP_REF_MISSING_*`) and require their dependency sets to
   cover the four exact new packages (`BP_DEP_UNRESOLVED_*`).
5. **Accepted residual, documented honestly**: create-fresh-enums-and-
   retype-every-variable would pass the closure — enumerator content is
   unreadable headless (spike-facts §E), so a fresh factory-default enum at
   the new path is indistinguishable from a renamed one. It is strictly
   MORE work than the one-call-per-enum rename with automatic fixup, so it
   carries no reward-hacking incentive; an enumerator-content check is
   added only if a future spike finds a read route (design anti-gaming
   entry 5).

## Hidden invariants

- The check denominator is fixed at 11 on every leg, including the
  untouched-baseline (empty) submission — a genuine **0/11** — and a
  no-`unreal` import. A submission cannot improve its reported
  `tests_passed/tests_run` by making checks unreachable.
- C9-C10 substitute an old package ONLY through a redirector that C5-C8
  actually verified (exact target). An unverified redirector, an
  unreadable tag, or a still-real old enum counts as a LIVE old name.
- The grader loads no assets. Allowed old paths are registry-read only
  (the contract rule); new paths too — there is nothing a crafted asset
  can execute or redirect during grading.
- Every verifier-side failure path — registry handle, AssetData probe, tag
  read/parse, referencer/dependency read, folder listing — emits a distinct
  token from the script's `UNCREDITED_TOKENS` tuple, which appears in
  **no** discrimination-matrix row, so a broken probe can never be credited
  as a variant's named failure.
- Echoed registry-derived text (class names, tag text, referencer/extra
  package names) is sanitized (whitespace and `=` become `~`) and
  length-capped before it reaches a check detail, so an adversarial name
  cannot inject an automation-result marker into the grading log.
- Nothing outside `/Game/Tasks/t2-consistent-enum-names/` is graded; the
  folder inventory reads only the task's own `Enums/` folder (the 544
  engine-side redirectors can never reach a check).

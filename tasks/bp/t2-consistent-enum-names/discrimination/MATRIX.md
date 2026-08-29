# Discrimination matrix — t2-consistent-enum-names

The self-validation oracle: the reference solution must PASS and every gaming
variant + the empty leg must FAIL **at the predicted check, via the named
substring**. A wrong-reason FAIL (L1 build failure, a different check, a
`0`-check/`error` L2I verdict, SANDBOX-REJECT exit 4) means the verifier is
NOT discriminated — fix it, or relabel the task for the weaker property it
actually tests.

> **STATUS: BOTH HALVES AUTHORED (2026-07-30).** The committed BASELINE
> (four misnamed enums + two referencing Blueprints in the substrate), the
> reference, and both variant `.uasset` sets now exist, authored by
> `../authoring/run_author_all_assets.sh`. That runner is **multi-boot**:
> each leg is authored in its own fresh editor boot, harvested to a staging
> area, and then graded in a SEPARATE COLD BOOT whose state the runner
> materializes on disk beforehand — stashed baseline + a copy-only overlay,
> byte-for-byte what `tools/verify-single` does to a graded workdir. Only
> after that cold boot asserts the leg's exact expected vector is the
> deliverable promoted into `../reference/` or `discrimination/<leg>/`, so
> no unverified byte can reach this tree. The shape is forced, not chosen:
> an in-session package delete makes the registry lie about that path for
> the rest of the boot (notes.md §5, the tombstone law), which had produced
> a same-boot grade that FALSE-PASSED four checks while false-failing one.
> The offline oracle in
> `tools/verify-single/tests/test_introspect_consistent_enum_names.py`
> remains the LOGIC oracle (fake `unreal` module) and additionally pins the
> authoring lane's safety properties statically.

## Four parser traps this matrix is written against

- **NO cell may reach PAST a runtime placeholder into the value.** Added
  2026-08-12 by the salvage wave, after `test_matrix_substring_oracle`
  caught this row: `refs_resolved_bp_ref_a`'s cell used to read
  `BP_DEP_OLD_NAME_LIVE_BP_RefA old=/Game/…/Enums/E_ammo_kind`, but the
  script formats that tail as `old=%s` interpolating
  `",".join(sorted(old_live))` — a RUNTIME set join. The longer cell matched
  only because `E_ammo_kind` happens to sort before `WeaponType`; add an
  old package that sorts earlier and a *correct* FAIL starts reading as
  wrong-reason. This is the `granted=0` vs `granted=` rule from
  `matrix_oracle`'s docstring, and this row was on the wrong side of it. The
  cell is now cut at the placeholder (`BP_DEP_OLD_NAME_LIVE_BP_RefA old=`),
  which still names the check and the Blueprint and no longer depends on
  sort order. **Do not restore the longer form.**
- **ONE parseable row per label.** `discriminate.parse_matrix` returns
  `Dict[label -> MatrixRow]`, so a *second* table that repeats a variant
  label silently **overwrites** the first — and a table without a
  "substring" header column yields an empty message tuple, so the overwrite
  blanks the leg. This file has **exactly one table with variant rows**;
  every secondary observation lives in prose below it.
- **Every "Expected substring" cell is a backtick-wrapped literal that
  CONTAINS A SPACE** (or one of `(),.=`), so `_extract_substrings` keeps it
  verbatim instead of falling through to the broken backticks-attached
  branch. Pairing each token with the fixed `key=value` text that follows it
  in the script makes the cell substantive AND keeps it a literal substring
  of the printed `detail`.
- **The "Expected substring" header is the only column `parse_matrix` reads
  for substrings.** The "Also fails" column deliberately does NOT contain
  the words "message" or "substring", so its backticked tokens are never
  harvested as expectations.

## Two L2I traps this matrix is written against

- **The substring is matched against the raw `detail` string as printed
  inside the `CRAFTBENCH-INTROSPECT-JSON` block** — not against the layer's
  note rendering. Every "Expected substring" cell below is a literal token
  emitted by `tools/verify-single/introspect/consistent_enum_names.py`.
- **Exactly ONE introspect script per task.** `registry.py` keeps only
  `li_last_log`, so a substring printed by an earlier script could never be
  credited. This task declares one script, and must keep declaring one.

**ASCII rule:** every expected substring is ASCII-only (the UE log's UTF-8
read back as cp1252 turns non-ASCII into mojibake and the grep misses — live
incident, `t2-homing-projectile`, 2026-07-21). The whole introspect script is
ASCII by construction, and echoed registry-derived text (class names, tag
text, referencer/extra package names) is sanitized and length-capped before
printing.

**Error tokens are distinct from failure tokens.** Every verifier-side
failure path in the script emits a token from its `UNCREDITED_TOKENS` tuple
(`*_READ_ERROR`, `ENUM_OLD_ASSETDATA_UNAVAILABLE`, `ENUM_OLD_TAG_UNREADABLE`
/ `..._UNPARSEABLE`, `RENAME_REGISTRY_UNAVAILABLE`,
`RENAME_INTROSPECTION_ABORTED`, ...) that appears in **no** matrix row, so a
broken probe (or a registry surprise) can never be credited as a variant's
named failure. Asserted by
`test_introspect_consistent_enum_names.py::TestErrorTokensAreDisjointFromMatrix`.

**The `allow_redirectors` lane.** This task's spec front matter allowlists
the four OLD packages, so a submitted redirector at an old path reaches the
grader instead of dying `REDIRECTOR_SUBMITTED` in the integrity preamble.
The flag is a DEFENSIVE declaration and stays: a legitimate agent rename can
still ship that state. No folder leg exercises the lane end-to-end — see the
Coverage note below the table (2026-07-30: the residue is not manufacturable
headless), so the flag's own behavior is pinned by the harness unit tests
(`tools/verify-single/tests/test_asset_integrity.py::TestAllowRedirectorsFlag`)
and the grader's handling of the state by the offline oracle.

## Layout (folder-local; agent-writable prefixes only — a stray root file -> SANDBOX-REJECT exit 4)

- `../reference/Content/Tasks/t2-consistent-enum-names/Enums/{E_WeaponType,E_AmmoKind,E_DamageType,E_ItemRarity}.uasset`
  + `.../Content/Tasks/t2-consistent-enum-names/{BP_RefA,BP_RefB}.uasset`
  — the clean rename (Lane A): four new enums + the two resaved referencing
  Blueprints; NO old-path files (the rename deleted them; the graded
  overlay resurrects the baseline enums as orphans, which is the tri-state's
  orphan branch and part of the reference's expected PASS).
- `duplicate-not-rename/Content/Tasks/t2-consistent-enum-names/Enums/{E_WeaponType,E_AmmoKind,E_DamageType,E_ItemRarity}.uasset`
  — four fresh correctly-named enums only; the Blueprints are untouched (not
  shipped) and keep referencing the old names.
- `one-left-behind/Content/Tasks/t2-consistent-enum-names/Enums/{E_WeaponType,E_AmmoKind,E_DamageType}.uasset`
  + `.../{BP_RefA,BP_RefB}.uasset` — three renamed, `ItemRarity` untouched;
  BP_RefB still depends on the old `ItemRarity`.
- empty leg — run IMPLICITLY by `cb discriminate` (a throwaway empty dir).
  The graded state is the untouched committed baseline: a genuine **0/11**.

## Requirements table (checklist §7, the mandatory soundness artifact)

Added 2026-08-12 by the eval-import salvage wave. The row shipped before the
2026-08-11 owner decision that made this table mandatory, so it is
retro-fitted here: one row per requirement in the agent-visible prompt,
naming the assertion that checks it and the condition under which that gate
is skipped. The check id is the durable join key; every backticked span is a
contiguous literal in
`tools/verify-single/introspect/consistent_enum_names.py`.

Its first cells are integers and its columns name neither "substring" nor
"message", so `discriminate.parse_matrix` skips it entirely — verified by
re-parsing this file after the table was added (4 rows, unchanged).

| # | Prompt requirement | Asserted | Enforcing check — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | derive the convention-correct name for each of the four (`E_` + PascalCase, no separators, no word restating "enumeration") | fully | C1-C4 `new_asset_weapon_type` … `new_asset_item_rarity` — `ENUM_NEW_MISSING_` (the mapping is hard-coded, so a wrong derivation lands nowhere) | unconditional | nothing — a wrong name is an absent expected package |
| 2 | each of the four lives in that same `Enums/` folder | fully | C1-C4 pin the full package path under `Enums/`; C11 `folder_inventory` — `ENUM_FOLDER_INCOMPLETE` | unconditional | nothing |
| 3 | each of the four is an enumeration asset (not some other asset wearing the name) | fully | C1-C4's class half — `ENUM_NEW_WRONG_CLASS_` | unconditional | enumerator CONTENT — see row 7 |
| 4 | everything that used these enumerations keeps working | fully | C9-C10 `refs_resolved_bp_ref_a` / `_b` — `BP_DEP_UNRESOLVED_` (dep set must cover the new packages) and `BP_DEP_OLD_NAME_LIVE_` (no un-redirected old package may remain) | unconditional | a consumer OUTSIDE the two named Blueprints — none exists in the substrate, so the set is closed |
| 5 | `BP_RefA` / `BP_RefB` keep their variables' MEANING (A → weapon+ammo, B → damage+rarity) | fully | C9-C10 check each BP against its own expected pair, not a union — swapping the two Blueprints' variables fails both | unconditional | variable NAMES and order — deliberately ungraded, the prompt does not constrain them |
| 6 | do not add anything else to that folder | fully | C11 `folder_inventory` — `ENUM_FOLDER_UNEXPECTED_ASSET` (exact 8-package set) | unconditional | assets added OUTSIDE `Enums/` — deliberate, the prompt scopes this to that folder |
| 7 | the four assets are the SAME four, brought to the convention (a rename, not four fresh assets) | **partially** | C5-C8 `old_path_retired_*` — `ENUM_OLD_STILL_REFERENCED_` / `ENUM_OLD_REDIRECT_WRONG_TARGET_` force the old paths out of load-bearing use | unconditional | **the accepted residual**: create-fresh-then-retype-every-variable satisfies the whole closure. Enumerator content is unreadable headless (spike-facts §E), so a factory-default enum at the new path is indistinguishable from a renamed one. Recorded as anti-gaming entry 5; it is strictly MORE work than the rename, so it carries no reward-hacking incentive |
| 8 | save everything you touched | fully | no separate check by design — the runner grades a file overlay, so an unsaved rename presents as no new file and fails C1-C4 | unconditional | nothing |

**Holes this table found: none that lack a defense.** Row 7 is the one
requirement not fully asserted, and it was already known, already recorded
in the task's anti-gaming notes, and already engine-limited rather than
verifier-limited — so per §7a no new hand-authored variant is owed. Rows 1-6
and 8 each name a live gate. The two variants this package ships predate the
decision and are kept: they were authored against anti-gaming entry 1 and
still earn their keep as the only live coverage of the C5-C10 closure.

## Matrix

**This is the only table in this file that carries variant rows.** The
requirements table above carries none — see the first parser trap and the
note under that table.

| Submission | Overall | Fails at (check id) | Expected substring | Also fails (recorded, not matched) | Anti-gaming note |
|---|---|---|---|---|---|
| `../reference` | PASS | — | all 11 checks green (11/11) | — | — |
| empty | FAIL | `new_asset_weapon_type` | `ENUM_NEW_MISSING_E_WeaponType path=/Game/Tasks/t2-consistent-enum-names/Enums/E_WeaponType` | every other check — 0/11: the three sibling `ENUM_NEW_MISSING_*`, four `ENUM_OLD_STILL_REFERENCED_*`, two `BP_DEP_OLD_NAME_LIVE_*`, and the `ENUM_FOLDER_INCOMPLETE` inventory | FR-017 |
| `duplicate-not-rename/` | FAIL | `refs_resolved_bp_ref_a` | `BP_DEP_OLD_NAME_LIVE_BP_RefA old=` | the four `ENUM_OLD_STILL_REFERENCED_*` (old enums keep their referencers) and `refs_resolved_bp_ref_b` (`BP_DEP_OLD_NAME_LIVE_BP_RefB`); C1-C4 + C11 PASS — 5/11 | #1 duplicate-instead-of-rename |
| `one-left-behind/` | FAIL | `new_asset_item_rarity` | `ENUM_NEW_MISSING_E_ItemRarity path=/Game/Tasks/t2-consistent-enum-names/Enums/E_ItemRarity` | `old_path_retired_item_rarity` (`ENUM_OLD_STILL_REFERENCED_ItemRarity`), `refs_resolved_bp_ref_b` (`BP_DEP_OLD_NAME_LIVE_BP_RefB`), `folder_inventory` (`ENUM_FOLDER_INCOMPLETE`) — 7/11 | #1 partial laziness |

Why each "Also fails" entry is expected and does **not** make the
discrimination muddy (prose on purpose — a table here would re-register the
labels and blank their substrings):

- **empty** is the committed baseline unchanged, and the baseline is
  designed to fail everything: 0/11 with every token named. The matched
  substring is the first missing new asset.
- **`duplicate-not-rename/`** fails exactly the six closure checks that
  distinguish a copy from a rename (four old paths still referenced + both
  BP dependency sets still on the old names) while C1-C4 and the exact
  inventory PASS — which is precisely the trap the tri-state exists to
  close. The matched substring is the BP_RefA dependency check: it names
  the OLD packages still live in a resaved-nothing submission.
- **`one-left-behind/`** fails exactly the four checks that mention
  `ItemRarity`'s lane (its new asset, its old path, BP_RefB's deps, and the
  now-7-package inventory). Every substring the row records is disjoint
  from every other leg's matched substring.

Coverage note — **the redirector branch of the tri-state ships with NO
folder leg** (recorded 2026-07-30, from the authoring boot's live findings;
this is a real coverage gap in this row's matrix, not a closed question).
C5-C8 accept a retired old path in either of two dispositions: (a) a
`UObjectRedirector` forwarding to exactly the expected new package, or
(b) a resurrected orphan with zero referencers. Branch (b) is the
reference's own state and is live-covered. Branch (a) is **not
manufacturable headless on this box**, so the originally-designed
`redirector-wrong-target/` variant was retired before it was ever authored.
Three routes were tried and are dead:

1. **The stock rename lane** (`EditorAssetLibrary.rename_asset`) with
   LOADABLE Blueprint referencers always takes Lane A — referencers are
   fixed up in memory and resaved, the old package file is DELETED, and no
   redirector remains (`old_registered=False new_registered=True`, class at
   the old path `None`). This CONFIRMS the design's engine-source
   prediction that `FAssetRenameManager` sets `bCreateRedirector` only on
   fixup-FAILURE conditions.
2. **The read-only-referencer trick** (chmod the referencing Blueprint
   files, expecting `DetectReadOnlyPackages` to force `bCreateRedirector`)
   does NOT fire headless — the boot aborted with its named token
   `RENLANE-REDIRECTOR-NOT-CREATED`.
3. **An UNLOADED MAP referencer** (the design's other cited route) cannot
   be arranged: a level containing a placed instance of the referencing
   Blueprint references the BLUEPRINT, not the enum
   (`level_refs_enum=False`), so the enum's referencer set never includes
   an unloaded map, and the rename fixed up and deleted cleanly again.

Python cannot construct a redirector directly either —
`UObjectRedirector::DestinationObject` is a plain unreflected C++ member.
**Consequence:** branch (a) is covered by the OFFLINE oracle rather than by
a folder leg, and this row therefore ships **4 legs** (reference + empty +
the two negatives above). The offline pins on the REAL grader are
`TestTriStateContract::test_lane_b_correct_redirector_passes` (correct
target -> `ENUM_OLD_REDIRECTS_OK`, 11/11) and
`::test_wrong_target_redirector_fails_by_name` (wrong target ->
`ENUM_OLD_REDIRECT_WRONG_TARGET_WeaponType`, plus the blocked C9
substitution). The grader keeps BOTH branches, the 11-check denominator,
and the redirector tokens — a legitimate agent rename (with source control,
a genuinely unloaded map referencer, or a partially-failing fixup) can still
produce the residue, and a grader that dropped it would fail a correct
submission. The `allow_redirectors` flag's own behavior is pinned by
`tools/verify-single/tests/test_asset_integrity.py::TestAllowRedirectorsFlag`.

Further bounded coverage (argued from the named checks rather than run as
separate submissions — each shape pinned by the offline oracle on the REAL
grader):

- **A CHAINED redirector** (old -> intermediate -> new): the one-hop tag
  equals the intermediate, not the expected package — fails C5 with the
  wrong-target token. Pinned offline.
- **A forged redirector with a missing/garbage DestinationObject tag**:
  falls to `ENUM_OLD_TAG_UNREADABLE` / `ENUM_OLD_TAG_UNPARSEABLE` —
  uncredited conservative FAIL. Pinned offline.
- **A wrong-class impostor at a new path** (e.g. a Blueprint named
  `E_WeaponType`): fails its `new_asset_*` check with
  `ENUM_NEW_WRONG_CLASS_*`. Pinned offline.
- **Folder junk** (`E_WeaponType_1` and friends): fails C11 with
  `ENUM_FOLDER_UNEXPECTED_ASSET`. Pinned offline; no folder spent —
  the token is disjoint from every committed leg's.
- **Registry/probe breakage** (no registry, unreadable deps, missing old
  AssetData): grades tokens from `UNCREDITED_TOKENS` that no row here
  credits (conservative taxonomy). Pinned offline.

## How to run (deterministic verifier, no agent, no tokens)

```sh
cb discriminate --task bp/t2-consistent-enum-names
```

Per-leg fallback while iterating on one variant (a short `--workdir` dodges
Windows MAX_PATH; use the `py` launcher — this box's `py -3.12` does not
resolve, use `py -3.13`):

```sh
UE='<UE-root>'
py -3.13 tools/verify-single/run_task.py \
    --task tasks/bp/t2-consistent-enum-names/task.md \
    --submission tasks/bp/t2-consistent-enum-names/discrimination/duplicate-not-rename \
    --ue-root "$UE" --workdir C:\cb\wd\kvr4var       # expect exit 1
```

Then open the workdir's `report.json` and the `L2I` log it names, find the
`CRAFTBENCH-INTROSPECT-JSON-START` block, and confirm the failing check's raw
`detail` contains this table's "Expected substring" cell.

**L2I graders are read from the LIVE working tree**, so iterating on
`consistent_enum_names.py` needs no commit — but the `.uasset` legs (and the
BASELINE, which grading reads from git HEAD via the substrate
materialization) DO need committing before a non-`--wip` grade sees them.

## Status

- Text half authored 2026-07-30 from the o2-rename-lane design (row R4,
  GREEN-after-flag; the `allow_redirectors` flag landed at `f221cf0`).
- **Binary half authored 2026-07-30**, all four legs verified in COLD boots
  that graded the real materialized graded state (no rescan, no in-session
  mutation, nothing simulated). Cold-boot vectors, in prose because a second
  table here would re-register the variant labels and blank their expected
  substrings — parser trap #1 above, which this very line was written to
  violate and then didn't: the reference read **11/11**; the empty leg (the
  committed baseline itself) **0/11**; the duplicate variant **5/11**,
  failing the six closure checks; the one-left-behind variant **7/11**,
  failing the four `ItemRarity`-lane checks. Every failing set matched its
  row in the matrix above exactly, and every "Expected substring" was
  asserted present in the raw `detail` before the leg was promoted out of
  staging.
- `redirector-wrong-target/` was **retired 2026-07-30, unauthored** — the
  redirector residue is not manufacturable headless (three dead routes,
  Coverage note above). The row ships **4 legs**: reference + empty + the
  two negatives.
- Every one of the remaining negative legs parses out of this file with a
  **non-empty, backtick-free** substring, and every substring is proven to
  be a literal the introspect script actually prints — simulated offline
  against a fake `unreal` module and joined through the REAL
  `discriminate.parse_matrix` + the REAL `layers/l2_introspect` parser by
  `tools/verify-single/tests/test_introspect_consistent_enum_names.py`.
- **Still missing, in order:** (1) the rest of the headless authoring boot
  (`../authoring/run_author_all_assets.sh` — baseline build, per-leg
  in-process grading against exact expected vectors, and the named
  calibration pin still outstanding: the DestinationObject tag shape, which
  now has no live route at all and stays an open question); (2) the
  baseline + binary commit; (3) the first live `cb discriminate --wip`
  (4 legs: reference, empty, two variants); (4) the git-HEAD certification
  re-run; (5) the shared import-lane registry reconciliation (deliberately
  NOT in this change-set).

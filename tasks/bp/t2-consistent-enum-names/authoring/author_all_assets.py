"""Author ALL t2-consistent-enum-names assets: the committed BASELINE, the
reference rename, and 3 discrimination variants, with the real grader run
in-process at every state.

Run headless on the ThirdPerson substrate project:
  UnrealEditor-Cmd <ThirdPerson.uproject> \
      -ExecutePythonScript=<this file> -nullrhi -unattended -nosplash

ROUTE MAP (design-o2-rename-lane 2026-07-30 + spike-facts of the same date;
notes.md section 5 is the calibration checklist this script answers):
  * UDE creation: `asset_tools.create_asset(name, dir, unreal.UserDefinedEnum,
    unreal.EnumFactory())` - LIVE-PROVEN (spike facts section E). The created
    enums carry FACTORY-DEFAULT enumerators: stock Python has NO enumerator
    read/write surface (section E), the baked decision accepts that (the
    grader never reads members; task.md records the residual), and the
    deferred alternative is the Aura MCP `edit_enumeration` lane.
  * BP member variables typed to the UDEs: RESOLVED 2026-07-30 (spike 3,
    live on UE 5.8) - the route is STOCK PYTHON, no MCP lane. The blocker was
    never `add_member_variable`: `unreal.EdGraphPinType()` constructs fine but
    its properties are PROTECTED, so `set_editor_property("pin_category", ...)`
    raises "Failed to find property" / "is protected and cannot be set". The
    working route is TEXT IMPORT on the struct:
        pin = unreal.EdGraphPinType()
        pin.import_text('(PinCategory="byte",PinSubCategoryObject='
                        '"/Game/Tasks/<id>/Enums/E_Kind.E_Kind")')
        unreal.BlueprintEditorLibrary.add_member_variable(bp, "Var", pin)
    NOTE the object-path form: <package path>.<asset name> (the doubled leaf),
    quoted. `pin.export_text()` reads the resolved object back
    (PinSubCategoryObject="/Script/Engine.UserDefinedEnum'/Game/...E_Kind'"),
    and `BlueprintEditorLibrary.get_member_variable_type(bp, "Var")` harvests
    the same pin off the SAVED Blueprint. Every attempt is still verified by
    the ONLY fact grading needs - the saved BP's registry dependency set must
    contain the enum package (after the rescan below) - plus the harvested
    type. No route -> named abort RENLANE-BPVAR-ROUTE-UNAVAILABLE (which now
    means the proven stock route REGRESSED, not that it is unknown).
  * Reference rename leg: `EditorAssetLibrary.rename_asset` (Lane A).
    LIVE-PROVEN for the UNREFERENCED case only (spike facts section F: old
    file deleted, no redirector). Referencer fixup + resave with loadable BP
    referencers is STILL UNPROVEN live -> every rename here prints
    RENLANE-CAL lines (old-gone / new-exists / BP-deps-updated) and the leg's
    in-process grade is the checkpoint.
  * Redirector manufacture (wrong-target variant): os.chmod the referencing
    BP file READ-ONLY before the rename - DetectReadOnlyPackages
    (AssetRenameManager.cpp:1322) then forces bCreateRedirector - restore
    afterwards. The DestinationObject tag of the manufactured redirector is
    printed RAW (RENLANE-CAL tag-shape ...) - THE design open question this
    boot pins.
  * DEPENDENCY EDGES ARE SCAN-TIME, NOT SAVE-TIME (live-proven 2026-07-30,
    spikes 4-6). A Blueprint created AND saved in the SAME editor session
    reports ZERO dependencies (not even /Script/Engine) and its referenced
    enum reports ZERO referencers - even after compile_blueprint + save_asset.
    `AssetRegistryDependencyOptions()` is NOT the cause: its defaults already
    carry bIncludeSoftPackageReferences=True and bIncludeHardPackageReferences
    =True (export_text confirmed), and a shipped Blueprint returns its deps
    under every flag combination. The fix, verified:
        ar.scan_paths_synchronous(["/Game/Tasks/<id>"], force_rescan=True)
        ar.wait_for_completion()
    A REAL grade is unaffected (submissions are overlaid before the editor
    boots, so the edges exist at the startup scan) - this bites ONLY
    in-process authoring-time grading, which is exactly what this script
    does. So `rescan()` is called by `grade()` itself (un-forgettable: every
    in-process grade rescans first) and before every other dependency /
    referencer / redirector-AssetData read.
  * IN-SESSION DELETE IS A ONE-WAY DOOR - THE TOMBSTONE LAW (live-proven
    2026-07-30, probe 2; THE reason this script is multi-boot). Once a
    package is DELETED in a session - which is exactly what rename_asset's
    Lane A fixup does to the old package - the registry never tells the
    truth about that path again for the rest of the boot, and it lies in
    BOTH directions at once:
      - ``get_assets_by_path(<folder>)`` DROPS the package permanently;
      - ``get_asset_by_object_path(<old>)`` and ``does_asset_exist(<old>)``
        keep returning the STALE pre-delete AssetData forever (class
        UserDefinedEnum, referencers now empty after the fixup) - which
        reads exactly like a PASSING orphan branch and is a FALSE PASS.
    Copying the baseline file back at the old path does NOT undo it. Every
    resurrection route was tried and ALL FAILED to restore by-path
    visibility: scan_paths_synchronous(force_rescan=True) on the Enums
    folder AND on the task root, the same with
    ignore_deny_list_scan_filters=True, scan_files_synchronous(<the exact
    .uasset file paths>, force_rescan=True), and
    scan_modified_asset_files(<the exact file paths>) - each followed by
    wait_for_completion. So an in-process "overlay simulation" after a
    rename CANNOT reproduce the graded state, and any vector taken there is
    worthless in both directions. It is therefore GONE from this script.
  * SAME-BOOT MULTI-LEG AUTHORING CORRUPTS THE BYTES (live-proven the same
    day, from the failed 3-legs-one-boot run): a rename leg run AFTER an
    earlier leg's file-level baseline restore renames against stale loaded
    objects, and the referencer fixup silently writes Blueprints with NO
    enum dependency at all (shipped BP_RefA deps=[], BP_RefB deps=[one of
    two]) - bytes that LOOK fine on disk and grade 9/11 in a cold boot. In
    a FRESH boot the identical four renames produce the correct
    BP_RefA=[E_AmmoKind,E_WeaponType], BP_RefB=[E_DamageType,E_ItemRarity].
    So each leg is authored in its OWN boot from the stashed baseline.

STATE MACHINE - ONE PHASE PER BOOT (the substrate must END every boot
holding EXACTLY the committed baseline). The runner drives the boots; the
phase is selected by RENLANE_PHASE (+ RENLANE_LEG):

  RENLANE_PHASE=baseline
      REFUSES to run if anything exists under the task content dir
      (leftover-clear step for a full rerun: delete
      UE-projects/ThirdPerson/Content/Tasks/t2-consistent-enum-names/ AND
      authoring/.baseline-stash/ - a rerun re-mints enum GUIDs, so the
      baseline and every leg must derive from ONE stash). Authors the four
      misnamed enums + the two referencing Blueprints, stashes them
      byte-for-byte, and pins the EMPTY leg's exact 0/11 in-process (this
      grade is trustworthy: the boot has deleted nothing).

  RENLANE_PHASE=author RENLANE_LEG=<leg>
      Fresh boot on the restored baseline. Pins the baseline 0/11 first
      (still trustworthy - nothing deleted yet), runs the leg's mutation,
      and harvests the deliverable into authoring/.staged/<leg>/ - a
      STAGING area, NOT the shipped tree. Takes NO in-process vector of the
      mutated state (see the tombstone law). Ends by restoring the
      substrate file-level from the stash and byte-comparing it.

  RENLANE_PHASE=verify RENLANE_LEG=<leg>
      The runner has ALREADY materialized the graded state FILE-LEVEL
      BEFORE this boot - stashed baseline + a copy-only overlay of
      .staged/<leg>/ - so this editor's FIRST scan sees every package and
      no tombstone exists anywhere in the session. This phase is the real
      graded lane, not a simulation of it: it asserts the on-disk inventory
      is exactly baseline+overlay, grades WITHOUT any rescan or mutation
      (the runner's editor does not rescan either), asserts the EXACT
      expected vector + substrings, and ONLY THEN PROMOTES
      .staged/<leg>/ into the shipped tree. Doubtful bytes never reach
      reference/ or discrimination/ at all.

Output contract (grep the EDITOR LOG, newest ThirdPerson*.log):
  RENLANE-CAL ...            calibration facts (routes, tag shape, fixup)
  RENLANE-VECTOR <state> passed=n/11 fails=[...]
  RENLANE-STAGED <leg> -> <staged file>     harvested, NOT yet shipped
  RENLANE-ASSET-OK <leg> -> <shipped file>  promoted after a cold-boot pass
  RENLANE-PHASE-OK <phase>   one phase completed
  RENLANE-*-UNAVAILABLE / RENLANE-ERROR   named aborts
  RENLANE-DONE               per-boot success marker; absent = FAILED
"""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import stat

import unreal

TASK_ID = "t2-consistent-enum-names"
PKG_DIR = "/Game/Tasks/%s" % TASK_ID
ENUM_DIR = "%s/Enums" % PKG_DIR

# (key, old name, new name) - must mirror the grader's hard-coded mapping.
ENUM_SPECS = (
    ("weapon_type", "WeaponType", "E_WeaponType"),
    ("ammo_kind", "E_ammo_kind", "E_AmmoKind"),
    ("damage_type", "enum_DamageType", "E_DamageType"),
    ("item_rarity", "ItemRarity", "E_ItemRarity"),
)
OLD_BY_KEY = {k: "%s/%s" % (ENUM_DIR, old) for k, old, _ in ENUM_SPECS}
NEW_BY_KEY = {k: "%s/%s" % (ENUM_DIR, new) for k, _, new in ENUM_SPECS}

# (BP name, variable-name/enum-key pairs)
BP_SPECS = (
    ("BP_RefA", (("WeaponKind", "weapon_type"), ("AmmoKind", "ammo_kind"))),
    ("BP_RefB", (("DamageKind", "damage_type"), ("RarityKind", "item_rarity"))),
)
BP_PKGS = {name: "%s/%s" % (PKG_DIR, name) for name, _ in BP_SPECS}

DECOY_PKG = "%s/DecoyEnum" % PKG_DIR  # wrong-target forward, task ROOT (not
#                                       Enums/ - C11 must stay green on that leg)

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
# Basket "bp", not the retired provenance-named set. The 2026-08-12 salvage
# moved the task and this line was missed: it is the one place the path is
# BUILT FROM COMPONENTS rather than written as a literal, so the path sweep's
# grep for the old set name slid straight past it. The runner reads
# $REPO/tasks/bp/$TASK_ID/authoring/{.baseline-stash,.staged}, so the mismatch
# had this script WRITING to the retired set's folder while the shell READ
# from tasks/bp/ -- which is what kept regenerating a retired folder on disk.
TASK_DIR = os.path.join(REPO, "tasks", "bp", TASK_ID)
SUB_ROOT = os.path.join(REPO, "UE-projects", "ThirdPerson", "Content", "Tasks",
                        TASK_ID)
ENUM_FS = os.path.join(SUB_ROOT, "Enums")
STASH = os.path.join(TASK_DIR, "authoring", ".baseline-stash")
#: Harvested-but-unverified leg deliverables. Nothing reaches reference/ or
#: discrimination/ until a COLD verify boot graded it in real graded-lane
#: conditions and asserted the exact expected vector (see the state machine).
STAGE = os.path.join(TASK_DIR, "authoring", ".staged")
GRADER = os.path.join(REPO, "tools", "verify-single", "introspect",
                      "consistent_enum_names.py")

EAL = unreal.EditorAssetLibrary
TOTAL = 11

BASELINE_FILES = tuple(
    [os.path.join("Enums", old + ".uasset") for _, old, _ in ENUM_SPECS]
    + [name + ".uasset" for name, _ in BP_SPECS])

# Exact-vector shorthand: the baseline (== empty leg) fails ALL 11.
ALL_CHECKS = (
    "new_asset_weapon_type", "new_asset_ammo_kind", "new_asset_damage_type",
    "new_asset_item_rarity", "old_path_retired_weapon_type",
    "old_path_retired_ammo_kind", "old_path_retired_damage_type",
    "old_path_retired_item_rarity", "refs_resolved_bp_ref_a",
    "refs_resolved_bp_ref_b", "folder_inventory",
)


def die(msg):
    print("RENLANE-ERROR %s" % msg)
    raise SystemExit(msg)


def save(path):
    if not EAL.save_asset(path, only_if_is_dirty=False):
        die("save_asset failed for %s" % path)


def registry():
    ar = unreal.AssetRegistryHelpers.get_asset_registry()
    if ar is None:
        die("asset registry unavailable")
    return ar


def rescan():
    """Force the registry to re-read the task folder.

    LOAD-BEARING, not cosmetic (live-proven 2026-07-30, spikes 4-6):
    dependency and referencer edges are SCAN-time, not save-time. A Blueprint
    created and saved in THIS editor session reports zero dependencies and
    its enum reports zero referencers until the folder is force-rescanned -
    so an in-process grade taken without this reads a phantom 0-edge world
    and would either ship doubtful bytes or manufacture a fake failure.
    Called by `grade()` itself, by every file-level restore/overlay step, and
    before every dependency / referencer / redirector-AssetData read.

    A rescan that cannot run is a NAMED ABORT: without it no in-process grade
    in this script means anything.
    """
    ar = registry()
    fn = getattr(ar, "scan_paths_synchronous", None)
    if fn is None:
        die("RENLANE-RESCAN-UNAVAILABLE AssetRegistry.scan_paths_synchronous "
            "is not exposed - dependency edges are scan-time (spikes 4-6), so "
            "no in-process grade in this script could be trusted")
    try:
        fn([PKG_DIR], force_rescan=True)
    except TypeError:
        try:
            fn([PKG_DIR])
        except Exception as e:  # noqa: BLE001
            die("RENLANE-RESCAN-FAILED scan_paths_synchronous(%s) raised %r"
                % (PKG_DIR, e))
    except Exception as e:  # noqa: BLE001
        die("RENLANE-RESCAN-FAILED scan_paths_synchronous(%s, force_rescan="
            "True) raised %r" % (PKG_DIR, e))
    with contextlib.suppress(Exception):
        ar.wait_for_completion()


def deps_of(pkg):
    ar = registry()
    out = ar.get_dependencies(pkg, unreal.AssetRegistryDependencyOptions())
    return sorted(str(x) for x in (out or []))


# --------------------------------------------------------------------------- #
# grading (the real verifier, in-process)                                      #
# --------------------------------------------------------------------------- #

def grade(rescan_first=True):
    """Run the real verifier in-process.

    ``rescan_first`` is TRUE for every AUTHORING-phase grade (fact 2, spikes
    4-6: edges are scan-time, and those boots create assets in-session) and
    FALSE for the VERIFY phase, which must read the registry exactly as the
    graded lane's editor does - first scan only, no forced rescan. The
    grader itself deliberately never rescans (notes.md decision #16).
    """
    if rescan_first:
        rescan()
    spec = importlib.util.spec_from_file_location("renlane_grader", GRADER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        mod.main()
    out = buf.getvalue()
    try:
        payload = out.split(mod.INTROSPECT_JSON_START)[1].split(
            mod.INTROSPECT_JSON_END)[0]
        checks = json.loads(payload.strip())["checks"]
    except Exception as e:  # noqa: BLE001
        die("grader output unparseable: %r; tail=%r" % (e, out[-400:]))
    return {c["id"]: (bool(c["passed"]), c.get("detail", "")) for c in checks}


def expect(state, vector, fail_exactly, substrings=()):
    """Assert the EXACT expected vector for a state (house law: every leg is
    graded in-process against exact expected vectors before shipping)."""
    if len(vector) != TOTAL:
        die("%s: vector has %d checks, expected %d" % (state, len(vector), TOTAL))
    fails = sorted(cid for cid, (ok, _) in vector.items() if not ok)
    print("RENLANE-VECTOR %s passed=%d/%d fails=%s"
          % (state, len(vector) - len(fails), len(vector), fails))
    if fails != sorted(fail_exactly):
        die("%s: failing set %s != expected %s" % (state, fails,
                                                   sorted(fail_exactly)))
    for cid, sub in substrings:
        detail = vector.get(cid, (None, ""))[1]
        if sub not in detail:
            die("%s: %s detail %r missing expected substring %r"
                % (state, cid, detail, sub))


BASELINE_SUBSTRINGS = [
    ("new_asset_weapon_type",
     "ENUM_NEW_MISSING_E_WeaponType path=%s" % NEW_BY_KEY["weapon_type"]),
    ("old_path_retired_weapon_type", "ENUM_OLD_STILL_REFERENCED_WeaponType"),
    ("refs_resolved_bp_ref_a", "BP_DEP_OLD_NAME_LIVE_BP_RefA old="),
    ("folder_inventory", "ENUM_FOLDER_INCOMPLETE missing="),
]


def grade_baseline(state, rescan_first=True):
    expect(state, grade(rescan_first), fail_exactly=list(ALL_CHECKS),
           substrings=BASELINE_SUBSTRINGS)


# --------------------------------------------------------------------------- #
# file-level helpers (stash / overlay simulation / restore)                    #
# --------------------------------------------------------------------------- #

def _fs(rel):
    return os.path.join(SUB_ROOT, rel.replace("/", os.sep))


def stash_baseline():
    os.makedirs(STASH, exist_ok=True)
    for rel in BASELINE_FILES:
        src = _fs(rel)
        if not os.path.isfile(src):
            die("stash: baseline file missing on disk: %s" % src)
        dst = os.path.join(STASH, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
    print("RENLANE-CAL baseline stashed: %d files -> %s"
          % (len(BASELINE_FILES), STASH))


def restore_baseline():
    """Return the substrate to EXACTLY the committed baseline, file-level,
    and prove it byte-for-byte.

    NO editor-route deletes and NO re-grade, both deliberately (2026-07-30
    tombstone law, module docstring): once this boot has deleted a package,
    the registry's account of that path is permanently wrong - a
    'baseline-restored' vector taken here would be a FALSE 0/11 assembled
    from stale AssetData, i.e. exactly the kind of reassuring lie this
    script exists to refuse. The file bytes are the only truth left in the
    session, so the file bytes are what gets asserted; the next boot's
    registry reads them fresh.
    """
    want = {rel.replace(os.sep, "/"): os.path.join(STASH,
                                                   rel.replace("/", os.sep))
            for rel in BASELINE_FILES}
    if os.path.isdir(SUB_ROOT):
        for root, _dirs, files in os.walk(SUB_ROOT):
            for f in files:
                p = os.path.join(root, f)
                rel = os.path.relpath(p, SUB_ROOT).replace(os.sep, "/")
                # An untouched baseline file is left ALONE. Not an
                # optimization: a package this boot still has loaded keeps a
                # file handle open on Windows, and deleting-then-recopying a
                # file that already holds the right bytes is a pure way to
                # manufacture a WinError 32.
                if rel in want and _same_bytes(p, want[rel]):
                    continue
                os.chmod(p, stat.S_IWRITE | stat.S_IREAD)  # undo chmod trick
                _remove_with_gc(p)
    for rel, src in want.items():
        dst = _fs(rel)
        if os.path.isfile(dst) and _same_bytes(dst, src):
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
    assert_substrate_is_baseline()


def _same_bytes(a, b):
    try:
        with open(a, "rb") as fa, open(b, "rb") as fb:
            return fa.read() == fb.read()
    except OSError:
        return False


def _remove_with_gc(path):
    """Delete a substrate file, forcing a GC pass if the editor still holds
    the package open. A file this boot cannot delete is a NAMED abort: it
    would leave the substrate carrying more than the committed baseline."""
    try:
        os.remove(path)
        return
    except OSError:
        pass
    with contextlib.suppress(Exception):
        unreal.SystemLibrary.collect_garbage()
    try:
        os.remove(path)
    except OSError as e:
        die("RENLANE-RESTORE-LOCKED cannot delete %s even after "
            "collect_garbage (%r) - the substrate would not end at the "
            "committed baseline" % (path, e))


def assert_substrate_is_baseline():
    """The per-boot exit invariant: the substrate holds EXACTLY the six
    committed baseline files, byte-identical to the stash."""
    on_disk = sorted(
        os.path.relpath(os.path.join(root, f), SUB_ROOT).replace(os.sep, "/")
        for root, _dirs, files in os.walk(SUB_ROOT) for f in files)
    want = sorted(r.replace(os.sep, "/") for r in BASELINE_FILES)
    if on_disk != want:
        die("final substrate inventory %s != committed baseline %s"
            % (on_disk, want))
    for rel in BASELINE_FILES:
        a, b = _fs(rel), os.path.join(STASH, rel.replace("/", os.sep))
        with open(a, "rb") as fa, open(b, "rb") as fb:
            if fa.read() != fb.read():
                die("final substrate file %s differs from the stashed "
                    "baseline byte-for-byte" % rel)
    print("RENLANE-CAL substrate state = exactly the %d committed baseline "
          "files, byte-identical to the stash" % len(BASELINE_FILES))


def _leg_content_dir(root, leg):
    return os.path.join(root, leg.replace("/", os.sep) if leg else "",
                        "Content", "Tasks", TASK_ID)


def stage(leg, rels):
    """HARVEST this leg's deliverable into the staging area.

    Staging, not shipping: these bytes are unverified until a cold verify
    boot grades them in real graded-lane conditions (`promote`).
    """
    dest_root = os.path.join(STAGE, leg)
    if os.path.isdir(dest_root):
        shutil.rmtree(dest_root)
    for rel in rels:
        src = _fs(rel)
        if not os.path.isfile(src):
            die("%s: %s not on disk" % (leg, src))
        dst = os.path.join(_leg_content_dir(STAGE, leg),
                           rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        print("RENLANE-STAGED %s -> %s" % (leg, dst))


def staged_rels(leg):
    """The overlay this leg's staging area carries, as substrate-relative
    paths (the runner copies exactly these over the baseline)."""
    root = _leg_content_dir(STAGE, leg)
    if not os.path.isdir(root):
        return []
    return sorted(
        os.path.relpath(os.path.join(r, f), root).replace(os.sep, "/")
        for r, _dirs, files in os.walk(root) for f in files)


def promote(leg, target_rel, rels):
    """SHIP a leg: move the staged deliverable into the task tree. Called
    ONLY after the cold verify boot asserted this leg's exact vector."""
    src_root = _leg_content_dir(STAGE, leg)
    dst_root = _leg_content_dir(TASK_DIR, target_rel)
    have = staged_rels(leg)
    if have != sorted(rels):
        die("%s: staged inventory %s != declared deliverable %s - refusing "
            "to promote" % (leg, have, sorted(rels)))
    if os.path.isdir(dst_root):
        shutil.rmtree(dst_root)
    for rel in rels:
        src = os.path.join(src_root, rel.replace("/", os.sep))
        dst = os.path.join(dst_root, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        print("RENLANE-ASSET-OK %s -> %s" % (leg, dst))


# --------------------------------------------------------------------------- #
# authoring routes                                                             #
# --------------------------------------------------------------------------- #

def _probe_types():
    for name in ("UserDefinedEnum", "EnumFactory", "Blueprint",
                 "BlueprintFactory", "EdGraphPinType"):
        if getattr(unreal, name, None) is None:
            die("RENLANE-TYPE-UNAVAILABLE unreal.%s is not exposed" % name)
    if getattr(unreal.BlueprintEditorLibrary, "add_member_variable", None) is None:
        die("RENLANE-BPVAR-ROUTE-UNAVAILABLE BlueprintEditorLibrary."
            "add_member_variable is not exposed - the stock route proven live "
            "on 2026-07-30 (notes.md section 5) has REGRESSED")
    probe = unreal.EdGraphPinType()
    for meth in ("import_text", "export_text"):
        if getattr(probe, meth, None) is None:
            die("RENLANE-BPVAR-ROUTE-UNAVAILABLE EdGraphPinType has no %s - "
                "the TEXT-IMPORT route is the only one that works (the pin's "
                "properties are PROTECTED, so set_editor_property raises); "
                "live-proven 2026-07-30, notes.md section 5" % meth)
    if getattr(registry(), "scan_paths_synchronous", None) is None:
        die("RENLANE-RESCAN-UNAVAILABLE AssetRegistry.scan_paths_synchronous "
            "is not exposed - dependency edges are scan-time (spikes 4-6), so "
            "no in-process grade in this script could be trusted")
    print("RENLANE-CAL type probe ok: EnumFactory + BlueprintFactory + "
          "add_member_variable + EdGraphPinType.import_text/export_text + "
          "AssetRegistry.scan_paths_synchronous exposed")


def _create_enum(pkg):
    d, name = pkg.rsplit("/", 1)
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    asset = tools.create_asset(name, d, unreal.UserDefinedEnum,
                               unreal.EnumFactory())
    if asset is None:
        die("RENLANE-ENUMFACTORY-UNAVAILABLE create_asset %s returned None"
            % pkg)
    save(pkg)
    return asset


def _create_bp(pkg):
    d, name = pkg.rsplit("/", 1)
    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", unreal.Actor)
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    bp = tools.create_asset(name, d, unreal.Blueprint, factory)
    if bp is None:
        die("create_asset %s returned None" % pkg)
    save(pkg)
    return bp


def _pin_text(category, enum_pkg):
    """Struct text for a member variable typed to a UserDefinedEnum.

    THE route (live-proven 2026-07-30): EdGraphPinType's properties are
    PROTECTED - set_editor_property("pin_category", ...) raises "Failed to
    find property" / "is protected and cannot be set" - so the pin is built by
    TEXT IMPORT. Note the object-path form UE wants: <package path>.<asset
    name>, the doubled leaf, quoted.
    """
    leaf = enum_pkg.rsplit("/", 1)[1]
    return ('(PinCategory="%s",PinSubCategoryObject="%s.%s")'
            % (category, enum_pkg, leaf))


def _pin_type(category, enum_pkg):
    """Build the pin by text import. Returns the pin, or None when this
    category did not RESOLVE the enum object (caller tries the next one, then
    aborts named) - proven by reading the struct back with export_text."""
    pt = unreal.EdGraphPinType()
    text = _pin_text(category, enum_pkg)
    try:
        pt.import_text(text)
    except Exception as e:  # noqa: BLE001 - a candidate that will not import
        print("RENLANE-CAL pin import_text(%s) raised %r" % (text, e))
        return None
    back = ""
    with contextlib.suppress(Exception):
        back = str(pt.export_text())
    if enum_pkg not in back:
        print("RENLANE-CAL pin category %r did NOT resolve %s (export_text="
              "%r)" % (category, enum_pkg, back))
        return None
    print("RENLANE-CAL pin category %r -> export_text=%s" % (category, back))
    return pt


def _drop_member_variable(bp, bp_pkg, var_name):
    """Undo a variable that carried no hard dependency. The baseline must
    NEVER ship a variable whose enum typing was not verified, so a removal
    that does not take is a named abort rather than a shrug."""
    lib = unreal.BlueprintEditorLibrary
    for meth in ("remove_member_variable", "delete_member_variable"):
        fn = getattr(lib, meth, None)
        if fn is None:
            continue
        with contextlib.suppress(Exception):
            fn(bp, var_name)
            break
    with contextlib.suppress(Exception):
        lib.compile_blueprint(bp)
    with contextlib.suppress(Exception):
        EAL.save_asset(bp_pkg, only_if_is_dirty=False)
    names = []
    with contextlib.suppress(Exception):
        names = [str(n) for n in (lib.list_member_variable_names(bp) or [])]
    if var_name in names:
        die("RENLANE-BPVAR-UNDO-FAILED %s.%s survived the removal attempt - "
            "the baseline would ship a variable with no verified enum "
            "dependency" % (bp_pkg, var_name))


_RESCAN_PROOF = []


def _add_enum_variable(bp, bp_pkg, var_name, enum_key):
    """Add one member variable typed to the UDE via the text-import route.

    Verified by the ONE fact the grader reads - the saved BP's registry
    dependency set contains the enum package, AFTER the forced rescan (edges
    are scan-time) - plus the type harvested back off the saved Blueprint.
    """
    enum_pkg = OLD_BY_KEY[enum_key]
    if not EAL.does_asset_exist(enum_pkg):
        die("enum %s does not exist - cannot type %s.%s to it"
            % (enum_pkg, bp_pkg, var_name))
    for category in ("byte", "enum"):
        pt = _pin_type(category, enum_pkg)
        if pt is None:
            continue
        ok = False
        try:
            ok = bool(unreal.BlueprintEditorLibrary.add_member_variable(
                bp, var_name, pt))
        except Exception as e:  # noqa: BLE001
            print("RENLANE-CAL add_member_variable(%s, %s) raised %r"
                  % (bp_pkg, var_name, e))
        if not ok:
            continue
        unreal.BlueprintEditorLibrary.compile_blueprint(bp)
        save(bp_pkg)
        # THE fact-2 pin, recorded once from live evidence: the same saved
        # Blueprint reports no edges until the folder is force-rescanned.
        stale = deps_of(bp_pkg)
        rescan()
        fresh = deps_of(bp_pkg)
        if not _RESCAN_PROOF:
            _RESCAN_PROOF.append(True)
            print("RENLANE-CAL dependency edges are SCAN-time: %s deps "
                  "immediately after compile+save=%s, after "
                  "scan_paths_synchronous(force_rescan=True)=%s"
                  % (bp_pkg, stale, fresh))
        if enum_pkg in fresh:
            harvested = ""
            with contextlib.suppress(Exception):
                harvested = str(unreal.BlueprintEditorLibrary
                                .get_member_variable_type(bp, var_name)
                                .export_text())
            if enum_pkg not in harvested:
                die("RENLANE-BPVAR-TYPE-NOT-HARVESTABLE %s.%s: the SAVED "
                    "Blueprint's member-variable type does not carry %s "
                    "(get_member_variable_type export_text=%r) even though "
                    "the package dependency exists - the dependency may come "
                    "from something other than the variable typing; do not "
                    "ship until that is explained"
                    % (bp_pkg, var_name, enum_pkg, harvested))
            print("RENLANE-CAL %s.%s typed to %s via pin category %r "
                  "(dependency + harvested type verified)"
                  % (bp_pkg, var_name, enum_pkg, category))
            return
        # wrong category: the variable exists but carries no hard dep - undo
        _drop_member_variable(bp, bp_pkg, var_name)
    die("RENLANE-BPVAR-ROUTE-UNAVAILABLE no pin category produced a hard "
        "dependency %s -> %s via the text-import route that was live-proven "
        "2026-07-30 (notes.md section 5) - the route has REGRESSED; do not "
        "ship" % (bp_pkg, enum_pkg))


def _rename(old_pkg, new_pkg, expect_redirector=False):
    """One rename leg with the RENLANE-CAL prints that pin Lane A/B live
    semantics.

    Lane A is now LIVE-PROVEN (2026-07-30): with loadable Blueprint
    referencers the manager fixes them up, resaves them, and DELETES the old
    package - no redirector - exactly as the design's engine-source reading
    predicted.

    ``expect_redirector=True`` is RETAINED but no longer reachable from a
    default boot: no known headless route manufactures the residue (see the
    RETIRED note on BASE_LEGS). It stays wired, with its
    RENLANE-REDIRECTOR-NOT-CREATED abort and its tag-shape calibration print,
    so a future engine/SCC configuration can re-attempt the manufacture under
    RENLANE_TRY_REDIRECTOR=1 without re-deriving any of it.
    """
    ok = EAL.rename_asset(old_pkg, new_pkg)
    if not ok:
        die("RENLANE-RENAME-FAILED %s -> %s" % (old_pkg, new_pkg))
    # Fact 2: registry state after a file-changing op is only as fresh as the
    # last scan. Rescan BEFORE reading the old path's disposition (existence,
    # class, DestinationObject tag) so a stale index cannot invent a
    # RENLANE-REDIRECTOR-NOT-CREATED abort or a phantom tag shape.
    rescan()
    old_exists = EAL.does_asset_exist(old_pkg)
    new_exists = EAL.does_asset_exist(new_pkg)
    print("RENLANE-CAL rename %s -> %s: old_registered=%s new_registered=%s"
          % (old_pkg, new_pkg, old_exists, new_exists))
    if not new_exists:
        die("RENLANE-RENAME-FAILED new path missing after rename: %s" % new_pkg)
    if expect_redirector:
        ar = registry()
        ad = ar.get_asset_by_object_path(
            "%s.%s" % (old_pkg, old_pkg.rsplit("/", 1)[1]))
        cls = ""
        with contextlib.suppress(Exception):
            cls = str(ad.asset_class_path.asset_name) if ad else "<none>"
        if cls != "ObjectRedirector":
            die("RENLANE-REDIRECTOR-NOT-CREATED old=%s class=%r (the chmod "
                "read-only trick did not force bCreateRedirector)" % (old_pkg, cls))
        raw = None
        with contextlib.suppress(Exception):
            raw = ad.get_tag_value("DestinationObject")
        # THE tag-shape calibration print (design open question):
        print("RENLANE-CAL tag-shape DestinationObject raw=%r" % (raw,))


# --------------------------------------------------------------------------- #
# legs - AUTHOR halves only (the expected vectors live in LEG_SPECS and are    #
# asserted by the COLD verify boot, never here: see the tombstone law)         #
# --------------------------------------------------------------------------- #

def author_duplicate_not_rename():
    """The lazy copy: four correctly-named enums appear, nothing is renamed,
    the Blueprints are never touched (and so are NOT part of the
    deliverable)."""
    for key in NEW_BY_KEY:
        _create_enum(NEW_BY_KEY[key])
    rescan()


def author_one_left_behind():
    """Three of the four renamed; ItemRarity untouched, so BP_RefB keeps a
    live dependency on the old name."""
    for key in ("weapon_type", "ammo_kind", "damage_type"):
        _rename(OLD_BY_KEY[key], NEW_BY_KEY[key])
    rescan()


def _chmod_bp(bp_name, read_only):
    p = _fs(bp_name + ".uasset")
    os.chmod(p, stat.S_IREAD if read_only
             else (stat.S_IWRITE | stat.S_IREAD))


def author_redirector_wrong_target():
    """RETIRED 2026-07-30, OPT-IN ONLY (RENLANE_TRY_REDIRECTOR=1). Step 2's
    chmod trick does not force bCreateRedirector headless, so this leg aborts
    RENLANE-REDIRECTOR-NOT-CREATED on this box; it is kept verbatim for a
    future engine/SCC configuration. Its shape is pinned offline instead -
    TestTriStateContract::test_wrong_target_redirector_fails_by_name."""
    # 1. clean renames FIRST (BPs writable -> fixup resaves them), so the
    #    later read-only rename cannot be followed by a resave that rewrites
    #    BP_RefA's WeaponType import (ordering avoids the ambiguity the
    #    design flagged).
    for key in ("ammo_kind", "damage_type", "item_rarity"):
        _rename(OLD_BY_KEY[key], NEW_BY_KEY[key])
    # 2. the chmod trick: BP_RefA (the WeaponType referencer) goes read-only,
    #    forcing bCreateRedirector on the next rename.
    _chmod_bp("BP_RefA", read_only=True)
    try:
        _rename(OLD_BY_KEY["weapon_type"], DECOY_PKG, expect_redirector=True)
    finally:
        _chmod_bp("BP_RefA", read_only=False)
    # 3. the correct-named enum exists too (C1-C4 must stay green on this
    #    leg - the ONLY defect is the wrong-target forward).
    _create_enum(NEW_BY_KEY["weapon_type"])
    rescan()


def author_reference():
    """THE deliverable: all four renamed, both Blueprints fixed up + resaved
    by the rename manager (Lane A)."""
    for key in ("weapon_type", "ammo_kind", "damage_type", "item_rarity"):
        _rename(OLD_BY_KEY[key], NEW_BY_KEY[key])
    rescan()
    # Advisory only - the AUTHORITATIVE dependency read is the verify boot's
    # (this session has deleted four packages, so its registry is already
    # partly a tombstone; see the module docstring).
    for bp_name in BP_PKGS:
        print("RENLANE-CAL %s deps after full rename (in-session, ADVISORY): "
              "%s" % (bp_name, deps_of(BP_PKGS[bp_name])))


#: leg -> (shipped-tree target dir, author fn, deliverable rels, exact
#: failing-check set the COLD verify boot must observe, required substrings).
#: The deliverable rels double as the runner's copy-only overlay list.
#:
#: `empty` is not authored at all: its graded state IS the untouched
#: committed baseline, so it verifies with no overlay and promotes nothing -
#: which makes the verify pass a certification of the BASELINE bytes.
LEG_SPECS = {
    "empty": dict(
        target=None, author=None, deliverable=[],
        fail_exactly=list(ALL_CHECKS), substrings=BASELINE_SUBSTRINGS),
    "duplicate-not-rename": dict(
        target="discrimination/duplicate-not-rename",
        author=author_duplicate_not_rename,
        deliverable=["Enums/%s.uasset" % new for _, _, new in ENUM_SPECS],
        fail_exactly=["old_path_retired_weapon_type",
                      "old_path_retired_ammo_kind",
                      "old_path_retired_damage_type",
                      "old_path_retired_item_rarity",
                      "refs_resolved_bp_ref_a", "refs_resolved_bp_ref_b"],
        substrings=[
            ("refs_resolved_bp_ref_a",
             "BP_DEP_OLD_NAME_LIVE_BP_RefA old=%s" % OLD_BY_KEY["ammo_kind"]),
            ("old_path_retired_weapon_type",
             "ENUM_OLD_STILL_REFERENCED_WeaponType"),
            ("refs_resolved_bp_ref_b", "BP_DEP_OLD_NAME_LIVE_BP_RefB")]),
    "one-left-behind": dict(
        target="discrimination/one-left-behind",
        author=author_one_left_behind,
        deliverable=["Enums/E_WeaponType.uasset", "Enums/E_AmmoKind.uasset",
                     "Enums/E_DamageType.uasset", "BP_RefA.uasset",
                     "BP_RefB.uasset"],
        fail_exactly=["new_asset_item_rarity", "old_path_retired_item_rarity",
                      "refs_resolved_bp_ref_b", "folder_inventory"],
        substrings=[
            ("new_asset_item_rarity",
             "ENUM_NEW_MISSING_E_ItemRarity path=%s"
             % NEW_BY_KEY["item_rarity"]),
            ("old_path_retired_item_rarity",
             "ENUM_OLD_STILL_REFERENCED_ItemRarity"),
            ("refs_resolved_bp_ref_b", "BP_DEP_OLD_NAME_LIVE_BP_RefB"),
            ("folder_inventory", "ENUM_FOLDER_INCOMPLETE missing=")]),
    "reference": dict(
        target="reference", author=author_reference,
        deliverable=["Enums/%s.uasset" % new for _, _, new in ENUM_SPECS]
        + ["BP_RefA.uasset", "BP_RefB.uasset"],
        fail_exactly=[], substrings=[]),
    # Opt-in only (RENLANE_TRY_REDIRECTOR=1): the redirector residue is not
    # manufacturable headless on this box - live-proven three ways: (1)
    # rename_asset with LOADABLE Blueprint referencers always takes Lane A
    # (fixup in memory, referencers resaved, old package DELETED, no
    # redirector), CONFIRMING the design's engine-source prediction that
    # bCreateRedirector fires only on fixup-FAILURE conditions; (2) the chmod
    # read-only-referencer trick does not reach DetectReadOnlyPackages
    # headless (this script's own RENLANE-REDIRECTOR-NOT-CREATED abort
    # fired); (3) an UNLOADED MAP referencer cannot be arranged - a level
    # holding a placed instance of the referencing Blueprint references the
    # BLUEPRINT, not the enum, so the enum's referencer set never includes an
    # unloaded map. Python cannot construct a UObjectRedirector directly
    # either (DestinationObject is an unreflected C++ member). The leg, the
    # _rename(..., expect_redirector=True) capability and the named abort are
    # RETAINED so a future engine/SCC configuration can re-attempt the
    # manufacture without re-deriving any of it; until then the tri-state's
    # redirector branch is covered by the OFFLINE oracle only (MATRIX.md's
    # Coverage note). It aborts in the AUTHOR phase, so its verify-phase
    # expectations are never reached.
    "redirector-wrong-target": dict(
        target="discrimination/redirector-wrong-target",
        author=author_redirector_wrong_target,
        deliverable=["Enums/E_WeaponType.uasset", "Enums/E_AmmoKind.uasset",
                     "Enums/E_DamageType.uasset", "Enums/E_ItemRarity.uasset",
                     "Enums/WeaponType.uasset",  # the manufactured redirector
                     "DecoyEnum.uasset", "BP_RefA.uasset", "BP_RefB.uasset"],
        fail_exactly=["old_path_retired_weapon_type",
                      "refs_resolved_bp_ref_a"],
        substrings=[
            ("old_path_retired_weapon_type",
             "ENUM_OLD_REDIRECT_WRONG_TARGET_WeaponType got=%s" % DECOY_PKG),
            ("refs_resolved_bp_ref_a",
             "BP_DEP_OLD_NAME_LIVE_BP_RefA old=%s"
             % OLD_BY_KEY["weapon_type"])]),
}


def _spec(leg):
    spec = LEG_SPECS.get(leg)
    if spec is None:
        die("unknown RENLANE_LEG %r (want one of %s)"
            % (leg, sorted(LEG_SPECS)))
    return spec


# --------------------------------------------------------------------------- #
# phases (ONE per boot)                                                        #
# --------------------------------------------------------------------------- #

def phase_baseline():
    if os.path.isdir(SUB_ROOT) and os.listdir(SUB_ROOT):
        die("substrate already carries %s - refusing to overwrite. Leftover-"
            "clear step for a full rerun: delete that directory AND %s (a "
            "rerun re-mints enum GUIDs, so the baseline and every leg must "
            "derive from ONE stash)." % (SUB_ROOT, STASH))
    os.makedirs(ENUM_FS, exist_ok=True)
    for _key, old, _new in ENUM_SPECS:
        _create_enum("%s/%s" % (ENUM_DIR, old))
    for bp_name, var_specs in BP_SPECS:
        bp = _create_bp(BP_PKGS[bp_name])
        for var_name, enum_key in var_specs:
            _add_enum_variable(bp, BP_PKGS[bp_name], var_name, enum_key)
    rescan()
    stash_baseline()
    # The committed-baseline state IS the empty leg's graded state. This
    # in-process 0/11 is TRUSTWORTHY (this boot has deleted nothing, so no
    # tombstone exists); the `empty` verify boot re-pins it cold anyway.
    grade_baseline("empty-in-authoring-boot")
    assert_substrate_is_baseline()


def phase_author(leg):
    spec = _spec(leg)
    if spec["author"] is None:
        die("leg %r has no author phase (its graded state is the untouched "
            "baseline) - run RENLANE_PHASE=verify for it" % leg)
    if not os.path.isdir(STASH):
        die("RENLANE_PHASE=author needs the baseline stash at %s (run "
            "RENLANE_PHASE=baseline first)" % STASH)
    # Trustworthy: a fresh boot on the restored baseline, nothing deleted yet.
    grade_baseline("preflight-%s" % leg)
    spec["author"]()
    stage(leg, spec["deliverable"])
    restore_baseline()


def phase_verify(leg):
    """Grade the REAL graded lane: the runner already materialized
    baseline+overlay on disk BEFORE this boot, so the first registry scan saw
    everything and no tombstone exists. No rescan, no mutation, no
    simulation."""
    spec = _spec(leg)
    want = sorted(set(r.replace(os.sep, "/") for r in BASELINE_FILES)
                  | set(spec["deliverable"]))
    on_disk = sorted(
        os.path.relpath(os.path.join(root, f), SUB_ROOT).replace(os.sep, "/")
        for root, _dirs, files in os.walk(SUB_ROOT) for f in files)
    if on_disk != want:
        die("RENLANE-VERIFY-SUBSTRATE-WRONG %s: on disk %s != baseline+"
            "overlay %s - the runner did not materialize the graded state"
            % (leg, on_disk, want))
    print("RENLANE-CAL verify substrate for %s = %d baseline + %d overlay "
          "file(s), materialized before the boot"
          % (leg, len(BASELINE_FILES), len(spec["deliverable"])))
    expect("verify-%s" % leg, grade(rescan_first=False),
           fail_exactly=spec["fail_exactly"], substrings=spec["substrings"])
    if spec["target"]:
        promote(leg, spec["target"], spec["deliverable"])
    else:
        print("RENLANE-CAL %s promotes nothing (its graded state is the "
              "committed baseline itself)" % leg)
    restore_baseline()


# --------------------------------------------------------------------------- #
# main                                                                         #
# --------------------------------------------------------------------------- #

PHASES = {"baseline": None, "author": phase_author, "verify": phase_verify}


def main():
    phase = os.environ.get("RENLANE_PHASE", "").strip()
    leg = os.environ.get("RENLANE_LEG", "").strip()
    if phase not in PHASES:
        die("RENLANE_PHASE must be one of %s (got %r); the runner "
            "run_author_all_assets.sh drives every boot" % (sorted(PHASES),
                                                            phase))
    _probe_types()
    if phase == "baseline":
        phase_baseline()
    else:
        if not leg:
            die("RENLANE_PHASE=%s needs RENLANE_LEG=<leg> (one of %s)"
                % (phase, sorted(LEG_SPECS)))
        PHASES[phase](leg)
    print("RENLANE-PHASE-OK %s%s" % (phase, (" " + leg) if leg else ""))
    print("RENLANE-DONE")


main()

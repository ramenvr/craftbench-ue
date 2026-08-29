"""Author the kp-derived-class-search CORPUS BASELINE + REFERENCE report.

Run headless on the ThirdPerson substrate project (authoring only, no render):
  UnrealEditor-Cmd <ThirdPerson.uproject> \
      -ExecutePythonScript=<this file> -nullrhi -unattended -nosplash

This task ships a verifier-authored CORPUS as substrate baseline and a text
REPORT as the only deliverable, so the flow is:

  1. Build the five corpus Blueprints at their real content paths
     (/Game/Tasks/kp-derived-class-search/corpus/): BP_MachineBase
     (parent: the engine's placeable-actor root), BP_DrillRig (parent:
     BP_MachineBase), BP_HeavyDrillRig (parent: BP_DrillRig - the
     transitive child), BP_MachineBaseplate and BP_ScoutRig (parent: the
     engine root - the two red herrings). Bare classes on purpose: the
     graded fact is DERIVATION, and every extra authored feature is extra
     failure surface. NO event-graph logic anywhere (K2 graph wiring is not
     authorable from stock python; this corpus needs none - class parentage
     only).
  2. Write the reference report from READ-BACK truth: derivation is
     recomputed from the saved classes via class_is_child_of only (the
     direct parent is computed as the most-derived corpus ancestor, so no
     protected reflection and no super-struct walk is ever read).
  3. GRADE IN-PROCESS with the real verifier script
     (tools/verify-single/introspect/kp_derived_class_search.py,
     stdout captured, CRAFTBENCH-INTROSPECT-JSON parsed); harvest ONLY on a
     10/10 vector.
  4. Harvest the REPORT into tasks/python/kp-derived-class-search/
     reference/ and DELETE it from the substrate. The corpus STAYS in the
     substrate - it is the committed baseline, and this script prints one
     KDBS-CORPUS line per on-disk corpus file so the commit step knows
     exactly what to add.

Fail-closed pattern (author_all_assets.py precedent): every step verifies
its own result and die()s loudly; the KDBS-DONE marker prints ONLY on full
success - its absence means FAILED. TASK_DIR is derived from this file's
own location (tasks/<basket>/<id>/aids/), never a hardcoded basket.

UE 5.8 python cautions honoured (each burned us before):
  * CDOs via ``unreal.get_default_object(cls)`` ONLY - NEVER
    ``cls.get_default_object()`` (it resolves against the class of the
    instance and poisons everything downstream; refgate catch 2026-08-12).
  * NO reads of protected reflection properties (UbergraphPages,
    EdGraphPinType pins, new_variables) - nothing here needs them.
  * Components would go through
    ``unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)`` - this
    corpus deliberately has none.
  * BP creation via BlueprintFactory works; K2 GRAPH WIRING does not - the
    corpus is designed to need no graphs at all. THE ONE UNPROVEN STEP is
    BlueprintFactory with a Blueprint GENERATED class as parent_class (the
    BP-of-BP chain). If it refuses, this script die()s naming the MCP graph
    lane (create the two child Blueprints via the desktop editor / MCP
    ``create_assets``/``edit_blueprint``, then re-run this aid - it skips
    corpus members that already exist AND verifies their parentage before
    proceeding).
  * Asset renames leave registry tombstones - nothing here renames an
    asset; every asset is created once at its final path.
  * CLEANUP TREATS DISK AS TRUTH: after a validated harvest, a stale
    in-memory registry row is a KDBS-WARN, never a die.

Output contract (grep the EDITOR LOG, newest ThirdPerson*.log):
  KDBS-SPELLING <step>=<winning route>
  KDBS-CORPUS <substrate-relative corpus file to commit>
  KDBS-VECTOR passed=<n>/10 fails=[ids]
  KDBS-HARVEST <task-relative destination>
  KDBS-WARN <non-fatal oddity>
  KDBS-DONE               (success marker; absent = FAILED)
"""
import contextlib
import importlib.util
import io
import json
import os
import shutil

import unreal

TASK_ID = "kp-derived-class-search"
CORPUS_PKG = "/Game/Tasks/%s/corpus" % TASK_ID

BASE_NAME = "BP_MachineBase"
DRILL_NAME = "BP_DrillRig"
HEAVY_NAME = "BP_HeavyDrillRig"
BASEPLATE_NAME = "BP_MachineBaseplate"
SCOUT_NAME = "BP_ScoutRig"

# (name, parent) in creation order - parents before children. None = engine
# placeable-actor root (unreal.Actor); a string = the generated class of the
# already-created corpus member with that name.
CORPUS_PLAN = (
    (BASE_NAME, None),
    (DRILL_NAME, BASE_NAME),
    (HEAVY_NAME, DRILL_NAME),
    (BASEPLATE_NAME, None),
    (SCOUT_NAME, None),
)
CORPUS_NAMES = tuple(name for name, _parent in CORPUS_PLAN)

# Repo layout, derived from this file living at tasks/<basket>/<id>/aids/.
_HERE = os.path.dirname(os.path.abspath(__file__))
TASK_DIR = os.path.abspath(os.path.join(_HERE, ".."))
REPO = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
SUBSTRATE = os.path.join(REPO, "UE-projects", "ThirdPerson")
SUBSTRATE_CORPUS = os.path.join(SUBSTRATE, "Content", "Tasks", TASK_ID,
                                "corpus")
SUBSTRATE_REPORTS = os.path.join(SUBSTRATE, "Content", "Tasks", TASK_ID,
                                 "reports")
REPORT_FILE = os.path.join(SUBSTRATE_REPORTS, "derived.txt")
REFERENCE_DIR = os.path.join(TASK_DIR, "reference")
REFERENCE_REPORT = os.path.join(REFERENCE_DIR, "Content", "Tasks", TASK_ID,
                                "reports", "derived.txt")
GRADER = os.path.join(REPO, "tools", "verify-single", "introspect",
                      "kp_derived_class_search.py")

EAL = unreal.EditorAssetLibrary


def die(msg):
    print("KDBS-ERROR %s" % msg)
    raise SystemExit(msg)


_SPELLING_LOG = {}


def note_spelling(step, spelling):
    if step not in _SPELLING_LOG:
        _SPELLING_LOG[step] = spelling
        print("KDBS-SPELLING %s=%s" % (step, spelling))


def asset_path(name):
    return "%s/%s" % (CORPUS_PKG, name)


def class_path(name):
    return "%s/%s.%s_C" % (CORPUS_PKG, name, name)


def generated_class(name):
    cls = unreal.load_object(None, class_path(name))
    if cls is None:
        die("generated class unresolvable at %s" % class_path(name))
    return cls


def child_of(child_cls, base_cls):
    lib = getattr(unreal, "MathLibrary", None)
    fn = getattr(lib, "class_is_child_of", None) if lib is not None else None
    if fn is None:
        die("MathLibrary.class_is_child_of is not exposed to Python")
    return bool(fn(child_cls, base_cls))


# --------------------------------------------------------------------------- #
# 1. Corpus: five bare Blueprints, parents before children                     #
# --------------------------------------------------------------------------- #

def create_corpus_bp(name, parent_cls):
    """One bare Blueprint at its final path; compile, save, verify."""
    factory = unreal.BlueprintFactory()
    try:
        factory.set_editor_property("parent_class", parent_cls)
    except Exception as e:  # noqa: BLE001
        die("BlueprintFactory refused parent_class=%r for %s: %r - if the "
            "parent is a Blueprint generated class this is THE unproven "
            "BP-of-BP step (notes.md section 4): create %s via the desktop "
            "editor / MCP graph lane with that parent, then re-run this aid "
            "(it skips existing corpus members and verifies their parentage)"
            % (parent_cls, name, name))
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    bp = tools.create_asset(name, CORPUS_PKG, unreal.Blueprint, factory)
    if bp is None:
        die("create_asset failed at %s - if the parent is a Blueprint "
            "generated class this is THE unproven BP-of-BP step; use the "
            "MCP graph lane fallback (notes.md section 4) and re-run"
            % asset_path(name))
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    if not EAL.save_asset(asset_path(name), only_if_is_dirty=False):
        die("save_asset failed for %s" % asset_path(name))
    if not EAL.does_asset_exist(asset_path(name)):
        die("saved corpus asset does not resolve at %s" % asset_path(name))


def build_corpus():
    """Create every corpus member that does not already exist (idempotent so
    the MCP-lane fallback can pre-create the hard ones), then verify EVERY
    pinned parentage fact by read-back regardless of who created what."""
    for name, parent_name in CORPUS_PLAN:
        if EAL.does_asset_exist(asset_path(name)):
            print("KDBS-WARN corpus member %s already exists; verifying "
                  "parentage only" % name)
            continue
        if parent_name is None:
            parent_cls = unreal.Actor
        else:
            parent_cls = generated_class(parent_name)
        create_corpus_bp(name, parent_cls)
        note_spelling("factory_parent_%s" % name,
                      "engine_root" if parent_name is None else parent_name)

    # Read-back verification of the whole pinned truth table.
    classes = {name: generated_class(name) for name in CORPUS_NAMES}
    base = classes[BASE_NAME]
    cdo = unreal.get_default_object(base)  # the ONE correct CDO route
    if cdo is None or not isinstance(cdo, unreal.Actor):
        die("BP_MachineBase CDO is not a placeable actor (read back %r)"
            % (cdo,))
    facts = (
        (DRILL_NAME, BASE_NAME, True),
        (HEAVY_NAME, DRILL_NAME, True),
        (HEAVY_NAME, BASE_NAME, True),   # the transitive fact itself
        (BASEPLATE_NAME, BASE_NAME, False),
        (SCOUT_NAME, BASE_NAME, False),
        (DRILL_NAME, HEAVY_NAME, False),  # direction sanity
    )
    for child_name, base_name, want in facts:
        got = child_of(classes[child_name], classes[base_name])
        if got is not want:
            die("parentage read-back: child_of(%s, %s) = %r, wanted %r"
                % (child_name, base_name, got, want))
    return classes


# --------------------------------------------------------------------------- #
# 2. Report from READ-BACK truth (class_is_child_of only)                      #
# --------------------------------------------------------------------------- #

def compute_derived(classes):
    """[(name, direct_parent_name)] for every corpus member derived from the
    base, direct parent = the MOST-DERIVED corpus ancestor. Uses only
    class_is_child_of - no super-struct walk, no protected reflection."""
    out = []
    for name in CORPUS_NAMES:
        if name == BASE_NAME:
            continue
        if not child_of(classes[name], classes[BASE_NAME]):
            continue
        ancestors = [other for other in CORPUS_NAMES
                     if other != name and child_of(classes[name],
                                                   classes[other])]
        if not ancestors:
            die("%s derives from the base but has no corpus ancestor" % name)
        direct = None
        for cand in ancestors:
            if all(cand == other or child_of(classes[cand], classes[other])
                   for other in ancestors):
                direct = cand
                break
        if direct is None:
            die("no most-derived ancestor among %s for %s"
                % (ancestors, name))
        out.append((name, direct))
    if not out:
        die("computed derived set is empty - corpus authoring went wrong")
    return sorted(out)


def build_report(classes):
    lines = ["derived name=%s parent=%s" % (name, parent)
             for name, parent in compute_derived(classes)]
    os.makedirs(SUBSTRATE_REPORTS, exist_ok=True)
    with open(REPORT_FILE, "w", encoding="ascii", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    print("KDBS-REPORT %d lines" % len(lines))


# --------------------------------------------------------------------------- #
# 3. Grade in-process with the REAL grader; harvest only on 10/10              #
# --------------------------------------------------------------------------- #

def load_grader():
    spec = importlib.util.spec_from_file_location("kdbs_grader", GRADER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def grade_in_process(mod):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        mod.main()
    out = buf.getvalue()
    try:
        payload = out.split(mod.INTROSPECT_JSON_START)[1].split(
            mod.INTROSPECT_JSON_END)[0]
        checks = json.loads(payload.strip())["checks"]
    except Exception as e:  # noqa: BLE001
        die("grader output unparseable: %r; raw=%r" % (e, out[-500:]))
    return {c["id"]: (bool(c["passed"]), c.get("detail", "")) for c in checks}


def harvest():
    if not os.path.isfile(REPORT_FILE):
        die("nothing to harvest at %s" % REPORT_FILE)
    os.makedirs(os.path.dirname(REFERENCE_REPORT), exist_ok=True)
    shutil.copy2(REPORT_FILE, REFERENCE_REPORT)
    print("KDBS-HARVEST %s"
          % os.path.relpath(REFERENCE_REPORT, TASK_DIR).replace(os.sep, "/"))
    # The corpus stays in the substrate as committed baseline; enumerate it
    # for the commit step.
    corpus_files = sorted(os.listdir(SUBSTRATE_CORPUS)) \
        if os.path.isdir(SUBSTRATE_CORPUS) else []
    expected = sorted("%s.uasset" % name for name in CORPUS_NAMES)
    if corpus_files != expected:
        die("substrate corpus files %s != expected %s"
            % (corpus_files, expected))
    for fname in corpus_files:
        print("KDBS-CORPUS %s" % (
            "UE-projects/ThirdPerson/Content/Tasks/%s/corpus/%s"
            % (TASK_ID, fname)))


def cleanup():
    """Leave the substrate exactly as this task ships it: corpus present,
    reports absent. DISK IS TRUTH here - after the validated harvest above,
    any stale in-memory/asset-registry oddity is a KDBS-WARN, never a die."""
    if os.path.isdir(SUBSTRATE_REPORTS):
        shutil.rmtree(SUBSTRATE_REPORTS, ignore_errors=True)
    if os.path.isdir(SUBSTRATE_REPORTS):
        die("filesystem residue remains at %s" % SUBSTRATE_REPORTS)
    # The corpus must still be intact on disk (it is the shipped baseline).
    corpus_files = sorted(os.listdir(SUBSTRATE_CORPUS)) \
        if os.path.isdir(SUBSTRATE_CORPUS) else []
    expected = sorted("%s.uasset" % name for name in CORPUS_NAMES)
    if corpus_files != expected:
        die("corpus baseline damaged during cleanup: %s" % corpus_files)
    # Registry view is advisory only after the disk checks passed.
    try:
        for name in CORPUS_NAMES:
            if not EAL.does_asset_exist(asset_path(name)):
                print("KDBS-WARN registry row stale for %s (disk file is "
                      "present and verified; ignoring)" % name)
    except Exception as e:  # noqa: BLE001
        print("KDBS-WARN registry probe raised %r after validated harvest; "
              "ignoring" % (e,))


def main():
    if os.path.isfile(REFERENCE_REPORT):
        die("reference report already exists at %s - delete it first to "
            "re-author" % REFERENCE_REPORT)
    if os.path.isfile(REPORT_FILE):
        die("substrate already carries %s - refusing to overwrite"
            % REPORT_FILE)

    classes = build_corpus()
    build_report(classes)

    vector = grade_in_process(load_grader())
    fails = sorted(cid for cid, (ok, _) in vector.items() if not ok)
    print("KDBS-VECTOR passed=%d/%d fails=%s"
          % (len(vector) - len(fails), len(vector), fails))
    if len(vector) != 10:
        die("grader emitted %d checks, wanted 10" % len(vector))
    if fails:
        for cid in fails:
            print("KDBS-FAIL %s: %s" % (cid, vector[cid][1]))
        die("reference did not grade 10/10; nothing harvested")

    harvest()
    cleanup()
    print("KDBS-DONE")


main()

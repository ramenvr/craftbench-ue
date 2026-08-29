"""Author the kp-config-source-audit BASELINE CORPUS + REFERENCE deliverable.

Run headless on the ThirdPerson substrate project (authoring only, no
render):
  UnrealEditor-Cmd <ThirdPerson.uproject> \
      -ExecutePythonScript=<this file> -nullrhi -unattended -nosplash

This task is unusual in the basket: the aid builds TWO different products
in one run:

  1. The SUBSTRATE BASELINE - four corpus config-carrier Blueprints
     (/Game/Tasks/kp-config-source-audit/corpus/Flash_*) and the one wiring
     artifact (/Game/Tasks/kp-config-source-audit/wiring/BP_DashRig, whose
     FlashSlot holds the live corpus class). These STAY in the substrate
     and must be COMMITTED as baseline content afterwards - the script
     prints one KPGCA-BASELINE line per file that needs committing.
  2. The REFERENCE deliverable - reports/config.txt, generated from
     READ-BACK truth (the real grader's own trace helpers, so report and
     grader can never disagree by construction), harvested into
     tasks/python/kp-config-source-audit/reference/ ONLY on a 12/12 in-process
     grade, then DELETED from the substrate (the agent must start without
     it).

Fail-closed pattern (author_all_assets.py / kp-audit precedent): every step
verifies its own result and die()s loudly; the KPGCA-DONE marker prints
ONLY on full success - its absence means FAILED. TASK_DIR is derived from
this file's own location (tasks/<basket>/<id>/aids/), never a hardcoded
basket.

UE 5.8 python lane laws baked in (each proven or burned-in this week):

  * CDOs: ``unreal.get_default_object(cls)`` is the ONLY legal route -
    ``cls.get_default_object()`` resolves against the class OF THE
    INSTANCE (the CDO of BlueprintGeneratedClass itself) and poisons every
    downstream read (refgate catch 2026-08-12 on the audit-report task).
    THIS SCRIPT NEEDS NO CDO AT ALL: every authored value lives on an SCS
    component template, so the foot-gun cannot arise; the law is recorded
    here so a future edit does not re-introduce it.
  * NO reads of protected reflection properties: no UbergraphPages, no
    EdGraphPinType pin walks. No BP member variables are authored and no
    K2 graph node is touched - BlueprintFactory creation works, K2 GRAPH
    WIRING does not, and this design needs none (component + property +
    asset-reference wiring only; the "reference" is FlashSlot's held
    class, a plain template property).
  * Components via ``unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)``
    (ENGINE subsystem - get_editor_subsystem raises).
  * SCS SOCKET attachment cannot be set from python
    (craftbench-scs-attachtoname-gap) - not needed: every part hangs off
    the default scene root.
  * Asset renames leave registry tombstones - nothing here renames an
    asset; every asset is created once at its final path. To RE-AUTHOR,
    delete /Game/Tasks/kp-config-source-audit in the editor, commit/clean the
    working tree, and run this aid again in a FRESH editor session.
  * Property names are underscore-folded - every set/read tries each
    plausible spelling and FAILS CLOSED if none sticks; winning spellings
    print as KPGCA-SPELLING lines for the notes.md calibration record.
  * CLEANUP TREATS DISK AS TRUTH: after a validated harvest, a stale
    in-memory asset-registry row is a KPGCA-WARN, never a die() - only a
    real on-disk residue (the report file still present) or real on-disk
    LOSS (a baseline .uasset missing) aborts.

Output contract (grep the EDITOR LOG, newest ThirdPerson*.log):
  KPGCA-SPELLING <step>=<winning spelling>
  KPGCA-VECTOR passed=<n>/12 fails=[ids]
  KPGCA-HARVEST <relative destination>
  KPGCA-BASELINE <substrate-relative path that must be committed>
  KPGCA-DONE               (success marker; absent = FAILED)
"""
import contextlib
import importlib.util
import io
import json
import os
import shutil

import unreal

TASK_ID = "kp-config-source-audit"
CORPUS_PKG = "/Game/Tasks/%s/corpus" % TASK_ID
WIRING_PKG = "/Game/Tasks/%s/wiring" % TASK_ID
WIRING_NAME = "BP_DashRig"
WIRING_BP = "%s/%s" % (WIRING_PKG, WIRING_NAME)
SLOT_NAME = "FlashSlot"
GLOW_NAME = "Glow"

# The verifier-owned constants (MUST mirror the grader's pins; the script
# cross-dies below if the imported grader disagrees).
LIVE_NAME = "Flash_Archive_2024"
LIVE_VALUE = 725.0
CORPUS_VALUES = (
    ("Flash_Primary", 1450.0),
    ("Flash_Current", 950.0),
    (LIVE_NAME, LIVE_VALUE),
    ("Flash_Test_DoNotUse", 1200.0),
)
LIVE_ASSET = "%s/%s" % (CORPUS_PKG, LIVE_NAME)
LIVE_CLASS_PATH = "%s.%s_C" % (LIVE_ASSET, LIVE_NAME)

# Repo layout, derived from this file living at tasks/<basket>/<id>/aids/.
_HERE = os.path.dirname(os.path.abspath(__file__))
TASK_DIR = os.path.abspath(os.path.join(_HERE, ".."))
REPO = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
SUBSTRATE = os.path.join(REPO, "UE-projects", "ThirdPerson")
SUBSTRATE_TASK_CONTENT = os.path.join(SUBSTRATE, "Content", "Tasks", TASK_ID)
REPORTS_DIR = os.path.join(SUBSTRATE_TASK_CONTENT, "reports")
REPORT_FILE = os.path.join(REPORTS_DIR, "config.txt")
REFERENCE_DIR = os.path.join(TASK_DIR, "reference")
GRADER = os.path.join(REPO, "tools", "verify-single", "introspect",
                      "kp_config_source_audit.py")

EAL = unreal.EditorAssetLibrary
SDS_LIB = unreal.SubobjectDataBlueprintFunctionLibrary


def die(msg):
    print("KPGCA-ERROR %s" % msg)
    raise SystemExit(msg)


_SPELLING_LOG = {}


def note_spelling(step, spelling):
    if step not in _SPELLING_LOG:
        _SPELLING_LOG[step] = spelling
        print("KPGCA-SPELLING %s=%s" % (step, spelling))


def set_prop(obj, value, *names):
    last = None
    for name in names:
        try:
            obj.set_editor_property(name, value)
            note_spelling(names[0], name)
            return
        except Exception as e:  # noqa: BLE001
            last = e
    die("no writable spelling among %s: %r" % (names, last))


# --------------------------------------------------------------------------- #
# grader import (the truth source for every read-back)                         #
# --------------------------------------------------------------------------- #

def load_grader():
    spec = importlib.util.spec_from_file_location("kpgca_grader", GRADER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # The one authoring-time consistency gate that makes constant drift
    # impossible: this aid's pins and the grader's pins must be identical.
    if mod.LIVE_ASSET != LIVE_ASSET or mod.LIVE_CLASS_PATH != LIVE_CLASS_PATH:
        die("grader pins disagree on the live asset: %s vs %s"
            % (mod.LIVE_ASSET, LIVE_ASSET))
    if abs(mod.LIVE_VALUE - LIVE_VALUE) > 1e-9:
        die("grader pins disagree on the live value: %s vs %s"
            % (mod.LIVE_VALUE, LIVE_VALUE))
    graded = dict((name, val) for _cid, name, val in mod.CORPUS_SPECS)
    ours = dict(CORPUS_VALUES)
    if graded != ours:
        die("grader corpus specs disagree: %s vs %s" % (graded, ours))
    return mod


# --------------------------------------------------------------------------- #
# 1. Corpus: four look-alike config carriers (BlueprintFactory + one light)    #
# --------------------------------------------------------------------------- #

def scene_root_handle(sds, bp):
    handles = list(sds.k2_gather_subobject_data_for_blueprint(bp))
    if not handles:
        die("subobject gather came back empty")
    named = []
    for h in handles:
        try:
            data = SDS_LIB.get_data(h)
            named.append((h, str(SDS_LIB.get_variable_name(data))))
        except Exception:  # noqa: BLE001
            named.append((h, "<unreadable>"))
    for h, name in named:
        if name == "DefaultSceneRoot":
            return h
    print("KPGCA-WARN no DefaultSceneRoot among %s; using last handle"
          % [n for _, n in named])
    return handles[-1]


def add_component(sds, bp, parent, cls, var_name):
    params = unreal.AddNewSubobjectParams(
        parent_handle=parent, new_class=cls, blueprint_context=bp)
    res = sds.add_new_subobject(params)
    handle, fail = (res if isinstance(res, tuple) else (res, None))
    ok = False
    try:
        ok = bool(handle.is_valid())
    except Exception:  # noqa: BLE001
        ok = handle is not None
    if not ok:
        die("add_new_subobject(%s) failed: %s" % (var_name, fail))
    if not sds.rename_subobject(handle, unreal.Text(var_name)):
        die("rename_subobject to %r failed" % var_name)
    data = SDS_LIB.get_data(handle)
    got = str(SDS_LIB.get_variable_name(data))
    if got != var_name:
        die("component name read back %r, wanted %r (case-sensitive gate)"
            % (got, var_name))
    obj = SDS_LIB.get_object(data)
    if obj is None:
        die("no template object behind %s" % var_name)
    return obj


def create_actor_blueprint(pkg_dir, name):
    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", unreal.Actor)
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    bp = tools.create_asset(name, pkg_dir, unreal.Blueprint, factory)
    if bp is None:
        die("create_asset failed at %s/%s" % (pkg_dir, name))
    return bp


def compile_and_save(bp, asset_path):
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    if not EAL.save_asset(asset_path, only_if_is_dirty=False):
        die("save_asset failed for %s" % asset_path)


def build_corpus(mod):
    for name, value in CORPUS_VALUES:
        asset_path = "%s/%s" % (CORPUS_PKG, name)
        bp = create_actor_blueprint(CORPUS_PKG, name)
        sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
        if sds is None:
            die("SubobjectDataSubsystem unavailable")
        root = scene_root_handle(sds, bp)
        glow = add_component(sds, bp, root, unreal.PointLightComponent,
                             GLOW_NAME)
        set_prop(glow, float(value), "intensity", "Intensity")
        compile_and_save(bp, asset_path)
        # Read-back verification through the GRADER's own truth helper -
        # if the grader cannot read what we just wrote, fail NOW, not at
        # refgate time.
        got, fail = mod._read_glow(asset_path)
        if got is None:
            die("grader cannot read %s after authoring: %s"
                % (asset_path, fail))
        if abs(got - value) > 1e-3:
            die("%s read back %s, wanted %s" % (asset_path, got, value))
        print("KPGCA-CORPUS %s value=%s" % (asset_path, got))


# --------------------------------------------------------------------------- #
# 2. Wiring: one rig whose FlashSlot holds the live corpus class               #
# --------------------------------------------------------------------------- #

def set_child_class(comp, cls):
    last = None
    for name in ("child_actor_class", "ChildActorClass"):
        try:
            comp.set_editor_property(name, cls)
            note_spelling("child_actor_class", name)
            return
        except Exception as e:  # noqa: BLE001
            last = e
    setter = getattr(comp, "set_child_actor_class", None)
    if setter is not None:
        try:
            setter(cls)
            note_spelling("child_actor_class", "set_child_actor_class")
            return
        except Exception as e:  # noqa: BLE001
            last = e
    die("no writable child-actor-class route: %r" % (last,))


def build_wiring(mod):
    live_cls = unreal.load_object(None, LIVE_CLASS_PATH)
    if live_cls is None:
        die("live corpus class unresolvable at %s" % LIVE_CLASS_PATH)
    bp = create_actor_blueprint(WIRING_PKG, WIRING_NAME)
    sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    if sds is None:
        die("SubobjectDataSubsystem unavailable")
    root = scene_root_handle(sds, bp)
    slot = add_component(sds, bp, root, unreal.ChildActorComponent, SLOT_NAME)
    set_child_class(slot, live_cls)
    compile_and_save(bp, WIRING_BP)
    # Read-back verification through the grader's wiring route: reload and
    # walk the saved asset, exactly as grading will.
    fresh = EAL.load_asset(WIRING_BP)
    if fresh is None:
        die("wiring BP unloadable after save at %s" % WIRING_BP)
    slot_obj = None
    for got, obj in mod._scene_components(fresh):
        if got == SLOT_NAME:
            slot_obj = obj
            break
    if slot_obj is None:
        die("FlashSlot not found on the saved wiring BP")
    cls = mod._read_property(slot_obj, "child_actor_class", "ChildActorClass")
    cls_path = "None" if cls is None else str(cls.get_path_name())
    if cls_path != LIVE_CLASS_PATH:
        die("slot read back class %s, wanted %s"
            % (cls_path, LIVE_CLASS_PATH))
    print("KPGCA-WIRING %s slot_class=%s" % (WIRING_BP, cls_path))


# --------------------------------------------------------------------------- #
# 3. Report: written from a FRESH live trace (never transcribed from pins)     #
# --------------------------------------------------------------------------- #

def _fmt_num(v):
    v = float(v)
    if v == int(v):
        return "%d" % int(v)
    return "%.3f" % v


def build_report(mod):
    """Trace the wiring the way the grader does and write config.txt from
    what the trace RETURNS - the pins only cross-check, never supply."""
    fresh = EAL.load_asset(WIRING_BP)
    if fresh is None:
        die("report step could not load %s" % WIRING_BP)
    slot_obj = None
    for got, obj in mod._scene_components(fresh):
        if got == SLOT_NAME:
            slot_obj = obj
            break
    if slot_obj is None:
        die("report step found no FlashSlot")
    cls = mod._read_property(slot_obj, "child_actor_class", "ChildActorClass")
    if cls is None:
        die("report step read a None slot class")
    live_pkg = str(cls.get_path_name()).split(".")[0]
    value, fail = mod._read_glow(live_pkg)
    if value is None:
        die("report step could not read the wired asset: %s" % fail)
    # Authoring-time consistency: the trace must land on the pins.
    if live_pkg != LIVE_ASSET:
        die("trace landed on %s, pins say %s" % (live_pkg, LIVE_ASSET))
    if abs(value - LIVE_VALUE) > 1e-3:
        die("trace read value %s, pins say %s" % (value, LIVE_VALUE))
    lines = [
        "source asset=%s" % live_pkg,
        "value brightness=%s" % _fmt_num(value),
    ]
    os.makedirs(REPORTS_DIR, exist_ok=True)
    with open(REPORT_FILE, "w", encoding="ascii", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    print("KPGCA-REPORT %d lines" % len(lines))


# --------------------------------------------------------------------------- #
# 4. Grade in-process with the REAL grader; harvest only on 12/12              #
# --------------------------------------------------------------------------- #

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
    """Copy ONLY the report into reference/ - the corpus and wiring are
    substrate baseline, not submission overlay."""
    if not os.path.isfile(REPORT_FILE):
        die("nothing to harvest at %s" % REPORT_FILE)
    dest = os.path.join(REFERENCE_DIR, "Content", "Tasks", TASK_ID,
                        "reports", "config.txt")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copy2(REPORT_FILE, dest)
    print("KPGCA-HARVEST %s"
          % os.path.relpath(dest, TASK_DIR).replace(os.sep, "/"))


def list_baseline_files():
    """Every substrate file the human must COMMIT as baseline."""
    out = []
    for sub in ("corpus", "wiring"):
        root = os.path.join(SUBSTRATE_TASK_CONTENT, sub)
        if not os.path.isdir(root):
            die("expected baseline dir missing on disk: %s" % root)
        for dirpath, _dirs, files in os.walk(root):
            for name in files:
                out.append(os.path.join(dirpath, name))
    if len(out) < 5:
        die("baseline on disk has %d files, expected at least 5 (four "
            "corpus + one wiring)" % len(out))
    return out


def cleanup():
    """Leave the substrate as this task ships it: baseline PRESENT, report
    ABSENT. DISK IS TRUTH here - after the validated harvest above, a stale
    in-memory registry row downgrades to a WARN, never a die."""
    if os.path.isdir(REPORTS_DIR):
        shutil.rmtree(REPORTS_DIR, ignore_errors=True)
    if os.path.isdir(REPORTS_DIR):
        die("report residue remains on disk at %s" % REPORTS_DIR)
    # Baseline must still be on disk (the commit payload).
    for path in list_baseline_files():
        rel = os.path.relpath(path, SUBSTRATE).replace(os.sep, "/")
        print("KPGCA-BASELINE %s" % rel)
    # Registry cross-look is advisory only (disk already verified).
    for name, _value in CORPUS_VALUES:
        asset_path = "%s/%s" % (CORPUS_PKG, name)
        try:
            if not EAL.does_asset_exist(asset_path):
                print("KPGCA-WARN registry does not list %s but its bytes "
                      "are on disk; stale registry row, disk is truth"
                      % asset_path)
        except Exception as e:  # noqa: BLE001
            print("KPGCA-WARN registry probe raised %r for %s"
                  % (e, asset_path))


def main():
    for name, _value in CORPUS_VALUES:
        if EAL.does_asset_exist("%s/%s" % (CORPUS_PKG, name)):
            die("substrate already carries %s/%s - to re-author, delete "
                "/Game/Tasks/%s and run again in a FRESH editor session "
                "(registry tombstones)" % (CORPUS_PKG, name, TASK_ID))
    if EAL.does_asset_exist(WIRING_BP):
        die("substrate already carries %s - refusing to overwrite"
            % WIRING_BP)
    if os.path.isfile(REPORT_FILE):
        die("report already exists at %s - refusing to overwrite"
            % REPORT_FILE)
    if os.path.isdir(os.path.join(REFERENCE_DIR, "Content")):
        die("reference/ already populated - delete it first to re-author")

    mod = load_grader()
    build_corpus(mod)
    build_wiring(mod)
    build_report(mod)

    vector = grade_in_process(mod)
    fails = sorted(cid for cid, (ok, _) in vector.items() if not ok)
    print("KPGCA-VECTOR passed=%d/%d fails=%s"
          % (len(vector) - len(fails), len(vector), fails))
    if len(vector) != 12:
        die("grader emitted %d checks, wanted 12" % len(vector))
    if fails:
        for cid in fails:
            print("KPGCA-FAIL %s: %s" % (cid, vector[cid][1]))
        die("reference did not grade 12/12; nothing harvested")

    harvest()
    cleanup()
    print("KPGCA-DONE")


main()

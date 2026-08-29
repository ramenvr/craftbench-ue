"""Author the kp-blueprint-actor-audit-report REFERENCE deliverable.

Run headless on the ThirdPerson substrate project (authoring only, no render):
  UnrealEditor-Cmd <ThirdPerson.uproject> \
      -ExecutePythonScript=<this file> -nullrhi -unattended -nosplash

This task ships NO substrate baseline, so the flow is: build the three
artifacts at their real content paths (Blueprint -> level -> report), GRADE
THEM IN-PROCESS with the real verifier script
(tools/verify-single/introspect/kp_blueprint_actor_audit_report.py, stdout
captured, CRAFTBENCH-INTROSPECT-JSON parsed), harvest into
tasks/python/kp-blueprint-actor-audit-report/reference/ ONLY on a 20/20
vector, then delete everything from the substrate so it ends with no
/Game/Tasks/kp-blueprint-actor-audit-report folder at all.

Fail-closed pattern (author_all_assets.py precedent): every step verifies
its own result and die()s loudly; the KPAUDIT-DONE marker prints ONLY on
full success - its absence means FAILED. TASK_DIR is derived from this
file's own location (tasks/<basket>/<id>/aids/), never a hardcoded basket.

UE 5.8 python cautions honoured (each burned us before):
  * SCS component SOCKET attachment cannot be set from python
    (craftbench-scs-attachtoname-gap) - this design needs none: both
    components hang off the default scene root, no socket anywhere.
  * Asset renames leave registry tombstones - nothing here renames an
    asset; every asset is created once at its final path.
  * import_text on pins must be pinned exactly - no graph nodes are
    authored at all (components + variables + level only).
  * Property names in python are underscore-folded (and bools drop the
    leading 'b') - every set/read tries each plausible spelling and FAILS
    CLOSED if none sticks; winning spellings print as KPAUDIT-SPELLING
    lines for the notes.md calibration record.
  * BP member-variable creation from stock python is THE unproven step
    (notes.md section 4): BlueprintEditorLibrary.add_member_variable with
    an EdGraphPinType is tried across the plausible pin-category spellings
    ('bool'; 'real'/'double', 'real'/'float', 'float'). If no route works
    this script die()s with the MCP-graph-lane fallback named - it never
    ships a half-set Blueprint.

Output contract (grep the EDITOR LOG, newest ThirdPerson*.log):
  KPAUDIT-SPELLING <step>=<winning spelling>
  KPAUDIT-VECTOR passed=<n>/20 fails=[ids]
  KPAUDIT-HARVEST <relative destination>
  KPAUDIT-DONE               (success marker; absent = FAILED)
"""
import contextlib
import importlib.util
import io
import json
import os
import shutil

import unreal

TASK_ID = "kp-blueprint-actor-audit-report"
PKG_DIR = "/Game/Tasks/%s" % TASK_ID
BP_NAME = "BP_AuditTarget"
BP_PATH = "%s/%s" % (PKG_DIR, BP_NAME)
LEVEL_NAME = "L_AuditScene"
LEVEL_PATH = "%s/%s" % (PKG_DIR, LEVEL_NAME)

BODY_NAME = "Body"
BEACON_NAME = "Beacon"
FLAG_NAME = "Flagged"
SCORE_NAME = "Score"
CUBE_PATH = "/Engine/BasicShapes/Cube.Cube"
ALPHA = ("Audit_Alpha", (0.0, 0.0, 100.0))
BETA = ("Audit_Beta", (500.0, 0.0, 100.0))

# A neutral ENGINE map to park the editor on before deleting the task level.
# ThirdPerson's committed Default*Map (never a task map; checklist section 4).
NEUTRAL_MAP = "/Engine/Maps/Entry"

# Repo layout, derived from this file living at tasks/<basket>/<id>/aids/.
_HERE = os.path.dirname(os.path.abspath(__file__))
TASK_DIR = os.path.abspath(os.path.join(_HERE, ".."))
REPO = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
SUBSTRATE = os.path.join(REPO, "UE-projects", "ThirdPerson")
SUBSTRATE_TASK_CONTENT = os.path.join(SUBSTRATE, "Content", "Tasks", TASK_ID)
SUBSTRATE_EXT_ACTORS = os.path.join(
    SUBSTRATE, "Content", "__ExternalActors__", "Tasks", TASK_ID)
SUBSTRATE_EXT_OBJECTS = os.path.join(
    SUBSTRATE, "Content", "__ExternalObjects__", "Tasks", TASK_ID)
REFERENCE_DIR = os.path.join(TASK_DIR, "reference")
GRADER = os.path.join(REPO, "tools", "verify-single", "introspect",
                      "kp_blueprint_actor_audit_report.py")
REPORT_FILE = os.path.join(SUBSTRATE_TASK_CONTENT, "reports", "audit.txt")

EAL = unreal.EditorAssetLibrary
SDS_LIB = unreal.SubobjectDataBlueprintFunctionLibrary


def die(msg):
    print("KPAUDIT-ERROR %s" % msg)
    raise SystemExit(msg)


_SPELLING_LOG = {}


def note_spelling(step, spelling):
    if step not in _SPELLING_LOG:
        _SPELLING_LOG[step] = spelling
        print("KPAUDIT-SPELLING %s=%s" % (step, spelling))


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


def read_prop(obj, *names):
    last = None
    for name in names:
        try:
            return obj.get_editor_property(name)
        except Exception as e:  # noqa: BLE001
            last = e
    die("no readable spelling among %s: %r" % (names, last))


# --------------------------------------------------------------------------- #
# 1. Blueprint: factory, components, variables, defaults, compile, save        #
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
    print("KPAUDIT-WARN no DefaultSceneRoot among %s; using last handle"
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
        die("variable name read back %r, wanted %r (case-sensitive gate)"
            % (got, var_name))
    obj = SDS_LIB.get_object(data)
    if obj is None:
        die("no template object behind %s" % var_name)
    return obj


def _pin_type(category, sub=None):
    """An EdGraphPinType for a member variable; dies if unconstructible."""
    try:
        pin = unreal.EdGraphPinType()
    except Exception as e:  # noqa: BLE001
        die("EdGraphPinType not constructible from python: %r - fall back to "
            "the MCP graph lane (edit_blueprint) for the two variables and "
            "re-run this aid with ADD_VARIABLES disabled" % (e,))
    set_prop(pin, unreal.Name(category), "pin_category", "PinCategory")
    if sub is not None:
        try:
            pin.set_editor_property("pin_sub_category", unreal.Name(sub))
        except Exception:  # noqa: BLE001 - a sub-category miss is tolerable
            pass
    return pin


def add_member_variable(bp, name, pin_specs):
    """Add one BP member variable, trying each (category, sub) spec."""
    lib = getattr(unreal, "BlueprintEditorLibrary", None)
    fn = getattr(lib, "add_member_variable", None) if lib else None
    if fn is None:
        die("BlueprintEditorLibrary.add_member_variable is not exposed - "
            "fall back to the MCP graph lane (edit_blueprint / bp_agent) for "
            "the two variables, then re-run this aid with the variable step "
            "removed (notes.md section 4)")
    last = None
    for category, sub in pin_specs:
        try:
            if bool(fn(bp, unreal.Name(name), _pin_type(category, sub))):
                note_spelling("pin_%s" % name,
                              "%s/%s" % (category, sub or "-"))
                return
        except Exception as e:  # noqa: BLE001
            last = e
    die("add_member_variable(%s) failed on every pin spec %s: %r"
        % (name, pin_specs, last))


def compile_and_save_bp(bp):
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    if not EAL.save_asset(BP_PATH, only_if_is_dirty=False):
        die("save_asset failed for %s" % BP_PATH)


def generated_class():
    cls = unreal.load_object(None, "%s.%s_C" % (BP_PATH, BP_NAME))
    if cls is None:
        die("generated class unresolvable for %s" % BP_PATH)
    return cls


def default_object(cls):
    getter = getattr(cls, "get_default_object", None)
    if getter is not None:
        try:
            cdo = getter()
            if cdo is not None:
                note_spelling("cdo_route", "Class.get_default_object")
                return cdo
        except Exception:  # noqa: BLE001
            pass
    fn = getattr(unreal, "get_default_object", None)
    if fn is not None:
        cdo = fn(cls)
        if cdo is not None:
            note_spelling("cdo_route", "unreal.get_default_object")
            return cdo
    die("no CDO route for %s" % BP_PATH)


def build_blueprint():
    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", unreal.Actor)
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    bp = tools.create_asset(BP_NAME, PKG_DIR, unreal.Blueprint, factory)
    if bp is None:
        die("create_asset failed at %s" % BP_PATH)
    sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    if sds is None:
        die("SubobjectDataSubsystem unavailable")
    root = scene_root_handle(sds, bp)

    body = add_component(sds, bp, root, unreal.StaticMeshComponent, BODY_NAME)
    cube = unreal.load_object(None, CUBE_PATH)
    if cube is None:
        die("engine cube unloadable at %s" % CUBE_PATH)
    set_prop(body, cube, "static_mesh", "StaticMesh")

    add_component(sds, bp, root, unreal.PointLightComponent, BEACON_NAME)

    # Variables: bool + float (UE5 BP floats are double-backed; try both).
    add_member_variable(bp, FLAG_NAME, [("bool", None)])
    add_member_variable(bp, SCORE_NAME,
                        [("real", "double"), ("real", "float"),
                         ("float", None), ("double", None)])
    compile_and_save_bp(bp)

    # Defaults live on the CDO once compiled: set, recompile, save, verify.
    cdo = default_object(generated_class())
    set_prop(cdo, True, FLAG_NAME, "flagged")
    set_prop(cdo, 99.0, SCORE_NAME, "score")
    compile_and_save_bp(bp)

    cdo = default_object(generated_class())
    flag = read_prop(cdo, FLAG_NAME, "flagged")
    score = read_prop(cdo, SCORE_NAME, "score")
    if flag is not True:
        die("Flagged default read back %r, wanted True" % (flag,))
    if abs(float(score) - 99.0) > 1e-3:
        die("Score default read back %r, wanted 99.0" % (score,))
    return bp


# --------------------------------------------------------------------------- #
# 2. Level: new level, two labeled instances at exact spots, save              #
# --------------------------------------------------------------------------- #

def _level_subsystem():
    try:
        return unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    except Exception:  # noqa: BLE001
        return None


def new_level():
    les = _level_subsystem()
    if les is not None and getattr(les, "new_level", None) is not None:
        if bool(les.new_level(LEVEL_PATH)):
            note_spelling("new_level_route", "LevelEditorSubsystem.new_level")
            return
    legacy = getattr(unreal, "EditorLevelLibrary", None)
    if legacy is not None and getattr(legacy, "new_level", None) is not None:
        if bool(legacy.new_level(LEVEL_PATH)):
            note_spelling("new_level_route", "EditorLevelLibrary.new_level")
            return
    die("no new-level route created %s" % LEVEL_PATH)


def spawn_instance(gen_cls, label, location):
    loc = unreal.Vector(*location)
    actor = None
    try:
        eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    except Exception:  # noqa: BLE001
        eas = None
    if eas is not None and getattr(eas, "spawn_actor_from_class", None):
        actor = eas.spawn_actor_from_class(gen_cls, loc, unreal.Rotator())
    if actor is None:
        legacy = getattr(unreal, "EditorLevelLibrary", None)
        if legacy is not None and getattr(legacy, "spawn_actor_from_class", None):
            actor = legacy.spawn_actor_from_class(gen_cls, loc,
                                                  unreal.Rotator())
    if actor is None:
        die("spawn_actor_from_class produced no actor for %s" % label)
    actor.set_actor_label(label)
    got = str(actor.get_actor_label())
    if got != label:
        die("label read back %r, wanted %r" % (got, label))
    aloc = actor.get_actor_location()
    if max(abs(float(aloc.x) - location[0]), abs(float(aloc.y) - location[1]),
           abs(float(aloc.z) - location[2])) > 0.1:
        die("%s spawned at (%s, %s, %s), wanted %s"
            % (label, aloc.x, aloc.y, aloc.z, location))
    return actor


def save_level():
    les = _level_subsystem()
    if les is not None and getattr(les, "save_current_level", None) is not None:
        if bool(les.save_current_level()):
            note_spelling("save_level_route",
                          "LevelEditorSubsystem.save_current_level")
            return
    lib = getattr(unreal, "EditorLoadingAndSavingUtils", None)
    if lib is not None and getattr(lib, "save_dirty_packages", None) is not None:
        if bool(lib.save_dirty_packages(True, True)):
            note_spelling("save_level_route",
                          "EditorLoadingAndSavingUtils.save_dirty_packages")
            return
    die("no save-level route saved %s" % LEVEL_PATH)


def build_level(gen_cls):
    new_level()
    spawn_instance(gen_cls, *ALPHA)
    spawn_instance(gen_cls, *BETA)
    save_level()
    if not EAL.does_asset_exist(LEVEL_PATH):
        die("saved level does not resolve at %s" % LEVEL_PATH)


# --------------------------------------------------------------------------- #
# 3. Report: written from READ-BACK truth (same routes the grader uses)        #
# --------------------------------------------------------------------------- #

def build_report():
    """Write audit.txt from the graded artifacts by importing the REAL
    grader's truth helpers - the report is read back, never transcribed."""
    spec = importlib.util.spec_from_file_location("kpaudit_grader", GRADER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    bp = EAL.load_asset(BP_PATH)
    if bp is None:
        die("report step could not load %s" % BP_PATH)
    gen_cls = mod._generated_class(bp)
    parent = mod._parent_class_name(bp, gen_cls)
    components = sorted((name, mod._class_name(obj))
                        for name, obj in mod._scene_components(bp))
    clean, status = mod._compile_status_clean(bp)
    if not clean:
        die("Blueprint is not up to date at report time: %s" % status)

    if not mod._load_level():
        die("report step could not load %s" % LEVEL_PATH)
    instances = []
    for actor in mod._all_level_actors():
        if actor is None:
            continue
        if mod._is_instance_of(actor, gen_cls):
            loc = mod._location_of(actor)
            instances.append((str(actor.get_actor_label()), loc))
    if len(instances) != 2:
        die("report step found %d instances, wanted 2" % len(instances))

    lines = ["class name=%s parent=%s" % (BP_NAME, parent)]
    for name, cls_name in components:
        lines.append("component name=%s class=%s" % (name, cls_name))
    lines.append("variable name=%s type=bool" % FLAG_NAME)
    lines.append("variable name=%s type=float" % SCORE_NAME)
    lines.append("compile status=clean")
    for label, loc in sorted(instances):
        lines.append("instance label=%s location=%s,%s,%s"
                     % (label, _fmt_num(loc[0]), _fmt_num(loc[1]),
                        _fmt_num(loc[2])))
    os.makedirs(os.path.dirname(REPORT_FILE), exist_ok=True)
    with open(REPORT_FILE, "w", encoding="ascii", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    print("KPAUDIT-REPORT %d lines" % len(lines))
    return mod


def _fmt_num(v):
    v = float(v)
    if v == int(v):
        return "%d" % int(v)
    return "%.3f" % v


# --------------------------------------------------------------------------- #
# 4. Grade in-process with the REAL grader; harvest only on 20/20              #
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


def _copytree_into(src, dst):
    for root, _dirs, files in os.walk(src):
        for name in files:
            s = os.path.join(root, name)
            rel = os.path.relpath(s, src)
            d = os.path.join(dst, rel)
            os.makedirs(os.path.dirname(d), exist_ok=True)
            shutil.copy2(s, d)
            print("KPAUDIT-HARVEST %s"
                  % os.path.relpath(d, TASK_DIR).replace(os.sep, "/"))


def harvest():
    if not os.path.isdir(SUBSTRATE_TASK_CONTENT):
        die("nothing to harvest at %s" % SUBSTRATE_TASK_CONTENT)
    _copytree_into(SUBSTRATE_TASK_CONTENT,
                   os.path.join(REFERENCE_DIR, "Content", "Tasks", TASK_ID))
    # OFPA mirrors, if the editor saved the level One-File-Per-Actor. Both
    # prefixes are asset_writable in the ThirdPerson manifest.
    if os.path.isdir(SUBSTRATE_EXT_ACTORS):
        _copytree_into(SUBSTRATE_EXT_ACTORS,
                       os.path.join(REFERENCE_DIR, "Content",
                                    "__ExternalActors__", "Tasks", TASK_ID))
    if os.path.isdir(SUBSTRATE_EXT_OBJECTS):
        _copytree_into(SUBSTRATE_EXT_OBJECTS,
                       os.path.join(REFERENCE_DIR, "Content",
                                    "__ExternalObjects__", "Tasks", TASK_ID))


def cleanup():
    """Leave the substrate exactly as this task ships it: nothing at all."""
    # Park the editor on a neutral ENGINE map so the task level is deletable.
    les = _level_subsystem()
    parked = False
    if les is not None and getattr(les, "load_level", None) is not None:
        try:
            parked = bool(les.load_level(NEUTRAL_MAP))
        except Exception:  # noqa: BLE001
            parked = False
    if not parked:
        lib = getattr(unreal, "EditorLoadingAndSavingUtils", None)
        if lib is not None and getattr(lib, "load_map", None) is not None:
            parked = lib.load_map(NEUTRAL_MAP) is not None
    if not parked:
        die("could not park the editor off the task level; not deleting")
    if not EAL.delete_directory(PKG_DIR):
        die("delete_directory(%s) failed" % PKG_DIR)
    if EAL.does_asset_exist(BP_PATH) or EAL.does_asset_exist(LEVEL_PATH):
        die("assets still exist after delete")
    # Filesystem residue (the report + any OFPA leftovers) - remove and check.
    for path in (SUBSTRATE_TASK_CONTENT, SUBSTRATE_EXT_ACTORS,
                 SUBSTRATE_EXT_OBJECTS):
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
        if os.path.isdir(path):
            die("filesystem residue remains at %s" % path)


def main():
    if EAL.does_asset_exist(BP_PATH) or EAL.does_asset_exist(LEVEL_PATH):
        die("substrate already carries %s content - refusing to overwrite"
            % PKG_DIR)
    if os.path.isdir(os.path.join(REFERENCE_DIR, "Content")):
        die("reference/ already populated - delete it first to re-author")

    build_blueprint()
    build_level(generated_class())
    mod = build_report()

    vector = grade_in_process(mod)
    fails = sorted(cid for cid, (ok, _) in vector.items() if not ok)
    print("KPAUDIT-VECTOR passed=%d/%d fails=%s"
          % (len(vector) - len(fails), len(vector), fails))
    if len(vector) != 20:
        die("grader emitted %d checks, wanted 20" % len(vector))
    if fails:
        for cid in fails:
            print("KPAUDIT-FAIL %s: %s" % (cid, vector[cid][1]))
        die("reference did not grade 20/20; nothing harvested")

    harvest()
    cleanup()
    print("KPAUDIT-DONE")


main()

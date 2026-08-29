"""Author the t1-playable-level-bootstrap REFERENCE deliverable.

Run headless on the ThirdPerson substrate project (authoring only, no render):
  UnrealEditor-Cmd <ThirdPerson.uproject> \
      -ExecutePythonScript=<this file> -nullrhi -unattended -nosplash

This task ships NO substrate baseline and NO corpus (the workspace starts
empty - there is nothing to bake beyond the reference itself), so the flow
is: refuse to run on a dirty substrate -> author the two Blueprint assets
(rules + pawn, PROPERTY WIRING ONLY - no event-graph logic anywhere in this
design, because K2 graph wiring is not authorable from stock editor Python
and the graded outcome deliberately needs none) -> create the level at the
real content path -> place the floor and the single spawn marker -> set the
level's world-settings game-rules override (verifying every write by reading
it back) -> save -> GRADE IT IN-PROCESS with the real verifier script (12/12
required) -> harvest the saved files (.umap + 2 .uasset plus any
One-File-Per-Actor mirrors) into the task's reference/ tree -> unload ->
delete the staged assets. The substrate ends with no
/Game/Tasks/t1-playable-level-bootstrap folder at all.

Validation is the actual grader, not a re-implementation: the authored state
is scored by tools/verify-single/introspect/kp_playable_level_bootstrap.py
(stdout captured, CRAFTBENCH-INTROSPECT-JSON block parsed) and harvested
ONLY on a 12/12 vector. The level-load half of that grade rides the
map-load lane the kp-spawn / audit refgates already proved live under
-nullrhi; this run is additionally the LIVE SPIKE for the world-settings
write/read routes and the CDO pawn wiring - if either is dead here, the
task is blocked and this script dies loudly saying so.

Fail-closed pattern (mirrors tasks/python/kp-spawn-level-actors/aids/
author_reference.py): TASK_DIR is derived from this file's own location
(never a hardcoded basket, so tree moves survive); the KPBOOT-DONE marker is
printed ONLY on full success; every uncertain step dies loudly otherwise.

UE 5.8 lane laws honoured (each has burned a prior task):
  * CDO access is ``unreal.get_default_object(cls)`` ONLY - NEVER
    ``cls.get_default_object()`` (refgate catch 2026-08-12: the instance-
    method spelling resolves against the class OF THE INSTANCE and returns
    the CDO of BlueprintGeneratedClass itself, poisoning every downstream
    read AND write).
  * Property names are underscore-folded by the Python codegen, so every
    property write probes several spellings and VERIFIES BY READBACK
    (set_prop below); a wrong guess dies before anything is harvested.
  * NO reads of protected reflection properties (UbergraphPages,
    EdGraphPinType pins) - nothing here touches a graph.
  * BP creation via BlueprintFactory works; K2 GRAPH WIRING does not - this
    design needs component/property/asset-reference wiring only. (If a
    future variant needs a graph, that is an MCP-graph-lane authoring step,
    recorded fail-closed in notes.md - not a thing this aid may attempt.)
  * Components would go through
    ``unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)`` - this
    design needs NO added components (the pawn parents the stock Character,
    which already carries its capsule/mesh/movement natively).
  * No asset is ever RENAMED (renames leave Asset Registry tombstones that
    haunt later runs) - every name is final at creation time.
  * Cleanup treats DISK as the truth (measured 2026-08-11 on the kp-spawn
    run: the registry keeps a stale in-memory row for the just-open level
    until exit; dying on it would throw away an already-validated harvest).
    A stale registry row is a WARN; on-disk leftovers still die.

Output contract (grep the EDITOR LOG, newest ThirdPerson*.log):
  KPBOOT-SPELLING <property>=<winning name>
  KPBOOT-ASSET-OK <name>
  KPBOOT-ACTOR-OK <label>
  KPBOOT-WIRING-OK <fact>
  KPBOOT-VECTOR passed=<n>/12 fails=[ids]
  KPBOOT-HARVEST <relative path>
  KPBOOT-DONE               (success marker; absent = FAILED)
"""
import contextlib
import importlib.util
import io
import json
import os
import shutil

import unreal

TASK_ID = "t1-playable-level-bootstrap"
PKG_DIR = "/Game/Tasks/%s" % TASK_ID
LEVEL_NAME = "L_PlayableBootstrap"
LEVEL_ASSET = "%s/%s" % (PKG_DIR, LEVEL_NAME)

GM_NAME = "BP_BootstrapRules"
PAWN_NAME = "BP_BootstrapBody"
GM_ASSET = "%s/%s" % (PKG_DIR, GM_NAME)
PAWN_ASSET = "%s/%s" % (PKG_DIR, PAWN_NAME)
GM_CLASS_PATH = "%s.%s_C" % (GM_ASSET, GM_NAME)
PAWN_CLASS_PATH = "%s.%s_C" % (PAWN_ASSET, PAWN_NAME)

# A neutral ENGINE map to park the editor on before deleting the staged level
# (never a task map, and never a Content/ map - the startup-maps invariant).
PARK_MAP = "/Engine/Maps/Entry"

CUBE_MESH_PKG = "/Engine/BasicShapes/Cube"
CUBE_MESH_OBJ = "/Engine/BasicShapes/Cube.Cube"

# Placement (satisfies the grader's constants with margin: floor half-extent
# 50x20 = 1000 units >= 100; floor top at z=0; start at z=110 -> gap 110,
# inside the [-10, +500] band; start X,Y dead-center of the floor).
START_LOCATION = (0.0, 0.0, 110.0)
FLOOR_LOCATION = (0.0, 0.0, -50.0)
FLOOR_SCALE = (20.0, 20.0, 1.0)

EXPECTED_CHECKS = 12

# Repo layout, derived from this file living at tasks/<basket>/<id>/aids/.
_HERE = os.path.dirname(os.path.abspath(__file__))
TASK_DIR = os.path.abspath(os.path.join(_HERE, ".."))  # never a hardcoded basket
REPO = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
SUBSTRATE = os.path.join(REPO, "UE-projects", "ThirdPerson")
GRADER = os.path.join(REPO, "tools", "verify-single", "introspect",
                      "kp_playable_level_bootstrap.py")

# On-disk paths the save may produce (OFPA mirrors are optional: whether a new
# level saves One-File-Per-Actor depends on the project's world settings).
CONTENT_TASK_DIR = os.path.join(SUBSTRATE, "Content", "Tasks", TASK_ID)
UMAP_FILE = os.path.join(CONTENT_TASK_DIR, LEVEL_NAME + ".umap")
EXTERNAL_DIRS = (
    os.path.join(SUBSTRATE, "Content", "__ExternalActors__", "Tasks", TASK_ID),
    os.path.join(SUBSTRATE, "Content", "__ExternalObjects__", "Tasks", TASK_ID),
)
REFERENCE_DIR = os.path.join(TASK_DIR, "reference")

EAL = unreal.EditorAssetLibrary


def die(msg):
    print("KPBOOT-ERROR %s" % msg)
    raise SystemExit(msg)


# --------------------------------------------------------------------------- #
# subsystem / route helpers (each dies loudly rather than guessing)            #
# --------------------------------------------------------------------------- #

def _editor_subsystem(name):
    cls = getattr(unreal, name, None)
    if cls is None:
        return None
    try:
        return unreal.get_editor_subsystem(cls)
    except Exception:  # noqa: BLE001 - caller has a fallback route
        return None


def _level_subsystem_call(method, *args):
    """Try LevelEditorSubsystem.<method>, then EditorLevelLibrary.<method>."""
    les = _editor_subsystem("LevelEditorSubsystem")
    fn = getattr(les, method, None) if les is not None else None
    if fn is not None:
        return fn(*args)
    ell = getattr(unreal, "EditorLevelLibrary", None)
    fn = getattr(ell, method, None) if ell is not None else None
    if fn is not None:
        return fn(*args)
    # Third route (review catch 2026-08-12: the lane law names a THREE-route
    # loader): EditorLoadingAndSavingUtils spells the verbs differently.
    elsu = getattr(unreal, "EditorLoadingAndSavingUtils", None)
    alias = {"load_level": "load_map", "new_level": "new_blank_map",
             "save_current_level": "save_dirty_packages"}.get(method)
    fn = getattr(elsu, alias, None) if (elsu is not None and alias) else None
    if fn is not None:
        if method == "new_level":
            return fn(False)
        if method == "save_current_level":
            return fn(True, True)
        return fn(*args)
    die("no route for level operation %r (LevelEditorSubsystem, "
        "EditorLevelLibrary and EditorLoadingAndSavingUtils all unavailable)" % method)


def _spawn(cls, location):
    eas = _editor_subsystem("EditorActorSubsystem")
    fn = getattr(eas, "spawn_actor_from_class", None) if eas is not None else None
    if fn is None:
        ell = getattr(unreal, "EditorLevelLibrary", None)
        fn = getattr(ell, "spawn_actor_from_class", None) if ell is not None else None
    if fn is None:
        die("no spawn_actor_from_class route is exposed to Python")
    actor = fn(cls, unreal.Vector(*location), unreal.Rotator(0.0, 0.0, 0.0))
    if actor is None:
        die("spawn_actor_from_class(%r) returned None" % cls)
    return actor


_SPELLING_LOG = {}


def set_prop(obj, value, *names):
    """set_editor_property under the first accepted spelling; readback is the
    caller's duty (values like class refs need identity-shaped compares)."""
    last = None
    for name in names:
        try:
            obj.set_editor_property(name, value)
        except Exception as e:  # noqa: BLE001
            last = e
            continue
        if names[0] not in _SPELLING_LOG:
            _SPELLING_LOG[names[0]] = name
            print("KPBOOT-SPELLING %s=%s" % (names[0], name))
        return
    die("no writable spelling among %s: %r" % (names, last))


def read_prop(obj, *names):
    last = None
    for name in names:
        try:
            return obj.get_editor_property(name)
        except Exception as e:  # noqa: BLE001
            last = e
    die("no readable spelling among %s: %r" % (names, last))


def _vec3(v):
    return (float(v.x), float(v.y), float(v.z))


def _close(got, want, tol):
    return all(abs(g - w) <= tol for g, w in zip(got, want))


def _set_label(actor, label):
    actor.set_actor_label(label)
    got = str(actor.get_actor_label())
    if got != label:
        die("label readback %r, wanted %r" % (got, label))


def _default_object(cls):
    """unreal.get_default_object ONLY - see the module docstring lane law."""
    fn = getattr(unreal, "get_default_object", None)
    if fn is None:
        die("unreal.get_default_object is not exposed - the CDO wiring "
            "cannot be authored (and the grader could not read it either); "
            "stop and record it in notes.md")
    cdo = fn(cls)
    if cdo is None:
        die("get_default_object(%r) returned None" % cls)
    return cdo


# --------------------------------------------------------------------------- #
# the two Blueprint assets (BlueprintFactory; property wiring only)            #
# --------------------------------------------------------------------------- #

def _create_blueprint(name, parent_cls):
    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", parent_cls)
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    bp = tools.create_asset(name, PKG_DIR, unreal.Blueprint, factory)
    if bp is None:
        die("BlueprintFactory create_asset(%s, %s) returned None"
            % (name, PKG_DIR))
    print("KPBOOT-ASSET-OK %s" % name)
    return bp


def _generated_class(bp, class_path):
    lib = getattr(unreal, "BlueprintEditorLibrary", None)
    if lib is not None and getattr(lib, "generated_class", None) is not None:
        try:
            cls = lib.generated_class(bp)
            if cls is not None:
                return cls
        except Exception:  # noqa: BLE001 - fall through to load_object
            pass
    cls = unreal.load_object(None, class_path)
    if cls is None:
        die("generated class unresolvable at %s" % class_path)
    return cls


def _save_asset(asset_path):
    ok = False
    try:
        ok = bool(EAL.save_asset(asset_path, only_if_is_dirty=False))
    except TypeError:
        ok = bool(EAL.save_asset(asset_path))
    if not ok:
        die("save_asset(%s) reported failure" % asset_path)


def author_blueprints():
    """Create rules + pawn BPs, wire the pawn into the rules CDO, save both.

    Returns the rules generated class (for the world-settings write)."""
    gm_parent = getattr(unreal, "GameModeBase", None)
    pawn_parent = getattr(unreal, "Character", None)
    if gm_parent is None or pawn_parent is None:
        die("GameModeBase/Character parent classes are not exposed to Python")

    gm_bp = _create_blueprint(GM_NAME, gm_parent)
    pawn_bp = _create_blueprint(PAWN_NAME, pawn_parent)

    gm_cls = _generated_class(gm_bp, GM_CLASS_PATH)
    pawn_cls = _generated_class(pawn_bp, PAWN_CLASS_PATH)

    gm_cdo = _default_object(gm_cls)
    set_prop(gm_cdo, pawn_cls, "default_pawn_class", "DefaultPawnClass")
    got = read_prop(gm_cdo, "default_pawn_class", "DefaultPawnClass")
    if got is None or str(got.get_path_name()) != PAWN_CLASS_PATH:
        die("default pawn readback %r, wanted %s"
            % (got, PAWN_CLASS_PATH))
    print("KPBOOT-WIRING-OK default_pawn_class=%s" % PAWN_CLASS_PATH)

    _save_asset(PAWN_ASSET)
    _save_asset(GM_ASSET)
    return gm_cls


# --------------------------------------------------------------------------- #
# the level: floor + spawn marker + world-settings override                    #
# --------------------------------------------------------------------------- #

def _load_engine_mesh():
    mesh = EAL.load_asset(CUBE_MESH_PKG)
    if mesh is None:
        die("engine mesh %s failed to load" % CUBE_MESH_PKG)
    got = str(mesh.get_path_name())
    if got != CUBE_MESH_OBJ:
        die("engine mesh path readback %r, wanted %r" % (got, CUBE_MESH_OBJ))
    return mesh


def build_floor():
    cube = _load_engine_mesh()
    floor = _spawn(unreal.StaticMeshActor, FLOOR_LOCATION)
    cls = getattr(unreal, "StaticMeshComponent", None)
    if cls is None:
        die("StaticMeshComponent is not exposed to Python")
    comps = list(floor.get_components_by_class(cls) or [])
    if not comps:
        die("Floor: spawned mesh actor carries no static mesh component")
    comp = comps[0]
    assigned = False
    setter = getattr(comp, "set_static_mesh", None)
    if setter is not None:
        try:
            setter(cube)
            assigned = True
        except Exception:  # noqa: BLE001 - fall through to the property route
            assigned = False
    if not assigned:
        set_prop(comp, cube, "static_mesh", "StaticMesh")
    got = read_prop(comp, "static_mesh", "StaticMesh")
    if got is None or str(got.get_path_name()) != CUBE_MESH_OBJ:
        die("Floor: mesh readback %r, wanted %s" % (got, CUBE_MESH_OBJ))
    floor.set_actor_scale3d(unreal.Vector(*FLOOR_SCALE))
    got_scale = _vec3(floor.get_actor_scale3d())
    if not _close(got_scale, FLOOR_SCALE, 0.001):
        die("Floor: scale readback %s, wanted %s" % (got_scale, FLOOR_SCALE))
    got_loc = _vec3(floor.get_actor_location())
    if not _close(got_loc, FLOOR_LOCATION, 0.01):
        die("Floor: location readback %s, wanted %s"
            % (got_loc, FLOOR_LOCATION))
    _set_label(floor, "Floor")
    print("KPBOOT-ACTOR-OK Floor")


def build_start():
    cls = getattr(unreal, "PlayerStart", None)
    if cls is None:
        die("PlayerStart is not exposed to Python")
    start = _spawn(cls, START_LOCATION)
    got = _vec3(start.get_actor_location())
    if not _close(got, START_LOCATION, 0.01):
        die("Start: location readback %s, wanted %s" % (got, START_LOCATION))
    _set_label(start, "Start")
    print("KPBOOT-ACTOR-OK Start")


def _world_settings():
    """The open level's world-settings actor, via three routes (die on none)."""
    errors = []
    world = None
    ues = _editor_subsystem("UnrealEditorSubsystem")
    fn = getattr(ues, "get_editor_world", None) if ues is not None else None
    if fn is not None:
        try:
            world = fn()
        except Exception as e:  # noqa: BLE001
            errors.append(repr(e))
    if world is None:
        ell = getattr(unreal, "EditorLevelLibrary", None)
        fn = getattr(ell, "get_editor_world", None) if ell is not None else None
        if fn is not None:
            try:
                world = fn()
            except Exception as e:  # noqa: BLE001
                errors.append(repr(e))
    if world is not None:
        getter = getattr(world, "get_world_settings", None)
        if getter is not None:
            try:
                ws = getter()
                if ws is not None:
                    return ws
            except Exception as e:  # noqa: BLE001
                errors.append(repr(e))
        try:
            level = read_prop(world, "persistent_level", "PersistentLevel")
            if level is not None:
                ws = level.get_editor_property("world_settings")
                if ws is not None:
                    return ws
        except Exception as e:  # noqa: BLE001
            errors.append(repr(e))
    die("no world-settings route worked: %s - the grader's read routes "
        "would be blind too; stop and record it in notes.md" % errors)


def wire_world_settings(gm_cls):
    ws = _world_settings()
    set_prop(ws, gm_cls, "default_game_mode", "DefaultGameMode")
    got = read_prop(ws, "default_game_mode", "DefaultGameMode")
    if got is None or str(got.get_path_name()) != GM_CLASS_PATH:
        die("game-rules override readback %r, wanted %s"
            % (got, GM_CLASS_PATH))
    print("KPBOOT-WIRING-OK default_game_mode=%s" % GM_CLASS_PATH)


# --------------------------------------------------------------------------- #
# grade in-process with the REAL verifier                                      #
# --------------------------------------------------------------------------- #

def grade_in_process():
    """Run the real grader; return {check_id: (passed, detail)}."""
    spec = importlib.util.spec_from_file_location("kpboot_grader", GRADER)
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
        die("grader output unparseable: %r; raw=%r" % (e, out[-500:]))
    return {c["id"]: (bool(c["passed"]), c.get("detail", "")) for c in checks}


# --------------------------------------------------------------------------- #
# harvest + cleanup                                                            #
# --------------------------------------------------------------------------- #

def _harvest_tree(src_root, rel_root):
    """Copy an on-disk tree into reference/ preserving the submission path."""
    dst_root = os.path.join(REFERENCE_DIR, rel_root)
    for dirpath, _dirnames, filenames in os.walk(src_root):
        for filename in filenames:
            src = os.path.join(dirpath, filename)
            rel = os.path.relpath(src, src_root)
            dst = os.path.join(dst_root, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            print("KPBOOT-HARVEST %s"
                  % os.path.join(rel_root, rel).replace(os.sep, "/"))


def harvest():
    if not os.path.isfile(UMAP_FILE):
        die("saved level not on disk at %s" % UMAP_FILE)
    if os.path.isdir(REFERENCE_DIR) and any(os.scandir(REFERENCE_DIR)):
        die("reference/ is not empty - refusing to overwrite %s" % REFERENCE_DIR)
    _harvest_tree(CONTENT_TASK_DIR, "Content/Tasks/%s" % TASK_ID)
    for ext_dir in EXTERNAL_DIRS:
        if os.path.isdir(ext_dir):
            rel = os.path.relpath(ext_dir, os.path.join(SUBSTRATE))
            _harvest_tree(ext_dir, rel.replace(os.sep, "/"))
    for needed in (LEVEL_NAME + ".umap", GM_NAME + ".uasset",
                   PAWN_NAME + ".uasset"):
        path = os.path.join(REFERENCE_DIR, "Content", "Tasks", TASK_ID, needed)
        if not os.path.isfile(path):
            die("harvest produced no %s" % path)


def cleanup():
    """Park on a neutral engine map, then delete every staged asset/file."""
    parked = _level_subsystem_call("load_level", PARK_MAP)
    if not parked:
        die("could not park on %s before deleting the staged level" % PARK_MAP)
    try:
        EAL.delete_directory(PKG_DIR)
    except Exception as e:  # noqa: BLE001 - the disk sweep below is the gate
        print("KPBOOT-WARN delete_directory(%s) raised %r" % (PKG_DIR, e))
    # DISK is the truth (measured 2026-08-11 on the kp-spawn run: the
    # registry keeps a stale in-memory row for the just-open level until
    # exit; dying on it threw away an already-validated harvest). The
    # on-disk sweep below still dies.
    for asset in (LEVEL_ASSET, GM_ASSET, PAWN_ASSET):
        try:
            if EAL.does_asset_exist(asset):
                print("KPBOOT-WARN stale in-memory registry entry for %s "
                      "(disk is clean; the next session rescans)" % asset)
        except Exception:  # noqa: BLE001 - a broken probe changes nothing here
            pass
    for leftover in (CONTENT_TASK_DIR,) + EXTERNAL_DIRS:
        if os.path.isdir(leftover):
            shutil.rmtree(leftover, ignore_errors=True)
        if os.path.isdir(leftover) and any(os.scandir(leftover)):
            die("on-disk leftovers remain at %s" % leftover)


# --------------------------------------------------------------------------- #
# main                                                                         #
# --------------------------------------------------------------------------- #

def main():
    # Refuse to run on a dirty substrate: this task ships NO baseline.
    for asset in (LEVEL_ASSET, GM_ASSET, PAWN_ASSET):
        if EAL.does_asset_exist(asset):
            die("substrate already carries %s - refusing to overwrite" % asset)
    for pre_existing in (CONTENT_TASK_DIR,) + EXTERNAL_DIRS:
        if os.path.isdir(pre_existing) and any(os.scandir(pre_existing)):
            die("substrate already carries files under %s - clean it first"
                % pre_existing)

    gm_cls = author_blueprints()

    created = _level_subsystem_call("new_level", LEVEL_ASSET)
    if not created:
        die("new_level(%s) reported failure" % LEVEL_ASSET)

    build_floor()
    build_start()
    wire_world_settings(gm_cls)

    saved = _level_subsystem_call("save_current_level")
    if not saved:
        die("save_current_level reported failure")
    if not os.path.isfile(UMAP_FILE):
        die("save reported success but no file at %s" % UMAP_FILE)

    # The in-process grade re-loads the level exactly the way the L2I leg
    # will and re-reads the whole wiring chain. 12/12 or nothing is
    # harvested. NB the CDO/world-settings values it reads are the live
    # in-memory objects this session authored - the committed BYTES are
    # re-proven from a fresh session by `cb refgate` (the authoring-time
    # close); a save that silently dropped the wiring dies there, not here.
    vector = grade_in_process()
    fails = sorted(cid for cid, (ok, _) in vector.items() if not ok)
    print("KPBOOT-VECTOR passed=%d/%d fails=%s"
          % (len(vector) - len(fails), len(vector), fails))
    if len(vector) != EXPECTED_CHECKS:
        die("grader emitted %d checks, expected the constant %d"
            % (len(vector), EXPECTED_CHECKS))
    if fails:
        for cid in fails:
            print("KPBOOT-FAIL-DETAIL %s: %s" % (cid, vector[cid][1]))
        die("reference did not grade 12/12 - not harvesting")

    harvest()
    cleanup()
    print("KPBOOT-DONE")


main()

"""Author the kp-spawn-level-actors REFERENCE deliverable (the saved level).

Run headless on the ThirdPerson substrate project (authoring only, no render):
  UnrealEditor-Cmd <ThirdPerson.uproject> \
      -ExecutePythonScript=<this file> -nullrhi -unattended -nosplash

This task ships NO substrate baseline, so the flow is: refuse to run on a
dirty substrate -> create the level at the real content path -> spawn, label
and transform the six actors (verifying every write by reading it back) ->
save -> GRADE IT IN-PROCESS with the real verifier script (17/17 required) ->
harvest the saved files (.umap plus any One-File-Per-Actor mirrors) into the
task's reference/ tree -> unload -> delete the staged assets. The substrate
ends with no /Game/Tasks/kp-spawn-level-actors folder at all.

Validation is the actual grader, not a re-implementation: the authored level
is scored by tools/verify-single/introspect/kp_spawn_level_actors.py (stdout
captured, CRAFTBENCH-INTROSPECT-JSON block parsed) and harvested ONLY on a
17/17 vector. This run is also the LIVE SPIKE for the headless level-load
route (plan U1) the grader itself depends on - if the grader cannot open the
level here, the task is blocked and this script dies loudly saying so.

Fail-closed pattern (mirrors tasks/bp/t1-dawn-fog-lighting-rig/authoring/
author_all_assets.py): TASK_DIR is derived from this file's own location
(never a hardcoded basket, so tree moves survive); the KPSPAWN-DONE marker is
printed ONLY on full success; every uncertain step dies loudly otherwise.

UE 5.8 cautions honoured (each has burned a prior task):
  * Property names are underscore-folded by the Python codegen, so every
    property write probes several spellings and VERIFIES BY READBACK
    (set_prop below); a wrong guess dies before anything is harvested.
  * No asset is ever RENAMED (renames leave Asset Registry tombstones that
    haunt later runs) - every name is final at creation time.
  * No SCS component socket attachment is needed anywhere in this design
    (unsettable from Python on UE 5.8 - designs needing it are avoided).
  * No graph pins, so no import_text pinning applies.
  * The bounds region is a box-collision actor, NOT a brush-based volume:
    brush geometry cannot be built from stock editor Python, which is exactly
    why the task spec diverged from the sheet's nav-volume (divergence 2).

Output contract (grep the EDITOR LOG, newest ThirdPerson*.log):
  KPSPAWN-SPELLING <property>=<winning name>
  KPSPAWN-ACTOR-OK <label>
  KPSPAWN-VECTOR passed=<n>/17 fails=[ids]
  KPSPAWN-HARVEST <relative path>
  KPSPAWN-DONE               (success marker; absent = FAILED)
"""
import contextlib
import importlib.util
import io
import json
import os
import shutil

import unreal

TASK_ID = "kp-spawn-level-actors"
PKG_DIR = "/Game/Tasks/%s" % TASK_ID
LEVEL_NAME = "L_ActorLayout"
LEVEL_ASSET = "%s/%s" % (PKG_DIR, LEVEL_NAME)

# A neutral ENGINE map to park the editor on before deleting the staged level
# (never a task map, and never a Content/ map - the startup-maps invariant).
PARK_MAP = "/Engine/Maps/Entry"

CUBE_MESH_PKG = "/Engine/BasicShapes/Cube"
SPHERE_MESH_PKG = "/Engine/BasicShapes/Sphere"
CUBE_MESH_OBJ = "/Engine/BasicShapes/Cube.Cube"
SPHERE_MESH_OBJ = "/Engine/BasicShapes/Sphere.Sphere"

# Repo layout, derived from this file living at tasks/<basket>/<id>/aids/.
_HERE = os.path.dirname(os.path.abspath(__file__))
TASK_DIR = os.path.abspath(os.path.join(_HERE, ".."))  # never a hardcoded basket
REPO = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
SUBSTRATE = os.path.join(REPO, "UE-projects", "ThirdPerson")
GRADER = os.path.join(
    REPO, "tools", "verify-single", "introspect", "kp_spawn_level_actors.py")

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
    print("KPSPAWN-ERROR %s" % msg)
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
    die("no route for level operation %r (LevelEditorSubsystem and "
        "EditorLevelLibrary both unavailable)" % method)


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
    """set_editor_property under the first accepted spelling; readback-verified."""
    last = None
    for name in names:
        try:
            obj.set_editor_property(name, value)
        except Exception as e:  # noqa: BLE001
            last = e
            continue
        if names[0] not in _SPELLING_LOG:
            _SPELLING_LOG[names[0]] = name
            print("KPSPAWN-SPELLING %s=%s" % (names[0], name))
        return
    die("no writable spelling among %s: %r" % (names, last))


def _vec3(v):
    return (float(v.x), float(v.y), float(v.z))


def _close(got, want, tol):
    return all(abs(g - w) <= tol for g, w in zip(got, want))


def _set_label(actor, label):
    actor.set_actor_label(label)
    got = str(actor.get_actor_label())
    if got != label:
        die("label readback %r, wanted %r (labels are the grader's identity "
            "key and are case-sensitive)" % (got, label))


def _require_location(actor, want):
    got = _vec3(actor.get_actor_location())
    if not _close(got, want, 0.01):
        die("location readback %s, wanted %s" % (got, want))


def _load_engine_mesh(pkg_path, obj_path):
    mesh = EAL.load_asset(pkg_path)
    if mesh is None:
        die("engine mesh %s failed to load" % pkg_path)
    got = str(mesh.get_path_name())
    if got != obj_path:
        die("engine mesh path readback %r, wanted %r" % (got, obj_path))
    return mesh


def _assign_mesh(actor, mesh, obj_path, label):
    cls = getattr(unreal, "StaticMeshComponent", None)
    if cls is None:
        die("StaticMeshComponent is not exposed to Python")
    comps = list(actor.get_components_by_class(cls) or [])
    if not comps:
        die("%s: spawned mesh actor carries no static mesh component" % label)
    comp = comps[0]
    assigned = False
    setter = getattr(comp, "set_static_mesh", None)
    if setter is not None:
        try:
            setter(mesh)
            assigned = True
        except Exception:  # noqa: BLE001 - fall through to the property route
            assigned = False
    if not assigned:
        set_prop(comp, mesh, "static_mesh", "StaticMesh")
    got = comp.get_editor_property("static_mesh")
    if got is None or str(got.get_path_name()) != obj_path:
        die("%s: mesh readback %r, wanted %s"
            % (label, got, obj_path))


# --------------------------------------------------------------------------- #
# the six actors                                                               #
# --------------------------------------------------------------------------- #

def build_floor():
    cube = _load_engine_mesh(CUBE_MESH_PKG, CUBE_MESH_OBJ)
    floor = _spawn(unreal.StaticMeshActor, (0.0, 0.0, -50.0))
    _assign_mesh(floor, cube, CUBE_MESH_OBJ, "Floor")
    floor.set_actor_scale3d(unreal.Vector(20.0, 20.0, 1.0))
    got = _vec3(floor.get_actor_scale3d())
    if not _close(got, (20.0, 20.0, 1.0), 0.001):
        die("Floor: scale readback %s, wanted (20, 20, 1)" % (got,))
    _set_label(floor, "Floor")
    _require_location(floor, (0.0, 0.0, -50.0))
    print("KPSPAWN-ACTOR-OK Floor")


def build_start():
    cls = getattr(unreal, "PlayerStart", None)
    if cls is None:
        die("PlayerStart is not exposed to Python")
    start = _spawn(cls, (0.0, 0.0, 110.0))
    _set_label(start, "Start")
    _require_location(start, (0.0, 0.0, 110.0))
    print("KPSPAWN-ACTOR-OK Start")


def build_bounds():
    cls = getattr(unreal, "TriggerBox", None)
    if cls is None:
        die("TriggerBox is not exposed to Python")
    bounds = _spawn(cls, (0.0, 0.0, 200.0))
    box_cls = getattr(unreal, "BoxComponent", None)
    if box_cls is None:
        die("BoxComponent is not exposed to Python")
    boxes = list(bounds.get_components_by_class(box_cls) or [])
    if not boxes:
        die("Bounds: the spawned trigger actor carries no box component")
    box = boxes[0]
    setter = getattr(box, "set_box_extent", None)
    if setter is not None:
        setter(unreal.Vector(1000.0, 1000.0, 400.0))
    else:
        set_prop(box, unreal.Vector(1000.0, 1000.0, 400.0),
                 "box_extent", "BoxExtent")
    getter = getattr(box, "get_scaled_box_extent", None)
    if getter is None:
        die("Bounds: get_scaled_box_extent unavailable - the grader's extent "
            "route would be unreadable too; stop and record it in notes.md")
    got = _vec3(getter())
    if not _close(got, (1000.0, 1000.0, 400.0), 0.01):
        die("Bounds: scaled extent readback %s, wanted (1000, 1000, 400)"
            % (got,))
    _set_label(bounds, "Bounds")
    _require_location(bounds, (0.0, 0.0, 200.0))
    print("KPSPAWN-ACTOR-OK Bounds")


def build_enemies():
    sphere = _load_engine_mesh(SPHERE_MESH_PKG, SPHERE_MESH_OBJ)
    for label, location in (("Enemy_1", (300.0, 0.0, 110.0)),
                            ("Enemy_2", (-300.0, 0.0, 110.0)),
                            ("Enemy_3", (0.0, 300.0, 110.0))):
        enemy = _spawn(unreal.StaticMeshActor, location)
        _assign_mesh(enemy, sphere, SPHERE_MESH_OBJ, label)
        _set_label(enemy, label)
        _require_location(enemy, location)
        print("KPSPAWN-ACTOR-OK %s" % label)


# --------------------------------------------------------------------------- #
# grade in-process with the REAL verifier                                      #
# --------------------------------------------------------------------------- #

def grade_in_process():
    """Run the real grader; return {check_id: (passed, detail)}."""
    spec = importlib.util.spec_from_file_location("kpspawn_grader", GRADER)
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
            print("KPSPAWN-HARVEST %s"
                  % os.path.join(rel_root, rel).replace(os.sep, "/"))


def harvest():
    if not os.path.isfile(UMAP_FILE):
        die("saved level not on disk at %s" % UMAP_FILE)
    if os.path.isdir(REFERENCE_DIR) and any(os.scandir(REFERENCE_DIR)):
        die("reference/ is not empty - refusing to overwrite %s" % REFERENCE_DIR)
    _harvest_tree(CONTENT_TASK_DIR,
                  "Content/Tasks/%s" % TASK_ID)
    for ext_dir in EXTERNAL_DIRS:
        if os.path.isdir(ext_dir):
            rel = os.path.relpath(ext_dir, os.path.join(SUBSTRATE))
            _harvest_tree(ext_dir, rel.replace(os.sep, "/"))
    harvested_umap = os.path.join(
        REFERENCE_DIR, "Content", "Tasks", TASK_ID, LEVEL_NAME + ".umap")
    if not os.path.isfile(harvested_umap):
        die("harvest produced no %s" % harvested_umap)


def cleanup():
    """Park on a neutral engine map, then delete every staged asset/file."""
    parked = _level_subsystem_call("load_level", PARK_MAP)
    if not parked:
        die("could not park on %s before deleting the staged level" % PARK_MAP)
    try:
        EAL.delete_directory(PKG_DIR)
    except Exception as e:  # noqa: BLE001 - the disk sweep below is the gate
        print("KPSLA-WARN delete_directory(%s) raised %r" % (PKG_DIR, e))
    # DISK is the truth (measured 2026-08-11: the registry keeps a stale
    # in-memory row for the just-open level until exit; dying on it threw
    # away an already-validated harvest). The on-disk sweep below still dies.
    if EAL.does_asset_exist(LEVEL_ASSET):
        print("KPSLA-WARN stale in-memory registry entry for %s (disk is "
              "clean; the next session rescans)" % LEVEL_ASSET)
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
    if EAL.does_asset_exist(LEVEL_ASSET):
        die("substrate already carries %s - refusing to overwrite" % LEVEL_ASSET)
    for pre_existing in (CONTENT_TASK_DIR,) + EXTERNAL_DIRS:
        if os.path.isdir(pre_existing) and any(os.scandir(pre_existing)):
            die("substrate already carries files under %s - clean it first"
                % pre_existing)

    created = _level_subsystem_call("new_level", LEVEL_ASSET)
    if not created:
        die("new_level(%s) reported failure" % LEVEL_ASSET)

    build_floor()
    build_start()
    build_bounds()
    build_enemies()

    saved = _level_subsystem_call("save_current_level")
    if not saved:
        die("save_current_level reported failure")
    if not os.path.isfile(UMAP_FILE):
        die("save reported success but no file at %s" % UMAP_FILE)

    # The in-process grade is also the live spike for the grader's unspiked
    # headless level-load route (plan U1): the grader re-loads the level
    # itself. 17/17 or nothing is harvested.
    vector = grade_in_process()
    fails = sorted(cid for cid, (ok, _) in vector.items() if not ok)
    print("KPSPAWN-VECTOR passed=%d/%d fails=%s"
          % (len(vector) - len(fails), len(vector), fails))
    if len(vector) != 17:
        die("grader emitted %d checks, expected the constant 17" % len(vector))
    if fails:
        for cid in fails:
            print("KPSPAWN-FAIL-DETAIL %s: %s" % (cid, vector[cid][1]))
        die("reference did not grade 17/17 - not harvesting")

    harvest()
    cleanup()
    print("KPSPAWN-DONE")


main()

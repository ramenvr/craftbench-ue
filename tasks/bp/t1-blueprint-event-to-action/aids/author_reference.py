"""Authoring aid for t1-blueprint-event-to-action (map + baseline BP + reference).

Run headless on the CraftBenchTemplate substrate with a REAL off-screen RHI
(map authoring crashes under -nullrhi):

  UnrealEditor-Cmd.exe <repo>/UE-projects/CraftBenchTemplate/CraftBenchTemplate.uproject \
      -ExecutePythonScript="<this file> <stage>" -unattended -nopause -nosplash -RenderOffScreen

Stages (the one positional arg; default "map"):

  map      Create the committed substrate binaries this task needs:
             1. the BASELINE Blueprint /Game/Tasks/t1-blueprint-event-to-action/
                BP_DelayedMover -- an EMPTY subclass of ADelayedMoverActor (no
                event implementations);
             2. a file-level backup of that baseline .uasset (used by the
                harvest stage to restore the substrate);
             3. the map /Game/Maps/t1-blueprint-event-to-action/L_DelayedMove
                with exactly one placed BP_DelayedMover instance at
                (0, -400, 150) -- MUST match the fixture's StartLocation --
                and the ADelayedMoveFunctionalTest fixture actor.
           Prints T1BEA-MAP-DONE only on full success.

  harvest  AFTER the reference graph has been authored into BP_DelayedMover
           (see THE MANUAL STEP below): copy the edited .uasset into the task's
           reference/ tree, then restore the substrate's BP_DelayedMover from
           the stage-"map" backup so the committed substrate stays baseline.
           Prints T1BEA-HARVEST-DONE only on full success.

THE MANUAL STEP (between the stages). Stock UE 5.8 editor Python cannot author
K2 event-graph nodes, so the reference graph is authored via the proven MCP
graph-authoring lane (aura-mcp: add_blueprint_node_to_strand /
set_node_pins_defaults / connect_blueprint_nodes / compile_blueprint) or by
hand in the editor. The reference graph is exactly:

    Event BeginPlay -> Delay (Duration = 1.0) -> AddActorWorldOffset
        (DeltaLocation = (300, 0, 0), Sweep = false, Teleport = false)

Compile + save the Blueprint, then run stage "harvest".

Fail-closed pattern (mirrors tasks/python/kp-spawn-level-actors/aids/
author_reference.py): all paths derive from this file's own location (never a
hardcoded basket); the -DONE marker is printed ONLY on full success; every
uncertain step dies loudly.

UE 5.8 cautions honoured:
  * Property names are underscore-folded by the Python codegen -- every
    set_editor_property probes several spellings and verifies by readback.
  * NOTHING is ever renamed (renames leave Asset Registry tombstones); every
    name is final at creation time. The harvest-stage restore is
    delete-then-file-copy-then-rescan at the SAME path, never a rename.
  * No SCS socket attachment anywhere (unsettable from Python on UE 5.8).

Output contract (grep the newest editor log):
  T1BEA-SPELLING <property>=<winning name>
  T1BEA-BASELINE-OK / T1BEA-BACKUP-OK / T1BEA-PLACED-OK / T1BEA-FIXTURE-OK
  T1BEA-MAP-DONE                (stage map success marker; absent = FAILED)
  T1BEA-HARVEST <relative path>
  T1BEA-HARVEST-DONE            (stage harvest success marker; absent = FAILED)
"""
import os
import shutil
import sys

import unreal

TASK_ID = "t1-blueprint-event-to-action"

# --- asset-space constants (must match the fixture + task.md) --------------- #
PKG_DIR = "/Game/Tasks/%s" % TASK_ID
BP_NAME = "BP_DelayedMover"
BP_ASSET = "%s/%s" % (PKG_DIR, BP_NAME)
SCAFFOLD_CLASS_PATH = "/Script/CraftBenchTemplate.DelayedMoverActor"
FIXTURE_CLASS_PATH = "/Script/CraftBenchTests.DelayedMoveFunctionalTest"

MAP_PKG_DIR = "/Game/Maps/%s" % TASK_ID
MAP_NAME = "L_DelayedMove"
MAP_ASSET = "%s/%s" % (MAP_PKG_DIR, MAP_NAME)
MAP_TEMPLATE = "/Engine/Maps/Templates/Template_Default"  # ships WorldSettings

# Placement constants. START must equal the fixture's StartLocation
# (DelayedMoveFunctionalTest.cpp) -- off the world origin on purpose.
START = (0.0, -400.0, 150.0)
FIXTURE_LOC = (0.0, 400.0, 150.0)
IDENTITY_TAG = "DelayedMoverRoot"

# --- repo layout, derived from this file at tasks/<basket>/<id>/aids/ ------- #
_HERE = os.path.dirname(os.path.abspath(__file__))
TASK_DIR = os.path.abspath(os.path.join(_HERE, ".."))       # never a hardcoded basket
REPO = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
SUBSTRATE = os.path.join(REPO, "UE-projects", "CraftBenchTemplate")

BP_FILE = os.path.join(SUBSTRATE, "Content", "Tasks", TASK_ID, BP_NAME + ".uasset")
MAP_FILE = os.path.join(SUBSTRATE, "Content", "Maps", TASK_ID, MAP_NAME + ".umap")
BACKUP_DIR = os.path.join(_HERE, "_baseline_backup")        # working artifact, not committed
BACKUP_FILE = os.path.join(BACKUP_DIR, BP_NAME + ".uasset")
REFERENCE_DIR = os.path.join(TASK_DIR, "reference")
REFERENCE_FILE = os.path.join(
    REFERENCE_DIR, "Content", "Tasks", TASK_ID, BP_NAME + ".uasset")

EAL = unreal.EditorAssetLibrary


def die(msg):
    print("T1BEA-ERROR %s" % msg)
    raise SystemExit(msg)


def _editor_subsystem(name):
    cls = getattr(unreal, name, None)
    if cls is None:
        return None
    try:
        return unreal.get_editor_subsystem(cls)
    except Exception:  # noqa: BLE001 - caller has a fallback route
        return None


def _level_call(method, *args):
    """LevelEditorSubsystem.<method>, falling back to EditorLevelLibrary."""
    les = _editor_subsystem("LevelEditorSubsystem")
    fn = getattr(les, method, None) if les is not None else None
    if fn is not None:
        return fn(*args)
    ell = getattr(unreal, "EditorLevelLibrary", None)
    fn = getattr(ell, method, None) if ell is not None else None
    if fn is not None:
        return fn(*args)
    die("no route for level operation %r" % method)


def set_prop(obj, value, *names):
    """set_editor_property under the first accepted spelling (underscore-fold)."""
    last = None
    for name in names:
        try:
            obj.set_editor_property(name, value)
        except Exception as e:  # noqa: BLE001
            last = e
            continue
        print("T1BEA-SPELLING %s=%s" % (names[0], name))
        return
    die("no writable spelling among %s: %r" % (names, last))


def _vec3(v):
    return (float(v.x), float(v.y), float(v.z))


def _close(got, want, tol=0.01):
    return all(abs(g - w) <= tol for g, w in zip(got, want))


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


def _compile_bp(bp):
    bel = getattr(unreal, "BlueprintEditorLibrary", None)
    fn = getattr(bel, "compile_blueprint", None) if bel is not None else None
    if fn is None:
        die("BlueprintEditorLibrary.compile_blueprint unavailable on this build")
    fn(bp)


# --------------------------------------------------------------------------- #
# stage: map                                                                   #
# --------------------------------------------------------------------------- #

def stage_map():
    # Refuse to run on a dirty substrate (re-authoring is a deliberate manual
    # cleanup, not something this script guesses at).
    if EAL.does_asset_exist(BP_ASSET):
        die("substrate already carries %s - clean it first" % BP_ASSET)
    if EAL.does_asset_exist(MAP_ASSET):
        die("substrate already carries %s - clean it first" % MAP_ASSET)
    if os.path.isfile(BACKUP_FILE):
        die("stale baseline backup at %s - remove it first" % BACKUP_FILE)

    parent = unreal.load_class(None, SCAFFOLD_CLASS_PATH)
    fixture_cls = unreal.load_class(None, FIXTURE_CLASS_PATH)
    if parent is None or fixture_cls is None:
        die("task classes not found - build CraftBenchTemplateEditor first "
            "(scaffold=%s fixture=%s)" % (SCAFFOLD_CLASS_PATH, FIXTURE_CLASS_PATH))

    # 1. Baseline Blueprint: an EMPTY subclass of the scaffold.
    factory = unreal.BlueprintFactory()
    set_prop(factory, parent, "parent_class", "ParentClass")
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    bp = tools.create_asset(BP_NAME, PKG_DIR, None, factory)
    if bp is None:
        die("create_asset(%s) returned None" % BP_ASSET)
    _compile_bp(bp)
    if not EAL.save_asset(BP_ASSET):
        die("save_asset(%s) failed" % BP_ASSET)
    if not os.path.isfile(BP_FILE):
        die("save reported success but no file at %s" % BP_FILE)
    print("T1BEA-BASELINE-OK %s" % BP_ASSET)
    # NOTE: the empty discrimination leg assumes the baseline's generated class
    # has NO own ReceiveBeginPlay/ReceiveTick (factory ghost nodes are disabled
    # and should not compile into stubs). Python cannot introspect UFunctions;
    # the `cb discriminate --wip` empty leg is the check that resolves this --
    # see discrimination/MATRIX.md "Empty-row message contingency".
    print("T1BEA-TODO verify empty-leg named assertion via cb discriminate --wip")

    # 2. File-level backup of the baseline for the harvest-stage restore.
    os.makedirs(BACKUP_DIR, exist_ok=True)
    shutil.copy2(BP_FILE, BACKUP_FILE)
    if not os.path.isfile(BACKUP_FILE):
        die("baseline backup copy failed at %s" % BACKUP_FILE)
    print("T1BEA-BACKUP-OK %s" % BACKUP_FILE)

    # 3. The map: template level + one placed BP instance + the fixture.
    if not _level_call("new_level_from_template", MAP_ASSET, MAP_TEMPLATE):
        die("new_level_from_template(%s) failed" % MAP_ASSET)

    gen_cls = EAL.load_blueprint_class(BP_ASSET)
    if gen_cls is None:
        die("load_blueprint_class(%s) returned None" % BP_ASSET)
    host = _spawn(gen_cls, START)
    got = _vec3(host.get_actor_location())
    if not _close(got, START):
        die("placed instance location readback %s, wanted %s (must match the "
            "fixture's StartLocation)" % (got, START))
    tags = [str(t) for t in host.tags]
    if IDENTITY_TAG not in tags:
        die("placed instance carries tags %s but not %r - the Blueprint does "
            "not subclass the scaffold?" % (tags, IDENTITY_TAG))
    print("T1BEA-PLACED-OK %s at %s" % (host.get_name(), (START,)))

    fixture = _spawn(fixture_cls, FIXTURE_LOC)
    print("T1BEA-FIXTURE-OK %s" % fixture.get_name())

    if not _level_call("save_current_level"):
        die("save_current_level failed")
    if not os.path.isfile(MAP_FILE):
        die("save reported success but no file at %s" % MAP_FILE)

    print("T1BEA-MAP-DONE")


# --------------------------------------------------------------------------- #
# stage: harvest                                                               #
# --------------------------------------------------------------------------- #

def stage_harvest():
    if not os.path.isfile(BP_FILE):
        die("no Blueprint on disk at %s - run stage 'map' (and the manual "
            "graph step) first" % BP_FILE)
    if not os.path.isfile(BACKUP_FILE):
        die("no baseline backup at %s - cannot restore the substrate after "
            "harvest; refusing" % BACKUP_FILE)
    with open(BP_FILE, "rb") as f_cur, open(BACKUP_FILE, "rb") as f_base:
        if f_cur.read() == f_base.read():
            die("BP_DelayedMover is byte-identical to the baseline backup - "
                "the reference graph has not been authored yet (see THE "
                "MANUAL STEP in this file's docstring)")
    if os.path.isdir(REFERENCE_DIR) and any(os.scandir(REFERENCE_DIR)):
        die("reference/ is not empty - refusing to overwrite %s" % REFERENCE_DIR)

    # Harvest the edited asset into the reference tree (submission-shaped path).
    os.makedirs(os.path.dirname(REFERENCE_FILE), exist_ok=True)
    shutil.copy2(BP_FILE, REFERENCE_FILE)
    if not os.path.isfile(REFERENCE_FILE):
        die("harvest copy failed at %s" % REFERENCE_FILE)
    print("T1BEA-HARVEST %s" % os.path.relpath(REFERENCE_FILE, TASK_DIR).replace(os.sep, "/"))

    # Restore the substrate baseline: park away from the task map, drop the
    # edited asset, file-copy the baseline back at the SAME path (no rename,
    # no tombstone), and re-register it.
    if not _level_call("load_level", MAP_TEMPLATE):
        die("could not park on %s before restoring the baseline" % MAP_TEMPLATE)
    if EAL.does_asset_exist(BP_ASSET):
        if not EAL.delete_asset(BP_ASSET):
            die("delete_asset(%s) failed - cannot restore baseline" % BP_ASSET)
    if os.path.isfile(BP_FILE):
        os.remove(BP_FILE)
    shutil.copy2(BACKUP_FILE, BP_FILE)
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    registry.scan_files_synchronous([BP_FILE], True)
    if not EAL.does_asset_exist(BP_ASSET):
        die("baseline restored on disk but %s is not visible to the Asset "
            "Registry after rescan" % BP_ASSET)
    print("T1BEA-RESTORED %s" % BP_ASSET)

    print("T1BEA-HARVEST-DONE")


# --------------------------------------------------------------------------- #
# main                                                                         #
# --------------------------------------------------------------------------- #

def main():
    stage = (sys.argv[1] if len(sys.argv) > 1 else "map").strip().lower()
    if stage == "map":
        stage_map()
    elif stage == "harvest":
        stage_harvest()
    else:
        die("unknown stage %r (expected 'map' or 'harvest')" % stage)


main()

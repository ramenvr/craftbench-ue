"""Deterministic baseline, map, and reference authoring driver.

The Widget Blueprint tree and graph edits live exclusively in the task-local
verifier-only ``UFocusStackAssetAuthoring`` helper. This thin Editor-Python
driver calls that helper, performs independent asset/disk readback, saves and
backs up the untouched baseline, creates the committed-path map, then harvests
the reference and restores the exact baseline bytes.

Run only after ThirdPersonEditor has been rebuilt with the task helper. The
``map`` stage requires a real off-screen RHI; do not use ``-nullrhi`` for it.
Every stage emits its DONE marker only after all readbacks succeed.
"""
import os
import shutil
import sys

import unreal


TASK_ID = "t2-top-screen-keeps-focus-until-dismissed"
ASSET_DIR = "/Game/Tasks/%s" % TASK_ID
ASSET_NAMES = ("WBP_MenuRoot", "WBP_HomeScreen", "WBP_DetailScreen")
ASSET_PATHS = tuple("%s/%s" % (ASSET_DIR, name) for name in ASSET_NAMES)

MAP_DIR = "/Game/Maps/%s" % TASK_ID
MAP_NAME = "L_FocusStack"
MAP_PATH = "%s/%s" % (MAP_DIR, MAP_NAME)
MAP_TEMPLATE = "/Game/ThirdPerson/Lvl_ThirdPerson"
PARK_MAP = "/Engine/Maps/Entry"

POLICY_CLASS = "/Script/ThirdPerson.MenuFocusPolicy"
HOST_CLASS = "/Script/CraftBenchTests.MenuLifecycleHost"
FIXTURE_CLASS = "/Script/CraftBenchTests.FocusStackFunctionalTest"
ADMISSION_CLASS = "/Script/CraftBenchTests.CommonUIFocusAdmissionFunctionalTest"

PLACEMENTS = (
    (POLICY_CLASS, "MenuFocusPolicy", (0.0, 0.0, 300.0)),
    (HOST_CLASS, "MenuLifecycleHost", (0.0, 200.0, 300.0)),
    (FIXTURE_CLASS, "FocusStackFunctionalTest", (0.0, 400.0, 300.0)),
    (ADMISSION_CLASS, "CommonUIFocusAdmissionFunctionalTest", (0.0, 600.0, 300.0)),
)

_HERE = os.path.dirname(os.path.abspath(__file__))
TASK_DIR = os.path.abspath(os.path.join(_HERE, ".."))
REPO = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
SUBSTRATE = os.path.join(REPO, "UE-projects", "ThirdPerson")
CONTENT = os.path.join(SUBSTRATE, "Content")
BASELINE_BACKUP = os.path.join(_HERE, "_baseline_backup")
REFERENCE = os.path.join(TASK_DIR, "reference")
REFERENCE_CANDIDATE = os.path.join(_HERE, "_reference_candidate")
MAP_FILE = os.path.join(CONTENT, "Maps", TASK_ID, MAP_NAME + ".umap")

EAL = unreal.EditorAssetLibrary


def die(message):
    print("FOCUS-AUTHOR-ERROR %s" % message)
    raise SystemExit(message)


def _asset_file(name):
    return os.path.join(CONTENT, "Tasks", TASK_ID, name + ".uasset")


def _backup_file(name):
    return os.path.join(BASELINE_BACKUP, name + ".uasset")


def _reference_file(name):
    return os.path.join(
        REFERENCE, "Content", "Tasks", TASK_ID, name + ".uasset")


def _reference_candidate_file(name):
    return os.path.join(REFERENCE_CANDIDATE, name + ".uasset")


def _helper_call(method_name):
    helper = getattr(unreal, "FocusStackAssetAuthoring", None)
    method = getattr(helper, method_name, None) if helper is not None else None
    if method is None:
        die("task authoring helper is unavailable: %s" % method_name)
    try:
        result = bool(method())
    except Exception as exc:  # noqa: BLE001
        die("helper %s raised %r" % (method_name, exc))
    if not result:
        die("helper %s returned false" % method_name)
    print("FOCUS-AUTHOR-HELPER %s" % method_name)


def _editor_subsystem(name):
    cls = getattr(unreal, name, None)
    if cls is None:
        return None
    try:
        return unreal.get_editor_subsystem(cls)
    except Exception:  # noqa: BLE001
        return None


def _level_call(method, *args):
    subsystem = _editor_subsystem("LevelEditorSubsystem")
    fn = getattr(subsystem, method, None) if subsystem is not None else None
    if fn is not None:
        return fn(*args)
    legacy = getattr(unreal, "EditorLevelLibrary", None)
    fn = getattr(legacy, method, None) if legacy is not None else None
    if fn is not None:
        return fn(*args)
    die("no editor level route for %s" % method)


def _spawn(cls, location):
    subsystem = _editor_subsystem("EditorActorSubsystem")
    fn = getattr(subsystem, "spawn_actor_from_class", None) if subsystem else None
    if fn is None:
        legacy = getattr(unreal, "EditorLevelLibrary", None)
        fn = getattr(legacy, "spawn_actor_from_class", None) if legacy else None
    if fn is None:
        die("no spawn_actor_from_class route")
    actor = fn(cls, unreal.Vector(*location), unreal.Rotator(0.0, 0.0, 0.0))
    if actor is None:
        die("spawn returned None for %s" % cls)
    return actor


def _set_label(actor, label):
    try:
        actor.set_actor_label(label)
    except Exception as exc:  # noqa: BLE001
        die("could not label %s: %r" % (label, exc))
    if actor.get_actor_label() != label:
        die("actor label readback failed for %s" % label)


def _load_asset(path):
    if not EAL.does_asset_exist(path):
        die("asset registry is missing %s" % path)
    asset = unreal.load_asset(path)
    if asset is None:
        die("could not load %s" % path)
    return asset


def _generated_class(path):
    try:
        cls = EAL.load_blueprint_class(path)
        if cls is not None:
            return cls
    except Exception:  # noqa: BLE001
        pass
    name = path.rsplit("/", 1)[-1]
    return unreal.load_object(None, path + "." + name + "_C")


def _derives(cls, base_cls):
    try:
        return bool(unreal.MathLibrary.class_is_child_of(cls, base_cls))
    except Exception:  # noqa: BLE001
        return False


def _read_prop(obj, *names):
    last = None
    for name in names:
        try:
            return obj.get_editor_property(name)
        except Exception as exc:  # noqa: BLE001
            last = exc
    die("property unavailable: %s (%r)" % (names[0], last))


def _tree(asset):
    try:
        tree = unreal.find_object(asset, "WidgetTree")
    except Exception as exc:  # noqa: BLE001
        die("WidgetTree readback failed for %s: %r" % (asset, exc))
    if tree is None:
        die("WidgetTree missing for %s" % asset)
    return tree


def _widget(asset, name):
    try:
        return unreal.find_object(_tree(asset), name)
    except Exception as exc:  # noqa: BLE001
        die("widget readback failed for %s: %r" % (name, exc))


def _save_and_readback(reference_expected, save_assets=True):
    assets = [_load_asset(path) for path in ASSET_PATHS]
    base = unreal.load_class(None, "/Script/CommonUI.CommonActivatableWidget")
    if base is None or not all(_derives(_generated_class(path), base)
                               for path in ASSET_PATHS):
        die("one or more generated classes are not activatable screens")

    home_button = _widget(assets[1], "Button_HomePrimary")
    detail_primary = _widget(assets[2], "Button_DetailPrimary")
    detail_alternate = _widget(assets[2], "Button_DetailAlternate")
    buttons = (home_button, detail_primary, detail_alternate)
    if any(button is None or not isinstance(button, unreal.Button)
           for button in buttons):
        die("named button readback failed")
    focusable = [bool(_read_prop(button, "is_focusable", "IsFocusable"))
                 for button in buttons]

    stack_type = getattr(unreal, "CommonActivatableWidgetStack", None)
    stack = _widget(assets[0], "ScreenStack")
    if reference_expected:
        if stack_type is None or stack is None or not isinstance(stack, stack_type):
            die("reference ScreenStack readback failed")
        home_cls = _generated_class(ASSET_PATHS[1])
        declared = _read_prop(
            stack, "root_content_widget_class", "RootContentWidgetClass")
        if declared is None or home_cls is None or \
                str(declared.get_path_name()) != str(home_cls.get_path_name()):
            die("ScreenStack root-content class is not exact Home class")
        if focusable != [True, True, True]:
            die("reference focusable readback mismatch: %s" % focusable)
    else:
        if stack is not None:
            die("baseline unexpectedly contains ScreenStack")
        if focusable != [False, False, False]:
            die("baseline focusable readback mismatch: %s" % focusable)

    for path, name in zip(ASSET_PATHS, ASSET_NAMES):
        if save_assets and not EAL.save_asset(path, only_if_is_dirty=False):
            die("save_asset failed for %s" % path)
        if not os.path.isfile(_asset_file(name)):
            die("asset saved in registry but disk file is missing: %s" % path)
        print("FOCUS-AUTHOR-READBACK %s" % path)


def _copy_baseline_backup():
    if os.path.isdir(BASELINE_BACKUP) and any(os.scandir(BASELINE_BACKUP)):
        die("baseline backup is not empty: %s" % BASELINE_BACKUP)
    os.makedirs(BASELINE_BACKUP, exist_ok=True)
    for name in ASSET_NAMES:
        shutil.copy2(_asset_file(name), _backup_file(name))
        if not os.path.isfile(_backup_file(name)):
            die("backup copy failed for %s" % name)
        print("FOCUS-AUTHOR-BASELINE %s" % name)


def stage_baseline():
    if any(EAL.does_asset_exist(path) or os.path.isfile(_asset_file(name))
           for path, name in zip(ASSET_PATHS, ASSET_NAMES)):
        die("one or more baseline assets already exist; refusing to overwrite")
    _helper_call("create_baseline_assets")
    _helper_call("validate_baseline_assets")
    _save_and_readback(reference_expected=False)
    _copy_baseline_backup()
    print("FOCUS-AUTHOR-BASELINE-DONE")


def stage_map():
    _helper_call("validate_baseline_assets")
    _save_and_readback(reference_expected=False)
    if EAL.does_asset_exist(MAP_PATH) or os.path.isfile(MAP_FILE):
        die("map already exists; refusing to overwrite %s" % MAP_PATH)
    loaded = []
    for class_path, label, _ in PLACEMENTS:
        cls = unreal.load_class(None, class_path)
        if cls is None:
            die("class unavailable; build the editor first: %s" % class_path)
        loaded.append((cls, label))

    if not _level_call("new_level_from_template", MAP_PATH, MAP_TEMPLATE):
        die("new_level_from_template failed for %s" % MAP_PATH)

    placed = []
    for (cls, label), (_, _, location) in zip(loaded, PLACEMENTS):
        actor = _spawn(cls, location)
        _set_label(actor, label)
        placed.append(actor)
        print("FOCUS-AUTHOR-PLACED %s" % label)

    policy_tags = [str(tag) for tag in placed[0].tags]
    host_tags = [str(tag) for tag in placed[1].tags]
    if "MenuFocusPolicy" not in policy_tags:
        die("policy constructor tag missing after placement")
    if "MenuLifecycleHost" not in host_tags:
        die("host constructor tag missing after placement")
    if not _level_call("save_current_level"):
        die("save_current_level failed")
    if not os.path.isfile(MAP_FILE):
        die("map save reported success but file is absent: %s" % MAP_FILE)
    print("FOCUS-AUTHOR-MAP-DONE")


def _bytes_equal(left, right):
    with open(left, "rb") as lhs, open(right, "rb") as rhs:
        return lhs.read() == rhs.read()


def _restore_baseline():
    if not _level_call("load_level", PARK_MAP):
        die("could not park editor on %s before baseline restore" % PARK_MAP)
    for path, name in zip(ASSET_PATHS, ASSET_NAMES):
        if EAL.does_asset_exist(path) and not EAL.delete_asset(path):
            die("could not unload/delete edited asset before restore: %s" % path)
        current = _asset_file(name)
        if os.path.isfile(current):
            os.remove(current)
        shutil.copy2(_backup_file(name), current)
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    registry.scan_files_synchronous([_asset_file(name) for name in ASSET_NAMES], True)
    for path in ASSET_PATHS:
        if not EAL.does_asset_exist(path):
            die("restored file did not re-register: %s" % path)
    _helper_call("validate_baseline_assets")
    _save_and_readback(reference_expected=False, save_assets=False)
    for name in ASSET_NAMES:
        if not _bytes_equal(_asset_file(name), _backup_file(name)):
            die("restored baseline bytes changed during readback: %s" % name)
    print("FOCUS-AUTHOR-BASELINE-RESTORED")


def stage_reference():
    for name in ASSET_NAMES:
        if not os.path.isfile(_backup_file(name)):
            die("missing baseline backup for %s; run baseline first" % name)
    if os.path.isdir(REFERENCE_CANDIDATE) and any(os.scandir(REFERENCE_CANDIDATE)):
        die("reference candidate directory is not empty: %s" % REFERENCE_CANDIDATE)

    expected_existing = {
        os.path.normcase(os.path.abspath(_reference_file(name)))
        for name in ASSET_NAMES
    }
    actual_existing = set()
    if os.path.isdir(REFERENCE):
        for root, _, files in os.walk(REFERENCE):
            actual_existing.update(
                os.path.normcase(os.path.abspath(os.path.join(root, filename)))
                for filename in files)
    if actual_existing and actual_existing != expected_existing:
        die("reference contains unexpected files; refusing scoped replacement")

    _helper_call("validate_baseline_assets")
    restore_required = True
    try:
        _helper_call("build_reference_assets")
        _helper_call("validate_reference_assets")
        _save_and_readback(reference_expected=True)
        os.makedirs(REFERENCE_CANDIDATE, exist_ok=True)
        for name in ASSET_NAMES:
            if _bytes_equal(_asset_file(name), _backup_file(name)):
                die("%s is byte-identical to baseline; reference is incomplete" % name)
            candidate = _reference_candidate_file(name)
            shutil.copy2(_asset_file(name), candidate)
            if not os.path.isfile(candidate):
                die("reference harvest failed for %s" % name)

        # Preserve an earlier (possibly uncertified) reference until all three
        # new candidates have passed helper/Python/disk readback. Each final
        # path is then replaced atomically and only within the declared trio.
        for name in ASSET_NAMES:
            target = _reference_file(name)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            os.replace(_reference_candidate_file(name), target)
            print("FOCUS-AUTHOR-REFERENCE %s" %
                  os.path.relpath(target, TASK_DIR).replace(os.sep, "/"))
        os.rmdir(REFERENCE_CANDIDATE)
    finally:
        if restore_required:
            _restore_baseline()
    print("FOCUS-AUTHOR-REFERENCE-DONE")


def main():
    # Unreal's -ExecutePythonScript route does not reliably forward positional
    # arguments across all pinned editor command-line modes. Prefer the
    # inherited, task-specific environment variable; retain argv for an
    # interactive editor invocation.
    stage = os.environ.get("CRAFTBENCH_FOCUS_AUTHOR_STAGE", "").strip().lower()
    if not stage:
        stage = (sys.argv[1] if len(sys.argv) > 1 else "").strip().lower()
    if stage == "baseline":
        stage_baseline()
    elif stage == "map":
        stage_map()
    elif stage == "reference":
        stage_reference()
    else:
        die("expected stage baseline, map, or reference")


main()

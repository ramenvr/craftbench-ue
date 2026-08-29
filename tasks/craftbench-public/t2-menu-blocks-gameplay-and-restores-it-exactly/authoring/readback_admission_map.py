"""Fresh-process, read-only validation of the authored admission map."""
import hashlib
import os
import stat

import unreal


TASK_ID = "t2-menu-blocks-gameplay-and-restores-it-exactly"
MAP_ASSET = "/Game/Maps/%s/L_MenuInputRouting" % TASK_ID
PROJECT_DIR = os.path.normpath(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
CONTENT_DIR = os.path.join(PROJECT_DIR, "Content")
MAP_DIR = os.path.join(CONTENT_DIR, "Maps", TASK_ID)
MAIN_MAP_FILE = os.path.join(MAP_DIR, "L_MenuInputRouting.umap")
TASK_DIR = os.path.join(CONTENT_DIR, "Tasks", TASK_ID)
SUPPORT_DIR = os.path.join(MAP_DIR, "Support")
EXTERNAL_ACTORS_DIR = os.path.join(
    CONTENT_DIR, "__ExternalActors__", "Maps", TASK_ID,
    "L_MenuInputRouting")
EXTERNAL_OBJECTS_DIR = os.path.join(
    CONTENT_DIR, "__ExternalObjects__", "Maps", TASK_ID,
    "L_MenuInputRouting")
REFERENCE_DIR = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "reference"))

EXPECTED_MAIN_HASH = (
    "c48ddd5b6cf00b32478d07dd9b2d7ce74dba6bf12ac86399f419c98392a37525")
EXPECTED_MAP_MANIFEST = (
    "c494ff1355142fc460c05e947b4f21e626a60f57d3b306456bcdc3e3576df7ed")
EXPECTED_AUTHORED_MANIFEST = (
    "9a127d44ebe027b27ec0470f74e3d0db49492f99cee06210f9c20c8bb4a0984b")
EXPECTED_STOCK_MANIFEST = (
    "b197fab3f5d75c48b4e33ae072e3bf10fdfe0b6d4af6cbcb51810e13797f9b81")

EXPECTED_TASK_FILES = {"WBP_InputBlockingMenu.uasset"}
EXPECTED_SUPPORT_FILES = {
    "IA_GameplayProbe.uasset",
    "IA_MenuProbe.uasset",
    "IA_UnrelatedProbe.uasset",
    "IMC_GameplayQuartz.uasset",
    "IMC_GameplayViolet.uasset",
    "IMC_MenuQuartz.uasset",
    "IMC_MenuViolet.uasset",
    "IMC_UnrelatedQuartz.uasset",
    "IMC_UnrelatedViolet.uasset",
}
STOCK_FILES = (
    os.path.join(CONTENT_DIR, "ThirdPerson", "Lvl_ThirdPerson.umap"),
    os.path.join(CONTENT_DIR, "ThirdPerson", "Blueprints",
                 "BP_ThirdPersonCharacter.uasset"),
    os.path.join(CONTENT_DIR, "ThirdPerson", "Blueprints",
                 "BP_ThirdPersonGameMode.uasset"),
    os.path.join(CONTENT_DIR, "ThirdPerson", "Blueprints",
                 "BP_ThirdPersonPlayerController.uasset"),
)
EXPECTED_CONTRACT = (
    "PASS MENU_INPUT_MAP_CONTRACT map_exact=1 hosts=1 policies=1 "
    "final_fixtures=1 admission_fixtures=1 fixture_total=2 "
    "player_starts=1 game_mode_exact=1 pawn_exact=1 controller_exact=1 "
    "visible_mesh=1 anim_class=1 input_actions=4 runtime_observed=0")


def fail(message):
    rendered = "MENU-INPUT-MAP-COLD-READBACK-ERROR " + message
    unreal.log_error(rendered)
    print(rendered, flush=True)
    raise RuntimeError(message)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def is_reparse(path):
    info = os.lstat(path)
    attributes = getattr(info, "st_file_attributes", 0)
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def require_plain_path(path):
    current = os.path.normpath(path)
    stop = os.path.normcase(os.path.normpath(CONTENT_DIR))
    while True:
        if not os.path.exists(current):
            fail("required path missing: " + current)
        if os.path.islink(current) or is_reparse(current):
            fail("reparse path rejected: " + current)
        if os.path.normcase(current) == stop:
            return
        parent = os.path.dirname(current)
        if parent == current:
            fail("path escaped Content root: " + path)
        current = parent


def files_under(root):
    require_plain_path(root)
    result = []
    for current, directories, files in os.walk(root):
        for directory in directories:
            require_plain_path(os.path.join(current, directory))
        for filename in files:
            path = os.path.join(current, filename)
            require_plain_path(path)
            result.append(path)
    return sorted(result, key=lambda path: path.replace("\\", "/").lower())


def manifest(paths):
    digest = hashlib.sha256()
    vector = {}
    for path in sorted(paths, key=lambda value: value.replace("\\", "/").lower()):
        require_plain_path(path)
        relative = os.path.relpath(path, PROJECT_DIR).replace("\\", "/")
        size = os.path.getsize(path)
        file_hash = sha256(path)
        vector[relative] = (size, file_hash)
        digest.update(("%s\0%d\0%s\n" %
                       (relative, size, file_hash)).encode("utf-8"))
    return digest.hexdigest(), vector


def package_vector():
    task_files = files_under(TASK_DIR)
    support_files = files_under(SUPPORT_DIR)
    if {os.path.relpath(path, TASK_DIR).replace("\\", "/")
            for path in task_files} != EXPECTED_TASK_FILES:
        fail("task inventory mismatch")
    if {os.path.relpath(path, SUPPORT_DIR).replace("\\", "/")
            for path in support_files} != EXPECTED_SUPPORT_FILES:
        fail("support inventory mismatch")

    map_direct_files = {
        name for name in os.listdir(MAP_DIR)
        if os.path.isfile(os.path.join(MAP_DIR, name))}
    map_direct_dirs = {
        name for name in os.listdir(MAP_DIR)
        if os.path.isdir(os.path.join(MAP_DIR, name))}
    if map_direct_files != {"L_MenuInputRouting.umap"} or \
            map_direct_dirs != {"Support"}:
        fail("map root inventory mismatch files=%s dirs=%s" %
             (sorted(map_direct_files), sorted(map_direct_dirs)))

    external_actors = files_under(EXTERNAL_ACTORS_DIR)
    external_objects = files_under(EXTERNAL_OBJECTS_DIR)
    if len(external_actors) != 69 or len(external_objects) != 2:
        fail("OFPA cardinality mismatch actors=%d objects=%d" %
             (len(external_actors), len(external_objects)))

    map_files = [MAIN_MAP_FILE] + external_actors + external_objects
    map_manifest, map_vector = manifest(map_files)
    authored_manifest, authored_vector = manifest(task_files + support_files)
    stock_manifest, stock_vector = manifest(list(STOCK_FILES))
    if sha256(MAIN_MAP_FILE) != EXPECTED_MAIN_HASH:
        fail("main map hash differs from first authoring")
    if map_manifest != EXPECTED_MAP_MANIFEST:
        fail("map/OFPA manifest differs from first authoring")
    if authored_manifest != EXPECTED_AUTHORED_MANIFEST:
        fail("authored asset manifest differs from frozen cold readback")
    if stock_manifest != EXPECTED_STOCK_MANIFEST:
        fail("stock manifest differs from frozen preflight")
    return {
        "map": map_vector,
        "authored": authored_vector,
        "stock": stock_vector,
    }


def require_reference_absent():
    if os.path.lexists(REFERENCE_DIR):
        fail("reference must remain absent: " + REFERENCE_DIR)


def main():
    require_reference_absent()
    before = package_vector()
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if levels is None or not levels.load_level(MAP_ASSET):
        fail("cold load_level failed: " + MAP_ASSET)
    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem).get_editor_world()
    if world is None:
        fail("editor world unavailable after cold map load")

    helper = getattr(unreal, "MenuInputAssetAuthoring", None)
    inspect = getattr(helper, "inspect_admission_map_contract", None) \
        if helper is not None else None
    if inspect is None:
        fail("compiled verifier-owned map helper is unavailable")
    contract = str(inspect(world))
    if contract != EXPECTED_CONTRACT:
        fail("map contract mismatch: " + contract)

    require_reference_absent()
    after = package_vector()
    if after != before:
        fail("cold map readback changed a protected package")

    marker = (
        "MENU-INPUT-MAP-COLD-READBACK-PASS map_files=72 side_packages=71 "
        "assets=10 stock=4 hashes_unchanged=1 no_reparse=1 "
        "hosts=1 policies=1 final_fixtures=1 admission_fixtures=1 "
        "player_starts=1 playable=1 runtime_observed=0 reference_absent=1")
    unreal.log(marker)
    print(marker, flush=True)


main()

"""Fresh-process, read-only validation of the authored menu input assets.

This script never saves, compiles, creates, deletes, renames, or quarantines an
asset. It pins the exact first-wave package bytes before and after invoking the
verifier-owned C++ readback helper.
"""
import hashlib
import os
import stat

import unreal


TASK_ID = "t2-menu-blocks-gameplay-and-restores-it-exactly"
PROJECT_DIR = os.path.normpath(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
CONTENT_DIR = os.path.join(PROJECT_DIR, "Content")
TASK_DIR = os.path.join(CONTENT_DIR, "Tasks", TASK_ID)
SUPPORT_DIR = os.path.join(CONTENT_DIR, "Maps", TASK_ID, "Support")
MAP_FILE = os.path.join(
    CONTENT_DIR, "Maps", TASK_ID, "L_MenuInputRouting.umap")
REFERENCE_DIR = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "reference"))

TASK_ASSET = (
    "/Game/Tasks/%s/WBP_InputBlockingMenu" % TASK_ID)
SUPPORT_ASSETS = tuple(
    "/Game/Maps/%s/Support/%s" % (TASK_ID, name)
    for name in (
        "IA_GameplayProbe",
        "IA_MenuProbe",
        "IA_UnrelatedProbe",
        "IMC_GameplayQuartz",
        "IMC_GameplayViolet",
        "IMC_MenuQuartz",
        "IMC_MenuViolet",
        "IMC_UnrelatedQuartz",
        "IMC_UnrelatedViolet",
    ))
ASSET_PATHS = (TASK_ASSET,) + SUPPORT_ASSETS

EXPECTED_TASK_FILES = {"WBP_InputBlockingMenu.uasset"}
EXPECTED_SUPPORT_FILES = {
    "%s.uasset" % path.rsplit("/", 1)[-1] for path in SUPPORT_ASSETS}

# Frozen immediately after the successful first authoring process.
EXPECTED_HASHES = {
    "WBP_InputBlockingMenu.uasset":
        "1c61d351779608bb69df3880ac00371dfcb1b68c1c3745a3d852e04b57ee3fd0",
    "IA_GameplayProbe.uasset":
        "83013436e91e27fde185d627848f76b1a0da35406c58209feee5185468e089fa",
    "IA_MenuProbe.uasset":
        "99facea7eadf0089d638b92d8af4c38e4dad9ec9b32443b1b141d9da71774b6e",
    "IA_UnrelatedProbe.uasset":
        "92272356f0b3b640adf9fcf0937acd9e4b573577ac1956de527328b11e8eb536",
    "IMC_GameplayQuartz.uasset":
        "be03e71f1fb20151027082a8154f5eec78a70d1c7abd2279dc1f2d02c3d4356c",
    "IMC_GameplayViolet.uasset":
        "4e53228c5d0d37204d804156da4ce387bb505ff70a2d7468797a9c42adae03a6",
    "IMC_MenuQuartz.uasset":
        "540101c7d6b04c388d62c880e6628b117a0ba1c9bd6c8d7aa2d03b33893ffb52",
    "IMC_MenuViolet.uasset":
        "9b0f92087180137fd36051b182567d17cd5976858686aa9bee60c13db966b2a8",
    "IMC_UnrelatedQuartz.uasset":
        "092f8eebd401f569c6d4ef5045c67a20701d1b27215c2c011e16056dc08d5d90",
    "IMC_UnrelatedViolet.uasset":
        "6795b125de661b6041e50677330417100f30d77dc3e8c95126150163ceaac35b",
}

STOCK_FILES = {
    os.path.join(CONTENT_DIR, "ThirdPerson", "Lvl_ThirdPerson.umap"):
        "3e668a9b3098a76f49ce307759ab00662406c7fa0870eeee6e7a2dbf7f854386",
    os.path.join(CONTENT_DIR, "ThirdPerson", "Blueprints",
                 "BP_ThirdPersonCharacter.uasset"):
        "45e6eca3e0e2af0b2fdb9780db8ebfc24f63eac6c5d8721e82814722c81e63ed",
    os.path.join(CONTENT_DIR, "ThirdPerson", "Blueprints",
                 "BP_ThirdPersonGameMode.uasset"):
        "3520d665f8c2fbb8ea3d3868dbdf268e6a88b342ffe6bfbafb7177f9e172e74c",
    os.path.join(CONTENT_DIR, "ThirdPerson", "Blueprints",
                 "BP_ThirdPersonPlayerController.uasset"):
        "a68229ef07d29a92a453b475cb28bbe6001883f163014ba10512959d2d71d0c5",
}


def die(message):
    unreal.log_error("MENU-INPUT-ASSETS-COLD-READBACK-ERROR %s" % message)
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


def require_plain_path(path, stop):
    current = os.path.normpath(path)
    stop = os.path.normcase(os.path.normpath(stop))
    while True:
        if not os.path.exists(current):
            die("required path missing: %s" % current)
        if os.path.islink(current) or is_reparse(current):
            die("reparse path rejected: %s" % current)
        if os.path.normcase(current) == stop:
            return
        parent = os.path.dirname(current)
        if parent == current:
            die("path escaped expected root: %s" % path)
        current = parent


def inventory(root):
    if not os.path.isdir(root):
        die("inventory root missing: %s" % root)
    result = set()
    for current, directories, files in os.walk(root):
        for directory in directories:
            require_plain_path(os.path.join(current, directory), CONTENT_DIR)
        for filename in files:
            full = os.path.join(current, filename)
            require_plain_path(full, CONTENT_DIR)
            result.add(os.path.relpath(full, root).replace("\\", "/"))
    return result


def file_vector():
    task_inventory = inventory(TASK_DIR)
    support_inventory = inventory(SUPPORT_DIR)
    if task_inventory != EXPECTED_TASK_FILES:
        die("task inventory mismatch: %s" % sorted(task_inventory))
    if support_inventory != EXPECTED_SUPPORT_FILES:
        die("support inventory mismatch: %s" % sorted(support_inventory))

    result = {}
    for filename in EXPECTED_TASK_FILES:
        result[filename] = sha256(os.path.join(TASK_DIR, filename))
    for filename in EXPECTED_SUPPORT_FILES:
        result[filename] = sha256(os.path.join(SUPPORT_DIR, filename))
    for path, expected in STOCK_FILES.items():
        require_plain_path(path, CONTENT_DIR)
        result[os.path.normcase(path)] = sha256(path)
        if result[os.path.normcase(path)] != expected:
            die("stock hash mismatch: %s" % path)
    if {key: result[key] for key in EXPECTED_HASHES} != EXPECTED_HASHES:
        die("authored asset hash vector differs from frozen first authoring")
    return result


def require_protected_outputs_absent():
    if os.path.lexists(MAP_FILE):
        die("final map must remain absent: %s" % MAP_FILE)
    if os.path.lexists(REFERENCE_DIR):
        die("reference must remain absent: %s" % REFERENCE_DIR)


def main():
    require_protected_outputs_absent()
    before = file_vector()
    missing = [path for path in ASSET_PATHS
               if not unreal.EditorAssetLibrary.does_asset_exist(path)]
    if missing:
        die("asset registry inventory incomplete: %s" % missing)

    helper = getattr(unreal, "MenuInputAssetAuthoring", None)
    validate = getattr(helper, "validate_admission_assets", None) \
        if helper is not None else None
    if validate is None:
        die("compiled verifier-owned readback helper is unavailable")
    if not bool(validate()):
        die("ValidateAdmissionAssets returned false")

    require_protected_outputs_absent()
    after = file_vector()
    if after != before:
        die("read-only validation changed a protected package hash")

    marker = (
        "MENU-INPUT-ASSETS-COLD-READBACK-PASS assets=10 stock=4 "
        "hashes_unchanged=1 no_reparse=1 map_absent=1 reference_absent=1")
    unreal.log(marker)
    print(marker)


if __name__ == "__main__":
    main()

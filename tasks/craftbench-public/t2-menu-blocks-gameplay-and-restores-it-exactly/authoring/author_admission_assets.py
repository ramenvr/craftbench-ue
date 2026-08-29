"""Fail-closed first authoring step for menu/input admission assets."""
import os

import unreal


TASK_ID = "t2-menu-blocks-gameplay-and-restores-it-exactly"
TASK_ROOT = "/Game/Tasks/%s" % TASK_ID
SUPPORT_ROOT = "/Game/Maps/%s/Support" % TASK_ID
MENU = "%s/WBP_InputBlockingMenu" % TASK_ROOT
ACTIONS = (
    "%s/IA_GameplayProbe" % SUPPORT_ROOT,
    "%s/IA_MenuProbe" % SUPPORT_ROOT,
    "%s/IA_UnrelatedProbe" % SUPPORT_ROOT,
)
CONTEXTS = tuple(
    "%s/IMC_%s%s" % (SUPPORT_ROOT, family, leg)
    for leg in ("Quartz", "Violet")
    for family in ("Gameplay", "Menu", "Unrelated")
)


def die(message):
    unreal.log_error("MENU-INPUT-ASSETS-ERROR %s" % message)
    raise RuntimeError(message)


def main():
    outputs = (MENU,) + ACTIONS + CONTEXTS
    existing = [path for path in outputs
                if unreal.EditorAssetLibrary.does_asset_exist(path)]
    if existing:
        die("exact output already exists: %s" % existing)

    content = os.path.normpath(unreal.Paths.project_content_dir())
    os.makedirs(os.path.join(content, "Tasks", TASK_ID), exist_ok=True)
    os.makedirs(os.path.join(content, "Maps", TASK_ID, "Support"), exist_ok=True)

    helper = getattr(unreal, "MenuInputAssetAuthoring", None)
    create = getattr(helper, "create_admission_assets", None) \
        if helper is not None else None
    validate = getattr(helper, "validate_admission_assets", None) \
        if helper is not None else None
    if create is None or validate is None:
        die("compiled verifier-owned authoring helper is unavailable")
    if not bool(create()):
        die("CreateAdmissionAssets returned false")
    if not bool(validate()):
        die("ValidateAdmissionAssets returned false")

    missing = [path for path in outputs
               if not unreal.EditorAssetLibrary.does_asset_exist(path)]
    if missing:
        die("asset registry readback missing: %s" % missing)
    unreal.log("MENU-INPUT-ASSETS-SAVED baseline=1 actions=3 contexts=6")
    print("MENU-INPUT-ASSETS-SAVED baseline=1 actions=3 contexts=6")


if __name__ == "__main__":
    main()

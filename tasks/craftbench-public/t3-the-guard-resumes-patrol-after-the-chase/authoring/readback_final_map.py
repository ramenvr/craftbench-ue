"""Fresh-process read-only validation of the retained production map."""

from pathlib import Path
import os
import re
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from guard_authoring_common import (  # noqa: E402
    ADMISSION_MAP, ADMISSION_MAP_DIR, FINAL_MAP, REFERENCE,
    exact_admission_asset_vector, exact_final_asset_vector, require_plain,
    sha256, stock_vector,
)

TASK_ID = "t3-the-guard-resumes-patrol-after-the-chase"
MAP = "/Game/Maps/" + TASK_ID + "/L_GuardPatrolChase"
SUCCESS = re.compile(
    r"^PASS admission=0 subject=1 alert=1 target=1 markers=2 "
    r"admission_fixture=0 final_fixture=1 player_start=1 nav_bounds=1 "
    r"tags=1 fixture_contract=1 game_mode=1 playable=1 "
    r"decision_reference=1 runtime_observed=0 world=.+$")


def fail(message):
    unreal.log_error("GUARD-FINAL-MAP-COLD-FAILED " + message)
    raise RuntimeError(message)


def native_detail(value):
    if type(value) is str:
        return value
    if (isinstance(value, tuple) and len(value) == 2 and
            type(value[0]) is bool and type(value[1]) is str and value[0]):
        return value[1]
    fail("unexpected native return shape: %r" % (value,))


def snapshot():
    for path in (ADMISSION_MAP, FINAL_MAP):
        require_plain(path)
    direct_files = {item.name for item in ADMISSION_MAP_DIR.iterdir()
                    if item.is_file()}
    direct_dirs = {item.name for item in ADMISSION_MAP_DIR.iterdir()
                   if item.is_dir()}
    if direct_files != {ADMISSION_MAP.name, FINAL_MAP.name} or direct_dirs:
        fail("map inventory mismatch files=%r dirs=%r" %
             (sorted(direct_files), sorted(direct_dirs)))
    if os.path.lexists(REFERENCE):
        fail("reference must remain absent")
    return {
        "admission_map": sha256(ADMISSION_MAP),
        "final_map": sha256(FINAL_MAP),
        "admission_assets": exact_admission_asset_vector(),
        "final_assets": exact_final_asset_vector(),
        "stock": stock_vector(),
    }


def main():
    before = snapshot()
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not levels.load_level(MAP):
        fail("cold load_level failed")
    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem).get_editor_world()
    helper = getattr(unreal, "GuardPatrolChaseAssetAuthoring", None)
    if world is None or helper is None:
        fail("world or compiled helper unavailable")
    detail = native_detail(helper.inspect_authored_map_text(world, False))
    if SUCCESS.fullmatch(detail) is None:
        fail("native final-map readback mismatch: " + detail)
    if snapshot() != before:
        fail("cold final-map readback changed protected package hash")
    marker = (
        "GUARD-FINAL-MAP-COLD-PASS maps=2 admission_assets=2 "
        "final_assets=2 stock=4 hashes_unchanged=1 no_reparse=1 "
        "runtime_observed=0 reference_absent=1")
    unreal.log(marker)
    print(marker)


main()

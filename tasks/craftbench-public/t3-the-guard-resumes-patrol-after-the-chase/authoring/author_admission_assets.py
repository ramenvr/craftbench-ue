"""One-shot, fail-closed authoring of the isolated correct admission assets."""

import os
from pathlib import Path
import re
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from guard_authoring_common import (  # noqa: E402
    ADMISSION_DIR, REFERENCE, admission_assets, exact_admission_asset_vector,
    require_protected_absent, stock_vector,
)

TASK_ID = "t3-the-guard-resumes-patrol-after-the-chase"
DIRECTORY = "/Game/__CraftBenchAdmission/" + TASK_ID
BLACKBOARD = DIRECTORY + "/BB_GuardPatrolChase_Admission"
TREE = DIRECTORY + "/BT_GuardPatrolChase_Admission"
SUCCESS = re.compile(
    r"^PASS SAVED PASS blackboard_contract=1 priority_selector=1 "
    r"observer_abort=1 chase_target=1 patrol_loop=1 tree=.+ blackboard=.+$")


def fail(message):
    unreal.log_error("GUARD-ADMISSION-ASSETS-FAILED " + message)
    raise RuntimeError(message)


def native_detail(value):
    if type(value) is str:
        return value
    if (isinstance(value, tuple) and len(value) == 2 and
            type(value[0]) is bool and type(value[1]) is str and value[0]):
        return value[1]
    fail("unexpected native return shape: %r" % (value,))


def main():
    if os.path.lexists(ADMISSION_DIR) or unreal.EditorAssetLibrary.does_directory_exist(
            DIRECTORY):
        fail("refusing existing admission namespace: " + DIRECTORY)
    require_protected_absent(admission_map=True)
    stock_before = stock_vector()
    helper = getattr(unreal, "GuardPatrolChaseAssetAuthoring", None)
    if helper is None:
        fail("compiled native helper unavailable")
    detail = native_detail(helper.author_decision_assets_text(
        BLACKBOARD, TREE, True))
    if SUCCESS.fullmatch(detail) is None:
        fail("native success vector mismatch: " + detail)
    expected = {BLACKBOARD, TREE}
    observed = {str(value).split(".", 1)[0] for value in
                unreal.EditorAssetLibrary.list_assets(
                    DIRECTORY, recursive=True, include_folder=False)}
    if observed != expected:
        fail("asset registry inventory mismatch: %r" % sorted(observed))
    for path in admission_assets():
        if not path.is_file() or path.is_symlink():
            fail("missing/non-regular exact output: " + str(path))
    hashes = exact_admission_asset_vector()
    require_protected_absent(admission_map=True)
    if stock_vector() != stock_before:
        fail("stock package hash changed")
    marker = (
        "GUARD-ADMISSION-ASSETS-SAVED assets=2 graph=editable "
        "structure=4/4 stock=4 hashes=" + repr(hashes))
    unreal.log(marker)
    print(marker)


main()

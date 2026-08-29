"""Create the exact empty, editable final task scaffold once."""

from pathlib import Path
import os
import re
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from guard_authoring_common import (  # noqa: E402
    ADMISSION_DIR, ADMISSION_MAP, FINAL_DIR, FINAL_MAP, REFERENCE,
    exact_admission_asset_vector, require_plain, sha256, stock_vector, vector,
)

TASK_ID = "t3-the-guard-resumes-patrol-after-the-chase"
DIRECTORY = "/Game/Tasks/" + TASK_ID
BLACKBOARD = DIRECTORY + "/BB_GuardPatrolChase"
TREE = DIRECTORY + "/BT_GuardPatrolChase"
SUCCESS = re.compile(
    r"^PASS SAVED PASS baseline_empty=1 blackboard_contract=1 "
    r"tree=.+ blackboard=.+$")


def fail(message):
    unreal.log_error("GUARD-BASELINE-ASSETS-FAILED " + message)
    raise RuntimeError(message)


def native_detail(value):
    if type(value) is str:
        return value
    if (isinstance(value, tuple) and len(value) == 2 and
            type(value[0]) is bool and type(value[1]) is str and value[0]):
        return value[1]
    fail("unexpected native return shape: %r" % (value,))


def protected_snapshot():
    result = {"stock": stock_vector()}
    result["admission_assets"] = (exact_admission_asset_vector()
                                  if ADMISSION_DIR.exists() else "absent")
    if ADMISSION_MAP.exists():
        require_plain(ADMISSION_MAP)
        result["admission_map"] = sha256(ADMISSION_MAP)
    else:
        result["admission_map"] = "absent"
    return result


def final_vector():
    expected = {
        FINAL_DIR / "BB_GuardPatrolChase.uasset",
        FINAL_DIR / "BT_GuardPatrolChase.uasset",
    }
    observed = set(FINAL_DIR.iterdir()) if FINAL_DIR.is_dir() else set()
    if observed != expected:
        fail("final baseline inventory mismatch: %r" %
             sorted(str(item) for item in observed))
    return vector(tuple(sorted(expected)))


def main():
    if os.path.lexists(FINAL_DIR) or unreal.EditorAssetLibrary.does_directory_exist(
            DIRECTORY):
        fail("refusing existing final namespace: " + DIRECTORY)
    for path in (FINAL_MAP, REFERENCE):
        if os.path.lexists(path):
            fail("protected later output must remain absent: " + str(path))
    before = protected_snapshot()
    helper = getattr(unreal, "GuardPatrolChaseAssetAuthoring", None)
    if helper is None:
        fail("compiled native helper unavailable")
    detail = native_detail(helper.author_decision_assets_text(
        BLACKBOARD, TREE, False))
    if SUCCESS.fullmatch(detail) is None:
        fail("native baseline contract mismatch: " + detail)
    observed = {str(value).split(".", 1)[0] for value in
                unreal.EditorAssetLibrary.list_assets(
                    DIRECTORY, recursive=True, include_folder=False)}
    if observed != {BLACKBOARD, TREE}:
        fail("asset registry inventory mismatch: %r" % sorted(observed))
    hashes = final_vector()
    if protected_snapshot() != before:
        fail("admission or stock package changed")
    if os.path.lexists(FINAL_MAP) or os.path.lexists(REFERENCE):
        fail("map/reference changed")
    marker = (
        "GUARD-BASELINE-ASSETS-SAVED assets=2 baseline_empty=1 "
        "blackboard_contract=1 protected_hashes_unchanged=1 hashes=" +
        repr(hashes))
    unreal.log(marker)
    print(marker)


main()

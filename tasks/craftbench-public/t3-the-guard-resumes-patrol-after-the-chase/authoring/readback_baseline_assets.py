"""Fresh-process read-only validation of the exact empty final scaffold."""

from pathlib import Path
import os
import re
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from guard_authoring_common import (  # noqa: E402
    FINAL_DIR, FINAL_MAP, REFERENCE, require_plain, stock_vector, vector,
)

TASK_ID = "t3-the-guard-resumes-patrol-after-the-chase"
DIRECTORY = "/Game/Tasks/" + TASK_ID
BLACKBOARD = DIRECTORY + "/BB_GuardPatrolChase"
TREE = DIRECTORY + "/BT_GuardPatrolChase"
SUCCESS = re.compile(
    r"^PASS baseline_empty=1 blackboard_contract=1 tree=.+ blackboard=.+$")


def fail(message):
    unreal.log_error("GUARD-BASELINE-COLD-FAILED " + message)
    raise RuntimeError(message)


def native_detail(value):
    if type(value) is str:
        return value
    if (isinstance(value, tuple) and len(value) == 2 and
            type(value[0]) is bool and type(value[1]) is str and value[0]):
        return value[1]
    fail("unexpected native return shape: %r" % (value,))


def baseline_vector():
    expected = (
        FINAL_DIR / "BB_GuardPatrolChase.uasset",
        FINAL_DIR / "BT_GuardPatrolChase.uasset",
    )
    for path in expected:
        require_plain(path)
    if set(FINAL_DIR.iterdir()) != set(expected):
        fail("final asset inventory is not exact two")
    return vector(expected)


def main():
    for path in (FINAL_MAP, REFERENCE):
        if os.path.lexists(path):
            fail("later output must remain absent: " + str(path))
    before = {"baseline": baseline_vector(), "stock": stock_vector()}
    blackboard = unreal.EditorAssetLibrary.load_asset(BLACKBOARD)
    tree = unreal.EditorAssetLibrary.load_asset(TREE)
    helper = getattr(unreal, "GuardPatrolChaseAssetAuthoring", None)
    if blackboard is None or tree is None or helper is None:
        fail("declared assets or native helper unavailable")
    detail = native_detail(helper.inspect_baseline_assets_text(tree, blackboard))
    if SUCCESS.fullmatch(detail) is None:
        fail("native baseline readback mismatch: " + detail)
    after = {"baseline": baseline_vector(), "stock": stock_vector()}
    if after != before:
        fail("cold readback changed package hashes")
    marker = (
        "GUARD-BASELINE-ASSETS-COLD-PASS assets=2 baseline_empty=1 "
        "hashes_unchanged=1 stock=4 map_absent=1 reference_absent=1")
    unreal.log(marker)
    print(marker)


main()

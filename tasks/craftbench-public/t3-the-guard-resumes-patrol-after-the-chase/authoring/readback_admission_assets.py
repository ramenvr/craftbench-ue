"""Fresh-process read-only admission asset validation."""

from pathlib import Path
import re
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from guard_authoring_common import (  # noqa: E402
    exact_admission_asset_vector, require_protected_absent, stock_vector,
)

TASK_ID = "t3-the-guard-resumes-patrol-after-the-chase"
DIRECTORY = "/Game/__CraftBenchAdmission/" + TASK_ID
BLACKBOARD = DIRECTORY + "/BB_GuardPatrolChase_Admission"
TREE = DIRECTORY + "/BT_GuardPatrolChase_Admission"
SUCCESS = re.compile(
    r"^PASS blackboard_contract=1 priority_selector=1 observer_abort=1 "
    r"chase_target=1 patrol_loop=1 tree=.+ blackboard=.+$")


def fail(message):
    unreal.log_error("GUARD-ADMISSION-ASSETS-COLD-FAILED " + message)
    raise RuntimeError(message)


def native_detail(value):
    if type(value) is str:
        return value
    if (isinstance(value, tuple) and len(value) == 2 and
            type(value[0]) is bool and type(value[1]) is str and value[0]):
        return value[1]
    fail("unexpected native return shape: %r" % (value,))


def main():
    require_protected_absent(admission_map=True)
    before = {"assets": exact_admission_asset_vector(),
              "stock": stock_vector()}
    blackboard = unreal.EditorAssetLibrary.load_asset(BLACKBOARD)
    tree = unreal.EditorAssetLibrary.load_asset(TREE)
    if blackboard is None or tree is None:
        fail("declared asset failed to load")
    helper = getattr(unreal, "GuardPatrolChaseAssetAuthoring", None)
    if helper is None:
        fail("compiled native helper unavailable")
    detail = native_detail(helper.inspect_decision_assets_text(tree, blackboard))
    if SUCCESS.fullmatch(detail) is None:
        fail("native readback mismatch: " + detail)
    require_protected_absent(admission_map=True)
    after = {"assets": exact_admission_asset_vector(),
             "stock": stock_vector()}
    if after != before:
        fail("readback changed package hashes")
    marker = (
        "GUARD-ADMISSION-ASSETS-COLD-PASS assets=2 structure=4/4 "
        "hashes_unchanged=1 stock=4 final_absent=1 map_absent=1 "
        "reference_absent=1")
    unreal.log(marker)
    print(marker)


main()

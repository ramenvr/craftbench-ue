"""Fresh-process read-only inspection of the temporary live reference assets."""

from pathlib import Path
import json
import os
import re
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import reference_contract as contract  # noqa: E402
from guard_authoring_common import exact_final_asset_vector  # noqa: E402


DIRECTORY = "/Game/Tasks/" + contract.TASK_ID
BLACKBOARD = DIRECTORY + "/BB_GuardPatrolChase"
TREE = DIRECTORY + "/BT_GuardPatrolChase"
SUCCESS = re.compile(
    r"^PASS blackboard_contract=1 priority_selector=1 observer_abort=1 "
    r"chase_target=1 patrol_loop=1 tree=.+ blackboard=.+$")


def fail(message):
    unreal.log_error("GUARD-REFERENCE-COLD-FAILED " + message)
    raise RuntimeError(message)


def native_detail(value):
    if type(value) is str:
        return value
    fail("unexpected native return shape: %r" % (value,))


def main():
    raw = os.environ.get("CRAFTBENCH_GUARD_REFERENCE_HASHES", "")
    try:
        expected = json.loads(raw)
    except Exception as exc:
        fail("reference hash environment is invalid: %r" % exc)
    before = {
        "reference": exact_final_asset_vector(),
        "immutable": contract.immutable_vector(),
    }
    if before["reference"] != expected:
        fail("temporary reference hashes do not match author evidence")
    contract.require_reference_absent()
    blackboard = unreal.EditorAssetLibrary.load_asset(BLACKBOARD)
    tree = unreal.EditorAssetLibrary.load_asset(TREE)
    helper = getattr(unreal, "GuardPatrolChaseAssetAuthoring", None)
    if blackboard is None or tree is None or helper is None:
        fail("declared assets or compiled helper unavailable")
    detail = native_detail(helper.inspect_decision_assets_text(tree, blackboard))
    if SUCCESS.fullmatch(detail) is None:
        fail("native fixed readback mismatch: " + detail)
    after = {
        "reference": exact_final_asset_vector(),
        "immutable": contract.immutable_vector(),
    }
    if after != before:
        fail("cold reference readback changed protected packages")
    contract.require_reference_absent()
    marker = (
        "GUARD-REFERENCE-COLD-PASS assets=2 l2i=4 "
        "hashes_unchanged=1 reference_absent=1")
    unreal.log(marker)
    print(marker)


main()

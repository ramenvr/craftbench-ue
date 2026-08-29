"""Fresh-process proof that reference closure restored the empty baseline."""

from pathlib import Path
import re
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import reference_contract as contract  # noqa: E402


DIRECTORY = "/Game/Tasks/" + contract.TASK_ID
BLACKBOARD = DIRECTORY + "/BB_GuardPatrolChase"
TREE = DIRECTORY + "/BT_GuardPatrolChase"
SUCCESS = re.compile(
    r"^PASS baseline_empty=1 blackboard_contract=1 tree=.+ blackboard=.+$")


def fail(message):
    unreal.log_error("GUARD-RESTORED-BASELINE-COLD-FAILED " + message)
    raise RuntimeError(message)


def main():
    before = {
        "baseline": contract.baseline_vector(),
        "immutable": contract.immutable_vector(),
    }
    contract.require_reference_absent()
    blackboard = unreal.EditorAssetLibrary.load_asset(BLACKBOARD)
    tree = unreal.EditorAssetLibrary.load_asset(TREE)
    helper = getattr(unreal, "GuardPatrolChaseAssetAuthoring", None)
    if blackboard is None or tree is None or helper is None:
        fail("declared assets or compiled helper unavailable")
    detail = helper.inspect_baseline_assets_text(tree, blackboard)
    if type(detail) is not str or SUCCESS.fullmatch(detail) is None:
        fail("native restored-baseline mismatch: %r" % (detail,))
    after = {
        "baseline": contract.baseline_vector(),
        "immutable": contract.immutable_vector(),
    }
    if after != before:
        fail("restored-baseline readback changed protected packages")
    marker = (
        "GUARD-RESTORED-BASELINE-COLD-PASS assets=2 baseline_empty=1 "
        "maps=2 admission_assets=2 stock=4 hashes_unchanged=1 "
        "reference_absent=1")
    unreal.log(marker)
    print(marker)


main()

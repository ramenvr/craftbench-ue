"""One-shot UE author leg used only by close_reference.py."""

from pathlib import Path
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
    r"^PASS SAVED PASS blackboard_contract=1 priority_selector=1 "
    r"observer_abort=1 chase_target=1 patrol_loop=1 tree=.+ blackboard=.+$")


def fail(message):
    unreal.log_error("GUARD-REFERENCE-AUTHOR-FAILED " + message)
    raise RuntimeError(message)


def native_detail(value):
    if type(value) is str:
        return value
    fail("unexpected native return shape: %r" % (value,))


def main():
    contract.require_live_namespace_absent()
    contract.require_reference_absent()
    immutable_before = contract.immutable_vector()
    helper = getattr(unreal, "GuardPatrolChaseAssetAuthoring", None)
    if helper is None:
        fail("compiled native helper unavailable")
    detail = native_detail(helper.author_decision_assets_text(
        BLACKBOARD, TREE, True))
    if SUCCESS.fullmatch(detail) is None:
        fail("native complete-solution contract mismatch: " + detail)
    authored = exact_final_asset_vector()
    by_name = {Path(key).name: value for key, value in authored.items()}
    if by_name == contract.BASELINE_HASHES:
        fail("authored reference is byte-identical to empty baseline")
    if contract.immutable_vector() != immutable_before:
        fail("reference author changed protected packages")
    contract.require_reference_absent()
    marker = (
        "GUARD-REFERENCE-AUTHOR-PASS assets=2 l2i=4 "
        "protected_hashes_unchanged=1 hashes=" + repr(authored))
    unreal.log(marker)
    print(marker)


main()

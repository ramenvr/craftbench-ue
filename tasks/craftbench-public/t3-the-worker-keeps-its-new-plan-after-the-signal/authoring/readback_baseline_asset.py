"""Fresh-process readback of the empty production StateTree scaffold."""

from pathlib import Path
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from worker_plan_final_common import (  # noqa: E402
    FINAL_TREE, final_vector, immutable_vector,
)

TREE_OBJECT = FINAL_TREE + ".ST_WorkerPlan"
SCHEMA_OBJECT = TREE_OBJECT + ":StateTreeEditorData_0.StateTreeAIComponentSchema_0"
SUCCESS = (
    "PASS baseline_empty=1 ownership=1 signal_transition=0 navigation_task=0 "
    "tree=" + TREE_OBJECT + " schema=" + SCHEMA_OBJECT)


def fail(message):
    unreal.log_error("WORKER-PLAN-BASELINE-ASSET-READBACK-FAILED: " + message)
    raise RuntimeError(message)


def main():
    before = {"final": final_vector(), "immutable": immutable_vector()}
    tree = unreal.EditorAssetLibrary.load_asset(FINAL_TREE)
    helper = getattr(unreal, "WorkerPlanAssetAuthoring", None)
    if tree is None or helper is None:
        fail("tree/helper unavailable")
    detail = helper.inspect_state_tree_shell(tree)
    if type(detail) is not str or detail != SUCCESS:
        fail("native shell contract mismatch expected=%r actual=%r" %
             (SUCCESS, detail))
    after = {"final": final_vector(), "immutable": immutable_vector()}
    if after != before:
        fail("readback changed protected artifacts")
    marker = ("WORKER-PLAN-BASELINE-ASSET-READBACK-PASS assets=1 "
              "baseline_empty=1 ownership=1 hashes_unchanged=1")
    unreal.log(marker)
    print(marker, flush=True)


main()

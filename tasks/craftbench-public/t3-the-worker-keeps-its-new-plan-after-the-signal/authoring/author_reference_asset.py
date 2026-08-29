"""Author the correct StateTree into an absent live namespace for harvesting."""

import os
from pathlib import Path
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from worker_plan_final_common import (  # noqa: E402
    FINAL_DIR, FINAL_TREE, REFERENCE, final_vector, immutable_vector,
)

TREE_OBJECT = FINAL_TREE + ".ST_WorkerPlan"
SCHEMA_OBJECT = TREE_OBJECT + ":StateTreeEditorData_0.StateTreeAIComponentSchema_0"
AUTHOR_SUCCESS = (
    "PASS SAVED PASS ownership=1 signal_transition=1 navigation_task=1 "
    "tree=" + TREE_OBJECT + " schema=" + SCHEMA_OBJECT)
READBACK_SUCCESS = AUTHOR_SUCCESS.removeprefix("PASS SAVED ")


def fail(message):
    unreal.log_error("WORKER-PLAN-REFERENCE-AUTHOR-FAILED: " + message)
    raise RuntimeError(message)


def exact(value, expected, name):
    if type(value) is not str or value != expected:
        fail("%s contract mismatch expected=%r actual=%r" %
             (name, expected, value))


def main():
    if os.path.lexists(FINAL_DIR) or os.path.lexists(REFERENCE):
        fail("live final namespace and reference must be absent")
    before = immutable_vector()
    helper = getattr(unreal, "WorkerPlanAssetAuthoring", None)
    if helper is None:
        fail("compiled helper unavailable")
    exact(helper.author_state_tree(FINAL_TREE), AUTHOR_SUCCESS,
          "author_state_tree")
    tree = unreal.EditorAssetLibrary.load_asset(FINAL_TREE)
    exact(helper.inspect_state_tree(tree), READBACK_SUCCESS,
          "inspect_state_tree")
    hashes = final_vector()
    if immutable_vector() != before:
        fail("immutable artifacts changed")
    marker = ("WORKER-PLAN-REFERENCE-AUTHOR-PASS assets=1 ownership=1 "
              "signal_transition=1 navigation_task=1 hashes=%r" % hashes)
    unreal.log(marker)
    print(marker, flush=True)


main()

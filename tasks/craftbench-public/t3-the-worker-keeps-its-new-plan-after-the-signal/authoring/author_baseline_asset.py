"""Create the exact empty, editable production StateTree scaffold once."""

import os
from pathlib import Path
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from worker_plan_final_common import (  # noqa: E402
    FINAL_DIR, FINAL_FILE, FINAL_MAP, FINAL_TREE, REFERENCE,
    final_vector, immutable_vector,
)

TREE_OBJECT = FINAL_TREE + ".ST_WorkerPlan"
SCHEMA_OBJECT = TREE_OBJECT + ":StateTreeEditorData_0.StateTreeAIComponentSchema_0"
AUTHOR_SUCCESS = (
    "PASS SAVED PASS baseline_empty=1 ownership=1 signal_transition=0 "
    "navigation_task=0 tree=" + TREE_OBJECT + " schema=" + SCHEMA_OBJECT)
READBACK_SUCCESS = AUTHOR_SUCCESS.removeprefix("PASS SAVED ")


def fail(message):
    unreal.log_error("WORKER-PLAN-BASELINE-ASSET-FAILED: " + message)
    raise RuntimeError(message)


def require_exact(value, expected, call_name):
    if type(value) is not str or value != expected:
        fail("%s contract mismatch expected=%r actual=%r" %
             (call_name, expected, value))
    return value


def main():
    if os.path.lexists(FINAL_DIR) or unreal.EditorAssetLibrary.does_directory_exist(
            "/Game/Tasks/t3-the-worker-keeps-its-new-plan-after-the-signal"):
        fail("refusing existing final task namespace")
    if os.path.lexists(FINAL_MAP) or os.path.lexists(REFERENCE):
        fail("final map/reference must remain absent")
    before = immutable_vector()
    helper = getattr(unreal, "WorkerPlanAssetAuthoring", None)
    if helper is None:
        fail("compiled helper unavailable")
    require_exact(helper.author_state_tree_shell(FINAL_TREE), AUTHOR_SUCCESS,
                  "author_state_tree_shell")
    if not FINAL_FILE.is_file():
        fail("exact baseline package missing")
    observed = {str(value).split(".", 1)[0] for value in
                unreal.EditorAssetLibrary.list_assets(
                    "/Game/Tasks/t3-the-worker-keeps-its-new-plan-after-the-signal",
                    recursive=True, include_folder=False)}
    if observed != {FINAL_TREE}:
        fail("asset registry inventory mismatch: %r" % sorted(observed))
    tree = unreal.EditorAssetLibrary.load_asset(FINAL_TREE)
    require_exact(helper.inspect_state_tree_shell(tree), READBACK_SUCCESS,
                  "inspect_state_tree_shell")
    hashes = final_vector()
    if immutable_vector() != before:
        fail("admission/stock artifacts changed")
    marker = ("WORKER-PLAN-BASELINE-ASSET-SAVED assets=1 baseline_empty=1 "
              "ownership=1 immutable_hashes_unchanged=1 hashes=%r" % hashes)
    unreal.log(marker)
    print(marker, flush=True)


main()

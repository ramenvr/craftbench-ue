"""Fresh-process read-only admission StateTree verification."""

import hashlib
from pathlib import Path

import unreal


TASK_ID = "t3-the-worker-keeps-its-new-plan-after-the-signal"
DIR = "/Game/__CraftBenchAdmission/" + TASK_ID
TREE = DIR + "/ST_WorkerPlan_Admission"
TREE_OBJECT = TREE + ".ST_WorkerPlan_Admission"
SCHEMA_OBJECT = (TREE_OBJECT
                 + ":StateTreeEditorData_0.StateTreeAIComponentSchema_0")
READBACK_SUCCESS = (
    "PASS ownership=1 signal_transition=1 navigation_task=1 "
    "tree=" + TREE_OBJECT + " schema=" + SCHEMA_OBJECT)
REPO = Path(__file__).resolve().parents[4]
FILE = (REPO / "UE-projects" / "ThirdPerson" / "Content" /
        "__CraftBenchAdmission" / TASK_ID / "ST_WorkerPlan_Admission.uasset")


def fail(message):
    unreal.log_error("WORKER-PLAN-ADMISSION-READBACK-FAILED: " + message)
    raise RuntimeError(message)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def require_native_success(result):
    """Require UE 5.8's exact single-string binding and every native gate."""
    if type(result) is not str:  # exact built-in shape, not string-coercible
        fail("inspect_state_tree returned unexpected UE5.8 shape: %r" %
             (result,))
    if result != READBACK_SUCCESS:
        fail("inspect_state_tree success vector mismatch expected=%r actual=%r"
             % (READBACK_SUCCESS, result))
    return result


def main():
    if not FILE.is_file() or FILE.is_symlink():
        fail("exact package file missing/non-regular: " + str(FILE))
    before = sha256(FILE)
    observed = {str(value).split(".", 1)[0] for value in
                unreal.EditorAssetLibrary.list_assets(
                    DIR, recursive=True, include_folder=False)}
    if observed != {TREE}:
        fail("exact inventory expected one StateTree, got %r" % sorted(observed))
    tree = unreal.EditorAssetLibrary.load_asset(TREE)
    helper = getattr(unreal, "WorkerPlanAssetAuthoring", None)
    if tree is None or helper is None:
        fail("exact tree or native helper unavailable")
    detail = require_native_success(helper.inspect_state_tree(tree))
    after = sha256(FILE)
    if after != before:
        fail("readback changed package hash")
    unreal.log("WORKER-PLAN-ADMISSION-READBACK-PASS path=%s sha256=%s %s" %
               (TREE, after, detail))


main()

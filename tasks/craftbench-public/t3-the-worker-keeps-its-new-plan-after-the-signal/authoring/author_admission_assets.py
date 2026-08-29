"""One-shot, fail-closed admission StateTree authoring."""

import hashlib
import os
from pathlib import Path

import unreal


TASK_ID = "t3-the-worker-keeps-its-new-plan-after-the-signal"
DIR = "/Game/__CraftBenchAdmission/" + TASK_ID
TREE = DIR + "/ST_WorkerPlan_Admission"
TREE_OBJECT = TREE + ".ST_WorkerPlan_Admission"
SCHEMA_OBJECT = (TREE_OBJECT
                 + ":StateTreeEditorData_0.StateTreeAIComponentSchema_0")
AUTHOR_SUCCESS = (
    "PASS SAVED PASS ownership=1 signal_transition=1 navigation_task=1 "
    "tree=" + TREE_OBJECT + " schema=" + SCHEMA_OBJECT)
READBACK_SUCCESS = (
    "PASS ownership=1 signal_transition=1 navigation_task=1 "
    "tree=" + TREE_OBJECT + " schema=" + SCHEMA_OBJECT)
REPO = Path(__file__).resolve().parents[4]
CONTENT = REPO / "UE-projects" / "ThirdPerson" / "Content"
OUTPUT = CONTENT / "__CraftBenchAdmission" / TASK_ID / "ST_WorkerPlan_Admission.uasset"
PROTECTED = {
    "final_assets": CONTENT / "Tasks" / TASK_ID,
    "final_map": CONTENT / "Maps" / TASK_ID / "L_WorkerPlan.umap",
    "admission_map": CONTENT / "Maps" / TASK_ID / "L_WorkerPlanAdmission.umap",
    "reference": REPO / "tasks" / "bp" / TASK_ID / "reference",
}


def fail(message):
    unreal.log_error("WORKER-PLAN-ADMISSION-ASSETS-FAILED: " + message)
    raise RuntimeError(message)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def is_link(path):
    junction = getattr(path, "is_junction", None)
    return path.is_symlink() or (junction is not None and junction())


def snapshot(path):
    if is_link(path):
        fail("protected path is link/reparse: " + str(path))
    if not path.exists():
        return {"kind": "absent"}
    if path.is_file():
        return {"kind": "file", "sha256": sha256(path)}
    files = {}
    for root, dirs, names in os.walk(path, followlinks=False):
        root_path = Path(root)
        for name in dirs:
            if is_link(root_path / name):
                fail("protected child is link/reparse: " + str(root_path / name))
        for name in names:
            child = root_path / name
            if is_link(child) or not child.is_file():
                fail("protected child is not regular: " + str(child))
            files[str(child.relative_to(path)).replace("\\", "/")] = sha256(child)
    return {"kind": "directory", "files": files}


def protected_snapshot():
    return {name: snapshot(path) for name, path in PROTECTED.items()}


def require_native_success(result, expected, call_name):
    """Validate the exact UE 5.8 Python shape and the complete success vector.

    UE 5.8 exposes this BlueprintCallable ``bool + FString& Out`` signature as
    the single output string. Treating a prefix, truthy object, or tuple as
    success would drop one or more native gates, so all are rejected.
    """
    if type(result) is not str:  # exact built-in shape, not string-coercible
        fail("%s returned unexpected UE5.8 shape: %r" % (call_name, result))
    if result != expected:
        fail("%s success vector mismatch expected=%r actual=%r" %
             (call_name, expected, result))
    return result


def main():
    disk_dir = OUTPUT.parent
    if disk_dir.exists() or unreal.EditorAssetLibrary.does_directory_exist(DIR):
        fail("refusing non-empty/existing admission namespace: " + DIR)
    before = protected_snapshot()
    helper = getattr(unreal, "WorkerPlanAssetAuthoring", None)
    if helper is None:
        fail("native author helper unavailable")
    detail = require_native_success(
        helper.author_state_tree(TREE), AUTHOR_SUCCESS, "author_state_tree")
    if not OUTPUT.is_file() or is_link(OUTPUT):
        fail("exact output missing or non-regular: " + str(OUTPUT))
    observed = {str(value).split(".", 1)[0] for value in
                unreal.EditorAssetLibrary.list_assets(
                    DIR, recursive=True, include_folder=False)}
    if observed != {TREE}:
        fail("exact package set mismatch: %r" % sorted(observed))
    tree = unreal.EditorAssetLibrary.load_asset(TREE)
    inspect_detail = require_native_success(
        helper.inspect_state_tree(tree), READBACK_SUCCESS,
        "inspect_state_tree")
    after = protected_snapshot()
    if after != before:
        fail("protected final/map/reference boundary changed")
    # This is the only terminal success marker. It is unreachable unless both
    # native calls matched the complete three-gate vector and every filesystem
    # and protected-boundary check above passed.
    unreal.log("WORKER-PLAN-ADMISSION-ASSETS-SAVED path=%s sha256=%s %s" %
               (TREE, sha256(OUTPUT), inspect_detail))


main()

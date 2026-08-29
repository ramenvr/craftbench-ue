"""One-shot retained empty-scaffold authoring; never overwrites packages."""

import hashlib
import os
from pathlib import Path

import unreal


TASK_ID = "t3-alerted-crowd-shares-live-poses-by-state"
ROOT = "/Game/Tasks/" + TASK_ID
SETUP = ROOT + "/AS_AlertCrowdSharing"
PROCESSOR = ROOT + "/BP_AlertCrowdStateProcessor"
REPO = Path(__file__).resolve().parents[4]
CONTENT = Path(unreal.Paths.convert_relative_path_to_full(
    unreal.Paths.project_content_dir()))
OUTPUTS = (
    CONTENT / "Tasks" / TASK_ID / "AS_AlertCrowdSharing.uasset",
    CONTENT / "Tasks" / TASK_ID / "BP_AlertCrowdStateProcessor.uasset",
)
PROTECTED = {
    "admission_assets": CONTENT / "__CraftBenchAdmission" / TASK_ID,
    "admission_map": CONTENT / "Maps" / TASK_ID /
    "L_AlertCrowdSharingAdmission.umap",
    "final_map": CONTENT / "Maps" / TASK_ID / "L_AlertCrowdSharing.umap",
    "reference": REPO / "tasks" / "bp" / TASK_ID / "reference",
}


def fail(message):
    unreal.log_error("ALERT-CROWD-FINAL-ASSETS-FAILED: " + message)
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
        current = Path(root)
        for name in dirs:
            if is_link(current / name):
                fail("protected descendant is link/reparse: " + str(current / name))
        for name in names:
            child = current / name
            if is_link(child) or not child.is_file():
                fail("protected descendant is not regular: " + str(child))
            files[str(child.relative_to(path)).replace("\\", "/")] = sha256(child)
    return {"kind": "directory", "files": files}


def protected_snapshot():
    return {name: snapshot(path) for name, path in PROTECTED.items()}


def main():
    if OUTPUTS[0].parent.exists() \
            or unreal.EditorAssetLibrary.does_directory_exist(ROOT):
        fail("refusing existing final namespace: " + ROOT)
    before = protected_snapshot()
    helper = getattr(unreal, "AlertCrowdSharingAssetAuthoring", None)
    if helper is None:
        fail("native authoring helper unavailable")
    detail = helper.author_empty_final_scaffold()
    if type(detail) is not str or not detail.startswith(
            "PASS EMPTY_SCAFFOLD setup="):
        fail("native empty-scaffold vector mismatch: %r" % (detail,))
    observed = {str(value).split(".", 1)[0] for value in
                unreal.EditorAssetLibrary.list_assets(
                    ROOT, recursive=True, include_folder=False)}
    if observed != {SETUP, PROCESSOR}:
        fail("exact package inventory mismatch: %r" % sorted(observed))
    if any(not path.is_file() or is_link(path) for path in OUTPUTS):
        fail("exact output missing/non-regular")
    readback = helper.inspect_final_assets(False)
    if type(readback) is not str or not readback.startswith(
            "PASS EMPTY exact_assets=2 expected_complete=0 "):
        fail("same-process empty readback mismatch: %r" % (readback,))
    if protected_snapshot() != before:
        fail("protected admission/map/reference boundary changed")
    hashes = ",".join(path.name + "=" + sha256(path) for path in OUTPUTS)
    unreal.log("ALERT-CROWD-FINAL-ASSETS-SAVED exact=2 complete=0 "
               "hashes=%s %s" % (hashes, readback))


main()

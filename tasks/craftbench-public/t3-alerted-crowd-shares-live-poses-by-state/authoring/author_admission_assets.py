"""One-shot, fail-closed admission Animation Sharing asset authoring."""

import hashlib
import os
from pathlib import Path

import unreal


TASK_ID = "t3-alerted-crowd-shares-live-poses-by-state"
ROOT = "/Game/__CraftBenchAdmission/" + TASK_ID
SETUP = ROOT + "/AS_AlertCrowdSharing_Admission"
PROCESSOR = ROOT + "/BP_AlertCrowdStateProcessor_Admission"
REPO = Path(__file__).resolve().parents[4]
CONTENT = REPO / "UE-projects" / "ThirdPerson" / "Content"
OUTPUTS = (
    CONTENT / "__CraftBenchAdmission" / TASK_ID /
    "AS_AlertCrowdSharing_Admission.uasset",
    CONTENT / "__CraftBenchAdmission" / TASK_ID /
    "BP_AlertCrowdStateProcessor_Admission.uasset",
)
PROTECTED = {
    "final_assets": CONTENT / "Tasks" / TASK_ID,
    "final_map": CONTENT / "Maps" / TASK_ID / "L_AlertCrowdSharing.umap",
    "admission_map": CONTENT / "Maps" / TASK_ID /
    "L_AlertCrowdSharingAdmission.umap",
    "reference": REPO / "tasks" / "bp" / TASK_ID / "reference",
}


def fail(message):
    unreal.log_error("ALERT-CROWD-ADMISSION-ASSETS-FAILED: " + message)
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
    disk_root = OUTPUTS[0].parent
    if disk_root.exists() or unreal.EditorAssetLibrary.does_directory_exist(ROOT):
        fail("refusing existing admission namespace: " + ROOT)
    before = protected_snapshot()
    helper = getattr(unreal, "AlertCrowdSharingAssetAuthoring", None)
    if helper is None:
        fail("native authoring helper unavailable")
    detail = helper.author_admission_assets()
    if type(detail) is not str or not detail.startswith(
            "PASS SAVED exact_assets=2 setup={PASS "):
        fail("native complete success vector mismatch: %r" % (detail,))
    observed = {str(value).split(".", 1)[0] for value in
                unreal.EditorAssetLibrary.list_assets(
                    ROOT, recursive=True, include_folder=False)}
    if observed != {SETUP, PROCESSOR}:
        fail("exact package inventory mismatch: %r" % sorted(observed))
    for path in OUTPUTS:
        if not path.is_file() or is_link(path):
            fail("exact output missing/non-regular: " + str(path))
    readback = helper.inspect_admission_assets()
    if type(readback) is not str or not readback.startswith(
            "PASS exact_assets=2 setup={PASS "):
        fail("same-process readback mismatch: %r" % (readback,))
    if protected_snapshot() != before:
        fail("protected final/map/reference boundary changed")
    hashes = ",".join(path.name + "=" + sha256(path) for path in OUTPUTS)
    unreal.log("ALERT-CROWD-ADMISSION-ASSETS-SAVED exact=2 hashes=%s %s" %
               (hashes, readback))


main()

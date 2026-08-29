"""Disposable-substrate complete reference authoring at the final paths."""

import hashlib
from pathlib import Path

import unreal


TASK_ID = "t3-alerted-crowd-shares-live-poses-by-state"
ROOT = "/Game/Tasks/" + TASK_ID
SETUP = ROOT + "/AS_AlertCrowdSharing"
PROCESSOR = ROOT + "/BP_AlertCrowdStateProcessor"
CONTENT = Path(unreal.Paths.convert_relative_path_to_full(
    unreal.Paths.project_content_dir()))
OUTPUTS = (
    CONTENT / "Tasks" / TASK_ID / "AS_AlertCrowdSharing.uasset",
    CONTENT / "Tasks" / TASK_ID / "BP_AlertCrowdStateProcessor.uasset",
)
MAP_FILE = CONTENT / "Maps" / TASK_ID / "L_AlertCrowdSharing.umap"


def fail(message):
    unreal.log_error("ALERT-CROWD-REFERENCE-ASSETS-FAILED: " + message)
    raise RuntimeError(message)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main():
    if OUTPUTS[0].parent.exists() \
            or unreal.EditorAssetLibrary.does_directory_exist(ROOT):
        fail("refusing existing final namespace: " + ROOT)
    if not MAP_FILE.is_file() or MAP_FILE.is_symlink():
        fail("retained final map missing/non-regular")
    map_before = sha256(MAP_FILE)
    helper = getattr(unreal, "AlertCrowdSharingAssetAuthoring", None)
    if helper is None:
        fail("native authoring helper unavailable")
    detail = helper.author_reference_assets()
    if type(detail) is not str or not detail.startswith(
            "PASS SAVED exact_assets=2 setup={PASS "):
        fail("native complete vector mismatch: %r" % (detail,))
    observed = {str(value).split(".", 1)[0] for value in
                unreal.EditorAssetLibrary.list_assets(
                    ROOT, recursive=True, include_folder=False)}
    if observed != {SETUP, PROCESSOR}:
        fail("exact package inventory mismatch: %r" % sorted(observed))
    if any(not path.is_file() or path.is_symlink() for path in OUTPUTS):
        fail("exact output missing/non-regular")
    readback = helper.inspect_final_assets(True)
    if type(readback) is not str or not readback.startswith(
            "PASS COMPLETE exact_assets=2 expected_complete=1 "):
        fail("same-process complete readback mismatch: %r" % (readback,))
    if sha256(MAP_FILE) != map_before:
        fail("reference authoring changed retained map bytes")
    hashes = ",".join(path.name + "=" + sha256(path) for path in OUTPUTS)
    unreal.log("ALERT-CROWD-REFERENCE-ASSETS-SAVED exact=2 complete=1 "
               "map_unchanged=1 hashes=%s %s" % (hashes, readback))


main()

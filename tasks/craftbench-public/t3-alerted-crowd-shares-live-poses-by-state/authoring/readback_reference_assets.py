"""Fresh-process complete-reference readback in a disposable substrate."""

import hashlib
from pathlib import Path

import unreal


TASK_ID = "t3-alerted-crowd-shares-live-poses-by-state"
ROOT = "/Game/Tasks/" + TASK_ID
SETUP = ROOT + "/AS_AlertCrowdSharing"
PROCESSOR = ROOT + "/BP_AlertCrowdStateProcessor"
CONTENT = Path(unreal.Paths.convert_relative_path_to_full(
    unreal.Paths.project_content_dir()))
FILES = (
    CONTENT / "Tasks" / TASK_ID / "AS_AlertCrowdSharing.uasset",
    CONTENT / "Tasks" / TASK_ID / "BP_AlertCrowdStateProcessor.uasset",
)
MAP_FILE = CONTENT / "Maps" / TASK_ID / "L_AlertCrowdSharing.umap"


def fail(message):
    unreal.log_error("ALERT-CROWD-REFERENCE-READBACK-FAILED: " + message)
    raise RuntimeError(message)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main():
    if any(not path.is_file() or path.is_symlink() for path in FILES):
        fail("exact two package files are missing or links")
    if not MAP_FILE.is_file() or MAP_FILE.is_symlink():
        fail("retained final map missing/non-regular")
    before = {path.name: sha256(path) for path in FILES}
    map_before = sha256(MAP_FILE)
    observed = {str(value).split(".", 1)[0] for value in
                unreal.EditorAssetLibrary.list_assets(
                    ROOT, recursive=True, include_folder=False)}
    if observed != {SETUP, PROCESSOR}:
        fail("exact inventory mismatch: %r" % sorted(observed))
    helper = getattr(unreal, "AlertCrowdSharingAssetAuthoring", None)
    detail = helper.inspect_final_assets(True) if helper else None
    if type(detail) is not str or not detail.startswith(
            "PASS COMPLETE exact_assets=2 expected_complete=1 "):
        fail("cold complete vector mismatch: %r" % (detail,))
    after = {path.name: sha256(path) for path in FILES}
    if after != before or sha256(MAP_FILE) != map_before:
        fail("readback changed protected bytes")
    unreal.log("ALERT-CROWD-REFERENCE-READBACK-PASS exact=2 complete=1 "
               "map_unchanged=1 hashes=%r %s" % (after, detail))


main()

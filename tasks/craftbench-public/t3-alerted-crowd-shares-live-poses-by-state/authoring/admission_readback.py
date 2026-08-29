"""Fresh-process, read-only admission asset validation."""

import hashlib
from pathlib import Path

import unreal


TASK_ID = "t3-alerted-crowd-shares-live-poses-by-state"
ROOT = "/Game/__CraftBenchAdmission/" + TASK_ID
SETUP = ROOT + "/AS_AlertCrowdSharing_Admission"
PROCESSOR = ROOT + "/BP_AlertCrowdStateProcessor_Admission"
REPO = Path(__file__).resolve().parents[4]
CONTENT = REPO / "UE-projects" / "ThirdPerson" / "Content"
FILES = (
    CONTENT / "__CraftBenchAdmission" / TASK_ID /
    "AS_AlertCrowdSharing_Admission.uasset",
    CONTENT / "__CraftBenchAdmission" / TASK_ID /
    "BP_AlertCrowdStateProcessor_Admission.uasset",
)


def fail(message):
    unreal.log_error("ALERT-CROWD-ADMISSION-READBACK-FAILED: " + message)
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
    before = {path.name: sha256(path) for path in FILES}
    observed = {str(value).split(".", 1)[0] for value in
                unreal.EditorAssetLibrary.list_assets(
                    ROOT, recursive=True, include_folder=False)}
    if observed != {SETUP, PROCESSOR}:
        fail("exact inventory mismatch: %r" % sorted(observed))
    setup = unreal.EditorAssetLibrary.load_asset(SETUP)
    processor = unreal.EditorAssetLibrary.load_asset(PROCESSOR)
    if setup is None or processor is None:
        fail("exact assets did not load")
    helper = getattr(unreal, "AlertCrowdSharingAssetAuthoring", None)
    detail = helper.inspect_admission_assets() if helper else None
    if type(detail) is not str or not detail.startswith(
            "PASS exact_assets=2 setup={PASS "):
        fail("cold native success vector mismatch: %r" % (detail,))
    after = {path.name: sha256(path) for path in FILES}
    if after != before:
        fail("readback changed package bytes")
    unreal.log("ALERT-CROWD-ADMISSION-READBACK-PASS exact=2 hashes=%r %s" %
               (after, detail))


main()

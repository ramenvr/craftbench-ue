"""Fresh-process read-only admission map identity check."""

import hashlib
from pathlib import Path

import unreal


TASK_ID = "t3-alerted-crowd-shares-live-poses-by-state"
SETUP = "/Game/__CraftBenchAdmission/" + TASK_ID + "/AS_AlertCrowdSharing_Admission"
MAP = "/Game/Maps/" + TASK_ID + "/L_AlertCrowdSharingAdmission"
REPO = Path(__file__).resolve().parents[4]
MAP_FILE = (REPO / "UE-projects" / "ThirdPerson" / "Content" / "Maps" /
            TASK_ID / "L_AlertCrowdSharingAdmission.umap")


def fail(message):
    unreal.log_error("ALERT-CROWD-ADMISSION-MAP-READBACK-FAILED: " + message)
    raise RuntimeError(message)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main():
    if not MAP_FILE.is_file() or MAP_FILE.is_symlink():
        fail("exact map file missing/non-regular")
    before = sha256(MAP_FILE)
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not levels.load_level(MAP):
        fail("map load failed")
    actors = list(unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem).get_all_level_actors())
    subjects = [a for a in actors if
                a.get_class() == unreal.AlertCrowdSharingSubject.static_class()]
    hosts = [a for a in actors if
             a.get_class() == unreal.AlertCrowdSharingHost.static_class()]
    fixtures = [a for a in actors if a.get_class() ==
                unreal.AlertCrowdSharingAdmissionFunctionalTest.static_class()]
    setup = unreal.EditorAssetLibrary.load_asset(SETUP)
    if len(subjects) != 6 or len(hosts) != 1 or len(fixtures) != 1 \
            or setup is None:
        fail("exact map identity/cardinality failed")
    if sorted(int(a.get_editor_property("slot_index")) for a in subjects) \
            != list(range(6)):
        fail("slot inventory is not exact 0..5")
    if hosts[0].get_editor_property("sharing_setup") != setup \
            or fixtures[0].get_editor_property("expected_setup") != setup:
        fail("exact setup identity assignment failed")
    after = sha256(MAP_FILE)
    if after != before:
        fail("read-only map load changed bytes")
    unreal.log("ALERT-CROWD-ADMISSION-MAP-READBACK-PASS map=%s sha256=%s "
               "subjects=6 host=1 fixture=1 exact_setup=1" % (MAP, after))


main()

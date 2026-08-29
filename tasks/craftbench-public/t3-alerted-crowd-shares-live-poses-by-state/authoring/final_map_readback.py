"""Fresh-process read-only retained map identity check."""

import hashlib
from pathlib import Path

import unreal


TASK_ID = "t3-alerted-crowd-shares-live-poses-by-state"
SETUP = "/Game/Tasks/" + TASK_ID + "/AS_AlertCrowdSharing"
MAP = "/Game/Maps/" + TASK_ID + "/L_AlertCrowdSharing"
CONTENT = Path(unreal.Paths.convert_relative_path_to_full(
    unreal.Paths.project_content_dir()))
MAP_FILE = CONTENT / "Maps" / TASK_ID / "L_AlertCrowdSharing.umap"
ASSET_FILES = (
    CONTENT / "Tasks" / TASK_ID / "AS_AlertCrowdSharing.uasset",
    CONTENT / "Tasks" / TASK_ID / "BP_AlertCrowdStateProcessor.uasset",
)


def fail(message):
    unreal.log_error("ALERT-CROWD-FINAL-MAP-READBACK-FAILED: " + message)
    raise RuntimeError(message)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main():
    locked = (MAP_FILE,) + ASSET_FILES
    if any(not path.is_file() or path.is_symlink() for path in locked):
        fail("exact retained packages missing/non-regular")
    before = {path.name: sha256(path) for path in locked}
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not levels.load_level(MAP):
        fail("map load failed")
    actors = list(unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem).get_all_level_actors())
    subjects = [actor for actor in actors if actor.get_class() ==
                unreal.AlertCrowdSharingSubject.static_class()]
    hosts = [actor for actor in actors if actor.get_class() ==
             unreal.AlertCrowdSharingHost.static_class()]
    fixtures = [actor for actor in actors if actor.get_class() ==
                unreal.AlertCrowdSharingFunctionalTest.static_class()]
    setup = unreal.EditorAssetLibrary.load_asset(SETUP)
    helper = getattr(unreal, "AlertCrowdSharingAssetAuthoring", None)
    asset_detail = helper.inspect_final_assets(False) if helper else None
    if len(subjects) != 6 or len(hosts) != 1 or len(fixtures) != 1 \
            or setup is None:
        fail("exact map identity/cardinality failed")
    if sorted(int(actor.get_editor_property("slot_index"))
              for actor in subjects) != list(range(6)):
        fail("slot inventory is not exact 0..5")
    if hosts[0].get_editor_property("sharing_setup") != setup \
            or fixtures[0].get_editor_property("expected_setup") != setup:
        fail("exact setup identity assignment failed")
    if type(asset_detail) is not str or not asset_detail.startswith(
            "PASS EMPTY exact_assets=2 expected_complete=0 "):
        fail("retained empty asset contract failed: %r" % (asset_detail,))
    after = {path.name: sha256(path) for path in locked}
    if after != before:
        fail("read-only map load changed protected bytes")
    unreal.log("ALERT-CROWD-FINAL-MAP-READBACK-PASS map=%s sha256=%s "
               "subjects=6 host=1 fixture=1 exact_setup=1 complete=0" %
               (MAP, after[MAP_FILE.name]))


main()

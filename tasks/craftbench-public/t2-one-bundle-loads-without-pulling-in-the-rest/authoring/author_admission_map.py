"""Author the isolated verifier-owned engine-control admission map once."""

import hashlib
from pathlib import Path
import unreal


TASK = "t2-one-bundle-loads-without-pulling-in-the-rest"
MAP = f"/Game/Maps/{TASK}/L_BundleLeaseAdmission"
FINAL_MAP = f"/Game/Maps/{TASK}/L_BundleLeases"


def protected_assets():
    root = (Path(unreal.Paths.convert_relative_path_to_full(
        unreal.Paths.project_content_dir())) / "Maps" / TASK / "Records")
    files = sorted(root.glob("*.uasset"))
    if len(files) != 15:
        fail("protected asset inventory=%d expected=15" % len(files))
    return files


def hashes(files):
    return {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in files}


def fail(message):
    unreal.log_error("BUNDLE-LEASE-ADMISSION-MAP-AUTHOR-ERROR " + message)
    raise RuntimeError(message)


def make_id(name):
    asset_type = unreal.PrimaryAssetType()
    asset_type.set_editor_property("name", "BundleLeaseRecord")
    value = unreal.PrimaryAssetId()
    value.set_editor_property("primary_asset_type", asset_type)
    value.set_editor_property("primary_asset_name", name)
    return value


def spawn(eas, cls, location, label):
    actor = eas.spawn_actor_from_class(cls, location, unreal.Rotator())
    if actor is None:
        fail("spawn failed: " + label)
    actor.set_actor_label(label)
    return actor


def main():
    if unreal.EditorAssetLibrary.does_asset_exist(MAP):
        fail("exact admission map already exists; quarantine explicitly")
    if unreal.EditorAssetLibrary.does_asset_exist(FINAL_MAP):
        fail("final map unexpectedly exists before admission authoring")
    assets = protected_assets()
    before = hashes(assets)
    scenario_cls = getattr(unreal, "BundleLeaseScenario", None)
    fixture_cls = getattr(unreal, "BundleLeaseAdmissionFunctionalTest", None)
    if not scenario_cls or not fixture_cls:
        fail("admission classes unavailable; build ThirdPersonEditor")
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if not les.new_level_from_template(MAP, "/Engine/Maps/Templates/Template_Default"):
        fail("new_level_from_template failed")
    for actor in list(eas.get_all_level_actors()):
        eas.destroy_actor(actor)

    scenario = spawn(eas, scenario_cls, unreal.Vector(0, 0, 100), "BundleLeaseScenario")
    scenario.set_editor_property("selected_primary_asset_id", make_id("DA_BundleRecord_Quartz"))
    scenario.set_editor_property("selected_bundle_name", "Violet")
    scenario.set_editor_property("release_a_first", False)
    fixture = spawn(eas, fixture_cls, unreal.Vector(-300, 0, 100),
                    "BundleLeaseAdmissionFunctionalTest")
    spawn(eas, unreal.PlayerStart, unreal.Vector(-600, 0, 100), "PlayerStart")
    spawn(eas, unreal.DirectionalLight, unreal.Vector(0, 0, 800), "DirectionalLight")
    if not les.save_current_level():
        fail("save_current_level returned false")
    if scenario is fixture:
        fail("scenario/fixture identity collision")
    if hashes(assets) != before:
        fail("map author changed a protected record package")
    unreal.log("BUNDLE-LEASE-ADMISSION-MAP-SAVED map=L_BundleLeaseAdmission "
               "scenario=1 admission_fixture=1 final_fixture=0 runtime_hosts=0 runtime_consumers=0")


main()

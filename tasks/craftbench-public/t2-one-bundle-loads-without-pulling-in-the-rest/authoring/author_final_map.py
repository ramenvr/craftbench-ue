"""Author the production map with editable runtime host/consumers once."""

import hashlib
from pathlib import Path
import unreal


TASK = "t2-one-bundle-loads-without-pulling-in-the-rest"
MAP = f"/Game/Maps/{TASK}/L_BundleLeases"
ADMISSION_MAP = f"/Game/Maps/{TASK}/L_BundleLeaseAdmission"


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
    unreal.log_error("BUNDLE-LEASE-FINAL-MAP-AUTHOR-ERROR " + message)
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


def add_tag(actor, tag):
    tags = [str(item) for item in actor.get_editor_property("tags") if str(item) != tag]
    tags.append(tag)
    actor.set_editor_property("tags", tags)


def mesh_actor(eas, mesh, location, scale, label):
    actor = spawn(eas, unreal.StaticMeshActor, location, label)
    actor.static_mesh_component.set_static_mesh(mesh)
    actor.set_actor_scale3d(scale)
    return actor


def main():
    if unreal.EditorAssetLibrary.does_asset_exist(MAP):
        fail("exact final map already exists; quarantine explicitly")
    if not unreal.EditorAssetLibrary.does_asset_exist(ADMISSION_MAP):
        fail("admission map must exist before final authoring")
    assets = protected_assets()
    before = hashes(assets)
    classes = {name: getattr(unreal, name, None) for name in (
        "BundleLeaseHost", "BundleLeaseConsumer", "BundleLeaseScenario",
        "BundleLeaseFunctionalTest")}
    if any(value is None for value in classes.values()):
        fail("one or more final runtime/verifier classes are unavailable")
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if not les.new_level_from_template(MAP, "/Engine/Maps/Templates/Template_Default"):
        fail("new_level_from_template failed")
    for actor in list(eas.get_all_level_actors()):
        eas.destroy_actor(actor)

    host = spawn(eas, classes["BundleLeaseHost"], unreal.Vector(0, 0, 120),
                 "BundleLeaseHost")
    consumer_a = spawn(eas, classes["BundleLeaseConsumer"],
                       unreal.Vector(0, -300, 120), "BundleLeaseConsumer_A")
    consumer_b = spawn(eas, classes["BundleLeaseConsumer"],
                       unreal.Vector(0, 300, 120), "BundleLeaseConsumer_B")
    add_tag(consumer_a, "BundleLease.ConsumerA")
    add_tag(consumer_b, "BundleLease.ConsumerB")
    for actor, decoy, bundle in (
            (consumer_a, "DA_BundleRecord_Quartz", "Quartz"),
            (consumer_b, "DA_BundleRecord_Violet", "Violet")):
        actor.set_editor_property("lease_host", host)
        actor.set_editor_property("requested_primary_asset_id", make_id(decoy))
        actor.set_editor_property("requested_bundle_name", bundle)

    scenario = spawn(eas, classes["BundleLeaseScenario"],
                     unreal.Vector(400, 0, 100), "BundleLeaseScenario")
    scenario.set_editor_property("selected_primary_asset_id", make_id("DA_BundleRecord_Amber"))
    scenario.set_editor_property("selected_bundle_name", "Quartz")
    scenario.set_editor_property("release_a_first", True)
    spawn(eas, classes["BundleLeaseFunctionalTest"], unreal.Vector(-450, 0, 100),
          "BundleLeaseFunctionalTest")

    cube = unreal.EditorAssetLibrary.load_asset("/Engine/BasicShapes/Cube.Cube")
    cylinder = unreal.EditorAssetLibrary.load_asset("/Engine/BasicShapes/Cylinder.Cylinder")
    if cube is None or cylinder is None:
        fail("engine basic shape assets unavailable")
    mesh_actor(eas, cube, unreal.Vector(0, 0, -50), unreal.Vector(14, 10, 1),
               "BundleLeaseFloor")
    mesh_actor(eas, cylinder, unreal.Vector(0, -300, 40), unreal.Vector(1, 1, 2),
               "ConsumerA_Marker")
    mesh_actor(eas, cylinder, unreal.Vector(0, 300, 40), unreal.Vector(1, 1, 2),
               "ConsumerB_Marker")
    mesh_actor(eas, cube, unreal.Vector(400, 0, 50), unreal.Vector(2, 2, 1),
               "ScenarioMarker")
    spawn(eas, unreal.PlayerStart, unreal.Vector(-700, 0, 100), "PlayerStart")
    spawn(eas, unreal.DirectionalLight, unreal.Vector(0, 0, 800), "DirectionalLight")
    spawn(eas, unreal.SkyLight, unreal.Vector(0, 0, 700), "SkyLight")

    if not les.save_current_level():
        fail("save_current_level returned false")
    if hashes(assets) != before:
        fail("final map author changed a protected record package")
    unreal.log("BUNDLE-LEASE-FINAL-MAP-SAVED map=L_BundleLeases scenario=1 "
               "final_fixture=1 admission_fixture=0 runtime_hosts=1 runtime_consumers=2")


main()

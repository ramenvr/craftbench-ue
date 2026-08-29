"""Author one exact final or admission host map; never overwrite."""

from __future__ import annotations

import os

import unreal


TASK_ID = "t3-only-the-requested-district-enters-and-leaves-the-world"
FINAL_MAP = "/Game/Maps/%s/L_DistrictStreaming" % TASK_ID
ADMISSION_MAP = "/Game/__CraftBenchAdmission/%s/L_DistrictStreamingAdmission" % TASK_ID
ALPHA = "/Game/Maps/%s/Support/L_DistrictAlpha" % TASK_ID
BETA = "/Game/Maps/%s/Support/L_DistrictBeta" % TASK_ID
FINAL_LOADER = "/Game/Tasks/%s/BP_DistrictStreamLoader.BP_DistrictStreamLoader_C" % TASK_ID
ADMISSION_LOADER = "/Script/CraftBenchTests.DistrictStreamingAdmissionLoader"
FINAL_FIXTURES = (
    "/Script/CraftBenchTests.DistrictStreamingFunctionalTestAlpha",
    "/Script/CraftBenchTests.DistrictStreamingFunctionalTestBeta",
)
ADMISSION_FIXTURES = (
    "/Script/CraftBenchTests.DistrictStreamingAdmissionFunctionalTestAlpha",
    "/Script/CraftBenchTests.DistrictStreamingAdmissionFunctionalTestBeta",
)


def fail(message: str) -> None:
    unreal.log_error("DISTRICT-STREAMING-HOST-ERROR " + message)
    raise RuntimeError(message)


def load_world(path: str):
    value = unreal.EditorAssetLibrary.load_asset(path)
    if value is None or value.get_class().get_name() != "World":
        fail("support world did not load " + path)
    return value


def spawn(actor_class, label: str, location: unreal.Vector):
    value = unreal.EditorLevelLibrary.spawn_actor_from_class(actor_class, location)
    if value is None:
        fail("spawn failed " + label)
    value.set_actor_label(label)
    return value


def configure_request(actor, requested, control, requested_id: str, control_id: str) -> None:
    actor.set_editor_property("requested_district", requested)
    actor.set_editor_property("unrelated_control_district", control)
    actor.set_editor_property("requested_district_id", requested_id)
    actor.set_editor_property("control_district_id", control_id)
    actor.set_editor_property("instance_name", "District%sInstance" % requested_id)


def main() -> None:
    mode = os.environ.get("CRAFTBENCH_DISTRICT_HOST_MODE", "")
    if mode not in ("final", "admission"):
        fail("CRAFTBENCH_DISTRICT_HOST_MODE must be final or admission")
    package = FINAL_MAP if mode == "final" else ADMISSION_MAP
    loader_path = FINAL_LOADER if mode == "final" else ADMISSION_LOADER
    fixture_paths = FINAL_FIXTURES if mode == "final" else ADMISSION_FIXTURES
    fixture_labels = (
        ("DistrictStreamingFunctionalTestAlpha",
         "DistrictStreamingFunctionalTestBeta")
        if mode == "final" else
        ("DistrictStreamingAlpha", "DistrictStreamingBeta")
    )
    if unreal.EditorAssetLibrary.does_asset_exist(package):
        fail("refusing to overwrite " + package)
    alpha = load_world(ALPHA)
    beta = load_world(BETA)
    loader_class = unreal.load_class(None, loader_path)
    request_class = unreal.load_class(None, "/Script/ThirdPerson.DistrictStreamRequest")
    fixture_classes = [unreal.load_class(None, path) for path in fixture_paths]
    if loader_class is None or request_class is None or any(value is None for value in fixture_classes):
        fail("required class did not load")
    if not unreal.EditorLevelLibrary.new_level(package):
        fail("new_level failed " + package)
    spawn(loader_class, "DistrictStreamLoader", unreal.Vector(0.0, 0.0, 50.0))
    request_alpha = spawn(
        request_class, "DistrictRequestAlpha", unreal.Vector(-200.0, 0.0, 50.0)
    )
    request_beta = spawn(
        request_class, "DistrictRequestBeta", unreal.Vector(200.0, 0.0, 50.0)
    )
    configure_request(request_alpha, alpha, beta, "Alpha", "Beta")
    configure_request(request_beta, beta, alpha, "Beta", "Alpha")
    spawn(fixture_classes[0], fixture_labels[0], unreal.Vector(-300.0, 250.0, 50.0))
    spawn(fixture_classes[1], fixture_labels[1], unreal.Vector(300.0, 250.0, 50.0))
    if not unreal.EditorLevelLibrary.save_current_level():
        fail("host map save failed")
    actors = unreal.EditorLevelLibrary.get_all_level_actors()
    loader_count = sum(1 for actor in actors if actor.get_class() == loader_class)
    request_count = sum(1 for actor in actors if actor.get_class() == request_class)
    fixture_counts = [sum(1 for actor in actors if actor.get_class() == cls) for cls in fixture_classes]
    if loader_count != 1 or request_count != 2 or fixture_counts != [1, 1]:
        fail(
            "host cardinality loader=%d requests=%d fixtures=%r"
            % (loader_count, request_count, fixture_counts)
        )
    unreal.log(
        "DISTRICT-STREAMING-HOST-SAVED mode=%s loaders=1 requests=2 fixtures=2 support_worlds=2"
        % mode
    )
    print(
        "DISTRICT-STREAMING-HOST-SAVED mode=%s loaders=1 requests=2 fixtures=2 support_worlds=2"
        % mode
    )


main()

"""Fresh-process, read-only final/admission host-map contract check."""

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


def soft_package(value) -> str:
    text = str(value)
    if text.startswith("<Object '") and text.endswith("'>"):
        text = text[9:-2]
    return text.split(".", 1)[0]


def main() -> None:
    mode = os.environ.get("CRAFTBENCH_DISTRICT_HOST_MODE", "")
    if mode not in ("final", "admission"):
        raise RuntimeError("DISTRICT_HOST_READBACK_MODE")
    package = FINAL_MAP if mode == "final" else ADMISSION_MAP
    loader_path = FINAL_LOADER if mode == "final" else ADMISSION_LOADER
    fixture_paths = FINAL_FIXTURES if mode == "final" else ADMISSION_FIXTURES
    fixture_labels = (
        ("DistrictStreamingFunctionalTestAlpha",
         "DistrictStreamingFunctionalTestBeta")
        if mode == "final" else
        ("DistrictStreamingAlpha", "DistrictStreamingBeta")
    )
    if not unreal.EditorLoadingAndSavingUtils.load_map(package):
        raise RuntimeError("DISTRICT_HOST_READBACK_LOAD")
    loader_class = unreal.load_class(None, loader_path)
    request_class = unreal.load_class(None, "/Script/ThirdPerson.DistrictStreamRequest")
    fixture_classes = [unreal.load_class(None, path) for path in fixture_paths]
    actors = unreal.EditorLevelLibrary.get_all_level_actors()
    loaders = [actor for actor in actors if actor.get_class() == loader_class]
    requests = [actor for actor in actors if actor.get_class() == request_class]
    fixture_counts = [sum(1 for actor in actors if actor.get_class() == cls) for cls in fixture_classes]
    if len(loaders) != 1 or len(requests) != 2 or fixture_counts != [1, 1]:
        raise RuntimeError(
            "DISTRICT_HOST_READBACK_COUNT loader=%d requests=%d fixtures=%r"
            % (len(loaders), len(requests), fixture_counts)
        )
    observed_labels = sorted(
        actor.get_actor_label() for actor in actors
        if actor.get_class() in fixture_classes
    )
    if observed_labels != sorted(fixture_labels):
        raise RuntimeError(
            "DISTRICT_HOST_READBACK_LABELS %r" % observed_labels
        )
    facts = {}
    for request in requests:
        requested_id = str(request.get_editor_property("requested_district_id"))
        control_id = str(request.get_editor_property("control_district_id"))
        facts[requested_id] = (
            soft_package(request.get_editor_property("requested_district")),
            control_id,
            soft_package(request.get_editor_property("unrelated_control_district")),
        )
    expected = {"Alpha": (ALPHA, "Beta", BETA), "Beta": (BETA, "Alpha", ALPHA)}
    if facts != expected:
        raise RuntimeError("DISTRICT_HOST_READBACK_REQUESTS %r" % facts)
    unreal.log(
        "DISTRICT-STREAMING-HOST-READBACK PASS mode=%s loaders=1 requests=2 fixtures=2 matrix=reciprocal"
        % mode
    )
    print(
        "DISTRICT-STREAMING-HOST-READBACK PASS mode=%s loaders=1 requests=2 fixtures=2 matrix=reciprocal"
        % mode
    )


main()

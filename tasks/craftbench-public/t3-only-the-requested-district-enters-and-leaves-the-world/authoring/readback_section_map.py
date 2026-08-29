"""Fresh-process, read-only streamed-section contract check."""

from __future__ import annotations

import os

import unreal


TASK_ID = "t3-only-the-requested-district-enters-and-leaves-the-world"
SUPPORT_DIR = "/Game/Maps/%s/Support" % TASK_ID
SECTIONS = {
    "Alpha": SUPPORT_DIR + "/L_DistrictAlpha",
    "Beta": SUPPORT_DIR + "/L_DistrictBeta",
}


def main() -> None:
    district = os.environ.get("CRAFTBENCH_DISTRICT_SECTION", "")
    package = SECTIONS.get(district)
    if package is None:
        raise RuntimeError("DISTRICT_SECTION_READBACK_MODE")
    if not unreal.EditorLoadingAndSavingUtils.load_map(package):
        raise RuntimeError("DISTRICT_SECTION_READBACK_LOAD " + package)
    marker_class = unreal.load_class(None, "/Script/ThirdPerson.DistrictSectionMarker")
    markers = [
        actor
        for actor in unreal.EditorLevelLibrary.get_all_level_actors()
        if actor.get_class() == marker_class
    ]
    if len(markers) != 1:
        raise RuntimeError("DISTRICT_SECTION_READBACK_COUNT %d" % len(markers))
    marker = markers[0]
    if str(marker.get_editor_property("district_id")) != district:
        raise RuntimeError("DISTRICT_SECTION_READBACK_ID")
    mesh = marker.get_editor_property("visible_marker")
    if mesh is None or mesh.get_editor_property("static_mesh") is None:
        raise RuntimeError("DISTRICT_SECTION_READBACK_VISIBLE")
    unreal.log(
        "DISTRICT-STREAMING-SECTION-READBACK PASS district=%s markers=1 visible=1"
        % district
    )
    print(
        "DISTRICT-STREAMING-SECTION-READBACK PASS district=%s markers=1 visible=1"
        % district
    )


main()

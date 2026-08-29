"""Author one verifier-owned streamed section selected by an environment key."""

from __future__ import annotations

import os

import unreal


TASK_ID = "t3-only-the-requested-district-enters-and-leaves-the-world"
SUPPORT_DIR = "/Game/Maps/%s/Support" % TASK_ID
SECTIONS = {
    "Alpha": SUPPORT_DIR + "/L_DistrictAlpha",
    "Beta": SUPPORT_DIR + "/L_DistrictBeta",
}


def fail(message: str) -> None:
    unreal.log_error("DISTRICT-STREAMING-SECTION-ERROR " + message)
    raise RuntimeError(message)


def main() -> None:
    district = os.environ.get("CRAFTBENCH_DISTRICT_SECTION", "")
    if district not in SECTIONS:
        fail("CRAFTBENCH_DISTRICT_SECTION must be Alpha or Beta")
    package = SECTIONS[district]
    if unreal.EditorAssetLibrary.does_asset_exist(package):
        fail("refusing to overwrite " + package)
    if not unreal.EditorLevelLibrary.new_level(package):
        fail("new_level failed " + package)
    marker_class = unreal.load_class(
        None, "/Script/ThirdPerson.DistrictSectionMarker"
    )
    if marker_class is None:
        fail("DistrictSectionMarker class missing")
    marker = unreal.EditorLevelLibrary.spawn_actor_from_class(
        marker_class, unreal.Vector(0.0, 0.0, 100.0)
    )
    if marker is None:
        fail("marker spawn failed")
    marker.set_actor_label("District%sMarker" % district)
    marker.set_editor_property("district_id", district)
    marker.tags = ["DistrictSectionMarker", "District" + district]
    if not unreal.EditorLevelLibrary.save_current_level():
        fail("section map save failed")
    observed = [
        actor
        for actor in unreal.EditorLevelLibrary.get_all_level_actors()
        if actor.get_class() == marker_class
    ]
    if len(observed) != 1 or str(observed[0].get_editor_property("district_id")) != district:
        fail("same-process marker readback mismatch count=%d" % len(observed))
    unreal.log(
        "DISTRICT-STREAMING-SECTION-SAVED district=%s markers=1 package=%s"
        % (district, package)
    )
    print(
        "DISTRICT-STREAMING-SECTION-SAVED district=%s markers=1 package=%s"
        % (district, package)
    )


main()

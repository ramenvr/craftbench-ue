"""Fresh-process, read-only proof for both retained travel maps."""

from pathlib import Path
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from epoch_travel_common import (  # noqa: E402
    NEW_MAP_VECTOR, NEW_PACKAGE, OLD_MAP_VECTOR, OLD_PACKAGE, map_vector,
    record_vector, reference_vector, source_vector,
)


def fail(message: str) -> None:
    unreal.log_error("EPOCH-TRAVEL-MAP-READBACK-FAILED: " + message)
    raise RuntimeError(message)


def main() -> None:
    before = {"maps": map_vector(), "records": record_vector(),
              "source": source_vector(), "reference": reference_vector()}
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    helper = getattr(unreal, "EpochTravelAssetAuthoring", None)
    if helper is None:
        fail("native helper unavailable")
    for package, start_stage, expected in (
            (OLD_PACKAGE, True, OLD_MAP_VECTOR),
            (NEW_PACKAGE, False, NEW_MAP_VECTOR)):
        if not levels.load_level(package):
            fail("cold load failed: " + package)
        world = unreal.get_editor_subsystem(
            unreal.UnrealEditorSubsystem).get_editor_world()
        detail = helper.inspect_map(world, start_stage) if world else None
        if type(detail) is not str or detail != expected:
            fail("cold map contract mismatch: %r" % detail)
    after = {"maps": map_vector(), "records": record_vector(),
             "source": source_vector(), "reference": reference_vector()}
    if after != before:
        fail("cold map readback changed protected hashes")
    marker = "EPOCH-TRAVEL-MAP-READBACK-PASS maps=2 displays=2 " \
        "fixtures=2 player_starts=2 playable=1 hashes_unchanged=1 " \
        "runtime_observed=0"
    unreal.log(marker)
    print(marker, flush=True)


main()

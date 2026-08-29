"""Fresh-process, read-only map contract proof."""

from __future__ import annotations

from pathlib import Path
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from run_resume_common import (  # noqa: E402
    MAP_PACKAGE, MAP_VECTOR, map_vector, reference_vector, source_vector,
)


def fail(message: str) -> None:
    unreal.log_error("RUN-RESUME-MAP-READBACK-FAILED: " + message)
    raise RuntimeError(message)


def main() -> None:
    before = {"map": map_vector(), "source": source_vector(),
              "reference": reference_vector()}
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not levels.load_level(MAP_PACKAGE):
        fail("cold load_level failed")
    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem).get_editor_world()
    helper = getattr(unreal, "LatestMarkerResumeAssetAuthoring", None)
    if world is None or helper is None:
        fail("world/helper unavailable")
    detail = helper.inspect_map(world)
    if type(detail) is not str or detail != MAP_VECTOR:
        fail("cold map contract mismatch: %r" % detail)
    if {"map": map_vector(), "source": source_vector(),
            "reference": reference_vector()} != before:
        fail("cold readback changed protected hashes")
    marker = "RUN-RESUME-MAP-READBACK-PASS map=1 subject=1 checkpoints=2 " \
        "rewards=3 fixtures=2 player_start=1 playable=1 hashes_unchanged=1"
    unreal.log(marker)
    print(marker, flush=True)


main()

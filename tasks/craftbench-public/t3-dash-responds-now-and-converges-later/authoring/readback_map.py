"""Fresh-process, read-only predicted-dash map proof."""

from pathlib import Path
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from author_map import inspect  # noqa: E402
from dash_common import MAP_DIR, MAP_FILE, MAP_PACKAGE, files_under, vector  # noqa: E402


def fail(message: str) -> None:
    unreal.log_error("PREDICTED-DASH-MAP-READBACK-ERROR: " + message)
    raise RuntimeError(message)


def main() -> None:
    before_files = files_under(MAP_DIR)
    if MAP_FILE not in before_files:
        fail("map missing")
    before = vector(before_files)
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not levels.load_level(MAP_PACKAGE):
        fail("cold load failed")
    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem).get_editor_world()
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if world is None:
        fail("cold world missing")
    details = inspect(world, actors)
    after_files = files_under(MAP_DIR)
    if after_files != before_files or vector(after_files) != before:
        fail("cold readback changed map files")
    marker = "PREDICTED-DASH-MAP-READBACK-PASS %s map_files=%d " \
        "hashes_unchanged=1 runtime_observed=0" % (details, len(before_files))
    unreal.log(marker)
    print(marker, flush=True)


main()

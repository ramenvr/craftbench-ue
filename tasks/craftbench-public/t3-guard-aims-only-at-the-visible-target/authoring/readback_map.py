"""Fresh-process exact loaded-world readback for a Guard Visible Aim map."""

import argparse
from pathlib import Path
import sys

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))

from guard_aim_common import ADMISSION_MAP, FINAL_MAP


parser = argparse.ArgumentParser()
parser.add_argument("--mode", choices=("admission", "final"), required=True)
args = parser.parse_args()
map_package = ADMISSION_MAP if args.mode == "admission" else FINAL_MAP
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if levels is None or not levels.load_level(map_package):
    raise RuntimeError("GUARD_AIM_MAP_LOAD " + map_package)
world = unreal.get_editor_subsystem(
    unreal.UnrealEditorSubsystem).get_editor_world()
detail = str(unreal.GuardVisibleAimAssetAuthoring.inspect_world(
    world, args.mode == "admission"))
if not detail.startswith("PASS "):
    raise RuntimeError("GUARD_AIM_MAP_READBACK " + detail)
unreal.log("GUARD-AIM-MAP-READBACK-PASS mode=%s detail=%s" %
           (args.mode, detail))

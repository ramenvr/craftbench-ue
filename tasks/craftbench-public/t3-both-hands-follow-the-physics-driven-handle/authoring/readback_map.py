"""Fresh-process read-only map contract validation."""

import os
from pathlib import Path
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from two_hand_authoring_common import (  # noqa: E402
    ADMISSION_MAP, FINAL_MAP, asset_vector, map_files,
    reference_state, vector, STOCK,
)


TASK_ID = "t3-both-hands-follow-the-physics-driven-handle"
MODE = os.environ.get("CRAFTBENCH_TWO_HAND_MAP_MODE", "admission").lower()
if MODE == "admission":
    MAP_FILE = ADMISSION_MAP
    MAP_PACKAGE = "/Game/Maps/%s/L_TwoHandPhysicsAdmission" % TASK_ID
    ADMISSION = True
elif MODE == "final":
    MAP_FILE = FINAL_MAP
    MAP_PACKAGE = "/Game/Maps/%s/L_TwoHandPhysics" % TASK_ID
    ADMISSION = False
else:
    raise RuntimeError("unknown CRAFTBENCH_TWO_HAND_MAP_MODE=" + MODE)


def snapshot():
    return {"map": vector(map_files(MAP_FILE)),
            "admission": asset_vector(True), "task": asset_vector(False),
            "stock": vector(STOCK), "reference": reference_state()}


before = snapshot()
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if not levels.load_level(MAP_PACKAGE):
    raise RuntimeError("TWO-HAND-MAP-COLD load_level failed")
world = unreal.get_editor_subsystem(
    unreal.UnrealEditorSubsystem).get_editor_world()
detail = str(unreal.TwoHandRigAssetAuthoring.inspect_authored_world(
    world, ADMISSION))
if not detail.startswith("PASS TWO_HAND_MAP_READBACK"):
    raise RuntimeError("TWO-HAND-MAP-COLD " + detail)
after = snapshot()
if after != before:
    raise RuntimeError("TWO-HAND-MAP-COLD protected hashes changed")
marker = ("TWO-HAND-MAP-COLD-PASS mode=%s hash_files=%d "
          "authored_contract=1 runtime_observed=0 hashes_unchanged=1 %s" %
          (MODE, len(before["map"]), detail))
unreal.log(marker)
print(marker)

"""Fresh-process exact readback for either Guard Aim asset namespace."""

import argparse
from pathlib import Path
import sys
import unreal

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from guard_aim_common import ADMISSION_ANIM, ADMISSION_DIR, FINAL_ANIM, FINAL_DIR


parser = argparse.ArgumentParser()
parser.add_argument("--mode", choices=("admission", "final"), required=True)
args = parser.parse_args()
path = ADMISSION_ANIM if args.mode == "admission" else FINAL_ANIM
directory = ADMISSION_DIR if args.mode == "admission" else FINAL_DIR
expected = {path}
observed = {str(value).split(".", 1)[0]
            for value in unreal.EditorAssetLibrary.list_assets(
                directory, recursive=True, include_folder=False)}
asset = unreal.EditorAssetLibrary.load_asset(path)
helper = getattr(unreal, "GuardVisibleAimVerifierLibrary", None)
if observed != expected or asset is None or helper is None:
    raise RuntimeError("GUARD_AIM_ASSET_INVENTORY expected=%r observed=%r" %
                       (sorted(expected), sorted(observed)))
detail = str(helper.inspect_anim_blueprint(asset, args.mode == "admission"))
if '"probe_ok":true' not in detail:
    raise RuntimeError("GUARD_AIM_ASSET_READBACK " + detail)
unreal.log("GUARD-AIM-ASSET-READBACK-PASS mode=%s inventory=1 detail=%s" %
           (args.mode, detail))

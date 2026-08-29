"""Fresh-process exact structural readback for one Alert Stride asset set."""

import argparse
from pathlib import Path
import sys

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))

from alert_stride_common import (
    ADMISSION_INTERFACE, ADMISSION_ROOT, FINAL_INTERFACE, FINAL_ROOT,
    all_packages,
)


parser = argparse.ArgumentParser()
parser.add_argument(
    "--mode", choices=("admission", "final", "reference"), required=True)
args = parser.parse_args()
is_admission = args.mode == "admission"
is_complete = args.mode in ("admission", "reference")
root = ADMISSION_ROOT if is_admission else FINAL_ROOT
interface = ADMISSION_INTERFACE if is_admission else FINAL_INTERFACE
expected = set(all_packages(root, interface))
observed = {str(value).split(".", 1)[0]
            for value in unreal.EditorAssetLibrary.list_assets(
                root, recursive=True, include_folder=False)}
helper = getattr(unreal, "AlertStrideVerifierLibrary", None)
if unreal.EditorAssetLibrary.does_asset_exist(interface):
    observed.add(interface)
if observed != expected or helper is None \
        or not unreal.EditorAssetLibrary.does_asset_exist(interface):
    raise RuntimeError("ALERT_STRIDE_ASSET_INVENTORY expected=%r observed=%r" %
                       (sorted(expected), sorted(observed)))
facts = str(helper.inspect_asset_set(
    root, interface, is_complete))
if '"probe_ok":true' not in facts:
    raise RuntimeError("ALERT_STRIDE_ASSET_READBACK " + facts)
unreal.log("ALERT-STRIDE-ASSET-READBACK-PASS mode=%s inventory=5 editable=4 facts=%s" %
           (args.mode, facts))

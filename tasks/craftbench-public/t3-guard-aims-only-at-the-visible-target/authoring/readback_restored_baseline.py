"""Cold-read the byte-restored incomplete Guard Visible Aim baseline."""

import os
from pathlib import Path
import sys

import unreal

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import reference_contract as contract  # noqa: E402


expected_hash = os.environ.get("CRAFTBENCH_GUARD_AIM_BASELINE_HASH", "")
if not expected_hash:
    raise RuntimeError("GUARD-AIM-BASELINE-COLD-FAILED missing hash lock")
before = contract.exact_live_vector()
if before != {contract.FINAL_ASSET.name: expected_hash}:
    raise RuntimeError("GUARD-AIM-BASELINE-COLD-FAILED hash mismatch")
asset = unreal.EditorAssetLibrary.load_asset(
    "/Game/Tasks/t3-guard-aims-only-at-the-visible-target/ABP_GuardVisibleAim")
helper = getattr(unreal, "GuardVisibleAimVerifierLibrary", None)
if asset is None or helper is None:
    raise RuntimeError("GUARD-AIM-BASELINE-COLD-FAILED asset/helper missing")
detail = str(helper.inspect_anim_blueprint(asset, False))
if '"probe_ok":true' not in detail or '"expect_aim":false' not in detail:
    raise RuntimeError("GUARD-AIM-BASELINE-COLD-FAILED " + detail)
if contract.exact_live_vector() != before:
    raise RuntimeError("GUARD-AIM-BASELINE-COLD-FAILED bytes changed")
marker = "GUARD-AIM-BASELINE-COLD-PASS assets=1 hashes_unchanged=1 " + detail
unreal.log(marker)
print(marker, flush=True)

"""Fresh-process, read-only Door Blueprint structural readback."""

import os
from pathlib import Path
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from door_common import (  # noqa: E402
    ADMISSION_ASSET, ADMISSION_VECTOR, BASELINE_VECTOR, FINAL_ASSET,
    optional_vector,
)


def fail(message: str) -> None:
    unreal.log_error("REPLICATED-DOOR-ASSET-READBACK-ERROR: " + message)
    raise RuntimeError(message)


def main() -> None:
    mode = os.environ.get("CRAFTBENCH_DOOR_ASSET_MODE", "")
    if mode not in ("baseline", "admission"):
        fail("mode must be baseline or admission")
    admission = mode == "admission"
    expected = ADMISSION_VECTOR if admission else BASELINE_VECTOR
    target = ADMISSION_ASSET if admission else FINAL_ASSET
    before = optional_vector((FINAL_ASSET, ADMISSION_ASSET))
    if before[str(target)] is None:
        fail("target asset missing")
    helper = getattr(unreal, "ReplicatedDoorAssetAuthoring", None)
    detail = helper.inspect_door_blueprint(admission, admission) if helper else None
    if type(detail) is not str or detail != expected:
        fail("cold native vector mismatch: %r" % detail)
    after = optional_vector((FINAL_ASSET, ADMISSION_ASSET))
    if after != before:
        fail("cold readback changed asset hashes")
    marker = "REPLICATED-DOOR-ASSET-READBACK-PASS mode=%s assets=1 " \
        "hashes_unchanged=1 solved=%d" % (mode, 1 if admission else 0)
    unreal.log(marker)
    print(marker, flush=True)


main()

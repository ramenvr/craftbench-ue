"""Create only the isolated solved admission Door Blueprint."""

from pathlib import Path
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from door_common import (  # noqa: E402
    ADMISSION_ASSET, ADMISSION_MAP, ADMISSION_VECTOR, FINAL_ASSET, FINAL_MAP,
    REFERENCE_ASSET, assert_absent, exact_files, optional_vector, regular_vector,
)


def fail(message: str) -> None:
    unreal.log_error("REPLICATED-DOOR-ADMISSION-ASSET-ERROR: " + message)
    raise RuntimeError(message)


def main() -> None:
    try:
        assert_absent(ADMISSION_ASSET, ADMISSION_MAP, FINAL_MAP, REFERENCE_ASSET)
        protected_before = optional_vector((FINAL_ASSET, FINAL_MAP, REFERENCE_ASSET))
        helper = getattr(unreal, "ReplicatedDoorAssetAuthoring", None)
        detail = helper.create_admission_door_blueprint() if helper else None
        if type(detail) is not str or detail != ADMISSION_VECTOR:
            fail("native admission vector mismatch: %r" % detail)
        files = exact_files(ADMISSION_ASSET.parent)
        if files != (ADMISSION_ASSET,):
            fail("admission inventory mismatch: %r" % ([str(x) for x in files],))
        hashes = regular_vector((ADMISSION_ASSET,))
        if optional_vector((FINAL_ASSET, FINAL_MAP, REFERENCE_ASSET)) \
                != protected_before:
            fail("protected final/reference state changed")
        assert_absent(ADMISSION_MAP)
        marker = "REPLICATED-DOOR-ADMISSION-ASSET-SAVED assets=1 hash=%s" % (
            hashes[str(ADMISSION_ASSET)]["sha256"])
        unreal.log(marker)
        print(marker, flush=True)
    except Exception as exc:
        if "ADMISSION-ASSET-ERROR" not in str(exc):
            unreal.log_error("REPLICATED-DOOR-ADMISSION-ASSET-ERROR: %s" % exc)
        raise


main()

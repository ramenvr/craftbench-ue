"""Create only the editable empty Door Blueprint baseline."""

from pathlib import Path
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from door_common import (  # noqa: E402
    ADMISSION_ASSET, ADMISSION_MAP, BASELINE_VECTOR, FINAL_ASSET, FINAL_MAP,
    REFERENCE_ASSET, assert_absent, exact_files, regular_vector,
)


def fail(message: str) -> None:
    unreal.log_error("REPLICATED-DOOR-BASELINE-AUTHOR-ERROR: " + message)
    raise RuntimeError(message)


def main() -> None:
    try:
        assert_absent(FINAL_ASSET, FINAL_MAP, ADMISSION_ASSET, ADMISSION_MAP,
                      REFERENCE_ASSET)
        helper = getattr(unreal, "ReplicatedDoorAssetAuthoring", None)
        detail = helper.create_baseline_door_blueprint() if helper else None
        if type(detail) is not str or detail != BASELINE_VECTOR:
            fail("native baseline vector mismatch: %r" % detail)
        files = exact_files(FINAL_ASSET.parent)
        if files != (FINAL_ASSET,):
            fail("baseline inventory mismatch: %r" % ([str(x) for x in files],))
        hashes = regular_vector((FINAL_ASSET,))
        assert_absent(FINAL_MAP, ADMISSION_ASSET, ADMISSION_MAP, REFERENCE_ASSET)
        marker = "REPLICATED-DOOR-BASELINE-ASSET-SAVED assets=1 hash=%s" % (
            hashes[str(FINAL_ASSET)]["sha256"])
        unreal.log(marker)
        print(marker, flush=True)
    except Exception as exc:
        if not str(exc).startswith("native baseline vector"):
            unreal.log_error("REPLICATED-DOOR-BASELINE-AUTHOR-ERROR: %s" % exc)
        raise


main()

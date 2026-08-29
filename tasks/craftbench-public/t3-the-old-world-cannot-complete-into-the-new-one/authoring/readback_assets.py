"""Fresh-process, read-only proof for the two protected records."""

from pathlib import Path
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from epoch_travel_common import (  # noqa: E402
    NEW_MAP, OLD_MAP, RECORD_VECTOR, record_vector, reference_vector,
    source_vector,
)


def fail(message: str) -> None:
    unreal.log_error("EPOCH-TRAVEL-ASSET-READBACK-FAILED: " + message)
    raise RuntimeError(message)


def main() -> None:
    before = {"records": record_vector(), "source": source_vector(),
              "reference": reference_vector()}
    if OLD_MAP.exists() or NEW_MAP.exists():
        fail("maps must remain absent during record readback")
    helper = getattr(unreal, "EpochTravelAssetAuthoring", None)
    detail = helper.inspect_records() if helper else None
    if type(detail) is not str or detail != RECORD_VECTOR:
        fail("cold record contract mismatch: %r" % detail)
    if {"records": record_vector(), "source": source_vector(),
            "reference": reference_vector()} != before:
        fail("cold readback changed protected hashes")
    marker = "EPOCH-TRAVEL-ASSET-READBACK-PASS records=2 hashes_unchanged=1"
    unreal.log(marker)
    print(marker, flush=True)


main()

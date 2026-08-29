"""Fresh-process, read-only structural proof of the solved Door reference."""

from pathlib import Path
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from door_common import (  # noqa: E402
    ADMISSION_ASSET, ADMISSION_MAP, FINAL_ASSET, FINAL_MAP,
    FINAL_SOLVED_VECTOR, REFERENCE_ASSET, optional_vector,
)


def fail(message: str) -> None:
    unreal.log_error("REPLICATED-DOOR-REFERENCE-READBACK-ERROR: " + message)
    raise RuntimeError(message)


def main() -> None:
    before = optional_vector((FINAL_ASSET, ADMISSION_ASSET, FINAL_MAP,
                              ADMISSION_MAP, REFERENCE_ASSET))
    if before[str(FINAL_ASSET)] is None:
        fail("live solved asset missing")
    if before[str(REFERENCE_ASSET)] is not None:
        fail("reference must remain absent until harvest")
    helper = getattr(unreal, "ReplicatedDoorAssetAuthoring", None)
    detail = helper.inspect_door_blueprint(False, True) if helper else None
    if type(detail) is not str or detail != FINAL_SOLVED_VECTOR:
        fail("cold solved vector mismatch: %r" % detail)
    after = optional_vector((FINAL_ASSET, ADMISSION_ASSET, FINAL_MAP,
                             ADMISSION_MAP, REFERENCE_ASSET))
    if after != before:
        fail("cold solved readback changed protected hashes")
    marker = "REPLICATED-DOOR-REFERENCE-READBACK-PASS solved=1 rpc=1 " \
        "repnotify=1 hashes_unchanged=1"
    unreal.log(marker)
    print(marker, flush=True)


main()

"""Build the solved Door graph in the live baseline package only."""

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
    unreal.log_error("REPLICATED-DOOR-REFERENCE-AUTHOR-ERROR: " + message)
    raise RuntimeError(message)


def main() -> None:
    before = optional_vector((FINAL_ASSET, ADMISSION_ASSET, FINAL_MAP,
                              ADMISSION_MAP, REFERENCE_ASSET))
    if before[str(FINAL_ASSET)] is None:
        fail("live baseline missing")
    if before[str(ADMISSION_ASSET)] is None or before[str(FINAL_MAP)] is None \
            or before[str(ADMISSION_MAP)] is None:
        fail("protected authored input missing")
    if before[str(REFERENCE_ASSET)] is not None:
        fail("reference must be absent")
    helper = getattr(unreal, "ReplicatedDoorAssetAuthoring", None)
    detail = helper.build_reference_door_graph() if helper else None
    if type(detail) is not str or detail != FINAL_SOLVED_VECTOR:
        fail("native solved vector mismatch: %r" % detail)
    after = optional_vector((FINAL_ASSET, ADMISSION_ASSET, FINAL_MAP,
                             ADMISSION_MAP, REFERENCE_ASSET))
    if after[str(FINAL_ASSET)] == before[str(FINAL_ASSET)]:
        fail("reference author left baseline bytes unchanged")
    for protected in (ADMISSION_ASSET, FINAL_MAP, ADMISSION_MAP,
                      REFERENCE_ASSET):
        if after[str(protected)] != before[str(protected)]:
            fail("protected input changed: %s" % protected)
    marker = "REPLICATED-DOOR-REFERENCE-AUTHOR-PASS solved=1 rpc=1 " \
        "repnotify=1 protected_unchanged=1"
    unreal.log(marker)
    print(marker, flush=True)


main()

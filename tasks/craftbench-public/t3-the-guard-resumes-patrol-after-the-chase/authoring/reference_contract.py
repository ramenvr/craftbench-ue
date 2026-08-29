"""Byte-level contracts for the guard reference closure."""

from __future__ import annotations

import os
from pathlib import Path

from guard_authoring_common import (
    ADMISSION_MAP,
    FINAL_DIR,
    FINAL_MAP,
    REFERENCE,
    exact_admission_asset_vector,
    exact_final_asset_vector,
    require_plain,
    sha256,
    stock_vector,
    vector,
)


TASK_ID = "t3-the-guard-resumes-patrol-after-the-chase"
REFERENCE_ASSET_DIR = (
    REFERENCE / "Content" / "Tasks" / TASK_ID
)
BASELINE_HASHES = {
    "BB_GuardPatrolChase.uasset":
        "c614a865f577e0dfde2187ef133a0340ef9996260787beafdee39bdd1ee3d774",
    "BT_GuardPatrolChase.uasset":
        "2732258c0a74de60b47184ef217281b24d9bae82378e813be1807258a7dc12e6",
}
FINAL_MAP_SHA256 = (
    "bf2fd8d3d6eaa8a6ce8492f7ab dfe380ea234b8c0636cb3aee3fdd7cb11171e2"
    .replace(" ", "")
)


class ContractError(RuntimeError):
    """A protected package or filesystem contract was violated."""


def baseline_vector() -> dict[str, str]:
    observed = exact_final_asset_vector()
    by_name = {Path(key).name: value for key, value in observed.items()}
    if by_name != BASELINE_HASHES:
        raise ContractError("baseline hashes mismatch: %r" % by_name)
    return observed


def immutable_vector() -> dict[str, object]:
    require_plain(ADMISSION_MAP)
    require_plain(FINAL_MAP)
    final_hash = sha256(FINAL_MAP)
    if final_hash != FINAL_MAP_SHA256:
        raise ContractError(
            "final map hash mismatch expected=%s actual=%s" %
            (FINAL_MAP_SHA256, final_hash))
    return {
        "admission_assets": exact_admission_asset_vector(),
        "admission_map": sha256(ADMISSION_MAP),
        "final_map": final_hash,
        "stock": stock_vector(),
    }


def require_reference_absent() -> None:
    if os.path.lexists(REFERENCE):
        raise ContractError("reference output already exists: %s" % REFERENCE)


def reference_vector() -> dict[str, str]:
    expected = {
        REFERENCE_ASSET_DIR / "BB_GuardPatrolChase.uasset",
        REFERENCE_ASSET_DIR / "BT_GuardPatrolChase.uasset",
    }
    if not REFERENCE_ASSET_DIR.is_dir():
        raise ContractError("reference asset directory missing")
    observed = {item for item in REFERENCE_ASSET_DIR.iterdir()}
    if observed != expected:
        raise ContractError(
            "reference inventory mismatch: %r" %
            sorted(str(item) for item in observed))
    return vector(tuple(sorted(expected)))


def require_live_namespace_absent() -> None:
    if os.path.lexists(FINAL_DIR):
        raise ContractError("live task namespace must be absent: %s" % FINAL_DIR)

"""Fail-closed filesystem contract for the Guard Visible Aim reference."""

from __future__ import annotations

import os
from pathlib import Path

from guard_aim_common import (
    ADMISSION_ANIM, ADMISSION_MAP, FINAL_ANIM, FINAL_DIR, FINAL_MAP,
    REFERENCE, disk, sha256, snapshot,
)


FINAL_DISK_DIR = disk(FINAL_DIR, "")
FINAL_ASSET = disk(FINAL_ANIM, ".uasset")
REFERENCE_DIR = REFERENCE.parent


def exact_live_vector() -> dict[str, str]:
    expected = {FINAL_ASSET.name}
    if not FINAL_DISK_DIR.is_dir() or FINAL_DISK_DIR.is_symlink():
        raise RuntimeError("live final namespace missing or linked")
    observed = {path.name for path in FINAL_DISK_DIR.iterdir()
                if path.is_file()}
    if observed != expected or any(not path.is_file()
                                   for path in FINAL_DISK_DIR.iterdir()):
        raise RuntimeError("live final inventory mismatch: %r" % sorted(observed))
    return {FINAL_ASSET.name: sha256(FINAL_ASSET)}


def immutable_vector() -> dict[str, dict]:
    return {
        "admission_anim": snapshot(disk(ADMISSION_ANIM, ".uasset")),
        "admission_map": snapshot(disk(ADMISSION_MAP, ".umap")),
        "final_map": snapshot(disk(FINAL_MAP, ".umap")),
    }


def require_reference_absent() -> None:
    if os.path.lexists(REFERENCE) or os.path.lexists(REFERENCE_DIR):
        raise RuntimeError("reference destination must be absent")

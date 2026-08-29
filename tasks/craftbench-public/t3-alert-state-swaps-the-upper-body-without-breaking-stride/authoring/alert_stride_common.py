"""Exact task paths plus no-follow byte snapshots for Alert Stride."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


TASK_ID = "t3-alert-state-swaps-the-upper-body-without-breaking-stride"
REPO = Path(__file__).resolve().parents[4]
PROJECT = REPO / "UE-projects" / "ThirdPerson" / "ThirdPerson.uproject"
CONTENT = PROJECT.parent / "Content"
FINAL_ROOT = "/Game/Tasks/" + TASK_ID
ADMISSION_ROOT = "/Game/__CraftBenchAdmission/" + TASK_ID + "/Assets"
FINAL_MAP = "/Game/Maps/%s/L_AlertStride" % TASK_ID
ADMISSION_MAP = "/Game/__CraftBenchAdmission/%s/L_AlertStrideAdmission" % TASK_ID
FINAL_INTERFACE = "/Game/Maps/%s/ALI_AlertStrideUpperBody" % TASK_ID
ADMISSION_INTERFACE = ADMISSION_ROOT + "/ALI_AlertStrideUpperBody"
ASSET_NAMES = (
    "ABP_AlertStrideHost",
    "ABP_AlertStrideCalmLayer",
    "ABP_AlertStrideAlertLayer",
    "ST_AlertStride",
)
REFERENCE = (REPO / "tasks" / "bp" / TASK_ID / "reference" / "Content"
             / "Tasks" / TASK_ID)


def packages(root: str) -> tuple[str, ...]:
    return tuple(root + "/" + name for name in ASSET_NAMES)


def all_packages(root: str, interface: str) -> tuple[str, ...]:
    return (interface,) + packages(root)


def disk(package: str, suffix: str) -> Path:
    return CONTENT / (package.removeprefix("/Game/") + suffix)


def is_link(path: Path) -> bool:
    junction = getattr(path, "is_junction", None)
    return path.is_symlink() or bool(junction and junction())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def snapshot(path: Path) -> dict:
    if is_link(path):
        raise RuntimeError("protected path is link/junction: %s" % path)
    if not path.exists():
        return {"kind": "absent"}
    if path.is_file():
        return {"kind": "file", "sha256": sha256(path)}
    files = {}
    for root, dirs, names in os.walk(path, followlinks=False):
        base = Path(root)
        for name in dirs:
            if is_link(base / name):
                raise RuntimeError("protected tree link: %s" % (base / name))
        for name in names:
            child = base / name
            if is_link(child) or not child.is_file():
                raise RuntimeError("protected tree non-file: %s" % child)
            files[str(child.relative_to(path)).replace("\\", "/")] = sha256(child)
    return {"kind": "directory", "files": files}


def signature(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest().upper()

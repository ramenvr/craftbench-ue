"""Fail-closed author/readback/harvest/restore closure for row 11."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
from typing import Any

from two_hand_authoring_common import (
    ADMISSION_ASSETS,
    ADMISSION_MAP,
    FINAL_MAP,
    PROJECT,
    REFERENCE_DIR,
    REPO,
    STOCK,
    TASK_ASSETS,
    TASK_DIR,
    asset_vector,
    map_files,
    sha256,
    vector,
)

#: Engine root. Override with CB_UE_ROOT; defaults to Epic's standard install.
_UE_ROOT = Path(os.environ.get("CB_UE_ROOT", r"C:\Program Files\Epic Games\UE_5.8"))


HERE = Path(__file__).resolve().parent
AUTHOR_SCRIPT = HERE / "author_reference.py"
READBACK_SCRIPT = HERE / "readback_assets.py"
BASELINE_HASHES = {
    TASK_ASSETS[0]: "64CD3E7EC0ED744F0D8FFA3D6BA64FA8A4F047CC900E8F0E2D79CAADBA180C1B",
    TASK_ASSETS[1]: "F260F9D4A823C58A4F6645772E8A193CA58AB7567EC1A1961626E4918A44D537",
}
REFERENCE_PAYLOAD_DIR = REFERENCE_DIR / "Content" / "Tasks" / TASK_DIR.name
REFERENCE_FILES = tuple(REFERENCE_PAYLOAD_DIR / path.name for path in TASK_ASSETS)
AUTHOR_MARKER = "TWO-HAND-REFERENCE-AUTHOR-PASS"
REFERENCE_MARKER = "TWO-HAND-ASSET-COLD-PASS mode=reference"
BASELINE_MARKER = "TWO-HAND-ASSET-COLD-PASS mode=baseline"
FORBIDDEN = (
    "LogPython: Error",
    "Python script executed with errors",
    "Ensure condition failed",
    "Assertion failed",
    "Fatal error",
    "LowLevelFatalError",
    "TWO-HAND-REFERENCE-AUTHOR-FAILED",
    "TWO-HAND-READBACK",
)


class ClosureError(RuntimeError):
    """A closure invariant failed."""


def is_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    attributes = getattr(path.lstat(), "st_file_attributes", 0)
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def require_plain_existing(path: Path) -> None:
    current = Path(os.path.abspath(os.fspath(path)))
    if not current.exists():
        raise ClosureError("required path missing: %s" % current)
    while True:
        if is_reparse(current):
            raise ClosureError("link/reparse rejected: %s" % current)
        if current.parent == current:
            return
        current = current.parent


def require_plain_output(path: Path) -> None:
    current = Path(os.path.abspath(os.fspath(path)))
    while not current.exists():
        if current.parent == current:
            raise ClosureError("no existing output ancestor: %s" % path)
        current = current.parent
    require_plain_existing(current)


def facts(path: Path) -> dict[str, Any]:
    require_plain_existing(path)
    if not path.is_file():
        raise ClosureError("required regular file missing: %s" % path)
    return {"path": str(path), "size": path.stat().st_size,
            "sha256": sha256(path)}


def write_json(path: Path, value: object) -> None:
    temporary = path.with_name(path.name + ".tmp")
    if os.path.lexists(temporary):
        raise ClosureError("stale JSON temporary: %s" % temporary)
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8")
    os.replace(temporary, path)


def copy_verified(source: Path, destination: Path, expected_hash: str) -> None:
    if sha256(source) != expected_hash:
        raise ClosureError("copy source hash mismatch: %s" % source)
    require_plain_existing(source)
    if destination.exists() or os.path.lexists(destination):
        raise ClosureError("copy destination exists: %s" % destination)
    require_plain_output(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    require_plain_output(destination)
    temporary = destination.with_name(destination.name + ".copy-tmp")
    if os.path.lexists(temporary):
        raise ClosureError("stale copy temporary: %s" % temporary)
    shutil.copy2(source, temporary)
    if is_reparse(temporary) or sha256(temporary) != expected_hash:
        raise ClosureError("temporary copy verification failed: %s" % temporary)
    os.replace(temporary, destination)
    if sha256(destination) != expected_hash:
        raise ClosureError("installed copy verification failed: %s" % destination)


def move_exact(source: Path, destination: Path) -> None:
    require_plain_existing(source)
    if not source.is_file():
        raise ClosureError("move source is not a file: %s" % source)
    if destination.exists() or os.path.lexists(destination):
        raise ClosureError("move destination exists: %s" % destination)
    require_plain_output(destination)
    if os.path.splitdrive(os.path.abspath(source))[0].lower() != \
            os.path.splitdrive(os.path.abspath(destination))[0].lower():
        raise ClosureError("atomic move requires one volume")
    destination.parent.mkdir(parents=True, exist_ok=True)
    source.replace(destination)


def immutable_vector() -> dict[str, str]:
    paths = tuple(ADMISSION_ASSETS) + tuple(STOCK) + \
        map_files(ADMISSION_MAP) + map_files(FINAL_MAP)
    return vector(paths)


def exact_baseline_vector() -> dict[str, str]:
    actual = asset_vector(False)
    expected = {
        str(path.relative_to(REPO)).replace("\\", "/"): digest
        for path, digest in BASELINE_HASHES.items()
    }
    if actual != expected:
        raise ClosureError(
            "live baseline vector mismatch expected=%r actual=%r" %
            (expected, actual))
    return actual


def preflight(editor: Path, output: Path) -> dict[str, Any]:
    for required in (editor, PROJECT, AUTHOR_SCRIPT, READBACK_SCRIPT):
        if not required.is_file():
            raise ClosureError("required closure input missing: %s" % required)
        require_plain_existing(required)
    require_plain_output(output)
    if output.exists() or os.path.lexists(output):
        raise ClosureError("fresh output exists: %s" % output)
    if REFERENCE_DIR.exists() or os.path.lexists(REFERENCE_DIR):
        raise ClosureError("reference must be absent: %s" % REFERENCE_DIR)
    if os.path.splitdrive(os.path.abspath(output))[0].lower() != \
            os.path.splitdrive(os.path.abspath(TASK_DIR))[0].lower():
        raise ClosureError("output and live baseline must share a volume")
    return {"baseline": exact_baseline_vector(),
            "immutable": immutable_vector(), "reference_absent": True}


def kill_exact_tree(process: subprocess.Popen[Any]) -> dict[str, Any]:
    completed = subprocess.run(
        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
        capture_output=True, text=True, check=False, timeout=30)
    try:
        process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=30)
    return {"pid": process.pid, "method": "taskkill-exact-tree",
            "taskkill_exit": completed.returncode,
            "output": (completed.stdout + completed.stderr).strip(),
            "exit_code": process.returncode}


def run_editor(editor: Path, output: Path, label: str, script: Path,
               marker: str, timeout_seconds: int,
               environment: dict[str, str] | None = None) -> dict[str, Any]:
    logs = output / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    abslog = logs / (label + ".log")
    stdout = logs / (label + ".stdout.log")
    if os.path.lexists(abslog) or os.path.lexists(stdout):
        raise ClosureError("fresh log collision: %s" % label)
    command = [
        str(editor), str(PROJECT), "-run=pythonscript",
        "-script=%s" % script, "-unattended", "-nopause", "-nop4",
        "-nosplash", "-nosound", "-RenderOffscreen", "-stdout",
        "-FullStdOutLogOutput", "-abslog=%s" % abslog,
    ]
    child_environment = os.environ.copy()
    child_environment.update(environment or {})
    with stdout.open("wb") as stream:
        process = subprocess.Popen(
            command, cwd=REPO, stdout=stream, stderr=subprocess.STDOUT,
            env=child_environment)
        try:
            exit_code = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            write_json(output / (label + "-watchdog.json"),
                       kill_exact_tree(process))
            raise ClosureError("%s exceeded watchdog" % label) from exc
    if exit_code != 0:
        raise ClosureError("%s editor exit=%d" % (label, exit_code))
    if not abslog.is_file():
        raise ClosureError("%s abslog missing" % label)
    texts = {
        "abslog": abslog.read_text(encoding="utf-8", errors="replace"),
        "stdout": stdout.read_text(encoding="utf-8", errors="replace"),
    }
    for stream_name, text in texts.items():
        if marker not in text:
            raise ClosureError("%s marker absent in %s" % (label, stream_name))
        for token in FORBIDDEN:
            if token.lower() in text.lower():
                raise ClosureError("%s %s contains %s" %
                                   (label, stream_name, token))
        if re.search(r"Log[A-Za-z0-9_]+:\s*Error:", text):
            raise ClosureError("%s %s contains engine/task error" %
                               (label, stream_name))
    return {"command": command, "exit_code": exit_code,
            "abslog": facts(abslog), "stdout": facts(stdout)}


def restore_from_vault(vault: Path, output: Path) -> None:
    for live in TASK_ASSETS:
        baseline_hash = BASELINE_HASHES[live]
        source = vault / live.name
        if live.is_file() and sha256(live) != baseline_hash:
            move_exact(
                live,
                output / "rollback" / "partial-live" / live.name)
        if not live.is_file():
            copy_verified(source, live, baseline_hash)
    exact_baseline_vector()


def rollback(vault: Path, output: Path) -> list[str]:
    errors: list[str] = []
    try:
        if REFERENCE_DIR.exists() or os.path.lexists(REFERENCE_DIR):
            destination = output / "rollback" / "partial-reference"
            if destination.exists() or os.path.lexists(destination):
                raise ClosureError("partial-reference quarantine exists")
            destination.parent.mkdir(parents=True, exist_ok=True)
            REFERENCE_DIR.replace(destination)
    except Exception as exc:  # noqa: BLE001
        errors.append("reference quarantine: %s" % exc)
    try:
        if vault.is_dir():
            restore_from_vault(vault, output)
    except Exception as exc:  # noqa: BLE001
        errors.append("baseline restore: %s" % exc)
    return errors


def close(editor: Path, output: Path, timeout_seconds: int) -> None:
    entry = preflight(editor, output)
    output.mkdir(parents=True)
    manifest: dict[str, Any] = {
        "schema": 1, "task": TASK_DIR.name, "status": "running",
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "entry": entry, "steps": {},
    }
    vault = output / "baseline-vault"
    reference_vault = output / "reference-vault"
    try:
        for live in TASK_ASSETS:
            copy_verified(live, vault / live.name, BASELINE_HASHES[live])
        manifest["baseline_vault"] = [facts(vault / path.name)
                                      for path in TASK_ASSETS]

        # The native graph helper is intentionally fresh-only.  Move the exact
        # baseline pair out before the UE boot; rollback restores from the
        # independent vault if creation stops after either package.
        for live in TASK_ASSETS:
            move_exact(
                live,
                output / "evidence" / "baseline-live" / live.name)
        if tuple(TASK_DIR.glob("*.uasset")):
            raise ClosureError("live task namespace is not empty before author")

        manifest["steps"]["01-author-reference"] = run_editor(
            editor, output, "01-author-reference", AUTHOR_SCRIPT,
            AUTHOR_MARKER, timeout_seconds)
        authored = asset_vector(False)
        reference_hashes = {
            path: authored[str(path.relative_to(REPO)).replace("\\", "/")]
            for path in TASK_ASSETS
        }
        if any(reference_hashes[path] == BASELINE_HASHES[path]
               for path in TASK_ASSETS):
            raise ClosureError("reference author left a baseline file unchanged")
        if immutable_vector() != entry["immutable"]:
            raise ClosureError("reference author changed immutable packages")
        manifest["authored"] = authored

        manifest["steps"]["02-cold-reference"] = run_editor(
            editor, output, "02-cold-reference", READBACK_SCRIPT,
            REFERENCE_MARKER, timeout_seconds,
            {"CRAFTBENCH_TWO_HAND_READBACK_MODE": "reference"})
        if asset_vector(False) != authored or immutable_vector() != entry["immutable"]:
            raise ClosureError("cold reference readback changed protected bytes")
        for live in TASK_ASSETS:
            copy_verified(live, reference_vault / live.name,
                          reference_hashes[live])

        for live in TASK_ASSETS:
            move_exact(
                live,
                output / "evidence" / "reference-live" / live.name)
            copy_verified(vault / live.name, live, BASELINE_HASHES[live])
        restored = exact_baseline_vector()
        if immutable_vector() != entry["immutable"]:
            raise ClosureError("baseline restore changed immutable packages")
        manifest["restored"] = restored
        manifest["steps"]["03-cold-baseline"] = run_editor(
            editor, output, "03-cold-baseline", READBACK_SCRIPT,
            BASELINE_MARKER, timeout_seconds,
            {"CRAFTBENCH_TWO_HAND_READBACK_MODE": "baseline"})
        if exact_baseline_vector() != restored or \
                immutable_vector() != entry["immutable"]:
            raise ClosureError("cold baseline readback changed protected bytes")

        for live, reference_file in zip(TASK_ASSETS, REFERENCE_FILES):
            copy_verified(reference_vault / live.name, reference_file,
                          reference_hashes[live])
        reference_facts = [facts(path) for path in REFERENCE_FILES]
        actual_reference_files = {
            path for path in REFERENCE_DIR.rglob("*") if path.is_file()
        }
        if actual_reference_files != set(REFERENCE_FILES):
            raise ClosureError("reference inventory is not exact two")
        exact_baseline_vector()
        if immutable_vector() != entry["immutable"]:
            raise ClosureError("final immutable vector changed")
        manifest["reference"] = reference_facts
        manifest["status"] = "pass"
        manifest["completed_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(output / "closure.json", manifest)
        print(
            "TWO-HAND-REFERENCE-CLOSURE-PASS assets=2 live_restored=1 "
            "cold_reference=1 cold_baseline=1 immutable_unchanged=1 output=%s" %
            output,
            flush=True)
    except Exception as exc:
        manifest["status"] = "fail"
        manifest["error"] = str(exc)
        manifest["rollback_errors"] = rollback(vault, output)
        manifest["completed_utc"] = datetime.now(timezone.utc).isoformat()
        try:
            write_json(output / "closure.json", manifest)
        except Exception as manifest_error:  # noqa: BLE001
            manifest["rollback_errors"].append(
                "failure manifest: %s" % manifest_error)
        detail = str(exc)
        if manifest["rollback_errors"]:
            detail += "; rollback incomplete: " + "; ".join(
                manifest["rollback_errors"])
        raise ClosureError(detail) from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ue-root", type=Path, default=_UE_ROOT)
    parser.add_argument("--watchdog-seconds", type=int, default=720)
    parser.add_argument("--preflight-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.watchdog_seconds < 60:
        print("TWO-HAND-REFERENCE-CLOSURE-ERROR watchdog must be >=60",
              file=sys.stderr)
        return 1
    editor = args.ue_root / "Engine" / "Binaries" / "Win64" / \
        "UnrealEditor-Cmd.exe"
    output = Path(os.path.abspath(args.output))
    try:
        entry = preflight(editor, output)
        if args.preflight_only:
            print(
                "TWO-HAND-REFERENCE-PREFLIGHT-PASS baseline=2 immutable=%d "
                "reference_absent=1 output_absent=1 no_reparse=1" %
                len(entry["immutable"]))
            return 0
        close(editor, output, args.watchdog_seconds)
        return 0
    except ClosureError as exc:
        print("TWO-HAND-REFERENCE-CLOSURE-ERROR %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

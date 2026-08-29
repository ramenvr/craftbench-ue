"""Fail-closed author/readback/harvest/baseline closure for district loader."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any

import reference_contract as contract

#: Engine root. Override with CB_UE_ROOT; defaults to Epic's standard install.
_UE_ROOT = Path(os.environ.get("CB_UE_ROOT", r"C:\Program Files\Epic Games\UE_5.8"))


PROJECT = contract.PROJECT_ROOT / "ThirdPerson.uproject"
AUTHOR_SCRIPT = contract.HERE / "author_reference.py"
REFERENCE_READBACK = contract.HERE / "readback_reference.py"
BASELINE_READBACK = contract.HERE / "readback_baseline.py"
RELATIVE_ASSET = (
    Path("Content") / "Tasks" / contract.TASK_ID /
    "BP_DistrictStreamLoader.uasset")
AUTHOR_MARKER = "DISTRICT-REFERENCE-AUTHOR-PASS"
REFERENCE_MARKER = "DISTRICT-REFERENCE-COLD-READBACK-PASS"
BASELINE_MARKER = "DISTRICT-BASELINE-COLD-READBACK-PASS"
FORBIDDEN = (
    "LogPython: Error", "Python script executed with errors",
    "Ensure condition failed", "Assertion failed", "Fatal error",
    "LowLevelFatalError", "DISTRICT-REFERENCE-AUTHOR-ERROR",
    "DISTRICT-REFERENCE-COLD-READBACK-ERROR",
    "DISTRICT-BASELINE-COLD-READBACK-ERROR",
)


class ClosureError(RuntimeError):
    """One closure invariant failed."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, value: object) -> None:
    temporary = path.with_name(path.name + ".tmp")
    if os.path.lexists(temporary):
        raise ClosureError("stale JSON temp requires inspection: %s" % temporary)
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8")
    os.replace(temporary, path)


def facts(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ClosureError("required file missing: %s" % path)
    return {"path": str(path), "size": path.stat().st_size,
            "sha256": contract.sha256(path)}


def require_plain_output(path: Path) -> None:
    current = Path(os.path.abspath(os.fspath(path)))
    while not current.exists():
        parent = current.parent
        if parent == current:
            raise ClosureError("no existing output ancestor: %s" % path)
        current = parent
    while True:
        if contract.is_reparse(current):
            raise ClosureError("output ancestor is link/reparse: %s" % current)
        if current.parent == current:
            break
        current = current.parent


def copy_verified(source: Path, destination: Path, expected_hash: str) -> None:
    if not source.is_file():
        raise ClosureError("copy source missing: %s" % source)
    require_plain_output(source)
    if destination.exists() or os.path.lexists(destination):
        raise ClosureError("copy destination already exists: %s" % destination)
    require_plain_output(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    require_plain_output(destination)
    temporary = destination.with_name(destination.name + ".copy-tmp")
    if os.path.lexists(temporary):
        raise ClosureError("stale copy temp requires inspection: %s" % temporary)
    shutil.copy2(source, temporary)
    if contract.is_reparse(temporary) or contract.sha256(temporary) != expected_hash:
        raise ClosureError("temporary copy failed hash/plain gate: %s" % temporary)
    os.replace(temporary, destination)
    if contract.sha256(destination) != expected_hash:
        raise ClosureError("installed copy hash mismatch: %s" % destination)


def move_exact(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise ClosureError("move source missing: %s" % source)
    require_plain_output(source)
    if destination.exists() or os.path.lexists(destination):
        raise ClosureError("move destination already exists: %s" % destination)
    require_plain_output(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    require_plain_output(destination)
    if os.path.splitdrive(os.path.abspath(source))[0].lower() != \
            os.path.splitdrive(os.path.abspath(destination))[0].lower():
        raise ClosureError("atomic move requires one volume")
    source.replace(destination)


def preflight(editor: Path, output: Path) -> dict[str, Any]:
    for required in (
            PROJECT, AUTHOR_SCRIPT, REFERENCE_READBACK, BASELINE_READBACK,
            editor):
        if not required.is_file():
            raise ClosureError("required closure input missing: %s" % required)
    require_plain_output(output)
    if output.exists() or os.path.lexists(output):
        raise ClosureError("fresh output already exists: %s" % output)
    if os.path.splitdrive(os.path.abspath(output))[0].lower() != \
            os.path.splitdrive(os.path.abspath(contract.LOADER_FILE))[0].lower():
        raise ClosureError("output must share live baseline volume")
    return contract.snapshot(expected_loader_hash=contract.BASELINE_SHA256)


def kill_exact_tree(process: subprocess.Popen[Any]) -> dict[str, Any]:
    evidence: dict[str, Any] = {"pid": process.pid}
    if process.poll() is not None:
        evidence.update(method="already-exited", exit_code=process.returncode)
        return evidence
    completed = subprocess.run(
        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
        capture_output=True, text=True, check=False, timeout=30)
    evidence.update(
        method="taskkill-exact-tree", taskkill_exit=completed.returncode,
        output=(completed.stdout + completed.stderr).strip())
    try:
        process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=30)
        evidence["fallback"] = "process-kill"
    evidence["exit_code"] = process.returncode
    return evidence


def run_editor(editor: Path, output: Path, label: str, script: Path,
               marker: str, timeout_seconds: int,
               environment: dict[str, str] | None = None) -> dict[str, Any]:
    log_root = output / "logs"
    log_root.mkdir(parents=True, exist_ok=True)
    abslog = log_root / (label + ".log")
    stdout_path = log_root / (label + ".stdout.log")
    if os.path.lexists(abslog) or os.path.lexists(stdout_path):
        raise ClosureError("fresh editor evidence already exists: %s" % label)
    command = [
        str(editor), str(PROJECT), "-run=pythonscript",
        "-script=%s" % script, "-unattended", "-nopause", "-nop4",
        "-nosplash", "-nosound", "-nullrhi", "-stdout",
        "-FullStdOutLogOutput", "-abslog=%s" % abslog,
    ]
    child_environment = os.environ.copy()
    child_environment.update(environment or {})
    with stdout_path.open("wb") as stream:
        process = subprocess.Popen(
            command, cwd=contract.REPO, stdout=stream,
            stderr=subprocess.STDOUT, env=child_environment)
        try:
            exit_code = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            watchdog = kill_exact_tree(process)
            write_json(output / (label + "-watchdog.json"), watchdog)
            raise ClosureError(
                "%s exceeded %ds outer watchdog" %
                (label, timeout_seconds)) from exc
    if exit_code != 0:
        raise ClosureError("%s editor exit=%d" % (label, exit_code))
    if not abslog.is_file():
        raise ClosureError("%s did not create abslog" % label)
    log_text = abslog.read_text(encoding="utf-8", errors="replace")
    stdout_text = stdout_path.read_text(encoding="utf-8", errors="replace")
    for stream_name, text in (("abslog", log_text), ("stdout", stdout_text)):
        if marker not in text:
            raise ClosureError("%s missing marker in %s" % (label, stream_name))
        for token in FORBIDDEN:
            if token.lower() in text.lower():
                raise ClosureError("%s %s contains %s" %
                                   (label, stream_name, token))
    if re.search(r"LogBlueprint[^\n]*Error", log_text, re.IGNORECASE):
        raise ClosureError("%s contains Blueprint error" % label)
    return {"command": command, "exit_code": exit_code,
            "abslog": facts(abslog), "stdout": facts(stdout_path)}


def restore_baseline(vault: Path, output: Path) -> dict[str, Any]:
    live = contract.LOADER_FILE
    require_plain_output(live)
    if live.is_file():
        if contract.sha256(live) == contract.BASELINE_SHA256:
            return facts(live)
        move_exact(live, output / "rollback" / "partial-live" / RELATIVE_ASSET)
    copy_verified(vault, live, contract.BASELINE_SHA256)
    return facts(live)


def rollback(vault: Path, output: Path) -> list[str]:
    errors: list[str] = []
    try:
        if contract.REFERENCE_ROOT.exists():
            destination = output / "rollback" / "partial-reference"
            if destination.exists():
                raise ClosureError("partial reference quarantine already exists")
            destination.parent.mkdir(parents=True, exist_ok=True)
            contract.REFERENCE_ROOT.replace(destination)
    except Exception as exc:  # noqa: BLE001
        errors.append("reference quarantine: %s" % exc)
    try:
        if vault.is_file():
            restore_baseline(vault, output)
            contract.snapshot(expected_loader_hash=contract.BASELINE_SHA256)
    except Exception as exc:  # noqa: BLE001
        errors.append("baseline restore: %s" % exc)
    return errors


def close(editor: Path, output: Path, timeout_seconds: int) -> None:
    entry = preflight(editor, output)
    output.mkdir(parents=True)
    manifest: dict[str, Any] = {
        "schema": 1, "task": contract.TASK_ID, "status": "running",
        "started_utc": utc_now(), "entry": entry, "steps": {},
    }
    baseline_vault = output / "baseline-vault" / RELATIVE_ASSET
    reference_vault = output / "reference-vault" / RELATIVE_ASSET
    try:
        copy_verified(
            contract.LOADER_FILE, baseline_vault, contract.BASELINE_SHA256)
        manifest["baseline_vault"] = facts(baseline_vault)

        manifest["steps"]["01-author-reference"] = run_editor(
            editor, output, "01-author-reference", AUTHOR_SCRIPT,
            AUTHOR_MARKER, timeout_seconds)
        authored = contract.snapshot(expected_loader_hash=None)
        reference_hash = authored["loader"]["sha256"]
        if reference_hash == contract.BASELINE_SHA256:
            raise ClosureError("reference author left baseline bytes unchanged")
        if contract.immutable_vector(authored) != contract.immutable_vector(entry):
            raise ClosureError("reference author changed immutable vector")
        manifest["authored"] = authored

        manifest["steps"]["02-cold-reference"] = run_editor(
            editor, output, "02-cold-reference", REFERENCE_READBACK,
            REFERENCE_MARKER, timeout_seconds,
            {"CRAFTBENCH_DISTRICT_REFERENCE_SHA256": reference_hash})
        cold = contract.snapshot(expected_loader_hash=reference_hash)
        if cold != authored:
            raise ClosureError("cold reference readback changed protected bytes")
        copy_verified(contract.LOADER_FILE, reference_vault, reference_hash)
        manifest["reference_vault"] = facts(reference_vault)

        move_exact(
            contract.LOADER_FILE,
            output / "evidence" / "reference-live" / RELATIVE_ASSET)
        copy_verified(
            baseline_vault, contract.LOADER_FILE, contract.BASELINE_SHA256)
        restored = contract.snapshot(expected_loader_hash=contract.BASELINE_SHA256)
        if contract.immutable_vector(restored) != contract.immutable_vector(entry):
            raise ClosureError("baseline restore changed immutable vector")
        manifest["restored"] = restored
        manifest["steps"]["03-cold-baseline"] = run_editor(
            editor, output, "03-cold-baseline", BASELINE_READBACK,
            BASELINE_MARKER, timeout_seconds)
        if contract.snapshot(expected_loader_hash=contract.BASELINE_SHA256) != restored:
            raise ClosureError("cold baseline readback changed protected bytes")

        copy_verified(reference_vault, contract.REFERENCE_FILE, reference_hash)
        manifest["reference"] = contract.require_reference_exact(reference_hash)
        if contract.sha256(contract.LOADER_FILE) != contract.BASELINE_SHA256:
            raise ClosureError("live baseline differs after reference install")
        manifest["status"] = "pass"
        manifest["completed_utc"] = utc_now()
        write_json(output / "closure.json", manifest)
        print(
            "DISTRICT-REFERENCE-CLOSURE-PASS baseline_sha256=%s "
            "reference_sha256=%s live_restored=1 l2i=5 output=%s" %
            (contract.BASELINE_SHA256, reference_hash, output), flush=True)
    except Exception as exc:
        manifest["status"] = "fail"
        manifest["error"] = str(exc)
        manifest["rollback_errors"] = rollback(baseline_vault, output)
        manifest["completed_utc"] = utc_now()
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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ue-root", type=Path, default=_UE_ROOT)
    parser.add_argument("--watchdog-seconds", type=int, default=720)
    parser.add_argument("--preflight-only", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.watchdog_seconds < 60:
        print("DISTRICT-REFERENCE-CLOSURE-ERROR watchdog must be >=60s",
              file=sys.stderr)
        return 1
    editor = (
        args.ue_root / "Engine" / "Binaries" / "Win64" /
        "UnrealEditor-Cmd.exe")
    output = Path(os.path.abspath(args.output))
    try:
        entry = preflight(editor, output)
        if args.preflight_only:
            print(
                "DISTRICT-REFERENCE-PREFLIGHT-PASS baseline_sha256=%s "
                "immutable=3 final_absent=1 reference_absent=1 "
                "output_absent=1 no_reparse=1" % entry["loader"]["sha256"])
            return 0
        close(editor, output, args.watchdog_seconds)
        return 0
    except (ClosureError, contract.ContractError) as exc:
        print("DISTRICT-REFERENCE-CLOSURE-ERROR %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

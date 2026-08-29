"""Fail-closed author/readback/harvest/restore closure for the reference."""

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

import contract

#: Engine root. Override with CB_UE_ROOT; defaults to Epic's standard install.
_UE_ROOT = Path(os.environ.get("CB_UE_ROOT", r"C:\Program Files\Epic Games\UE_5.8"))


PROJECT_FILE = contract.PROJECT / "ThirdPerson.uproject"
HERE = Path(__file__).resolve().parent
AUTHOR = HERE / "author_reference_live.py"
REFERENCE_READBACK = HERE / "readback_reference_live.py"
BASELINE_READBACK = HERE / "readback_baseline_live.py"
BASELINE_SHA = contract.EXPECTED_FINAL_ASSET_HASHES[
    "UE-projects/ThirdPerson/Content/Tasks/"
    "t3-only-the-near-active-sector-exists/BP_NearActiveSectorController.uasset"]
RELATIVE_ASSET = (Path("Content") / "Tasks" / contract.TASK_ID /
                  contract.CONTROLLER_FILE.name)
FORBIDDEN = (
    "LogPython: Error", "Python script executed with errors",
    "Ensure condition failed", "Assertion failed", "Fatal error",
    "LowLevelFatalError", "NEAR-ACTIVE-SECTOR-REFERENCE-AUTHOR-FAILED",
    "NEAR-ACTIVE-SECTOR-REFERENCE-READBACK-FAILED",
    "NEAR-ACTIVE-SECTOR-BASELINE-READBACK-FAILED",
)


class ClosureError(RuntimeError):
    """One closure invariant failed."""


def sha(path: Path) -> str:
    return contract.sha256(path)


def facts(path: Path) -> dict[str, Any]:
    if not path.is_file() or contract.is_reparse(path):
        raise ClosureError("required regular file missing: %s" % path)
    return {"path": str(path), "size": path.stat().st_size, "sha256": sha(path)}


def write_json(path: Path, value: object) -> None:
    temporary = path.with_name(path.name + ".tmp")
    if os.path.lexists(temporary):
        raise ClosureError("stale JSON temp: %s" % temporary)
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8")
    os.replace(temporary, path)


def require_plain_chain(path: Path) -> None:
    current = Path(os.path.abspath(path))
    while not os.path.lexists(current):
        if current.parent == current:
            raise ClosureError("no existing ancestor: %s" % path)
        current = current.parent
    while True:
        if contract.is_reparse(current):
            raise ClosureError("reparse/symlink boundary: %s" % current)
        if current.parent == current:
            break
        current = current.parent


def copy_exact(source: Path, destination: Path, expected_hash: str) -> None:
    if not source.is_file() or sha(source) != expected_hash:
        raise ClosureError("copy source hash mismatch: %s" % source)
    require_plain_chain(source)
    if os.path.lexists(destination):
        raise ClosureError("copy destination exists: %s" % destination)
    require_plain_chain(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".copy-tmp")
    if os.path.lexists(temporary):
        raise ClosureError("stale copy temp: %s" % temporary)
    shutil.copy2(source, temporary)
    if contract.is_reparse(temporary) or sha(temporary) != expected_hash:
        raise ClosureError("temporary copy verification failed")
    os.replace(temporary, destination)
    if sha(destination) != expected_hash:
        raise ClosureError("installed copy verification failed")


def move_exact(source: Path, destination: Path) -> None:
    if not source.is_file() or contract.is_reparse(source):
        raise ClosureError("move source missing/reparse: %s" % source)
    if os.path.lexists(destination):
        raise ClosureError("move destination exists: %s" % destination)
    require_plain_chain(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if os.path.splitdrive(os.path.abspath(source))[0].lower() != \
            os.path.splitdrive(os.path.abspath(destination))[0].lower():
        raise ClosureError("atomic move requires one volume")
    source.replace(destination)


def kill_tree(process: subprocess.Popen[Any]) -> dict[str, Any]:
    result: dict[str, Any] = {"pid": process.pid}
    if process.poll() is not None:
        result.update(method="already-exited", exit_code=process.returncode)
        return result
    completed = subprocess.run(
        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
        capture_output=True, text=True, check=False, timeout=30)
    result.update(method="taskkill-exact-tree", exit_code=completed.returncode,
                  output=(completed.stdout + completed.stderr).strip())
    process.wait(timeout=30)
    return result


def run_editor(editor: Path, output: Path, label: str, script: Path,
               marker: str, timeout: int,
               extra_env: dict[str, str] | None = None) -> dict[str, Any]:
    logs = output / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    abslog = logs / (label + ".log")
    stdout = logs / (label + ".stdout.log")
    if os.path.lexists(abslog) or os.path.lexists(stdout):
        raise ClosureError("fresh evidence exists: %s" % label)
    command = [
        str(editor), str(PROJECT_FILE), "-unattended", "-nop4", "-nopause",
        "-nosplash", "-nosound", "-nullrhi", "-stdout",
        "-FullStdOutLogOutput", "-ExecutePythonScript=%s" % script,
        "-abslog=%s" % abslog,
    ]
    environment = os.environ.copy()
    environment.update(extra_env or {})
    with stdout.open("wb") as stream:
        process = subprocess.Popen(command, cwd=contract.REPO, stdout=stream,
                                   stderr=subprocess.STDOUT, env=environment)
        try:
            exit_code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            write_json(output / (label + "-watchdog.json"), kill_tree(process))
            raise ClosureError("%s exceeded %ds watchdog" % (label, timeout)) from exc
    if exit_code != 0 or not abslog.is_file():
        raise ClosureError("%s editor exit/log failure: %d" % (label, exit_code))
    for stream_name, path in (("abslog", abslog), ("stdout", stdout)):
        text = path.read_text(encoding="utf-8", errors="replace")
        if marker not in text:
            raise ClosureError("%s missing marker in %s" % (label, stream_name))
        for token in FORBIDDEN:
            if token.lower() in text.lower():
                raise ClosureError("%s %s contains %s" %
                                   (label, stream_name, token))
        if re.search(r"LogBlueprint[^\n]*Error", text, re.IGNORECASE):
            raise ClosureError("%s contains Blueprint error" % label)
    return {"command": command, "exit_code": exit_code,
            "abslog": facts(abslog), "stdout": facts(stdout)}


def entry_snapshot() -> dict[str, Any]:
    contract.require_reference_absent()
    contract.controller_hash(BASELINE_SHA)
    return {"baseline": facts(contract.CONTROLLER_FILE),
            "immutable": contract.immutable_snapshot()}


def restore_baseline(vault: Path, output: Path) -> None:
    if contract.CONTROLLER_FILE.is_file():
        if sha(contract.CONTROLLER_FILE) == BASELINE_SHA:
            return
        move_exact(contract.CONTROLLER_FILE,
                   output / "rollback" / "partial-live" / RELATIVE_ASSET)
    copy_exact(vault, contract.CONTROLLER_FILE, BASELINE_SHA)


def close(editor: Path, output: Path, timeout: int) -> None:
    if os.path.lexists(output):
        raise ClosureError("fresh output exists: %s" % output)
    require_plain_chain(output)
    if os.path.splitdrive(os.path.abspath(output))[0].lower() != \
            os.path.splitdrive(os.path.abspath(contract.CONTROLLER_FILE))[0].lower():
        raise ClosureError("closure output must share live asset volume")
    entry = entry_snapshot()
    output.mkdir(parents=True)
    manifest: dict[str, Any] = {
        "schema": 1, "task": contract.TASK_ID, "status": "running",
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "entry": entry, "steps": {},
    }
    baseline_vault = output / "baseline-vault" / RELATIVE_ASSET
    reference_vault = output / "reference-vault" / RELATIVE_ASSET
    try:
        copy_exact(contract.CONTROLLER_FILE, baseline_vault, BASELINE_SHA)
        manifest["baseline_vault"] = facts(baseline_vault)
        manifest["steps"]["01-author-reference"] = run_editor(
            editor, output, "01-author-reference", AUTHOR,
            "NEAR-ACTIVE-SECTOR-REFERENCE-AUTHOR-PASS", timeout)
        reference_hash = contract.controller_hash()
        if reference_hash == BASELINE_SHA:
            raise ClosureError("reference bytes equal baseline")
        if contract.immutable_snapshot() != entry["immutable"]:
            raise ClosureError("immutable vector changed after author")
        manifest["reference_hash"] = reference_hash
        manifest["steps"]["02-cold-reference"] = run_editor(
            editor, output, "02-cold-reference", REFERENCE_READBACK,
            "NEAR-ACTIVE-SECTOR-REFERENCE-COLD-READBACK-PASS", timeout,
            {"CRAFTBENCH_NEAR_SECTOR_REFERENCE_SHA256": reference_hash})
        copy_exact(contract.CONTROLLER_FILE, reference_vault, reference_hash)
        move_exact(contract.CONTROLLER_FILE,
                   output / "evidence" / "reference-live" / RELATIVE_ASSET)
        copy_exact(baseline_vault, contract.CONTROLLER_FILE, BASELINE_SHA)
        if entry_snapshot() != entry:
            raise ClosureError("baseline restore vector mismatch")
        manifest["steps"]["03-cold-baseline"] = run_editor(
            editor, output, "03-cold-baseline", BASELINE_READBACK,
            "NEAR-ACTIVE-SECTOR-BASELINE-COLD-READBACK-PASS", timeout)
        if entry_snapshot() != entry:
            raise ClosureError("cold baseline changed protected bytes")
        copy_exact(reference_vault, contract.REFERENCE_FILE, reference_hash)
        manifest["reference"] = contract.require_reference_exact(reference_hash)
        contract.controller_hash(BASELINE_SHA)
        manifest["status"] = "pass"
        manifest["completed_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(output / "closure.json", manifest)
        print("NEAR-ACTIVE-SECTOR-REFERENCE-CLOSURE-PASS "
              "baseline_sha256=%s reference_sha256=%s live_restored=1 l2i=3" %
              (BASELINE_SHA, reference_hash), flush=True)
    except Exception as exc:
        errors = []
        try:
            if contract.REFERENCE.exists():
                destination = output / "rollback" / "partial-reference"
                if os.path.lexists(destination):
                    raise ClosureError("partial reference quarantine exists")
                destination.parent.mkdir(parents=True, exist_ok=True)
                contract.REFERENCE.replace(destination)
        except Exception as rollback_exc:  # noqa: BLE001
            errors.append("reference quarantine: %s" % rollback_exc)
        try:
            if baseline_vault.is_file():
                restore_baseline(baseline_vault, output)
        except Exception as rollback_exc:  # noqa: BLE001
            errors.append("baseline restore: %s" % rollback_exc)
        manifest.update(status="fail", error=str(exc), rollback_errors=errors,
                        completed_utc=datetime.now(timezone.utc).isoformat())
        write_json(output / "closure.json", manifest)
        raise ClosureError("%s%s" %
                           (exc, "; rollback errors=" + repr(errors) if errors else ""))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ue-root", type=Path, default=_UE_ROOT)
    parser.add_argument("--watchdog-seconds", type=int, default=720)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args(argv)
    editor = args.ue_root / "Engine" / "Binaries" / "Win64" / \
        "UnrealEditor-Cmd.exe"
    output = Path(os.path.abspath(args.output))
    try:
        if not editor.is_file() or not PROJECT_FILE.is_file():
            raise ClosureError("editor/project missing")
        if args.watchdog_seconds < 60:
            raise ClosureError("watchdog must be >=60 seconds")
        if args.preflight_only:
            if os.path.lexists(output):
                raise ClosureError("fresh output exists")
            entry = entry_snapshot()
            print("NEAR-ACTIVE-SECTOR-REFERENCE-PREFLIGHT-PASS "
                  "baseline_sha256=%s immutable_groups=%d reference_absent=1" %
                  (entry["baseline"]["sha256"], len(entry["immutable"])))
            return 0
        close(editor, output, args.watchdog_seconds)
        return 0
    except Exception as exc:  # noqa: BLE001
        print("NEAR-ACTIVE-SECTOR-REFERENCE-CLOSURE-ERROR %s" % exc,
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

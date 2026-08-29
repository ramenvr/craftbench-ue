"""Atomic author/readback/harvest/restore closure for the reference asset."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import time

#: Engine root. Override with CB_UE_ROOT; defaults to Epic's standard install.
_UE_ROOT = Path(os.environ.get("CB_UE_ROOT", r"C:\Program Files\Epic Games\UE_5.8"))


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import reference_contract as contract  # noqa: E402
from guard_aim_common import PROJECT, REFERENCE  # noqa: E402


EDITOR = _UE_ROOT / "Engine/Binaries/Win64/UnrealEditor-Cmd.exe"
AUTHOR = HERE / "author_reference.py"
READ_REFERENCE = HERE / "readback_reference.py"
READ_BASELINE = HERE / "readback_restored_baseline.py"


class ClosureError(RuntimeError):
    pass


def is_reparse(path: Path) -> bool:
    info = path.lstat()
    return path.is_symlink() or bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def require_plain_ancestors(path: Path) -> None:
    current = Path(os.path.abspath(os.fspath(path)))
    while not current.exists():
        current = current.parent
    while True:
        if is_reparse(current):
            raise ClosureError("reparse ancestor rejected: %s" % current)
        if current.parent == current:
            break
        current = current.parent


def assert_no_writers() -> None:
    query = (
        "$p=Get-CimInstance Win32_Process | Where-Object { "
        "$_.Name -match '^(UnrealEditor|UnrealEditor-Cmd|UnrealBuildTool|cl|link)\\.exe$' }; "
        "$p | ForEach-Object { \"$($_.ProcessId)|$($_.Name)|$($_.CommandLine)\" }")
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", query],
        capture_output=True, text=True, check=False)
    active = [line for line in result.stdout.splitlines() if line.strip()]
    if result.returncode or active:
        raise ClosureError("heavy writer active/query failed: %r" % active)


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def move_directory(source: Path, destination: Path) -> None:
    if not source.is_dir() or os.path.lexists(destination):
        raise ClosureError("atomic move precondition failed")
    if source.drive.lower() != destination.drive.lower():
        raise ClosureError("atomic move requires same volume")
    destination.parent.mkdir(parents=True, exist_ok=False)
    os.replace(source, destination)


def run_editor(output: Path, stem: str, script: Path, watchdog: int,
               marker: str, env_extra: dict[str, str] | None = None) -> dict:
    log = output / (stem + ".log")
    stdout_path = output / (stem + ".stdout.log")
    argv = [
        str(EDITOR), str(PROJECT), "-run=pythonscript",
        "-script=" + script.as_posix(), "-unattended", "-nopause",
        "-nosplash", "-nosound", "-nullrhi", "-stdout",
        "-FullStdOutLogOutput", "-abslog=" + str(log),
    ]
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    started = time.monotonic()
    process = subprocess.Popen(
        argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", env=env)
    timed_out = False
    try:
        stdout, _ = process.communicate(timeout=watchdog)
    except subprocess.TimeoutExpired:
        timed_out = True
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       capture_output=True, text=True, check=False)
        stdout, _ = process.communicate()
    stdout_path.write_text(stdout, encoding="utf-8")
    log_text = log.read_text(encoding="utf-8", errors="replace") \
        if log.is_file() else ""
    combined = stdout + "\n" + log_text
    failures = [token for token in (
        "GUARD-AIM-REFERENCE-AUTHOR-FAILED",
        "GUARD-AIM-REFERENCE-COLD-FAILED",
        "GUARD-AIM-BASELINE-COLD-FAILED",
        "LogPython: Error", "Ensure condition failed", "Assertion failed",
        "Fatal error", "LowLevelFatalError") if token in combined]
    result = {
        "argv": argv, "exit_code": process.returncode,
        "timed_out": timed_out,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "marker": marker, "marker_present": marker in combined,
        "failures": failures, "log": str(log), "stdout": str(stdout_path),
    }
    if timed_out or process.returncode != 0 or failures or marker not in combined:
        raise ClosureError("editor step failed: %r" % result)
    return result


def recover(output: Path, baseline_vault: Path) -> list[str]:
    errors = []
    rollback = output / "rollback"
    try:
        if contract.FINAL_DISK_DIR.is_dir() and baseline_vault.is_dir():
            partial = rollback / "partial-live-reference" / contract.FINAL_DISK_DIR.name
            partial.parent.mkdir(parents=True, exist_ok=True)
            os.replace(contract.FINAL_DISK_DIR, partial)
        if baseline_vault.is_dir() and not contract.FINAL_DISK_DIR.exists():
            contract.FINAL_DISK_DIR.parent.mkdir(parents=True, exist_ok=True)
            os.replace(baseline_vault, contract.FINAL_DISK_DIR)
    except Exception as exc:
        errors.append("baseline recovery: %s" % exc)
    try:
        if contract.REFERENCE_DIR.exists():
            partial = rollback / "partial-installed-reference"
            partial.parent.mkdir(parents=True, exist_ok=True)
            os.replace(contract.REFERENCE_DIR, partial)
    except Exception as exc:
        errors.append("reference recovery: %s" % exc)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--watchdog-seconds", type=int, default=720)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    assert_no_writers()
    if not EDITOR.is_file() or not PROJECT.is_file():
        raise ClosureError("editor/project missing")
    for script in (AUTHOR, READ_REFERENCE, READ_BASELINE):
        if not script.is_file():
            raise ClosureError("closure script missing: %s" % script)
    if os.path.lexists(output):
        raise ClosureError("output must be fresh")
    require_plain_ancestors(output)
    contract.require_reference_absent()
    baseline = contract.exact_live_vector()
    immutable = contract.immutable_vector()
    if args.preflight_only:
        print("GUARD-AIM-REFERENCE-PREFLIGHT-PASS baseline=1 immutable=3 "
              "reference_absent=1 output_absent=1")
        return 0

    output.mkdir(parents=True, exist_ok=False)
    manifest: dict[str, object] = {
        "status": "running", "baseline": baseline,
        "immutable": immutable, "steps": {}}
    write_json(output / "closure.json", manifest)
    baseline_vault = output / "baseline-vault" / contract.FINAL_DISK_DIR.name
    reference_vault = output / "reference-vault" / contract.FINAL_DISK_DIR.name
    try:
        move_directory(contract.FINAL_DISK_DIR, baseline_vault)
        manifest["steps"]["author"] = run_editor(
            output, "01-author-reference", AUTHOR, args.watchdog_seconds,
            "GUARD-AIM-REFERENCE-AUTHOR-PASS")
        authored = contract.exact_live_vector()
        if authored == baseline:
            raise ClosureError("complete reference equals empty baseline")
        reference_hash = authored[contract.FINAL_ASSET.name]
        manifest["steps"]["reference_cold"] = run_editor(
            output, "02-cold-reference", READ_REFERENCE,
            args.watchdog_seconds, "GUARD-AIM-REFERENCE-COLD-PASS",
            {"CRAFTBENCH_GUARD_AIM_REFERENCE_HASH": reference_hash})
        move_directory(contract.FINAL_DISK_DIR, reference_vault)
        contract.FINAL_DISK_DIR.parent.mkdir(parents=True, exist_ok=True)
        os.replace(baseline_vault, contract.FINAL_DISK_DIR)
        if contract.exact_live_vector() != baseline:
            raise ClosureError("baseline restoration mismatch")
        manifest["steps"]["baseline_cold"] = run_editor(
            output, "03-cold-restored-baseline", READ_BASELINE,
            args.watchdog_seconds, "GUARD-AIM-BASELINE-COLD-PASS",
            {"CRAFTBENCH_GUARD_AIM_BASELINE_HASH":
             baseline[contract.FINAL_ASSET.name]})
        contract.require_reference_absent()
        contract.REFERENCE_DIR.mkdir(parents=True, exist_ok=False)
        shutil.copy2(reference_vault / contract.FINAL_ASSET.name, REFERENCE)
        if contract.sha256(REFERENCE) != reference_hash:
            raise ClosureError("installed reference hash mismatch")
        if contract.exact_live_vector() != baseline or \
                contract.immutable_vector() != immutable:
            raise ClosureError("final protected vector mismatch")
        manifest.update({
            "status": "pass", "reference_sha256": reference_hash,
            "final_baseline": contract.exact_live_vector(),
            "final_immutable": contract.immutable_vector(),
        })
        write_json(output / "closure.json", manifest)
        print("GUARD-AIM-REFERENCE-CLOSURE-PASS baseline_restored=1 "
              "reference=1 immutable=3 output=%s" % output)
        return 0
    except Exception as exc:
        recovery = recover(output, baseline_vault)
        manifest.update({"status": "fail", "error": str(exc),
                         "recovery_errors": recovery})
        write_json(output / "closure.json", manifest)
        raise


if __name__ == "__main__":
    raise SystemExit(main())

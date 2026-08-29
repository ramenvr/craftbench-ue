"""Recoverable author/readback/harvest/restore closure for the StateTree."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

#: Engine root. Override with CB_UE_ROOT; defaults to Epic's standard install.
_UE_ROOT = Path(os.environ.get("CB_UE_ROOT", r"C:\Program Files\Epic Games\UE_5.8"))


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from worker_plan_final_common import (  # noqa: E402
    FINAL_DIR, FINAL_FILE, FINAL_MAP, PROJECT, REFERENCE,
    REFERENCE_ASSET_DIR, final_vector, immutable_vector,
    reference_vector, require_plain_ancestors,
)

EDITOR = _UE_ROOT / "Engine/Binaries/Win64/UnrealEditor-Cmd.exe"
AUTHOR = HERE / "author_reference_asset.py"
REFERENCE_READBACK = HERE / "readback_reference_asset.py"
BASELINE_READBACK = HERE / "readback_baseline_asset.py"


class ClosureError(RuntimeError):
    """The closure stopped at a fail-closed boundary."""


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--watchdog-seconds", type=int, default=720)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    if args.watchdog_seconds < 60:
        parser.error("watchdog must be at least 60 seconds")
    return args


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def assert_no_writers():
    command = (
        "$p=Get-CimInstance Win32_Process | Where-Object { "
        "$_.Name -match '^(UnrealEditor|UnrealEditor-Cmd|UnrealBuildTool|cl|link)\\.exe$' }; "
        "$p | ForEach-Object { \"$($_.ProcessId)|$($_.Name)|$($_.CommandLine)\" }")
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise ClosureError("writer query failed: " + result.stderr.strip())
    active = [line for line in result.stdout.splitlines() if line.strip()]
    if active:
        raise ClosureError("heavy writer already active: " + " ; ".join(active))


def move_directory(source, destination):
    if not source.is_dir() or os.path.lexists(destination):
        raise ClosureError("atomic move precondition failed source=%s dest=%s" %
                           (source, destination))
    if source.drive.lower() != destination.drive.lower():
        raise ClosureError("atomic move requires the same volume")
    destination.parent.mkdir(parents=True, exist_ok=False)
    os.replace(source, destination)


def run_editor(output, stem, script, watchdog, marker):
    log = output / (stem + ".log")
    stdout_path = output / (stem + ".stdout.log")
    stderr_path = output / (stem + ".stderr.log")
    argv = [
        str(EDITOR), str(PROJECT), "-unattended", "-nop4", "-nosplash",
        "-nosound", "-nullrhi", "-stdout", "-FullStdOutLogOutput",
        "-ExecutePythonScript=" + str(script), "-abslog=" + str(log),
    ]
    started = time.monotonic()
    process = subprocess.Popen(
        argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace")
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=watchdog)
    except subprocess.TimeoutExpired:
        timed_out = True
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       capture_output=True, text=True, check=False, timeout=30)
        stdout, stderr = process.communicate()
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    log_text = log.read_text(encoding="utf-8", errors="replace") \
        if log.is_file() else ""
    combined = stdout + "\n" + stderr + "\n" + log_text
    failure_tokens = (
        "WORKER-PLAN-REFERENCE-AUTHOR-FAILED",
        "WORKER-PLAN-REFERENCE-READBACK-FAILED",
        "WORKER-PLAN-BASELINE-ASSET-READBACK-FAILED",
        "LogPython: Error", "Ensure condition failed", "Assertion failed",
        "Fatal error", "LowLevelFatalError",
    )
    failures = [token for token in failure_tokens if token in combined]
    result = {
        "argv": argv, "exit_code": process.returncode,
        "timed_out": timed_out,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "log": str(log), "stdout": str(stdout_path),
        "stderr": str(stderr_path), "failures": failures,
        "marker": marker, "marker_present": marker in combined,
    }
    if timed_out or process.returncode != 0 or failures or marker not in combined:
        raise ClosureError("editor step failed %s: %r" % (stem, result))
    return result


def same_asset_bytes(left, right):
    return ({Path(key).name: value for key, value in left.items()} ==
            {Path(key).name: value for key, value in right.items()})


def install_reference(vault):
    if os.path.lexists(REFERENCE):
        raise ClosureError("reference unexpectedly exists")
    REFERENCE_ASSET_DIR.mkdir(parents=True, exist_ok=False)
    source = vault / FINAL_FILE.name
    destination = REFERENCE_ASSET_DIR / FINAL_FILE.name
    if not source.is_file() or os.path.lexists(destination):
        raise ClosureError("reference copy precondition failed")
    shutil.copy2(source, destination)
    return reference_vector()


def recover(output, baseline_vault):
    errors = []
    rollback = output / "rollback"
    try:
        if os.path.lexists(REFERENCE):
            destination = rollback / "partial-reference"
            destination.parent.mkdir(parents=True, exist_ok=True)
            if os.path.lexists(destination):
                raise ClosureError("partial reference rollback exists")
            os.replace(REFERENCE, destination)
    except Exception as exc:
        errors.append("reference quarantine: %s" % exc)
    try:
        if baseline_vault.is_dir():
            if FINAL_DIR.is_dir():
                destination = rollback / "partial-live-reference"
                destination.parent.mkdir(parents=True, exist_ok=True)
                if os.path.lexists(destination):
                    raise ClosureError("partial live rollback exists")
                os.replace(FINAL_DIR, destination)
            if os.path.lexists(FINAL_DIR):
                raise ClosureError("live final namespace not absent")
            FINAL_DIR.parent.mkdir(parents=True, exist_ok=True)
            os.replace(baseline_vault, FINAL_DIR)
            final_vector()
    except Exception as exc:
        errors.append("baseline restore: %s" % exc)
    return errors


def preflight(output):
    assert_no_writers()
    for path in (EDITOR, PROJECT, AUTHOR, REFERENCE_READBACK,
                 BASELINE_READBACK, FINAL_MAP):
        if not path.is_file():
            raise ClosureError("required file missing: %s" % path)
    if os.path.lexists(output) or os.path.lexists(REFERENCE):
        raise ClosureError("output/reference must be absent")
    require_plain_ancestors(output)
    return {"baseline": final_vector(), "immutable": immutable_vector()}


def main():
    args = parse_args()
    output = Path(os.path.abspath(os.fspath(args.output)))
    initial = preflight(output)
    if args.preflight_only:
        print("WORKER-PLAN-REFERENCE-PREFLIGHT-PASS baseline=1 "
              "immutable=5 final_map=1 reference_absent=1 output_absent=1")
        return 0
    output.mkdir(parents=True, exist_ok=False)
    manifest = {"status": "running", "initial": initial, "steps": {}}
    write_json(output / "closure.json", manifest)
    baseline_vault = output / "baseline-vault" / FINAL_DIR.name
    reference_vault = output / "reference-vault" / FINAL_DIR.name
    try:
        move_directory(FINAL_DIR, baseline_vault)
        if immutable_vector() != initial["immutable"]:
            raise ClosureError("parking baseline changed immutable vector")
        manifest["steps"]["01-author-reference"] = run_editor(
            output, "01-author-reference", AUTHOR, args.watchdog_seconds,
            "WORKER-PLAN-REFERENCE-AUTHOR-PASS")
        authored = final_vector()
        if same_asset_bytes(authored, initial["baseline"]):
            raise ClosureError("correct reference bytes equal empty baseline")
        manifest["authored_reference"] = authored
        manifest["steps"]["02-readback-reference"] = run_editor(
            output, "02-readback-reference", REFERENCE_READBACK,
            args.watchdog_seconds, "WORKER-PLAN-REFERENCE-READBACK-PASS")
        move_directory(FINAL_DIR, reference_vault)
        FINAL_DIR.parent.mkdir(parents=True, exist_ok=True)
        os.replace(baseline_vault, FINAL_DIR)
        if final_vector() != initial["baseline"]:
            raise ClosureError("baseline restoration hash mismatch")
        manifest["steps"]["03-readback-restored-baseline"] = run_editor(
            output, "03-readback-restored-baseline", BASELINE_READBACK,
            args.watchdog_seconds,
            "WORKER-PLAN-BASELINE-ASSET-READBACK-PASS")
        installed = install_reference(reference_vault)
        if not same_asset_bytes(installed, authored):
            raise ClosureError("installed reference differs from authored bytes")
        if final_vector() != initial["baseline"] or \
                immutable_vector() != initial["immutable"]:
            raise ClosureError("final protected vector mismatch")
        manifest.update({
            "status": "pass", "reference": installed,
            "final_baseline": final_vector(),
            "final_immutable": immutable_vector(),
        })
        write_json(output / "closure.json", manifest)
        print("WORKER-PLAN-REFERENCE-CLOSURE-PASS baseline_restored=1 "
              "reference=1 immutable_hashes_unchanged=1 output=%s" % output)
        return 0
    except Exception as exc:
        recovery_errors = recover(output, baseline_vault)
        manifest.update({"status": "fail", "error": str(exc),
                         "recovery_errors": recovery_errors})
        try:
            write_json(output / "closure.json", manifest)
        except Exception:
            pass
        raise


if __name__ == "__main__":
    raise SystemExit(main())

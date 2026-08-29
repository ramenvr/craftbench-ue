"""Fail-closed author/readback/harvest/restore closure for the PCG graph."""

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
from pcg_task_common import (  # noqa: E402
    FINAL_GRAPH_ROOT, PROJECT, REFERENCE, REFERENCE_GRAPH_FILE,
    REFERENCE_GRAPH_ROOT, admission_graph_vector, admission_map_vector,
    final_graph_vector, final_map_vector, immutable_vector,
    reference_graph_vector,
)


EDITOR = _UE_ROOT / "Engine/Binaries/Win64/UnrealEditor-Cmd.exe"
AUTHOR_SCRIPT = HERE / "author_reference.py"
REFERENCE_READBACK = HERE / "readback_reference.py"
BASELINE_READBACK = HERE / "readback_restored_baseline.py"


class ClosureError(RuntimeError):
    """Reference closure stopped at a recoverable boundary."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--watchdog-seconds", type=int, default=720)
    parser.add_argument("--preflight-only", action="store_true")
    return parser.parse_args()


def is_reparse(path: Path) -> bool:
    info = path.lstat()
    return path.is_symlink() or bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def require_plain_existing_ancestors(path: Path) -> None:
    current = Path(os.path.abspath(os.fspath(path)))
    while not current.exists():
        parent = current.parent
        if parent == current:
            raise ClosureError("no existing ancestor for %s" % path)
        current = parent
    while True:
        if is_reparse(current):
            raise ClosureError("reparse ancestor rejected: %s" % current)
        parent = current.parent
        if parent == current:
            return
        current = parent


def assert_no_writers() -> None:
    command = (
        "$p=Get-CimInstance Win32_Process | Where-Object { "
        "$_.Name -match '^(UnrealEditor|UnrealEditor-Cmd|UnrealBuildTool|cl|link)\\.exe$' "
        "-or ($_.Name -match '^python(3)?\\.exe$' -and "
        "$_.CommandLine -match 'run_task.py|cb(.cmd)?\\s+refgate') }; "
        "$p | ForEach-Object { \"$($_.ProcessId)|$($_.Name)|$($_.CommandLine)\" }")
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise ClosureError("writer query failed: " + result.stderr.strip())
    active = [line for line in result.stdout.splitlines() if line.strip()]
    if active:
        raise ClosureError("heavy writer already active: " + " ; ".join(active))


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def protected_snapshot() -> dict[str, object]:
    return {
        "admission_graph": admission_graph_vector(),
        "admission_map": admission_map_vector(),
        "final_map": final_map_vector(),
        "immutable": immutable_vector(),
    }


def run_editor(output: Path, stem: str, script: Path, watchdog: int,
               required_marker: str,
               extra_env: dict[str, str] | None = None) -> dict[str, object]:
    log = output / (stem + ".log")
    stdout_path = output / (stem + ".stdout.log")
    stderr_path = output / (stem + ".stderr.log")
    argv = [
        str(EDITOR), str(PROJECT), "-unattended", "-nop4", "-nosplash",
        "-nosound", "-nullrhi", "-stdout", "-FullStdOutLogOutput",
        "-ExecutePythonScript=" + str(script), "-abslog=" + str(log),
    ]
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    started = time.monotonic()
    process = subprocess.Popen(
        argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace", env=env)
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=watchdog)
    except subprocess.TimeoutExpired:
        timed_out = True
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       capture_output=True, text=True, check=False)
        stdout, stderr = process.communicate()
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    log_text = log.read_text(encoding="utf-8", errors="replace") \
        if log.is_file() else ""
    combined = stdout + "\n" + stderr + "\n" + log_text
    failure_tokens = (
        "FILTERED-POINT-REFERENCE-AUTHOR-FAILED",
        "FILTERED-POINT-REFERENCE-COLD-FAILED",
        "FILTERED-POINT-RESTORED-BASELINE-COLD-FAILED",
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
        "required_marker": required_marker,
        "marker_present": required_marker in combined,
    }
    if timed_out or process.returncode != 0 or failures \
            or required_marker not in combined:
        raise ClosureError("editor step failed %s: %r" % (stem, result))
    return result


def move_directory(source: Path, destination: Path) -> None:
    if not source.is_dir() or os.path.lexists(destination):
        raise ClosureError(
            "atomic move precondition failed source=%s destination=%s" %
            (source, destination))
    if source.drive.lower() != destination.drive.lower():
        raise ClosureError("atomic move requires the same volume")
    destination.parent.mkdir(parents=True, exist_ok=False)
    os.replace(source, destination)


def by_name(vector: dict[str, object]) -> dict[str, object]:
    return {Path(key).name: value for key, value in vector.items()}


def install_reference(reference_vault: Path) -> dict[str, object]:
    if os.path.lexists(REFERENCE):
        raise ClosureError("reference destination already exists")
    REFERENCE_GRAPH_ROOT.mkdir(parents=True, exist_ok=False)
    sources = sorted(reference_vault.iterdir())
    if len(sources) != 1 or sources[0].name != REFERENCE_GRAPH_FILE.name:
        raise ClosureError("reference vault inventory mismatch")
    shutil.copy2(sources[0], REFERENCE_GRAPH_FILE)
    return reference_graph_vector()


def recover(output: Path, baseline_vault: Path) -> list[str]:
    errors: list[str] = []
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
            if FINAL_GRAPH_ROOT.is_dir():
                destination = rollback / "partial-live-reference"
                destination.parent.mkdir(parents=True, exist_ok=True)
                if os.path.lexists(destination):
                    raise ClosureError("partial live rollback exists")
                os.replace(FINAL_GRAPH_ROOT, destination)
            if os.path.lexists(FINAL_GRAPH_ROOT):
                raise ClosureError("live graph namespace is not absent")
            FINAL_GRAPH_ROOT.parent.mkdir(parents=True, exist_ok=True)
            os.replace(baseline_vault, FINAL_GRAPH_ROOT)
            final_graph_vector()
    except Exception as exc:
        errors.append("baseline restore: %s" % exc)
    return errors


def preflight(output: Path) -> dict[str, object]:
    assert_no_writers()
    if not EDITOR.is_file() or not PROJECT.is_file():
        raise ClosureError("editor or project missing")
    for script in (AUTHOR_SCRIPT, REFERENCE_READBACK, BASELINE_READBACK):
        if not script.is_file():
            raise ClosureError("closure script missing: %s" % script)
    if os.path.lexists(output) or os.path.lexists(REFERENCE):
        raise ClosureError("output and reference must be absent")
    require_plain_existing_ancestors(output)
    return {
        "baseline": final_graph_vector(),
        "protected": protected_snapshot(),
    }


def main() -> int:
    args = parse_args()
    output = Path(os.path.abspath(os.fspath(args.output)))
    initial = preflight(output)
    if args.preflight_only:
        print("FILTERED-POINT-REFERENCE-PREFLIGHT-PASS baseline=1 maps=2 "
              "admission_graph=1 reference_absent=1 output_absent=1")
        return 0

    output.mkdir(parents=True, exist_ok=False)
    manifest: dict[str, object] = {
        "status": "running", "initial": initial, "steps": {}}
    write_json(output / "closure.json", manifest)
    baseline_vault = output / "baseline-vault" / FINAL_GRAPH_ROOT.name
    reference_vault = output / "reference-vault" / FINAL_GRAPH_ROOT.name
    try:
        move_directory(FINAL_GRAPH_ROOT, baseline_vault)
        if protected_snapshot() != initial["protected"]:
            raise ClosureError("parking baseline changed protected vector")
        manifest["steps"]["01-author-reference"] = run_editor(
            output, "01-author-reference", AUTHOR_SCRIPT,
            args.watchdog_seconds, "FILTERED-POINT-REFERENCE-AUTHOR-PASS")
        authored = final_graph_vector()
        if by_name(authored) == by_name(initial["baseline"]):
            raise ClosureError("reference bytes equal empty baseline")
        manifest["authored_reference"] = authored
        manifest["steps"]["02-cold-reference"] = run_editor(
            output, "02-cold-reference", REFERENCE_READBACK,
            args.watchdog_seconds, "FILTERED-POINT-REFERENCE-COLD-PASS",
            {"CRAFTBENCH_FILTERED_POINT_REFERENCE_HASHES":
             json.dumps(authored, sort_keys=True)})
        move_directory(FINAL_GRAPH_ROOT, reference_vault)
        FINAL_GRAPH_ROOT.parent.mkdir(parents=True, exist_ok=True)
        os.replace(baseline_vault, FINAL_GRAPH_ROOT)
        if final_graph_vector() != initial["baseline"]:
            raise ClosureError("baseline restoration hash mismatch")
        manifest["steps"]["03-cold-restored-baseline"] = run_editor(
            output, "03-cold-restored-baseline", BASELINE_READBACK,
            args.watchdog_seconds,
            "FILTERED-POINT-RESTORED-BASELINE-COLD-PASS")
        installed = install_reference(reference_vault)
        if by_name(installed) != by_name(authored):
            raise ClosureError("installed reference differs from authored bytes")
        if final_graph_vector() != initial["baseline"] \
                or protected_snapshot() != initial["protected"]:
            raise ClosureError("final protected vector mismatch")
        manifest.update({
            "status": "pass", "reference": installed,
            "final_baseline": final_graph_vector(),
            "final_protected": protected_snapshot(),
        })
        write_json(output / "closure.json", manifest)
        print("FILTERED-POINT-REFERENCE-CLOSURE-PASS baseline_restored=1 "
              "reference=1 l2i=3 protected_hashes_unchanged=1 output=%s" %
              output)
        return 0
    except Exception as exc:
        recovery = recover(output, baseline_vault)
        manifest.update({"status": "fail", "error": str(exc),
                         "recovery_errors": recovery})
        try:
            write_json(output / "closure.json", manifest)
        except Exception:
            pass
        raise


if __name__ == "__main__":
    raise SystemExit(main())

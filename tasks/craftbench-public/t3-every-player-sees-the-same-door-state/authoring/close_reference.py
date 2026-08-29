"""Recoverable Door reference author/readback/harvest/restore closure."""

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
from door_common import (  # noqa: E402
    ADMISSION_ASSET, ADMISSION_MAP, BASELINE_VECTOR, FINAL_ASSET, FINAL_MAP,
    PROJECT, REFERENCE_ASSET, is_reparse, optional_vector, sha256,
)

AUTHOR = HERE / "author_reference_asset.py"
REFERENCE_READBACK = HERE / "readback_reference_asset.py"
BASELINE_READBACK = HERE / "readback_asset.py"
UPROJECT = PROJECT / "ThirdPerson.uproject"
AUTHOR_MARKER = "REPLICATED-DOOR-REFERENCE-AUTHOR-PASS"
REFERENCE_MARKER = "REPLICATED-DOOR-REFERENCE-READBACK-PASS"
BASELINE_MARKER = "REPLICATED-DOOR-ASSET-READBACK-PASS mode=baseline"


class ClosureError(RuntimeError):
    """A closure invariant failed."""


def facts(path: Path) -> dict[str, object]:
    if not path.is_file() or path.is_symlink() or is_reparse(path):
        raise ClosureError("required regular file missing: %s" % path)
    return {"size": path.stat().st_size, "sha256": sha256(path)}


def write_json(path: Path, payload: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8")
    os.replace(temporary, path)


def require_plain_ancestors(path: Path) -> None:
    current = Path(os.path.abspath(path))
    while not current.exists():
        parent = current.parent
        if parent == current:
            raise ClosureError("no existing ancestor: %s" % path)
        current = parent
    while True:
        if current.is_symlink() or is_reparse(current):
            raise ClosureError("link/reparse ancestor: %s" % current)
        if current.parent == current:
            return
        current = current.parent


def assert_no_writers() -> None:
    query = (
        "$p=Get-CimInstance Win32_Process | Where-Object { "
        "$_.Name -match '^(UnrealEditor|UnrealEditor-Cmd|UnrealBuildTool|cl|link|ThirdPerson)\\.exe$' "
        "-or ($_.Name -eq 'cmd.exe' -and $_.CommandLine -match 'Build\\.bat') }; "
        "$p | ForEach-Object { \"$($_.ProcessId)|$($_.Name)|$($_.CommandLine)\" }")
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", query], text=True,
        capture_output=True, check=False)
    if result.returncode != 0:
        raise ClosureError("writer query failed: " + result.stderr.strip())
    active = [line for line in result.stdout.splitlines() if line.strip()]
    if active:
        raise ClosureError("heavy writer active: " + " ; ".join(active))


def copy_verified(source: Path, destination: Path,
                  expected_hash: str) -> None:
    if os.path.lexists(destination):
        raise ClosureError("copy destination exists: %s" % destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".copy-tmp")
    if os.path.lexists(temporary):
        raise ClosureError("stale copy temporary: %s" % temporary)
    shutil.copy2(source, temporary)
    if sha256(temporary) != expected_hash:
        raise ClosureError("temporary copy hash mismatch")
    os.replace(temporary, destination)
    if sha256(destination) != expected_hash:
        raise ClosureError("installed copy hash mismatch")


def protected_vector() -> dict[str, object]:
    return optional_vector((ADMISSION_ASSET, FINAL_MAP, ADMISSION_MAP))


def run_editor(editor: Path, output: Path, stem: str, script: Path,
               marker: str, watchdog: int,
               environment: dict[str, str] | None = None) -> dict[str, object]:
    log = output / (stem + ".log")
    stdout_path = output / (stem + ".stdout.log")
    stderr_path = output / (stem + ".stderr.log")
    argv = [
        str(editor), str(UPROJECT), "-unattended", "-nop4", "-nosplash",
        "-nosound", "-nullrhi", "-stdout", "-FullStdOutLogOutput",
        "-ExecutePythonScript=" + str(script), "-abslog=" + str(log),
    ]
    child_environment = os.environ.copy()
    child_environment.update(environment or {})
    started = time.monotonic()
    process = subprocess.Popen(
        argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        encoding="utf-8", errors="replace", env=child_environment)
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
    forbidden = (
        "REPLICATED-DOOR-REFERENCE-AUTHOR-ERROR",
        "REPLICATED-DOOR-REFERENCE-READBACK-ERROR",
        "REPLICATED-DOOR-ASSET-READBACK-ERROR",
        "Ensure condition failed", "Assertion failed", "Fatal error",
        "LowLevelFatalError",
    )
    problems = [token for token in forbidden if token in combined]
    result = {
        "argv": argv, "exit_code": process.returncode,
        "timed_out": timed_out,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "marker": marker, "marker_present": marker in combined,
        "problems": problems, "log": str(log), "stdout": str(stdout_path),
        "stderr": str(stderr_path),
    }
    if timed_out or process.returncode != 0 or problems or marker not in combined:
        raise ClosureError("editor step failed %s: %r" % (stem, result))
    return result


def restore_baseline(baseline_vault: Path, output: Path,
                     baseline_hash: str) -> None:
    if FINAL_ASSET.is_file() and sha256(FINAL_ASSET) == baseline_hash:
        return
    if FINAL_ASSET.is_file():
        partial = output / "rollback" / "partial-live-reference.uasset"
        partial.parent.mkdir(parents=True, exist_ok=True)
        if os.path.lexists(partial):
            raise ClosureError("partial live quarantine exists")
        os.replace(FINAL_ASSET, partial)
    copy_verified(baseline_vault, FINAL_ASSET, baseline_hash)


def rollback(baseline_vault: Path, output: Path,
             baseline_hash: str) -> list[str]:
    errors: list[str] = []
    try:
        if os.path.lexists(REFERENCE_ASSET):
            partial = output / "rollback" / "partial-reference.uasset"
            partial.parent.mkdir(parents=True, exist_ok=True)
            if os.path.lexists(partial):
                raise ClosureError("partial reference quarantine exists")
            os.replace(REFERENCE_ASSET, partial)
    except Exception as exc:  # noqa: BLE001
        errors.append("reference quarantine: %s" % exc)
    try:
        if baseline_vault.is_file():
            restore_baseline(baseline_vault, output, baseline_hash)
    except Exception as exc:  # noqa: BLE001
        errors.append("baseline restore: %s" % exc)
    return errors


def preflight(editor: Path, output: Path) -> dict[str, object]:
    assert_no_writers()
    for required in (editor, UPROJECT, AUTHOR, REFERENCE_READBACK,
                     BASELINE_READBACK, FINAL_ASSET, FINAL_MAP,
                     ADMISSION_ASSET, ADMISSION_MAP):
        if not required.is_file():
            raise ClosureError("required input missing: %s" % required)
    if os.path.lexists(output) or os.path.lexists(REFERENCE_ASSET):
        raise ClosureError("output/reference must be absent")
    require_plain_ancestors(output)
    require_plain_ancestors(FINAL_ASSET)
    return {"baseline": facts(FINAL_ASSET), "protected": protected_vector()}


def close(editor: Path, output: Path, watchdog: int) -> None:
    initial = preflight(editor, output)
    output.mkdir(parents=True, exist_ok=False)
    manifest: dict[str, object] = {
        "schema": 1, "status": "running", "initial": initial, "steps": {},
    }
    write_json(output / "closure.json", manifest)
    baseline_hash = str(initial["baseline"]["sha256"])
    baseline_vault = output / "baseline-vault" / FINAL_ASSET.name
    authored_vault = output / "authored-vault" / FINAL_ASSET.name
    try:
        copy_verified(FINAL_ASSET, baseline_vault, baseline_hash)
        manifest["baseline_vault"] = facts(baseline_vault)
        steps = manifest["steps"]
        assert isinstance(steps, dict)
        steps["01-author-reference"] = run_editor(
            editor, output, "01-author-reference", AUTHOR, AUTHOR_MARKER,
            watchdog)
        authored = facts(FINAL_ASSET)
        if authored["sha256"] == baseline_hash:
            raise ClosureError("authored reference equals baseline bytes")
        if protected_vector() != initial["protected"]:
            raise ClosureError("reference author changed protected vector")
        manifest["authored"] = authored
        steps["02-cold-readback-reference"] = run_editor(
            editor, output, "02-cold-readback-reference", REFERENCE_READBACK,
            REFERENCE_MARKER, watchdog)
        if facts(FINAL_ASSET) != authored:
            raise ClosureError("cold solved readback changed live asset")
        copy_verified(FINAL_ASSET, authored_vault, str(authored["sha256"]))
        evidence = output / "evidence" / "reference-live.uasset"
        evidence.parent.mkdir(parents=True, exist_ok=True)
        os.replace(FINAL_ASSET, evidence)
        copy_verified(baseline_vault, FINAL_ASSET, baseline_hash)
        steps["03-cold-readback-baseline"] = run_editor(
            editor, output, "03-cold-readback-baseline", BASELINE_READBACK,
            BASELINE_MARKER, watchdog,
            {"CRAFTBENCH_DOOR_ASSET_MODE": "baseline"})
        if facts(FINAL_ASSET) != initial["baseline"]:
            raise ClosureError("baseline restoration hash mismatch")
        copy_verified(authored_vault, REFERENCE_ASSET,
                      str(authored["sha256"]))
        if facts(REFERENCE_ASSET) != authored:
            raise ClosureError("installed reference differs from authored bytes")
        if protected_vector() != initial["protected"]:
            raise ClosureError("final protected vector mismatch")
        manifest.update({
            "status": "pass", "reference": facts(REFERENCE_ASSET),
            "restored_baseline": facts(FINAL_ASSET),
            "final_protected": protected_vector(),
        })
        write_json(output / "closure.json", manifest)
        print("REPLICATED-DOOR-REFERENCE-CLOSURE-PASS baseline_restored=1 "
              "reference=1 protected_unchanged=1 output=%s" % output)
    except Exception as exc:
        recovery_errors = rollback(
            baseline_vault, output, baseline_hash) if baseline_vault.is_file() \
            else []
        manifest.update({"status": "fail", "error": str(exc),
                         "recovery_errors": recovery_errors})
        try:
            write_json(output / "closure.json", manifest)
        except Exception:
            pass
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--ue-root", type=Path, default=_UE_ROOT)
    parser.add_argument("--watchdog-seconds", type=int, default=720)
    parser.add_argument("--preflight-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.watchdog_seconds < 60:
        raise ClosureError("watchdog must be at least 60 seconds")
    editor = args.ue_root / "Engine" / "Binaries" / "Win64" \
        / "UnrealEditor-Cmd.exe"
    output = Path(os.path.abspath(args.output))
    initial = preflight(editor, output)
    if args.preflight_only:
        print("REPLICATED-DOOR-REFERENCE-PREFLIGHT-PASS baseline=1 "
              "protected=3 final_map=1 reference_absent=1 output_absent=1")
        return 0
    close(editor, output, args.watchdog_seconds)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ClosureError as exc:
        print("REPLICATED-DOOR-REFERENCE-CLOSURE-ERROR %s" % exc,
              file=sys.stderr)
        raise SystemExit(1)

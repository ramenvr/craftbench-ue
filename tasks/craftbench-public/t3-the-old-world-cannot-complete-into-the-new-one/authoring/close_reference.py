"""Recoverable reference/empty behavior closure for the epoch-travel task.

The live candidate source is always restored byte-for-byte in ``finally``.
Build and behavior steps are kept as separate evidence files under a fresh
external output directory.
"""

from __future__ import annotations

import argparse
import hashlib
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
from epoch_travel_common import (  # noqa: E402
    LIVE_SOURCE, MAP_ROOT, PROJECT, REFERENCE_SOURCE, map_vector,
    record_vector,
)

BUILD = _UE_ROOT / "Engine/Build/BatchFiles/Build.bat"
RUN_TRAVEL = HERE / "run_travel.py"
SOURCE_NAMES = ("EpochAssetWorldSubsystem.h", "EpochAssetWorldSubsystem.cpp")
EXPECTED_EMPTY_FAILURE = "GATE[NewWorldResolvesItsAssignedRecord]=FAIL"


class ClosureError(RuntimeError):
    """A fail-closed reference closure boundary was crossed."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def file_vector(root: Path) -> dict[str, dict[str, object]]:
    return {
        name: {"size": (root / name).stat().st_size,
               "sha256": sha256(root / name)}
        for name in SOURCE_NAMES
    }


def is_reparse(path: Path) -> bool:
    info = path.lstat()
    return path.is_symlink() or bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def require_plain_ancestors(path: Path) -> None:
    current = Path(os.path.abspath(os.fspath(path)))
    while not current.exists():
        current = current.parent
    while True:
        if is_reparse(current):
            raise ClosureError("reparse ancestor rejected: %s" % current)
        if current.parent == current:
            return
        current = current.parent


def assert_no_writers() -> None:
    query = (
        "$p=Get-CimInstance Win32_Process | Where-Object { "
        "$_.Name -match "
        "'^(UnrealEditor|UnrealEditor-Cmd|UnrealBuildTool|Build|cl|link)"
        "\\.exe$' }; "
        "$p | ForEach-Object { "
        "\"$($_.ProcessId)|$($_.Name)|$($_.CommandLine)\" }")
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", query],
        capture_output=True, text=True, check=False)
    active = [line for line in result.stdout.splitlines() if line.strip()]
    if result.returncode != 0 or active:
        raise ClosureError("heavy writer active/query failed: %r" % active)


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def atomic_copy(source: Path, destination: Path) -> None:
    temporary = destination.with_name(destination.name + ".cbtmp-overlay")
    if os.path.lexists(temporary):
        raise ClosureError("stale overlay temporary: %s" % temporary)
    shutil.copy2(source, temporary)
    os.replace(temporary, destination)
    # UBT's action graph can otherwise accept the restored file's old mtime
    # and leave the previously linked reference object in place.
    os.utime(destination, None)


def run_process(argv: list[str], stdout_path: Path, timeout: int) -> dict:
    started = time.monotonic()
    timed_out = False
    print("EPOCH-CLOSURE-STEP-START command=%s" % argv[0], flush=True)
    with stdout_path.open("w", encoding="utf-8") as stream:
        process = subprocess.Popen(
            argv, stdout=stream, stderr=subprocess.STDOUT, text=True,
            encoding="utf-8", errors="replace")
        try:
            returncode = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True, text=True, check=False, timeout=30)
            try:
                returncode = process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                returncode = 124
    result = {
        "argv": argv, "exit_code": returncode, "timed_out": timed_out,
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "stdout": str(stdout_path),
    }
    print("EPOCH-CLOSURE-STEP-END exit=%d timed_out=%d elapsed=%.2f log=%s"
          % (returncode, int(timed_out), result["elapsed_seconds"],
             stdout_path), flush=True)
    return result


def build_target(output: Path, label: str, target: str,
                 watchdog: int) -> dict:
    argv = [
        str(BUILD), target, "Win64", "Development", str(PROJECT),
        "-WaitMutex", "-NoHotReloadFromIDE", "-NoUBA",
        "-MaxParallelActions=2",
    ]
    result = run_process(argv, output / (label + ".log"), watchdog)
    text = Path(result["stdout"]).read_text(
        encoding="utf-8", errors="replace")
    compiled_candidate = "Compile [x64] EpochAssetWorldSubsystem.cpp" in text
    if result["exit_code"] != 0 or result["timed_out"] \
            or "Result: Succeeded" not in text or not compiled_candidate:
        raise ClosureError("build failed: %s" % label)
    result["compiled_candidate"] = True
    return result


def run_behavior(output: Path, label: str, watchdog: int,
                 expect_pass: bool) -> dict:
    run_output = output / label
    argv = [
        sys.executable, str(RUN_TRAVEL), "--project", str(PROJECT),
        "--ue-root", str(BUILD.parents[3]), "--output", str(run_output),
        "--watchdog-seconds", str(watchdog),
    ]
    result = run_process(argv, output / (label + ".runner.log"),
                         watchdog + 60)
    aggregate_path = run_output / "aggregate.json"
    if not aggregate_path.is_file():
        raise ClosureError("behavior aggregate missing: %s" % label)
    aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
    travel_text = (run_output / "travel.stdout.log").read_text(
        encoding="utf-8", errors="replace")
    if expect_pass:
        valid = (result["exit_code"] == 0
                 and aggregate.get("status") == "pass"
                 and aggregate.get("failure_kind") == "none")
    else:
        other_gates = (
            "OldWorldSubsystemDeinitializesOnce",
            "OldEpochCompletionCannotMutateNewWorld",
            "TravelLeavesNoOldWorldRootedObjects",
        )
        valid = (result["exit_code"] == 1
                 and aggregate.get("status") == "fail"
                 and aggregate.get("failure_kind") == "behavior"
                 and travel_text.count(EXPECTED_EMPTY_FAILURE) == 1
                 and all(travel_text.count("GATE[%s]=PASS" % gate) == 1
                         for gate in other_gates)
                 and "EPOCH-TRAVEL-HARNESS-ERROR" not in travel_text)
    if not valid:
        raise ClosureError("unexpected behavior result %s: %r" %
                           (label, aggregate))
    result["aggregate"] = aggregate
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--watchdog-seconds", type=int, default=900)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    if args.watchdog_seconds < 120:
        parser.error("watchdog must be at least 120 seconds")
    return args


def main() -> int:
    args = parse_args()
    output = args.output.resolve()
    assert_no_writers()
    for path in (BUILD, PROJECT, RUN_TRAVEL):
        if not path.is_file():
            raise ClosureError("required file missing: %s" % path)
    if os.path.lexists(output):
        raise ClosureError("output must be fresh: %s" % output)
    require_plain_ancestors(output)
    for root in (LIVE_SOURCE, REFERENCE_SOURCE):
        if sorted(path.name for path in root.iterdir() if path.is_file()) \
                != sorted(SOURCE_NAMES):
            if root == LIVE_SOURCE:
                # The live directory also owns protected reporter/fixtures.
                expected = sorted(SOURCE_NAMES + (
                    "EpochTravelProtectedTypes.h",
                    "EpochTravelProtectedTypes.cpp"))
                actual = sorted(path.name for path in root.iterdir()
                                if path.is_file())
                if actual != expected:
                    raise ClosureError("live source inventory mismatch: %r"
                                       % actual)
            else:
                raise ClosureError("reference source inventory mismatch")
    baseline = file_vector(LIVE_SOURCE)
    reference = file_vector(REFERENCE_SOURCE)
    immutable = {"maps": map_vector(), "records": record_vector()}
    if baseline == reference:
        raise ClosureError("reference is byte-identical to empty scaffold")
    if args.preflight_only:
        print("EPOCH-REFERENCE-PREFLIGHT-PASS baseline=2 reference=2 "
              "maps=2 records=2 output_absent=1", flush=True)
        return 0

    output.mkdir(parents=True, exist_ok=False)
    vault = output / "baseline-vault"
    vault.mkdir()
    for name in SOURCE_NAMES:
        shutil.copy2(LIVE_SOURCE / name, vault / name)
    manifest: dict[str, object] = {
        "status": "running", "baseline": baseline,
        "reference": reference, "immutable": immutable, "steps": {},
    }
    write_json(output / "closure.json", manifest)
    restored = False
    reference_error: Exception | None = None
    try:
        for name in SOURCE_NAMES:
            atomic_copy(REFERENCE_SOURCE / name, LIVE_SOURCE / name)
        if file_vector(LIVE_SOURCE) != reference:
            raise ClosureError("reference overlay hash mismatch")
        manifest["steps"]["reference_editor_build"] = build_target(
            output, "01-reference-editor-build", "ThirdPersonEditor",
            args.watchdog_seconds)
        manifest["steps"]["reference_game_build"] = build_target(
            output, "02-reference-game-build", "ThirdPerson",
            args.watchdog_seconds)
        manifest["steps"]["reference_behavior"] = run_behavior(
            output, "03-reference-behavior", args.watchdog_seconds, True)
    except Exception as exc:
        reference_error = exc
        manifest["reference_error"] = str(exc)
    finally:
        for name in SOURCE_NAMES:
            atomic_copy(vault / name, LIVE_SOURCE / name)
        restored = file_vector(LIVE_SOURCE) == baseline
        manifest["restored_in_finally"] = restored
        write_json(output / "closure.json", manifest)
    if not restored:
        raise ClosureError("baseline restoration failed")
    if {"maps": map_vector(), "records": record_vector()} != immutable:
        raise ClosureError("authored inputs changed during reference leg")
    manifest["steps"]["baseline_editor_build"] = build_target(
        output, "04-baseline-editor-build", "ThirdPersonEditor",
        args.watchdog_seconds)
    manifest["steps"]["baseline_game_build"] = build_target(
        output, "05-baseline-game-build", "ThirdPerson",
        args.watchdog_seconds)
    if reference_error is not None:
        manifest["status"] = "fail"
        write_json(output / "closure.json", manifest)
        raise reference_error
    manifest["steps"]["empty_behavior"] = run_behavior(
        output, "06-empty-behavior", args.watchdog_seconds, False)
    if file_vector(LIVE_SOURCE) != baseline or \
            {"maps": map_vector(), "records": record_vector()} != immutable:
        raise ClosureError("final source/input vector mismatch")
    manifest.update({"status": "pass", "final_baseline": baseline,
                     "final_immutable": immutable})
    write_json(output / "closure.json", manifest)
    print("EPOCH-REFERENCE-CLOSURE-PASS reference=1 empty_named_fail=1 "
          "baseline_restored=1 maps=2 records=2", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

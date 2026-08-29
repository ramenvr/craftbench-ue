"""Run the exact two verifier-owned district-streaming admission fixtures.

The broad filter is intentionally the exact admission-map Automation path.  The
authoritative JSON report must contain precisely the Alpha and Beta fixtures;
the runner never guesses or accepts another map or display name.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time
from typing import Any


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
VERIFY = REPO / "tools" / "verify-single"
TASK_ID = "t3-only-the-requested-district-enters-and-leaves-the-world"
UE_ROOT = Path(os.environ.get("CB_UE_ROOT", r"C:\Program Files\Epic Games\UE_5.8"))
PROJECT = REPO / "UE-projects" / "ThirdPerson" / "ThirdPerson.uproject"
CONTENT = PROJECT.parent / "Content"
MAP_NAME = "L_DistrictStreamingAdmission"
MAP_PACKAGE = "/Game/__CraftBenchAdmission/%s/%s" % (TASK_ID, MAP_NAME)
EXACT_FILTER = "Project.Functional Tests.__CraftBenchAdmission.%s.%s" % (
    TASK_ID, MAP_NAME)
EXPECTED_DISPLAYS = {
    "DistrictStreamingAlpha",
    "DistrictStreamingBeta",
}
EXPECTED_FULL_PATHS = {
    EXACT_FILTER + "." + display for display in EXPECTED_DISPLAYS
}
REFERENCE = HERE.parent / "reference"

EXPECTED = {
    CONTENT / "Tasks" / TASK_ID / "BP_DistrictStreamLoader.uasset":
        "BAE83D5C585EF6F7E916CCE540214F51D9D692574EB9BD41B2D89E325AEB9A9B",
    CONTENT / "Maps" / TASK_ID / "Support" / "L_DistrictAlpha.umap":
        "487D05B80BC8628CE248198A7140420D129280AFE30A1207F8F6BC713240ED7F",
    CONTENT / "Maps" / TASK_ID / "Support" / "L_DistrictBeta.umap":
        "273C35AA564B14559942A56F7A5B9272606018149CD83D6C06C95A25DFE9C7E8",
    CONTENT / "__CraftBenchAdmission" / TASK_ID
        / "L_DistrictStreamingAdmission.umap":
        "F8BE965DCC1972BC23D59F3A5C43F9E3E059FE6118187EA5738E484B7C60E065",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def is_reparse(path: Path) -> bool:
    attributes = getattr(path.lstat(), "st_file_attributes", 0)
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def require_plain(path: Path) -> None:
    current = Path(os.path.abspath(os.fspath(path)))
    stop = Path(os.path.abspath(os.fspath(REPO)))
    while True:
        if not current.exists():
            raise RuntimeError("protected path missing: %s" % current)
        if current.is_symlink() or is_reparse(current):
            raise RuntimeError("protected reparse path: %s" % current)
        if current == stop:
            return
        if stop not in current.parents:
            raise RuntimeError("protected path escaped repository: %s" % path)
        current = current.parent


def snapshot() -> dict[str, dict[str, Any]]:
    if os.path.lexists(REFERENCE):
        raise RuntimeError("reference must remain absent: %s" % REFERENCE)
    vector: dict[str, dict[str, Any]] = {}
    for path, expected_hash in EXPECTED.items():
        require_plain(path)
        actual_hash = sha256(path)
        if actual_hash != expected_hash:
            raise RuntimeError("protected hash mismatch %s actual=%s" %
                               (path, actual_hash))
        vector[path.relative_to(REPO).as_posix()] = {
            "size": path.stat().st_size,
            "sha256": actual_hash,
        }
    return vector


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True,
                               default=str) + "\n", encoding="utf-8")


def child_main(output: Path) -> int:
    sys.path.insert(0, str(VERIFY))
    sys.path.insert(0, str(VERIFY / "layers"))
    from l2_pie import run_l2  # noqa: PLC0415

    result = run_l2(
        ue_root=UE_ROOT,
        project_path=PROJECT,
        test_filter=EXACT_FILTER,
        log_path=output / "l2.log",
        report_dir=output / "report",
        map_name=MAP_NAME,
        map_package_path=MAP_PACKAGE,
        use_nullrhi=True,
        fps=60,
        timeout_seconds=3600.0,
        expected_test_count=2,
    )
    payload = dataclasses.asdict(result)
    write_json(output / "l2_result.json", payload)
    print("DISTRICT-STREAMING-ADMISSION-CHILD " +
          json.dumps(payload, sort_keys=True, default=str), flush=True)
    return 0 if result.status == "pass" else 1


def kill_tree(process: subprocess.Popen[Any]) -> dict[str, Any]:
    evidence: dict[str, Any] = {"pid": process.pid}
    if process.poll() is not None:
        evidence.update(method="already-exited", exit_code=process.returncode)
        return evidence
    completed = subprocess.run(
        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
        capture_output=True, text=True, check=False, timeout=30)
    evidence.update(method="taskkill-exact-tree",
                    taskkill_exit=completed.returncode,
                    output=(completed.stdout + completed.stderr).strip())
    try:
        process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=30)
        evidence["fallback"] = "process-kill"
    evidence["exit_code"] = process.returncode
    return evidence


def read_json(path: Path, problems: list[str]) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(value, dict):
            raise ValueError("root is not an object")
        return value
    except Exception as exc:  # noqa: BLE001
        problems.append("unreadable JSON %s: %r" % (path, exc))
        return {}


def audit(output: Path, before: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    problems: list[str] = []
    result = read_json(output / "l2_result.json", problems)
    index_path = output / "report" / "index.json"
    index = read_json(index_path, problems)
    tests = index.get("tests", [])
    if not isinstance(tests, list) or len(tests) != 2:
        problems.append("JSON test count=%r expected=2" %
                        (len(tests) if isinstance(tests, list) else tests))
        tests = []
    actual_displays = {
        item.get("testDisplayName") for item in tests if isinstance(item, dict)
    }
    actual_paths = {
        item.get("fullTestPath") for item in tests if isinstance(item, dict)
    }
    if actual_displays != EXPECTED_DISPLAYS:
        problems.append("display set mismatch: %r" % sorted(actual_displays))
    if actual_paths != EXPECTED_FULL_PATHS:
        problems.append("full path set mismatch: %r" % sorted(actual_paths))
    if any(item.get("state") != "Success" for item in tests
           if isinstance(item, dict)):
        problems.append("one or more exact test states were not Success")
    if (index.get("succeeded") != 2 or index.get("failed") != 0
            or int(index.get("succeededWithWarnings", 0) or 0) != 0
            or int(index.get("notRun", 0) or 0) != 0):
        problems.append("wrong Automation aggregate: %r" % index)
    if (result.get("status") != "pass" or result.get("tests_run") != 2
            or result.get("tests_passed") != 2
            or result.get("tests_failed") != 0
            or result.get("result_source") != "json"):
        problems.append("L2 result/count/source mismatch: %r" % result)

    log_path = output / "l2.log"
    log_text = (log_path.read_text(encoding="utf-8", errors="replace")
                if log_path.is_file() else "")
    for district in ("Alpha", "Beta"):
        marker = ("DISTRICT-STREAMING-SUCCEEDED request=%s gates=5 "
                  "runtime_observed=1" % district)
        if log_text.count(marker) != 1:
            problems.append("success marker %s count=%d expected=1" %
                            (district, log_text.count(marker)))
    telemetry_lines = [line for line in log_text.splitlines()
                       if "DISTRICT-STREAMING-TELEMETRY" in line]
    telemetry_pairs: set[tuple[str, int]] = set()
    for line in telemetry_lines:
        request = next((name for name in ("Alpha", "Beta")
                        if ("request=" + name) in line), "")
        checkpoint = next((index for index in range(7)
                           if ("cp=%d " % index) in line), -1)
        if request and checkpoint >= 0:
            telemetry_pairs.add((request, checkpoint))
    expected_pairs = {(request, checkpoint)
                      for request in ("Alpha", "Beta")
                      for checkpoint in range(7)}
    if telemetry_pairs != expected_pairs:
        problems.append("telemetry pair set mismatch: %r" %
                        sorted(telemetry_pairs))
    for token in ("NamedSectionInactiveAtStart:",
                  "ExactActorsEnterViaNamedSection:",
                  "UnrelatedSectionsUnchanged:",
                  "ExactActorsLeaveAfterUnload:",
                  "ReloadCreatesFreshSectionActors:",
                  "HARNESS-PRECONDITION", "Ensure condition failed",
                  "Assertion failed", "Fatal error", "LowLevelFatalError",
                  "L2 TIMEOUT"):
        if token in log_text:
            problems.append("forbidden admission marker: " + token)

    try:
        after = snapshot()
    except Exception as exc:  # noqa: BLE001
        after = {"snapshot_error": repr(exc)}
        problems.append("protected postflight failed: %r" % (exc,))
    if after != before:
        problems.append("protected four-file snapshot changed")
    summary = {
        "filter": EXACT_FILTER,
        "expected_test_count": 2,
        "expected_displays": sorted(EXPECTED_DISPLAYS),
        "expected_full_paths": sorted(EXPECTED_FULL_PATHS),
        "map_package": MAP_PACKAGE,
        "rhi": "null",
        "fps": 60,
        "result": result,
        "report": {"path": str(index_path), "tests": tests,
                   "succeeded": index.get("succeeded"),
                   "failed": index.get("failed")},
        "telemetry": telemetry_lines,
        "telemetry_pairs": sorted(telemetry_pairs),
        "protected_before": before,
        "protected_after": after,
        "reference_absent": not os.path.lexists(REFERENCE),
        "problems": problems,
    }
    write_json(output / "audit.json", summary)
    return not problems, summary


def parent_main(args: argparse.Namespace) -> int:
    if args.watchdog_seconds < 60:
        raise RuntimeError("watchdog must be at least 60 seconds")
    output = args.output.resolve()
    if os.path.lexists(output):
        raise RuntimeError("fresh output already exists: %s" % output)
    before = snapshot()
    output.mkdir(parents=True)
    write_json(output / "preflight.json", {
        "filter": EXACT_FILTER, "expected_test_count": 2,
        "map_package": MAP_PACKAGE, "rhi": "null", "fps": 60,
        "watchdog_seconds": args.watchdog_seconds,
        "protected_before": before,
    })
    command = [sys.executable, str(Path(__file__).resolve()), "--child",
               "--output", str(output)]
    with (output / "runner.stdout.log").open(
            "w", encoding="utf-8", errors="replace") as stream:
        process = subprocess.Popen(command, cwd=REPO, stdout=stream,
                                   stderr=subprocess.STDOUT, text=True)
        try:
            child_exit = process.wait(timeout=args.watchdog_seconds)
        except subprocess.TimeoutExpired:
            evidence = {
                "verdict": "INFRA_FREEZE", "filter": EXACT_FILTER,
                "elapsed_seconds": args.watchdog_seconds,
                "kill": kill_tree(process), "protected_before": before,
            }
            try:
                evidence["protected_after"] = snapshot()
            except Exception as exc:  # noqa: BLE001
                evidence["protected_after_error"] = repr(exc)
            write_json(output / "watchdog.json", evidence)
            print("DISTRICT-STREAMING-ADMISSION-INFRA-FREEZE " +
                  json.dumps(evidence, sort_keys=True), flush=True)
            return 4
    ok, summary = audit(output, before)
    if child_exit != 0:
        summary["problems"].append("child exit=%d expected=0" % child_exit)
        write_json(output / "audit.json", summary)
        ok = False
    if ok:
        print("DISTRICT-STREAMING-ADMISSION-RUNNER-PASS exact_count=2 "
              "state=Success alpha=1 beta=1 telemetry=14 hashes_unchanged=1 "
              "reference_absent=1 output=%s" % output, flush=True)
        return 0
    for problem in summary["problems"]:
        print("DISTRICT-STREAMING-ADMISSION-RUNNER-ERROR " + problem,
              flush=True)
    return 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--watchdog-seconds", type=int, default=720)
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.child:
        return child_main(args.output.resolve())
    try:
        return parent_main(args)
    except Exception as exc:  # noqa: BLE001
        print("DISTRICT-STREAMING-ADMISSION-RUNNER-ERROR %r" % (exc,),
              flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

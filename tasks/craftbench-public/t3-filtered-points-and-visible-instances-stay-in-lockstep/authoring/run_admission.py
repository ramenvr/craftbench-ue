"""Run one monitored exact-two PCG admission round with immutable locks."""

from __future__ import annotations

import argparse
import dataclasses
import json
from pathlib import Path
import subprocess
import sys
import time
import os


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from pcg_task_common import (  # noqa: E402
    ADMISSION_MAP, PROJECT, TASK_ID, admission_graph_vector,
    admission_map_vector, immutable_vector,
)

VERIFY = REPO / "tools" / "verify-single"
UE_ROOT = Path(os.environ.get("CB_UE_ROOT", r"C:\Program Files\Epic Games\UE_5.8"))
MAP_NAME = "L_FilteredPointInstancesAdmission"
TEST_FILTER = f"Project.Functional Tests.Maps.{TASK_ID}.{MAP_NAME}"
EXPECTED_TESTS = {
    TEST_FILTER + ".FilteredPointInstancesFunctionalTestA",
    TEST_FILTER + ".FilteredPointInstancesFunctionalTestB",
}
GATES = (
    "BelowThresholdPointsRejected",
    "ExclusionMarkedPointsRejected",
    "AllEligiblePointsRetained",
    "EligiblePointsNotDuplicated",
    "SpawnCountMatchesFilteredOutput",
    "SpawnTransformsMatchFilteredPoints",
)


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True,
                               default=str) + "\n", encoding="utf-8")


def protected_vector() -> dict[str, object]:
    return {
        "graph": admission_graph_vector(),
        "map": admission_map_vector(),
        "immutable": immutable_vector(),
    }


def child_command(output: Path) -> list[str]:
    return [sys.executable, "-B", str(Path(__file__).resolve()),
            "--child", "--output", str(output)]


def child_main(output: Path) -> int:
    sys.path.insert(0, str(VERIFY))
    sys.path.insert(0, str(VERIFY / "layers"))
    from l2_pie import run_l2  # noqa: PLC0415

    result = run_l2(
        ue_root=UE_ROOT,
        project_path=PROJECT,
        test_filter=TEST_FILTER,
        log_path=output / "l2.log",
        report_dir=output / "report",
        map_name=MAP_NAME,
        map_package_path=ADMISSION_MAP,
        use_nullrhi=True,
        render_offscreen=False,
        fps=60,
        timeout_seconds=700.0,
        expected_test_count=2,
    )
    write_json(output / "l2_result.json", dataclasses.asdict(result))
    return 0 if result.status == "pass" else 1


def kill_tree(process: subprocess.Popen) -> dict[str, object]:
    evidence: dict[str, object] = {"pid": process.pid}
    if process.poll() is not None:
        evidence.update(method="already-exited", exit_code=process.returncode)
        return evidence
    killed = subprocess.run(
        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
        capture_output=True, text=True, check=False, timeout=30)
    process.wait(timeout=30)
    evidence.update(method="taskkill-exact-tree",
                    taskkill_exit=killed.returncode,
                    output=(killed.stdout + killed.stderr).strip(),
                    exit_code=process.returncode)
    return evidence


def audit(output: Path, before: dict[str, object]) -> tuple[bool, dict]:
    problems: list[str] = []
    try:
        result = json.loads((output / "l2_result.json").read_text(
            encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        result = {}
        problems.append("l2_result unreadable: %r" % exc)
    try:
        index = json.loads((output / "report" / "index.json").read_text(
            encoding="utf-8-sig"))
    except Exception as exc:  # noqa: BLE001
        index = {}
        problems.append("automation index unreadable: %r" % exc)
    tests = index.get("tests", []) if isinstance(index, dict) else []
    observed_paths = {test.get("fullTestPath") for test in tests}
    if len(tests) != 2 or observed_paths != EXPECTED_TESTS \
            or any(test.get("state") != "Success" for test in tests):
        problems.append("exact test set/state mismatch: %r" % tests)
    if index.get("succeeded") != 2 or index.get("failed") != 0:
        problems.append("automation aggregate is not exact 2/0")
    if result.get("status") != "pass" or result.get("tests_run") != 2 \
            or result.get("tests_passed") != 2 \
            or result.get("result_source") != "json":
        problems.append("L2 result/count/source mismatch: %r" % result)
    log_path = output / "l2.log"
    log = log_path.read_text(encoding="utf-8", errors="replace") \
        if log_path.is_file() else ""
    for policy in ("A", "B"):
        token = f"FILTERED-POINT-PCG-SUCCEEDED policy={policy} gates=6/6"
        if log.count(token) != 1:
            problems.append(f"success marker {policy} count={log.count(token)}")
    for gate in GATES:
        token = f"GATE[{gate}]=PASS"
        if log.count(token) != 2:
            problems.append(f"gate marker {gate} count={log.count(token)}")
    for token in ("HARNESS-PRECONDITION", "GATE[", "Ensure condition failed",
                  "Fatal error", "LowLevelFatalError", "L2 TIMEOUT"):
        if token == "GATE[":
            if "=FAIL" in log:
                problems.append("named gate failure present")
        elif token in log:
            problems.append("forbidden log token: " + token)
    after = protected_vector()
    if after != before:
        problems.append("protected hash vector changed")
    summary = {
        "filter": TEST_FILTER,
        "expected_tests": sorted(EXPECTED_TESTS),
        "expected_count": 2,
        "rhi": "null",
        "fps": 60,
        "world_clock": True,
        "gates": list(GATES),
        "result": result,
        "automation": index,
        "hashes_before": before,
        "hashes_after": after,
        "telemetry": [line for line in log.splitlines()
                      if "FILTERED-POINT-PCG" in line or "GATE[" in line],
        "promotion_decision": "HOLD-UNTIL-REPEATED-CALIBRATION",
        "problems": problems,
    }
    write_json(output / "audit.json", summary)
    return not problems, summary


def parent_main(args: argparse.Namespace) -> int:
    output = args.output.resolve()
    if output.exists():
        raise SystemExit("fresh output already exists: %s" % output)
    if args.watchdog_seconds < 60:
        raise SystemExit("watchdog must be >= 60 seconds")
    output.mkdir(parents=True)
    before = protected_vector()
    write_json(output / "preflight.json", {
        "filter": TEST_FILTER,
        "expected_tests": sorted(EXPECTED_TESTS),
        "expected_count": 2,
        "rhi": "null",
        "fps": 60,
        "watchdog_seconds": args.watchdog_seconds,
        "hashes_before": before,
    })
    started = time.time()
    with (output / "runner.stdout.log").open(
            "w", encoding="utf-8", errors="replace") as stream:
        process = subprocess.Popen(child_command(output), cwd=REPO,
                                   stdout=stream,
                                   stderr=subprocess.STDOUT, text=True)
        try:
            child_exit = process.wait(timeout=args.watchdog_seconds)
        except subprocess.TimeoutExpired:
            write_json(output / "watchdog.json", {
                "verdict": "INFRA_FREEZE",
                "elapsed_seconds": time.time() - started,
                "kill": kill_tree(process),
                "hashes_before": before,
                "hashes_after": protected_vector(),
            })
            return 4
    ok, evidence = audit(output, before)
    print("FILTERED-POINT-ADMISSION-RUNNER child_exit=%d ok=%d output=%s" %
          (child_exit, 1 if ok else 0, output))
    for problem in evidence["problems"]:
        print("FILTERED-POINT-ADMISSION-AUDIT-FAILED " + problem)
    return 0 if ok else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--watchdog-seconds", type=float, default=720.0)
    parser.add_argument("--child", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    parsed = parse_args()
    raise SystemExit(child_main(parsed.output) if parsed.child
                     else parent_main(parsed))

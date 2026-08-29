"""Run exactly one guard admission test with an external parent watchdog."""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
from pathlib import Path
import subprocess
import sys
import time


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from guard_authoring_common import (  # noqa: E402
    ADMISSION_MAP, REPO, PROJECT, exact_admission_asset_vector,
    require_protected_absent, sha256, stock_vector,
)

TASK_ID = "t3-the-guard-resumes-patrol-after-the-chase"
UE_ROOT = Path(os.environ.get("CB_UE_ROOT", r"C:\Program Files\Epic Games\UE_5.8"))
VERIFY = REPO / "tools" / "verify-single"
MAP_NAME = "L_GuardPatrolChaseAdmission"
MAP_PACKAGE = "/Game/Maps/%s/%s" % (TASK_ID, MAP_NAME)
EXACT_FILTER = (
    "Project.Functional Tests.Maps.%s.%s."
    "GuardPatrolChaseAdmissionTest" % (TASK_ID, MAP_NAME))
EXPECTED_DISPLAY = "GuardPatrolChaseAdmissionTest"
SUCCESS_MARKER = (
    "GUARD-PATROL-CHASE-admission-PASS "
    "PrioritySelectorAndDecoratorsAuthored "
    "TrueKeyAbortsPatrolAndStartsChase ChaseClosesDistance "
    "ResetFalseExitsChase PatrolResumesAfterReset")


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True,
                               default=str) + "\n", encoding="utf-8")


def snapshot() -> dict[str, object]:
    require_protected_absent(admission_map=False)
    if not ADMISSION_MAP.is_file() or ADMISSION_MAP.is_symlink():
        raise RuntimeError("admission map missing/non-regular")
    return {
        "map": sha256(ADMISSION_MAP),
        "assets": exact_admission_asset_vector(),
        "stock": stock_vector(),
        "reference_absent": True,
        "final_absent": True,
    }


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
        use_nullrhi=False,
        fps=60,
        timeout_seconds=3600.0,
        expected_test_count=1,
    )
    payload = dataclasses.asdict(result)
    write_json(output / "l2_result.json", payload)
    print("GUARD-ADMISSION-CHILD " +
          json.dumps(payload, sort_keys=True, default=str), flush=True)
    return 0 if result.status == "pass" else 1


def kill_owned_tree(process: subprocess.Popen) -> dict[str, object]:
    evidence: dict[str, object] = {"pid": process.pid}
    if process.poll() is not None:
        evidence.update(method="already-exited", exit_code=process.returncode)
        return evidence
    completed = subprocess.run(
        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
        capture_output=True, text=True, check=False, timeout=30)
    evidence.update(
        method="taskkill-exact-owned-tree", taskkill_exit=completed.returncode,
        output=(completed.stdout + completed.stderr).strip())
    try:
        process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=30)
        evidence["fallback"] = "direct-child-kill"
    evidence["exit_code"] = process.returncode
    return evidence


def load_object(path: Path, problems: list[str]) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(value, dict):
            raise ValueError("root is not an object")
        return value
    except Exception as exc:  # noqa: BLE001
        problems.append("unreadable JSON %s: %r" % (path, exc))
        return {}


def audit(output: Path, before: dict[str, object], child_exit: int):
    problems: list[str] = []
    result = load_object(output / "l2_result.json", problems)
    report_path = output / "report" / "index.json"
    report = load_object(report_path, problems)
    tests = report.get("tests", [])
    if not isinstance(tests, list) or len(tests) != 1:
        problems.append("exact JSON test count is not one")
    else:
        test = tests[0] if isinstance(tests[0], dict) else {}
        if test.get("fullTestPath") != EXACT_FILTER:
            problems.append("wrong fullTestPath: %r" % test.get("fullTestPath"))
        if test.get("testDisplayName") != EXPECTED_DISPLAY:
            problems.append("wrong display: %r" % test.get("testDisplayName"))
        if test.get("state") != "Success":
            problems.append("wrong exact test state: %r" % test.get("state"))
    if (result.get("status") != "pass" or result.get("tests_run") != 1 or
            result.get("tests_passed") != 1 or
            result.get("tests_failed") != 0 or
            result.get("result_source") != "json"):
        problems.append("L2 result/count/source mismatch: %r" % result)
    if child_exit != 0:
        problems.append("child exit=%d" % child_exit)

    log_path = output / "l2.log"
    log_text = log_path.read_text(encoding="utf-8", errors="replace") \
        if log_path.is_file() else ""
    if log_text.count(SUCCESS_MARKER) != 1:
        problems.append("terminal success marker count=%d" %
                        log_text.count(SUCCESS_MARKER))
    for token in ("GATE[", "HARNESS-PRECONDITION", "Ensure condition failed",
                  "Assertion failed", "Fatal error", "LowLevelFatalError",
                  "L2 TIMEOUT"):
        if token in log_text:
            problems.append("forbidden failure marker: " + token)
    try:
        after = snapshot()
    except Exception as exc:  # noqa: BLE001
        after = {"snapshot_error": repr(exc)}
        problems.append("postflight snapshot failed: %r" % (exc,))
    if after != before:
        problems.append("map/assets/stock hashes changed")

    telemetry = [line for line in log_text.splitlines()
                 if "GUARD-PATROL-CHASE-" in line or "GATE[" in line or
                 "HARNESS-PRECONDITION" in line]
    audit_value = {
        "filter": EXACT_FILTER,
        "expected_display": EXPECTED_DISPLAY,
        "expected_count": 1,
        "map_package": MAP_PACKAGE,
        "rhi": "real",
        "fps": 60,
        "result": result,
        "report": report,
        "protected_before": before,
        "protected_after": after,
        "telemetry": telemetry,
        "problems": problems,
    }
    write_json(output / "audit.json", audit_value)
    return not problems, audit_value


def parent_main(args: argparse.Namespace) -> int:
    if args.watchdog_seconds < 60:
        raise RuntimeError("watchdog must be at least 60 seconds")
    output = args.output.resolve()
    if output.exists() or os.path.lexists(output):
        raise RuntimeError("fresh output already exists: %s" % output)
    before = snapshot()
    output.mkdir(parents=True)
    write_json(output / "preflight.json", {
        "filter": EXACT_FILTER,
        "expected_display": EXPECTED_DISPLAY,
        "expected_count": 1,
        "map_package": MAP_PACKAGE,
        "rhi": "real",
        "fps": 60,
        "watchdog_seconds": args.watchdog_seconds,
        "protected_before": before,
    })
    command = [sys.executable, str(Path(__file__).resolve()), "--child",
               "--output", str(output)]
    with (output / "runner.stdout.log").open(
            "w", encoding="utf-8", errors="replace") as stream:
        process = subprocess.Popen(command, cwd=REPO, stdout=stream,
                                   stderr=subprocess.STDOUT, text=True)
        started = time.monotonic()
        try:
            child_exit = process.wait(timeout=args.watchdog_seconds)
        except subprocess.TimeoutExpired:
            evidence = {
                "verdict": "INFRA_FREEZE",
                "elapsed_seconds": time.monotonic() - started,
                "deadline_seconds": args.watchdog_seconds,
                "filter": EXACT_FILTER,
                "kill": kill_owned_tree(process),
                "protected_before": before,
            }
            try:
                evidence["protected_after"] = snapshot()
            except Exception as exc:  # noqa: BLE001
                evidence["protected_after_error"] = repr(exc)
            write_json(output / "watchdog.json", evidence)
            print("GUARD-ADMISSION-INFRA-FREEZE " +
                  json.dumps(evidence, sort_keys=True, default=str), flush=True)
            return 4
    ok, value = audit(output, before, child_exit)
    if ok:
        print("GUARD-ADMISSION-RUNNER-PASS exact_count=1 state=Success "
              "assets=2 map=1 stock=4 hashes_unchanged=1 output=%s" % output,
              flush=True)
        return 0
    for problem in value["problems"]:
        print("GUARD-ADMISSION-RUNNER-ERROR " + problem, flush=True)
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
        print("GUARD-ADMISSION-RUNNER-ERROR %r" % (exc,), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Run exactly one real-RHI two-hand admission with an outer watchdog."""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from two_hand_authoring_common import (  # noqa: E402
    ADMISSION_MAP, PROJECT, REPO, asset_vector, map_files, vector, STOCK,
)


TASK_ID = "t3-both-hands-follow-the-physics-driven-handle"
UE_ROOT = Path(os.environ.get("CB_UE_ROOT", r"C:\Program Files\Epic Games\UE_5.8"))
VERIFY = REPO / "tools" / "verify-single"
MAP_NAME = "L_TwoHandPhysicsAdmission"
MAP_PACKAGE = "/Game/Maps/%s/%s" % (TASK_ID, MAP_NAME)
EXACT_FILTER = (
    "Project.Functional Tests.Maps.%s.%s."
    "TwoHandPhysicsAdmissionFunctionalTest" % (TASK_ID, MAP_NAME))
EXPECTED_DISPLAY = "TwoHandPhysicsAdmissionFunctionalTest"
SUCCESS = ("TWO-HAND-PHYSICS-ADMISSION PASS runtime ControlRig and "
           "two-leg telemetry admitted; thresholds frozen")
METRICS = re.compile(
    r"\[CB-TWO-HAND-METRICS\] mode=admission runtime_observed=1 "
    r"scenario=TwoHandPhysics\.AdmissionQuartz callbacks=([1-9][0-9]*) "
    r"samples=([1-9][0-9]*) first_n=([1-9][0-9]*) "
    r"second_n=([1-9][0-9]*).*thresholds_frozen=1")


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True,
                               default=str) + "\n", encoding="utf-8")


def snapshot():
    return {"map": vector(map_files(ADMISSION_MAP)),
            "admission": asset_vector(True), "task": asset_vector(False),
            "stock": vector(STOCK)}


def child_main(output):
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
    value = dataclasses.asdict(result)
    write_json(output / "l2_result.json", value)
    print("TWO-HAND-ADMISSION-CHILD " +
          json.dumps(value, sort_keys=True, default=str), flush=True)
    return 0 if result.status == "pass" else 1


def kill_owned_tree(process):
    evidence = {"pid": process.pid}
    if process.poll() is not None:
        evidence.update(method="already-exited", exit_code=process.returncode)
        return evidence
    completed = subprocess.run(
        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
        capture_output=True, text=True, check=False, timeout=30)
    evidence.update(method="taskkill-exact-owned-tree",
                    taskkill_exit=completed.returncode,
                    output=(completed.stdout + completed.stderr).strip())
    process.wait(timeout=30)
    evidence["exit_code"] = process.returncode
    return evidence


def read_json(path, problems):
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(value, dict):
            raise ValueError("root is not object")
        return value
    except Exception as exc:  # noqa: BLE001
        problems.append("unreadable JSON %s: %r" % (path, exc))
        return {}


def audit(output, before, child_exit):
    problems = []
    result = read_json(output / "l2_result.json", problems)
    report = read_json(output / "report" / "index.json", problems)
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
            problems.append("wrong state: %r" % test.get("state"))
    if (child_exit != 0 or result.get("status") != "pass" or
            result.get("tests_run") != 1 or result.get("tests_passed") != 1 or
            result.get("tests_failed") != 0 or
            result.get("result_source") != "json"):
        problems.append("L2 child/result/count/source mismatch: %r/%d" %
                        (result, child_exit))
    log_path = output / "l2.log"
    text = log_path.read_text(encoding="utf-8", errors="replace") \
        if log_path.is_file() else ""
    if text.count(SUCCESS) != 1:
        problems.append("terminal success marker count=%d" % text.count(SUCCESS))
    metrics = METRICS.findall(text)
    if len(metrics) != 1:
        problems.append("metrics marker count=%d" % len(metrics))
    for token in ("HARNESS-PRECONDITION", "Ensure condition failed",
                  "Assertion failed", "Fatal error", "LowLevelFatalError",
                  "L2 TIMEOUT"):
        if token in text:
            problems.append("forbidden log token: " + token)
    after = snapshot()
    if after != before:
        problems.append("protected map/assets/stock hash changed")
    value = {"filter": EXACT_FILTER, "expected_display": EXPECTED_DISPLAY,
             "expected_count": 1, "map_package": MAP_PACKAGE,
             "rhi": "real", "fps": 60, "thresholds": "frozen",
             "result": result, "report": report,
             "metrics": metrics, "protected_before": before,
             "protected_after": after, "problems": problems}
    write_json(output / "audit.json", value)
    return not problems, value


def parent_main(args):
    output = args.output.resolve()
    if args.watchdog_seconds < 60:
        raise RuntimeError("watchdog must be >=60 seconds")
    if output.exists() or os.path.lexists(output):
        raise RuntimeError("fresh output exists: %s" % output)
    before = snapshot()
    output.mkdir(parents=True)
    write_json(output / "preflight.json", {
        "filter": EXACT_FILTER, "expected_display": EXPECTED_DISPLAY,
        "expected_count": 1, "map_package": MAP_PACKAGE, "rhi": "real",
        "fps": 60, "watchdog_seconds": args.watchdog_seconds,
        "protected_before": before})
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
            value = {"verdict": "INFRA_FREEZE", "filter": EXACT_FILTER,
                     "elapsed_seconds": time.monotonic() - started,
                     "deadline_seconds": args.watchdog_seconds,
                     "kill": kill_owned_tree(process),
                     "protected_before": before, "protected_after": snapshot()}
            write_json(output / "watchdog.json", value)
            print("TWO-HAND-ADMISSION-INFRA-FREEZE " +
                  json.dumps(value, sort_keys=True, default=str), flush=True)
            return 4
    ok, value = audit(output, before, child_exit)
    if ok:
        print("TWO-HAND-ADMISSION-RUNNER-PASS exact_count=1 state=Success "
              "real_rhi=1 thresholds=frozen hashes_unchanged=1 output=%s" % output,
              flush=True)
        return 0
    for problem in value["problems"]:
        print("TWO-HAND-ADMISSION-RUNNER-ERROR " + problem, flush=True)
    return 1


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--watchdog-seconds", type=int, default=720)
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        return child_main(args.output.resolve()) if args.child else parent_main(args)
    except Exception as exc:  # noqa: BLE001
        print("TWO-HAND-ADMISSION-RUNNER-ERROR %r" % (exc,), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

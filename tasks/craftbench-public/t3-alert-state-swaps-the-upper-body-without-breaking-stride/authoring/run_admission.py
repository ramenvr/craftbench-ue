"""Run exactly one Alert Stride admission fixture under a watchdog."""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
from pathlib import Path
import subprocess
import sys

from alert_stride_common import (
    ADMISSION_MAP, ADMISSION_ROOT, FINAL_INTERFACE, FINAL_MAP, FINAL_ROOT,
    PROJECT, REFERENCE, REPO, disk, snapshot,
)

#: Engine root. Override with CB_UE_ROOT; defaults to Epic's standard install.
_UE_ROOT = Path(os.environ.get("CB_UE_ROOT", r"C:\Program Files\Epic Games\UE_5.8"))


DISPLAY = "AlertStrideAdmissionFunctionalTest"
FILTER = (
    "Project.Functional Tests.__CraftBenchAdmission."
    "t3-alert-state-swaps-the-upper-body-without-breaking-stride."
    "L_AlertStrideAdmission." + DISPLAY
)
LOCKS = {
    "admission_assets": disk(ADMISSION_ROOT, ""),
    "admission_map": disk(ADMISSION_MAP, ".umap"),
    "final_assets": disk(FINAL_ROOT, ""),
    "final_interface": disk(FINAL_INTERFACE, ".uasset"),
    "final_map": disk(FINAL_MAP, ".umap"),
    "reference": REFERENCE,
}
GATES = (
    "AlertStateBecomesActive",
    "BehaviorStateLinksAndDrivesDeclaredLayer",
    "LowerBodyStrideRemainsContinuous",
    "ClearRestoresOriginalLayerWithoutRestart",
)


def lock_snapshot():
    return {name: snapshot(path) for name, path in LOCKS.items()}


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True,
                               default=str) + "\n", encoding="utf-8")


def child(output, ue_root):
    verify = REPO / "tools" / "verify-single"
    sys.path.insert(0, str(verify))
    sys.path.insert(0, str(verify / "layers"))
    from l2_pie import run_l2
    value = run_l2(
        ue_root=ue_root, project_path=PROJECT, test_filter=FILTER,
        log_path=output / "l2.log", report_dir=output / "report",
        map_name="L_AlertStrideAdmission", map_package_path=ADMISSION_MAP,
        use_nullrhi=True, fps=60, timeout_seconds=3600.0,
        expected_test_count=1)
    write_json(output / "l2_result.json", dataclasses.asdict(value))
    return 0 if value.status == "pass" else 1


def audit(output, before, exit_code):
    result_path = output / "l2_result.json"
    report_path = output / "report" / "index.json"
    if not result_path.is_file() or not report_path.is_file():
        write_json(output / "audit.json", {
            "problems": ["result/report missing"], "exit_code": exit_code})
        return False
    result = json.loads(result_path.read_text(encoding="utf-8-sig"))
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    tests = report.get("tests", [])
    log_text = (output / "l2.log").read_text(
        encoding="utf-8", errors="replace")
    problems = []
    if exit_code or result.get("status") != "pass" \
            or result.get("tests_run") != 1:
        problems.append("L2 result/count mismatch")
    if len(tests) != 1 or tests[0].get("fullTestPath") != FILTER \
            or tests[0].get("testDisplayName") != DISPLAY \
            or tests[0].get("state") != "Success":
        problems.append("exact automation identity/state mismatch")
    for gate in GATES:
        if "GATE[%s]=PASS" % gate not in log_text:
            problems.append("missing named gate telemetry: " + gate)
    if log_text.count("[CB-ALERT-STRIDE] PASS scenario=Admission") != 1:
        problems.append("terminal marker count mismatch")
    after = lock_snapshot()
    if after != before:
        problems.append("protected task bytes changed")
    write_json(output / "audit.json", {
        "filter": FILTER, "display": DISPLAY, "expected_count": 1,
        "rhi": "nullrhi", "result": result, "report": report,
        "locks_before": before, "locks_after": after,
        "telemetry": [line for line in log_text.splitlines()
                      if "CB-ALERT-STRIDE" in line or "GATE[" in line],
        "problems": problems,
    })
    return not problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ue-root", type=Path, default=_UE_ROOT)
    parser.add_argument("--watchdog-seconds", type=int, default=720)
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    output = args.output.resolve()
    if args.child:
        return child(output, args.ue_root.resolve())
    if os.path.lexists(str(output)):
        raise RuntimeError("fresh output already exists: %s" % output)
    before = lock_snapshot()
    if before["admission_assets"].get("kind") != "directory" \
            or before["admission_map"].get("kind") != "file":
        raise RuntimeError("admission assets/map missing")
    output.mkdir(parents=True)
    write_json(output / "preflight.json", {
        "filter": FILTER, "display": DISPLAY, "expected_count": 1,
        "rhi": "nullrhi", "watchdog_seconds": args.watchdog_seconds,
        "locks": before})
    command = [sys.executable, str(Path(__file__).resolve()), "--child",
               "--output", str(output), "--ue-root", str(args.ue_root.resolve())]
    with (output / "runner.log").open("w", encoding="utf-8") as stream:
        process = subprocess.Popen(command, cwd=REPO, stdout=stream,
                                   stderr=subprocess.STDOUT, text=True)
        try:
            exit_code = process.wait(timeout=args.watchdog_seconds)
        except subprocess.TimeoutExpired:
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           check=False, capture_output=True, text=True)
            write_json(output / "watchdog.json", {
                "verdict": "INFRA_FREEZE", "pid": process.pid,
                "deadline": args.watchdog_seconds})
            return 4
    return 0 if audit(output, before, exit_code) else 1


if __name__ == "__main__":
    raise SystemExit(main())

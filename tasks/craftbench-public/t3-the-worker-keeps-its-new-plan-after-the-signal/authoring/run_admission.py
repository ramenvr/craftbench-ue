"""Fail-closed exact-one worker-plan admission runner."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import os

#: Engine root. Override with CB_UE_ROOT; defaults to Epic's standard install.
_UE_ROOT = Path(os.environ.get("CB_UE_ROOT", r"C:\Program Files\Epic Games\UE_5.8"))


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
VERIFY = REPO / "tools" / "verify-single"
TASK_ID = "t3-the-worker-keeps-its-new-plan-after-the-signal"
PROJECT = REPO / "UE-projects" / "ThirdPerson" / "ThirdPerson.uproject"
CONTENT = REPO / "UE-projects" / "ThirdPerson" / "Content"
MAP_NAME = "L_WorkerPlanAdmission"
MAP_PACKAGE = "/Game/Maps/%s/%s" % (TASK_ID, MAP_NAME)
FILTER = ("Project.Functional Tests.Maps.%s.%s.WorkerPlanFunctionalTest" %
          (TASK_ID, MAP_NAME))
PROTECTED = (
    CONTENT / "Maps" / TASK_ID / (MAP_NAME + ".umap"),
    CONTENT / "__CraftBenchAdmission" / TASK_ID / "ST_WorkerPlan_Admission.uasset",
)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hashes():
    missing = [str(path) for path in PROTECTED if not path.is_file()]
    if missing:
        raise RuntimeError("protected artifacts missing: %r" % missing)
    return {str(path.relative_to(CONTENT)).replace("\\", "/"): sha256(path)
            for path in PROTECTED}


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True,
                               default=str) + "\n",
                    encoding="utf-8")


def child(output):
    sys.path.insert(0, str(VERIFY))
    sys.path.insert(0, str(VERIFY / "layers"))
    from l2_pie import run_l2
    result = run_l2(
        ue_root=_UE_ROOT, project_path=PROJECT,
        test_filter=FILTER, log_path=output / "l2.log",
        report_dir=output / "report", map_name=MAP_NAME,
        map_package_path=MAP_PACKAGE, use_nullrhi=True,
        fps=60, timeout_seconds=600.0, expected_test_count=1)
    write_json(output / "l2_result.json", dataclasses.asdict(result))
    return 0 if result.status == "pass" else 1


def parent(args):
    output = REPO / "runs" / "authoring" / TASK_ID / "admission" / ("round-%d" % args.round)
    if output.exists():
        raise SystemExit("fresh output exists: " + str(output))
    output.mkdir(parents=True)
    before = hashes()
    command = [sys.executable, str(Path(__file__).resolve()), "--round",
               str(args.round), "--child", "--output", str(output)]
    with (output / "runner.stdout.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, cwd=REPO, stdout=log,
                                   stderr=subprocess.STDOUT, text=True)
        try:
            exit_code = process.wait(timeout=args.watchdog_seconds)
        except subprocess.TimeoutExpired:
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           check=False, capture_output=True, text=True, timeout=30)
            write_json(output / "watchdog.json", {"status": "INFRA_FREEZE",
                       "filter": FILTER, "hashes_before": before,
                       "hashes_after": hashes()})
            return 4
    result_path = output / "l2_result.json"
    report_path = output / "report" / "index.json"
    if not result_path.is_file() or not report_path.is_file():
        after = hashes()
        write_json(output / "audit.json", {
            "filter": FILTER,
            "expected_test_count": 1,
            "rhi": "null",
            "child_exit": exit_code,
            "result_present": result_path.is_file(),
            "report_present": report_path.is_file(),
            "hashes_before": before,
            "hashes_after": after,
            "problems": ["authoritative child result/report missing"],
        })
        return 1
    result = json.loads(result_path.read_text(encoding="utf-8"))
    index = json.loads(report_path.read_text(encoding="utf-8-sig"))
    tests = index.get("tests", [])
    problems = []
    if exit_code != 0 or result.get("status") != "pass":
        problems.append("child/result not pass")
    if len(tests) != 1 or tests[0].get("fullTestPath") != FILTER \
            or tests[0].get("state") != "Success":
        problems.append("exact test/count/state mismatch")
    if index.get("succeeded") != 1 or index.get("failed") != 0:
        problems.append("aggregate mismatch")
    after = hashes()
    if before != after:
        problems.append("protected hashes changed")
    write_json(output / "audit.json", {"filter": FILTER,
               "expected_test_count": 1, "rhi": "null", "result": result,
               "tests": tests, "hashes_before": before,
               "hashes_after": after, "problems": problems})
    return 1 if problems else 0


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--round", required=True, type=int)
    parser.add_argument("--watchdog-seconds", type=int, default=720)
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--output", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.round < 1 or args.watchdog_seconds < 60:
        parser.error("round >=1 and watchdog >=60 required")
    if args.child and args.output is None:
        parser.error("--child requires --output")
    return args


if __name__ == "__main__":
    parsed = parse_args()
    raise SystemExit(child(parsed.output.resolve()) if parsed.child else parent(parsed))

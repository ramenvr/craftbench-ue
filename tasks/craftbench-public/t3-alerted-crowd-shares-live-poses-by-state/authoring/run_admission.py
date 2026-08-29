"""Run one fail-closed NullRHI Animation Sharing admission round."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
VERIFY = REPO / "tools" / "verify-single"
TASK_ID = "t3-alerted-crowd-shares-live-poses-by-state"
UE_ROOT = Path(os.environ.get("CB_UE_ROOT", r"C:\Program Files\Epic Games\UE_5.8"))
PROJECT = REPO / "UE-projects" / "ThirdPerson" / "ThirdPerson.uproject"
CONTENT = REPO / "UE-projects" / "ThirdPerson" / "Content"
MAP_NAME = "L_AlertCrowdSharingAdmission"
MAP_PACKAGE = "/Game/Maps/%s/%s" % (TASK_ID, MAP_NAME)
TEST_FILTER = (
    "Project.Functional Tests.Maps.%s.%s."
    "AlertCrowdSharingAdmissionFunctionalTest" % (TASK_ID, MAP_NAME))
SUCCESS_TOKEN = "ALERT-CROWD-ADMISSION-SUCCEEDED"
PROTECTED_FILES = (
    CONTENT / "Maps" / TASK_ID / (MAP_NAME + ".umap"),
    CONTENT / "__CraftBenchAdmission" / TASK_ID /
    "AS_AlertCrowdSharing_Admission.uasset",
    CONTENT / "__CraftBenchAdmission" / TASK_ID /
    "BP_AlertCrowdStateProcessor_Admission.uasset",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def protected_hashes() -> dict[str, str]:
    missing = [str(path) for path in PROTECTED_FILES if not path.is_file()]
    if missing:
        raise RuntimeError("protected admission artifact missing: %s" % missing)
    return {str(path.relative_to(CONTENT)).replace("\\", "/"): sha256(path)
            for path in PROTECTED_FILES}


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True,
                               default=str) + "\n", encoding="utf-8")


def child_command(round_number: int, output: Path) -> list[str]:
    return [sys.executable, str(Path(__file__).resolve()),
            "--round", str(round_number), "--child", "--output", str(output)]


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
        map_package_path=MAP_PACKAGE,
        use_nullrhi=True,
        render_offscreen=False,
        fps=60,
        timeout_seconds=720.0,
        expected_test_count=1,
    )
    payload = dataclasses.asdict(result)
    write_json(output / "l2_result.json", payload)
    print("ALERT-CROWD-ADMISSION-CHILD " +
          json.dumps(payload, sort_keys=True, default=str))
    return 0 if result.status == "pass" else 1


def kill_exact_tree(process: subprocess.Popen) -> dict[str, object]:
    evidence: dict[str, object] = {"pid": process.pid}
    if process.poll() is not None:
        evidence.update(method="already-exited", exit_code=process.returncode)
        return evidence
    completed = subprocess.run(
        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
        capture_output=True, text=True, check=False, timeout=30)
    evidence.update(method="taskkill-exact-tree",
                    taskkill_exit=completed.returncode,
                    output=(completed.stdout + completed.stderr).strip())
    process.wait(timeout=30)
    evidence["exit_code"] = process.returncode
    return evidence


def audit(output: Path, before: dict[str, str]) -> tuple[bool, dict]:
    problems = []
    try:
        result = json.loads((output / "l2_result.json").read_text(
            encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        result = {}
        problems.append("l2_result unreadable: %r" % (exc,))
    try:
        index = json.loads((output / "report" / "index.json").read_text(
            encoding="utf-8-sig"))
    except Exception as exc:  # noqa: BLE001
        index = {}
        problems.append("automation index unreadable: %r" % (exc,))
    tests = index.get("tests", []) if isinstance(index, dict) else []
    if len(tests) != 1 or tests[0].get("fullTestPath") != TEST_FILTER \
            or tests[0].get("state") != "Success":
        problems.append("wrong exact test/cardinality/state: %r" % tests)
    if index.get("succeeded") != 1 or index.get("failed") != 0:
        problems.append("automation aggregate is not exact 1/0")
    if result.get("status") != "pass" or result.get("tests_run") != 1 \
            or result.get("tests_passed") != 1 \
            or result.get("result_source") != "json":
        problems.append("L2 result/count/source mismatch: %r" % result)
    log_path = output / "l2.log"
    text = log_path.read_text(encoding="utf-8", errors="replace") \
        if log_path.is_file() else ""
    if text.count(SUCCESS_TOKEN) != 1:
        problems.append("terminal marker count=%d expected=1" %
                        text.count(SUCCESS_TOKEN))
    for token in ("HARNESS-PRECONDITION", "Ensure condition failed",
                  "Fatal error", "LowLevelFatalError", "L2 TIMEOUT"):
        if token in text:
            problems.append("forbidden log token: " + token)
    after = protected_hashes()
    if after != before:
        problems.append("protected admission artifact hash changed")
    summary = {
        "filter": TEST_FILTER,
        "map_package": MAP_PACKAGE,
        "expected_test_count": 1,
        "rhi": "null",
        "world_clock": True,
        "result": result,
        "automation": {"succeeded": index.get("succeeded"),
                       "failed": index.get("failed"), "tests": tests},
        "hashes_before": before,
        "hashes_after": after,
        "telemetry": [line for line in text.splitlines()
                      if "ALERT-CROWD-" in line],
        "promotion_decision": "TBD-ADMISSION-NOT-AUTOMATIC-GO",
        "problems": problems,
    }
    write_json(output / "audit.json", summary)
    return not problems, summary


def parent_main(args: argparse.Namespace) -> int:
    if args.watchdog_seconds < 60:
        raise SystemExit("watchdog must be at least 60 seconds")
    output = (REPO / "runs" / "authoring" / TASK_ID / "admission" /
              ("round-%d" % args.round))
    if output.exists():
        raise SystemExit("fresh output already exists: %s" % output)
    output.mkdir(parents=True)
    before = protected_hashes()
    write_json(output / "preflight.json", {
        "filter": TEST_FILTER, "map_package": MAP_PACKAGE,
        "expected_test_count": 1, "rhi": "null",
        "watchdog_seconds": args.watchdog_seconds,
        "hashes_before": before,
    })
    started = time.time()
    with (output / "runner.stdout.log").open(
            "w", encoding="utf-8", errors="replace") as stream:
        process = subprocess.Popen(child_command(args.round, output), cwd=REPO,
                                   stdout=stream, stderr=subprocess.STDOUT,
                                   text=True)
        try:
            child_exit = process.wait(timeout=args.watchdog_seconds)
        except subprocess.TimeoutExpired:
            write_json(output / "watchdog.json", {
                "verdict": "INFRA_FREEZE",
                "elapsed_seconds": time.time() - started,
                "deadline_seconds": args.watchdog_seconds,
                "kill": kill_exact_tree(process),
                "hashes_before": before,
                "hashes_after": protected_hashes(),
            })
            return 4
    ok, summary = audit(output, before)
    print("ALERT-CROWD-ADMISSION-RUNNER child_exit=%d ok=%d output=%s" %
          (child_exit, 1 if ok else 0, output))
    for problem in summary["problems"]:
        print("ALERT-CROWD-ADMISSION-AUDIT-FAILED " + problem)
    return 0 if ok else 1


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--round", type=int, required=True)
    parser.add_argument("--watchdog-seconds", type=float, default=900.0)
    parser.add_argument("--child", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.round < 1:
        parser.error("--round must be >= 1")
    if args.child and args.output is None:
        parser.error("--child requires --output")
    return args


if __name__ == "__main__":
    parsed = parse_args()
    raise SystemExit(child_main(parsed.output) if parsed.child
                     else parent_main(parsed))

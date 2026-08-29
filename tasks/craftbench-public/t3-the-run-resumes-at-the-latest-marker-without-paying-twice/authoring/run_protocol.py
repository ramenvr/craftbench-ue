"""Run the exact write/terminate/resume SaveGame protocol in two UE processes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
import sys


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "verify-single"))
from layers.l2_pie import run_l2  # noqa: E402


TASK_ID = "t3-the-run-resumes-at-the-latest-marker-without-paying-twice"
MAP_PACKAGE = f"/Game/Maps/{TASK_ID}/L_LatestMarkerResume"
FILTER_BASE = (
    "Project.Functional Tests.Maps."
    f"{TASK_ID}.L_LatestMarkerResume."
)
WRITE_NAME = "LatestMarkerWriteFunctionalTest"
RESUME_NAME = "LatestMarkerResumeFunctionalTest"
GATES = (
    "FreshNonceScopedSlotBeginsEmpty",
    "NewestCheckpointRecordIsSerialized",
    "CollectedRewardIdentitySetIsSerialized",
    "ResumeUsesLatestMarkerTransform",
    "RewardTotalRestoresExactly",
    "AlreadyCollectedRewardsDoNotPayTwice",
    "UncollectedControlStillPaysOnce",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def is_reparse(path: Path) -> bool:
    info = path.lstat()
    return path.is_symlink() or bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--ue-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--watchdog-seconds", type=int, default=720)
    return parser.parse_args()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def audit_leg(result, expected_path: str, expected_name: str,
              log_text: str) -> list[str]:
    problems = []
    if result.status != "pass" or result.tests_run != 1 \
            or result.tests_passed != 1 or result.tests_failed != 0:
        problems.append("leg result/count mismatch: %r" % result)
    report = Path(result.report_path) if result.report_path else None
    if report is None or not report.is_file():
        problems.append("authoritative report missing")
    else:
        payload = json.loads(report.read_text(encoding="utf-8-sig"))
        tests = payload.get("tests", payload.get("automation", {}).get("tests", []))
        if len(tests) != 1:
            problems.append("report test count mismatch: %d" % len(tests))
        else:
            test = tests[0]
            actual_path = test.get("fullTestPath", test.get("full_test_path"))
            actual_name = test.get("testDisplayName", test.get("display_name"))
            if actual_path != expected_path or actual_name != expected_name \
                    or test.get("state") != "Success":
                problems.append("report identity/state mismatch: %r" % test)
    for token in ("HARNESS-PRECONDITION", "GATE["):
        if token == "GATE[":
            continue
        if token in log_text:
            problems.append("forbidden marker: " + token)
    return problems


def result_dict(result) -> dict[str, object]:
    return {
        "status": result.status,
        "duration_seconds": result.duration_seconds,
        "tests_run": result.tests_run,
        "tests_passed": result.tests_passed,
        "tests_failed": result.tests_failed,
        "tests_skipped": result.tests_skipped,
        "exit_code": result.exit_code,
        "report_path": str(result.report_path) if result.report_path else None,
        "result_source": result.result_source,
        "notes": list(result.notes),
        "rhi_unavailable": result.rhi_unavailable,
        "queued_never_started": result.queued_never_started,
        "harness_precondition": result.harness_precondition,
        "editor_never_started": result.editor_never_started,
    }


def main() -> int:
    args = parse_args()
    project = args.project.resolve()
    output = args.output.resolve()
    if output.exists() or not project.is_file():
        raise RuntimeError("output must be fresh and project must exist")
    output.mkdir(parents=True, exist_ok=False)
    nonce = secrets.token_hex(16)
    slot_name = "CB_RunResume_" + nonce
    slot_file = project.parent / "Saved" / "SaveGames" / (slot_name + ".sav")
    if os.path.lexists(slot_file):
        raise RuntimeError("nonce-scoped slot unexpectedly exists")
    protocol = {
        "schema": 1, "task_id": TASK_ID, "nonce": nonce,
        "slot_name": slot_name, "user_index": 0,
        "map": MAP_PACKAGE,
        "write_path": FILTER_BASE + WRITE_NAME,
        "resume_path": FILTER_BASE + RESUME_NAME,
        "checkpoint_ids": ["HarborOld", "CedarLatest"],
        "reward_facts": {
            "RewardQuartz": 17, "RewardViolet": 29,
            "RewardAmberControl": 41},
    }
    protocol_path = output / "protocol.json"
    write_json(protocol_path, protocol)
    protocol_hash = sha256(protocol_path)
    env = os.environ.copy()
    env.update({
        "CRAFTBENCH_RUN_RESUME_SLOT": slot_name,
        "CRAFTBENCH_RUN_RESUME_NONCE": nonce,
        "CRAFTBENCH_RUN_RESUME_PROTOCOL": str(protocol_path),
    })
    evidence: dict[str, object] = {
        "status": "running", "protocol": protocol,
        "protocol_sha256": protocol_hash, "slot_file": str(slot_file),
        "gates": list(GATES), "legs": {}, "problems": []}
    write_json(output / "aggregate.json", evidence)
    try:
        write_path = protocol["write_path"]
        write_result = run_l2(
            ue_root=args.ue_root, project_path=project,
            test_filter=write_path, map_package_path=MAP_PACKAGE,
            map_name="L_LatestMarkerResume", use_nullrhi=True, fps=60,
            timeout_seconds=args.watchdog_seconds, extra_env=env,
            log_path=output / "write.log", report_dir=output / "write-report",
            expected_test_count=1)
        write_text = (output / "write.log").read_text(
            encoding="utf-8", errors="replace")
        problems = audit_leg(write_result, write_path, WRITE_NAME, write_text)
        if not slot_file.is_file() or is_reparse(slot_file):
            problems.append("write leg did not create exact regular slot")
        slot_after_write = ({"size": slot_file.stat().st_size,
                             "sha256": sha256(slot_file)}
                            if slot_file.is_file() else {})
        if protocol_hash != sha256(protocol_path):
            problems.append("protocol mutated during write leg")
        evidence["legs"]["write"] = {
            "result": result_dict(write_result), "slot": slot_after_write}
        if problems:
            evidence["failure_kind"] = (
                "behavior" if write_result.status == "fail"
                and write_result.tests_run == 1
                and write_result.tests_failed == 1
                and not write_result.rhi_unavailable
                and not write_result.queued_never_started
                and not write_result.harness_precondition
                and not write_result.editor_never_started
                else "harness")
            evidence["problems"].extend(problems)
            raise RuntimeError("write leg failed: %r" % problems)

        resume_path = protocol["resume_path"]
        resume_result = run_l2(
            ue_root=args.ue_root, project_path=project,
            test_filter=resume_path, map_package_path=MAP_PACKAGE,
            map_name="L_LatestMarkerResume", use_nullrhi=True, fps=60,
            timeout_seconds=args.watchdog_seconds, extra_env=env,
            log_path=output / "resume.log", report_dir=output / "resume-report",
            expected_test_count=1)
        resume_text = (output / "resume.log").read_text(
            encoding="utf-8", errors="replace")
        problems = audit_leg(
            resume_result, resume_path, RESUME_NAME, resume_text)
        combined = write_text + "\n" + resume_text
        gate_counts = {gate: combined.count("GATE[%s]=PASS" % gate)
                       for gate in GATES}
        if any(count != 1 for count in gate_counts.values()):
            problems.append("aggregate gate cardinality mismatch: %r" % gate_counts)
        if "RUN-RESUME-WRITE-SUCCEEDED gates=3/3" not in write_text \
                or "RUN-RESUME-RESUME-SUCCEEDED gates=4/4" not in resume_text:
            problems.append("terminal leg markers missing")
        if protocol_hash != sha256(protocol_path):
            problems.append("protocol mutated during resume leg")
        if not slot_file.is_file() or is_reparse(slot_file):
            problems.append("slot missing/nonregular after resume")
        evidence["legs"]["resume"] = {"result": result_dict(resume_result)}
        evidence["gate_counts"] = gate_counts
        evidence["problems"].extend(problems)
        if problems:
            evidence["failure_kind"] = (
                "behavior" if resume_result.status == "fail"
                and resume_result.tests_run == 1
                and resume_result.tests_failed == 1
                and not resume_result.rhi_unavailable
                and not resume_result.queued_never_started
                and not resume_result.harness_precondition
                and not resume_result.editor_never_started
                else "harness")
            raise RuntimeError("resume/aggregate failed: %r" % problems)
        evidence["status"] = "pass"
        return 0
    except Exception as exc:
        evidence["status"] = "fail"
        evidence["error"] = str(exc)
        raise
    finally:
        cleanup = {"attempted": False, "removed": False}
        if slot_file.is_file() and not is_reparse(slot_file):
            cleanup["attempted"] = True
            slot_file.unlink()
            cleanup["removed"] = not os.path.lexists(slot_file)
        evidence["cleanup"] = cleanup
        evidence["protocol_unchanged"] = (
            protocol_path.is_file() and sha256(protocol_path) == protocol_hash)
        write_json(output / "aggregate.json", evidence)
        if evidence["status"] == "pass":
            print("RUN-RESUME-PROTOCOL-PASS processes=2 gates=7/7 "
                  "slot_cleaned=1 protocol_unchanged=1 output=%s" % output)


if __name__ == "__main__":
    raise SystemExit(main())

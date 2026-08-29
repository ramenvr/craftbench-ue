"""Canonical L2 adapter for the two-process SaveGame task.

The ordinary L2 layer runs all declared fixtures in one Editor process.  This
task explicitly grades persistence across process death, so its committed,
host-side protocol runner owns two separate ``run_l2`` calls and one exact
nonce-scoped SaveGame slot.  The adapter converts that retained aggregate into
the ordinary ``LayerReport`` contract without trusting candidate telemetry.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Iterable

from report import LayerReport


TASK_ID = "t3-the-run-resumes-at-the-latest-marker-without-paying-twice"
GATES = (
    "FreshNonceScopedSlotBeginsEmpty",
    "NewestCheckpointRecordIsSerialized",
    "CollectedRewardIdentitySetIsSerialized",
    "ResumeUsesLatestMarkerTransform",
    "RewardTotalRestoresExactly",
    "AlreadyCollectedRewardsDoNotPayTwice",
    "UncollectedControlStillPaysOnce",
)


def _counts(legs: Iterable[dict]) -> tuple[int, int, int]:
    run = passed = failed = 0
    for leg in legs:
        result = leg.get("result", {}) if isinstance(leg, dict) else {}
        run += int(result.get("tests_run", 0) or 0)
        passed += int(result.get("tests_passed", 0) or 0)
        failed += int(result.get("tests_failed", 0) or 0)
    return run, passed, failed


def classify_aggregate(aggregate: dict, returncode: int) -> str:
    """Return pass/fail/error from only structural retained evidence."""
    legs = aggregate.get("legs", {})
    ordered = [legs[key] for key in ("write", "resume") if key in legs]
    tests_run, tests_passed, tests_failed = _counts(ordered)
    gate_counts = aggregate.get("gate_counts", {})
    pass_contract = (
        returncode == 0
        and aggregate.get("status") == "pass"
        and tests_run == tests_passed == 2
        and tests_failed == 0
        and all(gate_counts.get(gate) == 1 for gate in GATES)
        and aggregate.get("protocol_unchanged") is True
        and aggregate.get("cleanup", {}).get("removed") is True
        and not aggregate.get("problems")
    )
    if pass_contract:
        return "pass"
    if aggregate.get("failure_kind") == "behavior":
        return "fail"
    return "error"


def run_protocol_layer(ctx, map_notes: list[str]) -> LayerReport:
    task_path = Path(ctx.task.source_path).resolve()
    runner = task_path.parent / "authoring" / "run_protocol.py"
    protocol_out = ctx.out_dir / "l2_run_resume_protocol"
    host_log = ctx.out_dir / "l2_run_resume_host.log"
    if not runner.is_file() or protocol_out.exists():
        return LayerReport(
            status="error", notes=map_notes + [
                "HARNESS: two-process runner missing or output not fresh",
                f"runner: {runner}", f"output: {protocol_out}"],
        )
    command = [
        sys.executable, "-B", str(runner),
        "--project", str(ctx.project_path),
        "--ue-root", str(ctx.args.ue_root),
        "--output", str(protocol_out),
        "--watchdog-seconds", str(min(int(ctx.task.deadline_s), 720)),
    ]
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command, cwd=str(task_path.parent.parent.parent),
            capture_output=True, text=True,
            timeout=max(60, int(ctx.task.deadline_s)), check=False,
        )
        host_log.write_text(
            "COMMAND: " + subprocess.list2cmdline(command) + "\n\nSTDOUT:\n"
            + completed.stdout + "\nSTDERR:\n" + completed.stderr,
            encoding="utf-8")
    except subprocess.TimeoutExpired as exc:
        host_log.write_text(
            "HARNESS: protocol adapter timeout\n" + str(exc),
            encoding="utf-8")
        return LayerReport(
            status="error", log=str(host_log), exit_code=124,
            duration_seconds=round(time.monotonic() - started, 2),
            notes=map_notes + ["HARNESS: two-process adapter timeout"],
        )

    aggregate_path = protocol_out / "aggregate.json"
    if not aggregate_path.is_file():
        return LayerReport(
            status="error", log=str(host_log), exit_code=completed.returncode,
            duration_seconds=round(time.monotonic() - started, 2),
            notes=map_notes + [
                "HARNESS: protocol aggregate missing", f"runner: {runner}"],
        )
    try:
        aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return LayerReport(
            status="error", log=str(host_log), exit_code=completed.returncode,
            duration_seconds=round(time.monotonic() - started, 2),
            notes=map_notes + [f"HARNESS: invalid protocol aggregate: {exc!r}"],
        )

    legs = aggregate.get("legs", {})
    ordered_legs = [legs[key] for key in ("write", "resume") if key in legs]
    tests_run, tests_passed, tests_failed = _counts(ordered_legs)
    gate_counts = aggregate.get("gate_counts", {})
    status = classify_aggregate(aggregate, completed.returncode)

    notes = map_notes + [
        "two-process SaveGame protocol: " + status,
        f"aggregate: {aggregate_path}",
        f"process legs: {len(ordered_legs)}; gates: {gate_counts}",
    ]
    problems = aggregate.get("problems", [])
    if problems:
        notes.extend(str(problem)[:900] for problem in problems[:4])
    return LayerReport(
        status=status, log=str(host_log), exit_code=completed.returncode,
        duration_seconds=round(time.monotonic() - started, 2),
        tests_run=tests_run, tests_passed=tests_passed,
        notes=notes,
    )

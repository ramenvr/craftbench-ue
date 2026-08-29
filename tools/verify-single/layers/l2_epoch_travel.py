"""Canonical L2 adapter for the one-process, two-world travel task."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import time

from report import LayerReport


TASK_ID = "t3-the-old-world-cannot-complete-into-the-new-one"
GATES = (
    "OldWorldSubsystemDeinitializesOnce",
    "OldEpochCompletionCannotMutateNewWorld",
    "NewWorldResolvesItsAssignedRecord",
    "TravelLeavesNoOldWorldRootedObjects",
)


def classify_aggregate(aggregate: dict, returncode: int) -> str:
    exact_pass = (
        returncode == 0 and aggregate.get("status") == "pass"
        and aggregate.get("failure_kind") == "none"
        and aggregate.get("tests_run") == 1
        and aggregate.get("tests_passed") == 1
        and aggregate.get("tests_failed") == 0
        and aggregate.get("inputs_unchanged") is True
        and all(aggregate.get("gate_counts", {}).get(gate) == 1
                for gate in GATES)
        and not aggregate.get("problems"))
    if exact_pass:
        return "pass"
    if aggregate.get("failure_kind") == "behavior" \
            and aggregate.get("tests_run") == 1 \
            and aggregate.get("tests_failed") == 1:
        return "fail"
    return "error"


def run_epoch_travel_layer(ctx, map_notes: list[str]) -> LayerReport:
    task_path = Path(ctx.task.source_path).resolve()
    runner = task_path.parent / "authoring" / "run_travel.py"
    output = ctx.out_dir / "l2_epoch_travel_protocol"
    host_log = ctx.out_dir / "l2_epoch_travel_host.log"
    if not runner.is_file() or output.exists():
        return LayerReport(status="error", notes=map_notes + [
            "HARNESS: travel runner missing or output not fresh",
            f"runner: {runner}", f"output: {output}"])
    command = [
        sys.executable, "-B", str(runner), "--project",
        str(ctx.project_path), "--ue-root", str(ctx.args.ue_root),
        "--output", str(output), "--watchdog-seconds",
        str(min(int(ctx.task.deadline_s), 720)),
    ]
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command, cwd=str(task_path.parent.parent.parent),
            capture_output=True, text=True,
            timeout=max(60, int(ctx.task.deadline_s)), check=False)
        host_log.write_text(
            "COMMAND: " + subprocess.list2cmdline(command) + "\n\nSTDOUT:\n"
            + completed.stdout + "\nSTDERR:\n" + completed.stderr,
            encoding="utf-8")
    except subprocess.TimeoutExpired as exc:
        host_log.write_text("HARNESS: travel adapter timeout\n" + str(exc),
                            encoding="utf-8")
        return LayerReport(
            status="error", log=str(host_log), exit_code=124,
            duration_seconds=round(time.monotonic() - started, 2),
            notes=map_notes + ["HARNESS: travel adapter timeout"])
    aggregate_path = output / "aggregate.json"
    if not aggregate_path.is_file():
        return LayerReport(
            status="error", log=str(host_log),
            exit_code=completed.returncode,
            duration_seconds=round(time.monotonic() - started, 2),
            notes=map_notes + ["HARNESS: travel aggregate missing"])
    try:
        aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return LayerReport(
            status="error", log=str(host_log),
            exit_code=completed.returncode,
            duration_seconds=round(time.monotonic() - started, 2),
            notes=map_notes + [f"HARNESS: invalid aggregate: {exc!r}"])
    status = classify_aggregate(aggregate, completed.returncode)
    notes = map_notes + [
        "ordinary travel protocol: " + status,
        f"aggregate: {aggregate_path}",
        f"gates: {aggregate.get('gate_counts', {})}",
    ]
    notes.extend(str(item)[:900] for item in aggregate.get("problems", [])[:4])
    return LayerReport(
        status=status, log=str(host_log), exit_code=completed.returncode,
        duration_seconds=round(time.monotonic() - started, 2),
        tests_run=int(aggregate.get("tests_run", 0) or 0),
        tests_passed=int(aggregate.get("tests_passed", 0) or 0),
        notes=notes)

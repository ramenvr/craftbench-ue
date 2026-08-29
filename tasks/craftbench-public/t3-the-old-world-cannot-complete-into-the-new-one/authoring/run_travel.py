"""Launch one real -game editor process and audit the ordinary travel result."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
VERIFY = REPO / "tools" / "verify-single"
sys.path.insert(0, str(VERIFY))
from job_governor import L2_MEM_MB, IS_WINDOWS, assign, resource_job  # noqa: E402


TASK_ID = "t3-the-old-world-cannot-complete-into-the-new-one"
START_MAP = f"/Game/Maps/{TASK_ID}/L_OldEpochStart"
GATES = (
    "OldWorldSubsystemDeinitializesOnce",
    "OldEpochCompletionCannotMutateNewWorld",
    "NewWorldResolvesItsAssignedRecord",
    "TravelLeavesNoOldWorldRootedObjects",
)
PROTECTED_RELATIVE = (
    f"Content/Maps/{TASK_ID}/L_OldEpochStart.umap",
    f"Content/Maps/{TASK_ID}/L_NewEpochDestination.umap",
    f"Content/Maps/{TASK_ID}/Support/DA_EpochRecord_Old.uasset",
    f"Content/Maps/{TASK_ID}/Support/DA_EpochRecord_New.uasset",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def input_vector(project_root: Path) -> dict[str, dict[str, object]]:
    result = {}
    for relative in PROTECTED_RELATIVE:
        path = project_root / Path(relative)
        if not path.is_file() or path.is_symlink():
            raise RuntimeError("protected input missing/nonregular: %s" % path)
        result[relative] = {"size": path.stat().st_size,
                            "sha256": sha256(path)}
    return result


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--ue-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--watchdog-seconds", type=int, default=720)
    return parser.parse_args()


def classify_log(text: str, returncode: int,
                 unchanged: bool) -> tuple[str, str, list[str], dict[str, int]]:
    problems = []
    gate_counts = {gate: text.count("GATE[%s]=PASS" % gate)
                   for gate in GATES}
    failed_gate_counts = {gate: text.count("GATE[%s]=FAIL" % gate)
                          for gate in GATES}
    harness = text.count("EPOCH-TRAVEL-HARNESS-ERROR")
    success = text.count("EPOCH-TRAVEL-SUCCEEDED gates=4/4")
    behavior = text.count("EPOCH-TRAVEL-FAILED kind=behavior")
    if text.count("EPOCH-TRAVEL-START READY") != 1:
        problems.append("start-stage cardinality mismatch")
    if text.count("EPOCH-TRAVEL-DESTINATION READY") != 1:
        problems.append("destination-stage cardinality mismatch")
    if text.count("EPOCH-TRAVEL-OLD-CLEANUP") != 1:
        problems.append("old-cleanup cardinality mismatch")
    if not unchanged:
        problems.append("protected inputs changed")
    exact_pass = (returncode == 0 and harness == 0 and behavior == 0
                  and success == 1 and not problems
                  and all(count == 1 for count in gate_counts.values())
                  and all(count == 0 for count in failed_gate_counts.values()))
    if exact_pass:
        return "pass", "none", problems, gate_counts
    exact_behavior = (harness == 0 and behavior == 1 and success == 0
                      and unchanged
                      and all(gate_counts[g] + failed_gate_counts[g] == 1
                              for g in GATES))
    if exact_behavior:
        return "fail", "behavior", problems, gate_counts
    if harness:
        problems.append("protected harness error marker")
    if returncode != 0:
        problems.append("editor exit=%d" % returncode)
    return "fail", "harness", problems, gate_counts


def main() -> int:
    args = parse_args()
    project = args.project.resolve()
    output = args.output.resolve()
    editor = (args.ue_root.resolve() / "Engine" / "Binaries" / "Win64"
              / "UnrealEditor-Cmd.exe")
    if output.exists() or not project.is_file() or not editor.is_file():
        raise RuntimeError("fresh output/project/editor precondition failed")
    if args.watchdog_seconds < 60:
        raise RuntimeError("watchdog must be at least 60 seconds")
    output.mkdir(parents=True, exist_ok=False)
    project_root = project.parent
    before = input_vector(project_root)
    nonce = secrets.token_hex(16)
    stdout_path = output / "travel.stdout.log"
    abslog_path = output / "travel.log"
    command = [
        str(editor), str(project), START_MAP, "-game", "-nullrhi",
        "-unattended", "-nopause", "-nosplash", "-nosound",
        "-deterministic", "-FPS=60", "-stdout",
        "-FullStdOutLogOutput", "-abslog=%s" % abslog_path,
    ]
    env = os.environ.copy()
    env.update({"CRAFTBENCH_EPOCH_TRAVEL_RUN": "1",
                "CRAFTBENCH_EPOCH_TRAVEL_NONCE": nonce})
    write_json(output / "invocation.json", {
        "schema": 1, "task_id": TASK_ID, "nonce": nonce,
        "command": command, "map": START_MAP,
        "watchdog_seconds": args.watchdog_seconds, "inputs": before})
    started = time.monotonic()
    timed_out = False
    returncode = -999
    with stdout_path.open("w", encoding="utf-8") as stream:
        with resource_job(memory_limit_mb=L2_MEM_MB,
                          name="cb-epoch-travel") as job:
            process = subprocess.Popen(
                command, stdout=stream, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", env=env,
                creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP
                               if (IS_WINDOWS and job is not None) else 0))
            assign(job, process.pid)
            try:
                returncode = process.wait(timeout=args.watchdog_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                if job is None:
                    subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        capture_output=True, text=True, check=False)
                try:
                    returncode = process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    returncode = 124
    text = stdout_path.read_text(encoding="utf-8", errors="replace")
    after = input_vector(project_root)
    unchanged = before == after
    status, failure_kind, problems, gate_counts = classify_log(
        text, returncode, unchanged)
    if timed_out:
        status, failure_kind = "fail", "harness"
        problems.append("watchdog timeout")
    result = {
        "schema": 1, "task_id": TASK_ID, "status": status,
        "failure_kind": failure_kind, "nonce": nonce,
        "returncode": returncode, "timed_out": timed_out,
        "duration_seconds": round(time.monotonic() - started, 2),
        "tests_run": 1 if failure_kind != "harness" else 0,
        "tests_passed": 1 if status == "pass" else 0,
        "tests_failed": 1 if failure_kind == "behavior" else 0,
        "gate_counts": gate_counts, "problems": problems,
        "inputs_before": before, "inputs_after": after,
        "inputs_unchanged": unchanged,
        "stdout_log": str(stdout_path), "abslog": str(abslog_path),
    }
    write_json(output / "aggregate.json", result)
    if status == "pass":
        print("EPOCH-TRAVEL-PROTOCOL-PASS processes=1 worlds=2 gates=4/4 "
              "inputs_unchanged=1 output=%s" % output, flush=True)
        return 0
    print("EPOCH-TRAVEL-PROTOCOL-%s kind=%s problems=%r output=%s" %
          (status.upper(), failure_kind, problems, output), flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

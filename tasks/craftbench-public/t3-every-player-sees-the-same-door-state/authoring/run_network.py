"""Run and aggregate one real dedicated-server/three-client Door protocol."""

from __future__ import annotations

import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
VERIFY = REPO / "tools" / "verify-single"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(VERIFY))
from door_common import (  # noqa: E402
    ADMISSION_MAP_PACKAGE, FINAL_MAP_PACKAGE, optional_vector,
)
from job_governor import IS_WINDOWS, L2_MEM_MB, assign, resource_job  # noqa: E402


TASK_ID = "t3-every-player-sees-the-same-door-state"
PEERS = ("SERVER", "A", "B", "C")
GATES = (
    "RequesterCannotChangeDoorLocally",
    "ServerStateConvergesOnEveryPeer",
    "LateJoinerReceivesCurrentDoorState",
    "SecondRequesterTogglesSameAuthorityState",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--ue-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--admission", action="store_true")
    parser.add_argument("--watchdog-seconds", type=int, default=120)
    return parser.parse_args()


def project_inputs(project: Path, admission: bool) -> tuple[Path, Path]:
    """Return the exact map/Blueprint files used by this project process."""
    content = project.resolve().parent / "Content"
    if admission:
        return (
            content / "__CraftBenchAdmission" / TASK_ID
            / "BP_ReplicatedDoorState_Admission.uasset",
            content / "__CraftBenchAdmission" / TASK_ID
            / "L_ReplicatedDoorStateAdmission.umap",
        )
    return (
        content / "Tasks" / TASK_ID / "BP_ReplicatedDoorState.uasset",
        content / "Maps" / TASK_ID / "L_ReplicatedDoorState.umap",
    )


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def wait_for(path: Path, token: str, process: subprocess.Popen,
             timeout: float, monitor) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        text = read_text(path)
        monitor({"event": "wait", "token": token,
                 "count": text.count(token), "pid": process.pid,
                 "returncode": process.poll()})
        if token in text:
            return True
        if process.poll() is not None:
            return False
        time.sleep(0.25)
    return False


def protected_lines(path: Path) -> list[str]:
    return [line.strip() for line in read_text(path).splitlines()
            if "LogDoorNetworkVerifier:" in line and "DOOR-NETWORK-" in line]


def tokens(line: str) -> dict[str, str]:
    result: dict[str, str] = {}
    marker_index = line.find("DOOR-NETWORK-")
    if marker_index < 0:
        return result
    for item in line[marker_index:].split()[1:]:
        if "=" in item:
            key, value = item.split("=", 1)
            result[key] = value.rstrip(",")
    return result


def marker_rows(lines: list[str], marker: str) -> list[dict[str, str]]:
    return [tokens(line) for line in lines if marker in line]


def exact_observation(lines: list[str], peer: str, revision: int,
                      state: str) -> bool:
    rows = marker_rows(lines, "DOOR-NETWORK-OBS")
    matches = [row for row in rows
               if row.get("peer") == peer
               and row.get("revision") == str(revision)]
    expected_closed = "1" if state == "closed" else "0"
    expected_open = "1" if state == "open" else "0"
    return len(matches) == 1 and matches[0].get("closed") == expected_closed \
        and matches[0].get("open") == expected_open \
        and matches[0].get("finite") == "1"


def audit(logs: dict[str, Path], nonce: str, first: str, second: str,
          late_launched: bool, returncodes: dict[str, int | None],
          inputs_unchanged: bool, timed_out: bool) -> dict[str, object]:
    by_peer = {peer: protected_lines(logs[peer]) for peer in PEERS}
    all_lines = [line for peer in PEERS for line in by_peer[peer]]
    harness_rows = [line for line in all_lines
                    if "DOOR-NETWORK-HARNESS-ERROR" in line]
    behavior_rows = [line for line in all_lines
                     if "DOOR-NETWORK-BEHAVIOR-FAIL" in line]
    problems: list[str] = []
    for peer in PEERS:
        lines = by_peer[peer]
        boots = marker_rows(lines, "DOOR-NETWORK-BOOT")
        if len(boots) != 1 or boots[0].get("nonce") != nonce \
                or boots[0].get("peer") != peer:
            problems.append("%s boot identity/cardinality mismatch" % peer)
        for line in lines:
            row = tokens(line)
            if row.get("nonce") not in (None, nonce):
                problems.append("%s foreign nonce" % peer)

    request_rows: dict[str, list[dict[str, str]]] = {}
    for peer in ("A", "B"):
        request_rows[peer] = marker_rows(by_peer[peer], "DOOR-NETWORK-REQUEST")
    first_rows = request_rows[first]
    second_rows = request_rows[second]
    gate1 = len(first_rows) == 1 \
        and first_rows[0].get("invoked") == "1" \
        and first_rows[0].get("before_revision") == "0" \
        and first_rows[0].get("after_revision") == "0" \
        and first_rows[0].get("unchanged") == "1"

    rev1_rows = marker_rows(by_peer["SERVER"],
                            "DOOR-NETWORK-SERVER-REVISION")
    rev1 = [row for row in rev1_rows if row.get("revision") == "1"]
    gate2 = len(rev1) == 1 and rev1[0].get("open") == "1" \
        and all(exact_observation(by_peer[peer], peer, 1, "open")
                for peer in ("SERVER", "A", "B"))

    c_observations = marker_rows(by_peer["C"], "DOOR-NETWORK-OBS")
    gate3 = late_launched and bool(c_observations) \
        and c_observations[0].get("revision") == "1" \
        and c_observations[0].get("open") == "1" \
        and c_observations[0].get("finite") == "1"

    rev2 = [row for row in rev1_rows if row.get("revision") == "2"]
    gate4 = len(second_rows) == 1 \
        and second_rows[0].get("invoked") == "1" \
        and second_rows[0].get("before_revision") == "1" \
        and second_rows[0].get("after_revision") == "1" \
        and second_rows[0].get("unchanged") == "1" \
        and len(rev2) == 1 and rev2[0].get("closed") == "1" \
        and all(exact_observation(by_peer[peer], peer, 2, "closed")
                for peer in PEERS)

    guid_values: set[str] = set()
    for line in all_lines:
        value = tokens(line).get("guid")
        if value:
            guid_values.add(value)
    if len(guid_values) != 1:
        problems.append("NetGUID convergence mismatch: %r" % sorted(guid_values))
    if not inputs_unchanged:
        problems.append("protected input hashes changed")
    if timed_out:
        problems.append("outer watchdog timeout")
    if harness_rows:
        problems.append("protected harness error marker")
    gate_values = dict(zip(GATES, (gate1, gate2, gate3, gate4)))

    server_complete = len(marker_rows(
        by_peer["SERVER"], "DOOR-NETWORK-SERVER-COMPLETE")) == 1
    client_complete = all(len(marker_rows(
        by_peer[peer], "DOOR-NETWORK-CLIENT-COMPLETE")) == 1
        for peer in ("A", "B", "C"))
    exact_pass = not problems and not behavior_rows and all(gate_values.values()) \
        and server_complete and client_complete \
        and all(returncodes.get(peer) == 0 for peer in PEERS)
    if exact_pass:
        status, kind = "pass", "none"
    elif behavior_rows or (not problems and not all(gate_values.values())):
        status, kind = "fail", "behavior"
    else:
        status, kind = "fail", "harness"
    return {
        "schema": 1, "task_id": TASK_ID, "status": status,
        "failure_kind": kind, "tests_run": 1 if kind != "harness" else 0,
        "tests_passed": 1 if status == "pass" else 0,
        "tests_failed": 1 if kind == "behavior" else 0,
        "gate_counts": {gate: int(value) for gate, value in gate_values.items()},
        "gates": gate_values, "problems": problems,
        "behavior_markers": behavior_rows, "harness_markers": harness_rows,
        "guid_values": sorted(guid_values), "returncodes": returncodes,
        "protected_line_counts": {peer: len(by_peer[peer]) for peer in PEERS},
        "server_complete": server_complete, "clients_complete": client_complete,
    }


def main() -> int:
    args = parse_args()
    project = args.project.resolve()
    output = args.output.resolve()
    ue_root = args.ue_root.resolve()
    if output.exists() or not project.is_file() or args.watchdog_seconds < 60:
        raise RuntimeError("fresh output/project/watchdog precondition failed")
    project_root = project.parent
    game_executable = project_root / "Binaries" / "Win64" / "ThirdPerson.exe"
    executable = ue_root / "Engine" / "Binaries" / "Win64" / \
        "UnrealEditor-Cmd.exe"
    if not game_executable.is_file():
        raise RuntimeError("Game target executable missing: %s" % game_executable)
    if not executable.is_file():
        raise RuntimeError("runtime editor executable missing: %s" % executable)
    map_package = ADMISSION_MAP_PACKAGE if args.admission else FINAL_MAP_PACKAGE
    inputs = project_inputs(project, args.admission)
    before_all = optional_vector(inputs)
    if any(before_all[str(path)] is None for path in inputs):
        raise RuntimeError("required map/asset input missing")
    output.mkdir(parents=True, exist_ok=False)

    nonce = secrets.token_hex(16)
    first = "A" if secrets.randbelow(2) == 0 else "B"
    second = "B" if first == "A" else "A"
    base = 12 + secrets.randbelow(19)
    closed = "%d,%d,%d,%d" % (base, -base // 2, 4 + base % 7,
                                7 + base % 13)
    opened = "%d,%d,%d,%d" % (base + 41, 115 + base,
                                28 + base % 11, 61 + base % 23)
    port = free_port()
    logs = {peer: output / (peer.lower() + ".log") for peer in PEERS}
    stdouts = {peer: output / (peer.lower() + ".stdout.log") for peer in PEERS}
    monitor_path = output / "monitor.jsonl"
    monitor_stream = monitor_path.open("w", encoding="utf-8")

    def monitor(value: dict[str, object]) -> None:
        value = dict(value)
        value["monotonic"] = round(time.monotonic(), 3)
        monitor_stream.write(json.dumps(value, sort_keys=True) + "\n")
        monitor_stream.flush()

    common_args = [
        "-unattended", "-nopause", "-nosplash", "-nosound", "-nullrhi",
        "-deterministic", "-FPS=60", "-ExecCmds=t.MaxFPS 60", "-stdout",
        "-FullStdOutLogOutput", "-NoLoadingScreen", "-nosteam",
    ]
    common_env = os.environ.copy()
    common_env.update({
        "CRAFTBENCH_DOOR_PROTOCOL": "1",
        "CRAFTBENCH_DOOR_NONCE": nonce,
        "CRAFTBENCH_DOOR_FIRST_REQUESTER": first,
        "CRAFTBENCH_DOOR_SECOND_REQUESTER": second,
        "CRAFTBENCH_DOOR_CLOSED_TRANSFORM": closed,
        "CRAFTBENCH_DOOR_OPEN_TRANSFORM": opened,
    })
    commands: dict[str, list[str]] = {}
    processes: dict[str, subprocess.Popen] = {}
    streams = {}
    late_launched = False
    timed_out = False
    started = time.monotonic()

    write_json(output / "invocation.json", {
        "schema": 1, "task_id": TASK_ID, "map": map_package,
        "admission": args.admission, "nonce": nonce, "port": port,
        "first_requester": first, "second_requester": second,
        "closed_transform": closed, "open_transform": opened,
        "inputs": before_all, "watchdog_seconds": args.watchdog_seconds,
    })

    def spawn(peer: str) -> subprocess.Popen:
        env = common_env.copy()
        env["CRAFTBENCH_DOOR_PEER"] = peer
        if peer == "SERVER":
            command = [str(executable), str(project), map_package, "-server",
                       "-game", "-port=%d" % port]
        else:
            command = [str(executable), str(project),
                       "127.0.0.1:%d?Name=Door%s" % (port, peer), "-game"]
        command += common_args + ["-abslog=%s" % logs[peer]]
        commands[peer] = command
        stream = stdouts[peer].open("w", encoding="utf-8")
        streams[peer] = stream
        process = subprocess.Popen(
            command, stdout=stream, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", env=env,
            creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP
                           if IS_WINDOWS else 0))
        processes[peer] = process
        monitor({"event": "spawn", "peer": peer, "pid": process.pid})
        return process

    try:
        with resource_job(memory_limit_mb=max(L2_MEM_MB * 4, 24576),
                          name="cb-replicated-door") as job:
            server = spawn("SERVER")
            assign(job, server.pid)
            if wait_for(logs["SERVER"], "DOOR-NETWORK-BOOT", server, 25, monitor):
                first_child = spawn(first)
                assign(job, first_child.pid)
                first_ready = wait_for(
                    logs[first], "DOOR-NETWORK-READY", first_child, 30, monitor)
                second_ready = False
                if first_ready:
                    second_child = spawn(second)
                    assign(job, second_child.pid)
                    second_ready = wait_for(
                        logs[second], "DOOR-NETWORK-READY", second_child,
                        30, monitor)
                if first_ready and second_ready and wait_for(
                        logs["SERVER"], "revision=1", server, 25, monitor):
                    late = spawn("C")
                    assign(job, late.pid)
                    late_launched = True
            deadline = started + args.watchdog_seconds
            while time.monotonic() < deadline:
                states = {peer: process.poll()
                          for peer, process in processes.items()}
                monitor({"event": "sample", "states": states,
                         "late_launched": late_launched})
                if server.poll() is not None:
                    break
                time.sleep(0.25)
            if server.poll() is None:
                timed_out = True
            grace_deadline = min(deadline, time.monotonic() + 8.0)
            while time.monotonic() < grace_deadline and any(
                    process.poll() is None for process in processes.values()):
                monitor({"event": "grace", "states": {
                    peer: process.poll() for peer, process in processes.items()}})
                time.sleep(0.25)
            # Closing an enabled Job Object reaps only this runner's owned tree.
            # On the fail-open ungoverned path, terminate the same explicit PIDs.
            if job is None:
                for process in processes.values():
                    if process.poll() is None:
                        process.terminate()
                for process in processes.values():
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
    finally:
        for process in processes.values():
            try:
                if process.poll() is None:
                    process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        for stream in streams.values():
            stream.close()
        monitor_stream.close()

    returncodes = {peer: processes[peer].poll() if peer in processes else None
                   for peer in PEERS}
    after_all = optional_vector(inputs)
    result = audit(logs, nonce, first, second, late_launched, returncodes,
                   before_all == after_all, timed_out)
    result.update({
        "nonce": nonce, "port": port, "first_requester": first,
        "second_requester": second, "late_launched": late_launched,
        "timed_out": timed_out,
        "duration_seconds": round(time.monotonic() - started, 2),
        "inputs_before": before_all, "inputs_after": after_all,
        "inputs_unchanged": before_all == after_all,
        "logs": {peer: str(path) for peer, path in logs.items()},
        "commands": commands,
    })
    write_json(output / "aggregate.json", result)
    if result["status"] == "pass":
        print("REPLICATED-DOOR-NETWORK-PASS processes=4 gates=4/4 "
              "late_join=1 inputs_unchanged=1 output=%s" % output, flush=True)
        return 0
    print("REPLICATED-DOOR-NETWORK-%s kind=%s gates=%r problems=%r output=%s" %
          (str(result["status"]).upper(), result["failure_kind"],
           result["gate_counts"], result["problems"], output), flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

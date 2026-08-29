"""Run two protected dedicated-server predicted-dash scenarios."""

from __future__ import annotations

import argparse
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
from dash_common import MAP_PACKAGE, project_inputs, vector  # noqa: E402
from job_governor import IS_WINDOWS, L2_MEM_MB, assign, resource_job  # noqa: E402


TASK_ID = "t3-dash-responds-now-and-converges-later"
PEERS = ("SERVER", "OWNER", "OBSERVER")
SCENARIOS = ("A", "B")
GATES = (
    "AutonomousProxyRespondsBeforeAcknowledgement",
    "ServerAndOwnerConvergeAfterCorrection",
    "SimulatedProxyObservesOneDash",
    "DashCostAppliesExactlyOnce",
    "RejectedDashRollsBackWithoutCost",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--ue-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--watchdog-seconds", type=int, default=180)
    return parser.parse_args()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def free_port() -> int:
    # UIpNetDriver listens on UDP.  Probing TCP can select a port whose UDP
    # endpoint is already occupied; UE then silently increments its listen
    # port while the clients keep dialing the originally requested one.
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
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
        content = read_text(path)
        monitor({"event": "wait", "token": token,
                 "count": content.count(token), "pid": process.pid,
                 "returncode": process.poll()})
        if token in content:
            return True
        if process.poll() is not None:
            return False
        time.sleep(0.25)
    return False


def protected_lines(path: Path) -> list[str]:
    return [line.strip() for line in read_text(path).splitlines()
            if "LogPredictedDashVerifier:" in line
            and "DASH-NETWORK-" in line]


def tokens(line: str) -> dict[str, str]:
    result: dict[str, str] = {}
    marker = line.find("DASH-NETWORK-")
    if marker < 0:
        return result
    for item in line[marker:].split()[1:]:
        if "=" in item:
            key, value = item.split("=", 1)
            result[key] = value.rstrip(",")
    return result


def rows(lines: list[str], marker: str) -> list[dict[str, str]]:
    return [tokens(line) for line in lines if marker in line]


def scenario_policy(scenario: str) -> dict[str, object]:
    if scenario == "A":
        return {
            "first_accepted": True, "initial_energy": 137, "cost": 31,
            "cooldown": 7, "accepted_nonce": 71031,
            "rejected_nonce": 71097, "accepted_direction": "0.8,0.6,0",
            "rejected_direction": "-0.35,0.93675,0",
            "accepted_distance": 465.0, "rejected_distance": 355.0,
            "start": "-250,110,96", "lag": 115, "loss": 1,
        }
    return {
        "first_accepted": False, "initial_energy": 181, "cost": 43,
        "cooldown": 11, "accepted_nonce": 82083,
        "rejected_nonce": 82019, "accepted_direction": "-0.6,0.8,0",
        "rejected_direction": "0.92848,-0.37139,0",
        "accepted_distance": 575.0, "rejected_distance": 425.0,
        "start": "180,-140,96", "lag": 165, "loss": 2,
    }


def audit_scenario(logs: dict[str, Path], nonce: str, scenario: str,
                   policy: dict[str, object], returncodes: dict[str, int | None],
                   timed_out: bool) -> dict[str, object]:
    by_peer = {peer: protected_lines(logs[peer]) for peer in PEERS}
    all_lines = [line for peer in PEERS for line in by_peer[peer]]
    problems: list[str] = []
    harness = [line for line in all_lines
               if "DASH-NETWORK-HARNESS-ERROR" in line]
    behavior = [line for line in all_lines
                if "DASH-NETWORK-BEHAVIOR-FAIL" in line]
    for peer in PEERS:
        boots = rows(by_peer[peer], "DASH-NETWORK-BOOT")
        if len(boots) != 1 or boots[0].get("nonce") != nonce \
                or boots[0].get("scenario") != scenario \
                or boots[0].get("peer") != peer:
            problems.append("%s boot identity/cardinality mismatch" % peer)
        for line in by_peer[peer]:
            row = tokens(line)
            if row.get("nonce") not in (None, nonce):
                problems.append("%s foreign run nonce" % peer)
    owner_requests = rows(by_peer["OWNER"], "DASH-NETWORK-REQUEST")
    owner_predicts = rows(by_peer["OWNER"], "DASH-NETWORK-PREDICT")
    expected_requests = {str(policy["accepted_nonce"]),
                         str(policy["rejected_nonce"])}
    gate1 = len(owner_requests) == 2 and len(owner_predicts) == 2 \
        and {item.get("request") for item in owner_requests} == expected_requests \
        and {item.get("request") for item in owner_predicts} == expected_requests \
        and all(item.get("before_ack") == "1" for item in owner_predicts)

    resolves = rows(by_peer["SERVER"], "DASH-NETWORK-SERVER-RESOLVE")
    accepted = [item for item in resolves if item.get("result") == "accepted"]
    rejected = [item for item in resolves if item.get("result") == "rejected"]
    converged_owner = rows(by_peer["OWNER"], "DASH-NETWORK-CONVERGED")
    converged_observer = rows(by_peer["OBSERVER"], "DASH-NETWORK-CONVERGED")
    gate2 = len(accepted) == 1 and len(rejected) == 1 \
        and len(converged_owner) == 1 and len(converged_observer) == 1 \
        and accepted[0].get("request") == str(policy["accepted_nonce"])

    simulated = rows(by_peer["OBSERVER"], "DASH-NETWORK-SIMULATED")
    gate3 = len(simulated) == 1 \
        and simulated[0].get("accepted") == str(policy["accepted_nonce"]) \
        and simulated[0].get("count") == "1"

    server_complete = rows(by_peer["SERVER"],
                           "DASH-NETWORK-SERVER-COMPLETE")
    expected_energy = int(policy["initial_energy"]) - int(policy["cost"])
    gate4 = len(server_complete) == 1 \
        and server_complete[0].get("energy") == str(expected_energy) \
        and server_complete[0].get("accounting") == "1" \
        and server_complete[0].get("cooldown") == str(policy["cooldown"]) \
        and server_complete[0].get("accepted") == str(policy["accepted_nonce"])

    rollback = rows(by_peer["OWNER"], "DASH-NETWORK-ROLLBACK")
    rejected_predict = [item for item in owner_predicts
                        if item.get("request") == str(policy["rejected_nonce"])]
    rejection_energy = (expected_energy if policy["first_accepted"]
                        else int(policy["initial_energy"]))
    rejection_accounting = "1" if policy["first_accepted"] else "0"
    rejection_cooldown = (str(policy["cooldown"])
                          if policy["first_accepted"] else "0")
    gate5 = len(rollback) == 1 and len(rejected_predict) == 1 \
        and rollback[0].get("rejected") == str(policy["rejected_nonce"]) \
        and rollback[0].get("energy") == str(rejection_energy) \
        and rollback[0].get("accounting") == rejection_accounting \
        and rollback[0].get("cooldown") == rejection_cooldown

    for peer in PEERS:
        full = read_text(logs[peer])
        if "PktLag set to %d" % int(policy["lag"]) not in full \
                or "PktLoss set to %d" % int(policy["loss"]) not in full:
            problems.append("%s packet emulation not observed" % peer)
        expected_rate = 30 if peer == "SERVER" else 60
        if "Bringing World " not in full \
                or "max tick rate %d" % expected_rate not in full:
            problems.append("%s real-time FPS cap not observed" % peer)
        if "CreateSavedMove: Hit limit" in full:
            problems.append("%s client prediction buffer overflow" % peer)
    if harness:
        problems.append("protected harness error marker")
    if timed_out:
        problems.append("scenario watchdog timeout")
    client_complete = all(len(rows(
        by_peer[peer], "DASH-NETWORK-CLIENT-COMPLETE")) == 1
        for peer in ("OWNER", "OBSERVER"))
    if (not client_complete or len(server_complete) != 1) and not behavior:
        problems.append("terminal marker cardinality mismatch")
    controlled_behavior_shutdown = bool(behavior) \
        and returncodes.get("SERVER") == 0 \
        and all(returncodes.get(peer) is not None for peer in PEERS)
    if any(returncodes.get(peer) != 0 for peer in PEERS) \
            and not controlled_behavior_shutdown:
        problems.append("nonzero/missing peer returncode")
    gates = dict(zip(GATES, (gate1, gate2, gate3, gate4, gate5)))
    exact_pass = not problems and not behavior and all(gates.values())
    kind = "none" if exact_pass else ("harness" if problems else "behavior")
    return {
        "schema": 1, "scenario": scenario,
        "status": "pass" if exact_pass else "fail",
        "failure_kind": kind, "gates": gates,
        "gate_counts": {key: int(value) for key, value in gates.items()},
        "problems": problems, "harness_markers": harness,
        "behavior_markers": behavior, "returncodes": returncodes,
        "protected_line_counts": {peer: len(by_peer[peer]) for peer in PEERS},
    }


def run_scenario(executable: Path, project: Path, output: Path,
                 scenario: str, watchdog: int) -> dict[str, object]:
    policy = scenario_policy(scenario)
    nonce = secrets.token_hex(16)
    port = free_port()
    logs = {peer: output / (peer.lower() + ".log") for peer in PEERS}
    stdouts = {peer: output / (peer.lower() + ".stdout.log") for peer in PEERS}
    monitor_stream = (output / "monitor.jsonl").open("w", encoding="utf-8")
    processes: dict[str, subprocess.Popen] = {}
    streams = {}
    commands: dict[str, list[str]] = {}
    started = time.monotonic()
    timed_out = False
    server_exit_seen: float | None = None

    def monitor(value: dict[str, object]) -> None:
        item = dict(value)
        item["monotonic"] = round(time.monotonic(), 3)
        monitor_stream.write(json.dumps(item, sort_keys=True) + "\n")
        monitor_stream.flush()

    common_args = [
        "-unattended", "-nopause", "-nosplash", "-nosound", "-nullrhi",
        # Network emulation delays packets in wall-clock time.  Do not use
        # -deterministic here: it advances fixed simulation frames without
        # real-time throttling and can exhaust CMC's saved-move pool before a
        # deliberately lagged acknowledgement can arrive.
        "-FPS=60", "-ExecCmds=t.MaxFPS 60", "-stdout",
        "-FullStdOutLogOutput", "-NoLoadingScreen", "-nosteam",
        "-PktLag=%d" % policy["lag"], "-PktLoss=%d" % policy["loss"],
    ]
    common_env = os.environ.copy()
    common_env.update({
        "CRAFTBENCH_DASH_PROTOCOL": "1",
        "CRAFTBENCH_DASH_SCENARIO": scenario,
        "CRAFTBENCH_DASH_RUN_NONCE": nonce,
    })
    server_env = common_env.copy()
    server_env.update({
        "CRAFTBENCH_DASH_FIRST_ACCEPTED":
            "1" if policy["first_accepted"] else "0",
        "CRAFTBENCH_DASH_INITIAL_ENERGY": str(policy["initial_energy"]),
        "CRAFTBENCH_DASH_COST": str(policy["cost"]),
        "CRAFTBENCH_DASH_COOLDOWN_TICKS": str(policy["cooldown"]),
        "CRAFTBENCH_DASH_ACCEPT_NONCE": str(policy["accepted_nonce"]),
        "CRAFTBENCH_DASH_REJECT_NONCE": str(policy["rejected_nonce"]),
        "CRAFTBENCH_DASH_ACCEPT_DIRECTION": str(policy["accepted_direction"]),
        "CRAFTBENCH_DASH_REJECT_DIRECTION": str(policy["rejected_direction"]),
        "CRAFTBENCH_DASH_ACCEPT_DISTANCE": str(policy["accepted_distance"]),
        "CRAFTBENCH_DASH_REJECT_DISTANCE": str(policy["rejected_distance"]),
        "CRAFTBENCH_DASH_START": str(policy["start"]),
    })

    def spawn(peer: str, env: dict[str, str]) -> subprocess.Popen:
        local_env = env.copy()
        local_env["CRAFTBENCH_DASH_PEER"] = peer
        if peer == "SERVER":
            command = [str(executable), str(project), MAP_PACKAGE,
                       "-server", "-game", "-port=%d" % port]
        else:
            command = [str(executable), str(project),
                       "127.0.0.1:%d?Name=Dash%s" % (port, peer), "-game"]
        command += common_args + ["-abslog=%s" % logs[peer]]
        commands[peer] = command
        stream = stdouts[peer].open("w", encoding="utf-8")
        streams[peer] = stream
        process = subprocess.Popen(
            command, stdout=stream, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", env=local_env,
            creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP
                           if IS_WINDOWS else 0))
        processes[peer] = process
        monitor({"event": "spawn", "peer": peer, "pid": process.pid})
        return process

    write_json(output / "invocation.json", {
        "schema": 1, "scenario": scenario, "nonce": nonce,
        "port": port, "policy": policy, "watchdog": watchdog,
    })
    try:
        with resource_job(memory_limit_mb=max(L2_MEM_MB * 3, 18432),
                          name="cb-predicted-dash-%s" % scenario) as job:
            server = spawn("SERVER", server_env)
            assign(job, server.pid)
            # A cold Editor-Cmd startup can spend over 30 seconds loading
            # plugins before the map begins play.  This gate observes the
            # protected boot marker and remains bounded independently of the
            # per-scenario behavior watchdog.
            boot_ready = wait_for(
                logs["SERVER"], "DASH-NETWORK-BOOT", server, 75.0, monitor)
            listen_ready = boot_ready and wait_for(
                logs["SERVER"], "IpNetDriver listening on port %d" % port,
                server, 2.0, monitor)
            if boot_ready and not listen_ready:
                monitor({"event": "server-port-mismatch",
                         "requested_port": port})
                server.terminate()
            if listen_ready:
                owner = spawn("OWNER", common_env)
                assign(job, owner.pid)
                time.sleep(1.5)
                observer = spawn("OBSERVER", common_env)
                assign(job, observer.pid)
            deadline = started + watchdog
            while time.monotonic() < deadline:
                states = {peer: process.poll()
                          for peer, process in processes.items()}
                monitor({"event": "sample", "states": states})
                if len(processes) == 3 and all(
                        value is not None for value in states.values()):
                    break
                if server.poll() is not None and len(processes) < 3:
                    break
                if len(processes) == 3 and server.poll() is not None:
                    if server_exit_seen is None:
                        server_exit_seen = time.monotonic()
                    elif time.monotonic() - server_exit_seen >= 3.0:
                        monitor({"event": "controlled-peer-shutdown",
                                 "reason": "server-exited"})
                        break
                time.sleep(0.25)
            if time.monotonic() >= deadline and any(
                    process.poll() is None for process in processes.values()):
                timed_out = True
            grace = time.monotonic() + 5.0
            while time.monotonic() < grace and any(
                    process.poll() is None for process in processes.values()):
                time.sleep(0.2)
            if job is None:
                for process in processes.values():
                    if process.poll() is None:
                        process.terminate()
    finally:
        for process in processes.values():
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
        for stream in streams.values():
            stream.close()
        monitor_stream.close()
    returncodes = {peer: processes[peer].poll() if peer in processes else None
                   for peer in PEERS}
    result = audit_scenario(
        logs, nonce, scenario, policy, returncodes, timed_out)
    result.update({
        "nonce": nonce, "port": port, "policy": policy,
        "timed_out": timed_out,
        "duration_seconds": round(time.monotonic() - started, 2),
        "logs": {peer: str(path) for peer, path in logs.items()},
        "commands": commands,
    })
    write_json(output / "scenario.json", result)
    return result


def main() -> int:
    args = parse_args()
    project = args.project.resolve()
    ue_root = args.ue_root.resolve()
    output = args.output.resolve()
    executable = ue_root / "Engine" / "Binaries" / "Win64" / \
        "UnrealEditor-Cmd.exe"
    game = project.parent / "Binaries" / "Win64" / "ThirdPerson.exe"
    if output.exists() or not project.is_file() or not executable.is_file() \
            or not game.is_file() or args.watchdog_seconds < 90:
        raise RuntimeError("fresh output/project/build/watchdog precondition failed")
    input_paths = project_inputs(project)
    if not input_paths or not any(path.suffix == ".umap" for path in input_paths):
        raise RuntimeError("map/source input inventory incomplete")
    before = vector(input_paths)
    output.mkdir(parents=True, exist_ok=False)
    results = []
    per_scenario = max(80, min(120, args.watchdog_seconds // 2))
    for scenario in SCENARIOS:
        scenario_out = output / ("scenario-" + scenario.lower())
        scenario_out.mkdir(parents=False, exist_ok=False)
        result = run_scenario(
            executable, project, scenario_out, scenario, per_scenario)
        results.append(result)
        if result["failure_kind"] == "harness":
            break
    after = vector(input_paths)
    unchanged = before == after
    complete = len(results) == 2
    gate_values = {gate: complete and all(
        result.get("gates", {}).get(gate) is True for result in results)
        for gate in GATES}
    harness = [problem for result in results
               if result.get("failure_kind") == "harness"
               for problem in result.get("problems", [])]
    behavior = [line for result in results
                for line in result.get("behavior_markers", [])]
    if not unchanged:
        harness.append("protected inputs changed")
    exact_pass = complete and unchanged and not harness and not behavior \
        and all(gate_values.values()) \
        and all(result.get("status") == "pass" for result in results)
    kind = "none" if exact_pass else ("harness" if harness or not complete
            else "behavior")
    aggregate = {
        "schema": 1, "task_id": TASK_ID,
        "status": "pass" if exact_pass else "fail",
        "failure_kind": kind, "tests_run": len(results),
        "tests_passed": sum(result.get("status") == "pass"
                            for result in results),
        "tests_failed": sum(result.get("failure_kind") == "behavior"
                            for result in results),
        "gates": gate_values,
        "gate_counts": {gate: int(value) for gate, value in gate_values.items()},
        "scenarios": results, "problems": harness,
        "behavior_markers": behavior,
        "inputs_before": before, "inputs_after": after,
        "inputs_unchanged": unchanged,
    }
    write_json(output / "aggregate.json", aggregate)
    if exact_pass:
        print("PREDICTED-DASH-NETWORK-PASS scenarios=2 processes=6 "
              "gates=5/5 inputs_unchanged=1 output=%s" % output, flush=True)
        return 0
    print("PREDICTED-DASH-NETWORK-FAIL kind=%s tests=%d gates=%r "
          "problems=%r output=%s" %
          (kind, len(results), aggregate["gate_counts"], harness, output),
          flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Fail-closed, one-boundary-at-a-time admission runner."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

#: Engine root. Override with CB_UE_ROOT; defaults to Epic's standard install.
_UE_ROOT = Path(os.environ.get("CB_UE_ROOT", r"C:\Program Files\Epic Games\UE_5.8"))


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TASK_ID = "t3-both-walkers-yield-and-still-arrive"
PROJECT = REPO / "UE-projects" / "ThirdPerson" / "ThirdPerson.uproject"
CONTENT = PROJECT.parent / "Content"
MAP_NAME = "L_BothWalkersYieldAdmission"
MAP_PACKAGE = "/Game/Maps/%s/%s" % (TASK_ID, MAP_NAME)
DISPLAY_NAME = "BothWalkersYieldAdmissionFunctionalTest"
EXACT_FILTER = ("Project.Functional Tests.Maps.%s.%s.%s" %
                (TASK_ID, MAP_NAME, DISPLAY_NAME))
BASELINE_FILE = CONTENT / "Tasks" / TASK_ID / "BP_YieldingWalker.uasset"
ADMISSION_FILE = (CONTENT / "__CraftBenchAdmission" / TASK_ID /
                  "BP_YieldingWalker_Admission.uasset")
ADMISSION_MAP_FILE = CONTENT / "Maps" / TASK_ID / (MAP_NAME + ".umap")
FINAL_MAP_FILE = CONTENT / "Maps" / TASK_ID / "L_BothWalkersYield.umap"
REFERENCE_DIR = HERE.parent / "reference"
CHECKPOINTS = ("BothAgentsConflictDrivenSteering",
               "BothAgentsKeepForwardProgress", "NoOverlapEnRoute",
               "BothAgentsReachOwnGoals")
CONTROL_GATES = {
    "no-avoidance": "BothAgentsConflictDrivenSteering",
    "freeze-one": "BothAgentsKeepForwardProgress",
    "collision-disabled": "NoOverlapEnRoute",
    "permanent-detour": "BothAgentsReachOwnGoals",
}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def snapshot(path):
    if path.is_symlink() or (getattr(path, "is_junction", lambda: False)()):
        raise RuntimeError("protected path is a link: " + str(path))
    if not path.exists():
        return {"state": "ABSENT"}
    if path.is_file():
        return {"state": "FILE", "size": path.stat().st_size,
                "sha256": sha256(path)}
    files = {}
    for item in sorted(path.rglob("*")):
        if item.is_symlink() or getattr(item, "is_junction", lambda: False)():
            raise RuntimeError("protected tree contains link: " + str(item))
        if item.is_file():
            files[item.relative_to(path).as_posix()] = sha256(item)
    return {"state": "DIRECTORY", "files": files}


def all_locks():
    paths = (BASELINE_FILE, ADMISSION_FILE, ADMISSION_MAP_FILE,
             FINAL_MAP_FILE, REFERENCE_DIR)
    return {str(path): snapshot(path) for path in paths}


def write_json(path, value):
    path.write_text(json.dumps(
        value, indent=2, sort_keys=True, default=str) + "\n",
                    encoding="utf-8")


def editor_command(ue_root, phase, output):
    editor = (ue_root / "Engine" / "Binaries" / "Win64" /
              "UnrealEditor-Cmd.exe")
    base = [str(editor), str(PROJECT), "-unattended", "-nopause", "-nosplash",
            "-nop4", "-stdout", "-FullStdOutLogOutput",
            "-abslog=" + str(output / "Unreal.log")]
    scripts = {
        "baseline-assets": (HERE / "author_assets.py", "baseline", None),
        "baseline-readback": (HERE / "introspect_walker_yield.py",
                              "baseline", "asset"),
        "admission-assets": (HERE / "author_assets.py", "admission", None),
        "admission-readback": (HERE / "introspect_walker_yield.py",
                               "admission", "asset"),
        "admission-map": (HERE / "author_admission_map.py", None, None),
        "admission-map-readback": (HERE / "introspect_walker_yield.py",
                                   "admission", "map"),
    }
    if phase in scripts:
        script, mode, kind = scripts[phase]
        # Asset and readback phases do not need a rendered viewport. Map
        # authoring deliberately retains a real RHI for navigation/map parity.
        if phase != "admission-map":
            base.append("-nullrhi")
        return base + ["-run=pythonscript", "-script=" + str(script)], mode, kind
    if phase == "enumerate":
        base.insert(2, MAP_PACKAGE)
        return (base + ["-nullrhi",
                        "-ExecCmds=Automation List; Quit",
                        "-TestExit=Automation Test Queue Empty"], None, None)
    raise AssertionError(phase)


def allowed_output(phase):
    return {
        "baseline-assets": BASELINE_FILE,
        "admission-assets": ADMISSION_FILE,
        "admission-map": ADMISSION_MAP_FILE,
    }.get(phase)


def preflight(phase):
    requirements = {
        "baseline-readback": (BASELINE_FILE,),
        "admission-readback": (ADMISSION_FILE,),
        "admission-map": (BASELINE_FILE, ADMISSION_FILE),
        "admission-map-readback": (BASELINE_FILE, ADMISSION_FILE,
                                   ADMISSION_MAP_FILE),
        "enumerate": (BASELINE_FILE, ADMISSION_FILE, ADMISSION_MAP_FILE),
        "test": (BASELINE_FILE, ADMISSION_FILE, ADMISSION_MAP_FILE),
    }.get(phase, ())
    missing = [str(path) for path in requirements
               if not path.is_file() or path.stat().st_size <= 0]
    if missing:
        raise RuntimeError("required retained inputs missing: %r" % missing)
    output = allowed_output(phase)
    if output is not None and output.exists():
        raise RuntimeError("refusing existing exact output: " + str(output))
    if phase != "baseline-assets" and phase.startswith("baseline") \
            and not BASELINE_FILE.is_file():
        raise RuntimeError("baseline missing")
    if FINAL_MAP_FILE.exists():
        raise RuntimeError("final map must remain absent during admission")


def terminate_owned_tree(process):
    if process.poll() is None:
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       check=False, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=30)


def run_owned(command, environment, timeout, stdout_path):
    with stdout_path.open("w", encoding="utf-8") as stream:
        process = subprocess.Popen(command, cwd=REPO, env=environment,
                                   stdout=stream, stderr=subprocess.STDOUT,
                                   text=True)
        try:
            return process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            terminate_owned_tree(process)
            return 124


def parse_enumeration(log_path):
    text = log_path.read_text(encoding="utf-8", errors="replace")
    candidates = sorted(set(re.findall(
        r"Project\.Functional Tests\.[A-Za-z0-9_ .\-/]+\."
        + re.escape(DISPLAY_NAME), text)))
    return candidates


def child_test(output, ue_root, control):
    if control == "none":
        os.environ.pop("CRAFTBENCH_WALKER_YIELD_CONTROL", None)
    else:
        os.environ["CRAFTBENCH_WALKER_YIELD_CONTROL"] = control
    sys.path.insert(0, str(REPO / "tools" / "verify-single"))
    sys.path.insert(0, str(REPO / "tools" / "verify-single" / "layers"))
    from l2_pie import run_l2
    result = run_l2(
        ue_root=ue_root, project_path=PROJECT, test_filter=EXACT_FILTER,
        log_path=output / "l2.log", report_dir=output / "report",
        map_name=MAP_NAME, map_package_path=MAP_PACKAGE, use_nullrhi=True,
        fps=60, timeout_seconds=600.0, expected_test_count=1)
    write_json(output / "l2_result.json", dataclasses.asdict(result))
    return 0 if result.status == "pass" else 1


def audit_test(output, exit_code, before, after, control):
    result = json.loads((output / "l2_result.json").read_text(
        encoding="utf-8"))
    index = json.loads((output / "report" / "index.json").read_text(
        encoding="utf-8-sig"))
    tests = index.get("tests", [])
    log_text = (output / "l2.log").read_text(
        encoding="utf-8", errors="replace")
    problems = []
    expected_gate = CONTROL_GATES.get(control)
    expected_state = "Fail" if expected_gate else "Success"
    expected_status = "fail" if expected_gate else "pass"
    expected_exit = 1 if expected_gate else 0
    if exit_code != expected_exit or result.get("status") != expected_status:
        problems.append("runner/result did not match expected control verdict")
    if len(tests) != 1 or tests[0].get("fullTestPath") != EXACT_FILTER \
            or tests[0].get("state") != expected_state:
        problems.append("exact count/path/state mismatch")
    if before != after:
        problems.append("retained hashes changed")
    minimum_checkpoints = 1 if expected_gate else 8
    if log_text.count("CB-CP") < minimum_checkpoints:
        problems.append("checkpoint log count below eight")
    if "WALKER-YIELD-TELEMETRY" not in log_text:
        problems.append("live walker telemetry absent")
    if "HARNESS-PRECONDITION:" in log_text:
        problems.append("harness precondition present")
    if "Ensure condition failed" in log_text or "Fatal error:" in log_text:
        problems.append("ensure or fatal present")
    if expected_gate:
        if expected_gate + ": At world" not in log_text:
            problems.append("expected named control gate absent: "
                            + expected_gate)
        unexpected = [gate for gate in CHECKPOINTS if gate != expected_gate
                      and gate + ": At world" in log_text]
        if unexpected:
            problems.append("unexpected named control gate(s): %r" % unexpected)
    return {"status": "PASS" if not problems else "FAIL",
            "control": control, "expected_gate": expected_gate,
            "exact_filter": EXACT_FILTER, "expected_test_count": 1,
            "result": result, "tests": tests, "locks_before": before,
            "locks_after": after, "named_gates": CHECKPOINTS,
            "problems": problems}


def parent(args):
    output = args.output.resolve()
    if output.exists():
        raise SystemExit("fresh output already exists: " + str(output))
    preflight(args.phase)
    output.mkdir(parents=True)
    before = all_locks()
    if args.phase == "test":
        command = [sys.executable, str(Path(__file__).resolve()), "--child-test",
                   "--output", str(output), "--ue-root", str(args.ue_root),
                   "--control", args.control]
        exit_code = run_owned(command, os.environ.copy(), args.watchdog,
                              output / "runner.stdout.log")
        after = all_locks()
        audit = audit_test(output, exit_code, before, after, args.control)
        write_json(output / "audit.json", audit)
        return 0 if audit["status"] == "PASS" else 1
    command, mode, kind = editor_command(args.ue_root, args.phase, output)
    environment = os.environ.copy()
    if mode:
        environment["CRAFTBENCH_WALKER_YIELD_MODE"] = mode
    if kind:
        environment["CRAFTBENCH_WALKER_YIELD_KIND"] = kind
    write_json(output / "command.json", {"argv": command, "mode": mode,
               "kind": kind, "locks_before": before})
    exit_code = run_owned(command, environment, args.watchdog,
                          output / "runner.stdout.log")
    after = all_locks()
    problems = []
    output_path = allowed_output(args.phase)
    for path, value in before.items():
        if output_path is not None and Path(path) == output_path:
            continue
        if after[path] != value:
            problems.append("protected path changed: " + path)
    if exit_code != 0:
        problems.append("editor exit=%d" % exit_code)
    if output_path is not None and not output_path.is_file():
        problems.append("exact output absent: " + str(output_path))
    log_path = output / "Unreal.log"
    log_text = (log_path.read_text(encoding="utf-8", errors="replace")
                if log_path.is_file() else "")
    markers = {
        "baseline-assets": "WALKER-YIELD-ASSET-SAVED mode=baseline",
        "baseline-readback": "WALKER-YIELD-ASSET-READBACK mode=baseline PASS ",
        "admission-assets": "WALKER-YIELD-ASSET-SAVED mode=admission",
        "admission-readback": "WALKER-YIELD-ASSET-READBACK mode=admission PASS ",
        "admission-map": "WALKER-YIELD-MAP-SAVED mode=admission",
        "admission-map-readback":
            "WALKER-YIELD-MAP-READBACK mode=admission",
    }
    expected_marker = markers.get(args.phase)
    if expected_marker is not None and log_text.count(expected_marker) != 1:
        problems.append("anchored marker exact-once mismatch: "
                        + expected_marker)
    if "WALKER-YIELD-" in log_text and "-FAILED:" in log_text:
        problems.append("task-local Python failure marker present")
    if "Ensure condition failed" in log_text:
        problems.append("ensure present in author/readback log")
    candidates = None
    if args.phase == "enumerate" and exit_code == 0:
        candidates = parse_enumeration(output / "Unreal.log")
        if candidates != [EXACT_FILTER]:
            problems.append("enumeration exact-one mismatch: %r" % candidates)
    audit = {"status": "PASS" if not problems else "FAIL",
             "phase": args.phase, "exit_code": exit_code,
             "exact_filter": EXACT_FILTER, "candidates": candidates,
             "locks_before": before, "locks_after": after,
             "problems": problems}
    write_json(output / "audit.json", audit)
    return 0 if not problems else 1


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=(
        "baseline-assets", "baseline-readback", "admission-assets",
        "admission-readback", "admission-map", "admission-map-readback",
        "enumerate", "test"))
    parser.add_argument("--ue-root", type=Path, default=_UE_ROOT)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--watchdog", type=int, default=720)
    parser.add_argument("--control", choices=("none", *CONTROL_GATES),
                        default="none")
    parser.add_argument("--child-test", action="store_true",
                        help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.watchdog < 60:
        parser.error("watchdog must be >=60")
    if not args.child_test and args.phase is None:
        parser.error("--phase is required")
    if not args.child_test and args.control != "none" and args.phase != "test":
        parser.error("--control is only valid with --phase test")
    return args


if __name__ == "__main__":
    OPTIONS = parse_args()
    if OPTIONS.child_test:
        raise SystemExit(child_test(OPTIONS.output.resolve(),
                                    OPTIONS.ue_root.resolve(),
                                    OPTIONS.control))
    raise SystemExit(parent(OPTIONS))

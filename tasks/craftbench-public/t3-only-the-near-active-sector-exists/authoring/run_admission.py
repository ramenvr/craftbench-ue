"""Run one exact Near Active Sector admission fixture, fail closed."""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
from pathlib import Path
import subprocess
import sys

#: Engine root. Override with CB_UE_ROOT; defaults to Epic's standard install.
_UE_ROOT = Path(os.environ.get("CB_UE_ROOT", r"C:\Program Files\Epic Games\UE_5.8"))


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import contract


PROJECT = contract.PROJECT / "ThirdPerson.uproject"
DISPLAY_NAMES = {
    "A": "NearActiveSectorAdmissionA",
    "B": "NearActiveSectorAdmissionB",
}
PASS_FIXTURE_PREFIXES = {
    "A": "fixture=NearActiveSectorAdmissionFunctionalTestA_",
    "B": "fixture=NearActiveSectorAdmissionFunctionalTestB_",
}
EXACT_FILTERS = {
    fixture: (
        "Project.Functional Tests.__CraftBenchAdmission."
        f"{contract.TASK_ID}.{contract.MAP_NAME}.{display}"
    )
    for fixture, display in DISPLAY_NAMES.items()
}
NAMED_GATES = (
    "InactiveLayerHasNoLiveActors",
    "ActiveNearCellLoadsExactActorSet",
    "LeavingCellUnloadsPriorIdentities",
    "ReturningCellCreatesFreshValidInstances",
)


def write_json(path: Path, value) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def retained_snapshot() -> dict:
    contract.require_production_absent()
    layers = contract.file_vector(contract.layer_files(allow_map=True))
    map_vector = contract.file_vector(contract.map_files())
    if len(map_vector) != contract.EXPECTED_MAP_FILE_COUNT:
        raise RuntimeError(
            "map file count mismatch: expected=%d actual=%d"
            % (contract.EXPECTED_MAP_FILE_COUNT, len(map_vector))
        )
    manifest = contract.manifest_sha(map_vector)
    if manifest != contract.EXPECTED_MAP_MANIFEST_SHA:
        raise RuntimeError(
            "map manifest mismatch: expected=%s actual=%s"
            % (contract.EXPECTED_MAP_MANIFEST_SHA, manifest)
        )
    expected_layer_hashes = {
        key: digest.upper()
        for key, digest in contract.EXPECTED_LAYER_HASHES.items()
    }
    actual_layer_hashes = {key: digest for key, (_, digest) in layers.items()}
    if actual_layer_hashes != expected_layer_hashes:
        raise RuntimeError("retained data-layer hashes changed")
    return {
        "map_files": map_vector,
        "map_manifest_sha256": manifest,
        "protected": contract.protected_vector(),
        "production_absent": True,
    }


def ensure_no_external_heavy_process() -> None:
    command = (
        "$p=Get-CimInstance Win32_Process | Where-Object { "
        "$_.Name -in @('UnrealEditor.exe','UnrealEditor-Cmd.exe',"
        "'UnrealBuildTool.exe','cl.exe','link.exe') }; "
        "$p | ForEach-Object { \"$($_.ProcessId)|$($_.Name)|$($_.CommandLine)\" }"
    )
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    if completed.returncode != 0:
        raise RuntimeError("could not inspect heavy-process ownership")
    observed = completed.stdout.strip()
    if observed:
        raise RuntimeError("external heavy process already active: " + observed)


def terminate_owned_tree(process: subprocess.Popen) -> None:
    if process.poll() is None:
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
        )


def run_owned(command: list[str], timeout: int, stdout_path: Path) -> int:
    with stdout_path.open("w", encoding="utf-8") as stream:
        process = subprocess.Popen(
            command,
            cwd=REPO,
            env=os.environ.copy(),
            stdout=stream,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            return process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            terminate_owned_tree(process)
            return 124


def child_test(output: Path, ue_root: Path, fixture: str) -> int:
    sys.path.insert(0, str(REPO / "tools" / "verify-single"))
    sys.path.insert(0, str(REPO / "tools" / "verify-single" / "layers"))
    from l2_pie import run_l2

    result = run_l2(
        ue_root=ue_root,
        project_path=PROJECT,
        test_filter=EXACT_FILTERS[fixture],
        log_path=output / "l2.log",
        report_dir=output / "report",
        map_name=contract.MAP_NAME,
        map_package_path=contract.MAP_PACKAGE,
        use_nullrhi=True,
        fps=60,
        timeout_seconds=600.0,
        expected_test_count=1,
    )
    write_json(output / "l2_result.json", dataclasses.asdict(result))
    return 0 if result.status == "pass" else 1


def audit(output: Path, fixture: str, exit_code: int, before: dict,
          after: dict) -> dict:
    problems: list[str] = []
    result_path = output / "l2_result.json"
    report_path = output / "report" / "index.json"
    log_path = output / "l2.log"
    if not result_path.is_file():
        problems.append("l2_result.json missing")
        result = {}
    else:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    if not report_path.is_file():
        problems.append("authoritative report/index.json missing")
        report = {}
    else:
        report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    log_text = (
        log_path.read_text(encoding="utf-8", errors="replace")
        if log_path.is_file()
        else ""
    )
    tests = report.get("tests", []) if isinstance(report, dict) else []
    expected_filter = EXACT_FILTERS[fixture]
    expected_display = DISPLAY_NAMES[fixture]
    if exit_code != 0:
        problems.append("owned child exit=%d" % exit_code)
    if result.get("status") != "pass" or result.get("result_source") != "json":
        problems.append("L2 did not produce a JSON-backed pass")
    if (
        result.get("tests_run") != 1
        or result.get("tests_passed") != 1
        or result.get("tests_failed") != 0
        or result.get("tests_skipped") != 0
    ):
        problems.append("L2 aggregate is not exact 1/1/0/0")
    if len(tests) != 1:
        problems.append("authoritative report test count is not one")
    elif (
        tests[0].get("fullTestPath") != expected_filter
        or tests[0].get("testDisplayName") != expected_display
        or tests[0].get("state") != "Success"
    ):
        problems.append("authoritative report path/display/state mismatch")
    if before != after:
        problems.append("retained map/source/protected snapshot changed")
    telemetry = [
        line
        for line in log_text.splitlines()
        if "LogTemp: Display: NEAR-ACTIVE-SECTOR-TELEMETRY" in line
        and "LogAutomationController" not in line
    ]
    if len(telemetry) != 5:
        problems.append("telemetry line count expected=5 actual=%d" % len(telemetry))
    for checkpoint in range(5):
        if sum(("cp=%d " % checkpoint) in line for line in telemetry) != 1:
            problems.append("telemetry checkpoint %d not exact-one" % checkpoint)
    pass_lines = [
        line
        for line in log_text.splitlines()
        if "LogTemp: Display: NEAR-ACTIVE-SECTOR-PASS fixture=" in line
        and "LogAutomationController" not in line
    ]
    if len(pass_lines) != 1:
        problems.append("terminal task pass marker is not exact-one")
    else:
        if PASS_FIXTURE_PREFIXES[fixture] not in pass_lines[0]:
            problems.append("task pass marker fixture mismatch")
        for gate in NAMED_GATES:
            if gate not in pass_lines[0]:
                problems.append("task pass marker missing gate: " + gate)
    forbidden = (
        "GATE[",
        "HARNESS-PRECONDITION:",
        "Ensure condition failed",
        "Assertion failed",
        "LowLevelFatalError",
        "Fatal error:",
        "NEAR-ACTIVE-SECTOR-ERROR",
    )
    for marker in forbidden:
        if marker in log_text:
            problems.append("forbidden log marker present: " + marker)
    lifecycle = [
        line
        for line in log_text.splitlines()
        if "LogTemp: Display: NEAR-ACTIVE-SECTOR-LIFECYCLE" in line
        and "LogAutomationController" not in line
    ]
    left = [line for line in lifecycle if "stage=left " in line]
    returned = [line for line in lifecycle if "stage=returned " in line]
    if len(left) != 1 or "retired_valid=2 endplay=2" not in left[0]:
        problems.append("departure lifecycle evidence mismatch")
    if len(returned) != 1:
        problems.append("return lifecycle evidence is not exact-one")
    else:
        import re
        match = re.search(r"reused_new_epoch=(\d+) recreated=(\d+)", returned[0])
        if match is None or int(match.group(1)) + int(match.group(2)) != 2:
            problems.append("return lifecycle cardinality mismatch")
    return {
        "status": "PASS" if not problems else "FAIL",
        "fixture": fixture,
        "exact_filter": expected_filter,
        "expected_display": expected_display,
        "exit_code": exit_code,
        "result": result,
        "tests": tests,
        "telemetry": telemetry,
        "pass_lines": pass_lines,
        "lifecycle": lifecycle,
        "locks_before": before,
        "locks_after": after,
        "named_gates": NAMED_GATES,
        "problems": problems,
    }


def parent(args) -> int:
    output = args.output.resolve()
    if output.exists():
        raise SystemExit("fresh output already exists: " + str(output))
    ensure_no_external_heavy_process()
    before = retained_snapshot()
    output.mkdir(parents=True)
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--child-test",
        "--fixture",
        args.fixture,
        "--output",
        str(output),
        "--ue-root",
        str(args.ue_root.resolve()),
    ]
    write_json(
        output / "preflight.json",
        {
            "fixture": args.fixture,
            "exact_filter": EXACT_FILTERS[args.fixture],
            "expected_test_count": 1,
            "rhi": "null",
            "fps": 60,
            "watchdog_seconds": args.watchdog,
            "locks_before": before,
            "owned_child_argv": command,
        },
    )
    exit_code = run_owned(command, args.watchdog, output / "runner.stdout.log")
    after = retained_snapshot()
    evidence = audit(output, args.fixture, exit_code, before, after)
    write_json(output / "audit.json", evidence)
    print(
        "NEAR-ACTIVE-SECTOR-ADMISSION-RUNNER "
        "fixture=%s status=%s problems=%d output=%s"
        % (args.fixture, evidence["status"], len(evidence["problems"]), output)
    )
    return 0 if evidence["status"] == "PASS" else 1


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", choices=sorted(DISPLAY_NAMES), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ue-root", type=Path, default=_UE_ROOT)
    parser.add_argument("--watchdog", type=int, default=720)
    parser.add_argument("--child-test", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--audit-existing", action="store_true",
                        help="read-only re-audit of a preserved completed leg")
    args = parser.parse_args()
    if args.watchdog < 60:
        parser.error("--watchdog must be at least 60 seconds")
    return args


if __name__ == "__main__":
    OPTIONS = parse_args()
    if OPTIONS.child_test:
        raise SystemExit(
            child_test(
                OPTIONS.output.resolve(), OPTIONS.ue_root.resolve(), OPTIONS.fixture
            )
        )
    if OPTIONS.audit_existing:
        EXISTING = OPTIONS.output.resolve()
        if not EXISTING.is_dir():
            raise SystemExit("existing output directory missing: " + str(EXISTING))
        PREFLIGHT = json.loads(
            (EXISTING / "preflight.json").read_text(encoding="utf-8")
        )
        EVIDENCE = audit(
            EXISTING,
            OPTIONS.fixture,
            0,
            PREFLIGHT["locks_before"],
            json.loads(json.dumps(retained_snapshot(), default=str)),
        )
        write_json(EXISTING / "audit.json", EVIDENCE)
        print(
            "NEAR-ACTIVE-SECTOR-ADMISSION-REAUDIT fixture=%s status=%s problems=%d"
            % (OPTIONS.fixture, EVIDENCE["status"], len(EVIDENCE["problems"]))
        )
        raise SystemExit(0 if EVIDENCE["status"] == "PASS" else 1)
    raise SystemExit(parent(OPTIONS))

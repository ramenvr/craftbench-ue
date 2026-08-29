"""Run exactly one fail-closed real-RHI two-LocalPlayer admission probe.

This script is intentionally admission-only. It cannot grade a submission and
refuses until the protected admission map exists. It owns an independent parent
watchdog because a silent editor child is not a verdict.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time
from typing import Any

#: Engine root. Override with CB_UE_ROOT; defaults to Epic's standard install.
_UE_ROOT = Path(os.environ.get("CB_UE_ROOT", r"C:\Program Files\Epic Games\UE_5.8"))


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TASK_ID = "t3-each-local-player-owns-its-top-modal"
VERIFY = REPO / "tools" / "verify-single"
PROJECT = REPO / "UE-projects" / "ThirdPerson" / "ThirdPerson.uproject"
PROJECT_ROOT = PROJECT.parent
PROJECT_CONFIG = PROJECT_ROOT / "Config"
TASK_SPEC = HERE.parent / "task.md"
SOURCE_DIR = (
    PROJECT_ROOT / "Source" / "CraftBenchTests" / "Tasks" / TASK_ID)

MAP_NAME = "L_LocalPlayerModalIsolationAdmission"
MAP_PACKAGE = "/Game/Maps/%s/%s" % (TASK_ID, MAP_NAME)
MAP_FILE = PROJECT_ROOT / "Content" / "Maps" / TASK_ID / (MAP_NAME + ".umap")
PRODUCTION_MAP = (
    PROJECT_ROOT / "Content" / "Maps" / TASK_ID /
    "L_LocalPlayerModalIsolation.umap")
TASK_ASSETS = PROJECT_ROOT / "Content" / "Tasks" / TASK_ID
REFERENCE = HERE.parent / "reference"
EXACT_FILTER = (
    "Project.Functional Tests.Maps.%s.%s."
    "LocalPlayerModalIsolationAdmissionFunctionalTest" %
    (TASK_ID, MAP_NAME))
EXPECTED_DISPLAY = "LocalPlayerModalIsolationAdmissionFunctionalTest"
EXPECTED_SUCCESS = (
    "LOCAL-PLAYER-MODAL-ADMISSION-PASS players=2 epochs=2 "
    "EachPlayerOwnsIndependentActionRouter "
    "TopModalConsumesOnlyOwningPlayersAction "
    "DismissRestoresOnlyThatPlayersFocus "
    "OtherPlayersStackNeverChanges")
CONFIG_FRAGMENTS = (
    HERE.parent / "ue-config" / "DefaultEngine.ini",
    HERE.parent / "ue-config" / "DefaultGame.ini",
)
LOCKED_FILES = (
    TASK_SPEC,
    SOURCE_DIR / "LocalPlayerModalIsolationAdmissionFunctionalTest.cpp",
    SOURCE_DIR / "LocalPlayerModalIsolationAdmissionFunctionalTest.h",
    MAP_FILE,
) + CONFIG_FRAGMENTS


def is_reparse(path: Path) -> bool:
    info = path.lstat()
    attributes = getattr(info, "st_file_attributes", 0)
    return bool(attributes &
                getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def require_plain_repo_path(path: Path) -> None:
    """Reject links/reparse points from an existing path back to repo root."""
    current = Path(os.path.abspath(os.fspath(path)))
    stop = Path(os.path.abspath(os.fspath(REPO)))
    while True:
        if not current.exists():
            raise RuntimeError("required path missing: %s" % current)
        if current.is_symlink() or is_reparse(current):
            raise RuntimeError("reparse path rejected: %s" % current)
        if current == stop:
            return
        if stop not in current.parents:
            raise RuntimeError("path escaped repository: %s" % path)
        current = current.parent


def require_absent(path: Path, label: str) -> None:
    if os.path.lexists(path):
        raise RuntimeError("%s must remain absent: %s" % (label, path))


def write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def protected_snapshot() -> dict[str, dict[str, object]]:
    snapshot: dict[str, dict[str, object]] = {}
    for path in LOCKED_FILES:
        require_plain_repo_path(path)
        if not path.is_file():
            raise RuntimeError("protected lock is not a file: %s" % path)
        rel = path.relative_to(REPO).as_posix()
        snapshot[rel] = {
            "size": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    return snapshot


def preflight() -> dict[str, Any]:
    for path in (PROJECT, TASK_SPEC, SOURCE_DIR, MAP_FILE, PROJECT_CONFIG):
        require_plain_repo_path(path)
    source_inventory = sorted(
        item.name for item in SOURCE_DIR.iterdir() if item.is_file())
    expected_source = [
        "LocalPlayerModalIsolationAdmissionFunctionalTest.cpp",
        "LocalPlayerModalIsolationAdmissionFunctionalTest.h",
    ]
    if source_inventory != expected_source:
        raise RuntimeError(
            "admission source inventory mismatch: %s" % source_inventory)
    require_absent(PRODUCTION_MAP, "production map")
    require_absent(TASK_ASSETS, "editable task assets")
    require_absent(REFERENCE, "reference")
    return {
        "filter": EXACT_FILTER,
        "display": EXPECTED_DISPLAY,
        "expected_test_count": 1,
        "map_package": MAP_PACKAGE,
        "rhi": "real-offscreen",
        "fps": 60,
        "admission_source": source_inventory,
        "production_map_absent": True,
        "task_assets_absent": True,
        "reference_absent": True,
        "protected_snapshot": protected_snapshot(),
    }


def apply_config_overlay() -> dict[str, Any]:
    sys.path.insert(0, str(VERIFY))
    import config_overlay  # noqa: PLC0415

    fragments = config_overlay.discover(TASK_SPEC)
    expected = {"DefaultEngine.ini", "DefaultGame.ini"}
    if set(fragments) != expected:
        raise RuntimeError(
            "config fragment inventory mismatch: %s" % sorted(fragments))
    before: dict[str, bytes | None] = {}
    for name in sorted(expected):
        target = PROJECT_CONFIG / name
        require_plain_repo_path(target)
        before[name] = target.read_bytes()
    try:
        applied = config_overlay.apply(PROJECT_CONFIG, fragments, TASK_ID)
    except Exception:
        for name, original in before.items():
            target = PROJECT_CONFIG / name
            if original is not None:
                target.write_bytes(original)
        raise
    if {item.ini_name for item in applied} != expected:
        config_overlay.revert(PROJECT_CONFIG, applied)
        raise RuntimeError("config overlay did not apply both fragments")
    return {"module": config_overlay, "applied": applied, "before": before}


def revert_config_overlay(state: dict[str, Any]) -> dict[str, Any]:
    state["module"].revert(PROJECT_CONFIG, state["applied"])
    mismatches: list[str] = []
    for name, original in state["before"].items():
        if (PROJECT_CONFIG / name).read_bytes() != original:
            mismatches.append(name)
    if mismatches:
        raise RuntimeError(
            "config did not restore byte-identically: %s" % mismatches)
    return {"restored_byte_identically": True,
            "files": sorted(state["before"])}


def child_main(output: Path) -> int:
    sys.path.insert(0, str(VERIFY))
    sys.path.insert(0, str(VERIFY / "layers"))
    from l2_pie import run_l2  # noqa: PLC0415

    result = run_l2(
        ue_root=_UE_ROOT,
        project_path=PROJECT,
        test_filter=EXACT_FILTER,
        log_path=output / "l2.log",
        report_dir=output / "report",
        map_name=MAP_NAME,
        map_package_path=MAP_PACKAGE,
        use_nullrhi=False,
        render_offscreen=True,
        fps=60,
        timeout_seconds=3600.0,
        expected_test_count=1,
    )
    payload = dataclasses.asdict(result)
    write_json(output / "l2_result.json", payload)
    print("LOCAL-PLAYER-MODAL-ADMISSION-CHILD " +
          json.dumps(payload, sort_keys=True, default=str), flush=True)
    return 0 if result.status == "pass" else 1


def read_json(path: Path, problems: list[str]) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(value, dict):
            raise ValueError("root is not an object")
        return value
    except Exception as exc:  # noqa: BLE001 - preserve all audit failures
        problems.append("unreadable JSON %s: %r" % (path, exc))
        return {}


def audit(output: Path) -> tuple[bool, dict[str, Any]]:
    problems: list[str] = []
    result = read_json(output / "l2_result.json", problems)
    index = read_json(output / "report" / "index.json", problems)
    tests = index.get("tests", [])
    if not isinstance(tests, list):
        tests = []
    if len(tests) != 1:
        problems.append("JSON test count=%d expected=1" % len(tests))
    else:
        test = tests[0] if isinstance(tests[0], dict) else {}
        if test.get("fullTestPath") != EXACT_FILTER:
            problems.append("wrong fullTestPath: %r" % test.get("fullTestPath"))
        if test.get("testDisplayName") != EXPECTED_DISPLAY:
            problems.append(
                "wrong testDisplayName: %r" % test.get("testDisplayName"))
        if test.get("state") != "Success":
            problems.append("wrong test state: %r" % test.get("state"))
    if (index.get("succeeded") != 1 or index.get("failed") != 0 or
            int(index.get("succeededWithWarnings", 0) or 0) != 0 or
            int(index.get("notRun", 0) or 0) != 0):
        problems.append("wrong automation aggregate: %r" % index)
    if (result.get("status") != "pass" or result.get("tests_run") != 1 or
            result.get("tests_passed") != 1 or result.get("tests_failed") != 0 or
            result.get("result_source") != "json"):
        problems.append("wrong L2 result/count/source: %r" % result)

    log_path = output / "l2.log"
    log_text = log_path.read_text(encoding="utf-8", errors="replace") \
        if log_path.is_file() else ""
    if log_text.count(EXPECTED_SUCCESS) != 1:
        problems.append(
            "terminal marker count=%d expected=1" %
            log_text.count(EXPECTED_SUCCESS))
    for token in ("GATE[", "HARNESS-PRECONDITION", "Ensure condition failed",
                  "Assertion failed", "Fatal error", "LowLevelFatalError",
                  "L2 TIMEOUT"):
        if token in log_text:
            problems.append("forbidden failure marker: " + token)
    telemetry = [
        line for line in log_text.splitlines()
        if "LOCAL-PLAYER-MODAL-" in line or "GATE[" in line or
        "HARNESS-PRECONDITION" in line
    ]
    summary = {
        "filter": EXACT_FILTER,
        "display": EXPECTED_DISPLAY,
        "expected_test_count": 1,
        "rhi": "real-offscreen",
        "fps": 60,
        "result": result,
        "automation": index,
        "telemetry": telemetry,
        "problems": problems,
    }
    write_json(output / "audit.json", summary)
    return not problems, summary


def kill_exact_tree(process: subprocess.Popen[Any]) -> dict[str, Any]:
    if process.poll() is not None:
        return {"pid": process.pid, "method": "already-exited",
                "exit_code": process.returncode}
    completed = subprocess.run(
        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
        capture_output=True, text=True, check=False, timeout=30)
    process.wait(timeout=30)
    return {"pid": process.pid, "method": "taskkill-exact-tree",
            "taskkill_exit": completed.returncode,
            "exit_code": process.returncode,
            "output": (completed.stdout + completed.stderr).strip()}


def parent_main(args: argparse.Namespace) -> int:
    if args.watchdog_seconds < 60:
        raise RuntimeError("watchdog must be at least 60 seconds")
    output = args.output.resolve()
    if os.path.lexists(output):
        raise RuntimeError("fresh output already exists: %s" % output)
    facts = preflight()
    output.mkdir(parents=True)
    facts["watchdog_seconds"] = args.watchdog_seconds
    write_json(output / "preflight.json", facts)

    overlay = apply_config_overlay()
    child_exit = -1
    timeout_evidence: dict[str, Any] | None = None
    started = time.monotonic()
    command = [sys.executable, str(Path(__file__).resolve()), "--child",
               "--output", str(output)]
    try:
        with (output / "runner.stdout.log").open(
                "w", encoding="utf-8", errors="replace") as stream:
            process = subprocess.Popen(
                command, cwd=REPO, stdout=stream,
                stderr=subprocess.STDOUT, text=True)
            try:
                child_exit = process.wait(timeout=args.watchdog_seconds)
            except subprocess.TimeoutExpired:
                timeout_evidence = {
                    "verdict": "INFRA_FREEZE",
                    "elapsed_seconds": time.monotonic() - started,
                    "kill": kill_exact_tree(process),
                }
    finally:
        restored = revert_config_overlay(overlay)
        write_json(output / "config_restore.json", restored)

    post_snapshot = protected_snapshot()
    post_absent = {
        "production_map_absent": not os.path.lexists(PRODUCTION_MAP),
        "task_assets_absent": not os.path.lexists(TASK_ASSETS),
        "reference_absent": not os.path.lexists(REFERENCE),
    }
    write_json(output / "postflight.json", {
        "protected_snapshot": post_snapshot,
        **post_absent,
    })

    if timeout_evidence is not None:
        timeout_evidence["config_restore"] = restored
        timeout_evidence["protected_snapshot_unchanged"] = (
            post_snapshot == facts["protected_snapshot"])
        timeout_evidence.update(post_absent)
        write_json(output / "watchdog.json", timeout_evidence)
        print("LOCAL-PLAYER-MODAL-ADMISSION-INFRA-FREEZE " +
              json.dumps(timeout_evidence, sort_keys=True), flush=True)
        return 4

    passed, summary = audit(output)
    if post_snapshot != facts["protected_snapshot"]:
        summary["problems"].append("protected snapshot changed during admission")
        passed = False
    changed_absence = [name for name, absent in post_absent.items() if not absent]
    if changed_absence:
        summary["problems"].append(
            "protected absent surface changed: %s" % changed_absence)
        passed = False
    if child_exit != 0:
        summary["problems"].append("child exit=%d expected=0" % child_exit)
        passed = False
    write_json(output / "audit.json", summary)
    if passed:
        print("LOCAL-PLAYER-MODAL-ADMISSION-RUNNER-PASS "
              "exact_count=1 players=2 epochs=2 rhi=real-offscreen output=%s" %
              output, flush=True)
        return 0
    for problem in summary["problems"]:
        print("LOCAL-PLAYER-MODAL-ADMISSION-RUNNER-ERROR " + problem,
              flush=True)
    return 1


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--watchdog-seconds", type=int, default=720)
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    if args.child:
        return child_main(args.output.resolve())
    try:
        return parent_main(args)
    except Exception as exc:  # noqa: BLE001 - stable operator marker
        print("LOCAL-PLAYER-MODAL-ADMISSION-RUNNER-ERROR %r" % (exc,),
              flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

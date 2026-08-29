"""Run exactly one isolated bundle-lease admission with an outer watchdog."""

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


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
VERIFY = REPO / "tools" / "verify-single"
TASK_ID = "t2-one-bundle-loads-without-pulling-in-the-rest"
UE_ROOT = Path(os.environ.get("CB_UE_ROOT", r"C:\Program Files\Epic Games\UE_5.8"))
PROJECT = REPO / "UE-projects" / "ThirdPerson" / "ThirdPerson.uproject"
CONTENT = PROJECT.parent / "Content"
TASK_SPEC = HERE.parent / "task.md"
MAP_NAME = "L_BundleLeaseAdmission"
MAP_PACKAGE = f"/Game/Maps/{TASK_ID}/{MAP_NAME}"
MAP_FILE = CONTENT / "Maps" / TASK_ID / (MAP_NAME + ".umap")
FINAL_MAP = CONTENT / "Maps" / TASK_ID / "L_BundleLeases.umap"
RECORD_DIR = CONTENT / "Maps" / TASK_ID / "Records"
EXACT_FILTER = (
    f"Project.Functional Tests.Maps.{TASK_ID}.{MAP_NAME}."
    "BundleLeaseAdmissionFunctionalTest")
EXPECTED_DISPLAY = "BundleLeaseAdmissionFunctionalTest"
SUCCESS = ("BUNDLE-LEASE-ADMISSION-PASS exact_bundle=1 hidden_dependency=1 "
           "unselected_nonresident=1 remove_bundle=1")


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, default=str) + "\n",
                    encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def is_reparse(path: Path) -> bool:
    attrs = getattr(path.lstat(), "st_file_attributes", 0)
    return path.is_symlink() or bool(
        attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def require_plain(path: Path) -> None:
    current = Path(os.path.abspath(os.fspath(path)))
    stop = Path(os.path.abspath(os.fspath(REPO)))
    while True:
        if not current.exists() or is_reparse(current):
            raise RuntimeError("missing/reparse protected path: %s" % current)
        if current == stop:
            return
        if stop not in current.parents:
            raise RuntimeError("protected path escaped repository: %s" % path)
        current = current.parent


def snapshot() -> dict[str, object]:
    require_plain(RECORD_DIR)
    require_plain(MAP_FILE)
    if FINAL_MAP.exists() or os.path.lexists(FINAL_MAP):
        raise RuntimeError("final map must remain absent during admission")
    assets = sorted(RECORD_DIR.glob("*.uasset"), key=lambda p: p.name.lower())
    if len(assets) != 15 or any(is_reparse(path) for path in assets):
        raise RuntimeError("protected asset inventory/reparse mismatch: %d" % len(assets))
    files = assets + [MAP_FILE]
    return {str(path.relative_to(PROJECT.parent)): {
        "size": path.stat().st_size, "sha256": sha(path)} for path in files}


def apply_overlay() -> dict[str, object]:
    sys.path.insert(0, str(VERIFY))
    import config_overlay  # noqa: PLC0415

    fragments = config_overlay.discover(TASK_SPEC)
    if set(fragments) != {"DefaultGame.ini"}:
        raise RuntimeError("task overlay inventory mismatch: %s" % sorted(fragments))
    config_dir = PROJECT.parent / "Config"
    target = config_dir / "DefaultGame.ini"
    original = target.read_bytes() if target.exists() else None
    applied = config_overlay.apply(config_dir, fragments, TASK_ID)
    return {"module": config_overlay, "applied": applied, "target": target,
            "original": original, "applied_hash": sha(target)}


def revert_overlay(state: dict[str, object]) -> dict[str, object]:
    state["module"].revert(PROJECT.parent / "Config", state["applied"])
    target = state["target"]
    actual = target.read_bytes() if target.exists() else None
    if actual != state["original"]:
        raise RuntimeError("DefaultGame.ini did not restore byte-identically")
    return {"restored_byte_identically": True}


def child_main(output: Path) -> int:
    sys.path.insert(0, str(VERIFY))
    sys.path.insert(0, str(VERIFY / "layers"))
    from l2_pie import run_l2  # noqa: PLC0415

    result = run_l2(
        ue_root=UE_ROOT,
        project_path=PROJECT,
        test_filter=EXACT_FILTER,
        log_path=output / "l2.log",
        report_dir=output / "report",
        map_name=MAP_NAME,
        map_package_path=MAP_PACKAGE,
        use_nullrhi=False,
        fps=60,
        timeout_seconds=3600.0,
        expected_test_count=1,
    )
    payload = dataclasses.asdict(result)
    write_json(output / "l2_result.json", payload)
    print("BUNDLE-LEASE-ADMISSION-CHILD " + json.dumps(payload, default=str), flush=True)
    return 0 if result.status == "pass" else 1


def kill_exact_tree(process: subprocess.Popen) -> dict[str, object]:
    if process.poll() is not None:
        return {"pid": process.pid, "method": "already-exited",
                "exit_code": process.returncode}
    if os.name == "nt":
        result = subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                capture_output=True, text=True, check=False, timeout=30)
        evidence = {"pid": process.pid, "method": "taskkill-exact-tree",
                    "taskkill_exit": result.returncode,
                    "output": (result.stdout + result.stderr).strip()}
    else:
        process.kill()
        evidence = {"pid": process.pid, "method": "process-kill"}
    process.wait(timeout=30)
    evidence["exit_code"] = process.returncode
    return evidence


def read_json(path: Path, problems: list[str]) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        return value if isinstance(value, dict) else {}
    except Exception as exc:  # noqa: BLE001
        problems.append("unreadable JSON %s: %r" % (path, exc))
        return {}


def audit(output: Path, before: dict[str, object]) -> tuple[bool, dict[str, object]]:
    problems: list[str] = []
    result = read_json(output / "l2_result.json", problems)
    index_path = output / "report" / "index.json"
    index = read_json(index_path, problems)
    tests = index.get("tests", []) if isinstance(index.get("tests", []), list) else []
    if len(tests) != 1:
        problems.append("exact JSON count=%d expected=1" % len(tests))
    else:
        test = tests[0]
        if test.get("fullTestPath") != EXACT_FILTER:
            problems.append("wrong fullTestPath: %r" % test.get("fullTestPath"))
        if test.get("testDisplayName") != EXPECTED_DISPLAY:
            problems.append("wrong display: %r" % test.get("testDisplayName"))
        if test.get("state") != "Success":
            problems.append("wrong state: %r" % test.get("state"))
    if (index.get("succeeded") != 1 or index.get("failed") != 0
            or int(index.get("succeededWithWarnings", 0) or 0) != 0
            or int(index.get("notRun", 0) or 0) != 0):
        problems.append("automation aggregate mismatch")
    if (result.get("status") != "pass" or result.get("tests_run") != 1
            or result.get("tests_passed") != 1 or result.get("result_source") != "json"):
        problems.append("L2 result/count/source mismatch: %r" % result)
    log = (output / "l2.log").read_text(encoding="utf-8", errors="replace") \
        if (output / "l2.log").is_file() else ""
    if log.count(SUCCESS) != 1:
        problems.append("success marker count=%d expected=1" % log.count(SUCCESS))
    for token in ("BUNDLE-LEASE-ADMISSION-FAIL", "HARNESS-PRECONDITION",
                  "Ensure condition failed", "Assertion failed", "Fatal error",
                  "LowLevelFatalError", "L2 TIMEOUT"):
        if token in log:
            problems.append("forbidden log token: " + token)
    try:
        after = snapshot()
    except Exception as exc:  # noqa: BLE001
        after = {"snapshot_error": repr(exc)}
        problems.append("protected postflight failed: %r" % (exc,))
    if after != before:
        problems.append("protected 15 assets/admission map changed")
    summary = {"filter": EXACT_FILTER, "expected_count": 1, "rhi": "real",
               "fps": 60, "result": result, "tests": tests,
               "protected_before": before, "protected_after": after,
               "problems": problems}
    write_json(output / "audit.json", summary)
    return not problems, summary


def parent_main(args: argparse.Namespace) -> int:
    output = args.output.resolve()
    if output.exists() or os.path.lexists(output):
        raise RuntimeError("fresh output already exists: %s" % output)
    if args.watchdog_seconds < 60:
        raise RuntimeError("watchdog must be at least 60 seconds")
    before = snapshot()
    output.mkdir(parents=True)
    overlay = apply_overlay()
    child_exit = -1
    timeout = None
    try:
        write_json(output / "preflight.json", {
            "filter": EXACT_FILTER, "expected_count": 1, "map": MAP_PACKAGE,
            "rhi": "real", "fps": 60, "watchdog": args.watchdog_seconds,
            "protected": before, "overlay_applied_before_boot": True,
            "overlay_hash": overlay["applied_hash"]})
        command = [sys.executable, str(Path(__file__).resolve()), "--child",
                   "--output", str(output)]
        with (output / "runner.stdout.log").open("w", encoding="utf-8") as stream:
            process = subprocess.Popen(command, cwd=REPO, stdout=stream,
                                       stderr=subprocess.STDOUT, text=True)
            try:
                child_exit = process.wait(timeout=args.watchdog_seconds)
            except subprocess.TimeoutExpired:
                timeout = {"verdict": "INFRA_FREEZE", "filter": EXACT_FILTER,
                           "kill": kill_exact_tree(process)}
    finally:
        restore = revert_overlay(overlay)
        write_json(output / "config_restore.json", restore)
    if timeout:
        timeout["protected_after"] = snapshot()
        write_json(output / "watchdog.json", timeout)
        print("BUNDLE-LEASE-ADMISSION-INFRA-FREEZE " + json.dumps(timeout), flush=True)
        return 4
    ok, summary = audit(output, before)
    if child_exit != 0:
        summary["problems"].append("child exit=%d expected=0" % child_exit)
        write_json(output / "audit.json", summary)
        ok = False
    if ok:
        print("BUNDLE-LEASE-ADMISSION-RUNNER-PASS exact_count=1 state=Success "
              "assets=15 map=1 hashes_unchanged=1 output=%s" % output, flush=True)
        return 0
    for problem in summary["problems"]:
        print("BUNDLE-LEASE-ADMISSION-RUNNER-ERROR " + problem, flush=True)
    return 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--watchdog-seconds", type=int, default=720)
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        return child_main(args.output.resolve()) if args.child else parent_main(args)
    except Exception as exc:  # noqa: BLE001
        print("BUNDLE-LEASE-ADMISSION-RUNNER-ERROR %r" % (exc,), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

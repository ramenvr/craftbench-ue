"""Run one fail-closed, real-RHI menu-input admission test.

The production L2 runner can block while consuming a silent editor stdout
stream.  This wrapper therefore runs it in a child process and owns an
independent wall-clock watchdog for that exact child tree.  Every run also
locks the admission map and its OFPA side packages, all authored input assets,
the four stock Third Person packages, and the still-absent reference.

One successful run establishes the exact Automation path/display-name evidence
for that run only.  It does not author the final Blueprint or start another
round automatically.
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


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
VERIFY = REPO / "tools" / "verify-single"
TASK_ID = "t2-menu-blocks-gameplay-and-restores-it-exactly"
UE_ROOT = Path(os.environ.get("CB_UE_ROOT", r"C:\Program Files\Epic Games\UE_5.8"))
PROJECT = REPO / "UE-projects" / "ThirdPerson" / "ThirdPerson.uproject"
PROJECT_CONFIG = PROJECT.parent / "Config"
CONTENT = REPO / "UE-projects" / "ThirdPerson" / "Content"
TASK_SPEC = HERE.parent / "task.md"

MAP_NAME = "L_MenuInputRouting"
MAP_PACKAGE = "/Game/Maps/%s/%s" % (TASK_ID, MAP_NAME)
EXACT_FILTER = (
    "Project.Functional Tests.Maps.%s.%s."
    "MenuInputAdmissionFunctionalTest" % (TASK_ID, MAP_NAME))
EXPECTED_DISPLAY = "MenuInputAdmissionFunctionalTest"
EXPECTED_SUCCESS = (
    "MENU-INPUT-admission-PASS GameplayActionBlockedWhileMenuActive "
    "TopMenuConsumesItsOwnAction PopRestoresExactPriorContexts "
    "UnrelatedContextRemainsUntouched gameplay=3 unrelated=3")

MAP_DIR = CONTENT / "Maps" / TASK_ID
MAIN_MAP = MAP_DIR / (MAP_NAME + ".umap")
TASK_ASSET_DIR = CONTENT / "Tasks" / TASK_ID
SUPPORT_DIR = MAP_DIR / "Support"
EXTERNAL_ACTORS_DIR = (
    CONTENT / "__ExternalActors__" / "Maps" / TASK_ID / MAP_NAME)
EXTERNAL_OBJECTS_DIR = (
    CONTENT / "__ExternalObjects__" / "Maps" / TASK_ID / MAP_NAME)
REFERENCE_DIR = HERE.parent / "reference"

EXPECTED_MAIN_HASH = (
    "c48ddd5b6cf00b32478d07dd9b2d7ce74dba6bf12ac86399f419c98392a37525")
EXPECTED_MAP_MANIFEST = (
    "c494ff1355142fc460c05e947b4f21e626a60f57d3b306456bcdc3e3576df7ed")
EXPECTED_AUTHORED_MANIFEST = (
    "9a127d44ebe027b27ec0470f74e3d0db49492f99cee06210f9c20c8bb4a0984b")
EXPECTED_STOCK_MANIFEST = (
    "b197fab3f5d75c48b4e33ae072e3bf10fdfe0b6d4af6cbcb51810e13797f9b81")

EXPECTED_TASK_FILES = frozenset({"WBP_InputBlockingMenu.uasset"})
EXPECTED_SUPPORT_FILES = frozenset({
    "IA_GameplayProbe.uasset",
    "IA_MenuProbe.uasset",
    "IA_UnrelatedProbe.uasset",
    "IMC_GameplayQuartz.uasset",
    "IMC_GameplayViolet.uasset",
    "IMC_MenuQuartz.uasset",
    "IMC_MenuViolet.uasset",
    "IMC_UnrelatedQuartz.uasset",
    "IMC_UnrelatedViolet.uasset",
})
STOCK_FILES = (
    CONTENT / "ThirdPerson" / "Lvl_ThirdPerson.umap",
    CONTENT / "ThirdPerson" / "Blueprints" / "BP_ThirdPersonCharacter.uasset",
    CONTENT / "ThirdPerson" / "Blueprints" / "BP_ThirdPersonGameMode.uasset",
    CONTENT / "ThirdPerson" / "Blueprints"
    / "BP_ThirdPersonPlayerController.uasset",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def is_reparse(path: Path) -> bool:
    info = path.lstat()
    attributes = getattr(info, "st_file_attributes", 0)
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def require_plain_path(path: Path) -> None:
    # ``resolve`` would follow the very junction/symlink that this walk is
    # meant to reject.  ``abspath`` normalizes spelling without dereferencing.
    current = Path(os.path.abspath(os.fspath(path)))
    stop = Path(os.path.abspath(os.fspath(CONTENT)))
    while True:
        if not current.exists():
            raise RuntimeError("required protected path missing: %s" % current)
        if current.is_symlink() or is_reparse(current):
            raise RuntimeError("protected reparse path rejected: %s" % current)
        if current == stop:
            return
        if stop not in current.parents:
            raise RuntimeError("protected path escaped Content root: %s" % path)
        current = current.parent


def require_plain_repo_path(path: Path) -> None:
    """Reject a junction/symlink anywhere from ``path`` back to the repo."""
    current = Path(os.path.abspath(os.fspath(path)))
    stop = Path(os.path.abspath(os.fspath(REPO)))
    while True:
        if not current.exists():
            raise RuntimeError("required repository path missing: %s" % current)
        if current.is_symlink() or is_reparse(current):
            raise RuntimeError("repository reparse path rejected: %s" % current)
        if current == stop:
            return
        if stop not in current.parents:
            raise RuntimeError("path escaped repository: %s" % path)
        current = current.parent


def apply_task_config_overlay() -> dict[str, Any]:
    """Apply both task fragments before the child boots.

    ``run_task.py`` normally performs this step on its composed workdir.  This
    author-only runner invokes ``l2_pie`` directly on the live substrate, so it
    must use the same shared overlay primitive and byte-identically revert it.
    """
    sys.path.insert(0, str(VERIFY))
    import config_overlay  # noqa: PLC0415

    require_plain_repo_path(PROJECT_CONFIG)
    fragments = config_overlay.discover(TASK_SPEC)
    expected = {"DefaultEngine.ini", "DefaultGame.ini"}
    if set(fragments) != expected:
        raise RuntimeError(
            "task config fragment inventory mismatch: %s" % sorted(fragments))
    before: dict[str, bytes | None] = {}
    for name in sorted(expected):
        target = PROJECT_CONFIG / name
        require_plain_repo_path(target)
        before[name] = target.read_bytes() if target.exists() else None
    try:
        applied = config_overlay.apply(PROJECT_CONFIG, fragments, TASK_ID)
    except Exception:
        for name, original in before.items():
            target = PROJECT_CONFIG / name
            if original is None:
                if target.exists():
                    target.unlink()
            else:
                target.write_bytes(original)
        raise
    if {item.ini_name for item in applied} != expected:
        config_overlay.revert(PROJECT_CONFIG, applied)
        raise RuntimeError("shared config overlay did not apply both fragments")
    applied_hashes = {
        name: sha256(PROJECT_CONFIG / name) for name in sorted(expected)}
    return {
        "module": config_overlay,
        "applied": applied,
        "before": before,
        "facts": {
            "fragments": sorted(expected),
            "targets": [str(PROJECT_CONFIG / name) for name in sorted(expected)],
            "applied_hashes": applied_hashes,
            "applied_before_child_boot": True,
        },
    }


def revert_task_config_overlay(state: dict[str, Any]) -> dict[str, Any]:
    state["module"].revert(PROJECT_CONFIG, state["applied"])
    problems: list[str] = []
    restored_hashes: dict[str, str | None] = {}
    for name, original in state["before"].items():
        target = PROJECT_CONFIG / name
        actual = target.read_bytes() if target.exists() else None
        if actual != original:
            problems.append("config target did not restore byte-identically: " + name)
        restored_hashes[name] = sha256(target) if target.exists() else None
    if problems:
        raise RuntimeError("; ".join(problems))
    return {
        "restored_byte_identically": True,
        "restored_hashes": restored_hashes,
    }


def require_reference_absent() -> None:
    if os.path.lexists(REFERENCE_DIR):
        raise RuntimeError("reference must remain absent: %s" % REFERENCE_DIR)
    current = REFERENCE_DIR.parent
    stop = REPO.resolve(strict=True)
    while True:
        if current.is_symlink() or is_reparse(current):
            raise RuntimeError("reference ancestor is a reparse path: %s" % current)
        if current.resolve(strict=True) == stop:
            return
        if stop not in current.resolve(strict=True).parents:
            raise RuntimeError("reference path escaped repository: %s" % REFERENCE_DIR)
        current = current.parent


def files_under(root: Path) -> list[Path]:
    require_plain_path(root)
    result: list[Path] = []
    for current_text, directories, filenames in os.walk(root):
        current = Path(current_text)
        for directory in directories:
            require_plain_path(current / directory)
        for filename in filenames:
            path = current / filename
            require_plain_path(path)
            result.append(path)
    return sorted(result, key=lambda item: item.as_posix().lower())


def manifest(paths: list[Path]) -> tuple[str, dict[str, dict[str, Any]]]:
    digest = hashlib.sha256()
    vector: dict[str, dict[str, Any]] = {}
    for path in sorted(paths, key=lambda item: item.as_posix().lower()):
        require_plain_path(path)
        relative = path.relative_to(PROJECT.parent).as_posix()
        size = path.stat().st_size
        file_hash = sha256(path)
        vector[relative] = {"size": size, "sha256": file_hash}
        digest.update(("%s\0%d\0%s\n" %
                       (relative, size, file_hash)).encode("utf-8"))
    return digest.hexdigest(), vector


def protected_snapshot() -> dict[str, Any]:
    require_reference_absent()
    task_files = files_under(TASK_ASSET_DIR)
    support_files = files_under(SUPPORT_DIR)
    task_inventory = {path.relative_to(TASK_ASSET_DIR).as_posix()
                      for path in task_files}
    support_inventory = {path.relative_to(SUPPORT_DIR).as_posix()
                         for path in support_files}
    if task_inventory != EXPECTED_TASK_FILES:
        raise RuntimeError("task asset inventory mismatch: %s" %
                           sorted(task_inventory))
    if support_inventory != EXPECTED_SUPPORT_FILES:
        raise RuntimeError("support asset inventory mismatch: %s" %
                           sorted(support_inventory))

    require_plain_path(MAP_DIR)
    direct_files = {path.name for path in MAP_DIR.iterdir() if path.is_file()}
    direct_dirs = {path.name for path in MAP_DIR.iterdir() if path.is_dir()}
    if direct_files != {MAIN_MAP.name} or direct_dirs != {"Support"}:
        raise RuntimeError(
            "map root inventory mismatch files=%s dirs=%s" %
            (sorted(direct_files), sorted(direct_dirs)))

    external_actors = files_under(EXTERNAL_ACTORS_DIR)
    external_objects = files_under(EXTERNAL_OBJECTS_DIR)
    if len(external_actors) != 69 or len(external_objects) != 2:
        raise RuntimeError(
            "OFPA cardinality mismatch actors=%d objects=%d" %
            (len(external_actors), len(external_objects)))

    map_digest, map_vector = manifest(
        [MAIN_MAP] + external_actors + external_objects)
    authored_digest, authored_vector = manifest(task_files + support_files)
    stock_digest, stock_vector = manifest(list(STOCK_FILES))
    if sha256(MAIN_MAP) != EXPECTED_MAIN_HASH:
        raise RuntimeError("main map hash differs from frozen authoring")
    if map_digest != EXPECTED_MAP_MANIFEST:
        raise RuntimeError("map72 manifest differs from frozen authoring")
    if authored_digest != EXPECTED_AUTHORED_MANIFEST:
        raise RuntimeError("authored10 manifest differs from frozen readback")
    if stock_digest != EXPECTED_STOCK_MANIFEST:
        raise RuntimeError("stock4 manifest differs from frozen preflight")
    return {
        "reference_absent": True,
        "no_reparse": True,
        "map": map_vector,
        "authored": authored_vector,
        "stock": stock_vector,
        "manifests": {
            "map72": map_digest,
            "authored10": authored_digest,
            "stock4": stock_digest,
        },
    }


def write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8")


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
    print("MENU-INPUT-ADMISSION-CHILD " +
          json.dumps(payload, sort_keys=True, default=str), flush=True)
    return 0 if result.status == "pass" else 1


def kill_exact_tree(process: subprocess.Popen[Any]) -> dict[str, Any]:
    evidence: dict[str, Any] = {"pid": process.pid}
    if process.poll() is not None:
        evidence.update(method="already-exited", exit_code=process.returncode)
        return evidence
    if os.name == "nt":
        completed = subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True, text=True, check=False, timeout=30)
        evidence.update(
            method="taskkill-exact-tree",
            taskkill_exit=completed.returncode,
            output=(completed.stdout + completed.stderr).strip())
    else:
        process.kill()
        evidence["method"] = "process-kill"
    try:
        process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=30)
        evidence["fallback"] = "process-kill"
    evidence["exit_code"] = process.returncode
    return evidence


def read_json(path: Path, problems: list[str]) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(value, dict):
            raise ValueError("root is not an object")
        return value
    except Exception as exc:  # noqa: BLE001 - audit must preserve all evidence
        problems.append("unreadable JSON %s: %r" % (path, exc))
        return {}


def audit(output: Path, before: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    problems: list[str] = []
    result = read_json(output / "l2_result.json", problems)
    index_path = output / "report" / "index.json"
    index = read_json(index_path, problems)
    tests = index.get("tests", []) if isinstance(index.get("tests", []), list) else []

    if len(tests) != 1:
        problems.append("JSON test count=%d expected=1" % len(tests))
    else:
        test = tests[0] if isinstance(tests[0], dict) else {}
        if test.get("fullTestPath") != EXACT_FILTER:
            problems.append("wrong fullTestPath: %r" % test.get("fullTestPath"))
        if test.get("testDisplayName") != EXPECTED_DISPLAY:
            problems.append("wrong testDisplayName: %r" %
                            test.get("testDisplayName"))
        if test.get("state") != "Success":
            problems.append("wrong exact test state: %r" % test.get("state"))
    if (index.get("succeeded") != 1 or index.get("failed") != 0
            or int(index.get("succeededWithWarnings", 0) or 0) != 0
            or int(index.get("notRun", 0) or 0) != 0):
        problems.append(
            "wrong JSON aggregate succeeded=%r warnings=%r failed=%r notRun=%r" %
            (index.get("succeeded"), index.get("succeededWithWarnings"),
             index.get("failed"), index.get("notRun")))
    if (result.get("status") != "pass" or result.get("tests_run") != 1
            or result.get("tests_passed") != 1
            or result.get("tests_failed") != 0
            or result.get("result_source") != "json"):
        problems.append("L2 result/count/source mismatch: %r" % result)

    log_path = output / "l2.log"
    text = log_path.read_text(encoding="utf-8", errors="replace") \
        if log_path.is_file() else ""
    if text.count(EXPECTED_SUCCESS) != 1:
        problems.append(
            "exact admission success marker count=%d expected=1" %
            text.count(EXPECTED_SUCCESS))
    for token in (
            "GATE[", "HARNESS-PRECONDITION", "FinishTest TestResult=Error.",
            "Ensure condition failed", "Assertion failed", "Fatal error",
            "LowLevelFatalError", "L2 TIMEOUT"):
        if token in text:
            problems.append("forbidden admission/error marker: " + token)

    try:
        after = protected_snapshot()
    except Exception as exc:  # noqa: BLE001 - turn mutation into a hard failure
        after = {"snapshot_error": repr(exc)}
        problems.append("protected postflight failed: %r" % (exc,))
    if after != before:
        problems.append("protected map72/authored10/stock4 snapshot changed")

    telemetry = [
        line for line in text.splitlines()
        if "MENU-INPUT-" in line or "GATE[" in line
        or "HARNESS-PRECONDITION" in line
    ]
    summary = {
        "filter": EXACT_FILTER,
        "expected_display": EXPECTED_DISPLAY,
        "expected_test_count": 1,
        "map_package": MAP_PACKAGE,
        "rhi": "real",
        "fps": 60,
        "result": result,
        "automation_report": {
            "path": str(index_path),
            "succeeded": index.get("succeeded"),
            "succeededWithWarnings": index.get("succeededWithWarnings"),
            "failed": index.get("failed"),
            "notRun": index.get("notRun"),
            "tests": tests,
        },
        "protected_before": before,
        "protected_after": after,
        "telemetry": telemetry,
        "problems": problems,
    }
    write_json(output / "audit.json", summary)
    return not problems, summary


def safe_postflight() -> dict[str, Any]:
    try:
        return {"snapshot": protected_snapshot()}
    except Exception as exc:  # noqa: BLE001 - watchdog evidence must be durable
        return {"snapshot_error": repr(exc)}


def parent_main(args: argparse.Namespace) -> int:
    if args.watchdog_seconds < 60:
        raise RuntimeError("watchdog must be at least 60 seconds")
    output = args.output.resolve()
    if output.exists() or os.path.lexists(output):
        raise RuntimeError("fresh output already exists: %s" % output)
    if not PROJECT.is_file():
        raise RuntimeError("project missing: %s" % PROJECT)

    before = protected_snapshot()
    output.mkdir(parents=True)
    child_command = [
        sys.executable, str(Path(__file__).resolve()), "--child",
        "--output", str(output),
    ]
    started = time.monotonic()
    overlay_state = apply_task_config_overlay()
    child_exit = -1
    timeout_evidence: dict[str, Any] | None = None
    try:
        write_json(output / "preflight.json", {
            "filter": EXACT_FILTER,
            "expected_display": EXPECTED_DISPLAY,
            "expected_test_count": 1,
            "map_package": MAP_PACKAGE,
            "rhi": "real",
            "fps": 60,
            "watchdog_seconds": args.watchdog_seconds,
            "protected_before": before,
            "config_overlay": overlay_state["facts"],
        })
        with (output / "runner.stdout.log").open(
                "w", encoding="utf-8", errors="replace") as stream:
            process = subprocess.Popen(
                child_command, cwd=REPO, stdout=stream,
                stderr=subprocess.STDOUT, text=True)
            try:
                child_exit = process.wait(timeout=args.watchdog_seconds)
            except subprocess.TimeoutExpired:
                timeout_evidence = {
                    "verdict": "INFRA_FREEZE",
                    "filter": EXACT_FILTER,
                    "elapsed_seconds": time.monotonic() - started,
                    "deadline_seconds": args.watchdog_seconds,
                    "kill": kill_exact_tree(process),
                    "protected_before": before,
                }
    finally:
        config_restore = revert_task_config_overlay(overlay_state)
        write_json(output / "config_restore.json", config_restore)

    if timeout_evidence is not None:
        timeout_evidence["config_restore"] = config_restore
        timeout_evidence["protected_after"] = safe_postflight()
        write_json(output / "watchdog.json", timeout_evidence)
        print("MENU-INPUT-ADMISSION-INFRA-FREEZE " +
              json.dumps(timeout_evidence, sort_keys=True, default=str),
              flush=True)
        return 4

    ok, summary = audit(output, before)
    summary["config_overlay"] = overlay_state["facts"]
    summary["config_restore"] = config_restore
    write_json(output / "audit.json", summary)
    if child_exit != 0:
        summary["problems"].append("child exit=%d expected=0" % child_exit)
        write_json(output / "audit.json", summary)
        ok = False
    if ok:
        print(
            "MENU-INPUT-ADMISSION-RUNNER-PASS exact_count=1 "
            "state=Success display=%s map_files=72 assets=10 stock=4 "
            "hashes_unchanged=1 no_reparse=1 reference_absent=1 output=%s" %
            (EXPECTED_DISPLAY, output), flush=True)
        return 0
    for problem in summary["problems"]:
        print("MENU-INPUT-ADMISSION-RUNNER-ERROR " + problem, flush=True)
    return 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--watchdog-seconds", type=int, default=720)
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.child:
        return child_main(args.output.resolve())
    try:
        return parent_main(args)
    except Exception as exc:  # noqa: BLE001 - emit one stable operator marker
        print("MENU-INPUT-ADMISSION-RUNNER-ERROR %r" % (exc,), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

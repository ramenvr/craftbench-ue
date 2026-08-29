"""Fail-closed scratch-reference admission runner for shared-helper leases.

Phases are deliberately separate. ``prepare`` copies the live substrate and
overlays the exact reference source only in scratch; ``build`` compiles both
scratch targets; ``test`` runs the same verifier fixture with exact-one L2.
The live empty runtime is hash-locked and is never an overlay destination.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Callable, Iterable, Mapping, Sequence

#: Engine root. Override with CB_UE_ROOT; defaults to Epic's standard install.
_UE_ROOT = Path(os.environ.get("CB_UE_ROOT", r"C:\Program Files\Epic Games\UE_5.8"))


TASK_ID = "t2-shared-helper-lives-until-the-last-lease-ends"
MAP_NAME = "L_SharedHelperLeaseAdmission"
MAP_PACKAGE = "/Game/__CraftBenchAdmission/%s/%s" % (TASK_ID, MAP_NAME)
TEST_FILTER = (
    "Project.Functional Tests.__CraftBenchAdmission.%s.%s."
    "SharedHelperLeaseAdmissionFunctionalTest" % (TASK_ID, MAP_NAME))
OUTER_WATCHDOG_SECONDS = 720
INNER_L2_TIMEOUT_SECONDS = 710
LIVE_SOURCE_NAMES = (
    "SharedHelperLeaseSubsystem.h", "SharedHelperLeaseSubsystem.cpp")
REFERENCE_SOURCE_NAMES = ("SharedHelperLeaseSubsystem.cpp",)

HERE = Path(__file__).resolve().parent
TASK_ROOT = HERE.parent
REPO_ROOT = TASK_ROOT.parents[2]
VERIFY_ROOT = REPO_ROOT / "tools/verify-single"
if str(VERIFY_ROOT) not in sys.path:
    sys.path.insert(0, str(VERIFY_ROOT))

from job_governor import L1_MEM_MB, L2_MEM_MB, assign, resource_job  # noqa: E402
from layers.l2_pie import run_l2  # noqa: E402
from run_task import copy_substrate_from_live  # noqa: E402


PROJECT_REL = Path("UE-projects/ThirdPerson")
RUNTIME_REL = Path("Source/ThirdPerson/Tasks") / TASK_ID
ADMISSION_MAP_REL = (Path("Content/__CraftBenchAdmission") / TASK_ID /
                     (MAP_NAME + ".umap"))
FINAL_MAP_REL = Path("Content/Maps") / TASK_ID / "L_SharedHelperLeases.umap"
REFERENCE_REL = (Path("tasks/craftbench-public") / TASK_ID / "reference/Source" /
                 "ThirdPerson/Tasks" / TASK_ID)


def fail(detail: str) -> None:
    raise RuntimeError("SHARED-HELPER-ADMISSION ERROR " + detail)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _is_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    if is_junction is not None and is_junction():
        return True
    try:
        return bool(getattr(os.lstat(path), "st_reparse_tag", 0)
                    or (getattr(os.lstat(path), "st_file_attributes", 0) & 0x400))
    except OSError:
        return False


def assert_no_reparse_chain(root: Path, path: Path) -> None:
    root = Path(os.path.abspath(root))
    path = Path(os.path.abspath(path))
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        fail("path escapes root root=%s path=%s" % (root, path))
        raise AssertionError from exc
    current = root
    if current.exists() and _is_reparse(current):
        fail("root is link/reparse: " + str(current))
    for part in relative.parts:
        current /= part
        if current.exists() and _is_reparse(current):
            fail("path traverses link/reparse: " + str(current))


def exact_source_snapshot(
    root: Path,
    prefix: str,
    expected_names: Sequence[str],
) -> dict[str, dict[str, object]]:
    if not root.is_dir():
        fail("missing source root: " + str(root))
    assert_no_reparse_chain(root.parent, root)
    found = sorted(item.name for item in root.iterdir() if item.is_file())
    if found != sorted(expected_names):
        fail("exact source inventory %s expected=%r found=%r" %
             (prefix, sorted(expected_names), found))
    facts = {}
    for name in expected_names:
        path = root / name
        assert_no_reparse_chain(root, path)
        facts[prefix + ":" + name] = {
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    return facts


def protected_snapshot(repo: Path = REPO_ROOT) -> dict[str, dict[str, object]]:
    project = repo / PROJECT_REL
    facts = exact_source_snapshot(
        project / RUNTIME_REL, "live", LIVE_SOURCE_NAMES)
    facts.update(exact_source_snapshot(
        repo / REFERENCE_REL, "reference", REFERENCE_SOURCE_NAMES))
    admission = project / ADMISSION_MAP_REL
    assert_no_reparse_chain(project, admission)
    if not admission.is_file():
        fail("admission map missing: " + str(admission))
    facts["admission_map"] = {
        "bytes": admission.stat().st_size,
        "sha256": sha256_file(admission),
    }
    final_map = project / FINAL_MAP_REL
    assert_no_reparse_chain(project, final_map.parent)
    if os.path.lexists(str(final_map)):
        fail("protected final map must remain absent: " + str(final_map))
    if len(facts) != 4:
        fail("internal lock cardinality expected=4 found=%d" % len(facts))
    return facts


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, default=str) + "\n",
                    encoding="utf-8")


def overlay_reference(reference: Path, destination: Path) -> dict[str, str]:
    """Overlay only reference implementation source and return scratch hashes."""
    source_facts = exact_source_snapshot(
        reference, "reference", REFERENCE_SOURCE_NAMES)
    if not destination.is_dir():
        fail("scratch runtime destination missing: " + str(destination))
    assert_no_reparse_chain(destination.parent, destination)
    exact_source_snapshot(destination, "scratch-live", LIVE_SOURCE_NAMES)
    now = time.time() + 2.0
    hashes = {}
    for name in REFERENCE_SOURCE_NAMES:
        src = reference / name
        dst = destination / name
        assert_no_reparse_chain(reference, src)
        assert_no_reparse_chain(destination, dst)
        shutil.copy2(src, dst)
        os.utime(dst, (now, now))
        observed = sha256_file(dst)
        expected = source_facts["reference:" + name]["sha256"]
        if observed != expected:
            fail("scratch overlay hash mismatch file=" + name)
        hashes[name] = observed
    return hashes


def prepare_phase(
    output_root: Path,
    copy_func: Callable[[Path, Path], None] = copy_substrate_from_live,
) -> dict:
    output_root = output_root.resolve()
    if os.path.lexists(str(output_root)):
        fail("fresh output root already exists: " + str(output_root))
    locks = protected_snapshot(REPO_ROOT)
    output_root.mkdir(parents=True)
    scratch_project = output_root / "scratch/ThirdPerson"
    copy_func(REPO_ROOT / PROJECT_REL, scratch_project)

    # Copied UBT makefiles and action histories contain absolute paths to the
    # live project.  Reusing them can compile the live empty implementation
    # while the scratch tree appears to contain the reference.  A port
    # admission is only meaningful with fresh scratch-generated products.
    for generated_name in ("Intermediate", "Binaries"):
        generated = scratch_project / generated_name
        if generated.is_dir():
            shutil.rmtree(generated)
        elif os.path.lexists(str(generated)):
            fail("unexpected non-directory scratch generated path: " +
                 str(generated))

    scratch_uproject = scratch_project / "ThirdPerson.uproject"
    if not scratch_uproject.is_file():
        fail("scratch copy lacks uproject")
    overlay = overlay_reference(
        REPO_ROOT / REFERENCE_REL, scratch_project / RUNTIME_REL)
    state = {
        "task_id": TASK_ID,
        "status": "prepared",
        "output_root": str(output_root),
        "scratch_project": str(scratch_project),
        "scratch_uproject": str(scratch_uproject),
        "protected": locks,
        "scratch_reference_overlay": overlay,
        "overlay_files": list(REFERENCE_SOURCE_NAMES),
    }
    write_json(output_root / "state.json", state)
    write_json(output_root / "prepare/complete.json", state)
    if protected_snapshot(REPO_ROOT) != locks:
        fail("live/reference/map locks changed during prepare")
    print("SHARED-HELPER-ADMISSION PREPARE PASS locks=4 overlay=1")
    return state


def load_state(output_root: Path) -> dict:
    path = output_root.resolve() / "state.json"
    if not path.is_file():
        fail("missing state: " + str(path))
    state = json.loads(path.read_text(encoding="utf-8"))
    if state.get("task_id") != TASK_ID or state.get("status") != "prepared":
        fail("invalid state identity/status")
    if protected_snapshot(REPO_ROOT) != state.get("protected"):
        fail("protected locks drifted since prepare")
    scratch_project = Path(state["scratch_project"])
    expected_overlay = state.get("scratch_reference_overlay")
    observed = {name: sha256_file(scratch_project / RUNTIME_REL / name)
                for name in REFERENCE_SOURCE_NAMES}
    if observed != expected_overlay:
        fail("scratch reference overlay drifted")
    return state


def build_commands(ue_root: Path, scratch_uproject: Path) -> list[list[str]]:
    build_script = ue_root.resolve() / "Engine/Build/BatchFiles/Build.bat"
    if not build_script.is_file():
        fail("missing Build.bat: " + str(build_script))
    common = [
        "Win64", "Development", "-Project=" + str(scratch_uproject),
        "-WaitMutex", "-NoHotReloadFromIDE", "-NoUBA",
        "-MaxParallelActions=2",
    ]
    prefix = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/s", "/c",
              str(build_script)]
    return [prefix + [target] + common for target in
            ("ThirdPersonEditor", "ThirdPerson")]


def terminate_tree(process: subprocess.Popen) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       check=False, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
    else:
        process.kill()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def run_owned(command: Sequence[str], log_path: Path, timeout_seconds: int,
              memory_limit_mb: int,
              environment: Mapping[str, str] | None = None) -> int:
    env = os.environ.copy()
    env["CRAFTBENCH_GOVERN_RESOURCES"] = "0"
    if environment:
        env.update(environment)
    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0
    with resource_job(memory_limit_mb=memory_limit_mb,
                      name="cb-shared-helper-admission") as job:
        process = subprocess.Popen(
            list(command), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", env=env,
            creationflags=flags)
        assign(job, process.pid)
        try:
            stdout, _ = process.communicate(timeout=timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            terminate_tree(process)
            partial = exc.stdout or ""
            if isinstance(partial, bytes):
                partial = partial.decode("utf-8", errors="replace")
            log_path.write_text(partial, encoding="utf-8")
            fail("owned-tree watchdog timeout=%ds log=%s" %
                 (timeout_seconds, log_path))
        log_path.write_text(stdout or "", encoding="utf-8")
        return int(process.returncode or 0)


def build_phase(output_root: Path, ue_root: Path,
                timeout_seconds: int) -> dict:
    state = load_state(output_root)
    phase = output_root.resolve() / "build"
    if os.path.lexists(str(phase)):
        fail("fresh build phase exists: " + str(phase))
    phase.mkdir()
    commands = build_commands(ue_root, Path(state["scratch_uproject"]))
    write_json(phase / "invocation.json", {"argv": commands,
               "timeout_seconds_per_target": timeout_seconds})
    results = []
    for command in commands:
        target = command[5]
        log = phase / (target + ".log")
        started = time.monotonic()
        code = run_owned(command, log, timeout_seconds, L1_MEM_MB)
        results.append({"target": target, "exit_code": code,
                        "seconds": time.monotonic() - started,
                        "log": str(log),
                        "path_isolation": str(
                            (REPO_ROOT / PROJECT_REL).resolve()).replace(
                                "\\", "/").lower() not in
                            log.read_text(encoding="utf-8", errors="replace").replace(
                                "\\", "/").lower()})
        if code != 0 or not results[-1]["path_isolation"]:
            break
    passed = len(results) == 2 and all(
        item["exit_code"] == 0 and item["path_isolation"] for item in results)
    evidence = {"status": "pass" if passed else "fail", "targets": results}
    write_json(phase / "result.json", evidence)
    load_state(output_root)
    if not passed:
        fail("scratch two-target build failed")
    write_json(phase / "complete.json", evidence)
    print("SHARED-HELPER-ADMISSION BUILD PASS targets=2")
    return evidence


def test_worker(output_root: Path, ue_root: Path) -> int:
    state = load_state(output_root)
    phase = output_root.resolve() / "test"
    result = run_l2(
        ue_root=ue_root,
        project_path=Path(state["scratch_uproject"]),
        test_filter=TEST_FILTER,
        log_path=phase / "l2_pie.log",
        report_dir=phase / "AutomationReport",
        map_name=MAP_NAME,
        map_package_path=MAP_PACKAGE,
        use_nullrhi=True,
        fps=60,
        timeout_seconds=INNER_L2_TIMEOUT_SECONDS,
        expected_test_count=1,
    )
    write_json(phase / "l2_result.json", asdict(result))
    return 0 if result.status == "pass" else 1


def test_phase(output_root: Path, ue_root: Path,
               watchdog_seconds: int) -> dict:
    state = load_state(output_root)
    if not (output_root.resolve() / "build/complete.json").is_file():
        fail("test requires completed build phase")
    phase = output_root.resolve() / "test"
    if os.path.lexists(str(phase)):
        fail("fresh test phase exists: " + str(phase))
    phase.mkdir()
    command = [sys.executable, str(Path(__file__).resolve()),
               "--phase", "_test-worker", "--output-root", str(output_root),
               "--ue-root", str(ue_root)]
    write_json(phase / "invocation.json", {
        "argv": command, "filter": TEST_FILTER, "map": MAP_PACKAGE,
        "expected_test_count": 1, "fps": 60, "rhi": "null",
        "inner_timeout_seconds": INNER_L2_TIMEOUT_SECONDS,
        "outer_watchdog_seconds": watchdog_seconds,
    })
    code = run_owned(command, phase / "worker.stdout.log",
                     watchdog_seconds, L2_MEM_MB)
    result_path = phase / "l2_result.json"
    report_path = phase / "AutomationReport/index.json"
    if not result_path.is_file() or not report_path.is_file():
        fail("test worker did not produce authoritative result/report")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    tests = report.get("tests", [])
    log_text = (phase / "l2_pie.log").read_text(
        encoding="utf-8", errors="replace")
    problems = []
    if code != 0 or result.get("status") != "pass":
        problems.append("worker/result not pass")
    if len(tests) != 1 or tests[0].get("fullTestPath") != TEST_FILTER \
            or tests[0].get("state") != "Success":
        problems.append("exact test/count/path/state mismatch")
    if report.get("succeeded") != 1 or report.get("failed") != 0:
        problems.append("authoritative aggregate mismatch")
    if "[CB-SHARED-LEASE] PASS checkpoints=4" not in log_text:
        problems.append("terminal live GC telemetry absent")
    for gate in ("SHL-1", "SHL-2", "SHL-3", "SHL-4", "SHL-5", "HARNESS:"):
        if gate in log_text:
            problems.append("named failure present: " + gate)
    if protected_snapshot(REPO_ROOT) != state.get("protected"):
        problems.append("protected locks drifted")
    evidence = {"status": "pass" if not problems else "fail",
                "filter": TEST_FILTER, "tests": tests,
                "result": result, "problems": problems,
                "protected_after": protected_snapshot(REPO_ROOT)}
    write_json(phase / "audit.json", evidence)
    if problems:
        fail("reference admission failed: " + "; ".join(problems))
    write_json(phase / "complete.json", evidence)
    print("SHARED-HELPER-ADMISSION TEST PASS exact=1 gates=5 gc_witnesses=3")
    return evidence


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True,
                        choices=("prepare", "build", "test", "_test-worker"))
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--ue-root", type=Path, default=_UE_ROOT)
    parser.add_argument("--build-timeout-seconds", type=int, default=720)
    parser.add_argument("--watchdog-seconds", type=int,
                        default=OUTER_WATCHDOG_SECONDS)
    args = parser.parse_args(argv)
    if args.build_timeout_seconds < 60 or args.watchdog_seconds < 60:
        parser.error("timeouts must be at least 60 seconds")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.phase == "prepare":
        prepare_phase(args.output_root)
    elif args.phase == "build":
        build_phase(args.output_root, args.ue_root, args.build_timeout_seconds)
    elif args.phase == "test":
        test_phase(args.output_root, args.ue_root, args.watchdog_seconds)
    else:
        return test_worker(args.output_root, args.ue_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

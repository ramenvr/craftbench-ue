"""Fail-closed exact-one admission runner for the catalog-reader task.

The public phases are deliberately separate.  No invocation chains a build,
automation enumeration, or a test:

    prepare   copy the live substrate to a disposable root and overlay reference
    build     build both scratch targets with the governed task-local argv
    enumerate list engine-discovered tests and lock one exact full path
    test      run that exact path through shared ``l2_pie.run_l2``

The live empty scaffold is never an overlay destination.  Twenty-one protected
files (live catalog 9, admission map 1, quarantined catalog 9, reference source
2) are byte-locked before and after every phase; the final map must stay absent.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Callable, Iterable, Mapping, Sequence


TASK_ID = "t2-each-catalog-reader-reports-only-its-own-records"
MAP_NAME = "L_CatalogReadersAdmission"
MAP_PACKAGE = f"/Game/__CraftBenchAdmission/{TASK_ID}/{MAP_NAME}"
# Functional-test automation uses the placed actor's authored label as the
# display-name segment.  The admission fixture is deliberately labelled
# differently from the final-map fixture, so lock the engine-observed admission
# identity rather than deriving it from the C++ class name.
DISPLAY_NAME = "CatalogReadersAdmissionFunctionalTest"
DEFAULT_QUARANTINE = Path(
    r"C:\cbtmp\catalog-assets-untrusted-20260820T115500Z\Catalog"
)
OUTER_WATCHDOG_SECONDS = 720
INNER_L2_TIMEOUT_SECONDS = 710

HERE = Path(__file__).resolve().parent
TASK_ROOT = HERE.parent
REPO_ROOT = TASK_ROOT.parents[2]
VERIFY_ROOT = REPO_ROOT / "tools" / "verify-single"
if str(VERIFY_ROOT) not in sys.path:
    sys.path.insert(0, str(VERIFY_ROOT))

# Shared seams are load-bearing.  In particular, the test phase must not grow a
# task-local imitation of the production L2 parser or process invocation.
from layers.l2_pie import L2Result, run_l2  # noqa: E402
from job_governor import L2_MEM_MB, assign, resource_job  # noqa: E402
from run_task import copy_substrate_from_live  # noqa: E402


PROJECT_REL = Path("UE-projects/ThirdPerson")
UPROJECT_NAME = "ThirdPerson.uproject"
CATALOG_REL = Path("Content/Maps") / TASK_ID / "Catalog"
ADMISSION_MAP_REL = (
    Path("Content/__CraftBenchAdmission") / TASK_ID / f"{MAP_NAME}.umap"
)
FINAL_MAP_REL = Path("Content/Maps") / TASK_ID / "L_CatalogReaders.umap"
RUNTIME_REL = Path("Source/ThirdPerson/Tasks") / TASK_ID / "CatalogReaderActor"
REFERENCE_ROOT_REL = (
    Path("Source/ThirdPerson/Tasks") / TASK_ID
)
REFERENCE_FILE_RELS = (
    REFERENCE_ROOT_REL / "CatalogReaderActor.cpp",
    REFERENCE_ROOT_REL / "CatalogReaderActor.h",
)
CATALOG_FILE_RELS = (
    Path("Outside/DA_Alpha_Outside.uasset"),
    Path("Outside/DA_Beta_Outside.uasset"),
    Path("ShelfA/DA_Alpha_Cedar.uasset"),
    Path("ShelfA/DA_Alpha_Lapis.uasset"),
    Path("ShelfA/DA_Alpha_Quartz.uasset"),
    Path("ShelfA/DA_Beta_WrongType.uasset"),
    Path("ShelfB/DA_Alpha_WrongType.uasset"),
    Path("ShelfB/DA_Beta_Amber.uasset"),
    Path("ShelfB/DA_Beta_Violet.uasset"),
)

EXPECTED_CHECKPOINTS = (
    "[CB-CP] idx=0 t=0.20",
    "[CB-CP] idx=1 t=0.80",
    "[CB-CP] idx=2 t=1.20",
)
EXPECTED_SUMMARY = (
    "[CB-CATALOG] checkpoint=2 readers=2 catalog=9 reports=2 unloaded=1"
)
NAMED_FAILURES = (
    "CR-0 reader_world_configuration",
    "CR-1 exact_actor_scoped_metadata_reports",
    "CR-2 all_examined_packages_remain_unloaded",
    "CR-3 one_beginplay_report_per_instance",
    "HARNESS:",
)


def fail(detail: str) -> None:
    raise RuntimeError("CATALOG-ADMISSION ERROR " + detail)


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
        return bool(getattr(os.lstat(path), "st_reparse_tag", 0))
    except OSError:
        return False


def assert_no_reparse_chain(root: Path, path: Path) -> None:
    root_abs = Path(os.path.abspath(root))
    path_abs = Path(os.path.abspath(path))
    try:
        relative = path_abs.relative_to(root_abs)
    except ValueError as exc:
        fail(f"path escapes declared root: root={root_abs} path={path_abs}")
        raise AssertionError from exc
    current = root_abs
    if current.exists() and _is_reparse(current):
        fail(f"declared root is a reparse point: {current}")
    for part in relative.parts:
        current /= part
        if current.exists() and _is_reparse(current):
            fail(f"protected path traverses a reparse point: {current}")


def file_fact(path: Path, *, root: Path) -> dict[str, object]:
    assert_no_reparse_chain(root, path)
    if not path.is_file():
        fail(f"missing protected regular file: {path}")
    return {
        "path": str(path.resolve()),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def assert_exact_tree(root: Path, expected: Iterable[Path]) -> None:
    expected_set = {item.as_posix() for item in expected}
    if not root.is_dir():
        fail(f"missing protected directory: {root}")
    assert_no_reparse_chain(root.parent, root)
    found: set[str] = set()
    for item in root.rglob("*"):
        assert_no_reparse_chain(root, item)
        if item.is_file():
            found.add(item.relative_to(root).as_posix())
    if found != expected_set:
        fail(
            "protected inventory mismatch "
            f"root={root} expected={sorted(expected_set)} found={sorted(found)}"
        )


def project_root(repo: Path) -> Path:
    return repo / PROJECT_REL


def reference_root(repo: Path) -> Path:
    return (
        repo
        / "tasks/craftbench-public"
        / TASK_ID
        / "reference"
    )


def assert_final_absent(repo: Path) -> None:
    final_path = project_root(repo) / FINAL_MAP_REL
    assert_no_reparse_chain(project_root(repo), final_path.parent)
    if os.path.lexists(str(final_path)):
        fail(f"protected final map must remain absent: {final_path}")


def protected_snapshot(
    repo: Path,
    quarantine: Path = DEFAULT_QUARANTINE,
) -> dict[str, dict[str, object]]:
    """Return the exact 21-file live/reference/quarantine lock."""

    project = project_root(repo)
    catalog = project / CATALOG_REL
    assert_exact_tree(catalog, CATALOG_FILE_RELS)
    assert_exact_tree(quarantine, CATALOG_FILE_RELS)
    ref = reference_root(repo)
    assert_exact_tree(ref, REFERENCE_FILE_RELS)
    assert_final_absent(repo)

    facts: dict[str, dict[str, object]] = {}
    for relative in CATALOG_FILE_RELS:
        facts[f"live_catalog:{relative.as_posix()}"] = file_fact(
            catalog / relative, root=catalog
        )
    facts["admission_map"] = file_fact(
        project / ADMISSION_MAP_REL, root=project
    )
    for relative in CATALOG_FILE_RELS:
        facts[f"quarantine_catalog:{relative.as_posix()}"] = file_fact(
            quarantine / relative, root=quarantine
        )
    for relative in REFERENCE_FILE_RELS:
        facts[f"reference:{relative.as_posix()}"] = file_fact(
            ref / relative, root=ref
        )
    if len(facts) != 21:
        fail(f"internal protected-lock cardinality expected=21 found={len(facts)}")
    return facts


def live_empty_snapshot(repo: Path) -> dict[str, dict[str, object]]:
    project = project_root(repo)
    cpp = project / RUNTIME_REL.with_suffix(".cpp")
    header = project / RUNTIME_REL.with_suffix(".h")
    cpp_text = cpp.read_text(encoding="utf-8")
    header_text = header.read_text(encoding="utf-8")
    if "Empty scaffold implementation" not in cpp_text:
        fail("live CatalogReaderActor.cpp is not the declared empty scaffold")
    # The behavior-only sentence is intentionally wrapped across comment lines.
    # Collapse whitespace so formatting alone cannot invalidate the empty proof.
    header_comment_text = " ".join(
        re.sub(r"^\s*//\s?", "", line).strip()
        for line in header_text.splitlines()
    )
    if "No catalog query or report behavior is supplied" not in header_comment_text:
        fail("live CatalogReaderActor.h is not the declared empty scaffold")
    facts = {
        "cpp": file_fact(cpp, root=project),
        "h": file_fact(header, root=project),
    }
    ref = reference_root(repo)
    for suffix, key in ((".cpp", "cpp"), (".h", "h")):
        ref_path = ref / RUNTIME_REL.with_suffix(suffix)
        if facts[key]["sha256"] == sha256_file(ref_path):
            fail(f"live empty scaffold already equals reference overlay: {suffix}")
    return facts


def _json_ready(value):
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_ready(value), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def read_json(path: Path) -> dict:
    if not path.is_file():
        fail(f"required state file is absent: {path}")
    try:
        # UE automation index.json is UTF-8 with a BOM on the pinned Windows
        # build; utf-8-sig is also byte-compatible with our BOM-free state JSON.
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"invalid state JSON {path}: {exc}")
    if not isinstance(value, dict):
        fail(f"state JSON root is not an object: {path}")
    return value


def compare_snapshot(label: str, expected: Mapping, actual: Mapping) -> None:
    if actual != expected:
        fail(
            f"{label} drifted; expected={json.dumps(expected, sort_keys=True)} "
            f"actual={json.dumps(actual, sort_keys=True)}"
        )


def content_identities(snapshot: Mapping[str, Mapping]) -> dict[str, dict]:
    """Drop absolute path fields when comparing live bytes to scratch bytes."""

    return {
        key: {
            "bytes": value.get("bytes"),
            "sha256": value.get("sha256"),
        }
        for key, value in snapshot.items()
    }


def scratch_content_snapshot(
    scratch_project: Path,
) -> dict[str, dict[str, object]]:
    facts: dict[str, dict[str, object]] = {}
    catalog = scratch_project / CATALOG_REL
    assert_exact_tree(catalog, CATALOG_FILE_RELS)
    for relative in CATALOG_FILE_RELS:
        facts[f"live_catalog:{relative.as_posix()}"] = file_fact(
            catalog / relative, root=catalog
        )
    facts["admission_map"] = file_fact(
        scratch_project / ADMISSION_MAP_REL, root=scratch_project
    )
    final = scratch_project / FINAL_MAP_REL
    if os.path.lexists(str(final)):
        fail(f"scratch final map must remain absent: {final}")
    return facts


def overlay_reference(repo: Path, scratch_project: Path) -> dict[str, dict]:
    ref = reference_root(repo)
    assert_exact_tree(ref, REFERENCE_FILE_RELS)
    destinations: list[tuple[Path, Path, dict]] = []
    for relative in REFERENCE_FILE_RELS:
        source = ref / relative
        destination = scratch_project / relative
        assert_no_reparse_chain(ref, source)
        assert_no_reparse_chain(scratch_project, destination)
        if not destination.is_file():
            fail(f"scratch scaffold overlay destination missing: {destination}")
        shutil.copy2(source, destination)
        source_fact = file_fact(source, root=ref)
        destination_fact = file_fact(destination, root=scratch_project)
        if source_fact["sha256"] != destination_fact["sha256"]:
            fail(f"reference overlay readback mismatch: {relative}")
        destinations.append((relative, destination, destination_fact))

    # The scratch copy intentionally retains live Intermediate/Binaries for an
    # incremental admission build.  copy2 preserves the reference's historical
    # mtime, which may be OLDER than the empty scaffold's cached object and let
    # UBT reuse the wrong code.  Mirror shared warm-cache policy: make overlaid
    # compile inputs four seconds newer than every cached artifact.
    newest_ns = 0
    for cached_name in ("Intermediate", "Binaries"):
        cached_root = scratch_project / cached_name
        if not cached_root.is_dir():
            continue
        for dirpath, _dirnames, filenames in os.walk(cached_root):
            for filename in filenames:
                try:
                    newest_ns = max(
                        newest_ns,
                        (Path(dirpath) / filename).stat().st_mtime_ns,
                    )
                except OSError:
                    continue
    bump_ns = max(time.time_ns(), newest_ns + 4_000_000_000)
    facts: dict[str, dict] = {}
    for relative, destination, destination_fact in destinations:
        os.utime(destination, ns=(bump_ns, bump_ns))
        facts[relative.as_posix()] = {
            "file": destination_fact,
            "compile_mtime_ns": destination.stat().st_mtime_ns,
        }
    return facts


def _assert_output_root_safe(repo: Path, output_root: Path) -> None:
    absolute = Path(os.path.abspath(output_root))
    repo_absolute = Path(os.path.abspath(repo))
    try:
        absolute.relative_to(repo_absolute)
    except ValueError:
        pass
    else:
        fail(f"disposable output root must be outside the repository: {absolute}")
    if os.path.lexists(str(absolute)):
        fail(f"fresh output root already exists: {absolute}")
    assert_no_reparse_chain(absolute.parent, absolute.parent)


def prepare_workspace(
    *,
    repo: Path,
    output_root: Path,
    quarantine: Path = DEFAULT_QUARANTINE,
    copy_func: Callable[[Path, Path], None] = copy_substrate_from_live,
) -> dict:
    repo = repo.resolve()
    # Expand any 8.3 component before the path reaches UBT/UE.  This mirrors
    # shared run_task.new_temp_workdir's ReportExportPath invariant.
    output_root = output_root.resolve()
    _assert_output_root_safe(repo, output_root)

    locks = protected_snapshot(repo, quarantine)
    empty_before = live_empty_snapshot(repo)
    live_project = project_root(repo)
    output_root.mkdir(parents=True)
    scratch_project = output_root / "scratch" / "ThirdPerson"
    scratch_project.parent.mkdir(parents=True)
    copy_func(live_project, scratch_project)

    # A copied UBT makefile/action history retains absolute paths to the live
    # project. Reusing it can compile the live empty source while appearing to
    # build the scratch overlay. This port requires a genuinely isolated cold
    # build, so discard only generated scratch products before overlaying.
    for generated_name in ("Intermediate", "Binaries"):
        generated = scratch_project / generated_name
        if generated.is_dir():
            shutil.rmtree(generated)
        elif os.path.lexists(str(generated)):
            fail(f"unexpected non-directory scratch generated path: {generated}")

    # Before overlay, the scratch destinations must be byte-identical to live.
    for suffix, key in ((".cpp", "cpp"), (".h", "h")):
        scratch = scratch_project / RUNTIME_REL.with_suffix(suffix)
        fact = file_fact(scratch, root=scratch_project)
        if fact["sha256"] != empty_before[key]["sha256"]:
            fail(f"scratch scaffold did not originate from live empty {suffix}")

    overlay = overlay_reference(repo, scratch_project)
    scratch_content = scratch_content_snapshot(scratch_project)
    live_subset = {
        key: value for key, value in locks.items()
        if key == "admission_map" or key.startswith("live_catalog:")
    }
    compare_snapshot(
        "scratch protected content",
        content_identities(live_subset),
        content_identities(scratch_content),
    )
    compare_snapshot("live 21-file lock", locks, protected_snapshot(repo, quarantine))
    compare_snapshot("live empty scaffold", empty_before, live_empty_snapshot(repo))

    state = {
        "schema": 1,
        "task_id": TASK_ID,
        "repo": str(repo),
        "quarantine": str(Path(os.path.abspath(quarantine))),
        "output_root": str(output_root),
        "scratch_project": str(scratch_project),
        "scratch_uproject": str(scratch_project / UPROJECT_NAME),
        "locks_21": locks,
        "live_empty": empty_before,
        "scratch_overlay": overlay,
        "scratch_content_10": scratch_content,
        "final_absent": True,
    }
    write_json(output_root / "state.json", state)
    print(
        "CATALOG-ADMISSION PREPARED "
        f"locks=21 scratch_content=10 overlay=2 root={output_root}"
    )
    return state


def load_and_validate_state(output_root: Path) -> dict:
    output_root = output_root.resolve()
    state = read_json(output_root / "state.json")
    if state.get("schema") != 1 or state.get("task_id") != TASK_ID:
        fail("state schema/task identity mismatch")
    if Path(state.get("output_root", "")) != output_root:
        fail("state output-root identity mismatch")
    repo = Path(state["repo"])
    quarantine = Path(state["quarantine"])
    compare_snapshot(
        "live 21-file lock",
        state["locks_21"],
        protected_snapshot(repo, quarantine),
    )
    compare_snapshot(
        "live empty scaffold",
        state["live_empty"],
        live_empty_snapshot(repo),
    )
    scratch_project = Path(state["scratch_project"])
    compare_snapshot(
        "scratch protected content",
        state["scratch_content_10"],
        scratch_content_snapshot(scratch_project),
    )
    for relative, expected in state["scratch_overlay"].items():
        actual = file_fact(scratch_project / relative, root=scratch_project)
        if actual != expected.get("file"):
            fail(f"scratch reference overlay drifted: {relative}")
        if (scratch_project / relative).stat().st_mtime_ns < int(
            expected.get("compile_mtime_ns", 0)
        ):
            fail(f"scratch reference overlay compile mtime regressed: {relative}")
    return state


@contextmanager
def temporary_environment(values: Mapping[str, str]):
    old = {key: os.environ.get(key) for key in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _terminate_owned_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        process.kill()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def run_owned(
    command: Sequence[str],
    *,
    log_path: Path,
    timeout_seconds: int,
    environment: Mapping[str, str] | None = None,
) -> int:
    """Run one exact argv behind a silent-safe owned-tree watchdog."""

    log_path.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    # The outer process always owns the tree.  A caller may deliberately pass
    # 0 to the child (the l2 worker does) to avoid nesting shared run_l2's Job
    # Object inside this already-governed tree.
    env["CRAFTBENCH_GOVERN_RESOURCES"] = "1"
    if environment:
        env.update(environment)
    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    with temporary_environment({"CRAFTBENCH_GOVERN_RESOURCES": "1"}):
        with resource_job(memory_limit_mb=L2_MEM_MB, name="cb-catalog-admission") as job:
            process = subprocess.Popen(
                list(command),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                creationflags=creationflags,
            )
            assign(job, process.pid)
            try:
                stdout, _ = process.communicate(timeout=timeout_seconds)
            except subprocess.TimeoutExpired as exc:
                _terminate_owned_tree(process)
                partial = exc.stdout or ""
                if isinstance(partial, bytes):
                    partial = partial.decode("utf-8", errors="replace")
                log_path.write_text(partial, encoding="utf-8")
                fail(
                    f"owned-tree watchdog timeout={timeout_seconds}s "
                    f"pid={process.pid} log={log_path}"
                )
            log_path.write_text(stdout or "", encoding="utf-8")
            return int(process.returncode or 0)


def build_commands(ue_root: Path, scratch_uproject: Path) -> list[list[str]]:
    """Return the exact two-target argv; every safety flag is explicit."""

    build_script = (
        ue_root.resolve() / "Engine/Build/BatchFiles/Build.bat"
    )
    if not build_script.is_file():
        fail(f"missing UBT build script: {build_script}")
    common = [
        "Win64",
        "Development",
        f"-Project={scratch_uproject}",
        "-WaitMutex",
        "-NoHotReloadFromIDE",
        "-NoUBA",
        "-MaxParallelActions=2",
    ]
    command_prefix = [
        os.environ.get("COMSPEC", "cmd.exe"),
        "/d",
        "/s",
        "/c",
        str(build_script),
    ]
    return [
        command_prefix + [target] + common
        for target in ("ThirdPersonEditor", "ThirdPerson")
    ]


def build_phase(
    *,
    output_root: Path,
    ue_root: Path,
    timeout_seconds: int,
    run_owned_fn: Callable[..., int] = run_owned,
) -> dict:
    state = load_and_validate_state(output_root)
    phase_root = Path(state["output_root"]) / "build"
    if os.path.lexists(str(phase_root)):
        fail(f"fresh build phase output already exists: {phase_root}")
    phase_root.mkdir()
    commands = build_commands(ue_root, Path(state["scratch_uproject"]))
    write_json(
        phase_root / "invocation.json",
        {
            "argv_by_target": commands,
            "timeout_seconds_per_target": timeout_seconds,
            "required_flags": [
                "-WaitMutex",
                "-NoHotReloadFromIDE",
                "-NoUBA",
                "-MaxParallelActions=2",
            ],
        },
    )
    results: list[dict] = []
    for command in commands:
        target = command[5]
        log_path = phase_root / f"{target}.log"
        started = time.monotonic()
        exit_code = run_owned_fn(
            command,
            log_path=log_path,
            timeout_seconds=timeout_seconds,
        )
        result = {
            "target": target,
            "argv": command,
            "exit_code": exit_code,
            "duration_seconds": time.monotonic() - started,
            "log": str(log_path),
        }
        log_text = log_path.read_text(encoding="utf-8", errors="replace")
        live_project_marker = str(project_root(Path(state["repo"])).resolve()).replace(
            "\\", "/"
        )
        result["path_isolation"] = (
            live_project_marker.lower()
            not in log_text.replace("\\", "/").lower()
        )
        results.append(result)
        if exit_code != 0 or not result["path_isolation"]:
            break
    evidence = {
        "status": (
            "pass"
            if len(results) == 2
            and all(item["exit_code"] == 0 and item["path_isolation"]
                    for item in results)
            else "fail"
        ),
        "targets": results,
        "required_flags": [
            "-WaitMutex",
            "-NoHotReloadFromIDE",
            "-NoUBA",
            "-MaxParallelActions=2",
        ],
    }
    write_json(phase_root / "result.json", evidence)
    load_and_validate_state(output_root)
    if evidence["status"] != "pass":
        fail(f"scratch reference two-target build failed: {evidence}")
    write_json(phase_root / "complete.json", evidence)
    print(
        "CATALOG-ADMISSION BUILD PASS targets=2 exit=0 "
        f"duration={sum(item['duration_seconds'] for item in results):.2f}"
    )
    return evidence


_LISTED_TEST_RE = re.compile(
    r"LogAutomationCommandLine:\s*Display:\s*'([^'\r\n]+)'"
)


def discover_exact_filter(log_text: str) -> dict[str, object]:
    listed = sorted(set(_LISTED_TEST_RE.findall(log_text)))
    map_prefix = (
        "Project.Functional Tests.__CraftBenchAdmission."
        f"{TASK_ID}.{MAP_NAME}."
    )
    candidates = [
        item for item in listed
        if item.startswith(map_prefix)
    ]
    if len(candidates) != 1:
        fail(
            "engine enumeration did not yield exactly one exact task/map path; "
            f"candidates={candidates} listed_count={len(listed)}"
        )
    full_path = candidates[0]
    observed_display = full_path.rsplit(".", 1)[-1]
    if observed_display != DISPLAY_NAME:
        fail(
            "engine display name mismatch "
            f"expected={DISPLAY_NAME!r} observed={observed_display!r} "
            f"path={full_path!r}"
        )
    return {
        "full_test_path": full_path,
        "display_name": observed_display,
        "listed_count": len(listed),
        "selection": (
            "engine Automation List; exact task/map prefix and observed display"
        ),
    }


def require_build_complete(state: Mapping) -> dict:
    complete = Path(state["output_root"]) / "build" / "complete.json"
    return read_json(complete)


def enumerate_phase(
    *, output_root: Path, ue_root: Path, timeout_seconds: int
) -> dict:
    state = load_and_validate_state(output_root)
    require_build_complete(state)
    phase_root = Path(state["output_root"]) / "enumerate"
    if os.path.lexists(str(phase_root)):
        fail(f"fresh enumeration output already exists: {phase_root}")
    phase_root.mkdir()
    editor = (
        ue_root.resolve()
        / "Engine/Binaries/Win64/UnrealEditor-Cmd.exe"
    )
    if not editor.is_file():
        fail(f"missing UE editor binary: {editor}")
    command = [
        str(editor),
        state["scratch_uproject"],
        MAP_PACKAGE,
        "-nullrhi",
        "-unattended",
        "-nopause",
        "-nosplash",
        "-nosound",
        "-deterministic",
        "-FPS=60",
        "-stdout",
        "-FullStdOutLogOutput",
        "-ExecCmds=Automation List; Quit",
    ]
    write_json(
        phase_root / "invocation.json",
        {"argv": command, "timeout_seconds": timeout_seconds},
    )
    log_path = phase_root / "automation_list.log"
    exit_code = run_owned(
        command, log_path=log_path, timeout_seconds=timeout_seconds
    )
    if exit_code != 0:
        fail(f"Automation List process exited {exit_code}; log={log_path}")
    evidence = discover_exact_filter(
        log_path.read_text(encoding="utf-8", errors="replace")
    )
    evidence.update({"exit_code": exit_code, "log": str(log_path)})
    write_json(phase_root / "enumeration.json", evidence)
    load_and_validate_state(output_root)
    print(
        "CATALOG-ADMISSION ENUMERATION PASS exact=1 "
        f"path={evidence['full_test_path']}"
    )
    return evidence


def _serialize_l2_result(result: L2Result) -> dict:
    value = asdict(result)
    value["log_path"] = str(result.log_path)
    value["report_path"] = str(result.report_path) if result.report_path else None
    return value


def l2_worker(
    request_path: Path,
    *,
    run_l2_fn: Callable[..., L2Result] = run_l2,
) -> dict:
    request = read_json(request_path)
    state = read_json(Path(request["state_json"]))
    enumeration = read_json(Path(request["enumeration_json"]))
    if state.get("task_id") != TASK_ID:
        fail("l2 worker state task identity mismatch")
    if Path(request["project"]) != Path(state.get("scratch_uproject", "")):
        fail("l2 worker refuses any project other than the disposable scratch")
    if request.get("full_test_path") != enumeration.get("full_test_path"):
        fail("l2 worker filter is not the engine-enumerated full path")
    result = run_l2_fn(
        ue_root=Path(request["ue_root"]),
        project_path=Path(request["project"]),
        test_filter=request["full_test_path"],
        log_path=Path(request["l2_log"]),
        report_dir=Path(request["report_dir"]),
        map_package_path=MAP_PACKAGE,
        use_nullrhi=True,
        fps=60,
        timeout_seconds=INNER_L2_TIMEOUT_SECONDS,
        expected_test_count=1,
        extra_env={"CRAFTBENCH_GOVERN_RESOURCES": "0"},
    )
    serialized = _serialize_l2_result(result)
    write_json(Path(request["result_json"]), serialized)
    return serialized


def _primary_logtemp_payloads(log_text: str) -> list[str]:
    payloads: list[str] = []
    marker = "LogTemp: Display: "
    for line in log_text.splitlines():
        if "LogAutomationController:" in line or marker not in line:
            continue
        payloads.append(line.split(marker, 1)[1].strip())
    return payloads


def _load_exact_report(report_path: Path, full_path: str) -> dict:
    report = read_json(report_path)
    tests = report.get("tests")
    if not isinstance(tests, list) or len(tests) != 1:
        fail(f"automation report expected exactly one test; found={tests!r}")
    test = tests[0]
    if not isinstance(test, dict):
        fail("automation report test entry is not an object")
    if test.get("fullTestPath") != full_path:
        fail(
            "automation report fullTestPath mismatch "
            f"expected={full_path!r} found={test.get('fullTestPath')!r}"
        )
    if test.get("testDisplayName") != DISPLAY_NAME:
        fail(
            "automation report display mismatch "
            f"expected={DISPLAY_NAME!r} found={test.get('testDisplayName')!r}"
        )
    if test.get("state") != "Success":
        fail(f"automation report state is not Success: {test.get('state')!r}")
    for field, expected in (
        ("succeeded", 1),
        ("succeededWithWarnings", 0),
        ("failed", 0),
        ("notRun", 0),
        ("inProcess", 0),
    ):
        if report.get(field) != expected:
            fail(
                f"automation report {field} expected={expected} "
                f"found={report.get(field)!r}"
            )
    return {"report": report, "test": test}


def audit_test_outputs(
    *, result: Mapping, full_path: str
) -> dict[str, object]:
    if result.get("status") != "pass":
        fail(f"shared l2_pie verdict was not PASS: {result}")
    expected_counts = {
        "tests_run": 1,
        "tests_passed": 1,
        "tests_failed": 0,
        "tests_skipped": 0,
    }
    for field, expected in expected_counts.items():
        if result.get(field) != expected:
            fail(
                f"shared l2_pie {field} expected={expected} "
                f"found={result.get(field)!r}"
            )
    if result.get("result_source") != "json":
        fail(f"authoritative report JSON was not used: {result.get('result_source')}")
    report_path_raw = result.get("report_path")
    if not report_path_raw:
        fail("shared l2_pie did not return an automation report path")
    report_path = Path(report_path_raw)
    report_data = _load_exact_report(report_path, full_path)

    log_path = Path(result["log_path"])
    if not log_path.is_file():
        fail(f"shared l2_pie log is absent: {log_path}")
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    payloads = _primary_logtemp_payloads(log_text)
    checkpoints = [item for item in payloads if item.startswith("[CB-CP]")]
    if checkpoints != list(EXPECTED_CHECKPOINTS):
        fail(
            f"world-clock checkpoint telemetry mismatch expected="
            f"{EXPECTED_CHECKPOINTS} found={checkpoints}"
        )
    summaries = [item for item in payloads if item.startswith("[CB-CATALOG]")]
    if summaries != [EXPECTED_SUMMARY]:
        fail(f"catalog completion telemetry mismatch: {summaries}")
    present_failures = [token for token in NAMED_FAILURES if token in log_text]
    if present_failures:
        fail(f"named failure telemetry appeared in PASS leg: {present_failures}")

    return {
        "executed_count": 1,
        "display_name": DISPLAY_NAME,
        "full_test_path": full_path,
        "state": "Success",
        "result_source": "json",
        "report_path": str(report_path),
        "report_counts": expected_counts,
        "checkpoints": list(EXPECTED_CHECKPOINTS),
        "summary": EXPECTED_SUMMARY,
        "named_gates": {
            "CR-1 exact_actor_scoped_metadata_reports": "PASS",
            "CR-2 all_examined_packages_remain_unloaded": "PASS",
            "CR-3 one_beginplay_report_per_instance": "PASS",
        },
        "report_test": report_data["test"],
    }


def test_phase(
    *, output_root: Path, ue_root: Path, timeout_seconds: int
) -> dict:
    if timeout_seconds != OUTER_WATCHDOG_SECONDS:
        fail(
            f"exact admission outer watchdog must be {OUTER_WATCHDOG_SECONDS}s; "
            f"found={timeout_seconds}"
        )
    state = load_and_validate_state(output_root)
    require_build_complete(state)
    enumeration = read_json(
        Path(state["output_root"]) / "enumerate" / "enumeration.json"
    )
    full_path = enumeration.get("full_test_path")
    if not isinstance(full_path, str) or not full_path:
        fail("engine-enumerated full test path is absent")
    # Re-validate the stored value through the same fail-closed selector shape.
    if not full_path.endswith(f".{MAP_NAME}.{DISPLAY_NAME}"):
        fail(f"stored engine-enumerated path identity mismatch: {full_path}")

    phase_root = Path(state["output_root"]) / "test"
    if os.path.lexists(str(phase_root)):
        fail(f"fresh test output already exists: {phase_root}")
    phase_root.mkdir()
    request = {
        "ue_root": str(ue_root.resolve()),
        "project": state["scratch_uproject"],
        "full_test_path": full_path,
        "l2_log": str(phase_root / "l2_pie.log"),
        "report_dir": str(phase_root / "AutomationReport"),
        "result_json": str(phase_root / "l2_result.json"),
        "inner_timeout_seconds": INNER_L2_TIMEOUT_SECONDS,
        "outer_watchdog_seconds": timeout_seconds,
        "expected_test_count": 1,
        "use_nullrhi": True,
        "fps": 60,
        "map_package": MAP_PACKAGE,
        "state_json": str(Path(state["output_root"]) / "state.json"),
        "enumeration_json": str(
            Path(state["output_root"]) / "enumerate" / "enumeration.json"
        ),
    }
    request_path = phase_root / "request.json"
    write_json(request_path, request)
    worker_command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--phase",
        "_l2-worker",
        "--request",
        str(request_path),
    ]
    write_json(phase_root / "invocation.json", {"argv": worker_command, **request})
    exit_code = run_owned(
        worker_command,
        log_path=phase_root / "worker.stdout.log",
        timeout_seconds=timeout_seconds,
        environment={"CRAFTBENCH_GOVERN_RESOURCES": "0"},
    )
    if exit_code != 0:
        fail(
            f"l2 worker exited {exit_code}; "
            f"log={phase_root / 'worker.stdout.log'}"
        )
    result = read_json(phase_root / "l2_result.json")
    evidence = audit_test_outputs(result=result, full_path=full_path)
    validated = load_and_validate_state(output_root)
    evidence["locks_21_after"] = validated["locks_21"]
    evidence["final_absent"] = True
    evidence["scratch_only_reference_overlay"] = validated["scratch_overlay"]
    write_json(phase_root / "test_evidence.json", evidence)
    print(
        "CATALOG-ADMISSION TEST PASS count=1 state=Success "
        "checkpoints=3 gates=3 locks=21"
    )
    return evidence


def parse_args(argv: Sequence[str] | None = None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--phase",
        required=True,
        choices=("prepare", "build", "enumerate", "test", "_l2-worker"),
    )
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--ue-root", type=Path)
    parser.add_argument("--request", type=Path)
    parser.add_argument("--build-timeout", type=int, default=1800)
    parser.add_argument(
        "--watchdog-seconds", type=int, default=OUTER_WATCHDOG_SECONDS
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.phase == "_l2-worker":
        if args.request is None:
            fail("_l2-worker requires --request")
        l2_worker(args.request)
        return 0
    if args.output_root is None:
        fail(f"{args.phase} requires --output-root")
    if args.phase == "prepare":
        prepare_workspace(
            repo=REPO_ROOT,
            output_root=args.output_root,
            quarantine=DEFAULT_QUARANTINE,
        )
        return 0
    if args.ue_root is None:
        fail(f"{args.phase} requires --ue-root")
    if args.phase == "build":
        build_phase(
            output_root=args.output_root,
            ue_root=args.ue_root,
            timeout_seconds=args.build_timeout,
        )
    elif args.phase == "enumerate":
        enumerate_phase(
            output_root=args.output_root,
            ue_root=args.ue_root,
            timeout_seconds=args.watchdog_seconds,
        )
    elif args.phase == "test":
        test_phase(
            output_root=args.output_root,
            ue_root=args.ue_root,
            timeout_seconds=args.watchdog_seconds,
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

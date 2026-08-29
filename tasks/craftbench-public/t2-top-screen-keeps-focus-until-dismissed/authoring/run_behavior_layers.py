"""Task-local L2/L2I recovery runner for the CommonUI focus-stack task.

This does not build.  It reuses a short-path project whose Editor and Game L1
targets already passed, then calls CraftBench's production L2 and L2I layer
adapters.  The controller wraps each adapter in a separate Python process so a
silent UnrealEditor freeze cannot defeat the wall-clock timeout in
``l2_pie._run_editor_with_marker_kill``.

The resulting report is supplemental behavior evidence, not a replacement for
a complete clean ``cb discriminate`` run.  In particular, it records and pins
the reused L1 log instead of claiming to have executed L1 itself.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

#: Engine root. Override with CB_UE_ROOT; defaults to Epic's standard install.
_UE_ROOT = Path(os.environ.get("CB_UE_ROOT", r"C:\Program Files\Epic Games\UE_5.8"))


TASK_ID = "t2-top-screen-keeps-focus-until-dismissed"
SUBMITTED_ASSETS = (
    f"Content/Tasks/{TASK_ID}/WBP_DetailScreen.uasset",
    f"Content/Tasks/{TASK_ID}/WBP_HomeScreen.uasset",
    f"Content/Tasks/{TASK_ID}/WBP_MenuRoot.uasset",
)
L1_TARGETS = ("ThirdPersonEditor", "ThirdPerson")
EMPTY_NAMED_TOKEN = "GATE[root_and_screens_are_activatable]: "


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _verify_root() -> Path:
    return _repo_root() / "tools" / "verify-single"


def _task_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _asset_hashes(root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for rel in SUBMITTED_ASSETS:
        path = root / Path(rel)
        if not path.is_file():
            raise FileNotFoundError(f"required asset missing: {path}")
        hashes[rel] = _sha256(path)
    return hashes


def _reference_hashes() -> dict[str, str]:
    return _asset_hashes(_task_root() / "reference")


def _baseline_sources() -> dict[str, Path]:
    baseline_dir = _task_root() / "authoring" / "_baseline_backup"
    sources: dict[str, Path] = {}
    for rel in SUBMITTED_ASSETS:
        source = baseline_dir / Path(rel).name
        if not source.is_file():
            raise FileNotFoundError(f"baseline asset missing: {source}")
        sources[rel] = source
    return sources


def _validate_l1_log(log_path: Path, project_root: Path) -> dict[str, object]:
    if not log_path.is_file():
        raise FileNotFoundError(f"reused L1 log missing: {log_path}")
    text = log_path.read_text(encoding="utf-8", errors="replace")
    missing: list[str] = []
    project_arg = f"-project={project_root / 'ThirdPerson.uproject'}".lower()
    lower = text.lower()
    for target in L1_TARGETS:
        header = f"=== L1 target: {target} (exit 0,"
        command = f" {target} Win64 Development "
        if header not in text:
            missing.append(f"successful target header: {target}")
        command_lines = [
            line for line in text.splitlines()
            if command.lower() in line.lower() and "UnrealBuildTool" in line
        ]
        if not command_lines:
            missing.append(f"UBT command: {target}")
            continue
        if not any("-MaxParallelActions=2" in line for line in command_lines):
            missing.append(f"-MaxParallelActions=2: {target}")
        if not any(project_arg in line.lower() for line in command_lines):
            missing.append(f"matching project path: {target}")
    if text.count("Result: Succeeded") < 2:
        missing.append("two Result: Succeeded markers")
    if missing:
        raise RuntimeError("L1 provenance check failed: " + "; ".join(missing))
    return {
        "reused": True,
        "executed_by_this_run": False,
        "log": str(log_path.resolve()),
        "sha256": _sha256(log_path),
        "targets": list(L1_TARGETS),
        "max_parallel_actions": 2,
    }


def _write_json_atomic(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temp.replace(path)


def _worker(layer: str, args: argparse.Namespace) -> int:
    verify_root = _verify_root()
    sys.path.insert(0, str(verify_root))

    from layers.base import LayerContext
    from layers.registry import L2IntrospectLayer, L2Layer
    from spec import parse_task_file

    task = parse_task_file(_task_root() / "task.md")
    project_root = args.project_root.resolve()
    layer_args = SimpleNamespace(
        ue_root=args.ue_root.resolve(),
        test_filter=None,
        use_nullrhi=True,
        capture=False,
    )
    context = LayerContext(
        task=task,
        args=layer_args,
        project_path=project_root / "ThirdPerson.uproject",
        workdir_substrate=project_root,
        out_dir=args.out_dir.resolve(),
        manifest=SimpleNamespace(writable=(), asset_writable=()),
        substrate_src=project_root,
        requested_layers={"L2", "L2I"},
        submitted_files=(SUBMITTED_ASSETS if args.mode == "reference" else ()),
    )
    adapter = L2Layer() if layer == "L2" else L2IntrospectLayer()
    started = time.monotonic()
    result = adapter.run(context)
    if result.duration_seconds is None:
        result.duration_seconds = round(time.monotonic() - started, 2)
    _write_json_atomic(args.worker_result, result.to_dict())
    return 0


def _stop_worker(proc: subprocess.Popen[object]) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=10.0)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10.0)


def _run_one_layer(
    *,
    layer: str,
    args: argparse.Namespace,
    env: dict[str, str],
) -> tuple[dict[str, object] | None, str | None]:
    result_path = args.out_dir / f"{layer.lower()}_worker_result.json"
    stdout_path = args.out_dir / f"{layer.lower()}_worker_stdout.log"
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker-layer",
        layer,
        "--mode",
        args.mode,
        "--project-root",
        str(args.project_root),
        "--out-dir",
        str(args.out_dir),
        "--ue-root",
        str(args.ue_root),
        "--worker-result",
        str(result_path),
    ]
    with stdout_path.open("w", encoding="utf-8") as stdout:
        proc = subprocess.Popen(
            command,
            cwd=_repo_root(),
            env=env,
            stdout=stdout,
            stderr=subprocess.STDOUT,
        )
        try:
            exit_code = proc.wait(timeout=args.layer_timeout)
        except subprocess.TimeoutExpired:
            _stop_worker(proc)
            return None, (
                f"{layer} worker exceeded {args.layer_timeout:.0f}s; controller "
                "terminated the exact worker, closing its editor Job Object"
            )
    if exit_code != 0:
        return None, f"{layer} worker exited {exit_code}; see {stdout_path}"
    if not result_path.is_file():
        return None, f"{layer} worker emitted no result: {result_path}"
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"{layer} worker result unreadable: {exc}"
    if not isinstance(result, dict):
        return None, f"{layer} worker result is not a JSON object"
    return result, None


def _replace_assets(project_root: Path, sources: dict[str, Path]) -> None:
    for rel, source in sources.items():
        destination = project_root / Path(rel)
        temp = destination.with_suffix(destination.suffix + ".cbtmp")
        shutil.copy2(source, temp)
        temp.replace(destination)


def _controller(args: argparse.Namespace) -> int:
    project_root = args.project_root.resolve()
    out_dir = args.out_dir.resolve()
    if out_dir.exists():
        raise FileExistsError(f"out-dir must not already exist: {out_dir}")
    out_dir.mkdir(parents=True)
    args.project_root = project_root
    args.out_dir = out_dir
    args.ue_root = args.ue_root.resolve()

    project_file = project_root / "ThirdPerson.uproject"
    required_binaries = (
        project_root / "Binaries/Win64/UnrealEditor-ThirdPerson.dll",
        project_root / "Binaries/Win64/UnrealEditor-CraftBenchTests.dll",
        project_root / "Binaries/Win64/ThirdPerson.exe",
    )
    if not project_file.is_file():
        raise FileNotFoundError(f"project missing: {project_file}")
    for binary in required_binaries:
        if not binary.is_file():
            raise FileNotFoundError(f"reused L1 binary missing: {binary}")

    l1 = _validate_l1_log(args.l1_log.resolve(), project_root)
    reference_hashes = _reference_hashes()
    initial_hashes = _asset_hashes(project_root)
    if initial_hashes != reference_hashes:
        raise RuntimeError(
            "staged project is not the exact reference overlay; refusing to reuse it"
        )

    env = dict(os.environ)
    env["CRAFTBENCH_L1_MAX_PARALLEL"] = "2"
    env["CRAFTBENCH_GOVERN_RESOURCES"] = (
        "0" if args.no_govern_resources else "1"
    )

    restored_hashes: dict[str, str] | None = None
    overlay_hashes: dict[str, str] | None = None
    controller_errors: list[str] = []
    layers: dict[str, object] = {}
    reference_sources: dict[str, Path] = {}
    if args.mode == "empty":
        backup_dir = out_dir / "pre_empty_reference_backup"
        backup_dir.mkdir()
        for rel in SUBMITTED_ASSETS:
            source = project_root / Path(rel)
            backup = backup_dir / Path(rel).name
            shutil.copy2(source, backup)
            reference_sources[rel] = backup

    try:
        if args.mode == "empty":
            _replace_assets(project_root, _baseline_sources())
            overlay_hashes = _asset_hashes(project_root)
            if overlay_hashes == reference_hashes:
                raise RuntimeError("empty overlay unexpectedly equals the reference")
        for layer in ("L2", "L2I"):
            result, error = _run_one_layer(layer=layer, args=args, env=env)
            if error:
                controller_errors.append(error)
                break
            assert result is not None
            layers[layer] = result
    finally:
        if args.mode == "empty":
            _replace_assets(project_root, reference_sources)
            restored_hashes = _asset_hashes(project_root)
            if restored_hashes != initial_hashes:
                controller_errors.append(
                    "failed to restore the staged reference assets byte-for-byte"
                )

    if controller_errors:
        overall = "harness-error"
    elif any(
        isinstance(value, dict) and value.get("status") == "error"
        for value in layers.values()
    ):
        overall = "harness-error"
    elif set(layers) == {"L2", "L2I"} and all(
        isinstance(value, dict) and value.get("status") == "pass"
        for value in layers.values()
    ):
        overall = "pass"
    else:
        overall = "fail"

    l2_log = out_dir / "l2_pie.log"
    l2_log_text = (
        l2_log.read_text(encoding="utf-8", errors="replace")
        if l2_log.is_file()
        else ""
    )
    empty_token_present = EMPTY_NAMED_TOKEN in l2_log_text
    empty_discrimination_met = (
        args.mode == "empty"
        and overall == "fail"
        and empty_token_present
    )
    report = {
        "schema": "craftbench-task-local-behavior-recovery-v1",
        "task_id": TASK_ID,
        "mode": args.mode,
        "overall": overall,
        "certification": (
            "supplemental L2/L2I evidence; L1 was reused and pinned, not rerun"
        ),
        "project_root": str(project_root),
        "out_dir": str(out_dir),
        "l1": l1,
        "resources": {
            "governed": not args.no_govern_resources,
            "l2_memory_mb": (
                None
                if args.no_govern_resources
                else int(env.get("CRAFTBENCH_L2_MEM_MB", "8192"))
            ),
            "layer_timeout_seconds": args.layer_timeout,
        },
        "asset_state": {
            "initial_reference": initial_hashes,
            "empty_overlay": overlay_hashes,
            "restored_reference": restored_hashes,
        },
        "layers": layers,
        "discrimination": {
            "empty_named_token": EMPTY_NAMED_TOKEN,
            "empty_named_token_present": empty_token_present,
            "empty_expected_fail_observed": empty_discrimination_met,
        },
        "controller_errors": controller_errors,
    }
    _write_json_atomic(out_dir / "behavior_report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if overall == "pass" else (7 if overall == "harness-error" else 1)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("reference", "empty"), required=True)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--l1-log", type=Path)
    parser.add_argument("--ue-root", type=Path, default=_UE_ROOT)
    parser.add_argument("--layer-timeout", type=float, default=720.0)
    parser.add_argument(
        "--no-govern-resources",
        action="store_true",
        help="Diagnostic only: opt out of the normal 8 GB L2 Windows Job cap.",
    )
    parser.add_argument(
        "--worker-layer",
        choices=("L2", "L2I"),
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--worker-result", type=Path, help=argparse.SUPPRESS)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.worker_layer:
        if args.worker_result is None:
            raise SystemExit("--worker-result is required in worker mode")
        return _worker(args.worker_layer, args)
    if args.l1_log is None:
        raise SystemExit("--l1-log is required in controller mode")
    return _controller(args)


if __name__ == "__main__":
    raise SystemExit(main())

"""Disposable author/cold-read/harvest closure for the walker reference."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys

#: Engine root. Override with CB_UE_ROOT; defaults to Epic's standard install.
_UE_ROOT = Path(os.environ.get("CB_UE_ROOT", r"C:\Program Files\Epic Games\UE_5.8"))


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LIVE_PROJECT = REPO / "UE-projects" / "ThirdPerson"
LIVE_UPROJECT = LIVE_PROJECT / "ThirdPerson.uproject"
TASK_ID = "t3-both-walkers-yield-and-still-arrive"
LIVE_BASELINE = (LIVE_PROJECT / "Content" / "Tasks" / TASK_ID /
                 "BP_YieldingWalker.uasset")
ADMISSION_ASSET = (LIVE_PROJECT / "Content" / "__CraftBenchAdmission" /
                   TASK_ID / "BP_YieldingWalker_Admission.uasset")
MAP_DIR = LIVE_PROJECT / "Content" / "Maps" / TASK_ID
FINAL_MAP = MAP_DIR / "L_BothWalkersYield.umap"
ADMISSION_MAP = MAP_DIR / "L_BothWalkersYieldAdmission.umap"
REFERENCE_ROOT = HERE.parent / "reference"
REFERENCE_FILE = (REFERENCE_ROOT / "Content" / "Tasks" / TASK_ID /
                  "BP_YieldingWalker.uasset")
AUTHOR_SCRIPT = HERE / "author_reference.py"
READBACK_SCRIPT = HERE / "introspect_walker_yield.py"
EXPECTED = {
    LIVE_BASELINE: "804F3DBC239C376A7115EBEE627E1CF0018C5C5B8CB9194FABD00FD52AD8DE49",
    ADMISSION_ASSET: "7B196B18EDC6AAA6BBF16FBCBDC44291610320FFC927B324638B0CD7CC820B07",
    FINAL_MAP: "AE632FFEC1235BC95E9355FF0073C1684BB1461E2E72A15E67E1F01C3EC3784E",
    ADMISSION_MAP: "943A5C2A3E9F3FF63ED429990B89598A89E84D15251D585AB8936FA084314FF6",
}


class ClosureError(RuntimeError):
    """A fail-closed reference invariant failed."""


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def is_reparse(path):
    if path.is_symlink():
        return True
    attributes = getattr(path.lstat(), "st_file_attributes", 0)
    return bool(attributes & getattr(
        stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def require_plain(path):
    current = Path(os.path.abspath(os.fspath(path)))
    if not current.exists():
        raise ClosureError("required path missing: " + str(current))
    while True:
        if is_reparse(current):
            raise ClosureError("link/reparse rejected: " + str(current))
        if current.parent == current:
            return
        current = current.parent


def locked_vector():
    result = {}
    for path, expected in EXPECTED.items():
        require_plain(path)
        actual = sha256(path)
        if actual != expected:
            raise ClosureError("locked hash mismatch: %s" % path)
        result[str(path)] = {"size": path.stat().st_size, "sha256": actual}
    return result


def write_json(path, value):
    temporary = path.with_name(path.name + ".tmp")
    if temporary.exists() or os.path.lexists(temporary):
        raise ClosureError("stale JSON temporary: " + str(temporary))
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8")
    os.replace(temporary, path)


def run_editor(editor, project, script, log, stdout, environment, marker,
               timeout_seconds):
    command = [
        str(editor), str(project), "-run=pythonscript",
        "-script=" + str(script), "-unattended", "-nopause", "-nop4",
        "-nosplash", "-nosound", "-nullrhi", "-stdout",
        "-FullStdOutLogOutput", "-abslog=" + str(log),
    ]
    child_environment = os.environ.copy()
    child_environment.update(environment)
    with stdout.open("wb") as stream:
        process = subprocess.Popen(
            command, cwd=REPO, env=child_environment,
            stdout=stream, stderr=subprocess.STDOUT)
        try:
            exit_code = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                check=False, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, timeout=30)
            raise ClosureError("editor watchdog expired") from exc
    if exit_code != 0:
        raise ClosureError("editor exit=%d for %s" % (exit_code, script.name))
    text = log.read_text(encoding="utf-8", errors="replace")
    if marker not in text:
        raise ClosureError("terminal marker absent: " + marker)
    for forbidden in ("WALKER-YIELD-REFERENCE-FAILED",
                      "WALKER-YIELD-READBACK-FAILED", "LogPython: Error",
                      "Ensure condition failed", "Fatal error"):
        if forbidden in text:
            raise ClosureError("forbidden log token: " + forbidden)
    return {"argv": command, "exit_code": exit_code,
            "log_sha256": sha256(log), "stdout_sha256": sha256(stdout)}


def atomic_copy(source, destination, expected_hash):
    if sha256(source) != expected_hash:
        raise ClosureError("harvest source changed")
    if destination.exists() or os.path.lexists(destination):
        raise ClosureError("reference destination exists")
    destination.parent.mkdir(parents=True, exist_ok=False)
    temporary = destination.with_name(destination.name + ".copy-tmp")
    shutil.copy2(source, temporary)
    if is_reparse(temporary) or sha256(temporary) != expected_hash:
        raise ClosureError("temporary reference copy failed verification")
    os.replace(temporary, destination)


def close(editor, output, timeout_seconds):
    if output.exists() or os.path.lexists(output):
        raise ClosureError("fresh output exists: " + str(output))
    if REFERENCE_ROOT.exists() or os.path.lexists(REFERENCE_ROOT):
        raise ClosureError("reference must be absent")
    for path in (editor, LIVE_UPROJECT, AUTHOR_SCRIPT, READBACK_SCRIPT):
        require_plain(path)
    entry = locked_vector()
    output.mkdir(parents=True)
    logs = output / "logs"
    logs.mkdir()
    scratch = output / "scratch" / "ThirdPerson"
    state = {"schema_version": 1, "status": "running",
             "started_utc": datetime.now(timezone.utc).isoformat(),
             "entry": entry, "steps": {}}
    write_json(output / "closure.json", state)

    sys.path.insert(0, str(REPO / "tools" / "verify-single"))
    from run_task import copy_substrate_from_live
    copy_substrate_from_live(LIVE_PROJECT, scratch)
    scratch_project = scratch / "ThirdPerson.uproject"
    scratch_asset = (scratch / "Content" / "Tasks" / TASK_ID /
                     "BP_YieldingWalker.uasset")
    if not scratch_project.is_file() or sha256(scratch_asset) != \
            EXPECTED[LIVE_BASELINE]:
        raise ClosureError("scratch copy is incomplete or baseline changed")

    state["steps"]["author"] = run_editor(
        editor, scratch_project, AUTHOR_SCRIPT, logs / "author.log",
        logs / "author.stdout.log", {"CRAFTBENCH_REFERENCE_SCRATCH": "1"},
        "WALKER-YIELD-REFERENCE-SAVED", timeout_seconds)
    reference_hash = sha256(scratch_asset)
    if reference_hash == EXPECTED[LIVE_BASELINE]:
        raise ClosureError("reference author left baseline unchanged")

    state["steps"]["cold_readback"] = run_editor(
        editor, scratch_project, READBACK_SCRIPT, logs / "readback.log",
        logs / "readback.stdout.log",
        {"CRAFTBENCH_WALKER_YIELD_MODE": "reference",
         "CRAFTBENCH_WALKER_YIELD_KIND": "asset"},
        "WALKER-YIELD-ASSET-READBACK mode=reference PASS ",
        timeout_seconds)
    if sha256(scratch_asset) != reference_hash:
        raise ClosureError("cold readback changed scratch reference")
    if locked_vector() != entry:
        raise ClosureError("live retained inputs changed during closure")

    atomic_copy(scratch_asset, REFERENCE_FILE, reference_hash)
    if sha256(REFERENCE_FILE) != reference_hash:
        raise ClosureError("harvested reference hash mismatch")
    state["reference"] = {"path": str(REFERENCE_FILE),
                          "size": REFERENCE_FILE.stat().st_size,
                          "sha256": reference_hash}

    resolved_scratch = scratch.resolve()
    if resolved_scratch.parent != (output / "scratch").resolve() \
            or is_reparse(scratch):
        raise ClosureError("scratch cleanup target is not exact/plain")
    shutil.rmtree(scratch)
    if scratch.exists() or os.path.lexists(scratch):
        raise ClosureError("scratch cleanup incomplete")
    (output / "scratch").rmdir()
    state["scratch_removed"] = True
    state["status"] = "pass"
    state["completed_utc"] = datetime.now(timezone.utc).isoformat()
    write_json(output / "closure.json", state)
    print("WALKER-YIELD-REFERENCE-CLOSURE-PASS reference=1 cold=1 "
          "live_unchanged=1 scratch_removed=1 sha256=%s" % reference_hash)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ue-root", type=Path, default=_UE_ROOT)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--watchdog", type=int, default=720)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    editor_path = (args.ue_root / "Engine" / "Binaries" / "Win64" /
                   "UnrealEditor-Cmd.exe")
    try:
        close(editor_path.resolve(), args.output.resolve(), args.watchdog)
    except Exception as error:
        print("WALKER-YIELD-REFERENCE-CLOSURE-FAILED: %s" % error,
              file=sys.stderr)
        raise

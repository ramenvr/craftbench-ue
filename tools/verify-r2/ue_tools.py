"""Live UE read-only introspection tool for the R2 judge (anti-circular).

``editor_introspect`` runs a READ-ONLY, judge-authored Python query against the
judge's CLEAN workspace via stock ``UnrealEditor-Cmd -ExecutePythonScript`` — NOT
Aura's bridge (that would be circular: grading Aura with Aura). The judge's script
prints findings between markers; we strip UE's ``LogPython:`` line prefix and hand
back the captured text. The editor launch is an injectable seam so the unit tests
run with no UE install.

Self-contained: imports only the stdlib + json. No Aura, no MCP — keeps
tools/verify-r2 anti-circular (enforced by tests/test_anticircularity.py).
"""
from __future__ import annotations

import platform
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

_START = "CRAFTBENCH-JUDGE-INTROSPECT-START"
_END = "CRAFTBENCH-JUDGE-INTROSPECT-END"
# UE prefixes editor-Python stdout lines like "[2026...][  0]LogPython: <text>".
_LOGPY_RE = re.compile(r"^.*?LogPython:\s?", re.IGNORECASE)


def editor_binary(ue_root: Path) -> Path:
    """Path to UnrealEditor-Cmd for the host platform."""
    root = Path(ue_root)
    sysname = platform.system()
    if sysname == "Darwin":
        return root / "Engine/Binaries/Mac/UnrealEditor-Cmd"
    if sysname == "Windows":
        return root / "Engine/Binaries/Win64/UnrealEditor-Cmd.exe"
    return root / "Engine/Binaries/Linux/UnrealEditor-Cmd"


def _resolve_uproject(project_path: Path) -> Optional[Path]:
    p = Path(project_path)
    if p.is_file() and p.suffix == ".uproject":
        return p
    if p.is_dir():
        for up in sorted(p.glob("*.uproject")):
            return up
    return None


def extract_marked_output(raw: str) -> str:
    """Return the text the judge's script printed between the markers, with UE's
    per-line ``LogPython:`` prefix stripped. Empty string if no START marker."""
    lines = raw.splitlines()
    out, capturing = [], False
    for line in lines:
        if _START in line:
            capturing = True
            continue
        if _END in line:
            break
        if capturing:
            out.append(_LOGPY_RE.sub("", line))
    return "\n".join(out).strip()


def build_editor_introspect_tool(
    ue_root: Path,
    project_path: Path,
    *,
    run_editor: Optional[Callable[[list], Tuple[int, str]]] = None,
    timeout: float = 300.0,
) -> Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]]:
    """Return ``{"editor_introspect": callable}`` bound to a workspace project.

    The callable takes ``{"script": "<read-only python>"}``; the script should
    ``print()`` / ``unreal.log()`` whatever it wants to observe. ``run_editor`` is
    injected in tests; in production it shells out to UnrealEditor-Cmd headless.
    """
    binary = editor_binary(Path(ue_root))
    uproject = _resolve_uproject(Path(project_path))

    def _default_run(cmd: list) -> Tuple[int, str]:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, (proc.stdout or "") + "\n" + (proc.stderr or "")

    run = run_editor or _default_run

    def editor_introspect(args: Dict[str, Any]) -> Dict[str, Any]:
        script = str((args or {}).get("script", "")).strip()
        if not script:
            return {"error": "missing 'script' (read-only python to run in the editor)"}
        if uproject is None:
            return {"error": f"no .uproject under {project_path}"}
        wrapped = (
            "import unreal\n"
            f"print('{_START}')\n"
            f"{script}\n"
            f"print('{_END}')\n"
        )
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(wrapped)
            spath = f.name
        cmd = [
            str(binary), str(uproject),
            f"-ExecutePythonScript={spath}",
            "-nullrhi", "-unattended", "-nopause", "-nosplash", "-NoSound",
        ]
        try:
            rc, raw = run(cmd)
        except Exception as e:  # noqa: BLE001 — surface to the judge, never crash the run
            return {"error": f"editor launch failed: {e}"}
        output = extract_marked_output(raw)
        res: Dict[str, Any] = {"output": output, "returncode": rc}
        if not output:
            res["note"] = "no marked output — the script may have errored before printing"
        return res

    return {"editor_introspect": editor_introspect}

"""Blueprint / .uasset deliverable capture for --submission-from-project runs.

BP-heavy tasks (e.g. gp-gas-launch solved as Blueprints) produce ``.uasset``
deliverables that the source-tree-only extraction misses for two reasons:

  1. **They live in memory.** Aura's sub-agents (bp_agent / material_agent / …)
     mutate in-memory packages; nothing hits disk until something saves. So we
     first run a headless ``save_all_dirty`` editor-Python pass (``save_dirty.py``)
     to flush every dirty content package to ``Content/``.

  2. **They live across manifest-approved asset roots.** Sub-agents author
     Blueprints under ``Content/Blueprints/``, ``Content/Abilities/``, and
     task-owned Game Feature plugin ``Content/`` trees — not only under the
     writable ``Content/Tasks/`` prefix that
     ``extract_writable_subset_from_project`` sweeps. So we walk the existing
     directory portions of every approved prefix for ``.uasset`` / ``.umap``,
     still honoring manifest deny prefixes so verifier-owned maps stay out.

Both pieces are split out here so they are unit-testable WITHOUT a UE install:
the save-dirty editor invocation is an injectable seam, and the asset sweep is
pure filesystem logic.

Anti-circularity: the save step runs through CraftBench's OWN headless editor +
stock UE Python, never through Aura's MCP tools.
"""
from __future__ import annotations

import os
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

# Asset file extensions we capture from manifest-approved asset roots in
# addition to the writable source tree. ``.umap`` is included so a NEW
# agent-authored map under a writable prefix is captured — but Content/Maps/
# stays denied, so verifier-owned task maps never flow into the submission.
ASSET_EXTENSIONS = (".uasset", ".umap")

SAVE_JSON_END = "CRAFTBENCH-SAVE-DIRTY-JSON-END"

_HERE = Path(__file__).resolve().parent
DEFAULT_SAVE_SCRIPT = _HERE / "introspect" / "save_all_dirty.py"


@dataclass
class SaveDirtyResult:
    status: str  # "ok" | "error" | "skipped"
    log_path: Optional[Path]
    exit_code: int
    duration_seconds: float
    notes: List[str] = field(default_factory=list)


def save_all_dirty_assets(
    *,
    ue_root: Path,
    project_path: Path,
    log_path: Path,
    save_script: Path = DEFAULT_SAVE_SCRIPT,
    timeout_seconds: float = 300.0,
    use_nullrhi: bool = True,
    _editor_binary: Optional[Callable[[Path], Path]] = None,
    _run_editor: Optional[Callable] = None,
) -> SaveDirtyResult:
    """Flush every dirty content package to disk via headless editor-Python.

    Runs ``save_all_dirty.py`` through ``UnrealEditor-Cmd -ExecutePythonScript=``
    (the same channel as L2-introspect). Best-effort: any failure returns a
    non-fatal "error" status so capture proceeds against whatever IS on disk.

    ``_editor_binary`` / ``_run_editor`` are injectable seams so this is fully
    unit-testable without a UE install.
    """
    # Lazy import so the module imports cleanly on machines without the layers
    # package present on sys.path during isolated unit tests.
    if _editor_binary is None or _run_editor is None:
        from layers.l2_pie import editor_binary as _default_editor_binary
        from layers.l2_pie import run_editor_with_marker_kill as _default_run_editor

        resolve_editor = _editor_binary or _default_editor_binary
        run_editor = _run_editor or _default_run_editor
    else:
        resolve_editor = _editor_binary
        run_editor = _run_editor

    notes: List[str] = []
    editor = resolve_editor(ue_root)
    if not editor.exists():
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(
            f"save-all-dirty SKIPPED: editor not found at {editor}\n", encoding="utf-8"
        )
        return SaveDirtyResult(
            status="error", log_path=log_path, exit_code=127,
            duration_seconds=0.0, notes=[f"editor binary missing at {editor}"],
        )
    if not save_script.exists():
        return SaveDirtyResult(
            status="error", log_path=None, exit_code=2,
            duration_seconds=0.0, notes=[f"save script missing at {save_script}"],
        )

    cmd: List[str] = [
        str(editor),
        str(project_path),
        f"-ExecutePythonScript={save_script}",
        "-unattended", "-nopause", "-nosplash", "-nosound",
        "-log", "-stdout", "-fullstdoutlogoutput",
    ]
    if use_nullrhi:
        cmd.insert(2, "-nullrhi")
    notes.append("cmd: " + " ".join(cmd))

    log_path.parent.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    try:
        exit_code, _killed = run_editor(
            cmd=cmd, env=None, log_path=log_path,
            timeout_seconds=timeout_seconds,
            extra_markers=(SAVE_JSON_END,),
        )
    except Exception as e:  # noqa: BLE001 — best-effort; never block capture
        return SaveDirtyResult(
            status="error", log_path=log_path, exit_code=124,
            duration_seconds=time.monotonic() - start,
            notes=notes + [f"editor run failed: {e}"],
        )
    return SaveDirtyResult(
        status="ok", log_path=log_path, exit_code=exit_code,
        duration_seconds=time.monotonic() - start, notes=notes,
    )


def _matches_prefix(rel: str, prefix: str) -> bool:
    """Exact-path-or-descendant prefix match (mirrors sandbox._matches_prefix)."""
    if not prefix:
        return False
    p = prefix.rstrip("/")
    return rel == p or rel.startswith(p + "/")


def _normalize_prefix(prefix) -> Optional[str]:
    """Return a safe project-relative POSIX prefix, or None when it escapes."""
    raw = str(prefix).strip().replace("\\", "/")
    if not raw or raw.startswith("/") or re.match(r"^[A-Za-z]:", raw):
        return None
    parts = [part for part in raw.split("/") if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        return None
    return "/".join(parts)


def _is_below(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _is_link_like(path: Path) -> bool:
    """True for symlinks, NTFS junctions, and any other reparse point."""
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    if is_junction is not None and is_junction():
        return True
    try:
        return bool(getattr(os.lstat(path), "st_reparse_tag", 0))
    except OSError:
        return False


def _plain_chain(root: Path, target: Path) -> bool:
    """Whether target is lexically below root with no link-like component."""
    root = Path(os.path.abspath(root))
    target = Path(os.path.abspath(target))
    try:
        rel = target.relative_to(root)
    except ValueError:
        return False
    current = root
    if os.path.lexists(str(current)) and _is_link_like(current):
        return False
    for part in rel.parts:
        current /= part
        if os.path.lexists(str(current)) and _is_link_like(current):
            return False
    return True


def _capture_roots(project_root: Path, allow_prefixes) -> List[Path]:
    """Deduplicated longest-existing directory roots for manifest prefixes."""
    project = Path(os.path.abspath(project_root))
    if not project.is_dir() or not _plain_chain(project, project):
        return []
    project_resolved = project.resolve()
    candidates: List[Path] = []
    for raw_prefix in allow_prefixes:
        norm = _normalize_prefix(raw_prefix)
        if norm is None:
            continue
        raw_text = str(raw_prefix).strip().replace("\\", "/")
        candidate = project.joinpath(*norm.split("/"))
        file_shaped = (not raw_text.endswith("/") and bool(candidate.suffix))
        if candidate.is_file() or (not candidate.exists() and file_shaped):
            candidate = candidate.parent
        while candidate != project and not candidate.is_dir():
            candidate = candidate.parent
        if not candidate.is_dir():
            continue
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if (not _plain_chain(project, candidate)
                or not _is_below(resolved, project_resolved)):
            continue
        candidates.append(candidate)

    # Parent roots subsume child roots. Sort before folding so the walk order is
    # deterministic and every filesystem subtree is visited at most once.
    roots: List[Path] = []
    for candidate in sorted(set(candidates), key=lambda p: (len(p.parts), str(p))):
        if any(_is_below(candidate, parent) for parent in roots):
            continue
        roots.append(candidate)
    return roots


def capture_content_assets(
    *,
    project_root: Path,
    out_dir: Path,
    deny_prefixes,
    allow_prefixes=None,
    extensions=ASSET_EXTENSIONS,
) -> List[str]:
    """Copy manifest-approved asset files below ``project_root`` into ``out_dir``,
    preserving the project-relative layout — but ONLY those the sandbox would
    accept: under an ``allow_prefixes`` entry AND not under a ``deny_prefixes``
    entry (deny wins). This keeps capture and the downstream sandbox scan in
    agreement, so every captured asset survives ``scan_submission`` instead of
    becoming a violation (exit 4).

    ``allow_prefixes`` is the manifest's ``asset_writable`` (+ ``writable``)
    set. When None/empty, NOTHING is captured (the BP path is opt-in via the
    manifest). ``Content/Maps/`` is excluded because it is a deny prefix.

    Returns the list of captured project-relative paths (POSIX). Intermediate /
    generated dirs are skipped. Idempotent: re-copying overwrites in place.
    """
    captured: List[str] = []
    allow = tuple(allow_prefixes or ())
    if not allow:
        return captured
    project_root = Path(os.path.abspath(project_root))
    if not project_root.is_dir() or not _plain_chain(project_root, project_root):
        return captured
    project_resolved = project_root.resolve()
    allow = tuple(
        norm for norm in (_normalize_prefix(p) for p in allow)
        if norm is not None
    )
    deny = tuple(
        norm for norm in (_normalize_prefix(p) for p in (deny_prefixes or ()))
        if norm is not None
    )
    if not allow:
        return captured
    skip_segments = {"Intermediate", "DerivedDataCache", "Saved"}
    allowed_extensions = {str(ext).lower() for ext in extensions}
    seen = set()
    for walk_root in _capture_roots(project_root, allow):
        if not _plain_chain(project_root, walk_root):
            continue
        for dirpath, dirnames, filenames in os.walk(walk_root, followlinks=False):
            here = Path(dirpath)
            kept_dirs = []
            for name in sorted(dirnames):
                child = here / name
                try:
                    resolved = child.resolve()
                except OSError:
                    continue
                if (name in skip_segments or _is_link_like(child)
                        or not _plain_chain(project_root, child)
                        or not _is_below(resolved, project_resolved)):
                    continue
                kept_dirs.append(name)
            dirnames[:] = kept_dirs

            for name in sorted(filenames):
                f = here / name
                if f.suffix.lower() not in allowed_extensions:
                    continue
                if _is_link_like(f) or not _plain_chain(project_root, f):
                    continue
                try:
                    resolved_file = f.resolve()
                except OSError:
                    continue
                if (not _is_below(resolved_file, project_resolved)
                        or not f.is_file()):
                    continue
                rel = f.relative_to(project_root).as_posix()
                if rel in seen:
                    continue
                if any(seg in skip_segments for seg in rel.split("/")):
                    continue
                if any(_matches_prefix(rel, d) for d in deny):
                    continue
                if not any(_matches_prefix(rel, a) for a in allow):
                    continue
                dst = out_dir / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dst)
                captured.append(rel)
                seen.add(rel)
    return captured

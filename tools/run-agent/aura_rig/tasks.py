"""Task discovery + parsing + resolution for the CraftBench task tree.

A *set* is a subdirectory of ``tasks/`` (plus the root itself, surfaced as ``root``);
a *task* is either the legacy flat form ``tasks/<set>/<id>.md`` or the folder form
``tasks/<set>/<id>/task.md`` (the 2026-07 layout: the folder co-locates the spec with
its ``reference/`` solution, ``discrimination/`` variants, and optional ``ue-config/``
fragments). Expansion is pure **file-drop** — drop a folder (or a ``.md``) into a set
dir for a new task, ``mkdir`` for a new set; everything here auto-discovers it, no
registry/config. When both shapes exist for one id in one set, the FOLDER wins.

Pure over the filesystem (no subprocess, no network) so it is unit-testable and is the
single source of truth shared by the eval task-resolver (run_graded), the interactive
picker (taskpicker / ``cb tasks``), and CI (``python -m aura_rig.tasks resolve <id>``).
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set

# THE single task-spec parser lives in tools/verify-single (a non-importable
# dir name) — bridge it onto sys.path, same pattern as graded_scratch.py.
_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE.parents[0]), str(_HERE.parents[1] / "verify-single")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import spec as _taskspec  # noqa: E402  (tools/verify-single/spec.py)

# Non-task docs that live alongside specs in the set dirs. ``task.md`` guards
# against a folder-form spec misplaced DIRECTLY in a set dir (it belongs one
# level down, at tasks/<set>/<id>/task.md).
_SKIP = {"README.md", "CATALOG.md", "task.md"}

# The spec filename inside a folder-form task dir.
_SPEC_NAME = "task.md"

# Legacy homes for per-task artifacts (pre-2026-07 layout); the folder-local
# ``reference/`` / ``discrimination/`` entries supersede these when present.
_LEGACY_REFERENCE_ROOT = ("tests", "reference-solutions")
_LEGACY_DISCRIMINATION_ROOT = ("tests", "discrimination")


@dataclass
class TaskInfo:
    """One task spec, with the bits the picker shows. ``id`` is the bare task id (the
    value ``cb eval --task`` takes); ``set_name`` is its set (``root`` or a subdir)."""

    id: str
    set_name: str
    path: Path
    title: str = ""
    concept: str = ""
    layers: str = ""
    prompt_preview: str = ""


def task_id_for(path: Path) -> str:
    """The bare task id a spec path denotes: the parent-dir name for the folder
    form (``.../<id>/task.md``), else the file stem (``.../<id>.md``)."""
    p = Path(path)
    return p.parent.name if p.name == _SPEC_NAME else p.stem


def bare_id(task_id: str) -> str:
    """Strip an optional ``set/`` qualifier (tolerating Windows backslashes):
    ``bp-g2/gp-x`` -> ``gp-x``. Bare ids pass through unchanged."""
    return (task_id or "").replace("\\", "/").rsplit("/", 1)[-1]


def _section(text: str, heading: str) -> str:
    """Body under an H2 ``## <heading>`` up to the next H1/H2 (or EOF), trimmed.

    Case-sensitive on the heading text — the task-spec H2 headings are normative
    (the same join-key the verifier's parser uses)."""
    m = re.search(
        rf"^## {re.escape(heading)}\s*$(.*?)(?=^#{{1,2}} |\Z)",
        text, re.MULTILINE | re.DOTALL,
    )
    return m.group(1).strip() if m else ""


def _first_line(s: str) -> str:
    """First non-empty content line (bullet/marker stripped) — a compact summary."""
    for ln in s.splitlines():
        ln = ln.strip().lstrip("-*").strip()
        if ln:
            return ln
    return ""


def parse_task(path: Path, set_name: str) -> TaskInfo:
    """Parse a task ``.md`` into a :class:`TaskInfo` (best-effort; never raises on a
    malformed spec — missing sections just yield empty fields)."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    tid = task_id_for(path)
    h1 = re.search(r"^# (.+)$", text, re.MULTILINE)
    title = h1.group(1).strip() if h1 else tid
    concept = _first_line(_section(text, "Primary concept"))
    # Layers come from THE single spec parser (front matter, the unified
    # "## Verifier layers" block, or the legacy "## Verifier layers used"
    # heading all resolve there — no hardcoded-heading drift here).
    try:
        layers = ", ".join(_taskspec.parse_task_file(path).layers)
    except Exception:
        layers = ""  # malformed/unreadable spec: best-effort empty field
    prompt = _section(text, "Prompt given to the agent")
    preview = " ".join(prompt.split())[:200]
    return TaskInfo(id=tid, set_name=set_name, path=path, title=title,
                    concept=concept, layers=layers, prompt_preview=preview)


def _is_task_md(p: Path) -> bool:
    return p.suffix == ".md" and p.name not in _SKIP


def _set_specs(set_dir: Path) -> List[Path]:
    """All spec paths in one set dir, both shapes, sorted by task id.

    Folder form (``<id>/task.md``) wins over a sibling legacy ``<id>.md``."""
    by_id: Dict[str, Path] = {}
    for p in set_dir.glob("*.md"):
        if _is_task_md(p):
            by_id[p.stem] = p
    for d in set_dir.iterdir():
        spec = d / _SPEC_NAME
        if d.is_dir() and spec.is_file():
            by_id[d.name] = spec  # folder wins over a same-id sibling .md
    return [by_id[k] for k in sorted(by_id)]


def discover(repo: Path) -> "Dict[str, List[TaskInfo]]":
    """Map ``set_name -> sorted [TaskInfo]``. Root ``tasks/*.md`` go under ``root``;
    each subdir containing specs (either shape) is its own set. Order: ``root``
    first, then sets alphabetically; tasks sorted by id. Empty sets are omitted.

    A dir directly under ``tasks/`` is always a SET dir, never a root task folder."""
    tasks_dir = repo / "tasks"
    out: "Dict[str, List[TaskInfo]]" = {}
    if not tasks_dir.is_dir():
        return out
    root = sorted((p for p in tasks_dir.glob("*.md") if _is_task_md(p)),
                  key=lambda p: p.stem)
    if root:
        out["root"] = [parse_task(p, "root") for p in root]
    for d in sorted((p for p in tasks_dir.iterdir() if p.is_dir()),
                    key=lambda p: p.name):
        specs = _set_specs(d)
        if specs:
            out[d.name] = [parse_task(p, d.name) for p in specs]
    return out


def resolve_task_candidates(repo: Path, task_id: str) -> List[Path]:
    """Every spec path a task id could denote, deduped per set (folder form wins
    within a set), sorted. A set-qualified id yields at most one candidate; a bare
    id may yield several (one per set that defines it) — the caller decides how to
    disambiguate (or errors, listing these)."""
    tasks_dir = repo / "tasks"
    tid = task_id[:-3] if task_id.endswith(".md") else task_id
    tid = tid.replace("\\", "/").strip("/")
    if not tid or not tasks_dir.is_dir():
        return []
    if "/" in tid:                                    # set-qualified "set/id"
        set_name, bare = tid.rsplit("/", 1)
        for p in (tasks_dir / set_name / bare / _SPEC_NAME,
                  tasks_dir / set_name / f"{bare}.md"):
            if p.is_file():
                return [p]
        return []
    by_set: Dict[str, Path] = {}
    root = tasks_dir / f"{tid}.md"
    if root.is_file():
        by_set[""] = root
    for p in tasks_dir.glob(f"*/{tid}.md"):           # legacy flat, first...
        by_set.setdefault(p.parent.name, p)
    for p in tasks_dir.glob(f"*/{tid}/{_SPEC_NAME}"):  # ...then folder form wins
        by_set[p.parent.parent.name] = p
    return [by_set[k] for k in sorted(by_set)]


def resolve_task_path(repo: Path, task_id: str) -> Optional[Path]:
    """Find a task spec by id, either layout. Accepts ``set/id`` (set-qualified;
    always unambiguous), else tries the repo ``tasks/<id>.md`` (root) first, then a
    UNIQUE set match (``tasks/*/<id>/task.md`` or ``tasks/*/<id>.md``). Returns
    ``None`` if missing or AMBIGUOUS (>1 set match → caller should ask for a
    set-qualified id; use :func:`resolve_task_candidates` to list the options)."""
    cands = resolve_task_candidates(repo, task_id)
    if len(cands) == 1:
        return cands[0]
    for p in cands:                                    # root wins (resolves a dup)
        if p.parent == repo / "tasks":
            return p
    return None


def qualified_id(repo: Path, spec_path: Path) -> str:
    """The set-qualified id (``set/id``, or the bare id for a root task) for a
    spec path returned by :func:`resolve_task_candidates` — either layout."""
    rel = Path(spec_path).relative_to(repo / "tasks")
    tid = task_id_for(spec_path)
    return tid if len(rel.parts) == 1 else f"{rel.parts[0]}/{tid}"


def known_task_ids(repo: Path) -> List[str]:
    """Every id ``--task`` accepts, in preferred DISPLAY form: the bare id when
    :func:`resolve_task_path` would accept it bare (unique across sets, or a
    root task — root wins a duplicate), else the set-qualified ``set/id``.
    Sorted + deduped — the suggestion pool for :func:`suggest_task_ids`."""
    tasks_dir = repo / "tasks"
    if not tasks_dir.is_dir():
        return []
    pairs: List[tuple] = []  # (set_name — "" for root, bare id)
    for p in tasks_dir.glob("*.md"):
        if _is_task_md(p):
            pairs.append(("", p.stem))
    for d in sorted(p for p in tasks_dir.iterdir() if p.is_dir()):
        pairs.extend((d.name, task_id_for(s)) for s in _set_specs(d))
    dupes = {b for _, b in pairs
             if sum(1 for _, other in pairs if other == b) > 1}
    out = {bare if (not set_name or bare not in dupes) else f"{set_name}/{bare}"
           for set_name, bare in pairs}
    return sorted(out)


def bare_task_ids(repo: Path) -> "Set[str]":
    """Every BARE task id in the tree, lowercased — the id that names a
    per-task UE folder (``Content/Tasks/<id>/``, ``Source/<module>/Tasks/<id>/``).

    Sibling of :func:`known_task_ids`, which answers "what may an operator
    TYPE" (display form, set-qualified on a collision). This one answers "what
    ids exist on disk", the question :mod:`aura_rig.task_scope` asks to decide
    whether a swept path belongs to ANOTHER task — so it must never be
    hand-coded and must never be set-qualified.

    Derived from the same spec layout every other resolver uses (``_set_specs``
    → both spec shapes, folder form winning), plus the front-matter ``id:``
    where the single spec parser can read it: a spec whose declared id differs
    from its folder name owns BOTH names, and over-inclusion here only ever
    means one more path is recognised as somebody's task folder."""
    tasks_dir = repo / "tasks"
    if not tasks_dir.is_dir():
        return set()
    specs: List[Path] = [p for p in tasks_dir.glob("*.md") if _is_task_md(p)]
    for d in sorted(p for p in tasks_dir.iterdir() if p.is_dir()):
        specs.extend(_set_specs(d))
    out: "Set[str]" = set()
    for s in specs:
        out.add(task_id_for(s).lower())
        try:
            declared = _taskspec.parse_task_file(s).id
        except Exception:      # malformed/unreadable spec: the path id stands
            continue
        if declared:
            out.add(str(declared).lower())
    return out


def suggest_task_ids(repo: Path, task_id: str, n: int = 3) -> List[str]:
    """Close-match suggestions for an id that failed to resolve — the o-for-0
    typo class (``to-sanity-…`` -> ``t0-sanity-…``). Matches against the known
    display ids; a set-qualified input falls back to matching its bare tail."""
    import difflib
    tid = (task_id or "").replace("\\", "/").strip("/")
    if tid.endswith(".md"):
        tid = tid[:-3]
    known = known_task_ids(repo)
    hits = difflib.get_close_matches(tid, known, n=n, cutoff=0.6)
    if not hits and "/" in tid:
        hits = difflib.get_close_matches(tid.rsplit("/", 1)[-1], known,
                                         n=n, cutoff=0.6)
    return hits


def resolution_error(repo: Path, task_id: str) -> str:
    """THE human message for a failed :func:`resolve_task_path` — every surface
    (cb eval routes, run_graded, the resolve CLI) prints this one, so the hint
    text can't go stale per-caller again (the retired ``concept-1/`` example
    outlived its set by two weeks). Ambiguous ids list their set-qualified
    candidates; missing ids get did-you-mean close matches + the browse pointer."""
    cands = resolve_task_candidates(repo, task_id)
    if cands:
        opts = "".join(
            f"\n  {qualified_id(repo, c)}  ({c.relative_to(repo).as_posix()})"
            for c in cands)
        return (f"ambiguous task id under tasks/: {task_id!r} — use a "
                f"set-qualified id:{opts}")
    sugg = suggest_task_ids(repo, task_id)
    hint = ("did you mean " + " or ".join(repr(s) for s in sugg) + "? "
            if sugg else "")
    return (f"task not found under tasks/: {task_id!r} — {hint}"
            "browse ids with `cb tasks`, or use a set-qualified '<set>/<id>'.")


def asset_deliverable_task(spec_path: Path) -> bool:
    """True iff the task's deliverable includes an in-editor-authored asset —
    derived from the spec's OWN layer declaration via THE single parser
    (``L2I`` structurally introspects a submitted ``.uasset``; the parser
    enforces that L2I always carries an ``introspect:`` list), never from
    task-id naming conventions like the ``-bp`` suffix.

    Why callers care: a BASELINE backend (claude-p / openrouter — generic file
    tools, no editor) cannot author a ``.uasset``, so on such a task it is a
    guaranteed harness-reason FAIL per the certified-lane contract — a matrix
    should refuse that cell before spending on it. Unreadable/malformed specs
    return False: the resolver / reference gate reports those with a better
    message than this predicate could."""
    try:
        return "L2I" in _taskspec.parse_task_file(Path(spec_path)).layers
    except Exception:
        return False


def task_dir(spec_path: Path) -> Optional[Path]:
    """The task's own folder for a folder-form spec (``.../<id>/task.md`` ->
    ``.../<id>/``); ``None`` for a legacy flat spec."""
    p = Path(spec_path)
    return p.parent if p.name == _SPEC_NAME else None


def _task_artifact_dir(repo: Path, task_id: str, local_name: str,
                       legacy_root: tuple) -> Optional[Path]:
    """Folder-local ``<task dir>/<local_name>/`` when it exists, else the legacy
    ``<legacy_root>/<bare id>/`` when THAT exists, else ``None``."""
    spec = resolve_task_path(repo, task_id)
    if spec is not None:
        d = task_dir(spec)
        if d is not None and (d / local_name).is_dir():
            return d / local_name
    legacy = repo.joinpath(*legacy_root) / bare_id(task_id)
    return legacy if legacy.is_dir() else None


def reference_dir(repo: Path, task_id: str) -> Optional[Path]:
    """The task's reference solution: folder-local ``reference/`` first, legacy
    ``tests/reference-solutions/<bare id>/`` fallback; ``None`` when neither exists."""
    return _task_artifact_dir(repo, task_id, "reference", _LEGACY_REFERENCE_ROOT)


def discrimination_dir(repo: Path, task_id: str) -> Optional[Path]:
    """The task's discrimination variants: folder-local ``discrimination/`` first,
    legacy ``tests/discrimination/<bare id>/`` fallback; ``None`` when neither."""
    return _task_artifact_dir(repo, task_id, "discrimination",
                              _LEGACY_DISCRIMINATION_ROOT)


def _main(argv: List[str]) -> int:
    """``python -m aura_rig.tasks resolve <id> [--repo <path>]`` — print the spec
    path (exit 0), or list candidates / report missing on stderr (exit 1). Used by
    CI to map ids to paths without duplicating the resolution rules in bash."""
    import argparse
    import sys as _sys

    ap = argparse.ArgumentParser(prog="python -m aura_rig.tasks")
    sub = ap.add_subparsers(dest="cmd", required=True)
    rp = sub.add_parser("resolve", help="print the spec path for a task id")
    rp.add_argument("task_id")
    rp.add_argument("--repo", default=None,
                    help="repo root (default: auto-detect from this file)")
    ns = ap.parse_args(argv)
    repo = Path(ns.repo) if ns.repo else Path(__file__).resolve().parents[3]
    p = resolve_task_path(repo, ns.task_id)
    if p is not None:
        print(p.as_posix())
        return 0
    print(resolution_error(repo, ns.task_id), file=_sys.stderr)
    return 1


if __name__ == "__main__":  # pragma: no cover
    import sys

    raise SystemExit(_main(sys.argv[1:]))

"""tools/dashboard/web/launcher.py — launch a standard run from the dashboard.

Feature #3 ("LAUNCH-A-RUN", the Agent-Loop closure): the read-only fleet
dashboard gets a single write action — *kick off one ``(task × model)`` run via
the canonical harness* (``tools/run-agent/run.py``). When ``run.py`` finishes it
drops a ``runs/<id>/result.json`` that ``collect()`` already reads, so the new
run shows up in the LIVE matrix without any extra plumbing — that is the closure.

Design constraints (all non-negotiable, see the spawning task brief):

  * **Argv list, never a shell.** The subprocess is always a list of strings
    handed straight to ``subprocess.Popen`` with the default ``shell=False``. No
    user-supplied string is ever interpolated into a shell command. This is the
    primary injection defense.
  * **Validate before spawn.** ``task_id`` (bare or set-qualified ``<set>/<id>``)
    must resolve to a real task spec on disk — flat ``tasks/[<set>/]<id>.md`` or
    folder-form ``tasks/<set>/<id>/task.md`` (rejects traversal / made-up ids);
    ``model`` must match the strict product-slug regex below (rejects anything
    not in the known backend set). A rejected request raises ``ValueError``
    *before* any process starts.
  * **Background + tracked.** Jobs run detached via ``Popen``; a ``JobManager``
    tracks lifecycle (``queued`` → ``running`` → ``done`` / ``failed``) and
    captures the combined stdout/stderr log so the UI can stream it.
  * **Injectable runner command.** The builder that turns ``(task, model, …)``
    into the argv list is a constructor parameter. Production uses the default
    (targets ``run.py``); tests inject a fake echo command so the suite never
    spawns UnrealEditor or ``run.py`` for real.

This module lives web-side and may import stdlib only — it deliberately does NOT
import fastapi/textual, keeping it usable from any front-end (the data layer,
``collect.py`` / ``model.py``, stays pure-stdlib and untouched by this file).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

# ---------------------------------------------------------------------------
# Validation surface
# ---------------------------------------------------------------------------

# The settled product-slug grammar. It mirrors the branches of
# ``tools/run-agent/adapters/registry.py::make_adapter`` that a clone of THIS
# repository can actually drive — claude-p (:485), unreal-mcp (:514), bare
# (:531) and openrouter (:546). A bare backend with no model is NOT accepted
# here: the dashboard always launches a concrete (backend:model) operating point.
#
# The model component admits '/' because two of the four backends REQUIRE it:
# ``bare:<provider/model>`` and ``openrouter:<provider/model>`` take OpenRouter
# ids, and per ``registry.py::is_openrouter_model_id`` (:216) the slash IS the
# routing decision. Every '/'-separated component still has to match the strict
# alphabet and may not start with '.', so no shell metacharacter, whitespace or
# traversal payload survives — the model is argv-only anyway, never path-joined.
#
# Anchored with ``\Z``, not ``$``: ``$`` also matches just before a trailing
# newline, so ``"claude-p:opus\n"`` passed the old gate and reached argv intact.
_MODEL_PART_RE = r"(?!\.)[A-Za-z0-9._-]+"
MODEL_SLUG_RE = re.compile(
    rf"^(bare|claude-p|openrouter|unreal-mcp):{_MODEL_PART_RE}(?:/{_MODEL_PART_RE})*\Z"
)

# Backends the adapter registry still KNOWS but that this repository cannot
# launch. Refused BY NAME, in the same voice as ``registry.py::_REMOVED_BACKENDS``
# (:412): a slug that used to work should be answered with what happened to it,
# not with a regex miss that reads like a typo. aura-mcp is the special case —
# it is dispatchable and documented (registry.py:490) but its MCP servers ship
# with Aura's private UE plugin, so a launch from a public clone cannot succeed.
_UNLAUNCHABLE_BACKENDS = {
    "aura-mcp": (
        "disclosed but not reproducible from this repository — its two MCP "
        "servers ship with Aura's private UE plugin, which is not here"
    ),
    "aura-product": "removed with the private product surface",
    "aura-agent": "removed with the private product surface",
    "aura-baseline": "removed with the private product surface",
    "aura-mcp-bridge": "removed with the private product surface",
}

# One task-id path COMPONENT: no separators, no '..'. A launchable id is either
# a bare id (``gp-x``) or a set-qualified ``<set>/<id>`` (max two components);
# EVERY '/'-separated component must match this alphabet, which refuses
# traversal payloads (``../``, ``\``, ``%2F``, shell metacharacters) before any
# path resolution. A leading '.' is forbidden so '..' and dotfiles can't sneak
# through.
TASK_ID_RE = re.compile(r"^(?!\.)[A-Za-z0-9._-]+$")

# Non-task docs that live in the tasks/ tree (never launchable). ``task.md``
# also guards a folder-form spec misplaced directly in a set dir — the real
# folder-form spec lives one level down, at tasks/<set>/<id>/task.md.
_TASK_SKIP_NAMES = ("README.md", "CATALOG.md", "task.md")

# The spec filename inside a folder-form task dir (tasks/<set>/<id>/task.md).
_TASK_SPEC_NAME = "task.md"

# Known product backends, surfaced to the UI so it can offer sensible model
# slugs without the user hand-typing a backend. These are the four RUNNABLE
# make_adapter() branches (the registry also knows aura-mcp, which is refused
# above); the regex is the authoritative gate.
_KNOWN_BACKENDS = ("claude-p", "unreal-mcp", "bare", "openrouter")

# A small, opinionated default set of (backend:model) operating points the UI
# can present as a dropdown. NOT a whitelist — any slug matching MODEL_SLUG_RE
# is accepted; this is just a convenience seed of the common points.
_DEFAULT_MODEL_SLUGS = (
    "claude-p:claude-sonnet-5",
    "claude-p:claude-opus-5",
    "unreal-mcp:claude-sonnet-5",
    "openrouter:openai/gpt-5.6-terra",
    "openrouter:deepseek/deepseek-v4-pro-0813",
    "bare:deepseek/deepseek-v4-pro-0813",
)

# The canonical harness the default builder targets. Resolved relative to the
# repo root so the spawned process finds it regardless of the dashboard's CWD.
_RUN_AGENT_REL = "tools/run-agent/run.py"


def _repo_root_default() -> Path:
    # tools/dashboard/web/launcher.py -> repo root is parents[3].
    return Path(__file__).resolve().parents[3]


def available_tasks(repo_root: Optional[Path] = None) -> List[str]:
    """Return the sorted launchable task ids found on disk, BOTH layouts.

    Root specs (``tasks/<id>.md``) list as the bare stem, matching how
    ``run.py`` and ``collect.py`` derive it; specs inside a set dir — legacy
    flat ``tasks/<set>/<id>.md`` or folder-form ``tasks/<set>/<id>/task.md`` —
    list SET-QUALIFIED (``<set>/<id>``) so each listed id round-trips through
    ``resolve_task_path`` unambiguously. README/CATALOG/task.md are never
    tasks, and only ids whose every component matches ``TASK_ID_RE`` are
    listed (anything else could not be launched anyway). Only this set is
    launchable — ``JobManager.start`` re-checks the requested id against disk,
    so a stale UI listing can never smuggle a non-existent task through.
    """
    root = Path(repo_root) if repo_root is not None else _repo_root_default()
    tasks_dir = root / "tasks"
    if not tasks_dir.is_dir():
        return []
    ids = {
        p.stem for p in tasks_dir.glob("*.md")
        if p.is_file() and p.name not in _TASK_SKIP_NAMES and TASK_ID_RE.match(p.stem)
    }
    for set_dir in tasks_dir.iterdir():
        if not set_dir.is_dir() or not TASK_ID_RE.match(set_dir.name):
            continue
        for p in set_dir.glob("*.md"):
            if p.is_file() and p.name not in _TASK_SKIP_NAMES and TASK_ID_RE.match(p.stem):
                ids.add(f"{set_dir.name}/{p.stem}")
        for d in set_dir.iterdir():
            if d.is_dir() and TASK_ID_RE.match(d.name) and (d / _TASK_SPEC_NAME).is_file():
                ids.add(f"{set_dir.name}/{d.name}")
    return sorted(ids)


def available_models() -> List[str]:
    """Return the convenience list of known (backend:model) product slugs.

    These seed the UI's model picker. The authoritative gate is MODEL_SLUG_RE
    (any conforming slug is accepted), so this list is advisory, not a whitelist.
    """
    return list(_DEFAULT_MODEL_SLUGS)


def known_backends() -> List[str]:
    """The four adapter backends this repository can actually launch."""
    return list(_KNOWN_BACKENDS)


# ---------------------------------------------------------------------------
# Routes (user-facing tool-layer) + per-route model menus + UE root
# ---------------------------------------------------------------------------

# The dashboard presents four ROUTES (the sketch's "backend selection") — one
# per RUNNABLE make_adapter() branch, and no others. "baseline" is the
# user-facing name for claude-p. ``live_editor`` says whether the route needs a
# live UnrealEditor + ``--live-project``; the UI reads it rather than keeping its
# own copy of the lane list, so this tuple stays the ONE place a lane is named.
_ROUTES = (
    {"id": "baseline", "backend": "claude-p", "live_editor": False,
     "label": "Baseline (Claude Code, no editor)"},
    {"id": "unreal-mcp", "backend": "unreal-mcp", "live_editor": True,
     "label": "Epic's in-editor MCP (live editor)"},
    {"id": "openrouter", "backend": "openrouter", "live_editor": False,
     "label": "Baseline via OpenRouter (any model)"},
    {"id": "bare", "backend": "bare", "live_editor": False,
     "label": "Minimal scaffold (5 file tools, no editor)"},
)
_ROUTE_TO_BACKEND = {r["id"]: r["backend"] for r in _ROUTES}
_ROUTE_NEEDS_EDITOR = {r["id"]: r["live_editor"] for r in _ROUTES}

# claude-p AND unreal-mcp run through the SAME `claude -p` harness (registry.py
# :485 / :514), so their model is a native Claude id — the ids the CLI takes
# without a slash (registry.py:216-224). Concrete versioned ids only, NO bare
# opus/sonnet/haiku aliases: the launch panel pins a real version, and the runs
# already carry the concrete id. Sources: aura_rig/model_keys.py::KEY_TO_WIRE
# (:66-75) and registry.py::_MODEL_CONTEXT_WINDOW (:175).
_CLAUDE_MODELS = (
    "claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5-20251001",
)
# openrouter AND bare take an OpenRouter ``provider/model`` id. This seed is the
# id set registry.py::_MODEL_CONTEXT_WINDOW (:175-190) pins real context windows
# for — the one dated, in-repo list of ids the harness has actually driven. Any
# other conforming id can still be launched; the menu is advisory, not a gate.
_OPENROUTER_MODELS = (
    "anthropic/claude-sonnet-5",
    "openai/gpt-5.6-terra",
    "deepseek/deepseek-v4-pro-0813",
    "x-ai/grok-4.6",
    "google/gemini-3.7-flash",
    "qwen/qwen3.8-max",
    "z-ai/glm-5.3",
)


def available_routes() -> List[dict]:
    """The four user-facing routes (tool-layers) + backend + label + live_editor."""
    return [dict(r) for r in _ROUTES]


def route_needs_live_editor(route: str) -> bool:
    """Does this route need a live UnrealEditor + ``--live-project``?

    True only for ``unreal-mcp`` — Epic's MCP server lives INSIDE the editor.
    The other three write files and never open one. Unknown routes answer False
    (``compose_slug`` is what rejects them, not this)."""
    return bool(_ROUTE_NEEDS_EDITOR.get(route, False))


def models_for_route(route: str) -> List[str]:
    """Model menu for a route.

    claude-p / unreal-mcp go through `claude -p`, so they get native Claude ids;
    openrouter / bare address OpenRouter, so they get ``provider/model`` ids."""
    backend = _ROUTE_TO_BACKEND.get(route, route)
    return (list(_OPENROUTER_MODELS) if backend in ("openrouter", "bare")
            else list(_CLAUDE_MODELS))


def models_by_route() -> Dict[str, List[str]]:
    """{route_id: [model, ...]} for the launch panel's dependent dropdowns."""
    return {r["id"]: models_for_route(r["id"]) for r in _ROUTES}


def compose_slug(route: str, model: str) -> str:
    """Map a (route, model) UI selection to a validated ``<backend>:<model>`` slug.

    Raises ValueError for an unknown route or a model that fails MODEL_SLUG_RE.
    """
    backend = _ROUTE_TO_BACKEND.get(route)
    if backend is None:
        raise ValueError(f"unknown route {route!r} (expected one of {list(_ROUTE_TO_BACKEND)})")
    return validate_model(f"{backend}:{model}")


# Common UE 5.8 install roots, probed in order for auto-location. Override always
# wins (CB_UE_ROOT, then legacy UE_ROOT, then the standard per-OS install dirs).
_UE_ROOT_CANDIDATES = (
    "/Users/Shared/Epic Games/UE_5.8",        # macOS (Epic launcher default)
    "/Applications/Epic Games/UE_5.8",        # macOS (alt)
    "C:/Program Files/Epic Games/UE_5.8",     # Windows
    "/opt/UnrealEngine/UE_5.8",               # Linux (source build)
)


def default_ue_root() -> Optional[str]:
    """Best-effort auto-locate a UE 5.8 install root; None if none is found.

    Precedence: ``CB_UE_ROOT`` (what the rest of the harness reads and what
    ``.env.example`` documents) -> ``UE_ROOT`` (the common Unreal convention,
    kept as a courtesy fallback) -> the standard per-OS install dirs.

    The documented variable MUST win. UE_ROOT is widely set to whatever engine
    a developer last worked on; letting it take precedence would pin a run to
    that engine via ``--ue-root``, silently overriding CB_UE_ROOT and grading
    against an engine this benchmark is not pinned to.

    The launch panel prefills this; the user can always override the field.
    """
    for cand in (os.environ.get("CB_UE_ROOT"), os.environ.get("UE_ROOT"),
                 str(Path.home() / "UE_5.8"), *_UE_ROOT_CANDIDATES):
        if cand and Path(cand).is_dir():
            return cand
    return None


def _contained_spec(candidate: Path, tasks_dir: Path) -> Optional[Path]:
    """Belt-and-braces containment check for one candidate spec path.

    The RESOLVED candidate must be a real file at exactly ``tasks/<id>.md``,
    ``tasks/<set>/<id>.md`` or ``tasks/<set>/<id>/task.md`` under ``tasks_dir``
    (itself already resolved). Returns the resolved path, or None for an absent
    file / a skip-name doc / any shape or containment miss — including a
    symlinked component that resolves outside ``tasks/``.
    """
    resolved = candidate.resolve()
    if not resolved.is_file():
        return None
    try:
        rel = resolved.relative_to(tasks_dir)
    except ValueError:
        return None  # escapes tasks/ (e.g. via a symlinked component)
    parts = rel.parts
    if len(parts) in (1, 2) and parts[-1].endswith(".md") \
            and parts[-1] not in _TASK_SKIP_NAMES:
        return resolved
    if len(parts) == 3 and parts[2] == _TASK_SPEC_NAME:
        return resolved
    return None


def resolve_task_path(task_id: str, repo_root: Optional[Path] = None) -> Path:
    """Resolve a task id to its on-disk spec path, or raise ValueError.

    Accepts a bare id (``gp-x``) or a set-qualified id (``<set>/gp-x``, max two
    components) and BOTH layouts. The anti-traversal contract has two rings:

      * every '/'-separated component must match ``TASK_ID_RE`` (no separators,
        no '..', no leading dot) BEFORE any filesystem resolution — this refuses
        traversal payloads including round-trips like '../tasks/<real>' that
        would otherwise land back inside tasks/; and
      * the candidate is ``.resolve()``d and re-checked (``_contained_spec``) to
        sit at exactly ``tasks/<id>.md`` | ``tasks/<set>/<id>.md`` |
        ``tasks/<set>/<id>/task.md`` under the real ``tasks/`` dir, so a
        symlinked component cannot escape either.

    A bare id resolves root-first (``tasks/<id>.md`` wins), then to a UNIQUE
    set match — folder form winning a flat same-id sibling within one set. A
    bare id defined in several sets is REJECTED as ambiguous: pass the
    set-qualified ``<set>/<id>`` instead.
    """
    if not isinstance(task_id, str):
        raise ValueError(f"task_id {task_id!r} is not a string")
    parts = task_id.split("/")
    if len(parts) > 2 or not all(TASK_ID_RE.match(c) for c in parts):
        raise ValueError(
            f"task_id {task_id!r} is not a valid task id (bare '<id>' or "
            f"set-qualified '<set>/<id>'; each component must match "
            f"{TASK_ID_RE.pattern})"
        )
    root = Path(repo_root) if repo_root is not None else _repo_root_default()
    tasks_dir = (root / "tasks").resolve()

    if len(parts) == 2:                       # set-qualified "<set>/<id>"
        set_name, bare = parts
        for candidate in (tasks_dir / set_name / bare / _TASK_SPEC_NAME,
                          tasks_dir / set_name / f"{bare}.md"):
            spec = _contained_spec(candidate, tasks_dir)
            if spec is not None:
                return spec
        raise ValueError(f"task_id {task_id!r} is not a real task spec under tasks/")

    # Bare id: the root flat spec wins any set-level duplicate.
    spec = _contained_spec(tasks_dir / f"{task_id}.md", tasks_dir)
    if spec is not None:
        return spec
    # Else a UNIQUE set match, either layout (folder form wins the flat sibling
    # within one set — same rule as the harness-side resolver).
    by_set: Dict[str, Path] = {}
    for p in tasks_dir.glob(f"*/{task_id}.md"):
        by_set.setdefault(p.parent.name, p)
    for p in tasks_dir.glob(f"*/{task_id}/{_TASK_SPEC_NAME}"):
        by_set[p.parent.parent.name] = p
    matches: List[Path] = []
    for set_name in sorted(by_set):
        if not TASK_ID_RE.match(set_name):
            continue  # a set dir we could never address by id — not launchable
        spec = _contained_spec(by_set[set_name], tasks_dir)
        if spec is not None:
            matches.append(spec)
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError(
            f"task_id {task_id!r} is ambiguous across sets — "
            f"use a set-qualified '<set>/{task_id}'"
        )
    raise ValueError(f"task_id {task_id!r} is not a real task spec under tasks/")


def validate_model(model: str) -> str:
    """Return ``model`` unchanged if it matches the product-slug regex, else raise.

    The regex constrains both the backend (a fixed alternation of the four
    runnable ones) and every model component (``[A-Za-z0-9._-]+``, no leading
    '.'), so no shell metacharacter, whitespace or traversal payload can
    survive — a second line of defense beyond argv-only spawning.

    A slug naming a backend this repository cannot launch is refused FIRST, by
    name: ``aura-mcp:*`` and the removed private lanes were real slugs once, and
    "not an allowed product slug" would read as a typo rather than as the
    release boundary it actually is.
    """
    if isinstance(model, str) and ":" in model:
        backend = model.split(":", 1)[0]
        why = _UNLAUNCHABLE_BACKENDS.get(backend)
        if why is not None:
            raise ValueError(
                f"backend {backend!r} ({why}) cannot be launched from this "
                f"repository, so slug {model!r} is not offered. The launchable "
                f"arms are {', '.join(_KNOWN_BACKENDS)}."
            )
    if not isinstance(model, str) or not MODEL_SLUG_RE.match(model):
        raise ValueError(
            f"model {model!r} is not an allowed product slug "
            f"(must match {MODEL_SLUG_RE.pattern})"
        )
    return model


# ---------------------------------------------------------------------------
# Runner-command builder (injectable)
# ---------------------------------------------------------------------------

# A RunnerCommandBuilder maps a validated launch request to an ARGV LIST. It is
# the single seam tests override to avoid spawning run.py / UnrealEditor for real.
RunnerCommandBuilder = Callable[..., List[str]]


def default_run_agent_command(
    *,
    task_path: Path,
    model: str,
    repo_root: Path,
    ue_root: Optional[str] = None,
    live_project: bool = False,
    extra_args: Optional[List[str]] = None,
) -> List[str]:
    """Build the canonical ``tools/run-agent/run.py`` argv list (never a shell str).

    Targets ``run.py`` — the one canonical harness. The live-editor contract is
    surfaced honestly: this builder always passes whatever ``ue_root`` /
    ``live_project`` the caller gave it — if ``unreal-mcp`` is launched without a
    live editor + ``--live-project`` + ``--ue-root``, ``run.py`` itself fails and
    the failure shows up as a failed job with its log (we do NOT manage UE here).
    """
    runner = repo_root / _RUN_AGENT_REL
    argv: List[str] = [
        sys.executable, str(runner),
        "--task", str(task_path),
        "--model", model,
    ]
    if ue_root:
        argv += ["--ue-root", ue_root]
    if live_project:
        argv += ["--live-project"]
    if extra_args:
        argv += list(extra_args)
    return argv


# ---------------------------------------------------------------------------
# Job model + manager
# ---------------------------------------------------------------------------

# Lifecycle states.
QUEUED = "queued"
RUNNING = "running"
DONE = "done"
FAILED = "failed"


@dataclass
class Job:
    """One launched run. Mutated by the watcher thread under the manager lock."""
    job_id: str
    task_id: str
    model: str
    argv: List[str]
    status: str = QUEUED
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    returncode: Optional[int] = None
    log: str = ""
    error: Optional[str] = None
    # Internal handle; never serialized.
    _proc: Optional[subprocess.Popen] = field(default=None, repr=False)

    def to_dict(self) -> dict:
        """JSON-safe status envelope for the API (no Popen handle)."""
        return {
            "job_id": self.job_id,
            "task_id": self.task_id,
            "model": self.model,
            "argv": list(self.argv),
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "returncode": self.returncode,
            "duration_s": (
                (self.finished_at - self.started_at)
                if (self.finished_at is not None and self.started_at is not None)
                else None
            ),
            "log": self.log,
            "error": self.error,
        }


class JobManager:
    """Launches harness runs as background subprocesses and tracks their lifecycle.

    Thread-safety: a single lock guards the job table and every job's mutable
    fields. Each launched job gets a daemon watcher thread that ``communicate()``s
    the process to completion, captures the combined log, and flips the status to
    ``done`` / ``failed`` under the lock. ``start`` validates the request and
    spawns synchronously, so by the time it returns the job is already ``running``
    (or has ``failed`` to spawn).
    """

    def __init__(
        self,
        repo_root: Optional[Path] = None,
        *,
        command_builder: RunnerCommandBuilder = default_run_agent_command,
        cwd: Optional[Path] = None,
        timeout_s: Optional[float] = 1800.0,
    ) -> None:
        self.repo_root = Path(repo_root) if repo_root is not None else _repo_root_default()
        # Injectable seam: tests pass a builder that returns a harmless echo argv.
        self._command_builder = command_builder
        # Subprocess CWD — defaults to the repo root so run.py's relative paths work.
        self._cwd = Path(cwd) if cwd is not None else self.repo_root
        # Wall-clock ceiling per job. A hung run.py / wedged UE would otherwise pin
        # the job in RUNNING forever (communicate() with no timeout never returns);
        # on expiry the watcher KILLS the child and marks the job failed. None
        # disables the ceiling (use only when the caller owns liveness).
        self._timeout_s = timeout_s
        self._jobs: Dict[str, Job] = {}
        self._watchers: Dict[str, threading.Thread] = {}
        self._lock = threading.Lock()

    # -- public API --------------------------------------------------------

    def start(
        self,
        task_id: str,
        model: str,
        *,
        ue_root: Optional[str] = None,
        live_project: bool = False,
        extra_args: Optional[List[str]] = None,
    ) -> str:
        """Validate, build the argv list, spawn in the background, return job_id.

        Raises ``ValueError`` BEFORE any spawn if ``task_id`` is not a real
        ``tasks/*.md`` file or ``model`` does not match the product-slug regex.
        The command is built as an argv LIST and handed to ``Popen`` with the
        default ``shell=False`` — no user string ever reaches a shell.
        """
        # --- validation (pre-spawn; raises on bad input) ---
        task_path = resolve_task_path(task_id, self.repo_root)
        validate_model(model)

        # --- build argv (list, never a shell string) ---
        argv = self._command_builder(
            task_path=task_path,
            model=model,
            repo_root=self.repo_root,
            ue_root=ue_root,
            live_project=live_project,
            extra_args=extra_args,
        )
        if not isinstance(argv, list) or not all(isinstance(a, str) for a in argv):
            raise ValueError("command_builder must return a list[str] argv")

        job = Job(job_id=uuid.uuid4().hex[:12], task_id=task_id, model=model, argv=argv)
        with self._lock:
            self._jobs[job.job_id] = job

        self._spawn(job)
        return job.job_id

    def status(self, job_id: str) -> Optional[dict]:
        """Return the JSON-safe status envelope for ``job_id``, or None if unknown."""
        with self._lock:
            job = self._jobs.get(job_id)
            return job.to_dict() if job is not None else None

    def list(self) -> List[dict]:
        """Return every job's status envelope, newest first."""
        with self._lock:
            jobs = list(self._jobs.values())
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return [j.to_dict() for j in jobs]

    def wait(self, job_id: str, timeout: Optional[float] = None) -> Optional[dict]:
        """Block until the job's watcher thread finishes (test/CLI convenience).

        Returns the final status envelope, or None for an unknown job_id. Does
        not affect the background lifecycle — it only joins the watcher thread.
        """
        with self._lock:
            job = self._jobs.get(job_id)
            watcher = self._watchers.get(job_id) if job is not None else None
        if job is None:
            return None
        if watcher is not None:
            watcher.join(timeout)
        return self.status(job_id)

    # -- internals ---------------------------------------------------------

    def _spawn(self, job: Job) -> None:
        """Popen the job's argv (shell=False) and start its watcher thread.

        A spawn failure (e.g. interpreter missing) is recorded as ``failed`` with
        the exception text, so the UI surfaces it honestly rather than hanging.
        """
        try:
            proc = subprocess.Popen(
                job.argv,
                cwd=str(self._cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                # shell=False is the default and is REQUIRED — argv-only spawning.
            )
        except (OSError, ValueError) as e:
            with self._lock:
                job.status = FAILED
                job.error = f"spawn failed: {e}"
                job.finished_at = time.time()
            return

        with self._lock:
            job._proc = proc
            job.status = RUNNING
            job.started_at = time.time()

        watcher = threading.Thread(
            target=self._watch, args=(job, proc), name=f"job-{job.job_id}", daemon=True
        )
        with self._lock:
            self._watchers[job.job_id] = watcher
        watcher.start()

    def _watch(self, job: Job, proc: subprocess.Popen) -> None:
        """Drain the process to completion, capture its log, flip terminal status.

        Bounded by ``self._timeout_s``: a child that hangs while holding its stdout
        pipe open (a wedged UE / stuck run.py) is KILLED on expiry and the job is
        marked failed, so it never pins forever in RUNNING.
        """
        timed_out = False
        try:
            out, _ = proc.communicate(timeout=self._timeout_s)
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.kill()
            try:
                out, _ = proc.communicate()  # reap the killed child
            except Exception:  # noqa: BLE001
                out = ""
        except Exception as e:  # noqa: BLE001 — never let a watcher die silently
            with self._lock:
                job.status = FAILED
                job.error = f"watch failed: {e}"
                job.finished_at = time.time()
            return
        with self._lock:
            job.log = out or ""
            job.returncode = proc.returncode
            job.finished_at = time.time()
            if timed_out:
                job.status = FAILED
                job.error = f"timed out after {self._timeout_s:.0f}s (process killed)"
            else:
                job.status = DONE if proc.returncode == 0 else FAILED

    # -- test/CLI hook -----------------------------------------------------

    def cancel(self, job_id: str) -> bool:
        """Best-effort terminate a running job. Returns True if a kill was issued."""
        with self._lock:
            job = self._jobs.get(job_id)
            proc = job._proc if job is not None else None
        if proc is None or proc.poll() is not None:
            return False
        proc.terminate()
        return True

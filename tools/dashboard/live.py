"""Read-only LIVE reader for the CraftBench live-status disk contract.

PURE STDLIB, READ-ONLY. This module is the live sibling of the frozen
``collect.py`` (post-hoc) data layer: where ``collect()`` reads completed
``runs/<id>/result.json`` for the matrix, ``live.py`` reads in-flight
``runs/<id>/status.json`` (spec §5.1) and ``runs/<id>/events.jsonl`` (spec §5.2)
for the Active-runs panel + live tool-tape (spec §8).

Design constraints (normative, spec §8):

- **Pure stdlib.** Imports only ``dataclasses``/``datetime``/``json``/``pathlib``/
  ``typing``. It NEVER imports ``textual``/``fastapi`` and — so the frozen v1
  contract stays untouched — it never imports ``model.py``/``collect.py`` either.
  Helpers (``_iso parsing``, the ``LiveRun`` dataclass) are duplicated locally on
  purpose rather than reaching into the frozen modules.
- **Never writes.** Every reader is best-effort: a torn / missing / garbage
  ``status.json`` or ``events.jsonl`` line is SKIPPED, never raised. The single
  writer is the adapter / orchestrator (one-writer invariant, spec §4); concurrent
  readers must tolerate a partial atomic-rewrite / mid-append.
- **Injectable clock.** ``now`` is injected for deterministic stale-detection in
  unit tests with no real wall-clock dependency.

The contract is consumed *by name* (not by importing the writer), so an adapter
in any language can satisfy it.
"""

from __future__ import annotations

import datetime as _dt
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Phases that mean "this run is over" — excluded from the Active panel EXCEPT
# briefly, so a just-finished run doesn't flicker out before result.json lands.
# (spec §5.1 phase enum: queued|launching|running|grading|done|error|timeout|cancelled)
_TERMINAL_PHASES = frozenset({"done", "error", "timeout", "cancelled"})

# Stale only applies while the orchestrator/adapter SHOULD be heartbeating
# status.json — i.e. running or launching (spec §5.1). queued/grading rows are
# not heartbeated, so an old updated_at there is expected, not stale.
_STALE_PHASES = frozenset({"running", "launching"})

PathLike = Union[str, Path]


@dataclass(frozen=True)
class LiveRun:
    """One in-flight run, parsed from ``runs/<id>/status.json`` (spec §5.1).

    Exactly the fields the TUI Active-runs row needs (spec §8): identity
    (``run_id``/``task_id``/``product``), progress (``phase``/``step``/
    ``max_steps``/``current_tool``/``tool_count``), cost (``tokens_in``/
    ``tokens_out``), timing (``elapsed_s``), outcome (``result``/``error``), and
    the derived ``stale`` flag.

    Coarse-mode adapters leave ``step`` / ``current_tool`` / ``tool_count``
    null; the row then shows phase only.

    ``stale`` is True when ``phase`` is running/launching and ``updated_at`` is
    strictly older than ``stale_after_s`` — the killed-orchestrator signal.
    """

    run_id: str
    task_id: str
    product: str
    phase: str
    step: Optional[int]
    max_steps: Optional[int]
    current_tool: Optional[str]
    tool_count: Optional[int]
    tokens_in: Optional[int]
    tokens_out: Optional[int]
    elapsed_s: Optional[float]
    result: Optional[str]
    error: Optional[str]
    stale: bool
    # The run directory the status.json was found in. Runs may nest one
    # container level down (runs/<backend>/<run_id>/), so consumers must use
    # this instead of rebuilding runs/<run_id> from the id. None only for
    # rows built without a source path (tests constructing LiveRun directly).
    path: Optional[Path] = None


def _parse_iso_z(value: Any) -> Optional[_dt.datetime]:
    """Parse an ISO-8601 timestamp (the contract writes a trailing 'Z') to an
    aware UTC datetime. Returns None on anything non-string / unparseable —
    callers treat None as "no usable timestamp" rather than raising."""
    if not isinstance(value, str) or not value:
        return None
    text = value.strip()
    # datetime.fromisoformat doesn't accept the 'Z' suffix before 3.11; normalize.
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = _dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_dt.timezone.utc)
    return dt.astimezone(_dt.timezone.utc)


def _as_int(value: Any) -> Optional[int]:
    """Coerce to int for real ints (not bool); else None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value == value and value not in (float("inf"), float("-inf")):
        return int(value)
    return None


def _as_float(value: Any) -> Optional[float]:
    """Coerce to float for finite numbers (not bool/NaN/Inf); else None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        f = float(value)
        if f == f and f not in (float("inf"), float("-inf")):
            return f
    return None


def _as_str(value: Any) -> Optional[str]:
    return value if isinstance(value, str) else None


def _liverun_from_status(obj: Dict[str, Any], now: _dt.datetime,
                         stale_after_s: float,
                         path: Optional[Path] = None) -> Optional[LiveRun]:
    """Build a LiveRun from a parsed status.json object, or None to skip it.

    Skips anything not shaped like §5.1 (missing run_id or phase). Stale is
    derived from updated_at vs the injected ``now``. ``path`` is the run dir
    the status.json lives in (carried so consumers can find sibling files —
    events.jsonl — without guessing the nesting level)."""
    if not isinstance(obj, dict):
        return None
    run_id = obj.get("run_id")
    phase = obj.get("phase")
    if not isinstance(run_id, str) or not run_id:
        return None
    if not isinstance(phase, str) or not phase:
        return None

    stale = False
    if phase in _STALE_PHASES:
        updated = _parse_iso_z(obj.get("updated_at"))
        if updated is not None:
            age = (now - updated).total_seconds()
            stale = age > stale_after_s

    return LiveRun(
        run_id=run_id,
        task_id=_as_str(obj.get("task_id")) or "",
        product=_as_str(obj.get("product")) or "",
        phase=phase,
        step=_as_int(obj.get("step")),
        max_steps=_as_int(obj.get("max_steps")),
        current_tool=_as_str(obj.get("current_tool")),
        tool_count=_as_int(obj.get("tool_count")),
        tokens_in=_as_int(obj.get("tokens_in")),
        tokens_out=_as_int(obj.get("tokens_out")),
        elapsed_s=_as_float(obj.get("elapsed_s")),
        result=_as_str(obj.get("result")),
        error=_as_str(obj.get("error")),
        stale=stale,
        path=path,
    )


def active_runs(repo_root: PathLike, *, now: Optional[_dt.datetime] = None,
                stale_after_s: float = 30.0) -> List[LiveRun]:
    """Glob ``runs/*/status.json`` + ``runs/*/*/status.json`` (per-backend
    folders) and return the active (plus briefly-terminal) runs as frozen
    ``LiveRun`` rows (spec §8).

    Filtering (spec §5.1): a run is returned when its ``phase`` is NOT terminal
    (done/error/timeout/cancelled). Terminal runs leave the Active panel and
    reappear in the post-hoc matrix once ``result.json`` lands. ``stale`` is set
    True when ``phase`` is running/launching and ``updated_at`` is strictly older
    than ``stale_after_s`` (the killed-orchestrator signal) — measured against the
    injected ``now`` (defaults to the real UTC clock).

    Best-effort: a torn / missing / garbage / mis-shaped ``status.json`` is
    skipped silently. A missing ``runs/`` dir yields ``[]``. Never raises.
    Results are sorted by ``run_id`` for stable rendering.
    """
    if now is None:
        now = _dt.datetime.now(_dt.timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=_dt.timezone.utc)

    runs_dir = Path(repo_root) / "runs"
    out: List[LiveRun] = []
    try:
        # Runs live flat (legacy runs/<id>/) or one container level down
        # (runs/<backend>/<id>/ — run.py's per-backend folder default).
        status_files = sorted(
            set(runs_dir.glob("*/status.json"))
            | set(runs_dir.glob("*/*/status.json")))
    except OSError:
        return out

    for status_path in status_files:
        try:
            raw = status_path.read_text(encoding="utf-8")
        except OSError:
            continue
        try:
            obj = json.loads(raw)
        except (ValueError, json.JSONDecodeError):
            continue  # torn atomic-rewrite / garbage → skip
        row = _liverun_from_status(obj, now, stale_after_s,
                                   path=status_path.parent)
        if row is None:
            continue
        if row.phase in _TERMINAL_PHASES:
            continue
        out.append(row)

    out.sort(key=lambda r: r.run_id)
    return out


def _resolve_events_path(run_id_or_dir: PathLike) -> Path:
    """Resolve the events.jsonl path from either a run directory or a path that
    already ends at the file. Callers pass a run dir (``runs/<id>/``); a path that
    already points at ``events.jsonl`` is accepted as-is."""
    p = Path(run_id_or_dir)
    if p.name == "events.jsonl":
        return p
    return p / "events.jsonl"


def tail_events(run_id_or_dir: PathLike, after_seq: int) -> List[Dict[str, Any]]:
    """Return parsed ``events.jsonl`` lines whose ``seq`` is strictly greater than
    ``after_seq`` (spec §8 incremental tail).

    Each line is one JSON object (spec §5.2). ``type`` is an open enum — unknown
    types pass through unchanged (the caller ignores them). The returned list is
    in file order (the writer emits monotonically increasing ``seq``).

    Best-effort: blank lines, non-JSON lines, objects without an integer ``seq``,
    and a torn (partial) FINAL line — the writer mid-append — are skipped. A
    missing file yields ``[]``. Never raises.
    """
    path = _resolve_events_path(run_id_or_dir)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return []

    out: List[Dict[str, Any]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except (ValueError, json.JSONDecodeError):
            continue  # garbage or torn final line → skip
        if not isinstance(obj, dict):
            continue
        seq = _as_int(obj.get("seq"))
        if seq is None:
            continue  # can't be ordered → skip
        if seq > after_seq:
            out.append(obj)
    return out

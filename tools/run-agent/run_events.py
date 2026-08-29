"""EventSink — the live disk-contract writer layer (design spec §5.1, §5.2, §7).

Adapters emit a tool-by-tool tape (``events.jsonl``) and a single rolling
``status.json`` as they stream; the read-only ``live.py`` / TUI tail those
files. This module owns the *write* side of that contract:

  - ``FileEventSink(run_dir)`` — appends one JSON line per ``emit`` to
    ``<run_dir>/events.jsonl`` with a monotonic ``seq`` (starting at 1) and a
    ``ts``; rewrites ``<run_dir>/status.json`` ATOMICALLY (tmp + ``os.replace``)
    on each ``status(**fields)``, merging fields and always bumping
    ``updated_at``.
  - ``NullEventSink`` — a no-op sink for adapters that don't emit and for
    existing positional callers (spec §7: ``events`` is keyword-only, default
    ``None`` → callers substitute ``NullEventSink``).
  - ``write_result_json(run_dir, obj)`` — atomic ``result.json`` writer, used
    to land ``result.json`` BEFORE ``status.json.phase`` flips to ``done``
    (spec §5.2, closes the torn-read window).

Pure stdlib. The wall-clock is injected (a ``now`` callable returning an ISO-Z
timestamp string) so the whole module is deterministic under test with no real
clock, editor, Aura, network, or API key.

One-writer invariant (spec §4): exactly one ``FileEventSink`` instance owns a
given ``run_dir``'s ``events.jsonl`` + the in-run ``status.json`` detail. ``seq``
monotonicity is guaranteed within that single instance (the orchestrator never
opens two emitting sinks on one run concurrently).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Protocol, runtime_checkable

# The frozen status.json schema tag (spec §5.1).
STATUS_SCHEMA = "craftbench.livestatus/v1"

# The full §5.1 status.json key set, in spec order. write_status_full() emits
# exactly these keys so the contract shape is pinned.
STATUS_FIELDS = (
    "schema",
    "run_id",
    "task_id",
    "product",
    "phase",
    "step",
    "max_steps",
    "current_tool",
    "tool_count",
    "tokens_in",
    "tokens_out",
    "started_at",
    "updated_at",
    "elapsed_s",
    "result",
    "error",
)


@runtime_checkable
class EventSink(Protocol):
    """The additive, product-neutral emission seam (spec §7).

    Adapters receive an ``EventSink`` by keyword and call ``emit`` per tool
    event and ``status`` to update the rolling live state. Both methods are
    fire-and-forget (return ``None``); a sink must never raise into the
    adapter's hot loop.
    """

    def emit(self, event: dict) -> None:
        """Append one event to events.jsonl (the sink stamps seq + ts)."""
        ...

    def status(self, **fields) -> None:
        """Merge ``fields`` into status.json and rewrite it atomically."""
        ...


def _utc_now_z() -> str:
    """Default clock: real UTC wall-clock as an ISO-8601 Zulu string.

    Tests inject a stub instead; this default is only used in production where
    a real clock is available.
    """
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _atomic_write_json(path: Path, obj: Dict[str, Any]) -> None:
    """Write ``obj`` as JSON to ``path`` atomically (tmp file + os.replace).

    The tmp file is created in the SAME directory as ``path`` so ``os.replace``
    is a same-filesystem rename (atomic on POSIX). On success no tmp file
    remains; on a mid-write crash the reader only ever sees the old complete
    file or the new complete file — never a partial one.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Unique-enough tmp name in the destination directory.
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)  # atomic same-dir rename
    finally:
        # Belt-and-suspenders: never leave a partial tmp behind if replace
        # didn't happen (e.g. an exception inside the with-block).
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


class FileEventSink:
    """Disk-backed EventSink for one run directory (spec §5.1/§5.2/§7).

    Append-only ``events.jsonl`` with monotonic ``seq`` (from 1) + injected
    ``ts``; atomically-rewritten ``status.json`` that merges successive
    ``status(**fields)`` calls and always bumps ``updated_at``.
    """

    def __init__(self, run_dir: Path, now: Optional[Callable[[], str]] = None):
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.events_path = self.run_dir / "events.jsonl"
        self.status_path = self.run_dir / "status.json"
        self._now = now or _utc_now_z
        self._seq = 0
        # In-memory mirror of the merged status so each rewrite is the FULL
        # object (status.json is a rolling full-state snapshot, not a patch).
        self._status: Dict[str, Any] = {}

    # --- events.jsonl (append-only tape, spec §5.2) ----------------------

    def emit(self, event: dict) -> None:
        """Append one event line. The sink owns ``seq`` and ``ts`` — any
        caller-supplied ``seq``/``ts`` is overwritten so the tape stays
        authoritative and monotonic."""
        self._seq += 1
        record = dict(event)
        record["ts"] = self._now()
        record["seq"] = self._seq
        line = json.dumps(record, ensure_ascii=False)
        # Append-only; one line per event. Open per-call so a killed
        # orchestrator still leaves a complete, flushed tape on disk.
        with open(self.events_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()

    # --- status.json (rolling full state, atomically rewritten, §5.1) ----

    def status(self, **fields) -> None:
        """Merge ``fields`` into the current status and rewrite atomically.
        ``updated_at`` is always bumped from the injected clock."""
        self._status.update(fields)
        self._status["updated_at"] = self._now()
        _atomic_write_json(self.status_path, self._status)

    def write_status_full(
        self,
        *,
        run_id: str,
        task_id: str,
        product: str,
        phase: str,
        step: Optional[int],
        max_steps: Optional[int],
        current_tool: Optional[str],
        tool_count: Optional[int],
        tokens_in: Optional[int],
        tokens_out: Optional[int],
        started_at: Optional[str],
        elapsed_s: Optional[float],
        result: Optional[str],
        error: Optional[str],
        schema: str = STATUS_SCHEMA,
    ) -> None:
        """Write the FULL §5.1 status object (all keys present), atomically.

        Used by the orchestrator to lay down the complete contract shape (e.g.
        the initial ``queued`` write). ``updated_at`` is stamped from the
        injected clock; subsequent ``status(**fields)`` calls merge on top of
        this full object so every later rewrite is still complete.
        """
        self._status = {
            "schema": schema,
            "run_id": run_id,
            "task_id": task_id,
            "product": product,
            "phase": phase,
            "step": step,
            "max_steps": max_steps,
            "current_tool": current_tool,
            "tool_count": tool_count,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "started_at": started_at,
            "updated_at": self._now(),
            "elapsed_s": elapsed_s,
            "result": result,
            "error": error,
        }
        _atomic_write_json(self.status_path, self._status)


class NullEventSink:
    """No-op EventSink (spec §7): adapters that don't emit and existing
    positional callers get this so ``events=`` is always safe to call. Writes
    nothing, raises nothing."""

    def emit(self, event: dict) -> None:  # noqa: D401 - no-op
        return None

    def status(self, **fields) -> None:  # noqa: D401 - no-op
        return None


def write_result_json(run_dir: Path, result_obj: Dict[str, Any]) -> Path:
    """Atomically write ``<run_dir>/result.json`` (tmp + os.replace).

    Spec §5.2: ``result.json`` is written atomically and lands BEFORE
    ``status.json.phase`` flips to ``done``, so any reader that sees ``done``
    can always find a complete matrix entry. Returns the result.json path.
    """
    run_dir = Path(run_dir)
    path = run_dir / "result.json"
    _atomic_write_json(path, result_obj)
    return path

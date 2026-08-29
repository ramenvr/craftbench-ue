"""reasoning_census — how much THINKING each panel model actually did, measured.

The harness sets no reasoning/thinking parameter anywhere (grep: no
``reasoning_effort``, no ``thinking``, no ``budget_tokens`` on any request path),
so every recorded run ran at its provider's DEFAULT effort. What that produced is
on no run record: §3 of the run-record contract lists tokens in/out + the cache split
and no reasoning field, and not one of the usage-log lines written before
2026-08-24 carries a reasoning count. This module is the RETROSPECTIVE half —
recovering the number for drives already paid for. Recording it live is the other
half and belongs in the proxy and the adapters, not here.

Two joins make that possible, both already in the tree:

  * ``aura_rig.proxy``'s USAGE_LOG holds one line per forwarded request with a
    ``ts``, the on-wire ``model`` and OpenRouter's ``gen-`` id;
  * ``GET /api/v1/generation?id=<gen-id>`` answers with
    ``native_tokens_reasoning`` / ``native_tokens_completion`` and the DATED
    permaslug that actually served the call.

``aura_rig.openrouter_cost`` already speaks to that endpoint and already parses
the reasoning field, so this module reuses its fetch rather than writing a second
client. What it adds is the OTHER end of the join: the usage log. The recorded
MCP-lane cells predate ``agent.generation_ids`` on the run record, so
``openrouter_cost``'s result.json-driven audit has nothing to read for them and
the log is the only place their ids exist.

THE ONE INVARIANT: "reasoning was 0" and "we could not find out" are different
answers and are never merged. A pending/missing/errored lookup is counted as
unresolved and contributes to no token sum; a resolved record whose
``native_tokens_reasoning`` is absent (provider did not report it) is counted
separately from one that reported zero. Reasoning shares are computed only over
calls where both numerator and denominator were actually reported: a call that
reported one side and not the other lands in a partially-reported counter and
enters NEITHER sum, since crediting its reasoning to a denominator it never
contributed to can push a share past 100%. Every table prints its own sample
size so a reader can see what the number rests on.

Usage:
    py -3 tools/run-agent/reasoning_census.py                  # 40 ids/model
    py -3 tools/run-agent/reasoning_census.py --sample 0 --limit 3000   # all
    py -3 tools/run-agent/reasoning_census.py --json
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from aura_rig import openrouter_cost as orc
from aura_rig import paths as cb_paths
from aura_rig import proxy

REPO = _HERE.parents[1]

#: Rotated/renamed copies count: the live proxy writes one name, but an operator
#: parking a sweep's log aside keeps the stem.
USAGE_GLOB = "cb-anthropic-usage*.jsonl"

#: Politeness between HTTP lookups. Higher than openrouter_cost's per-run 0.06
#: because a census walks thousands of ids in one pass, not tens.
DEFAULT_SLEEP_S = 0.12

#: Lanes whose run dirs are joined against the log. The whole MCP sweep.
DEFAULT_LANES = ("unreal-mcp", "aura-mcp", "claude-p", "openrouter")

#: Fairness hide + editor bring-up run between a cell's run-dir stamp and its
#: first proxied request, so its last request lands that same lead-in past
#: ``start + agent.duration_s``. Five minutes covers a bring-up with margin;
#: records that then fall in two windows are reported AMBIGUOUS, never assigned.
CELL_WINDOW_PAD_S = 300.0

_RUN_ID_RE = re.compile(r"^(\d{8})-(\d{6})-")


# ---------------------------------------------------------------------------
# Usage-log discovery + reading (pure; no network).
# ---------------------------------------------------------------------------

@dataclass
class LogFile:
    """One usage log found on disk, with what it covers."""

    path: Path
    records: int = 0
    unparsable: int = 0
    first_ts: Optional[float] = None
    last_ts: Optional[float] = None
    models: Dict[str, int] = field(default_factory=dict)
    #: Records with no on-wire model. Real requests, but not attributable.
    modelless: int = 0
    #: Records that already carry a reasoning count on the LINE. Zero for every
    #: line written before the proxy learned the field (2026-08-24); a nonzero
    #: count means this log no longer needs the ledger to answer the question.
    with_reasoning_field: int = 0
    #: Another discovered path whose bytes hash to this file's (e.g. a POSIX /tmp
    #: view of %TEMP%). Reported, not silently dropped.
    aliases: List[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "path": str(self.path),
            "records": self.records,
            "unparsable": self.unparsable,
            "first_utc": _iso(self.first_ts),
            "last_utc": _iso(self.last_ts),
            "models": dict(sorted(self.models.items(), key=lambda kv: -kv[1])),
            "modelless_records": self.modelless,
            "records_with_reasoning_field": self.with_reasoning_field,
            "aliases": self.aliases,
        }


@dataclass
class LogRecord:
    """The three fields of a usage line this census needs."""

    ts: float
    model: Optional[str]
    generation_id: str
    source: str


def _iso(ts: Optional[float]) -> Optional[str]:
    if ts is None:
        return None
    return _dt.datetime.fromtimestamp(ts, _dt.timezone.utc).isoformat(
        timespec="seconds")


def candidate_log_roots(extra: Sequence[Path] = ()) -> List[Path]:
    """Every directory a usage log could plausibly live in, deduped.

    The system temp is included DELIBERATELY (it is where the default
    ``proxy.USAGE_LOG`` lands), unlike ``paths.tmp_scratch_roots`` which excludes
    it because that function's callers DELETE what they find.
    """
    out: List[Path] = []

    def add(p) -> None:
        try:
            rp = Path(p).resolve()
        except (OSError, ValueError):
            return
        if rp.is_dir() and rp not in out:
            out.append(rp)

    add(proxy.USAGE_LOG.parent)
    add(tempfile.gettempdir())
    for var in ("CB_TMP", "TEMP", "TMP"):
        v = os.environ.get(var)
        if v:
            add(v)
    for r in cb_paths.tmp_scratch_roots():
        add(r)
    try:
        add(cb_paths.cb_root())
    except Exception:  # noqa: BLE001 - a machine without CB_ROOT is fine
        pass
    add(REPO / "runs")
    for e in extra:
        add(e)
    return out


def _content_digest(path: Path) -> Optional[str]:
    """SHA-256 of the file, or None when it cannot be read.

    Size+mtime is a fingerprint, not an identity: two logs from one sweep can
    share both and differ in every line, and dropping one as an "alias" loses its
    records from the census. None means UNPROVEN, which keeps the file.
    """
    h = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


def discover_logs(extra_roots: Sequence[Path] = (),
                  explicit: Sequence[Path] = ()) -> List[LogFile]:
    """Find every usage log, read its coverage, and collapse byte-identical aliases."""
    found: List[Path] = [Path(p) for p in explicit]
    if not found:
        for root in candidate_log_roots(extra_roots):
            try:
                found.extend(sorted(root.glob(USAGE_GLOB)))
            except OSError:
                continue
    logs: List[LogFile] = []
    by_digest: Dict[str, LogFile] = {}
    seen: set = set()
    for p in found:
        try:
            rp = p.resolve()
            if not rp.is_file():
                continue
        except OSError:
            continue
        if rp in seen:
            continue
        seen.add(rp)
        digest = _content_digest(rp)
        if digest is not None and digest in by_digest:
            by_digest[digest].aliases.append(str(rp))
            continue
        lf = _read_log(rp)
        if digest is not None:
            by_digest[digest] = lf
        logs.append(lf)
    return logs


def _iter_json_lines(path: Path):
    """Yield each JSONL line as a dict, or None when it would not parse.

    None rather than a silent skip: the coverage report counts unparsable lines,
    and a reader needs to know a log is damaged."""
    try:
        fh = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return
    with fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except ValueError:
                yield None


def _read_log(path: Path) -> LogFile:
    lf = LogFile(path=path)
    for r in _iter_json_lines(path):
        if r is None:
            lf.unparsable += 1
            continue
        lf.records += 1
        ts = r.get("ts")
        if isinstance(ts, (int, float)):
            lf.first_ts = ts if lf.first_ts is None else min(lf.first_ts, ts)
            lf.last_ts = ts if lf.last_ts is None else max(lf.last_ts, ts)
        if "reasoning_tokens" in r:
            lf.with_reasoning_field += 1
        m = r.get("model")
        if m:
            lf.models[m] = lf.models.get(m, 0) + 1
        else:
            lf.modelless += 1
    return lf


def read_records(logs: Sequence[LogFile]) -> List[LogRecord]:
    """Every generation-id-bearing record across the logs, oldest first.

    Deduped on the id: the same log copied to two names must not double-count a
    request, and one id per request is the proxy's invariant.
    """
    out: List[LogRecord] = []
    seen: set = set()
    for lf in logs:
        for r in _iter_json_lines(lf.path):
            if r is None:
                continue
            gid = r.get("generation_id")
            ts = r.get("ts")
            if not gid or gid in seen or not isinstance(ts, (int, float)):
                continue
            seen.add(gid)
            out.append(LogRecord(ts=float(ts), model=r.get("model"),
                                 generation_id=str(gid), source=str(lf.path)))
    out.sort(key=lambda r: r.ts)
    return out


def collect_result_ids(runs_root: Path) -> Dict[str, List[LogRecord]]:
    """Generation ids recorded ON a run record, keyed by run dir.

    A SECOND, independent source: ``adapters/bare_wire`` sets
    ``AgentResult.generation_ids``, so a bare-lane cell carries its own ids even
    when no proxy was running. Kept apart from the log-derived census rather than
    pooled — a bare cell is a different lane and a different task set, and one
    run's effort must not be reported as a model's panel-wide effort.

    ``model`` is left None on purpose: the ledger's own permaslug answers what
    served the call, so nothing here has to un-sanitize a directory name.
    """
    out: Dict[str, List[LogRecord]] = {}
    for name in ("result.json", "agent_result.json"):
        for p in sorted(runs_root.rglob(name)):
            try:
                d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
            except (OSError, ValueError):
                continue
            ids = ((d.get("agent") or {}).get("generation_ids")
                   or d.get("generation_ids") or [])
            if not ids:
                continue
            run_dir = p.parent.name
            ts = _run_start_ts(run_dir)
            if ts is None:
                try:
                    ts = p.stat().st_mtime
                except OSError:
                    continue
            bucket = out.setdefault(run_dir, [])
            have = {r.generation_id for r in bucket}
            for gid in ids:
                gid = str(gid)
                if gid.startswith(proxy.GENERATION_ID_PREFIX) and gid not in have:
                    have.add(gid)
                    bucket.append(LogRecord(ts=float(ts), model=None,
                                            generation_id=gid, source=str(p)))
    return out


def sample_records(records: Sequence[LogRecord], per_model: int
                   ) -> List[LogRecord]:
    """``per_model`` ids per model, spread evenly across that model's time span.

    Evenly rather than first-N: a model's records are contiguous per cell, so the
    first N would all come from one cell and its one task, and the census would
    report that cell's effort as the model's.
    """
    if per_model <= 0:
        return list(records)
    by_model: Dict[Optional[str], List[LogRecord]] = {}
    for r in records:
        by_model.setdefault(r.model, []).append(r)
    out: List[LogRecord] = []
    for _, rs in by_model.items():
        n = len(rs)
        if n <= per_model:
            out.extend(rs)
            continue
        idx = sorted({round(i * (n - 1) / (per_model - 1))
                      for i in range(per_model)}) if per_model > 1 else [0]
        out.extend(rs[i] for i in idx)
    out.sort(key=lambda r: r.ts)
    return out


# ---------------------------------------------------------------------------
# On-disk resolution cache.
# ---------------------------------------------------------------------------

#: Only TERMINAL answers are cached. A "pending" is the endpoint's indexing lag
#: and a re-run is exactly how it resolves; caching it would freeze a temporary
#: gap into a permanent one.
_CACHEABLE = ("ok", "missing")

_CACHE_FIELDS = ("generation_id", "status", "total_cost", "model_permaslug",
                 "provider_name", "native_tokens_prompt",
                 "native_tokens_completion", "native_tokens_reasoning")


def default_cache_path() -> Path:
    return REPO / "runs" / ".reasoning-census-cache.jsonl"


class GenCache:
    """Append-only JSONL sidecar of resolved generations. Last line wins."""

    def __init__(self, path: Optional[Path]):
        self.path = Path(path) if path else None
        self.entries: Dict[str, orc.GenerationFacts] = {}
        self.hits = 0
        if self.path and self.path.exists():
            self._load()

    def _load(self) -> None:
        try:
            fh = open(self.path, encoding="utf-8", errors="replace")
        except OSError:
            return
        with fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                gid = d.get("generation_id")
                if not gid:
                    continue
                self.entries[str(gid)] = orc.GenerationFacts(
                    **{k: d.get(k) for k in _CACHE_FIELDS
                       if k != "status"},
                    status=str(d.get("status") or "error: cache"),
                )

    def get(self, gid: str) -> Optional[orc.GenerationFacts]:
        f = self.entries.get(gid)
        if f is not None:
            self.hits += 1
        return f

    def put(self, facts: orc.GenerationFacts) -> None:
        if facts.status not in _CACHEABLE:
            return
        self.entries[facts.generation_id] = facts
        if self.path is None:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(
                    {k: getattr(facts, k) for k in _CACHE_FIELDS}) + "\n")
        except OSError:
            pass  # a census that cannot cache is slower, not wrong


# ---------------------------------------------------------------------------
# Aggregation (pure).
# ---------------------------------------------------------------------------

@dataclass
class ModelCensus:
    """One model's measured effort. Every counter names what it excludes."""

    model: str
    requests_logged: int = 0
    sampled: int = 0
    resolved: int = 0
    pending: int = 0
    missing: int = 0
    errors: int = 0
    #: Resolved calls that reported a reasoning count (the share's denominator set).
    reasoning_reported: int = 0
    #: Resolved calls whose reasoning field was ABSENT — not zero, unreported.
    reasoning_unreported: int = 0
    #: Resolved calls that reported reasoning but no completion. The share has no
    #: denominator for them, so they are in neither sum and get their own line.
    partially_reported: int = 0
    reasoning_zero: int = 0
    reasoning_nonzero: int = 0
    #: Summed ONLY over reasoning_reported calls, so numerator and denominator
    #: cover the same requests.
    reasoning_tokens: int = 0
    completion_tokens: int = 0
    prompt_tokens: int = 0
    max_reasoning: int = 0
    permaslugs: Dict[str, int] = field(default_factory=dict)
    providers: Dict[str, int] = field(default_factory=dict)

    @property
    def unresolved(self) -> int:
        return self.pending + self.missing + self.errors

    @property
    def reasoning_share(self) -> Optional[float]:
        """reasoning / native_completion over reported calls, or None."""
        if not self.reasoning_reported or self.completion_tokens <= 0:
            return None
        return self.reasoning_tokens / self.completion_tokens

    @property
    def mean_reasoning(self) -> Optional[float]:
        if not self.reasoning_reported:
            return None
        return self.reasoning_tokens / self.reasoning_reported

    @property
    def version_drift(self) -> bool:
        return len(self.permaslugs) > 1 or len(self.providers) > 1

    def as_dict(self) -> dict:
        return {
            "model": self.model,
            "requests_logged": self.requests_logged,
            "sampled": self.sampled,
            "resolved": self.resolved,
            "pending": self.pending,
            "missing": self.missing,
            "errors": self.errors,
            "reasoning_reported": self.reasoning_reported,
            "reasoning_unreported": self.reasoning_unreported,
            "partially_reported": self.partially_reported,
            "reasoning_zero": self.reasoning_zero,
            "reasoning_nonzero": self.reasoning_nonzero,
            "reasoning_tokens": self.reasoning_tokens,
            "completion_tokens": self.completion_tokens,
            "prompt_tokens": self.prompt_tokens,
            "max_reasoning": self.max_reasoning,
            "mean_reasoning_per_call": self.mean_reasoning,
            "reasoning_share": self.reasoning_share,
            "permaslugs": dict(sorted(self.permaslugs.items())),
            "providers": dict(sorted(self.providers.items())),
            "version_drift": self.version_drift,
        }


def _absorb(c: ModelCensus, f: orc.GenerationFacts) -> None:
    if f.status == "ok":
        c.resolved += 1
        if f.model_permaslug:
            c.permaslugs[f.model_permaslug] = c.permaslugs.get(
                f.model_permaslug, 0) + 1
        if f.provider_name:
            c.providers[f.provider_name] = c.providers.get(f.provider_name, 0) + 1
        r = f.native_tokens_reasoning
        if r is None:
            c.reasoning_unreported += 1
            return
        comp = f.native_tokens_completion
        if comp is None:
            c.partially_reported += 1
            return
        c.reasoning_reported += 1
        c.reasoning_tokens += int(r)
        c.max_reasoning = max(c.max_reasoning, int(r))
        if int(r) > 0:
            c.reasoning_nonzero += 1
        else:
            c.reasoning_zero += 1
        c.completion_tokens += int(comp)
        c.prompt_tokens += int(f.native_tokens_prompt or 0)
    elif f.status == "pending":
        c.pending += 1
    elif f.status == "missing":
        c.missing += 1
    else:
        c.errors += 1


def census_by_model(records: Sequence[LogRecord],
                    facts: Dict[str, orc.GenerationFacts],
                    logged_counts: Dict[str, int]) -> Dict[str, ModelCensus]:
    """The PRIMARY result: per-model aggregate, independent of any cell join."""
    out: Dict[str, ModelCensus] = {}
    for r in records:
        key = r.model or "(no on-wire model)"
        c = out.setdefault(key, ModelCensus(model=key))
        c.requests_logged = logged_counts.get(key, 0)
        f = facts.get(r.generation_id)
        if f is None:
            continue
        c.sampled += 1
        _absorb(c, f)
    return out


# ---------------------------------------------------------------------------
# Cell attribution (the bonus; the per-model aggregate never depends on it).
# ---------------------------------------------------------------------------

@dataclass
class Cell:
    run_dir: str
    lane: str
    task: str
    model: str
    start_ts: float
    duration_s: Optional[float]
    verdict: Optional[str]

    @property
    def end_ts(self) -> float:
        return self.start_ts + (self.duration_s or 0.0) + CELL_WINDOW_PAD_S


def _run_start_ts(name: str) -> Optional[float]:
    """Run dirs are stamped in UTC (``run.py::_make_run_id``)."""
    m = _RUN_ID_RE.match(name)
    if not m:
        return None
    try:
        return _dt.datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S"
                                     ).replace(tzinfo=_dt.timezone.utc).timestamp()
    except ValueError:
        return None


def load_cells(runs_root: Path, lanes: Sequence[str]) -> List[Cell]:
    cells: List[Cell] = []
    for lane in lanes:
        for rj in sorted((runs_root / lane).glob("*/result.json")):
            name = rj.parent.name
            st = _run_start_ts(name)
            if st is None:
                continue
            try:
                d = json.loads(rj.read_text(encoding="utf-8", errors="replace"))
            except (OSError, ValueError):
                continue
            agent = d.get("agent") or {}
            cells.append(Cell(
                run_dir=name, lane=lane, task=str(d.get("task") or ""),
                model=str(d.get("model") or "").split(":", 1)[-1],
                start_ts=st, duration_s=agent.get("duration_s"),
                verdict=d.get("overall"),
            ))
    return cells


@dataclass
class Attribution:
    per_cell: Dict[str, ModelCensus] = field(default_factory=dict)
    #: The cell each row came from, so a reader can see task + verdict beside the
    #: effort without a second join.
    cells: Dict[str, "Cell"] = field(default_factory=dict)
    ambiguous: int = 0
    unattributed: int = 0
    #: Cells whose windows overlap another cell of the SAME model.
    overlapping_cells: List[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "records_ambiguous": self.ambiguous,
            "records_unattributed": self.unattributed,
            "overlapping_cells": sorted(self.overlapping_cells),
            "cells": {k: dict(v.as_dict(),
                              task=self.cells[k].task if k in self.cells else None,
                              verdict=self.cells[k].verdict if k in self.cells else None)
                      for k, v in sorted(self.per_cell.items())},
        }


def attribute(records: Sequence[LogRecord], facts: Dict[str, orc.GenerationFacts],
              cells: Sequence[Cell]) -> Attribution:
    """Join records to cells by (model, time window). Ambiguity is REPORTED.

    A record inside two same-model windows is counted ambiguous and assigned to
    neither: the sweep is serial, so an overlap means the window model is wrong
    for that pair, and guessing would put one cell's effort on another's row.
    """
    att = Attribution()
    by_model: Dict[str, List[Cell]] = {}
    for c in cells:
        by_model.setdefault(c.model, []).append(c)
    for cs in by_model.values():
        cs.sort(key=lambda c: c.start_ts)
        for a, b in zip(cs, cs[1:]):
            if a.end_ts > b.start_ts:
                att.overlapping_cells.extend([a.run_dir, b.run_dir])
    for r in records:
        f = facts.get(r.generation_id)
        if f is None or not r.model:
            continue
        hits = [c for c in by_model.get(r.model, [])
                if c.start_ts <= r.ts <= c.end_ts]
        if len(hits) != 1:
            if hits:
                att.ambiguous += 1
            else:
                att.unattributed += 1
            continue
        c = hits[0]
        mc = att.per_cell.setdefault(
            c.run_dir, ModelCensus(model=f"{c.lane}:{c.model}"))
        att.cells[c.run_dir] = c
        mc.sampled += 1
        _absorb(mc, f)
    return att


# ---------------------------------------------------------------------------
# Resolution driver.
# ---------------------------------------------------------------------------

def resolve_all(records: Sequence[LogRecord], api_key: str, cache: GenCache, *,
                limit: int, sleep_s: float = DEFAULT_SLEEP_S,
                http_get: Optional[Callable] = None,
                sleep: Callable[[float], None] = time.sleep,
                now: Optional[float] = None,
                progress: Optional[Callable[[int, int], None]] = None,
                ) -> Tuple[Dict[str, orc.GenerationFacts], int, int]:
    """Resolve every record's id. Returns (facts, http_calls, skipped_over_limit).

    ``age_s`` comes from the RECORD's own ``ts``, not a file mtime, so the
    pending-vs-missing call is made against when the generation actually happened.
    """
    facts: Dict[str, orc.GenerationFacts] = {}
    calls = 0
    skipped = 0
    t_now = time.time() if now is None else now
    total = len(records)
    for i, r in enumerate(records):
        cached = cache.get(r.generation_id)
        if cached is not None:
            facts[r.generation_id] = cached
            continue
        if calls >= limit:
            skipped += 1
            continue
        if calls:
            sleep(sleep_s)
        f = orc.fetch_generation(r.generation_id, api_key,
                                 age_s=max(0.0, t_now - r.ts),
                                 http_get=http_get)
        calls += 1
        facts[r.generation_id] = f
        cache.put(f)
        if progress and calls % 25 == 0:
            progress(i + 1, total)
    return facts, calls, skipped


def api_key() -> Optional[str]:
    """Env first, then the repo ``.env`` — the rig's precedence everywhere."""
    k = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    if k:
        return k
    try:
        text = (REPO / ".env").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    from aura_rig import stack as _stack  # local: keep this module import-light

    return _stack._env_val(text, "OPENROUTER_API_KEY")


# ---------------------------------------------------------------------------
# Reporting.
# ---------------------------------------------------------------------------

def _fmt_share(v: Optional[float]) -> str:
    return "n/a" if v is None else f"{100.0 * v:5.1f}%"


def _excluded(c: "ModelCensus") -> int:
    """Resolved calls this row's share is NOT computed over.

    Every table that prints a share prints this beside it. A share whose
    excluded count is invisible reads as covering the whole row, and the two
    ways a call drops out -- the provider reported no reasoning, or reported
    reasoning with no completion to divide by -- are exactly the states that
    must never be mistaken for a measured zero.
    """
    return c.reasoning_unreported + c.partially_reported


def print_report(logs: Sequence[LogFile], by_model: Dict[str, ModelCensus],
                 att: Optional[Attribution], *, calls: int, cache_hits: int,
                 skipped: int, expected_models: Sequence[str] = (),
                 by_run: Optional[Dict[str, ModelCensus]] = None) -> None:
    print(f"USAGE LOGS ({len(logs)} found)")
    for lf in logs:
        print(f"  {lf.path}")
        print(f"    {lf.records} records  {_iso(lf.first_ts)} -> {_iso(lf.last_ts)}"
              f"  (modelless: {lf.modelless}, unparsable: {lf.unparsable}, "
              f"carrying a reasoning field: {lf.with_reasoning_field})")
        for a in lf.aliases:
            print(f"    alias (byte-identical): {a}")
        for m, n in sorted(lf.models.items(), key=lambda kv: -kv[1]):
            print(f"      {m:42s} {n:6d}")

    missing_models = [m for m in expected_models
                      if not any(m in lf.models for lf in logs)]
    if missing_models:
        print("\nNOT PRESENT IN ANY LOG - no ledger ids exist for these, so their "
              "reasoning is UNMEASURABLE from this source, not zero:")
        for m in missing_models:
            print(f"  {m}")

    print(f"\nHTTP lookups: {calls}   cache hits: {cache_hits}"
          + (f"   skipped (over --limit): {skipped}" if skipped else ""))

    print("\nPER-MODEL (primary result - no cell join involved)")
    print("  reason/compl are ledger native tokens: share = reason/compl, a "
          "RATIO not a guaranteed fraction - reasoning is normally reported "
          "inside completion, but some providers return a reasoning count that "
          "exceeds it. Not a share of the proxy's own output_tokens, which "
          "disagree with the ledger on some records.")
    hdr = (f"{'model':40s}{'logged':>7}{'smpl':>6}{'ok':>5}{'unres':>6}"
           f"{'reason':>9}{'compl':>9}{'share':>7}{'mean':>7}{'max':>7}  zero/nonzero")
    print(hdr)
    print("-" * len(hdr))
    for key in sorted(by_model, key=lambda k: -by_model[k].requests_logged):
        c = by_model[key]
        print(f"{c.model[:39]:40s}{c.requests_logged:>7}{c.sampled:>6}"
              f"{c.resolved:>5}{c.unresolved:>6}{c.reasoning_tokens:>9}"
              f"{c.completion_tokens:>9}{_fmt_share(c.reasoning_share):>7}"
              f"{(f'{c.mean_reasoning:.0f}' if c.mean_reasoning is not None else 'n/a'):>7}"
              f"{c.max_reasoning:>7}  {c.reasoning_zero}/{c.reasoning_nonzero}")

    print("\nDATED PERMASLUG(S) SERVED")
    for key in sorted(by_model):
        c = by_model[key]
        if not c.permaslugs:
            continue
        slugs = ", ".join(f"{s} x{n}" for s, n in sorted(c.permaslugs.items()))
        flags = []
        if len(c.permaslugs) > 1:
            flags.append("PERMASLUG DRIFT: one pin, more than one model version")
        if len(c.providers) > 1:
            flags.append("PROVIDER DRIFT: one pin served by more than one provider")
        flag = ("  <-- " + "; ".join(flags)) if flags else ""
        print(f"  {c.model:40s} {slugs}  [{', '.join(sorted(c.providers))}]{flag}")

    gaps = {k: v for k, v in by_model.items() if v.unresolved}
    if gaps:
        print("\nUNRESOLVED (counted in NO token sum - never as reasoning=0)")
        for k, v in sorted(gaps.items()):
            print(f"  {v.model:40s} pending={v.pending} missing={v.missing} "
                  f"errors={v.errors}")
    partial = {k: v for k, v in by_model.items()
               if v.reasoning_unreported or v.partially_reported}
    if partial:
        print("\nRESOLVED BUT NOT IN ANY SHARE (one side of it was never reported)")
        for k, v in sorted(partial.items()):
            print(f"  {v.model:40s} reasoning absent={v.reasoning_unreported}"
                  f"  completion absent={v.partially_reported}")

    if by_run:
        print("\nSECOND SOURCE - ids recorded ON a run record (exact attribution, "
              "no time join). Not pooled with the panel table above.")
        hdr3 = (f"{'run dir':66s}{'ids':>5}{'ok':>5}{'excl':>6}{'reason':>9}"
                f"{'compl':>9}{'share':>7}")
        print(hdr3)
        print("-" * len(hdr3))
        for name in sorted(by_run):
            c = by_run[name]
            print(f"{name[:65]:66s}{c.requests_logged:>5}{c.resolved:>5}"
                  f"{_excluded(c):>6}{c.reasoning_tokens:>9}"
                  f"{c.completion_tokens:>9}"
                  f"{_fmt_share(c.reasoning_share):>7}")
            for s, n in sorted(c.permaslugs.items()):
                print(f"    served by {s} x{n}  [{', '.join(sorted(c.providers))}]")

    if att is None:
        return
    print(f"\nPER-CELL ATTRIBUTION (bonus; ambiguous={att.ambiguous}, "
          f"unattributed={att.unattributed})")
    if att.overlapping_cells:
        print("  WINDOW OVERLAP between same-model cells - attribution for the "
              "overlapping span is AMBIGUOUS and was assigned to neither:")
        for d in sorted(set(att.overlapping_cells)):
            print(f"    {d}")
    if not att.per_cell:
        print("  (nothing attributable)")
        return
    hdr2 = (f"{'run dir':66s}{'ok':>5}{'excl':>6}{'reason':>9}{'compl':>9}"
            f"{'share':>7}  verdict")
    print(hdr2)
    print("-" * len(hdr2))
    for name in sorted(att.per_cell):
        c = att.per_cell[name]
        cell = att.cells.get(name)
        print(f"{name[:65]:66s}{c.resolved:>5}{_excluded(c):>6}"
              f"{c.reasoning_tokens:>9}"
              f"{c.completion_tokens:>9}{_fmt_share(c.reasoning_share):>7}"
              f"  {(cell.verdict if cell else '?')}")


def main(argv: Sequence[str]) -> int:
    ap = argparse.ArgumentParser(
        description="Measure per-model reasoning tokens from the proxy usage log "
                    "+ OpenRouter's generation ledger.")
    ap.add_argument("--sample", type=int, default=40,
                    help="ids to resolve per model, spread across its span "
                         "(0 = every id). Default 40.")
    ap.add_argument("--limit", type=int, default=400,
                    help="hard cap on HTTP lookups this invocation (cache hits "
                         "are free). Default 400.")
    ap.add_argument("--sleep", type=float, default=DEFAULT_SLEEP_S,
                    help="seconds between HTTP lookups.")
    ap.add_argument("--cache", default=None,
                    help="resolution cache JSONL (default runs/"
                         ".reasoning-census-cache.jsonl).")
    ap.add_argument("--no-cache", action="store_true",
                    help="neither read nor write the cache.")
    ap.add_argument("--log", action="append", default=[],
                    help="explicit usage log path (repeatable); disables discovery.")
    ap.add_argument("--extra-root", action="append", default=[],
                    help="extra directory to search for usage logs (repeatable).")
    ap.add_argument("--runs-root", default=str(REPO / "runs"))
    ap.add_argument("--lanes", default=",".join(DEFAULT_LANES))
    ap.add_argument("--no-attribute", action="store_true",
                    help="skip the per-cell join.")
    ap.add_argument("--no-from-results", action="store_true",
                    help="skip the second id source (agent.generation_ids on run "
                         "records).")
    ap.add_argument("--expect-model", action="append", default=[],
                    help="a model that SHOULD appear; absence is reported as an "
                         "unmeasurable gap (repeatable).")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(list(argv))

    logs = discover_logs([Path(p) for p in args.extra_root],
                         [Path(p) for p in args.log])
    if not logs:
        print("ERROR: no usage log found. The proxy writes "
              f"{proxy.USAGE_LOG}; pass --log or --extra-root.", file=sys.stderr)
        return 2

    records = read_records(logs)
    logged_counts: Dict[str, int] = {}
    for lf in logs:
        for m, n in lf.models.items():
            logged_counts[m] = logged_counts.get(m, 0) + n
        logged_counts["(no on-wire model)"] = (
            logged_counts.get("(no on-wire model)", 0) + lf.modelless)

    key = api_key()
    if not key:
        print("ERROR: OPENROUTER_API_KEY is not set and not in .env - the ledger "
              "cannot be read, and this tool will not guess a reasoning count.",
              file=sys.stderr)
        return 2

    picked = sample_records(records, args.sample)

    from_results: Dict[str, List[LogRecord]] = ({} if args.no_from_results
                                                else collect_result_ids(
                                                    Path(args.runs_root)))
    picked_results: Dict[str, List[LogRecord]] = {
        run: sample_records(rs, args.sample) for run, rs in from_results.items()}

    cache = GenCache(None if args.no_cache
                     else Path(args.cache) if args.cache else default_cache_path())

    def _progress(done: int, total: int) -> None:
        if not args.json:
            print(f"  ... {done}/{total} records walked", file=sys.stderr,
                  flush=True)

    all_picked = list(picked) + [r for rs in picked_results.values() for r in rs]
    facts, calls, skipped = resolve_all(
        all_picked, key, cache, limit=args.limit, sleep_s=args.sleep,
        progress=_progress)

    by_model = census_by_model(picked, facts, logged_counts)
    by_run: Dict[str, ModelCensus] = {}
    for run, rs in picked_results.items():
        c = ModelCensus(model=run, requests_logged=len(from_results[run]))
        for r in rs:
            f = facts.get(r.generation_id)
            if f is None:
                continue
            c.sampled += 1
            _absorb(c, f)
        by_run[run] = c

    att = None
    if not args.no_attribute:
        cells = load_cells(Path(args.runs_root),
                           [s for s in args.lanes.split(",") if s])
        att = attribute(picked, facts, cells)

    if args.json:
        print(json.dumps({
            "logs": [lf.as_dict() for lf in logs],
            "generation_ids_seen": len(records),
            "sampled": len(picked),
            "http_calls": calls,
            "cache_hits": cache.hits,
            "skipped_over_limit": skipped,
            "expected_models_absent": [
                m for m in args.expect_model
                if not any(m in lf.models for lf in logs)],
            "by_model": {k: v.as_dict() for k, v in sorted(by_model.items())},
            "by_run_record": {k: v.as_dict() for k, v in sorted(by_run.items())},
            "attribution": att.as_dict() if att else None,
        }, indent=2))
        return 0

    print_report(logs, by_model, att, calls=calls, cache_hits=cache.hits,
                 skipped=skipped, expected_models=args.expect_model,
                 by_run=by_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

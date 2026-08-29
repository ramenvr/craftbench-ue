"""Per-checkpoint measured states, read out of the graded L2 log.

Log parsing, not image work: ``graded_l2_log`` locates the run's L2 log and
``parse_checkpoint_states`` turns its lines into the measured value at each
checkpoint. It answers "what did the world actually look like at cp03", which is
what the run-summary card prints under each checkpoint.

This used to live beside the screenshot lane because captions were its first
consumer. It is kept here, on its own, because the measurement is useful with or
without pictures.

Read-only and never raises: every failure path returns an empty mapping, so a
pruned workdir or an unparseable log degrades to "no checkpoint lines".
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple


# The graded L2 editor log, relative to the run's recorded graded_workdir.
# workdir_retention's slim default KEEPS out/ whole, so this survives every
# retained graded run; a pruned/never-materialized workdir means no captions.
L2_LOG_RELPATH = ("out", "l2_pie.log")

# The base-class checkpoint breadcrumb (CraftBenchFunctionalTest.cpp::Tick,
# review-gated): "[CB-CP] idx=<n> t=<s>". Preferred over per-fixture lines —
# it fires for EVERY fixture, with the SCHEDULED checkpoint time.
_CB_CP_RE = re.compile(r"\[CB-CP\]\s+idx=(?P<idx>\d+)\s+t=(?P<t>\d+(?:\.\d+)?)")

# The per-fixture convention ("[POISON] idx=0 t=0.55 health=100.0 (…)",
# "[GLIDE] idx=2 t=2.10 speed=…"): generic "idx=<n> t=<s>", rest of the line
# is the measured state text.
_IDX_T_RE = re.compile(
    r"\bidx=(?P<idx>\d+)\s+t=(?P<t>\d+(?:\.\d+)?)[ \t]*(?P<rest>.*)")

@dataclass(frozen=True)
class CheckpointState:
    """One checkpoint's measured record from the graded L2 log.

    ``t`` is the checkpoint time in world-seconds (the [CB-CP] breadcrumb's
    scheduled time when present, else the fixture line's measured time);
    ``state`` is the per-fixture line's tail verbatim (``"health=100.0
    (A1=… )"``) — None when only the generic breadcrumb logged."""

    idx: int
    t: Optional[float]
    state: Optional[str]

def graded_l2_log(run_dir) -> Optional[Path]:
    """The GRADED run's L2 editor log, resolved via the run envelope's
    ``graded_workdir`` record -> ``out/l2_pie.log``, or None.

    Envelope precedence mirrors the report bridge (summary.json — the graded
    harness envelope — wins over result.json; an aura-product run's
    result.json is the TS driver's own record and must never be read past a
    present summary.json). Graceful absence everywhere: no envelope, corrupt
    envelope, no ``graded_workdir`` key (old runs), a pruned/slimmed-away
    workdir, or a missing log all return None — no captions, byte-identical
    page. Never raises."""
    try:
        run_dir = Path(run_dir)
        for name in ("summary.json", "result.json"):
            path = run_dir / name
            if not path.is_file():
                continue
            try:
                env = json.loads(path.read_text(encoding="utf-8",
                                                errors="replace"))
            except ValueError:
                return None  # corrupt preferred envelope: no caption, no guess
            if not isinstance(env, dict):
                return None
            gw = env.get("graded_workdir")
            if not gw:
                return None
            log = Path(str(gw)).joinpath(*L2_LOG_RELPATH)
            return log if log.is_file() else None
        return None
    except Exception:  # noqa: BLE001 — a caption source must never cost a page
        return None

def parse_checkpoint_states(text: str) -> Dict[int, "CheckpointState"]:
    """Per-checkpoint measured state parsed from L2 log text.

    Two line shapes feed one record per index: the base-class ``[CB-CP]``
    breadcrumb (preferred for ``t`` — it exists for every future fixture) and
    the per-fixture ``idx=<n> t=<s> <state…>`` convention (the only source of
    ``state`` text). First occurrence of an index wins on each channel — a
    replayed/duplicated log section never rewrites earlier checkpoints.
    Returns ``{}`` on no matches; never raises."""
    cb_t: Dict[int, float] = {}
    fixture: Dict[int, Tuple[float, Optional[str]]] = {}
    try:
        for line in str(text).splitlines():
            m = _CB_CP_RE.search(line)
            if m:
                idx = int(m.group("idx"))
                if idx not in cb_t:
                    cb_t[idx] = float(m.group("t"))
                continue
            m = _IDX_T_RE.search(line)
            if m:
                idx = int(m.group("idx"))
                if idx not in fixture:
                    rest = m.group("rest").strip() or None
                    fixture[idx] = (float(m.group("t")), rest)
        out: Dict[int, CheckpointState] = {}
        for idx in sorted(set(cb_t) | set(fixture)):
            fix_t, fix_state = fixture.get(idx, (None, None))
            t = cb_t.get(idx, fix_t)
            out[idx] = CheckpointState(idx=idx, t=t, state=fix_state)
        return out
    except Exception:  # noqa: BLE001 — malformed log text means "no captions"
        return {}

def checkpoint_states(run_dir) -> Dict[int, "CheckpointState"]:
    """The graded run's per-checkpoint measured states, or ``{}`` when the
    L2 log cannot be resolved/read/parsed. Read-only; never raises."""
    try:
        log = graded_l2_log(run_dir)
        if log is None:
            return {}
        return parse_checkpoint_states(
            log.read_text(encoding="utf-8", errors="replace"))
    except Exception:  # noqa: BLE001 — same law as the describer
        return {}

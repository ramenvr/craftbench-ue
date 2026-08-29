"""Wall-clock accounting for the runner's own phases.

WHY THIS EXISTS. ``report.json`` recorded exactly two kinds of duration: the
whole-verify ``duration_seconds`` and a per-layer ``duration_seconds`` that only
L1 and L2 ever populated. Everything between those — materializing the
substrate, the config overlay, the sandbox scan, applying the submission,
composing the report — was a single unattributed remainder, and L2I/L3/R2
reported no duration at all. Measured on eight kp- discrimination legs
(2026-07-30): L1 = 87.8% of the verify with sigma 0.4s, and the other ~20s was
un-attributable. You cannot decide what a lighter grading mode should trim
while 12% of the verify has no name.

THE ONE PROPERTY THAT MATTERS: **the block closes.** ``to_dict(total)`` always
emits an ``unaccounted`` entry computed as ``total - sum(spans)``, so the
phase block sums to the report's ``duration_seconds`` by construction. A phase
someone forgets to instrument shows up as a growing ``unaccounted``, not as a
silently-missing cost. That is the difference between an accounting and a
decoration.

USAGE (phases MUST NOT nest — see ``phase``)::

    pt = PhaseTimer()
    with pt.phase("stage_substrate"):
        ...
    with pt.phase("layers"):
        ...
    report.phases = pt.to_dict(total_seconds=elapsed)

Re-entering a name ACCUMULATES rather than overwrites, so a phase split across
two code sites (e.g. sandbox scan + the semantic config-lane validation) reports
one honest total.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Callable, Dict, Iterator, List, Tuple

# Key added by ``to_dict`` holding whatever wall time no span claimed. Never a
# phase name a caller may use — ``record`` rejects it.
UNACCOUNTED = "unaccounted"


class PhaseTimer:
    """Accumulates named, non-overlapping wall-clock spans.

    ``clock`` is injectable so tests drive it deterministically instead of
    sleeping. It must be monotonic — the spans are differences, and a wall clock
    that steps backwards would emit a negative phase.
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._totals: Dict[str, float] = {}
        self._order: List[str] = []

    def record(self, name: str, seconds: float) -> None:
        """Add ``seconds`` to the named phase (creating it on first use)."""
        if name == UNACCOUNTED:
            raise ValueError(
                f"{UNACCOUNTED!r} is derived by to_dict(); it cannot be recorded"
            )
        if name not in self._totals:
            self._totals[name] = 0.0
            self._order.append(name)
        self._totals[name] += seconds

    @contextmanager
    def phase(self, name: str) -> Iterator[None]:
        """Time a block and attribute it to ``name``.

        DO NOT NEST two phases: the inner span would be counted twice and the
        derived ``unaccounted`` would go negative to say so. Nesting is a
        modelling error, not a supported mode — split the outer phase instead.
        The span is recorded even when the body raises, so a grade that aborts
        mid-phase still accounts for the time it spent there.
        """
        t0 = self._clock()
        try:
            yield
        finally:
            self.record(name, self._clock() - t0)

    def spans(self) -> Tuple[Tuple[str, float], ...]:
        """Recorded (name, seconds) pairs in first-seen order, unrounded."""
        return tuple((n, self._totals[n]) for n in self._order)

    def total_recorded(self) -> float:
        return sum(self._totals.values())

    def to_dict(self, total_seconds: float, *, ndigits: int = 2) -> Dict[str, float]:
        """Rounded phase map plus the derived ``unaccounted`` remainder.

        ``total_seconds`` is the authoritative whole-verify duration (the
        report's own ``duration_seconds``), so the returned mapping sums to it.
        A NEGATIVE ``unaccounted`` is a real signal and is emitted as-is: it
        means spans overlapped (someone nested two phases) or that a caller
        passed a total smaller than the work it timed. Hiding it behind a clamp
        would turn a double-count into a plausible-looking number.
        """
        out = {n: round(v, ndigits) for n, v in self.spans()}
        out[UNACCOUNTED] = round(total_seconds - self.total_recorded(), ndigits)
        return out

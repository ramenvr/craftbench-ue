"""Tests for phase_timer.PhaseTimer and the report's `phases` block.

The contract under test is the one the block exists for: it CLOSES. Whatever
`to_dict` emits sums to the total it was handed, so an un-instrumented phase
shows up as a growing `unaccounted` rather than as cost that quietly vanished.
"""
import sys
import unittest
from pathlib import Path

_VERIFY = Path(__file__).resolve().parent.parent
if str(_VERIFY) not in sys.path:
    sys.path.insert(0, str(_VERIFY))

from phase_timer import UNACCOUNTED, PhaseTimer  # noqa: E402
from report import HostInfo, LayerReport, Report, report_from_dict  # noqa: E402


class FakeClock:
    """Deterministic monotonic clock — the timer never sleeps in tests."""

    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


class TestPhaseTimer(unittest.TestCase):
    def test_phase_records_elapsed(self):
        clock = FakeClock()
        pt = PhaseTimer(clock=clock)
        with pt.phase("build"):
            clock.advance(12.5)
        self.assertEqual(pt.spans(), (("build", 12.5),))

    def test_reentering_a_name_accumulates(self):
        """A phase split across two code sites reports ONE honest total."""
        clock = FakeClock()
        pt = PhaseTimer(clock=clock)
        with pt.phase("sandbox"):
            clock.advance(1.0)
        with pt.phase("layers"):
            clock.advance(5.0)
        with pt.phase("sandbox"):
            clock.advance(2.0)
        self.assertEqual(dict(pt.spans()), {"sandbox": 3.0, "layers": 5.0})
        # First-seen order is preserved, so the second sandbox span does not
        # reorder the block.
        self.assertEqual([n for n, _ in pt.spans()], ["sandbox", "layers"])

    def test_span_recorded_even_when_body_raises(self):
        """A grade that dies mid-phase still accounts for the time it spent."""
        clock = FakeClock()
        pt = PhaseTimer(clock=clock)
        with self.assertRaises(RuntimeError):
            with pt.phase("layers"):
                clock.advance(9.0)
                raise RuntimeError("boom")
        self.assertEqual(dict(pt.spans()), {"layers": 9.0})

    def test_block_closes_against_total(self):
        """THE contract: the emitted mapping sums to the total handed in."""
        clock = FakeClock()
        pt = PhaseTimer(clock=clock)
        with pt.phase("stage_substrate"):
            clock.advance(8.0)
        with pt.phase("layers"):
            clock.advance(140.0)
        d = pt.to_dict(total_seconds=164.0)
        self.assertAlmostEqual(sum(d.values()), 164.0, places=2)
        # The 16s nobody instrumented is NAMED, not dropped.
        self.assertAlmostEqual(d[UNACCOUNTED], 16.0, places=2)

    def test_unaccounted_present_even_with_no_phases(self):
        pt = PhaseTimer(clock=FakeClock())
        self.assertEqual(pt.to_dict(total_seconds=30.0), {UNACCOUNTED: 30.0})

    def test_overlap_surfaces_as_negative_rather_than_being_clamped(self):
        """Nesting double-counts; the block says so instead of looking plausible.

        A clamp here would turn a modelling error into a number a reader would
        trust, which is the exact failure this accounting exists to prevent.
        """
        clock = FakeClock()
        pt = PhaseTimer(clock=clock)
        with pt.phase("outer"):
            with pt.phase("inner"):
                clock.advance(10.0)
        d = pt.to_dict(total_seconds=10.0)
        self.assertLess(d[UNACCOUNTED], 0.0)

    def test_unaccounted_is_reserved(self):
        pt = PhaseTimer(clock=FakeClock())
        with self.assertRaises(ValueError):
            pt.record(UNACCOUNTED, 1.0)


def _report(**kw):
    base = dict(
        task_id="t0-sanity-log-on-beginplay",
        submission_sha="abc123",
        layers={"L1": LayerReport(status="pass", duration_seconds=144.5)},
        overall="pass",
        duration_seconds=164.0,
        ue_version="5.8",
        host=HostInfo(os="windows", arch="amd64"),
    )
    base.update(kw)
    return Report(**base)


class TestReportPhasesBlock(unittest.TestCase):
    def test_phases_omitted_when_absent(self):
        """Pre-existing reports must round-trip byte-identical."""
        self.assertNotIn("phases", _report().to_dict())

    def test_phases_serialized_and_round_trip(self):
        phases = {"layers": 144.5, "stage_substrate": 8.0, UNACCOUNTED: 11.5}
        d = _report(phases=phases, substrate_revision="deadbeef").to_dict()
        self.assertEqual(d["phases"], phases)
        rt = report_from_dict(d)
        self.assertEqual(rt.phases, phases)
        # substrate_revision used to round-trip to None (it was dropped by
        # report_from_dict), losing the FR-002 provenance anchor.
        self.assertEqual(rt.substrate_revision, "deadbeef")

    def test_render_text_shows_phases_and_layer_duration(self):
        text = _report(
            phases={"layers": 144.5, "stage_substrate": 8.0, UNACCOUNTED: 11.5}
        ).render_text()
        self.assertIn("phases", text)
        self.assertIn("stage_substrate", text)
        self.assertIn(UNACCOUNTED, text)
        # Per-layer duration is now visible on the layer line.
        self.assertIn("144.5s", text)

    def test_render_text_orders_phases_by_cost(self):
        text = _report(
            phases={"stage_substrate": 8.0, "layers": 144.5, UNACCOUNTED: 11.5}
        ).render_text()
        lines = [l.strip() for l in text.splitlines()]
        idx = {n: next(i for i, l in enumerate(lines) if l.startswith(n))
               for n in ("layers", "stage_substrate", UNACCOUNTED)}
        self.assertLess(idx["layers"], idx[UNACCOUNTED])
        self.assertLess(idx[UNACCOUNTED], idx["stage_substrate"])


if __name__ == "__main__":
    unittest.main()

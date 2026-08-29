"""Report schema: the R2 advisory block is carried but NON-GATING.

The certified ``overall`` is computed from the deterministic layers alone, so an
advisory score can never flip it (FR-020d). This proves it at the report layer:
the advisory round-trips, renders, and a gating advisory is refused at the door.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_VERIFY = _HERE.parent
if str(_VERIFY) not in sys.path:
    sys.path.insert(0, str(_VERIFY))

from report import HostInfo, LayerReport, Report, report_from_dict  # noqa: E402


def _report(overall: str, advisory=None, artifacts=None) -> Report:
    return Report(
        task_id="demo",
        submission_sha="a" * 64,
        layers={"L1": LayerReport(status="pass"), "L2I": LayerReport(status="pass")},
        overall=overall,
        duration_seconds=1.0,
        ue_version="5.7.4",
        host=HostInfo(os="darwin", arch="arm64"),
        r2_advisory=advisory,
        artifacts=artifacts if artifacts is not None else [],
    )


def _adv(score: float, gating=False) -> dict:
    return {"advisory_score": score, "confidence": 0.8, "gating": gating, "NON_GATING": not gating}


class TestReportAdvisory(unittest.TestCase):
    def test_advisory_absent_by_default(self):
        d = _report("pass").to_dict()
        self.assertNotIn("r2_advisory", d)

    def test_advisory_present_when_set_and_roundtrips(self):
        d = _report("pass", _adv(0.42)).to_dict()
        self.assertIn("r2_advisory", d)
        self.assertEqual(d["r2_advisory"]["advisory_score"], 0.42)
        back = report_from_dict(d)
        self.assertEqual(back.r2_advisory["advisory_score"], 0.42)
        self.assertEqual(back.overall, "pass")

    def test_advisory_does_not_appear_in_layers(self):
        # Structural non-gating: the advisory is never a layer, so the overall
        # computation (all layers pass) cannot see it.
        d = _report("pass", _adv(0.0)).to_dict()
        self.assertNotIn("r2_advisory", d["layers"])
        self.assertEqual(set(d["layers"]), {"L1", "L2I"})

    def test_gating_advisory_is_refused(self):
        with self.assertRaises(ValueError):
            _report("pass", _adv(1.0, gating=True))

    def test_render_marks_advisory_non_gating(self):
        text = _report("fail", _adv(0.9)).render_text()
        self.assertIn("overall   : FAIL", text)
        self.assertIn("NON-GATING", text)  # a high advisory next to a FAIL overall


class TestReportArtifacts(unittest.TestCase):
    """Optional "artifacts" key: omitted when empty (old JSON byte-identical),
    round-trips when present, tolerated when absent in old reports."""

    def test_empty_artifacts_omitted_from_json(self):
        d = _report("pass").to_dict()
        self.assertNotIn("artifacts", d)
        d = _report("pass", artifacts=[]).to_dict()
        self.assertNotIn("artifacts", d)

    def test_json_identical_to_pre_artifacts_shape(self):
        # A default report serializes to exactly the pre-artifacts key set.
        d = _report("pass").to_dict()
        self.assertEqual(
            set(d),
            {"task_id", "submission_sha", "layers", "overall",
             "duration_seconds", "ue_version", "host", "sandbox_violations"},
        )

    def test_artifacts_present_and_roundtrips(self):
        arts = ["artifacts/fps20_shot.png", "artifacts/shot.png"]
        d = _report("pass", artifacts=arts).to_dict()
        self.assertEqual(d["artifacts"], arts)
        back = report_from_dict(d)
        self.assertEqual(back.artifacts, arts)
        self.assertEqual(back.to_json(), _report("pass", artifacts=arts).to_json())

    def test_old_json_without_key_loads(self):
        d = _report("pass").to_dict()  # no "artifacts" key at all
        back = report_from_dict(d)
        self.assertEqual(back.artifacts, [])

    def test_render_counts_artifacts_when_present(self):
        text = _report("pass", artifacts=["artifacts/a.png", "artifacts/b.png"]).render_text()
        self.assertIn("artifacts : 2 file(s)", text)

    def test_render_silent_when_absent(self):
        self.assertNotIn("artifacts", _report("pass").render_text())


class TestReportSubstrateSource(unittest.TestCase):
    """Substrate provenance: "git-head" (certified default) vs "live"
    (--substrate-from-live / live-copy fallback — UNCERTIFIED). Optional so
    older reports / test literals stay byte-identical when unset."""

    def test_omitted_when_none(self):
        d = _report("pass").to_dict()
        self.assertNotIn("substrate_source", d)

    def test_present_and_roundtrips(self):
        for source in ("git-head", "live"):
            with self.subTest(source=source):
                r = _report("pass")
                r.substrate_source = source
                d = r.to_dict()
                self.assertEqual(d["substrate_source"], source)
                self.assertEqual(report_from_dict(d).substrate_source, source)

    def test_render_marks_live_as_uncertified(self):
        r = _report("pass")
        r.substrate_source = "live"
        text = r.render_text()
        self.assertIn("UNCERTIFIED", text)
        self.assertIn("live", text)

    def test_render_git_head_is_plain(self):
        r = _report("pass")
        r.substrate_source = "git-head"
        text = r.render_text()
        self.assertIn("git-head", text)
        self.assertNotIn("UNCERTIFIED", text)

    def test_old_json_without_key_loads(self):
        back = report_from_dict(_report("pass").to_dict())
        self.assertIsNone(back.substrate_source)


class TestReportGradedAt(unittest.TestCase):
    """The human-readable graded_at timestamp: leads the text render (so a run is
    legible at a glance, not just by content hash), round-trips in JSON when set, and
    is omitted — old-report byte-identical — when None (same contract as artifacts)."""

    def test_graded_at_omitted_when_none(self):
        self.assertNotIn("graded_at", _report("pass").to_dict())

    def test_graded_at_present_and_roundtrips(self):
        r = _report("pass")
        r.graded_at = "2026-07-09 14:12:34"
        d = r.to_dict()
        self.assertEqual(d["graded_at"], "2026-07-09 14:12:34")
        self.assertEqual(report_from_dict(d).graded_at, "2026-07-09 14:12:34")

    def test_render_leads_with_date_then_labels_the_hash(self):
        r = _report("pass")
        r.graded_at = "2026-07-09 14:12:34"
        lines = r.render_text().splitlines()
        # date/time sits RIGHT behind the task name; the opaque sha is a labelled line
        self.assertEqual(lines[1].split(":", 1)[0].strip(), "task_id")
        self.assertEqual(lines[2].split(":", 1)[0].strip(), "graded_at")
        self.assertIn("2026-07-09 14:12:34", lines[2])
        self.assertTrue(any("(sha256 of graded files)" in ln for ln in lines))

    def test_render_omits_date_line_when_none(self):
        self.assertNotIn("graded_at", _report("pass").render_text())

    def test_content_line_hidden_for_rejected_submission(self):
        r = _report("fail")
        r.submission_sha = "rejected"
        self.assertNotIn("sha256", r.render_text())


if __name__ == "__main__":
    unittest.main()


"""Tests for the OpenRouter ledger audit.

These pin the properties that make the tool trustworthy rather than its output
format. The whole point of replacing hand-computed cost is to stop reporting
numbers we cannot check, so every test here is about a way the tool could
quietly re-introduce that: a partial sum passed off as a total, a zero standing
in for an unknown, a 404 read as "free", or two model versions averaged into one
cell.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aura_rig.openrouter_cost import (  # noqa: E402
    LAG_GRACE_S, RunAudit, apply_to_result_json, audit_run, fetch_generation,
    read_run)


def _gen(cost=1.0, model="z-ai/glm-5.3-20260816", provider="Z.AI"):
    return {"data": {"total_cost": cost, "model": model, "provider_name": provider,
                     "native_tokens_prompt": 10, "native_tokens_completion": 2,
                     "native_tokens_reasoning": 1}}


def _fake_http(mapping):
    """(payload, status, error) keyed by the generation id inside the URL."""
    def get(url, api_key):
        gid = url.split("id=", 1)[1]
        return mapping.get(gid, (None, 404, None))
    return get


class TestFetch(unittest.TestCase):
    def test_ok_record_is_parsed(self):
        f = fetch_generation("g1", "k", http_get=_fake_http({"g1": (_gen(), 200, None)}))
        self.assertTrue(f.ok)
        self.assertEqual(f.total_cost, 1.0)
        self.assertEqual(f.model_permaslug, "z-ai/glm-5.3-20260816")
        self.assertEqual(f.provider_name, "Z.AI")

    def test_young_404_is_PENDING_not_missing(self):
        """Measured lag: a generation 404s ~3s after the call and resolves by ~60s.

        Calling that "missing" would invent a gap on every freshly finished run.
        """
        f = fetch_generation("nope", "k", age_s=5.0, http_get=_fake_http({}))
        self.assertEqual(f.status, "pending")

    def test_old_404_is_MISSING(self):
        f = fetch_generation("nope", "k", age_s=LAG_GRACE_S + 1, http_get=_fake_http({}))
        self.assertEqual(f.status, "missing")

    def test_a_404_never_becomes_a_zero_cost(self):
        """The failure this whole module exists to end."""
        f = fetch_generation("nope", "k", age_s=99999, http_get=_fake_http({}))
        self.assertIsNone(f.total_cost)

    def test_transport_error_is_reported_not_swallowed(self):
        def boom(url, api_key):
            return None, None, "URLError: unreachable"
        f = fetch_generation("g1", "k", http_get=boom)
        self.assertFalse(f.ok)
        self.assertIn("URLError", f.status)


class TestRunAudit(unittest.TestCase):
    def _audit(self, ids, mapping, age_s=99999):
        a = RunAudit(run_dir="r", generation_ids=ids)
        return audit_run(a, "k", age_s=age_s, http_get=_fake_http(mapping),
                         sleep=lambda _s: None)

    def test_fully_resolved_run_sums_the_provider_numbers(self):
        a = self._audit(["a", "b"], {"a": (_gen(0.25), 200, None),
                                     "b": (_gen(0.75), 200, None)})
        self.assertAlmostEqual(a.total_cost_usd, 1.0)
        self.assertFalse(a.drifted)

    def test_PARTIAL_resolution_yields_None_not_a_partial_sum(self):
        """A partial total under-reports while LOOKING complete — the worst shape.

        Two calls, one of which never resolves: reporting $0.25 here would be a
        published number that is wrong in the cheap direction, with nothing in the
        row to say so.
        """
        a = self._audit(["a", "missing"], {"a": (_gen(0.25), 200, None)})
        self.assertIsNone(a.total_cost_usd)
        self.assertEqual(a.unresolved, 1)

    def test_no_generation_ids_is_unauditable_not_free(self):
        a = self._audit([], {})
        self.assertIsNone(a.total_cost_usd)

    def test_version_drift_is_flagged(self):
        """One pin, two dated models = two systems averaged under one label."""
        a = self._audit(["a", "b"], {
            "a": (_gen(0.1, model="x-ai/grok-4.5-20260101"), 200, None),
            "b": (_gen(0.1, model="x-ai/grok-4.6-20260218"), 200, None)})
        self.assertTrue(a.drifted)
        self.assertEqual(len(a.model_versions), 2)

    def test_provider_drift_is_flagged_even_at_one_version(self):
        a = self._audit(["a", "b"], {
            "a": (_gen(0.1, provider="Fireworks"), 200, None),
            "b": (_gen(0.1, provider="Z.AI"), 200, None)})
        self.assertTrue(a.drifted)

    def test_pending_run_reports_pending_rather_than_a_number(self):
        a = self._audit(["a", "late"], {"a": (_gen(0.25), 200, None)}, age_s=1.0)
        self.assertEqual(a.pending, 1)
        self.assertIsNone(a.total_cost_usd)


class TestResultJson(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.rj = Path(self._tmp.name) / "result.json"

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, agent):
        self.rj.write_text(json.dumps({"overall": "PASS", "agent": agent}),
                           encoding="utf-8")

    def test_reads_ids_and_recorded_cost(self):
        self._write({"generation_ids": ["a", "b"], "cost_usd": 0.5})
        a = read_run(self.rj)
        self.assertEqual(a.generation_ids, ["a", "b"])
        self.assertEqual(a.recorded_cost_usd, 0.5)

    def test_legacy_run_without_ids_reads_as_empty_not_error(self):
        self._write({"cost_usd": None})
        a = read_run(self.rj)
        self.assertEqual(a.generation_ids, [])

    def test_apply_is_additive_and_never_touches_the_verdict(self):
        """A cost tool must not be able to damage a graded result."""
        self._write({"generation_ids": ["a"], "cost_usd": 0.5})
        audit = RunAudit(run_dir="r", generation_ids=["a"])
        audit_run(audit, "k", age_s=1, http_get=_fake_http({"a": (_gen(0.3), 200, None)}),
                  sleep=lambda _s: None)
        self.assertTrue(apply_to_result_json(self.rj, audit))

        d = json.loads(self.rj.read_text(encoding="utf-8"))
        self.assertEqual(d["overall"], "PASS")
        self.assertEqual(d["agent"]["cost_usd"], 0.5, "our own figure is preserved")
        self.assertAlmostEqual(d["agent"]["openrouter"]["total_cost_usd"], 0.3)
        self.assertEqual(d["agent"]["openrouter"]["model_versions"],
                         ["z-ai/glm-5.3-20260816"])

    def test_unreadable_file_is_a_skip_not_a_crash(self):
        self.rj.write_text("{not json", encoding="utf-8")
        self.assertIsNone(read_run(self.rj))


if __name__ == "__main__":
    unittest.main()

"""Tests for the reasoning census.

Most of these pin one property from different sides: the census must never let
"we could not find out" become a number. A pending 404, a missing record, a
provider that does not report the field, a call that reported one side of the
share and not the other, and a per-cell join that guesses when two windows
overlap are five ways the same lie gets told. The log-identity test pins the
same rule one step earlier: a whole log must not be dropped as a duplicate on a
claim nobody checked.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import reasoning_census as rc  # noqa: E402
from aura_rig.openrouter_cost import LAG_GRACE_S, GenerationFacts  # noqa: E402


def _gen(reasoning=100, completion=400):
    return {"data": {"total_cost": 0.5, "model": "x/y-20260810",
                     "provider_name": "P", "native_tokens_prompt": 9,
                     "native_tokens_completion": completion,
                     "native_tokens_reasoning": reasoning}}


def _http(mapping):
    """(payload, status, error) keyed by the id in the URL; unknown ids 404."""
    def get(url, api_key):
        return mapping.get(url.split("id=", 1)[1], (None, 404, None))
    return get


def _rec(gid, ts, model="m/one"):
    return rc.LogRecord(ts=ts, model=model, generation_id=gid, source="t")


class TestUnresolvedIsNotZero(unittest.TestCase):
    def test_pending_and_missing_contribute_to_no_token_sum(self):
        now = 1_000_000.0
        recs = [_rec("young", now - 1.0), _rec("old", now - 10 * LAG_GRACE_S)]
        facts, calls, _ = rc.resolve_all(
            recs, "k", rc.GenCache(None), limit=10, http_get=_http({}),
            sleep=lambda _s: None, now=now)
        self.assertEqual(calls, 2)
        self.assertEqual(facts["young"].status, "pending")
        self.assertEqual(facts["old"].status, "missing")

        c = rc.census_by_model(recs, facts, {"m/one": 2})["m/one"]
        self.assertEqual((c.pending, c.missing, c.unresolved), (1, 1, 2))
        self.assertEqual(c.reasoning_tokens, 0)
        self.assertEqual(c.reasoning_reported, 0)
        self.assertEqual(c.reasoning_zero, 0)
        self.assertIsNone(c.reasoning_share)
        self.assertIsNone(c.mean_reasoning)

    def test_reported_zero_and_unreported_are_different_counters(self):
        recs = [_rec("z", 1.0), _rec("u", 2.0)]
        facts, _, _ = rc.resolve_all(
            recs, "k", rc.GenCache(None), limit=10,
            http_get=_http({
                "z": (_gen(reasoning=0), 200, None),
                "u": ({"data": {"model": "x/y-20260810", "provider_name": "P",
                                "native_tokens_completion": 400}}, 200, None),
            }),
            sleep=lambda _s: None, now=10.0)
        c = rc.census_by_model(recs, facts, {"m/one": 2})["m/one"]
        self.assertEqual(c.resolved, 2)
        self.assertEqual(c.reasoning_zero, 1)
        self.assertEqual(c.reasoning_unreported, 1)
        self.assertEqual(c.reasoning_reported, 1)
        # The unreported call is in NEITHER sum, so the share stays paired.
        self.assertEqual(c.completion_tokens, 400)
        self.assertEqual(c.reasoning_share, 0.0)


    def test_reasoning_without_a_completion_is_in_neither_sum(self):
        """Counting one side of the share alone can push it past 100%."""
        recs = [_rec("pair", 1.0), _rec("half", 2.0)]
        facts, _, _ = rc.resolve_all(
            recs, "k", rc.GenCache(None), limit=10,
            http_get=_http({
                "pair": (_gen(reasoning=100, completion=400), 200, None),
                "half": ({"data": {"model": "x/y-20260810", "provider_name": "P",
                                   "native_tokens_reasoning": 500}}, 200, None),
            }),
            sleep=lambda _s: None, now=10.0)
        c = rc.census_by_model(recs, facts, {"m/one": 2})["m/one"]
        self.assertEqual(c.resolved, 2)
        self.assertEqual(c.partially_reported, 1)
        self.assertEqual(c.reasoning_reported, 1)
        self.assertEqual((c.reasoning_tokens, c.completion_tokens), (100, 400))
        self.assertEqual(c.reasoning_share, 0.25)

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc.print_report([], {"m/one": c}, None, calls=0, cache_hits=0,
                            skipped=0)
        self.assertIn("completion absent=1", out.getvalue())


class TestCache(unittest.TestCase):
    def test_pending_is_never_persisted_but_ok_is(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "cache.jsonl"
            cache = rc.GenCache(p)
            cache.put(GenerationFacts(generation_id="p", status="pending"))
            self.assertFalse(p.exists(), "a pending lookup froze into the cache")
            cache.put(GenerationFacts(generation_id="o", status="ok",
                                      native_tokens_reasoning=7,
                                      native_tokens_completion=9))
            reloaded = rc.GenCache(p)
            self.assertIsNone(reloaded.get("p"))
            f = reloaded.get("o")
            self.assertEqual((f.status, f.native_tokens_reasoning), ("ok", 7))

    def test_cached_ids_cost_no_http(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "cache.jsonl"
            rc.GenCache(p).put(GenerationFacts(generation_id="a", status="ok",
                                               native_tokens_reasoning=5,
                                               native_tokens_completion=10))

            def boom(url, api_key):  # any HTTP at all is the failure
                raise AssertionError("resolved a cached id over the network")

            facts, calls, _ = rc.resolve_all(
                [_rec("a", 1.0)], "k", rc.GenCache(p), limit=10,
                http_get=boom, sleep=lambda _s: None, now=10.0)
            self.assertEqual(calls, 0)
            self.assertEqual(facts["a"].native_tokens_reasoning, 5)


class TestAttribution(unittest.TestCase):
    def _cell(self, name, start, dur):
        return rc.Cell(run_dir=name, lane="unreal-mcp", task="t", model="m/one",
                       start_ts=start, duration_s=dur, verdict="pass")

    def test_record_inside_two_same_model_windows_is_ambiguous_not_assigned(self):
        a = self._cell("cellA", 0.0, 1000.0)
        b = self._cell("cellB", 500.0, 1000.0)
        rec = _rec("g", 600.0)
        facts = {"g": GenerationFacts(generation_id="g", status="ok",
                                      native_tokens_reasoning=50,
                                      native_tokens_completion=100)}
        att = rc.attribute([rec], facts, [a, b])
        self.assertEqual(att.ambiguous, 1)
        self.assertEqual(att.per_cell, {})
        self.assertEqual(set(att.overlapping_cells), {"cellA", "cellB"})

    def test_unambiguous_record_lands_on_its_cell(self):
        a = self._cell("cellA", 0.0, 100.0)
        b = self._cell("cellB", 5000.0, 100.0)
        rec = _rec("g", 200.0)  # inside A's window via the setup pad only
        facts = {"g": GenerationFacts(generation_id="g", status="ok",
                                      native_tokens_reasoning=50,
                                      native_tokens_completion=100)}
        att = rc.attribute([rec], facts, [a, b])
        self.assertEqual(att.ambiguous, 0)
        self.assertEqual(list(att.per_cell), ["cellA"])
        self.assertEqual(att.per_cell["cellA"].reasoning_tokens, 50)


class TestLogIdentity(unittest.TestCase):
    @staticmethod
    def _line(model):
        return json.dumps({"ts": 1.0, "model": model,
                           "generation_id": "g-" + model}) + "\n"

    def test_alias_means_the_bytes_matched_not_the_stat(self):
        """Two different logs can share a size and an mtime; a copy is the alias."""
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            a, b = d / "cb-anthropic-usage.jsonl", d / "cb-anthropic-usage-2.jsonl"
            copy = d / "cb-anthropic-usage-copy.jsonl"
            a.write_text(self._line("m/a"), encoding="utf-8")
            b.write_text(self._line("m/b"), encoding="utf-8")
            copy.write_bytes(a.read_bytes())
            self.assertEqual(a.stat().st_size, b.stat().st_size)
            st = a.stat()
            os.utime(b, ns=(st.st_atime_ns, st.st_mtime_ns))
            os.utime(copy, ns=(1_600_000_000 * 10 ** 9,) * 2)

            logs = rc.discover_logs(explicit=[a, b, copy])
            self.assertEqual(sorted(m for lf in logs for m in lf.models),
                             ["m/a", "m/b"])
            by_name = {lf.path.name: lf for lf in logs}
            self.assertEqual(by_name[a.name].aliases, [str(copy.resolve())])
            self.assertEqual(by_name[b.name].aliases, [])


class TestSampling(unittest.TestCase):
    def test_sample_spans_the_model_window_not_just_its_start(self):
        """A first-N sample would take one cell's calls and call them the model's."""
        recs = [_rec(f"g{i}", float(i)) for i in range(100)]
        picked = rc.sample_records(recs, 5)
        self.assertEqual(len(picked), 5)
        self.assertEqual((picked[0].ts, picked[-1].ts), (0.0, 99.0))
        gaps = [b.ts - a.ts for a, b in zip(picked, picked[1:])]
        self.assertTrue(all(g >= 20.0 for g in gaps), gaps)

    def test_zero_means_every_id(self):
        recs = [_rec(f"g{i}", float(i)) for i in range(7)]
        self.assertEqual(len(rc.sample_records(recs, 0)), 7)


if __name__ == "__main__":
    unittest.main()

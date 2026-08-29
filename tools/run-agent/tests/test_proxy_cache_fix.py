"""Unit tests for the cache-burn fixes in aura_rig.proxy.

Two craftbench-owned, Aura-independent fixes for the aura-agent token blowup:

  * cache_health(pu)        — flags a run whose server sent NO cache_control
                              (cache_read==0 AND cache_write==0 over >1 request),
                              the misconfig that re-sends the full prefix at full
                              input price every turn.
  * inject_cache_control()  — flag-gated proxy-side breakpoint injection so the
                              stable system+tools prefix actually caches on the
                              wire (models prod cost; OFF by default).

Fully offline: pure functions over dicts/bytes. No socket, no network.
"""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aura_rig import proxy  # noqa: E402


class TestCacheHealth(unittest.TestCase):
    def test_flags_the_no_cache_control_misconfig(self):
        # The exact shape the broken sonnet main loop produces.
        pu = {"requests": 11, "input_tokens": 727920, "output_tokens": 3028,
              "cache_read": 0, "cache_write": 0,
              "models": {"claude-sonnet-4-6": 11}}
        h = proxy.cache_health(pu)
        self.assertTrue(h["misconfigured"])
        self.assertEqual(h["cache_read"], 0)
        self.assertEqual(h["cache_write"], 0)
        self.assertEqual(h["hit_rate"], 0.0)

    def test_healthy_when_cache_is_read(self):
        pu = {"requests": 4, "input_tokens": 909, "output_tokens": 100,
              "cache_read": 21420, "cache_write": 22146,
              "models": {"claude-opus-4-7": 4}}
        h = proxy.cache_health(pu)
        self.assertFalse(h["misconfigured"])
        self.assertGreater(h["hit_rate"], 0.0)
        # hit_rate = cache_read / (input + cache_read + cache_write)
        self.assertAlmostEqual(h["hit_rate"], 21420 / (909 + 21420 + 22146), places=6)

    def test_single_request_is_not_misconfigured(self):
        # One request CAN'T demonstrate a cache miss (nothing to re-read yet).
        pu = {"requests": 1, "input_tokens": 5000, "output_tokens": 10,
              "cache_read": 0, "cache_write": 0, "models": {"claude-sonnet-4-6": 1}}
        self.assertFalse(proxy.cache_health(pu)["misconfigured"])

    def test_write_only_is_not_misconfigured(self):
        # First turn writes the cache; reads come later. Not a misconfig.
        pu = {"requests": 2, "input_tokens": 100, "output_tokens": 10,
              "cache_read": 0, "cache_write": 5000, "models": {"claude-opus-4-7": 2}}
        self.assertFalse(proxy.cache_health(pu)["misconfigured"])

    def test_empty_usage_is_safe(self):
        h = proxy.cache_health({})
        self.assertFalse(h["misconfigured"])
        self.assertEqual(h["hit_rate"], 0.0)


class TestInjectCacheControl(unittest.TestCase):
    def _ephemeral(self, block):
        return block.get("cache_control") == {"type": "ephemeral"}

    def test_str_system_becomes_block_with_breakpoint(self):
        body = json.dumps({
            "model": "claude-sonnet-4-6",
            "system": "You are Aura. " * 200,
            "messages": [{"role": "user", "content": "hi"}],
            "tools": [{"name": "a"}, {"name": "b"}, {"name": "c"}],
        }).encode()
        out = json.loads(proxy.inject_cache_control(body))
        # system str -> list with a cache_control breakpoint on the text block
        self.assertIsInstance(out["system"], list)
        self.assertTrue(self._ephemeral(out["system"][-1]))
        self.assertEqual(out["system"][-1]["type"], "text")
        # tools tail carries a breakpoint (caches ALL tool schemas as one prefix)
        self.assertTrue(self._ephemeral(out["tools"][-1]))
        # untouched earlier tools have no breakpoint
        self.assertNotIn("cache_control", out["tools"][0])

    def test_list_system_breakpoint_on_last_text_block(self):
        body = json.dumps({
            "system": [{"type": "text", "text": "preamble"},
                       {"type": "text", "text": "rules " * 100}],
            "tools": [{"name": "a"}],
            "messages": [{"role": "user", "content": "go"}],
        }).encode()
        out = json.loads(proxy.inject_cache_control(body))
        self.assertTrue(self._ephemeral(out["system"][-1]))
        self.assertNotIn("cache_control", out["system"][0])

    def test_breakpoint_on_last_message_block(self):
        body = json.dumps({
            "system": "sys",
            "tools": [{"name": "a"}],
            "messages": [
                {"role": "user", "content": "first"},
                {"role": "assistant", "content": [{"type": "text", "text": "ok"}]},
            ],
        }).encode()
        out = json.loads(proxy.inject_cache_control(body))
        last = out["messages"][-1]["content"][-1]
        self.assertTrue(self._ephemeral(last))

    def test_idempotent_does_not_stack_breakpoints(self):
        body = json.dumps({
            "system": [{"type": "text", "text": "s",
                        "cache_control": {"type": "ephemeral"}}],
            "tools": [{"name": "a", "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": "x"}],
        }).encode()
        out = json.loads(proxy.inject_cache_control(body))
        # still exactly one breakpoint on each — unchanged
        self.assertTrue(self._ephemeral(out["system"][-1]))
        self.assertTrue(self._ephemeral(out["tools"][-1]))

    def test_no_system_no_tools_returns_unchanged(self):
        body = json.dumps({"messages": [{"role": "user", "content": "hi"}]}).encode()
        self.assertEqual(proxy.inject_cache_control(body), body)

    def test_non_json_returns_unchanged(self):
        body = b"not json at all"
        self.assertEqual(proxy.inject_cache_control(body), body)

    def test_empty_returns_unchanged(self):
        self.assertEqual(proxy.inject_cache_control(b""), b"")


if __name__ == "__main__":
    unittest.main()

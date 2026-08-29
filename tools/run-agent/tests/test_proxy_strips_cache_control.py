"""The rolling breakpoint, and a remedy that did NOT work.

MEASURED 2026-08-26, reproduced from Claude Code's own captured request bodies.
The CLI rolls a cache breakpoint through the messages as the conversation grows:

    turn 1 (msgs=2):  cache_control on msg[0].blk[1]
    turn 2 (msgs=5):  cache_control on msg[3].blk[0]   <- msg[0] LOSES the key
    turn 3 (msgs=8):  cache_control on msg[6].blk[0]

msg[0]'s TEXT is byte-identical across all three (54,684 chars, verified). Only
the presence of the key moves. Anthropic, OpenAI and xAI treat that as metadata
and cached at 89-97%. deepseek and gemini measured 1.8% and 2.2% over 26 hours.

WHY THIS FILE EXISTS EVEN THOUGH THE REMEDY FAILED. Replaying the captured bodies
with the breakpoints stripped raised the absolute hit rate but did NOT restore
turn-to-turn caching: control 38.7% -> 38.5%, stripped 57.8% -> 57.5%. Turn 2
still gained nothing from turn 1, which IS the defect. So the strip is OFF by
default and these tests pin its behaviour for whoever picks this up next -- and
pin the default, because shipping an unproven behaviour change into a running
benchmark is the expensive mistake here, not leaving a knob unturned.

Stdlib only. No socket, no key, no tokens.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from aura_rig import proxy  # noqa: E402

CC = {"type": "ephemeral"}


def body(model="deepseek/deepseek-v4-pro-0813", mark_first=True) -> bytes:
    return json.dumps({
        "model": model,
        "system": [{"type": "text", "text": "S", "cache_control": CC}],
        "tools": [{"name": "t"}],
        "messages": [
            {"role": "user", "content": [
                dict({"type": "text", "text": "first"},
                     **({"cache_control": CC} if mark_first else {}))]},
            {"role": "assistant", "content": [{"type": "text", "text": "ok"}]},
        ],
    }).encode()


def marks(raw: bytes) -> int:
    return json.dumps(json.loads(raw)).count("cache_control")


class TestTheDefaultIsOff(unittest.TestCase):
    """The remedy is unproven. Off is the correct default for an unproven change
    to a benchmark that is mid-run."""

    def test_nothing_is_stripped_without_the_env(self):
        with mock.patch.object(proxy, "_NO_CC_MODELS", ()):
            self.assertEqual(body(), proxy.strip_cache_control(body()))

    def test_the_module_default_list_is_empty(self):
        src = (_ROOT / "aura_rig" / "proxy.py").read_text(encoding="utf-8")
        self.assertIn('"CB_PROXY_NO_CACHE_CONTROL", ""', src)


class TestWhenEnabledItStripsExactlyTheRightThings(unittest.TestCase):
    def setUp(self):
        self._p = mock.patch.object(proxy, "_NO_CC_MODELS", ("deepseek", "gemini"))
        self._p.start()
        self.addCleanup(self._p.stop)

    def test_every_breakpoint_goes(self):
        # Two in the fixture: the system block and the first message. The tools
        # entry carries none -- which mirrors the real capture, where the CLI
        # marked system[1], system[2] and one message block, and left all 27
        # tools unmarked.
        self.assertEqual(2, marks(body()))
        self.assertEqual(0, marks(proxy.strip_cache_control(body())))

    def test_it_strips_from_system_tools_and_messages_alike(self):
        out = json.loads(proxy.strip_cache_control(body()))
        self.assertNotIn("cache_control", out["system"][0])
        self.assertNotIn("cache_control", out["messages"][0]["content"][0])

    def test_the_content_itself_is_untouched(self):
        # The whole premise is that the TEXT never changed; only the key moved.
        # A strip that also perturbed text would break the prefix it is meant to
        # stabilise.
        out = json.loads(proxy.strip_cache_control(body()))
        self.assertEqual("first", out["messages"][0]["content"][0]["text"])
        self.assertEqual("S", out["system"][0]["text"])
        self.assertEqual([{"name": "t"}], out["tools"])

    def test_the_rolling_breakpoint_stops_changing_the_prefix(self):
        # The point of the remedy, stated as a property: two turns whose ONLY
        # difference is where the breakpoint sits must serialise identically once
        # stripped.
        a = proxy.strip_cache_control(body(mark_first=True))
        b = proxy.strip_cache_control(body(mark_first=False))
        self.assertEqual(json.loads(a)["messages"], json.loads(b)["messages"])

    def test_a_model_that_honours_breakpoints_is_left_alone(self):
        # Stripping here would destroy the 89-97% those backends actually get.
        for m in ("x-ai/grok-4.6", "openai/gpt-5.6-sol", "claude-sonnet-5"):
            self.assertEqual(body(m), proxy.strip_cache_control(body(m)), m)


class TestItNeverDamagesARequest(unittest.TestCase):
    def setUp(self):
        self._p = mock.patch.object(proxy, "_NO_CC_MODELS", ("deepseek",))
        self._p.start()
        self.addCleanup(self._p.stop)

    def test_a_body_with_no_breakpoints_comes_back_byte_identical(self):
        raw = json.dumps({"model": "deepseek/x", "messages": []}).encode()
        self.assertIs(raw, proxy.strip_cache_control(raw))

    def test_non_json_and_empty_bodies_pass_through(self):
        self.assertEqual(b"nope", proxy.strip_cache_control(b"nope"))
        self.assertEqual(b"", proxy.strip_cache_control(b""))

    def test_a_json_array_passes_through(self):
        self.assertEqual(b"[1,2]", proxy.strip_cache_control(b"[1,2]"))


class TestItIsWired(unittest.TestCase):
    def test_the_proxy_calls_it_on_outbound_messages(self):
        src = (_ROOT / "aura_rig" / "proxy.py").read_text(encoding="utf-8")
        self.assertIn("body = strip_cache_control(body)", src)

    def test_it_is_gated_on_the_openrouter_upstream(self):
        src = (_ROOT / "aura_rig" / "proxy.py").read_text(encoding="utf-8")
        i = src.index("body = strip_cache_control(body)")
        self.assertIn('up.path_prefix == "/api"', src[max(0, i - 400):i])


if __name__ == "__main__":
    unittest.main()

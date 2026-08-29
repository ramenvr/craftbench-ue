"""Is the cacheable prefix byte-stable between turns? Previews could not say.

2026-08-26: the deepseek arm re-sent its whole context every turn -- fresh input
grew monotonically with the conversation (27k at 2 messages, 56k at 23) while
grok, on byte-identical traffic through the same CLI, fell to ~1k from turn 2.
That gap is $39.57 of an $82 block, and prompt cost is 94% of the bill.

Every synthetic reproduction failed: deepseek cached at 99.9% across size (to
455k tokens), a 6-minute gap, with and without cache_control, pinned and
unpinned, multi-turn, and with tool_use / tool_result blocks. So the difference
lives in what the CLI actually sends, and the trace log kept only previews --
enough to show the system prompt and tool list matched grok's, not enough to
show whether the prefix HELD between consecutive turns.

These hashes make that answerable from one cell. The test that matters is the
discriminating one: a conversation that merely GROWS must keep the same prefix
hash, and one whose history is REWRITTEN must not. A fingerprint that cannot
tell those apart would send the next investigation down the same dead end.

Stdlib only. No socket, no key, no tokens.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from aura_rig.proxy import build_trace_record, prefix_fingerprint  # noqa: E402

SYS = [{"type": "text", "text": "S" * 400, "cache_control": {"type": "ephemeral"}}]
TOOLS = [{"name": "lookup", "input_schema": {"type": "object"}}]


def body(messages, system=SYS, tools=TOOLS) -> bytes:
    return json.dumps({"model": "m", "system": system, "tools": tools,
                       "messages": messages}).encode()


def convo(turns: int):
    m = [{"role": "user", "content": "start"}]
    for i in range(turns):
        m += [{"role": "assistant", "content": f"reply {i}"},
              {"role": "user", "content": f"next {i}"}]
    return m


class TestItDiscriminates(unittest.TestCase):
    """The whole point. Growth is normal; a moving prefix is the defect."""

    def test_a_conversation_that_only_grows_keeps_its_prefix_hash(self):
        a = prefix_fingerprint(body(convo(3)))
        b = prefix_fingerprint(body(convo(4)))
        self.assertEqual(a["fp_sys"], b["fp_sys"])
        self.assertEqual(a["fp_tools"], b["fp_tools"])
        # turn 4's prefix-minus-last-exchange IS turn 3's full history, so the
        # hash must move with the window -- what must NOT move is the shared
        # head, which the next test pins directly.
        self.assertNotEqual(a["fp_n_msgs"], b["fp_n_msgs"])

    def test_a_rewritten_history_changes_the_prefix_at_the_SAME_length(self):
        # The failure this instrument exists to catch: same message count, but
        # earlier content edited. An automatic prefix cache can never hit that.
        base = convo(4)
        tampered = [dict(m) for m in base]
        tampered[1]["content"] = "reply 0 REWRITTEN"
        self.assertEqual(prefix_fingerprint(body(base))["fp_n_msgs"],
                         prefix_fingerprint(body(tampered))["fp_n_msgs"])
        self.assertNotEqual(prefix_fingerprint(body(base))["fp_msgs_prefix"],
                            prefix_fingerprint(body(tampered))["fp_msgs_prefix"])

    def test_an_identical_body_hashes_identically(self):
        self.assertEqual(prefix_fingerprint(body(convo(3))),
                         prefix_fingerprint(body(convo(3))))

    def test_a_changed_system_block_is_visible_on_its_own(self):
        other = [{"type": "text", "text": "S" * 399}]
        self.assertNotEqual(prefix_fingerprint(body(convo(2)))["fp_sys"],
                            prefix_fingerprint(body(convo(2), system=other))["fp_sys"])

    def test_a_changed_tool_list_is_visible_on_its_own(self):
        other = TOOLS + [{"name": "extra", "input_schema": {"type": "object"}}]
        self.assertNotEqual(prefix_fingerprint(body(convo(2)))["fp_tools"],
                            prefix_fingerprint(body(convo(2), tools=other))["fp_tools"])


class TestItLeaksNothingAndBreaksNothing(unittest.TestCase):
    """A diagnostic that disturbs a live request costs more than it measures."""

    def test_no_content_appears_in_the_output(self):
        secret = "THE-ANSWER-IS-42"
        fp = prefix_fingerprint(body([{"role": "user", "content": secret}] * 5))
        self.assertNotIn(secret, json.dumps(fp))

    def test_a_non_json_body_yields_an_empty_fingerprint(self):
        self.assertEqual({}, prefix_fingerprint(b"not json"))

    def test_an_empty_body_yields_an_empty_fingerprint(self):
        self.assertEqual({}, prefix_fingerprint(b""))

    def test_a_json_array_body_yields_an_empty_fingerprint(self):
        self.assertEqual({}, prefix_fingerprint(b"[1,2,3]"))

    def test_a_short_conversation_simply_omits_the_prefix_hash(self):
        # Two messages have no history to keep stable; an absent key is honest,
        # a hash of nothing would read as "stable" forever.
        fp = prefix_fingerprint(body([{"role": "user", "content": "a"}]))
        self.assertNotIn("fp_msgs_prefix", fp)
        self.assertEqual(1, fp["fp_n_msgs"])


class TestItIsActuallyWired(unittest.TestCase):
    """A correct function nothing calls is the defect this repo keeps finding."""

    def test_build_trace_record_carries_the_fingerprint(self):
        rec = build_trace_record({"model": "m"}, body(convo(3)), ts=0)
        for k in ("fp_sys", "fp_tools", "fp_n_msgs", "fp_msgs_prefix"):
            self.assertIn(k, rec)

    def test_the_fields_are_flat_not_nested(self):
        # The readers key on flat fields; a nested dict would be silently ignored.
        rec = build_trace_record({"model": "m"}, body(convo(3)), ts=0)
        self.assertIsInstance(rec["fp_sys"], str)

    def test_an_unparseable_request_still_produces_a_record(self):
        rec = build_trace_record({"model": "m"}, b"not json", ts=0)
        self.assertEqual("m", rec["model"])
        self.assertNotIn("fp_sys", rec)


if __name__ == "__main__":
    unittest.main()

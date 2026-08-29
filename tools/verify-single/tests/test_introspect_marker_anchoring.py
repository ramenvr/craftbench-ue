"""The verdict-block markers must be END-OF-LINE anchored, or a submission can
delete itself from the pass-rate denominator by choosing a filename.

THE HOLE THIS PINS (found 2026-08-12 by the kp- salvage audit;
live on main until the fix landed alongside these tests).

`parse_introspect_verdict` extracts the L2I verdict between two markers. The
block is emitted as three separate print()/unreal.log() calls, so in a real log
each marker TERMINATES its line and the payload between them is a single line of
`json.dumps` output. Any other occurrence of the END marker is therefore INSIDE
that payload -- inside a string the SUBMISSION controls, because every check
detail quotes asset paths and names.

With the previous unanchored pattern -- `START \s* (?P<body>.*?) \s* END` -- the
non-greedy body stopped at the FIRST END-shaped run of characters. An agent that
named an asset `CRAFTBENCH-INTROSPECT-JSON-END` truncated the block mid-JSON:

    parse fails -> ParsedIntrospect(found=False)
                -> L2I status "error"
                -> run_task.harness_error_reasons -> HARNESS-ERROR, exit 7
                -> NON-GRADED (adapters.base.GRADED_VERDICTS allowlists 0/1 only)

i.e. a submission that could not solve the task left the denominator entirely,
by picking a filename. `finditer` + last-match does not save it: the block is
emitted twice (stdout and the UE log) and BOTH copies carry the same poisoned
payload, so every match truncates.

This is precisely the denominator-opt-out class `build_lock.py` was designed to
refuse ("could not take the lock -> non-graded" was rejected for exactly this
reason). The rule these tests defend is the repo's: a non-agent condition must
never reach a graded verdict, and an agent-chosen submission property must never
ESCAPE one.

The poisoned payload is still perfectly valid JSON -- the marker is just a
substring of a value -- so once the anchor skips it, the run grades normally and
the agent takes the FAIL it earned. That is the assertion that matters below:
not merely "no crash", but `found=True` AND `all_passed=False`.
"""
import sys
import unittest
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
_VERIFY = _TESTS.parent

sys.path.insert(0, str(_VERIFY))

from layers.l2_introspect import (  # noqa: E402
    INTEGRITY_JSON_END,
    INTEGRITY_JSON_START,
    INTROSPECT_JSON_END,
    INTROSPECT_JSON_START,
    parse_introspect_verdict,
)

# A real UE log line prefix. It sits BEFORE the marker, never after -- which is
# why anchoring on end-of-line is safe for genuine output.
PRE = "[2026.08.12-10.00.00:000][  2]LogPython: "


def _block(payload, start=INTROSPECT_JSON_START, end=INTROSPECT_JSON_END, prefix=PRE):
    return "\n".join([prefix + start, prefix + payload, prefix + end, ""])


class TestVerdictMarkerAnchoring(unittest.TestCase):
    def test_a_normal_verdict_block_still_parses(self):
        """The anchor must not break ordinary output -- the regression risk."""
        text = _block('{"checks": [{"id": "a", "passed": true, "detail": "ok"}]}')
        parsed = parse_introspect_verdict(text)
        self.assertTrue(parsed.found)
        self.assertEqual(1, parsed.total)
        self.assertTrue(parsed.all_passed)

    def test_block_parses_without_a_log_prefix(self):
        """Scripts also print() the block bare, with no UE decoration."""
        text = _block('{"checks": [{"id": "a", "passed": true, "detail": "ok"}]}', prefix="")
        parsed = parse_introspect_verdict(text)
        self.assertTrue(parsed.found)
        self.assertTrue(parsed.all_passed)

    def test_end_marker_inside_a_detail_string_does_not_truncate(self):
        """THE HOLE. An agent-chosen asset name must not void the verdict.

        Asserts the submission stays GRADED and keeps its FAIL -- not merely
        that nothing crashed. found=False here would mean exit 7 / NON-GRADED.
        """
        payload = (
            '{"checks": [{"id": "bp_pawn_present", "passed": false,'
            ' "detail": "/Game/Tasks/t/' + INTROSPECT_JSON_END + '"}]}'
        )
        parsed = parse_introspect_verdict(_block(payload))
        self.assertTrue(
            parsed.found,
            "a submission named an asset after the END marker and escaped the "
            "denominator: the block truncated, L2I reports 'error', and "
            "run_task routes that to HARNESS-ERROR (exit 7, NON-GRADED)",
        )
        self.assertEqual(1, parsed.total)
        self.assertFalse(parsed.all_passed, "the failing check must still count as a FAIL")

    def test_start_marker_inside_a_detail_string_does_not_shift_the_block(self):
        """The symmetric attack: poison the START marker instead."""
        payload = (
            '{"checks": [{"id": "x", "passed": false,'
            ' "detail": "/Game/Tasks/t/' + INTROSPECT_JSON_START + '"}]}'
        )
        parsed = parse_introspect_verdict(_block(payload))
        self.assertTrue(parsed.found)
        self.assertFalse(parsed.all_passed)

    def test_both_markers_poisoned_at_once(self):
        payload = (
            '{"checks": [{"id": "x", "passed": false, "detail": "'
            + INTROSPECT_JSON_START + " " + INTROSPECT_JSON_END + '"}]}'
        )
        parsed = parse_introspect_verdict(_block(payload))
        self.assertTrue(parsed.found)
        self.assertFalse(parsed.all_passed)

    def test_last_block_wins_when_several_are_emitted(self):
        """The block really is emitted twice (stdout + unreal.log)."""
        first = _block('{"checks": [{"id": "a", "passed": false, "detail": "old"}]}')
        second = _block('{"checks": [{"id": "a", "passed": true, "detail": "new"}]}')
        parsed = parse_introspect_verdict(first + second)
        self.assertTrue(parsed.found)
        self.assertTrue(parsed.all_passed, "the LAST block must win")

    def test_poisoned_payload_in_both_emitted_copies(self):
        """Why finditer+last-match is not itself a defence.

        Both copies carry the same submission-chosen name, so under the old
        pattern every match truncated and the last one was as broken as the
        first.
        """
        payload = (
            '{"checks": [{"id": "x", "passed": false,'
            ' "detail": "' + INTROSPECT_JSON_END + '"}]}'
        )
        parsed = parse_introspect_verdict(_block(payload) + _block(payload))
        self.assertTrue(parsed.found)
        self.assertFalse(parsed.all_passed)


class TestIntegrityMarkerAnchoring(unittest.TestCase):
    """The asset-integrity preamble shares the mechanism and the exposure.

    It reports on SUBMITTED asset paths, so its detail strings are equally
    agent-controlled.
    """

    def test_integrity_markers_are_anchored_too(self):
        from layers.l2_introspect import _INTEGRITY_BLOCK_RE

        payload = (
            '{"checks": [{"id": "asset_integrity", "passed": false,'
            ' "detail": "/Game/Tasks/t/' + INTEGRITY_JSON_END + '"}]}'
        )
        text = _block(payload, start=INTEGRITY_JSON_START, end=INTEGRITY_JSON_END)
        matches = list(_INTEGRITY_BLOCK_RE.finditer(text))
        self.assertTrue(matches, "the integrity block must still be found")
        body = matches[-1].group("body")
        self.assertIn(
            INTEGRITY_JSON_END,
            body,
            "the poisoned marker belongs INSIDE the captured body -- if it is "
            "absent the regex truncated there, which is the hole",
        )


if __name__ == "__main__":
    unittest.main()

"""Unit tests for driver.tool_auth_health — detect the Aura subscription-401 that
silently blocks every MCP tool and masquerades as NO_DELIVERABLE.

Each Aura MCP tool is wrapped by @requires_subscription; on a non-200 validation
it returns {"error": "Subscription validation request failed with status 401"}
as a NORMAL output (isError=false) WITHOUT running the tool body. The guard flags
a run as blocked ONLY when EVERY completed tool call is such a 401 — a lone
transient 401 among successes (observed even in passing runs) must NOT block.

Fully offline: pure function over the DriveResult.calls shape.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aura_rig import driver  # noqa: E402

_401 = '{"error": "Subscription validation request failed with status 401"}'


def _call(name, output):
    return {"seq": 1, "name": name, "input": {}, "output": output,
            "t_start": 0.0, "t_end": 0.0}


def _auth_out():
    return {"content": [{"type": "text", "text": _401}],
            "structuredContent": {"result": _401}, "isError": False}


def _ok_out(text="did the thing"):
    return {"content": [{"type": "text", "text": text}], "isError": False}


class TestToolAuthHealth(unittest.TestCase):
    def test_all_calls_401_is_blocked(self):
        # Mirrors the real opus/gas NO_DELIVERABLE runs: every completed call 401s.
        calls = [_call("get_unreal_context", _auth_out()),
                 _call("grep", _auth_out()),
                 _call("edit_cpp_file", _auth_out())]
        h = driver.tool_auth_health(calls)
        self.assertTrue(h["blocked"])
        self.assertEqual(h["tool_calls"], 3)
        self.assertEqual(h["auth_error_calls"], 3)
        self.assertIn("Subscription validation", h["sample_error"])

    def test_lone_transient_401_among_successes_not_blocked(self):
        # Mirrors a real PASSing run: 1 of 13 calls 401'd, the rest succeeded.
        calls = [_call("grep", _ok_out()) for _ in range(12)]
        calls.insert(5, _call("get_unreal_context", _auth_out()))
        h = driver.tool_auth_health(calls)
        self.assertFalse(h["blocked"])
        self.assertEqual(h["auth_error_calls"], 1)
        self.assertEqual(h["tool_calls"], 13)

    def test_zero_tool_calls_not_blocked(self):
        h = driver.tool_auth_health([])
        self.assertFalse(h["blocked"])
        self.assertEqual(h["tool_calls"], 0)
        self.assertIsNone(h["sample_error"])

    def test_healthy_run_not_blocked(self):
        calls = [_call("edit_cpp_file", _ok_out()), _call("grep", _ok_out())]
        h = driver.tool_auth_health(calls)
        self.assertFalse(h["blocked"])
        self.assertEqual(h["auth_error_calls"], 0)

    def test_benign_tool_error_is_not_auth_error(self):
        # The last GOOD run had this exact benign error — must NOT count as auth.
        benign = {"content": [{"type": "text",
                  "text": "Error executing tool grep: grep() got an unexpected keyword argument -A"}],
                  "isError": True}
        calls = [_call("grep", benign)]
        h = driver.tool_auth_health(calls)
        self.assertFalse(h["blocked"])
        self.assertEqual(h["auth_error_calls"], 0)

    def test_structured_content_only_marker_detected(self):
        out = {"structuredContent": {"result": _401}}
        h = driver.tool_auth_health([_call("edit_cpp_file", out)])
        self.assertTrue(h["blocked"])
        self.assertEqual(h["auth_error_calls"], 1)

    def test_incomplete_calls_without_output_are_not_counted(self):
        # A started-but-not-returned call (output None) isn't a completed call.
        calls = [_call("edit_cpp_file", _auth_out()), _call("grep", None)]
        h = driver.tool_auth_health(calls)
        self.assertEqual(h["tool_calls"], 1)   # only the one with output
        self.assertTrue(h["blocked"])


class TestEntitlementRefusalShapes(unittest.TestCase):
    """The 401 marker is only ONE of three ways @requires_subscription refuses a
    call. The commonest — an expired free trial — comes back HTTP 200 with the
    route's own sentence, so keying on the 401 alone scored a mid-drive account
    lapse as the MODEL's failure, and with writes that landed before the lapse it
    could reach a GRADED FAIL — a non-agent condition inside a pass-rate
    denominator, which is the repo's cardinal invariant (FAILURE-LOG 2026-08-06).
    """

    EXPIRED_TRIAL = ('{"error": "No active subscription found: user must have an '
                     'active subscription or free trial to use MCP tools. Ask the '
                     'user to go to the settings in Aura to manage their '
                     'subscription."}')
    NO_SESSION = ('{"error": "No valid session token found. Please ensure you are '
                  'logged in."}')

    def _blocked_out(self, err):
        return {"content": [{"type": "text", "text": err}], "isError": False}

    def test_expired_trial_refusals_are_blocked(self):
        calls = [_call("edit_cpp_file", self._blocked_out(self.EXPIRED_TRIAL)),
                 _call("grep", self._blocked_out(self.EXPIRED_TRIAL))]
        h = driver.tool_auth_health(calls)
        self.assertTrue(h["blocked"])
        self.assertEqual(h["auth_error_calls"], 2)
        self.assertIn("No active subscription", h["sample_error"])

    def test_missing_session_refusals_are_blocked(self):
        h = driver.tool_auth_health(
            [_call("edit_cpp_file", self._blocked_out(self.NO_SESSION))])
        self.assertTrue(h["blocked"])
        self.assertIn("No valid session token", h["sample_error"])

    def test_mixed_refusal_shapes_still_block(self):
        calls = [_call("grep", _auth_out()),
                 _call("edit_cpp_file", self._blocked_out(self.EXPIRED_TRIAL))]
        h = driver.tool_auth_health(calls)
        self.assertTrue(h["blocked"])
        self.assertEqual(h["auth_error_calls"], 2)

    def test_lone_expired_trial_among_successes_not_blocked(self):
        # Same all-or-nothing rule as the 401: one refusal among successes is a
        # transient, not a dead account.
        calls = [_call("grep", _ok_out()) for _ in range(5)]
        calls.insert(2, _call("edit_cpp_file", self._blocked_out(self.EXPIRED_TRIAL)))
        h = driver.tool_auth_health(calls)
        self.assertFalse(h["blocked"])
        self.assertEqual(h["auth_error_calls"], 1)

    def test_the_marker_strings_are_pinned(self):
        # Until 2026-08-28 this cross-checked driver's list against the
        # pre-drive stack gate's ACCOUNT_BLOCK_MARKERS, because drift between
        # the two is exactly how the gate learned to name a block the
        # post-drive check could not see. That gate was part of the
        # proprietary bring-up and is not in the open-source release, so there
        # is no second list left to drift from -- the strings themselves are
        # now what is pinned, since they are what the SERVER sends.
        for m in ("No active subscription", "No valid session token"):
            self.assertIn(m, driver._TOOL_BLOCK_MARKERS)


if __name__ == "__main__":
    unittest.main()

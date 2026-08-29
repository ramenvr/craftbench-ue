"""exit_status: naming an otherwise opaque exit code.

Motivated by a real run (2026-07-25) whose recorded verdict was the bare string
`exit3221225794`. Nothing in the repo said that is 0xC0000142
STATUS_DLL_INIT_FAILED; working it out took a manual hex conversion plus a
process-sampler cross-check. The decoder is DIAGNOSTIC ONLY — no verdict may
depend on it — so these tests pin the strings, not any grading behaviour.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aura_rig.exit_status import annotate_exit, decode_exit  # noqa: E402


class TestDecodeExit(unittest.TestCase):
    def test_the_real_incident_code_is_named(self):
        d = decode_exit(3221225794)
        self.assertIn("0xC0000142", d)
        self.assertIn("STATUS_DLL_INIT_FAILED", d)

    def test_access_violation(self):
        self.assertIn("ACCESS_VIOLATION", decode_exit(0xC0000005))

    def test_unknown_ntstatus_still_gets_its_hex(self):
        # The hex form is the searchable part, so an unmapped NTSTATUS must not
        # silently decode to None.
        d = decode_exit(0xC0000123)
        self.assertIsNotNone(d)
        self.assertIn("0xC0000123", d)

    def test_negative_ntstatus_is_normalised(self):
        # Some paths report the signed 32-bit form of the same value.
        self.assertEqual(decode_exit(-1073741502), decode_exit(0xC0000142))

    def test_l1_sentinels_are_posix_not_hex(self):
        # 124/127 are sentinels l1_build synthesises. Hex-decoding them would
        # actively mislead, so they must resolve to their POSIX meaning.
        self.assertIn("timeout", decode_exit(124))
        self.assertIn("could not be executed", decode_exit(127))
        for code in (124, 127):
            self.assertNotIn("0x", decode_exit(code))

    def test_signals(self):
        self.assertIn("signal 9", decode_exit(137))

    def test_success_and_ordinary_codes_are_silent(self):
        # So a caller can annotate unconditionally without noise on the happy path.
        self.assertIsNone(decode_exit(0))
        self.assertIsNone(decode_exit(1))
        self.assertIsNone(decode_exit(None))


class TestAnnotateExit(unittest.TestCase):
    def test_wraps_in_parens_when_meaningful(self):
        self.assertTrue(annotate_exit(3221225794).startswith(" ("))
        self.assertTrue(annotate_exit(3221225794).endswith(")"))

    def test_empty_when_nothing_to_say(self):
        # f"exit={rc}{annotate_exit(rc)}" must stay clean for 0 and 1.
        self.assertEqual(annotate_exit(0), "")
        self.assertEqual(annotate_exit(1), "")
        self.assertEqual(annotate_exit(None), "")

    def test_is_pure(self):
        self.assertEqual(annotate_exit(124), annotate_exit(124))


if __name__ == "__main__":
    unittest.main()

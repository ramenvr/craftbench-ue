"""Unit tests for l1_build's UE 5.8 build-tuning flags (UBA + parallelism cap)."""
import os
import unittest
from unittest import mock

from layers import l1_build


class TestMaxParallelActionsArgs(unittest.TestCase):
    def test_unset_means_no_cap(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CRAFTBENCH_L1_MAX_PARALLEL", None)
            self.assertEqual(l1_build._max_parallel_actions_args(), [])

    def test_positive_int_emits_flag(self):
        with mock.patch.dict(os.environ, {"CRAFTBENCH_L1_MAX_PARALLEL": "4"}, clear=False):
            self.assertEqual(l1_build._max_parallel_actions_args(), ["-MaxParallelActions=4"])

    def test_zero_and_negative_and_garbage_are_no_cap(self):
        for v in ("0", "-2", "abc", "  "):
            with mock.patch.dict(os.environ, {"CRAFTBENCH_L1_MAX_PARALLEL": v}, clear=False):
                self.assertEqual(l1_build._max_parallel_actions_args(), [],
                                 msg=f"value {v!r} should mean no cap")


if __name__ == "__main__":
    unittest.main()

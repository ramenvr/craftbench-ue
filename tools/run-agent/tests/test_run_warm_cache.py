"""run.py's warm-cache forwarding — and the mutual exclusion that makes it work.

Until 2026-08-03 run.py had NO warm-cache handling, so `cb eval` on every
baseline backend built COLD unconditionally while the flag reported success. A
Sonnet-5 t0 eval spent 87.2s of its 100.6s grade rebuilding what the slot
already held.
"""
import os
import sys
import unittest
from pathlib import Path

_RUN_AGENT = Path(__file__).resolve().parent.parent
if str(_RUN_AGENT) not in sys.path:
    sys.path.insert(0, str(_RUN_AGENT))

import run as run_mod  # noqa: E402


class TestWarmCacheForwarding(unittest.TestCase):
    def setUp(self):
        self._prev = os.environ.get("CB_WARM_CACHE")

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("CB_WARM_CACHE", None)
        else:
            os.environ["CB_WARM_CACHE"] = self._prev

    def _args(self, value):
        if value is None:
            os.environ.pop("CB_WARM_CACHE", None)
        else:
            os.environ["CB_WARM_CACHE"] = value
        return run_mod._verifier_workdir_args("run-id-123")

    def test_warm_forwards_the_flag(self):
        self.assertIn("--warm-cache", self._args("1"))

    def test_warm_does_NOT_pin_a_workdir(self):
        """run_task reads an explicit --workdir as FORCE COLD, so passing both
        would silently disable warming while the caller believed it was on."""
        self.assertNotIn("--workdir", self._args("1"))

    def test_cold_is_the_default_and_still_pins(self):
        """OPT-IN only: a warm slot is state reused across runs, and a MEASURED
        eval must start clean unless someone explicitly asks otherwise."""
        args = self._args(None)
        self.assertNotIn("--warm-cache", args)
        if os.name == "nt":
            self.assertIn("--workdir", args)

    def test_the_two_modes_are_mutually_exclusive(self):
        for val in ("1", "true", "yes", "on", None, "0", "false", ""):
            args = self._args(val)
            self.assertFalse(
                "--warm-cache" in args and "--workdir" in args,
                f"CB_WARM_CACHE={val!r} produced BOTH: {args}")

    def test_falsey_values_stay_cold(self):
        for val in ("0", "false", "", "no"):
            self.assertNotIn("--warm-cache", self._args(val), f"value {val!r}")


class TestRetentionIsToldAboutWarm(unittest.TestCase):
    def test_apply_is_called_with_warm(self):
        """warm= is NOT auto-detected by apply(); under CB_WARM_CACHE the graded
        workdir IS the shared slot, whose Intermediate/+Binaries/ ARE the
        path-bound UBT cache. Slimming it would cost every LATER verify too."""
        src = (_RUN_AGENT / "run.py").read_text(encoding="utf-8")
        self.assertIn("warm=_warm_cache_enabled()", src)
        i_warm = src.index("warm=_warm_cache_enabled()")
        i_apply = src.index("workdir_retention.apply(")
        self.assertLess(i_apply, i_warm)  # it is an argument OF apply()


if __name__ == "__main__":
    unittest.main()

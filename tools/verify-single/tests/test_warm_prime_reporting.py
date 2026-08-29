"""`cb warm-prime` must not report a slot it skipped as one it built.

A busy slot returned 0, which the caller counted as built, so the primer printed
"1 built" and exited 0 over an empty pool. The operator then runs --warm-cache
believing the pool is hot and every verify silently falls back to a cold build --
the failure is invisible precisely because the flag is only a timing claim.
"""

from __future__ import annotations

import contextlib
import io
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_HERE = Path(__file__).resolve().parent
_PARENT = _HERE.parent
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))

import build_warm_baseline  # noqa: E402
import warm_cache  # noqa: E402


class TestABusySlotIsNotAPrimedSlot(unittest.TestCase):

    def _prime_with_every_slot_busy(self, slots: str):
        tmp = Path(tempfile.mkdtemp(prefix="warm-busy-"))
        self.addCleanup(lambda: shutil.rmtree(tmp, ignore_errors=True))
        if not warm_cache.substrate_tree_sha(
                build_warm_baseline.REPO_ROOT / "UE-projects" / "CraftBenchTemplate",
                repo_root=build_warm_baseline.REPO_ROOT):
            self.skipTest("substrate has no git tree SHA here")
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(warm_cache.SlotLock, "acquire", lambda self: False), \
                mock.patch.object(warm_cache, "is_valid",
                                  lambda slot_dir, **kw: (False, "stale")), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = build_warm_baseline.main([
                "--substrate", "CraftBenchTemplate",
                "--ue-root", str(tmp / "UE_5.8"),
                "--warm-cache-dir", str(tmp / "pool"),
                "--slots", slots,
            ])
        return rc, out.getvalue(), err.getvalue()

    def test_an_all_busy_pool_is_a_failure_not_a_success(self) -> None:
        rc, out, err = self._prime_with_every_slot_busy("1")
        self.assertEqual(rc, 1, "priming nothing must not exit 0")
        self.assertIn("0 built", out)
        self.assertIn("BUSY", out)
        self.assertNotIn("verifies can now use", out,
                         "an empty pool must not advertise itself as usable")
        self.assertIn("NOTHING was primed", err)

    def test_a_busy_slot_is_counted_as_busy_not_built(self) -> None:
        _, out, _ = self._prime_with_every_slot_busy("2")
        self.assertIn("0 built", out)
        self.assertIn("2 BUSY", out)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

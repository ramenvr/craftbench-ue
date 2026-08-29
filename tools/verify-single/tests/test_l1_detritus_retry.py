"""L1 Darwin detritus self-heal (v2): a codesign "detritus not allowed"
failure is repaired by finishing the finalize ourselves (strip + ad-hoc sign
of the composed bundle); a whole-UBT retry happens only if the manual sign
fails. Other failures and other platforms never heal (the historical
single-attempt path stays byte-identical)."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_HERE = Path(__file__).resolve().parent.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from layers import l1_build  # noqa: E402
from layers.l1_build import _SingleTargetResult  # noqa: E402


def _result(target, exit_code, output=""):
    return _SingleTargetResult(
        target=target, exit_code=exit_code, output=output,
        duration_seconds=0.1, note=f"target {target}: exit {exit_code} in 0.1s",
    )


class TestDetritusHeal(unittest.TestCase):
    def _run(self, tmp, side_effects, system="Darwin", sign_ok=True):
        calls = []
        strips = []
        signs = []

        def fake_run_one_target(**kw):
            calls.append(kw["target"])
            return side_effects.pop(0)

        def fake_sign(project_path, target):
            signs.append(target)
            return sign_ok, "fake codesign transcript\n"

        log = Path(tmp) / "l1.log"
        with mock.patch.object(l1_build, "_run_one_target", fake_run_one_target), \
             mock.patch.object(l1_build.platform, "system", return_value=system), \
             mock.patch.object(l1_build, "_strip_xattrs", strips.append), \
             mock.patch.object(l1_build, "_manual_codesign_fallback", fake_sign), \
             mock.patch.object(l1_build, "_build_script",
                               return_value=Path(__file__)):
            res = l1_build.run_l1(
                ue_root=Path(tmp), project_path=Path(tmp) / "P" / "P.uproject",
                game_module="P", log_path=log,
            )
            log_text = log.read_text(encoding="utf-8")
        return res, calls, strips, signs, log_text

    def test_manual_codesign_heals_without_ubt_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            res, calls, strips, signs, log_text = self._run(tmp, [
                _result("PEditor", 0),
                _result("P", 6, "…detritus not allowed…"),
            ])
        self.assertEqual(res.status, "pass")
        # No second UBT invocation for the Game target — the sign healed it.
        self.assertEqual(calls, ["PEditor", "P"])
        self.assertEqual(signs, ["P"])
        self.assertEqual(strips, [])  # bundle strip happens inside the fallback
        self.assertTrue(any("harness completed the codesign" in n
                            for n in res.notes))
        # Both the failed attempt and the sign transcript are in the log.
        self.assertIn("detritus codesign failure", log_text)
        self.assertIn("harness codesign OK", log_text)

    def test_manual_sign_failure_falls_back_to_one_ubt_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            res, calls, strips, signs, _ = self._run(tmp, [
                _result("PEditor", 0),
                _result("P", 6, "…detritus not allowed…"),
                _result("P", 0),
            ], sign_ok=False)
        self.assertEqual(res.status, "pass")
        self.assertEqual(calls, ["PEditor", "P", "P"])
        self.assertEqual(signs, ["P"])
        self.assertEqual(len(strips), 1)  # project-tree strip before the retry

    def test_sign_fail_and_retry_fail_stays_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            res, calls, strips, signs, _ = self._run(tmp, [
                _result("PEditor", 0),
                _result("P", 6, "…detritus not allowed…"),
                _result("P", 6, "…detritus not allowed…"),
            ], sign_ok=False)
        self.assertEqual(res.status, "fail")
        # One retry only — never a heal loop.
        self.assertEqual(calls, ["PEditor", "P", "P"])
        self.assertEqual(signs, ["P"])

    def test_non_detritus_failure_never_heals(self):
        with tempfile.TemporaryDirectory() as tmp:
            res, calls, strips, signs, _ = self._run(tmp, [
                _result("PEditor", 6, "error C2065: undeclared identifier"),
            ])
        self.assertEqual(res.status, "fail")
        self.assertEqual(calls, ["PEditor"])
        self.assertEqual(signs, [])

    def test_detritus_on_non_darwin_never_heals(self):
        with tempfile.TemporaryDirectory() as tmp:
            res, calls, strips, signs, _ = self._run(tmp, [
                _result("PEditor", 6, "…detritus not allowed…"),
            ], system="Windows")
        self.assertEqual(res.status, "fail")
        self.assertEqual(calls, ["PEditor"])
        self.assertEqual(signs, [])


if __name__ == "__main__":
    unittest.main()

"""Unit tests for tools/verify-single/failure_evidence.py.

No UE required. The module's whole job is to survive a verdict-blind rmtree, so
every test here is written to fail if it stops doing that:

  - a non-passing layer's log IS excerpted beside the report, with the compile
    error in it;
  - an all-pass run writes NOTHING;
  - a report living INSIDE the workdir writes nothing (it would be deleted by
    the very rmtree this exists to survive) -- paired with a positive control
    from the identical setup, so the refusal cannot pass by writing nowhere;
  - the written FILE is byte-bounded on multi-byte text (the bug crash_evidence
    shipped twice: a byte-named cap that sliced characters, then a cap defeated
    by Windows newline translation);
  - a marker line early in a huge log survives (a pure tail would bury it);
  - the l2_pie -> l2_pie_nullrhi companion is preserved, because the layer's own
    notes say THAT is the file to read;
  - the call site in run_task stays ABOVE the rmtree -- moving it below would
    turn the whole module into a silent no-op that no other test would notice.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_VERIFY = _HERE.parent
if str(_VERIFY) not in sys.path:
    sys.path.insert(0, str(_VERIFY))

import failure_evidence  # noqa: E402
from failure_evidence import _EXCERPT_CAP_BYTES, preserve  # noqa: E402


class _Layer:
    """Stand-in for report.LayerReport: only .status and .log are read."""

    def __init__(self, status, log=None):
        self.status = status
        self.log = log


class FailureEvidenceTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.wd = self.root / "wd"
        (self.wd / "out").mkdir(parents=True)
        self.runside = self.root / "runside"
        self.runside.mkdir()
        self.report = self.runside / "cpp__gp-poison.report.json"
        self.report.write_text("{}", encoding="utf-8")
        self.l1log = self.wd / "out" / "l1_build.log"

    def tearDown(self):
        self._tmp.cleanup()

    def _preserve(self, layers, report=None):
        return preserve(layers, report_json_path=report or self.report,
                        workdir=self.wd)

    # ---- the positive case ------------------------------------------------

    def test_failed_layer_log_is_excerpted_beside_the_report(self):
        self.l1log.write_text(
            "Building ThirdPerson...\n"
            "PoisonStack.cpp(42): error C3859: virtual memory range for PCH "
            "exceeded\n"
            "fatal error C1076: compiler limit\n",
            encoding="utf-8")
        written = self._preserve({"L1": _Layer("fail", str(self.l1log))})

        self.assertEqual(1, len(written))
        dst = written[0]
        # .resolve() on BOTH sides: %TEMP% is an 8.3 short path on this box
        # ("SHORT~1"), and preserve() canonicalizes for the same reason
        # new_temp_workdir does (run_task.py, FAILURE-LOG 2026-07-25). The
        # tmpdir is deliberately left short so that stays exercised.
        self.assertEqual(self.runside.resolve(), dst.parent)
        self.assertEqual("cpp__gp-poison.l1_build.excerpt.log", dst.name)
        body = dst.read_text(encoding="utf-8")
        self.assertIn("error C3859", body)
        self.assertIn("fatal error C1076", body)
        # the original path is recorded, so a reader can say what was lost
        self.assertIn("l1_build.log", body)

    def test_all_pass_writes_nothing(self):
        self.l1log.write_text("ok\n", encoding="utf-8")
        self.assertEqual([], self._preserve({
            "L1": _Layer("pass", str(self.l1log)),
            "L2": _Layer("pass", str(self.l1log)),
        }))
        self.assertEqual([], list(self.runside.glob("*.excerpt.log")))

    def test_skipped_layer_with_a_real_log_is_still_preserved(self):
        # An L2 that skipped because L1 failed carries no log; an L2 that
        # skipped after the editor produced nothing carries the log that says
        # why. Only the second is worth keeping, and `not log` separates them.
        l2 = self.wd / "out" / "l2_pie.log"
        l2.write_text("RHI allocation failure\n", encoding="utf-8")
        written = self._preserve({
            "L1": _Layer("pass", str(self.l1log)),
            "L2": _Layer("skipped", str(l2)),
        })
        self.assertEqual(1, len(written))
        self.assertIn("RHI allocation failure",
                      written[0].read_text(encoding="utf-8"))

    def test_layer_without_a_log_is_silent(self):
        self.assertEqual([], self._preserve({"L2": _Layer("skipped", None)}))

    def test_log_path_that_is_not_a_file_is_silent(self):
        self.assertEqual([], self._preserve(
            {"L1": _Layer("fail", str(self.wd / "out"))}))
        self.assertEqual([], self._preserve(
            {"L1": _Layer("fail", str(self.wd / "out" / "nope.log"))}))

    def test_dict_shaped_layers_are_accepted(self):
        # batch_eval re-reads report.json WHOLE, so a caller may hand us the
        # deserialized dicts rather than LayerReport objects.
        self.l1log.write_text("error C2065: undeclared\n", encoding="utf-8")
        written = self._preserve(
            {"L1": {"status": "fail", "log": str(self.l1log)}})
        self.assertEqual(1, len(written))

    # ---- the refusal that is the whole point -----------------------------

    def test_refuses_when_the_report_lives_inside_the_workdir(self):
        """Writing there looks like evidence was kept, and keeps none."""
        self.l1log.write_text("error C3859: boom\n", encoding="utf-8")
        inside = self.wd / "out" / "report.json"
        inside.write_text("{}", encoding="utf-8")

        self.assertEqual([], self._preserve(
            {"L1": _Layer("fail", str(self.l1log))}, report=inside))
        self.assertEqual([], list((self.wd / "out").glob("*.excerpt.log")))

        # POSITIVE CONTROL from the identical layers/log: the refusal above must
        # be caused by the destination, not by the module writing nowhere ever.
        self.assertEqual(1, len(self._preserve(
            {"L1": _Layer("fail", str(self.l1log))})))

    # ---- the bounds ------------------------------------------------------

    def test_written_file_is_byte_bounded_on_multibyte_text(self):
        # 3 bytes/char in UTF-8, and UE really does emit this: a cap that
        # slices CHARACTERS overshoots by 3x, and on Windows an unbounded
        # newline translation puts it back over even after that is fixed.
        line = "由于目标骨架缺失，无法创建动画序列。" * 8 + "\n"
        self.l1log.write_text(line * 4000, encoding="utf-8")
        written = self._preserve({"L1": _Layer("fail", str(self.l1log))})

        self.assertEqual(1, len(written))
        size = written[0].stat().st_size
        self.assertLessEqual(size, _EXCERPT_CAP_BYTES,
                             "written file is %d bytes, cap is %d"
                             % (size, _EXCERPT_CAP_BYTES))
        # and it is not trivially empty / not invalid UTF-8
        self.assertGreater(size, 1024)
        written[0].read_text(encoding="utf-8")

    def test_marker_line_early_in_a_huge_log_survives(self):
        # A pure tail would bury this. If the marker scan is ever dropped, this
        # is the test that notices.
        noise = "Linking...........\n" * 60000
        self.l1log.write_text(
            "PoisonStack.cpp(7): error C2504: base class undefined\n" + noise,
            encoding="utf-8")
        written = self._preserve({"L1": _Layer("fail", str(self.l1log))})
        body = written[0].read_text(encoding="utf-8")
        self.assertIn("error C2504", body)

    def test_companion_log_is_preserved(self):
        l2 = self.wd / "out" / "l2_pie.log"
        l2.write_text("GPU retry\n", encoding="utf-8")
        (self.wd / "out" / "l2_pie_nullrhi.log").write_text(
            "the headless attempt: LogWindows: Error: ERROR: no tests\n",
            encoding="utf-8")

        written = self._preserve({"L2": _Layer("skipped", str(l2))})
        names = sorted(p.name for p in written)
        self.assertEqual(["cpp__gp-poison.l2_pie.excerpt.log",
                          "cpp__gp-poison.l2_pie_nullrhi.excerpt.log"], names)

    # ---- the wiring ------------------------------------------------------

    def test_call_site_stays_above_the_rmtree(self):
        """Below the rmtree the module is a no-op no other test can see.

        The log is gone by then, so `preserve` returns [] and every unit test in
        this file still passes -- the exact shape of the crash_evidence ordering
        hazard, where the call had to stay BELOW record_drive_pressure.
        """
        src = (_VERIFY / "run_task.py").read_text(encoding="utf-8")
        call = src.index("failure_evidence.preserve(")
        rmtree = src.index("robust_rmtree(workdir")
        self.assertLess(call, rmtree)

    def test_preserve_never_raises_on_a_hostile_filesystem(self):
        self.l1log.write_text("error C3859\n", encoding="utf-8")

        def boom(*_a, **_k):
            raise OSError("disk gone")

        orig = failure_evidence._bounded_write
        failure_evidence._bounded_write = boom
        try:
            self.assertEqual([], self._preserve(
                {"L1": _Layer("fail", str(self.l1log))}))
        finally:
            failure_evidence._bounded_write = orig


if __name__ == "__main__":
    unittest.main()

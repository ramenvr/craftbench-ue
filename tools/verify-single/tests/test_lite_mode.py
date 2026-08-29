"""--lite: the iteration mode, and the guarantees that keep it out of grades.

--lite exists because L1 is ~87% of a verify (measured: 87.4% on t0
CraftBenchTemplate, 87.7-87.8% across eight kp- ThirdPerson legs), so the build
is the only thing a lighter mode can meaningfully trim. Trimming it costs the one
guarantee the verifier is built on, which is why every test here is about the
verdict NOT escaping rather than about the speedup.
"""
import subprocess
import sys
import unittest
from pathlib import Path

_VERIFY = Path(__file__).resolve().parent.parent
_REPO = _VERIFY.parent.parent
if str(_VERIFY) not in sys.path:
    sys.path.insert(0, str(_VERIFY))
if str(_REPO / "tools" / "run-agent") not in sys.path:
    sys.path.insert(0, str(_REPO / "tools" / "run-agent"))

import run_task  # noqa: E402
from report import HostInfo, LayerReport, Report, report_from_dict  # noqa: E402


class TestUngradedTaxonomy(unittest.TestCase):
    def test_exit_code_is_distinct_from_every_other_state(self):
        codes = {
            run_task.EXIT_PASS, run_task.EXIT_FAIL, run_task.EXIT_USAGE,
            run_task.EXIT_SANDBOX_REJECT, run_task.EXIT_NO_UPROJECT,
            run_task.EXIT_HARNESS_ERROR, run_task.EXIT_UNGRADED,
        }
        self.assertEqual(len(codes), 7)
        self.assertEqual(run_task.EXIT_UNGRADED, 8)
        # 3 is retired-and-reserved, 6 is FORBIDDEN (UBT's own build-failure
        # code). Neither may be reused, including by this mode.
        self.assertNotIn(run_task.EXIT_UNGRADED, (3, 6))

    def test_ungraded_is_not_a_graded_verdict(self):
        """THE property. GRADED_VERDICTS is an allowlist, so this holds by
        omission — no consumer has to remember to filter UNGRADED out."""
        from adapters.base import (
            GRADED_VERDICTS,
            VERDICT_UNGRADED,
            is_graded_verdict,
        )
        self.assertNotIn(VERDICT_UNGRADED, GRADED_VERDICTS)
        self.assertFalse(is_graded_verdict(VERDICT_UNGRADED))

    def test_both_harness_verdict_maps_agree_on_exit_8(self):
        """adapters/base and aura_rig/driver are the same taxonomy on two
        routes; a disagreement makes one run read as two outcomes."""
        from adapters.base import VERDICT_UNGRADED, VERIFIER_EXIT_VERDICT
        from aura_rig.driver import VERDICT as DRIVER_VERDICT
        self.assertEqual(VERIFIER_EXIT_VERDICT[8], VERDICT_UNGRADED)
        self.assertEqual(DRIVER_VERDICT[8], VERDICT_UNGRADED)

    def test_ungraded_is_not_folded_into_harness_error(self):
        """A deliberate cheap run must stay distinguishable from a broken one."""
        from adapters.base import VERDICT_HARNESS_ERROR, VERDICT_UNGRADED
        self.assertNotEqual(VERDICT_UNGRADED, VERDICT_HARNESS_ERROR)
        self.assertNotEqual(run_task.OVERALL_UNGRADED,
                            run_task.OVERALL_HARNESS_ERROR)

    def test_overall_string_uppercases_to_the_verdict(self):
        """adapters.base derives the verdict by uppercasing report.overall."""
        from adapters.base import VERDICT_UNGRADED
        self.assertEqual(run_task.OVERALL_UNGRADED.upper(), VERDICT_UNGRADED)


class TestLiteParserSurface(unittest.TestCase):
    def test_flag_defaults_off(self):
        args = run_task.build_parser().parse_args(
            ["--task", "t.md", "--submission", "s", "--ue-root", "u"]
        )
        self.assertFalse(args.lite)

    def test_flag_parses(self):
        args = run_task.build_parser().parse_args(
            ["--task", "t.md", "--submission", "s", "--ue-root", "u", "--lite"]
        )
        self.assertTrue(args.lite)


class TestLiteRequiresAWarmSlot(unittest.TestCase):
    """--lite without a slot has NO binaries to run against, and every layer
    would fail for want of an editor — which would read as the submission's
    fault. It must die at argument-validation time, before any staging."""

    def test_lite_without_warm_cache_is_a_usage_error(self):
        proc = subprocess.run(
            [sys.executable, str(_VERIFY / "run_task.py"),
             "--task", str(_REPO / "tasks" / "cpp"
                           / "t0-sanity-log-on-beginplay" / "task.md"),
             "--submission", str(_REPO / "tasks" / "cpp"
                                / "t0-sanity-log-on-beginplay" / "reference"),
             "--ue-root", str(_REPO), "--lite"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        self.assertEqual(proc.returncode, run_task.EXIT_USAGE)
        self.assertIn("--lite requires --warm-cache", proc.stderr)


def _report(**kw):
    base = dict(
        task_id="t0-sanity-log-on-beginplay",
        submission_sha="abc123",
        layers={"L2": LayerReport(status="pass", tests_run=1, tests_passed=1)},
        overall=run_task.OVERALL_UNGRADED,
        duration_seconds=13.0,
        ue_version="5.8",
        host=HostInfo(os="windows", arch="amd64"),
    )
    base.update(kw)
    return Report(**base)


class TestLiteReportShape(unittest.TestCase):
    def test_ungraded_report_never_says_pass(self):
        """Even with every layer passing, `overall` is not pass."""
        d = _report().to_dict()
        self.assertEqual(d["overall"], "ungraded")
        self.assertNotEqual(d["overall"], "pass")

    def test_render_spells_out_why_it_is_not_a_verdict(self):
        text = _report().render_text()
        self.assertIn("UNGRADED", text)
        self.assertIn("NOT a verdict", text)
        self.assertIn("did not build", text)

    def test_notes_round_trip_and_render(self):
        note = ("--lite: submission contains 2 compile input(s) that were NOT "
                "built")
        r = _report(notes=[note])
        self.assertEqual(r.to_dict()["notes"], [note])
        self.assertEqual(report_from_dict(r.to_dict()).notes, [note])
        self.assertIn(note, r.render_text())

    def test_notes_omitted_when_empty(self):
        """Reports predating run-level notes stay byte-identical."""
        self.assertNotIn("notes", _report().to_dict())


class TestWarmSlotBinariesState(unittest.TestCase):
    """A warm slot's Binaries/ are NOT the baseline after the first grade.

    Regression cover for the 2026-07-31 measurement run, where a --lite grade
    reported t0 L2 1/1 PASS purely because the warm grade a minute earlier had
    linked that submission's code into the slot. The marker is what lets a
    build-free consumer tell the two apart.
    """

    def setUp(self):
        import tempfile
        import warm_cache
        self.wc = warm_cache
        self.slot = Path(tempfile.mkdtemp(prefix="cb-slotstate-"))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.slot, ignore_errors=True)

    def test_missing_marker_reads_unknown_not_pristine(self):
        """A slot primed before the marker existed has genuinely unknown
        binaries; guessing 'pristine' there would reinstate the false pass."""
        self.assertEqual(self.wc.read_binaries_state(self.slot), "unknown")
        self.assertNotEqual(self.wc.read_binaries_state(self.slot),
                            self.wc.PRISTINE)

    def test_round_trip(self):
        self.wc.write_binaries_state(self.slot, self.wc.PRISTINE)
        self.assertEqual(self.wc.read_binaries_state(self.slot),
                         self.wc.PRISTINE)
        self.wc.write_binaries_state(self.slot, "deadbeefsha")
        self.assertEqual(self.wc.read_binaries_state(self.slot), "deadbeefsha")

    def test_corrupt_marker_reads_unknown(self):
        self.wc.binaries_state_path(self.slot).write_text("{not json",
                                                          encoding="utf-8")
        self.assertEqual(self.wc.read_binaries_state(self.slot), "unknown")

    def test_fingerprint_covers_compile_inputs_only(self):
        """An asset edit must NOT invalidate the object-file cache — that is the
        redundant recompile this whole mechanism exists to remove."""
        sub = self.slot / "build"
        (sub / "Source" / "Mod").mkdir(parents=True)
        (sub / "Content" / "Tasks").mkdir(parents=True)
        (sub / "Source" / "Mod" / "A.cpp").write_text("int a;", encoding="utf-8")
        (sub / "Content" / "Tasks" / "x.uasset").write_bytes(b"v1")
        prefixes = ("Source/Mod/", "Content/Tasks/")
        fp0 = self.wc.compile_input_fingerprint(sub, prefixes)

        (sub / "Content" / "Tasks" / "x.uasset").write_bytes(b"v2-different")
        self.assertEqual(self.wc.compile_input_fingerprint(sub, prefixes), fp0)

        (sub / "Source" / "Mod" / "A.cpp").write_text("int b;", encoding="utf-8")
        self.assertNotEqual(self.wc.compile_input_fingerprint(sub, prefixes), fp0)

    def test_fingerprint_is_mtime_independent(self):
        """Content, not mtime — a reset restores pristine mtimes, which is
        precisely why mtime could not be trusted in the first place."""
        import os
        sub = self.slot / "build"
        (sub / "Source" / "Mod").mkdir(parents=True)
        f = sub / "Source" / "Mod" / "A.cpp"
        f.write_text("int a;", encoding="utf-8")
        fp0 = self.wc.compile_input_fingerprint(sub, ("Source/Mod/",))
        os.utime(f, (1, 1))
        self.assertEqual(
            self.wc.compile_input_fingerprint(sub, ("Source/Mod/",)), fp0
        )

    def test_fingerprint_detects_a_renamed_file(self):
        """Path is hashed alongside content, so moving code between files
        changes the fingerprint even when the bytes are conserved."""
        sub = self.slot / "build"
        (sub / "Source" / "Mod").mkdir(parents=True)
        (sub / "Source" / "Mod" / "A.cpp").write_text("x", encoding="utf-8")
        fp0 = self.wc.compile_input_fingerprint(sub, ("Source/Mod/",))
        (sub / "Source" / "Mod" / "A.cpp").rename(sub / "Source" / "Mod" / "B.cpp")
        self.assertNotEqual(
            self.wc.compile_input_fingerprint(sub, ("Source/Mod/",)), fp0
        )

    def test_incomplete_build_leaves_no_trusted_fingerprint(self):
        """The pre-build write records None; only a PASSING L1 fills it in. A
        reaped build must never look like a valid cache."""
        self.wc.write_binaries_state(self.slot, "somesha",
                                     compile_fingerprint=None)
        self.assertIsNone(self.wc.read_compile_fingerprint(self.slot))
        self.wc.write_binaries_state(self.slot, "somesha",
                                     compile_fingerprint="abc123")
        self.assertEqual(self.wc.read_compile_fingerprint(self.slot), "abc123")

    def test_fingerprint_recorded_only_after_a_passing_l1(self):
        """Source pin on the ordering that makes the above true."""
        src = (_VERIFY / "run_task.py").read_text(encoding="utf-8")
        i_dirty = src.index("compile_fingerprint=None,")
        i_layers = src.index("layers_out, advisory_out = run_layers(")
        i_commit = src.index("compile_fingerprint=_fp_now,")
        self.assertLess(i_dirty, i_layers)      # dirty BEFORE the build
        self.assertLess(i_layers, i_commit)     # trusted only AFTER it
        self.assertIn('_l1_report.status == "pass"', src)

    def test_primer_stamps_pristine_before_building(self):
        """Source pin: the stamp must precede run_l1, so a reaped build cannot
        leave a half-written binary labelled pristine."""
        src = (_VERIFY / "build_warm_baseline.py").read_text(encoding="utf-8")
        i_stamp = src.index("write_binaries_state(slot_dir, warm_cache.PRISTINE)")
        i_build = src.index("l1 = run_l1(")
        self.assertLess(i_stamp, i_build)

    def test_warm_grade_marks_dirty_before_building(self):
        """Same ordering pin on the verify path: the slot is recorded dirty
        before L1 runs, never after."""
        src = (_VERIFY / "run_task.py").read_text(encoding="utf-8")
        i_dirty = src.index("_wc_state.write_binaries_state(")
        i_layers = src.index("layers_out, advisory_out = run_layers(")
        self.assertLess(i_dirty, i_layers)


class TestLiteDropsL1FromRequestedLayers(unittest.TestCase):
    """L1 is REMOVED from the requested set, not skipped at run time.

    harness_error_reasons predicate (2) fires on 'a requested gating layer
    produced no key'. Under --lite that is the intent, so the token is dropped
    rather than the predicate weakened — the harness-error taxonomy keeps
    working for every other run.
    """

    def test_dropping_l1_leaves_no_harness_error(self):
        layers_out = {"L2": LayerReport(status="pass", tests_run=1,
                                        tests_passed=1)}
        # What --lite passes: the spec's layers minus L1.
        self.assertEqual(
            run_task.harness_error_reasons(layers_out, ("L2",)), []
        )

    def test_keeping_l1_requested_would_have_flagged_it(self):
        """Pins WHY the token is dropped: leaving it in is a harness error."""
        layers_out = {"L2": LayerReport(status="pass", tests_run=1,
                                        tests_passed=1)}
        self.assertNotEqual(
            run_task.harness_error_reasons(layers_out, ("L1", "L2")), []
        )


if __name__ == "__main__":
    unittest.main()


class TestApplySubmissionPreservesMtimes(unittest.TestCase):
    """A content-identical file must NOT be rewritten -- UBT reads mtimes.

    Measured 2026-08-03: --submission-from-project sweeps the whole writable
    subtree, not the agent's diff. On a kp- row whose real deliverable was ONE
    .uasset, the "submission" was 89 files (88 under Source/). Copying them
    unconditionally gave every source file a fresh mtime, UBT logged
    "Invalidating makefile (ThirdPerson.Build.cs modified)" and rebuilt all 47
    actions -- L1 127.5s where the same warm slot had just done 3.9s. The content
    fingerprint had already correctly decided the inputs were IDENTICAL.
    """

    def setUp(self):
        import tempfile
        self.tmp = Path(tempfile.mkdtemp(prefix="cb-apply-"))
        self.sub = self.tmp / "sub"
        self.wd = self.tmp / "wd"
        (self.sub / "Source" / "Mod").mkdir(parents=True)
        (self.wd / "Source" / "Mod").mkdir(parents=True)

    def tearDown(self):
        import shutil as _s
        _s.rmtree(self.tmp, ignore_errors=True)

    def _write(self, root, rel, body):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
        return p

    def test_identical_file_keeps_its_mtime(self):
        import os
        rel = "Source/Mod/Mod.Build.cs"
        self._write(self.sub, rel, "same bytes")
        dst = self._write(self.wd, rel, "same bytes")
        os.utime(dst, (1_000_000, 1_000_000))
        before = dst.stat().st_mtime
        run_task.apply_submission(self.sub, self.wd, [(self.sub / rel, rel)])
        self.assertEqual(dst.stat().st_mtime, before,
                         "an identical file was rewritten -> UBT rebuilds")

    def test_changed_file_IS_written(self):
        rel = "Source/Mod/A.cpp"
        self._write(self.sub, rel, "new content")
        dst = self._write(self.wd, rel, "old content")
        run_task.apply_submission(self.sub, self.wd, [(self.sub / rel, rel)])
        self.assertEqual(dst.read_text(encoding="utf-8"), "new content")

    def test_new_file_IS_written(self):
        rel = "Content/Tasks/x/new.uasset"
        self._write(self.sub, rel, "brand new")
        run_task.apply_submission(self.sub, self.wd, [(self.sub / rel, rel)])
        self.assertEqual((self.wd / rel).read_text(encoding="utf-8"), "brand new")

    def test_same_size_different_bytes_IS_written(self):
        """Size is only a cheap reject -- equal size must still compare bytes,
        or a same-length edit would be silently dropped from the grade."""
        rel = "Source/Mod/B.cpp"
        self._write(self.sub, rel, "AAAA")
        dst = self._write(self.wd, rel, "BBBB")
        run_task.apply_submission(self.sub, self.wd, [(self.sub / rel, rel)])
        self.assertEqual(dst.read_text(encoding="utf-8"), "AAAA")

"""Leg-count guard (run_l2 expected_test_count) + scaffolder retirement.

No UE needed — the editor subprocess / run_l2 are monkeypatched (same style as
test_capture_artifacts.py). Covers:

  - run_l2's PASS gate additionally requires tests_run == expected_test_count:
    a stubbed automation log where only 1 of 2 declared fixtures ran grades
    FAIL with the "leg dropped: ran N of M declared fixtures" note (and an
    over-count also fails).
  - expected_test_count=None keeps the legacy gate byte-identical (back-compat
    for callers that don't thread a count).
  - L2Layer threads the declared-fixture count into run_l2 (len(fixtures) on
    the multi-fixture path; 1 on the legacy single-fixture path).
  - Scaffolders retired: a missing map binary is an explicit L2 FAIL ("map
    binary missing: ...") and run_l2 is never invoked — no re-bake fallback.
"""
from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

_HERE = Path(__file__).resolve().parent
_VERIFY = _HERE.parent
if str(_VERIFY) not in sys.path:
    sys.path.insert(0, str(_VERIFY))

from layers.base import LayerContext  # noqa: E402
from layers.registry import L2Layer  # noqa: E402
import layers.l2_pie as l2pie  # noqa: E402


def _fixture(map_name: str, test_class: str):
    return types.SimpleNamespace(map_name=map_name, test_class=test_class)


def _stub_l2(status="pass", tests_run=1, tests_passed=None):
    if tests_passed is None:
        tests_passed = tests_run if status == "pass" else 0
    from layers.l2_pie import L2Result
    # Real dataclass — see the note in test_capture_artifacts._stub_l2.
    return L2Result(
        status=status, log_path=Path("/tmp/l2.log"), duration_seconds=1.0,
        tests_run=tests_run, tests_passed=tests_passed,
        tests_failed=0, tests_skipped=0, notes=[], exit_code=0,
        report_path=None, result_source="json",
    )


def _ctx(workdir: Path, *, fixtures=(), map_name=None, test_class_hint=None,
         test_filter=None, fps_legs=()) -> LayerContext:
    task = types.SimpleNamespace(
        task_id="t", layers=("L1", "L2"), raw_text="", map_name=map_name,
        test_class_hint=test_class_hint,
        fixtures=tuple(fixtures), introspect_scripts=(), artifact_path=None,
        l3_fixtures=(), fps_legs=fps_legs,
    )
    args = types.SimpleNamespace(
        ue_root=Path("/ue"), test_filter=test_filter,
        use_nullrhi=True, capture=False, r2=False,
    )
    out_dir = workdir / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    return LayerContext(
        task=task, args=args, project_path=workdir / "x.uproject",
        workdir_substrate=workdir, out_dir=out_dir,
        manifest=types.SimpleNamespace(writable=(), game_module="m"),
        substrate_src=Path("/s"), requested_layers={"L1", "L2"},
    )


def _drop_umap(workdir: Path, *rel_parts: str) -> Path:
    umap = workdir / "Content" / "Maps"
    for part in rel_parts:
        umap = umap / part
    umap.parent.mkdir(parents=True, exist_ok=True)
    umap.write_bytes(b"\x00fake umap")
    return umap


class TestRunL2LegCountGuard(unittest.TestCase):
    """run_l2's gate — the editor subprocess is faked; the automation result
    is fed through a stubbed stdout log (the stdout-fallback parse path)."""

    def _run(self, tmp: Path, log_lines: str, **kwargs):
        def fake_marker_kill(*, cmd, env, log_path, timeout_seconds):
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(log_lines, encoding="utf-8")
            return (0, False)

        fake_editor = tmp / "UnrealEditor-Cmd"
        fake_editor.write_text("stub", encoding="utf-8")
        with mock.patch.object(l2pie, "_editor_binary", lambda ue_root: fake_editor), \
             mock.patch.object(l2pie, "_run_editor_with_marker_kill", fake_marker_kill):
            return l2pie.run_l2(
                ue_root=tmp,
                project_path=tmp / "p.uproject",
                test_filter="A.B.C+A.B.D",
                log_path=tmp / "l2.log",
                **kwargs,
            )

    def test_one_of_two_declared_fixtures_ran_fails_with_leg_dropped_note(self):
        with tempfile.TemporaryDirectory() as d:
            res = self._run(Path(d), "TestResult=Passed\n", expected_test_count=2)
            self.assertEqual(res.status, "fail")
            self.assertIn(
                "leg dropped: ran 1 of 2 declared fixtures", res.notes,
            )

    def test_all_declared_fixtures_ran_passes(self):
        with tempfile.TemporaryDirectory() as d:
            res = self._run(
                Path(d), "TestResult=Passed\nTestResult=Passed\n",
                expected_test_count=2,
            )
            self.assertEqual(res.status, "pass")
            self.assertFalse(any("leg dropped" in n for n in res.notes))

    def test_over_count_also_fails(self):
        with tempfile.TemporaryDirectory() as d:
            res = self._run(
                Path(d),
                "TestResult=Passed\nTestResult=Passed\nTestResult=Passed\n",
                expected_test_count=2,
            )
            self.assertEqual(res.status, "fail")
            self.assertTrue(any("fixture over-count: ran 3 of 2" in n
                                for n in res.notes))

    def test_zero_tests_stays_skipped_not_leg_dropped(self):
        # tests_run == 0 keeps the legacy "skipped" semantics (the nullrhi
        # retry / discovery diagnostics key off it) — the guard only tightens
        # the PASS gate.
        with tempfile.TemporaryDirectory() as d:
            res = self._run(Path(d), "no results here\n", expected_test_count=2)
            self.assertEqual(res.status, "skipped")

    def test_no_expected_count_keeps_legacy_gate(self):
        with tempfile.TemporaryDirectory() as d:
            res = self._run(Path(d), "TestResult=Passed\n")
            self.assertEqual(res.status, "pass")

    def test_real_failure_stays_fail_regardless_of_count(self):
        with tempfile.TemporaryDirectory() as d:
            res = self._run(
                Path(d), "TestResult=Passed\nTestResult=Failed\n",
                expected_test_count=2,
            )
            self.assertEqual(res.status, "fail")


class TestL2LayerThreadsExpectedCount(unittest.TestCase):
    def test_multi_fixture_threads_declared_count(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            _drop_umap(d, "L_GasLaunch.umap")
            _drop_umap(d, "L_GasLaunchControl.umap")
            ctx = _ctx(d, fixtures=(
                _fixture("L_GasLaunch", "AGasLaunchFunctionalTest"),
                _fixture("L_GasLaunchControl", "AGasLaunchControlFunctionalTest"),
            ))
            calls = []

            def fake_run_l2(**kw):
                calls.append(kw)
                return _stub_l2("pass", tests_run=2, tests_passed=2)

            with mock.patch.object(l2pie, "run_l2", fake_run_l2):
                rep = L2Layer().run(ctx)

            self.assertEqual(rep.status, "pass")
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0]["expected_test_count"], 2)

    def test_single_fixture_legacy_path_expects_one(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            _drop_umap(d, "L_SanityTask.umap")
            ctx = _ctx(d, map_name="L_SanityTask",
                       test_class_hint="ASanityFunctionalTest")
            calls = []

            def fake_run_l2(**kw):
                calls.append(kw)
                return _stub_l2("pass")

            with mock.patch.object(l2pie, "run_l2", fake_run_l2):
                rep = L2Layer().run(ctx)

            self.assertEqual(rep.status, "pass")
            self.assertEqual(calls[0]["expected_test_count"], 1)

    def test_dt_legs_thread_expected_count_into_every_leg(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            _drop_umap(d, "L_SanityTask.umap")
            ctx = _ctx(d, map_name="L_SanityTask",
                       test_class_hint="ASanityFunctionalTest",
                       fps_legs=(60, 20))
            calls = []

            def fake_run_l2(**kw):
                calls.append(kw)
                return _stub_l2("pass")

            with mock.patch.object(l2pie, "run_l2", fake_run_l2):
                rep = L2Layer().run(ctx)

            self.assertEqual(rep.status, "pass")
            self.assertEqual([kw["fps"] for kw in calls], [60, 20])
            self.assertTrue(all(kw["expected_test_count"] == 1 for kw in calls))

    def test_explicit_test_filter_disables_guard_and_notes_it(self):
        # An explicit --test-filter is an operator debug override: running a
        # single leg of a multi-fixture task must NOT fail as "leg dropped".
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            _drop_umap(d, "L_GasLaunch.umap")
            _drop_umap(d, "L_GasLaunchControl.umap")
            ctx = _ctx(d, fixtures=(
                _fixture("L_GasLaunch", "AGasLaunchFunctionalTest"),
                _fixture("L_GasLaunchControl", "AGasLaunchControlFunctionalTest"),
            ), test_filter="Project.Functional Tests.Maps.L_GasLaunch.GasLaunchFunctionalTest")
            calls = []

            def fake_run_l2(**kw):
                calls.append(kw)
                return _stub_l2("pass", tests_run=1, tests_passed=1)

            with mock.patch.object(l2pie, "run_l2", fake_run_l2):
                rep = L2Layer().run(ctx)

            self.assertEqual(rep.status, "pass")
            self.assertIsNone(calls[0]["expected_test_count"])   # guard off
            self.assertTrue(any(
                "explicit --test-filter: leg-count guard disabled" in n
                for n in rep.notes))

    def test_explicit_filter_guard_note_surfaces_on_dt_legs_too(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            _drop_umap(d, "L_SanityTask.umap")
            ctx = _ctx(d, map_name="L_SanityTask",
                       test_class_hint="ASanityFunctionalTest",
                       test_filter="My.Explicit.Filter", fps_legs=(60, 20))
            calls = []

            def fake_run_l2(**kw):
                calls.append(kw)
                return _stub_l2("pass")

            with mock.patch.object(l2pie, "run_l2", fake_run_l2):
                rep = L2Layer().run(ctx)

            self.assertEqual(rep.status, "pass")
            self.assertTrue(all(kw["expected_test_count"] is None for kw in calls))
            self.assertTrue(any(
                "explicit --test-filter: leg-count guard disabled" in n
                for n in rep.notes))

    def test_over_count_note_surfaces_in_dt_leg_summary(self):
        # The dt-leg summary must surface BOTH guard notes — "leg dropped"
        # AND "fixture over-count" — else an over-count FAIL reads as
        # "failed while all tests passed" with no explanation.
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            _drop_umap(d, "L_SanityTask.umap")
            ctx = _ctx(d, map_name="L_SanityTask",
                       test_class_hint="ASanityFunctionalTest", fps_legs=(60,))

            def fake_run_l2(**kw):
                stub = _stub_l2("fail", tests_run=2, tests_passed=2)
                stub.notes = [
                    "fixture over-count: ran 2 of 1 declared fixtures — filter matched extra tests"
                ]
                return stub

            with mock.patch.object(l2pie, "run_l2", fake_run_l2):
                rep = L2Layer().run(ctx)

            self.assertEqual(rep.status, "fail")
            self.assertTrue(any("fixture over-count: ran 2 of 1" in n
                                for n in rep.notes))

    def test_leg_dropped_note_surfaces_in_layer_report(self):
        # End-to-end through L2Layer: the run_l2 result carries the note and
        # the single-session path folds l2.notes into the LayerReport.
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            _drop_umap(d, "L_GasLaunch.umap")
            _drop_umap(d, "L_GasLaunchControl.umap")
            ctx = _ctx(d, fixtures=(
                _fixture("L_GasLaunch", "AGasLaunchFunctionalTest"),
                _fixture("L_GasLaunchControl", "AGasLaunchControlFunctionalTest"),
            ))

            def fake_run_l2(**kw):
                # 1 of 2 legs ran and passed — mimic run_l2's guarded verdict.
                stub = _stub_l2("fail", tests_run=1, tests_passed=1)
                stub.notes = ["leg dropped: ran 1 of 2 declared fixtures"]
                return stub

            with mock.patch.object(l2pie, "run_l2", fake_run_l2):
                rep = L2Layer().run(ctx)

            self.assertEqual(rep.status, "fail")
            self.assertTrue(any("leg dropped: ran 1 of 2 declared fixtures" in n
                                for n in rep.notes))


class TestMissingMapBinaryFails(unittest.TestCase):
    def test_missing_single_fixture_map_is_explicit_fail_without_running(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "Content" / "Maps").mkdir(parents=True)
            ctx = _ctx(d, map_name="L_SanityTask",
                       test_class_hint="ASanityFunctionalTest")
            calls = []

            def fake_run_l2(**kw):
                calls.append(kw)
                return _stub_l2("pass")

            with mock.patch.object(l2pie, "run_l2", fake_run_l2):
                rep = L2Layer().run(ctx)

            self.assertEqual(rep.status, "fail")
            self.assertEqual(calls, [])  # no PIE session, no re-bake attempt
            self.assertTrue(any(
                "map binary missing: L_SanityTask" in n and
                "scaffolders retired 2026-07" in n
                for n in rep.notes))

    def test_missing_one_of_two_fixture_maps_fails(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            _drop_umap(d, "L_GasLaunch.umap")  # control map missing
            ctx = _ctx(d, fixtures=(
                _fixture("L_GasLaunch", "AGasLaunchFunctionalTest"),
                _fixture("L_GasLaunchControl", "AGasLaunchControlFunctionalTest"),
            ))
            calls = []

            def fake_run_l2(**kw):
                calls.append(kw)
                return _stub_l2("pass")

            with mock.patch.object(l2pie, "run_l2", fake_run_l2):
                rep = L2Layer().run(ctx)

            self.assertEqual(rep.status, "fail")
            self.assertEqual(calls, [])
            self.assertTrue(any("map binary missing: L_GasLaunchControl" in n
                                for n in rep.notes))

    def test_no_map_no_fixtures_still_runs_with_explicit_filter(self):
        # Tasks with map_name=None + an explicit --test-filter keep working:
        # there is nothing to locate, so no missing-binary FAIL fires.
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            ctx = _ctx(d, test_filter="My.Explicit.Filter")
            calls = []

            def fake_run_l2(**kw):
                calls.append(kw)
                return _stub_l2("pass")

            with mock.patch.object(l2pie, "run_l2", fake_run_l2):
                rep = L2Layer().run(ctx)

            self.assertEqual(rep.status, "pass")
            self.assertEqual(len(calls), 1)
            self.assertIsNone(calls[0]["map_package_path"])


if __name__ == "__main__":
    unittest.main()

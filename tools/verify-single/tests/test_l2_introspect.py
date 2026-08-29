"""Unit tests for the L2-introspect verification layer.

No UE install required — the headless editor run is an injectable seam, so
the verdict parser and the runner status logic are exercised fully offline.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_HERE = Path(__file__).resolve().parent
_VERIFY = _HERE.parent
if str(_VERIFY) not in sys.path:
    sys.path.insert(0, str(_VERIFY))

from layers.l2_introspect import (  # noqa: E402
    INTEGRITY_JSON_END,
    INTEGRITY_JSON_START,
    INTROSPECT_JSON_END,
    INTROSPECT_JSON_START,
    SUBMITTED_FILES_ENV,
    _canonical_submitted_relpaths,
    parse_introspect_verdict,
    run_l2_introspect,
)


def _verdict_block(checks):
    body = json.dumps({"checks": checks})
    return f"{INTROSPECT_JSON_START}\n{body}\n{INTROSPECT_JSON_END}\n"


class TestParseVerdict(unittest.TestCase):
    def test_all_pass(self):
        log = "noise\n" + _verdict_block([
            {"id": "has_idle_state", "passed": True, "detail": "found"},
            {"id": "has_walk_state", "passed": True, "detail": "found"},
        ]) + "trailing noise\n"
        p = parse_introspect_verdict(log)
        self.assertTrue(p.found)
        self.assertEqual(p.total, 2)
        self.assertEqual(p.passed_count, 2)
        self.assertTrue(p.all_passed)

    def test_one_fail(self):
        p = parse_introspect_verdict(_verdict_block([
            {"id": "a", "passed": True},
            {"id": "b", "passed": False, "detail": "missing transition"},
        ]))
        self.assertTrue(p.found)
        self.assertFalse(p.all_passed)
        self.assertEqual(p.passed_count, 1)

    def test_takes_last_block_on_double_run(self):
        # A re-run / double dispatch may emit the block twice; the last wins.
        log = _verdict_block([{"id": "a", "passed": False}]) + \
            _verdict_block([{"id": "a", "passed": True}])
        self.assertTrue(parse_introspect_verdict(log).all_passed)

    def test_ue_log_prefixed_block(self):
        # Real UE runs emit the verdict via ``unreal.log``, so every line —
        # markers AND the JSON payload — arrives wrapped in UE's log prefix
        # ``[<timestamp>][ N]LogPython: ``. The parser must isolate the JSON
        # object out of that decoration. (Regression for the mat-emissive-pulse
        # first live run, 2026-06-01.)
        pre = "[2026.06.01-10.00.58:848][  2]LogPython: "
        body = json.dumps({"checks": [
            {"id": "asset_exists", "passed": True, "detail": "/Game/x"},
            {"id": "blend_opaque", "passed": True, "detail": "<BlendMode.BLEND_OPAQUE: 0>"},
        ]})
        log = (
            "[2026.06.01-10.00.49:875][  0]LogPython: Using Python 3.11.8\n"
            + pre + INTROSPECT_JSON_START + "\n"
            + pre + body + "\n"
            + pre + INTROSPECT_JSON_END + "\n"
            + "[2026.06.01-10.00.59:000][  2]LogExit: Exiting.\n"
        )
        p = parse_introspect_verdict(log)
        self.assertTrue(p.found)
        self.assertEqual(p.total, 2)
        self.assertTrue(p.all_passed)

    def test_no_block(self):
        p = parse_introspect_verdict("editor started\n...\nLogExit: Exiting.\n")
        self.assertFalse(p.found)
        self.assertEqual(p.total, 0)
        self.assertFalse(p.all_passed)

    def test_malformed_json(self):
        log = f"{INTROSPECT_JSON_START}\n{{not valid json\n{INTROSPECT_JSON_END}\n"
        self.assertFalse(parse_introspect_verdict(log).found)

    def test_empty_checks_is_not_pass(self):
        # A verdict with zero checks must NOT count as a pass (fail-safe).
        p = parse_introspect_verdict(_verdict_block([]))
        self.assertTrue(p.found)
        self.assertEqual(p.total, 0)
        self.assertFalse(p.all_passed)


def _fake_editor_run_factory(verdict_text, exit_code=0):
    def _run(*, cmd, env, log_path, timeout_seconds, extra_markers=()):
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(verdict_text, encoding="utf-8")
        return (exit_code, True)
    return _run


class TestRunL2Introspect(unittest.TestCase):
    def _run(self, verdict_text):
        tmp = Path(tempfile.mkdtemp())
        fake_editor = tmp / "UnrealEditor-Cmd"
        fake_editor.write_text("#!/bin/sh\n")
        script = tmp / "introspect_task.py"
        script.write_text("# introspect")
        return run_l2_introspect(
            ue_root=tmp,
            project_path=tmp / "X.uproject",
            introspect_script=script,
            log_path=tmp / "out" / "l2_introspect.log",
            _editor_binary=lambda _root: fake_editor,
            _run_editor=_fake_editor_run_factory(verdict_text),
        )

    def test_pass(self):
        res = self._run(_verdict_block([{"id": "a", "passed": True}]))
        self.assertEqual(res.status, "pass")
        self.assertEqual(res.passed_count, 1)
        self.assertEqual(res.result_source, "json")

    def test_fail(self):
        res = self._run(_verdict_block([{"id": "a", "passed": False}]))
        self.assertEqual(res.status, "fail")
        self.assertEqual(res.total, 1)

    def test_no_verdict_is_error(self):
        res = self._run("the script crashed, no verdict\n")
        self.assertEqual(res.status, "error")
        self.assertEqual(res.result_source, "none")

    def test_missing_editor_is_error(self):
        tmp = Path(tempfile.mkdtemp())
        res = run_l2_introspect(
            ue_root=tmp,
            project_path=tmp / "X.uproject",
            introspect_script=tmp / "s.py",
            log_path=tmp / "l.log",
            _editor_binary=lambda _root: tmp / "does-not-exist",
            _run_editor=_fake_editor_run_factory(""),
        )
        self.assertEqual(res.status, "error")
        self.assertEqual(res.exit_code, 127)


class TestSubmittedFilesEnvironment(unittest.TestCase):
    def _run_and_capture(self, submitted):
        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp = Path(raw_tmp)
            fake_editor = tmp / "UnrealEditor-Cmd"
            fake_editor.write_text("#!/bin/sh\n", encoding="utf-8")
            script = tmp / "fixed_introspector.py"
            script.write_text("# verifier owned\n", encoding="utf-8")
            (tmp / "out").mkdir()

            # These nearby files deliberately exist but were not accepted by
            # the runner.  The L2I seam must never discover or leak them.
            (tmp / "reference").mkdir()
            (tmp / "reference" / "answer.uasset").write_bytes(b"reference")
            (tmp / "scaffold.cpp").write_text("// verifier\n", encoding="utf-8")

            captured = {}

            def fake_run(*, cmd, env, log_path, timeout_seconds, extra_markers=()):
                captured["env"] = env
                log_path.parent.mkdir(parents=True, exist_ok=True)
                log_path.write_text(
                    f"{INTEGRITY_JSON_START}\n{{\"violations\": []}}\n"
                    f"{INTEGRITY_JSON_END}\n"
                    + _verdict_block([{"id": "manifest", "passed": True}]),
                    encoding="utf-8",
                )
                return 0, False

            with mock.patch.dict(
                os.environ,
                {
                    "CRAFTBENCH_PARENT_ENV_CANARY": "preserved",
                    SUBMITTED_FILES_ENV: '["stale-parent-value"]',
                },
                clear=False,
            ):
                result = run_l2_introspect(
                    ue_root=tmp,
                    project_path=tmp / "X.uproject",
                    introspect_script=script,
                    log_path=tmp / "out" / "l2_introspect.log",
                    submitted_assets=submitted,
                    _editor_binary=lambda _root: fake_editor,
                    _run_editor=fake_run,
                )
                self.assertIsNot(captured["env"], os.environ)

            self.assertEqual(result.status, "pass")
            return captured["env"]

    def test_empty_submission_is_explicit_empty_json(self):
        env = self._run_and_capture([])
        self.assertEqual(env[SUBMITTED_FILES_ENV], "[]")

    def test_asset_only_is_exact_and_does_not_scan_nearby_files(self):
        expected = "Content/Tasks/t/ABP_HangingChain.uasset"
        env = self._run_and_capture([expected])
        self.assertEqual(json.loads(env[SUBMITTED_FILES_ENV]), [expected])
        self.assertNotIn("answer.uasset", env[SUBMITTED_FILES_ENV])
        self.assertNotIn("scaffold.cpp", env[SUBMITTED_FILES_ENV])

    def test_all_accepted_source_and_asset_paths_are_retained_sorted(self):
        env = self._run_and_capture([
            r"Source\ThirdPerson\Tasks\t\HangingChain.cpp",
            "Content/Tasks/t/ABP_HangingChain.uasset",
            r"Source\ThirdPerson\Tasks\t\HangingChain.h",
        ])
        self.assertEqual(json.loads(env[SUBMITTED_FILES_ENV]), [
            "Content/Tasks/t/ABP_HangingChain.uasset",
            "Source/ThirdPerson/Tasks/t/HangingChain.cpp",
            "Source/ThirdPerson/Tasks/t/HangingChain.h",
        ])

    def test_parent_environment_is_copied_and_manifest_is_overwritten(self):
        env = self._run_and_capture([])
        self.assertEqual(env["CRAFTBENCH_PARENT_ENV_CANARY"], "preserved")
        self.assertEqual(env[SUBMITTED_FILES_ENV], "[]")

    def test_non_relative_or_traversing_internal_paths_fail_closed(self):
        for bad in ("../reference/answer.uasset", "/absolute/file.uasset",
                    r"C:\outside\file.uasset", "Content//double.uasset"):
            with self.subTest(path=bad):
                with self.assertRaises(ValueError):
                    _canonical_submitted_relpaths([bad])


if __name__ == "__main__":
    unittest.main()

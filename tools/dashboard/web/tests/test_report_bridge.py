"""Tests for the single-run report bridge — render_run_report / render_report_response.

Synthesizes a small ``runs/<id>/`` + matching ``tasks/<id>.md`` tree in a tempdir
(mirroring the on-disk shape run-agent writes) and asserts the bridge:

  * renders full HTML containing the task id + outcome markers when a verifier
    report IS present (rich case);
  * still renders the banner (task id + overall) when ``verifier`` is ``None`` and
    no rich Aura inputs exist (graceful-degrade case);
  * raises a clean ``LookupError`` for an unknown run_id, and the ``response``
    helper turns that into a ``(html, 404)`` instead of crashing;
  * rejects a path-traversal run_id rather than reading outside ``runs/``;
  * never crashes when the submission dir / task spec are absent.

No fastapi, no UE, no server. Pure ``unittest``; run via the dashboard venv:

    tools/dashboard/.venv/bin/python -m unittest \
        tools.dashboard.web.tests.test_report_bridge
"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.dashboard.web.report_bridge import (
    RunNotFoundError,
    render_report_response,
    render_run_report,
    write_static_report,
)

# A verifier report.json in the single-task shape render.py:normalize_report reads.
_VERIFIER_REPORT = {
    "task_id": "gp-alpha",
    "overall": "PASS",
    "duration_seconds": 128.4,
    "submission_sha": "deadbeef",
    "ue_version": "5.7.4",
    "host": {"os": "Darwin", "arch": "arm64"},
    "layers": {
        "L1": {
            "status": "pass",
            "duration_seconds": 97.3,
            "notes": ["target CraftBenchTemplateEditor: exit 0"],
            "log_excerpt": "Build succeeded\nPASS: L1 build",
        },
        "L2": {
            "status": "pass",
            "duration_seconds": 31.0,
            "notes": ["Functional Test Passed"],
            "log_excerpt": "Test Passed: SanityFunctionalTest",
        },
    },
}

_TASK_MD = """\
## Task ID

gp-alpha

## Primary concept

BeginPlay logging

## Prompt given to the agent

Make the actor log a greeting when the level starts.

## Verifier layers used

L1, L2

## Verifier specification

Drive the actor in PIE and assert the greeting appears in the log.
"""


def _write_run(
    repo_root: Path,
    run_id: str,
    *,
    task: str = "tasks/gp-alpha.md",
    model: str = "claude-p:claude-sonnet-4-6",
    overall: str = "PASS",
    verifier: object = _VERIFIER_REPORT,
    submission: dict[str, str] | None = None,
) -> Path:
    """Create runs/<run_id>/result.json (+ optional submission/) and return its dir."""
    run_dir = repo_root / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "run_id": run_id,
        "task": task,
        "model": model,
        "overall": overall,
        "agent": {
            "exit_code": 0,
            "duration_s": 20.27,
            "summary": "Implemented the greeting log.",
            "tool_use_count": 5,
            "mcp_tool_use_count": 0,
            "tool_names": ["Read", "Edit"],
            "cost_usd": 0.15,
            "num_turns": 6,
        },
        "verifier": verifier,
    }
    (run_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    if submission:
        sub = run_dir / "submission"
        for rel, content in submission.items():
            dst = sub / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(content, encoding="utf-8")
    return run_dir


def _write_task(repo_root: Path, task_id: str = "gp-alpha", body: str = _TASK_MD) -> Path:
    tasks_dir = repo_root / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    path = tasks_dir / f"{task_id}.md"
    path.write_text(body, encoding="utf-8")
    return path


class TestRenderRunReport(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # -- rich case: verifier report + task spec + submission ------------------

    def test_full_run_renders_html_with_task_and_outcome(self) -> None:
        run_id = "20260603-000000-gp-alpha-claude-p-claude-sonnet-4-6"
        _write_task(self.repo)
        _write_run(
            self.repo,
            run_id,
            submission={"Source/CraftBenchTemplate/SanityActor.cpp": "// greeting\n"},
        )

        html = render_run_report(self.repo, run_id)

        self.assertIsInstance(html, str)
        self.assertIn("<!DOCTYPE html>", html)
        # Task id appears in the banner.
        self.assertIn("gp-alpha", html)
        # Outcome marker (render.py uppercases the banner outcome).
        self.assertIn("PASS", html)
        # Per-layer verification rendered from the inline report.
        self.assertIn("L1", html)
        self.assertIn("L2", html)
        # Task-spec excerpt (prompt) flowed through find_task_spec/parse.
        self.assertIn("Make the actor log a greeting", html)
        # Submission file rendered.
        self.assertIn("SanityActor.cpp", html)

    # -- graceful degrade: verifier is None -----------------------------------

    def test_verifier_null_still_renders_banner(self) -> None:
        run_id = "20260603-010000-gp-alpha-claude-p"
        # No task .md, no submission, verifier=None: only the synthesized banner.
        _write_run(
            self.repo,
            run_id,
            overall="AGENT_FAILED",
            verifier=None,
            submission=None,
        )

        html = render_run_report(self.repo, run_id)

        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("gp-alpha", html)
        self.assertIn("AGENT_FAILED", html)

    def test_missing_task_spec_does_not_crash(self) -> None:
        # verifier report present, but no tasks/gp-alpha.md on disk.
        run_id = "20260603-020000-gp-alpha-claude-p"
        _write_run(self.repo, run_id)
        html = render_run_report(self.repo, run_id)
        self.assertIn("gp-alpha", html)
        # Prompt excerpt absent (no spec) but page still produced.
        self.assertNotIn("Make the actor log a greeting", html)

    def test_missing_submission_dir_does_not_crash(self) -> None:
        run_id = "20260603-030000-gp-alpha-claude-p"
        _write_task(self.repo)
        _write_run(self.repo, run_id, submission=None)
        html = render_run_report(self.repo, run_id)
        self.assertIn("gp-alpha", html)

    # -- capture artifacts ----------------------------------------------------

    def test_artifacts_section_rendered_with_route_addressed_imgs(self) -> None:
        run_id = "20260603-060000-gp-alpha-claude-p"
        _write_task(self.repo)
        run_dir = _write_run(self.repo, run_id)
        art = run_dir / "artifacts"
        art.mkdir()
        (art / "shot-0002.png").write_bytes(b"\x89PNG2")
        (art / "shot-0001.png").write_bytes(b"\x89PNG1")
        (art / "notes.txt").write_text("not an image", encoding="utf-8")

        html = render_run_report(self.repo, run_id)

        self.assertIn(">Artifacts<", html)
        # <img> tags addressed at the dashboard's artifact route, sorted by name.
        self.assertIn(f'src="/api/run/{run_id}/artifact/shot-0001.png"', html)
        self.assertIn(f'src="/api/run/{run_id}/artifact/shot-0002.png"', html)
        self.assertLess(html.index("shot-0001.png"), html.index("shot-0002.png"))
        # Non-PNG files are not artifacts.
        self.assertNotIn("notes.txt", html)

    def test_no_artifacts_section_without_artifacts_dir(self) -> None:
        run_id = "20260603-070000-gp-alpha-claude-p"
        _write_task(self.repo)
        _write_run(self.repo, run_id)
        html = render_run_report(self.repo, run_id)
        self.assertNotIn(">Artifacts<", html)

    # -- unknown run_id -------------------------------------------------------

    def test_unknown_run_id_raises_lookup_error(self) -> None:
        (self.repo / "runs").mkdir(parents=True, exist_ok=True)
        with self.assertRaises(LookupError):
            render_run_report(self.repo, "does-not-exist")
        # And the concrete subclass.
        with self.assertRaises(RunNotFoundError):
            render_run_report(self.repo, "does-not-exist")

    def test_run_id_with_path_separator_rejected(self) -> None:
        # A run_id is a directory name, never a path; traversal must not read out.
        _write_task(self.repo)
        secret = self.repo / "secret.json"
        secret.write_text("{}", encoding="utf-8")
        with self.assertRaises(LookupError):
            render_run_report(self.repo, "../secret")
        with self.assertRaises(LookupError):
            render_run_report(self.repo, "sub/dir")

    # -- container-nested runs (runs/<backend>/<run_id>/) ---------------------

    def test_nested_backend_run_resolves(self) -> None:
        # run.py's default layout: runs/<backend>/<run_id>/result.json.
        run_id = "20260710-000000-gp-alpha-claude-p-sonnet"
        _write_task(self.repo)
        _write_run(self.repo, f"claude-p/{run_id}")  # nests under runs/claude-p/
        # Rewrite result.json's run_id to the leaf name (the collected value).
        rj = self.repo / "runs" / "claude-p" / run_id / "result.json"
        data = json.loads(rj.read_text(encoding="utf-8"))
        data["run_id"] = run_id
        rj.write_text(json.dumps(data), encoding="utf-8")

        html = render_run_report(self.repo, run_id)
        self.assertIn("gp-alpha", html)
        self.assertIn("PASS", html)

    def test_flat_run_wins_over_nested_same_name(self) -> None:
        # A direct child of runs/ takes precedence over a container twin.
        run_id = "20260710-010000-gp-alpha-claude-p"
        _write_task(self.repo)
        _write_run(self.repo, run_id, overall="PASS")
        _write_run(self.repo, f"claude-p/{run_id}", overall="FAIL_NO_EDITS")
        html = render_run_report(self.repo, run_id)
        self.assertIn("PASS", html)
        self.assertNotIn("FAIL_NO_EDITS", html)


class TestRenderReportResponse(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_response_ok_for_real_run(self) -> None:
        run_id = "20260603-040000-gp-alpha-claude-p"
        _write_task(self.repo)
        _write_run(self.repo, run_id)
        html, status = render_report_response(self.repo, run_id)
        self.assertEqual(status, 200)
        self.assertIn("gp-alpha", html)
        self.assertIn("<!DOCTYPE html>", html)

    def test_response_404_for_unknown_run(self) -> None:
        (self.repo / "runs").mkdir(parents=True, exist_ok=True)
        html, status = render_report_response(self.repo, "nope")
        self.assertEqual(status, 404)
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("nope", html)
        self.assertIn("not found", html.lower())

    def test_response_500_for_corrupt_result_json(self) -> None:
        run_id = "20260603-050000-corrupt"
        run_dir = self.repo / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "result.json").write_text("{ this is not json", encoding="utf-8")
        html, status = render_report_response(self.repo, run_id)
        self.assertEqual(status, 500)
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn(run_id, html)

    def test_response_never_raises_for_path_traversal(self) -> None:
        (self.repo / "runs").mkdir(parents=True, exist_ok=True)
        html, status = render_report_response(self.repo, "../etc")
        self.assertEqual(status, 404)
        self.assertIn("<!DOCTYPE html>", html)


def _write_aura_run(repo_root: Path, run_id: str, *,
                    verdict: str = "PASS",
                    posthog_url: str | None = None) -> Path:
    """runs/aura-product/<run_id>/ in the graded-harness shape: summary.json
    (the envelope) + a DECOY driver-schema result.json (no verdict/overall —
    exactly what run_graded leaves on disk) + deliverable/ + artifacts/."""
    run_dir = repo_root / "runs" / "aura-product" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "task_id": "gp-alpha",
        "model": "sonnet-5",
        "transport": "aura-product",
        "project": "C:\\cb\\scratch\\CraftBenchGraded",
        "verdict": verdict,
        "est_cost_usd": 0.0587,
        "graded_workdir": "C:\\cb\\wd\\deadbeef00",
        "agent": {
            "tool_calls": 4,
            "by_tool": {"execute_unreal_python": 1, "edit_cpp_file": 2,
                        "trigger_live_coding": 1},
        },
        "timings": {"drive_s": 176.9, "aura_execution_time": 122.0,
                    "grade_s": 472.3},
        "verifier": dict(_VERIFIER_REPORT),
    }
    if posthog_url:
        summary["posthog_url"] = posthog_url
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    # The TS driver's own result.json — WRONG schema for the report; the bridge
    # must prefer summary.json or the page renders "unknown".
    (run_dir / "result.json").write_text(
        json.dumps({"duration_s": 122.0, "model_pinned": "Sonnet-5"}),
        encoding="utf-8")
    deliv = run_dir / "deliverable" / "Source" / "CraftBenchTemplate"
    deliv.mkdir(parents=True, exist_ok=True)
    (deliv / "SanityActor.cpp").write_text("// greeting\n", encoding="utf-8")
    art = run_dir / "artifacts"
    art.mkdir(exist_ok=True)
    (art / "cp01.png").write_bytes(b"\x89PNG")
    return run_dir


class TestAuraProductEnvelope(unittest.TestCase):
    """summary.json (aura-product graded runs) must win over the TS driver's
    result.json, carry the run-summary table, and pick up deliverable/."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_summary_json_preferred_over_driver_result_json(self) -> None:
        run_id = "gp-alpha-20260722-215836"
        _write_task(self.repo)
        _write_aura_run(self.repo, run_id)
        html = render_run_report(self.repo, run_id)
        self.assertIn("gp-alpha", html)
        self.assertIn("PASS", html)          # from summary.verdict via verifier
        self.assertNotIn(">unknown<", html)  # the decoy result.json lost

    def test_run_summary_table_carries_model_cost_tools(self) -> None:
        run_id = "gp-alpha-20260722-215837"
        _write_aura_run(self.repo, run_id)
        html = render_run_report(self.repo, run_id)
        self.assertIn("Run summary", html)
        self.assertIn("sonnet-5", html)
        self.assertIn("$0.0587", html)
        self.assertIn("edit_cpp_file", html)
        self.assertIn("472.3s", html)

    def test_measured_quantities_carry_their_explanations(self) -> None:
        # Owner ask 2026-08-06 #6: the two numbers PostHog disagrees with are
        # labeled with WHAT they measure so the difference reads as expected.
        run_id = "gp-alpha-20260806-000001"
        _write_aura_run(self.repo, run_id)
        html = render_run_report(self.repo, run_id)
        self.assertIn("model spend", html)
        self.assertIn("thread-billed — includes tool/sub-agent turns; "
                      "PostHog&#x27;s main trace shows less", html)
        self.assertIn("agent time", html)
        self.assertIn("wall clock incl. editor/tool work; PostHog shows LLM "
                      "generation time only", html)

    def test_page_heading_is_the_envelope_task_id(self) -> None:
        # Owner ask 2026-08-06 #1: heading = task name, from data. The
        # aura-product envelope may carry a set-qualified id.
        run_id = "gp-alpha-20260806-000002"
        run_dir = _write_aura_run(self.repo, run_id)
        summary = json.loads(
            (run_dir / "summary.json").read_text(encoding="utf-8"))
        summary["task_id"] = "bp-g2/gp-alpha"
        (run_dir / "summary.json").write_text(json.dumps(summary),
                                              encoding="utf-8")
        html = render_run_report(self.repo, run_id)
        self.assertIn(">bp-g2/gp-alpha</h1>", html)
        self.assertNotIn("task verification", html)

    def test_deliverable_dir_rendered_as_submission(self) -> None:
        run_id = "gp-alpha-20260722-215838"
        _write_aura_run(self.repo, run_id)
        html = render_run_report(self.repo, run_id)
        self.assertIn("SanityActor.cpp", html)

    def test_posthog_trace_rendered_as_clickable_link(self) -> None:
        # aura-product envelopes stamp posthog_url (run_graded); the run-summary
        # table must draw it as an anchor — report.html is a static file, so a
        # bare URL string would be dead text.
        run_id = "gp-alpha-20260722-215840"
        url = "https://us.posthog.com/project/000000/llm-analytics/traces/th-123"
        _write_aura_run(self.repo, run_id, posthog_url=url)
        html = render_run_report(self.repo, run_id)
        self.assertIn("posthog trace", html)
        self.assertIn(f'href="{url}"', html)

    def test_no_posthog_url_no_trace_row(self) -> None:
        # Absent config/thread = absent field = absent row — never a blank cell.
        run_id = "gp-alpha-20260722-215841"
        _write_aura_run(self.repo, run_id)
        html = render_run_report(self.repo, run_id)
        self.assertNotIn("posthog trace", html)


class TestWriteStaticReport(unittest.TestCase):
    """write_static_report: report.html lands IN the run dir with run-dir-
    relative artifact hrefs (no /api/run route — it must work double-clicked)."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_static_report_written_with_relative_artifact_hrefs(self) -> None:
        run_id = "gp-alpha-20260722-215839"
        _write_task(self.repo)
        run_dir = _write_aura_run(self.repo, run_id)
        out = write_static_report(run_dir, self.repo)
        self.assertEqual(out, run_dir / "report.html")
        html = out.read_text(encoding="utf-8")
        self.assertIn("PASS", html)
        self.assertIn('src="artifacts/cp01.png"', html)
        self.assertNotIn("/api/run/", html)

    def test_static_report_for_baseline_result_json(self) -> None:
        run_id = "20260722-000000-gp-alpha-claude-p"
        _write_task(self.repo)
        run_dir = _write_run(self.repo, run_id,
                             submission={"Source/A.cpp": "// x\n"})
        out = write_static_report(run_dir, self.repo)
        html = out.read_text(encoding="utf-8")
        self.assertIn("gp-alpha", html)
        self.assertIn("PASS", html)
        self.assertIn("A.cpp", html)

    def test_static_report_raises_without_envelope(self) -> None:
        empty = self.repo / "runs" / "aura-product" / "empty-run"
        empty.mkdir(parents=True)
        with self.assertRaises(LookupError):
            write_static_report(empty, self.repo)


def _write_preview_bundle(run_dir: Path, *, status: str | None = "ok",
                          stills: tuple[str, ...] = ("hero.png", "angle_000.png"),
                          video: bool = True, notes: list[str] | None = None,
                          raw_status_text: str | None = None) -> Path:
    """``runs/<run>/preview/`` as the LIVE capture leaves it — the ADR-2 sibling
    of the envelope the bridge just read. No pointer key is written anywhere:
    the bundle is found because it is THERE, next to summary.json."""
    bundle = run_dir / "preview"
    (bundle / "stills").mkdir(parents=True, exist_ok=True)
    for name in stills:
        (bundle / "stills" / name).write_bytes(b"\x89PNG\r\n\x1a\n" + name.encode())
    if video:
        (bundle / "surround.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42")
    if raw_status_text is not None:
        (bundle / "live_capture.json").write_text(raw_status_text, encoding="utf-8")
    elif status is not None:
        (bundle / "live_capture.json").write_text(
            json.dumps({"status": status, "notes": list(notes or [])}),
            encoding="utf-8")
    return bundle


def _strip_generated(html_doc: str) -> str:
    """Drop the footer wall-clock stamp so two renders compare byte-for-byte."""
    return re.sub(r"Generated [^ ]+ ", "Generated <ts> ", html_doc)




class TestEnvelopeHardening(unittest.TestCase):
    """2026-07-23 review fixes: corruption stays LOUD (no silent fallthrough to
    the wrong-schema driver result.json), set-qualified task_ids resolve their
    spec, and the bridge stays importable without fastapi."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_corrupt_summary_does_not_fall_through_to_driver_result(self) -> None:
        # A killed harness leaves a truncated summary.json beside the TS
        # driver's result.json — that must be a 500, not a 200 garbage page.
        run_id = "gp-alpha-20260723-000001"
        run_dir = _write_aura_run(self.repo, run_id)
        (run_dir / "summary.json").write_text("{ truncated", encoding="utf-8")
        with self.assertRaises(ValueError):
            render_run_report(self.repo, run_id)
        html, status = render_report_response(self.repo, run_id)
        self.assertEqual(status, 500)
        self.assertIn("<!DOCTYPE html>", html)

    def test_set_qualified_task_id_still_finds_the_spec(self) -> None:
        # aura-product summary.json can record "craftbench-tasks/<id>"; the
        # spec lookup wants the bare id.
        run_id = "gp-alpha-20260723-000002"
        _write_task(self.repo)  # tasks/gp-alpha.md
        run_dir = _write_aura_run(self.repo, run_id)
        summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
        summary["task_id"] = "some-set/gp-alpha"
        (run_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        html = render_run_report(self.repo, run_id)
        self.assertIn("Make the actor log a greeting", html)

    def test_bridge_importable_without_fastapi(self) -> None:
        # cb's eval tail writes report.html on installs that never installed
        # the UI deps — importing the bridge must not execute web/app.py.
        import subprocess
        import sys as _sys
        repo_root = Path(__file__).resolve().parents[4]
        probe = (
            "import sys, importlib.abc\n"
            "class Block(importlib.abc.MetaPathFinder):\n"
            "    def find_spec(self, name, path=None, target=None):\n"
            "        if name.split('.')[0] == 'fastapi':\n"
            "            raise ModuleNotFoundError('fastapi blocked')\n"
            "sys.meta_path.insert(0, Block())\n"
            "import tools.dashboard.web.report_bridge as rb\n"
            "assert hasattr(rb, 'write_static_report')\n"
            "print('IMPORT-OK')\n"
        )
        cp = subprocess.run([_sys.executable, "-c", probe], cwd=str(repo_root),
                            capture_output=True, text=True, timeout=60)
        self.assertEqual(cp.returncode, 0, cp.stderr)
        self.assertIn("IMPORT-OK", cp.stdout)


if __name__ == "__main__":
    unittest.main()

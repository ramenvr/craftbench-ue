"""Smoke tests for the Textual TUI — build the app from a synthetic Snapshot.

WHY these are smoke tests, not pixel snapshots: the TUI is a thin read-only view
over the frozen data layer; the interesting logic (the matrix/head-to-head/
grounding math) is already exercised in ``test_collect.py``. Here we only assert
that the app *constructs its widgets without raising* against a realistic
Snapshot, that the pure cell/header helpers render the expected text, and that
the run-detail modal mounts. We build the Snapshot the same way ``test_collect``
does (a synthetic ``tasks/`` + ``runs/`` tempdir collected once), so the TUI is
tested against real ``collect()`` output, not a hand-mocked object.

``textual`` is a UI-only dep (``requirements.txt``); if it is not installed the
whole module skips rather than failing the pure-stdlib suite.

Run from the repo root::

    python3 -m unittest tools.dashboard.tests.test_tui
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.dashboard.collect import collect
from tools.dashboard.model import LayerResult, Run, Snapshot

try:  # textual is a UI-only dep; skip the whole module if it is absent.
    import textual  # noqa: F401

    _HAS_TEXTUAL = True
except ImportError:  # pragma: no cover - environment without the UI dep
    _HAS_TEXTUAL = False


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


# A small verifier_stdout.txt so the detail modal exercises the layer rows path.
_GOLDEN_STDOUT = """\
CraftBench verifier report
  task_id   : gp-alpha
  L1  : PASS    [exit=0, warn=2] log=/tmp/x/l1.log
        - target CraftBenchTemplateEditor: exit 0 in 50.0s
  L2  : FAIL    [exit=3, tests=0/1] log=/tmp/x/l2.log
        - filter: Project.Functional Tests.Maps.L_X.XTest
  overall   : FAIL
"""


def _task_md(name: str, capability: str, *, prompt: str = "Do the thing.") -> str:
    return (
        f"# {name}\n\n"
        "## Task ID and metadata\n\n"
        f"- task_id: {name}\n"
        "- tier: T1\n"
        f"- capability_bucket: {capability}\n"
        "- set: internal-1\n\n"
        "## Prompt given to the agent\n\n"
        f"> {prompt}\n\n"
        "## Verifier layers used\n\nL1, L2\n"
    )


def _result_json(run_id: str, task: str, model: str, overall: str, *, cost=0.3) -> str:
    return json.dumps(
        {
            "run_id": run_id,
            "task": task,
            "model": model,
            "overall": overall,
            "verifier": None,
            "agent": {"exit_code": 0, "summary": "did stuff",
                      "duration_s": 100.0, "cost_usd": cost},
        }
    )


def _build_synthetic_snapshot() -> Snapshot:
    """Collect a realistic Snapshot: 2 tasks, 3 products, a head-to-head + a FAIL."""
    tmp = tempfile.mkdtemp()
    root = Path(tmp)
    tasks, runs = root / "tasks", root / "runs"

    _write(tasks / "gp-alpha.md", _task_md("gp-alpha", "Gameplay Programming"))
    _write(tasks / "mat-beta.md", _task_md("mat-beta", "Technical Art"))

    # gp-alpha run by two products -> head-to-head; one PASS, one FAIL (with stdout).
    _write(
        runs / "20260602-100000-gp-alpha-claude-p-opus" / "result.json",
        _result_json("20260602-100000-gp-alpha-claude-p-opus", "tasks/gp-alpha.md",
                     "claude-p:opus", "PASS"),
    )
    _write(
        runs / "20260602-110000-gp-alpha-aura-mcp-claude-sonnet-4-6" / "result.json",
        _result_json("20260602-110000-gp-alpha-aura-mcp-claude-sonnet-4-6",
                     "tasks/gp-alpha.md", "aura-mcp:claude-sonnet-4-6", "FAIL"),
    )
    _write(
        runs / "20260602-110000-gp-alpha-aura-mcp-claude-sonnet-4-6" / "verifier_stdout.txt",
        _GOLDEN_STDOUT,
    )
    # mat-beta: a single FAIL_NO_EDITS run -> failures + coverage-gap views.
    _write(
        runs / "20260602-130000-mat-beta-claude-p-opus-4-7" / "result.json",
        _result_json("20260602-130000-mat-beta-claude-p-opus-4-7", "tasks/mat-beta.md",
                     "claude-p:opus-4-7", "FAIL_NO_EDITS"),
    )
    return collect(root)


def _empty_snapshot() -> Snapshot:
    """A no-runs, no-tasks Snapshot (edge case the panels must tolerate)."""
    tmp = tempfile.mkdtemp()
    root = Path(tmp)
    (root / "tasks").mkdir(parents=True)
    (root / "runs").mkdir(parents=True)
    return collect(root)


@unittest.skipUnless(_HAS_TEXTUAL, "textual not installed (UI-only dep)")
class TestPureHelpers(unittest.TestCase):
    """The non-Textual helpers render the expected text — no app needed."""

    def setUp(self) -> None:
        from tools.dashboard import tui

        self.tui = tui
        self.snap = _build_synthetic_snapshot()

    def test_cell_text_pass_fail_mixed_none(self):
        passing = Run("r", "t", "p:m", "p", "m", "PASS", True, None, None, None, "", None, [], None)
        failing = Run("r", "t", "p:m", "p", "m", "FAIL", False, None, None, None, "", "x", [], None)
        self.assertIn("1/1", self.tui._cell_text([passing]))
        self.assertIn("0/1", self.tui._cell_text([failing]))
        self.assertIn("1/2", self.tui._cell_text([passing, failing]))  # mixed
        self.assertEqual(self.tui._cell_text([]), self.tui._GLYPH_NONE)

    def test_format_totals_has_live_and_counts(self):
        line = self.tui._format_totals(self.snap, tick=1)
        self.assertIn("LIVE", line)
        self.assertIn("tasks", line)
        self.assertIn("runs", line)

    def test_newest_failures_newest_first(self):
        fails = self.tui._newest_failures(self.snap)
        self.assertTrue(fails)
        self.assertFalse(any(r.passed for r in fails))
        # newest (mat-beta 13:00) before older (gp-alpha 11:00)
        self.assertEqual(fails[0].task_id, "mat-beta")

    def test_undercovered_tasks(self):
        under = dict(self.tui._tasks_undercovered(self.snap))
        # mat-beta run by exactly one product -> undercovered (n=1).
        self.assertEqual(under.get("mat-beta"), 1)
        # gp-alpha run by two products -> NOT in the undercovered list.
        self.assertNotIn("gp-alpha", under)

    def test_empty_capabilities_none_when_all_covered(self):
        # Both capabilities have >=1 run, so none is empty.
        self.assertEqual(self.tui._empty_capabilities(self.snap), [])


@unittest.skipUnless(_HAS_TEXTUAL, "textual not installed (UI-only dep)")
class TestAppBuilds(unittest.IsolatedAsyncioTestCase):
    """Mount the app via Textual's pilot and assert it builds without raising.

    Every assertion runs INSIDE the ``run_test()`` context — leaving it tears the
    app down (no screens on the stack), so we must not return the pilot/app out.
    ``refresh_seconds=0`` disables the auto-refresh timer for determinism, and
    ``repo_root`` is irrelevant because a ``snapshot=`` is injected (no disk read).
    """

    def _make_app(self, snap: Snapshot):
        from tools.dashboard.tui import DashboardApp

        # refresh_seconds<=0 disables the timer so the test is deterministic.
        return DashboardApp(Path("."), refresh_seconds=0, snapshot=snap)

    async def test_builds_widgets(self):
        from textual.widgets import DataTable, Static

        snap = _build_synthetic_snapshot()
        app = self._make_app(snap)
        async with app.run_test() as pilot:
            await pilot.pause()
            # Header totals populated, matrix has the right column count, panels exist.
            totals = app.query_one("#totals", Static)
            self.assertIn("LIVE", str(totals.render()))
            table = app.query_one("#matrix", DataTable)
            # 2 fixed columns (task, capability) + 3 product columns.
            self.assertEqual(len(table.columns), 2 + len(snap.products))
            self.assertEqual(table.row_count, len(snap.tasks))
            # side panels exist.
            for pid in ("#failures", "#coverage", "#headtohead"):
                self.assertIsNotNone(app.query_one(pid, Static))

    async def test_empty_snapshot_does_not_raise(self):
        from textual.widgets import DataTable

        snap = _empty_snapshot()
        app = self._make_app(snap)
        async with app.run_test() as pilot:
            await pilot.pause()
            table = app.query_one("#matrix", DataTable)
            self.assertEqual(table.row_count, 0)

    async def test_refresh_action_repaints(self):
        snap = _build_synthetic_snapshot()
        app = self._make_app(snap)
        async with app.run_test() as pilot:
            await pilot.pause()
            # 'r' forces a re-collect/repaint; must not raise. (repo_root="." here
            # has no runs/, so collect returns an empty snapshot — still safe.)
            await pilot.press("r")
            await pilot.pause()

    async def test_row_selection_opens_detail_modal(self):
        from textual.widgets import DataTable
        from tools.dashboard.tui import RunDetailScreen

        snap = _build_synthetic_snapshot()
        app = self._make_app(snap)
        async with app.run_test() as pilot:
            await pilot.pause()
            # Focus the matrix, then Enter selects the cursor row -> RowSelected ->
            # the detail modal is pushed onto the screen stack.
            table = app.query_one("#matrix", DataTable)
            table.focus()
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            self.assertIsInstance(app.screen, RunDetailScreen)


@unittest.skipUnless(_HAS_TEXTUAL, "textual not installed (UI-only dep)")
class TestRunDetailScreen(unittest.IsolatedAsyncioTestCase):
    """The detail screen renders layer rows and the no-text fallback."""

    async def test_renders_layers_and_fallback(self):
        from tools.dashboard.tui import RunDetailScreen

        with_layers = Run(
            "r1", "gp-alpha", "aura-mcp:claude-sonnet-4-6", "aura-mcp",
            "claude-sonnet-4-6", "FAIL", False, None, 100.0, 0.4, "summary",
            "L2 failed", [LayerResult("L1", "pass", "exit=0"),
                          LayerResult("L2", "fail", "filter: X")], None,
        )
        no_layers = Run(
            "r2", "gp-alpha", "claude-p:opus", "claude-p", "opus",
            "PASS", True, None, 50.0, 0.3, "ok", None, [], None,
        )
        screen = RunDetailScreen("gp-alpha", "two products", [with_layers, no_layers])
        # _render_run is pure; assert both branches produce text without raising.
        with_text = screen._render_run(with_layers)
        without_text = screen._render_run(no_layers)
        self.assertIn("L1", with_text)
        self.assertIn("L2", with_text)
        self.assertIn("blocker", with_text)
        self.assertIn("no per-layer text captured", without_text)


def _live_run(
    run_id="20260604-120000-gp-x-aura-mcp-claude-sonnet-4-6",
    task_id="gp-x", product="aura-mcp:claude-sonnet-4-6", phase="running",
    step=12, max_steps=40, current_tool="generate_cpp_file", tool_count=28,
    tokens_in=41000, tokens_out=6000, elapsed_s=38.2, result=None, error=None,
    stale=False,
):
    from tools.dashboard.live import LiveRun

    return LiveRun(run_id, task_id, product, phase, step, max_steps, current_tool,
                   tool_count, tokens_in, tokens_out, elapsed_s, result, error, stale)


@unittest.skipUnless(_HAS_TEXTUAL, "textual not installed (UI-only dep)")
class TestLiveActiveHelpers(unittest.TestCase):
    """Pure helpers for the live Active-runs row + tool-tape (spec §8)."""

    def setUp(self) -> None:
        from tools.dashboard import tui

        self.tui = tui

    def test_active_glyph_running_and_stale(self):
        self.assertIn("▶", self.tui._active_glyph("running"))
        self.assertIn("⚠", self.tui._active_glyph("running", stale=True))

    def test_active_row_cells_full(self):
        cells = self.tui._active_row_cells(_live_run())
        self.assertEqual(len(cells), 6)
        self.assertIn("gp-x", cells[0])
        self.assertIn("running", cells[1])
        self.assertIn("generate_cpp_file", cells[2])
        self.assertIn("12/40", cells[3])
        self.assertIn("28", cells[4])

    def test_active_row_cells_coarse_mode(self):
        # step/current_tool/tool_count null (today's Playwright aura-agent) → phase only.
        cells = self.tui._active_row_cells(
            _live_run(step=None, current_tool=None, tool_count=None,
                      tokens_in=None, tokens_out=None)
        )
        self.assertIn("running", cells[1])
        self.assertIn("—", cells[2])
        self.assertIn("—", cells[3])

    def test_active_row_cells_stale_flag(self):
        self.assertIn("stale", self.tui._active_row_cells(_live_run(stale=True))[1])

    def test_tape_line_variants(self):
        self.assertIn("generate_cpp_file",
                      self.tui._tape_line({"type": "tool_call", "tool": "generate_cpp_file"}))
        self.assertIn("✓", self.tui._tape_line({"type": "tool_result", "ok": True}))
        self.assertIn("✗", self.tui._tape_line({"type": "tool_result", "ok": False}))
        self.assertIn("finish", self.tui._tape_line({"type": "finish", "finish_reason": "stop"}))
        self.assertIsNone(self.tui._tape_line({"type": "something-unknown"}))


@unittest.skipUnless(_HAS_TEXTUAL, "textual not installed (UI-only dep)")
class TestActivePanel(unittest.IsolatedAsyncioTestCase):
    """The Active-runs panel renders injected live rows and opens the tape."""

    def _app(self, rows):
        from tools.dashboard.tui import DashboardApp

        return DashboardApp(Path("."), refresh_seconds=0, snapshot=_empty_snapshot(),
                            live_provider=lambda: rows)

    async def test_active_panel_renders_live_rows(self):
        from textual.widgets import DataTable

        rows = [_live_run(run_id="r1", task_id="gp-a"),
                _live_run(run_id="r2", task_id="gp-b", phase="grading")]
        app = self._app(rows)
        async with app.run_test() as pilot:
            await pilot.pause()
            table = app.query_one("#active", DataTable)
            self.assertEqual(table.row_count, 2)
            self.assertEqual(len(table.columns), 6)

    async def test_active_panel_empty_does_not_raise(self):
        from textual.widgets import DataTable

        app = self._app([])
        async with app.run_test() as pilot:
            await pilot.pause()
            self.assertEqual(app.query_one("#active", DataTable).row_count, 0)

    async def test_active_row_selection_opens_tape(self):
        from textual.widgets import DataTable
        from tools.dashboard.tui import LiveTapeScreen

        app = self._app([_live_run(run_id="r1", task_id="gp-a")])
        async with app.run_test() as pilot:
            await pilot.pause()
            table = app.query_one("#active", DataTable)
            table.focus()
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            self.assertIsInstance(app.screen, LiveTapeScreen)


@unittest.skipUnless(_HAS_TEXTUAL, "textual not installed (UI-only dep)")
class TestLiveTapeScreen(unittest.IsolatedAsyncioTestCase):
    """The live tape appends injected events incrementally (spec §8)."""

    async def test_tape_appends_injected_events(self):
        from textual.widgets import Static
        from tools.dashboard.tui import DashboardApp, LiveTapeScreen

        app = DashboardApp(Path("."), refresh_seconds=0, snapshot=_empty_snapshot(),
                           live_provider=lambda: [])
        events = [
            {"seq": 1, "type": "tool_call", "tool": "generate_cpp_file",
             "input_preview": "UCBLaunchAbility"},
            {"seq": 2, "type": "tool_result", "ok": True, "ms": 100},
        ]
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = LiveTapeScreen(
                "r1", Path("."),
                tail_provider=lambda after: [e for e in events if e["seq"] > after],
                refresh_seconds=0,
            )
            await app.push_screen(screen)
            await pilot.pause()
            text = "\n".join(screen._lines)
            self.assertIn("generate_cpp_file", text)
            self.assertIn("✓", text)
            self.assertEqual(screen._after_seq, 2)


if __name__ == "__main__":
    unittest.main()

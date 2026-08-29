"""Unit tests for the read-only LIVE reader — SYNTHETIC runs/ in a tempdir.

Pure stdlib (``unittest``); no UE, no Aura, no textual/fastapi, no network, no real
API key. These assert that ``live.active_runs()`` globs ``runs/*/status.json``
(plus ``runs/<backend>/<id>/status.json`` one container level down),
filters out terminal runs (keeping briefly-terminal ones), flags ``stale`` when a
``running``/``launching`` row's ``updated_at`` is older than ``stale_after_s``
(with an INJECTED ``now`` so the test is deterministic), and that
``tail_events()`` returns only ``events.jsonl`` lines with ``seq`` > ``after_seq``
while tolerating a torn (partial) final line. Garbage / torn / missing
``status.json`` is skipped (best-effort), never raised.

The fixture ``status.json`` / ``events.jsonl`` are HAND-CRAFTED to match the
normative disk contract in spec §5.1 / §5.2 byte-for-byte in structure.

Run from the repo root:

    python3 -m unittest tools.dashboard.tests.test_live
"""

from __future__ import annotations

import datetime as _dt
import json
import tempfile
import unittest
from pathlib import Path

from tools.dashboard.live import LiveRun, active_runs, tail_events

# A fixed "now" so stale detection is deterministic. All fixture updated_at values
# are expressed relative to this instant.
NOW = _dt.datetime(2026, 6, 4, 12, 0, 0, tzinfo=_dt.timezone.utc)


def _iso(dt: _dt.datetime) -> str:
    return dt.astimezone(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ago(seconds: float) -> str:
    return _iso(NOW - _dt.timedelta(seconds=seconds))


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _status(
    run_id: str,
    *,
    task_id: str = "gp-gas-launch",
    product: str = "aura-agent:claude-sonnet-4-6",
    phase: str = "running",
    step=12,
    max_steps=40,
    current_tool="generate_cpp_file",
    tool_count=28,
    tokens_in=41000,
    tokens_out=6000,
    started_age_s: float = 100.0,
    updated_age_s: float = 0.0,
    elapsed_s=38.2,
    result=None,
    error=None,
) -> str:
    """A spec §5.1 status.json object, atomically-rewritten-shape, as a string."""
    obj = {
        "schema": "craftbench.livestatus/v1",
        "run_id": run_id,
        "task_id": task_id,
        "product": product,
        "phase": phase,
        "step": step,
        "max_steps": max_steps,
        "current_tool": current_tool,
        "tool_count": tool_count,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "started_at": _ago(started_age_s),
        "updated_at": _ago(updated_age_s),
        "elapsed_s": elapsed_s,
        "result": result,
        "error": error,
    }
    return json.dumps(obj, indent=2)


# A spec §5.2 events.jsonl tape: phase, tool_call, tool_result, finish.
EVENTS_JSONL = (
    '{"ts":"2026-06-04T11:58:00Z","seq":1,"type":"phase","phase":"running"}\n'
    '{"ts":"2026-06-04T11:58:10Z","seq":41,"type":"tool_call","tool":"generate_cpp_file",'
    '"tool_call_id":"tc_1","input_preview":"UCBLaunchAbility..."}\n'
    '{"ts":"2026-06-04T11:58:13Z","seq":42,"type":"tool_result","tool_call_id":"tc_1",'
    '"ok":true,"ms":3100,"output_preview":"wrote 2 files"}\n'
    '{"ts":"2026-06-04T11:58:40Z","seq":60,"type":"finish","finish_reason":"stop",'
    '"tokens_in":41000,"tokens_out":6000}\n'
)


class LiveBase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.runs = self.root / "runs"

    def tearDown(self) -> None:
        self._tmp.cleanup()


class TestActiveFiltering(LiveBase):
    def test_terminal_phases_excluded_active_kept(self):
        _write(self.runs / "r-running" / "status.json",
               _status("r-running", phase="running"))
        _write(self.runs / "r-launching" / "status.json",
               _status("r-launching", phase="launching"))
        _write(self.runs / "r-grading" / "status.json",
               _status("r-grading", phase="grading"))
        _write(self.runs / "r-queued" / "status.json",
               _status("r-queued", phase="queued"))
        # Terminal phases that must be filtered out.
        for term in ("done", "error", "timeout", "cancelled"):
            _write(self.runs / f"r-{term}" / "status.json",
                   _status(f"r-{term}", phase=term))

        rows = active_runs(self.root, now=NOW)
        ids = {r.run_id for r in rows}
        self.assertEqual(
            ids, {"r-running", "r-launching", "r-grading", "r-queued"})

    def test_nested_backend_runs_discovered(self):
        # run.py's per-backend folders: runs/<backend>/<run_id>/status.json is
        # one container level down and must show up alongside flat runs.
        _write(self.runs / "flat" / "status.json", _status("flat"))
        _write(self.runs / "claude-p" / "nested" / "status.json",
               _status("nested"))
        rows = active_runs(self.root, now=NOW)
        self.assertEqual({r.run_id for r in rows}, {"flat", "nested"})

    def test_returns_liverun_with_spec_fields(self):
        _write(self.runs / "r1" / "status.json", _status("r1"))
        rows = active_runs(self.root, now=NOW)
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertIsInstance(r, LiveRun)
        self.assertEqual(r.run_id, "r1")
        self.assertEqual(r.task_id, "gp-gas-launch")
        self.assertEqual(r.product, "aura-agent:claude-sonnet-4-6")
        self.assertEqual(r.phase, "running")
        self.assertEqual(r.step, 12)
        self.assertEqual(r.max_steps, 40)
        self.assertEqual(r.current_tool, "generate_cpp_file")
        self.assertEqual(r.tool_count, 28)
        self.assertEqual(r.tokens_in, 41000)
        self.assertEqual(r.tokens_out, 6000)
        self.assertAlmostEqual(r.elapsed_s, 38.2)
        self.assertIsNone(r.result)
        self.assertIsNone(r.error)
        self.assertFalse(r.stale)

    def test_liverun_is_frozen(self):
        _write(self.runs / "r1" / "status.json", _status("r1"))
        r = active_runs(self.root, now=NOW)[0]
        with self.assertRaises(Exception):
            r.phase = "done"  # type: ignore[misc]

    def test_coarse_mode_nulls_preserved(self):
        # Coarse mode: step/current_tool/tool_count null (spec §5.1).
        _write(
            self.runs / "coarse" / "status.json",
            _status("coarse", step=None, current_tool=None, tool_count=None),
        )
        r = active_runs(self.root, now=NOW)[0]
        self.assertIsNone(r.step)
        self.assertIsNone(r.current_tool)
        self.assertIsNone(r.tool_count)

    def test_no_runs_dir_returns_empty(self):
        # Missing runs/ entirely → [] (never raise).
        self.assertEqual(active_runs(self.root, now=NOW), [])

    def test_result_and_error_surfaced(self):
        _write(
            self.runs / "e" / "status.json",
            _status("e", phase="grading", result="PASS", error=None),
        )
        r = active_runs(self.root, now=NOW)[0]
        self.assertEqual(r.result, "PASS")


class TestStaleDetection(LiveBase):
    def test_running_old_update_is_stale(self):
        # updated 45s ago, threshold 30s, phase running → stale.
        _write(self.runs / "r" / "status.json",
               _status("r", phase="running", updated_age_s=45))
        r = active_runs(self.root, now=NOW, stale_after_s=30.0)[0]
        self.assertTrue(r.stale)

    def test_launching_old_update_is_stale(self):
        _write(self.runs / "r" / "status.json",
               _status("r", phase="launching", updated_age_s=45))
        r = active_runs(self.root, now=NOW, stale_after_s=30.0)[0]
        self.assertTrue(r.stale)

    def test_running_fresh_update_not_stale(self):
        _write(self.runs / "r" / "status.json",
               _status("r", phase="running", updated_age_s=5))
        r = active_runs(self.root, now=NOW, stale_after_s=30.0)[0]
        self.assertFalse(r.stale)

    def test_grading_old_update_not_stale(self):
        # Stale only applies to running/launching (spec §5.1), not grading.
        _write(self.runs / "r" / "status.json",
               _status("r", phase="grading", updated_age_s=999))
        r = active_runs(self.root, now=NOW, stale_after_s=30.0)[0]
        self.assertFalse(r.stale)

    def test_queued_old_update_not_stale(self):
        _write(self.runs / "r" / "status.json",
               _status("r", phase="queued", updated_age_s=999))
        r = active_runs(self.root, now=NOW, stale_after_s=30.0)[0]
        self.assertFalse(r.stale)

    def test_threshold_boundary_strictly_greater(self):
        # Exactly stale_after_s old → NOT stale (strictly older required).
        _write(self.runs / "r" / "status.json",
               _status("r", phase="running", updated_age_s=30))
        r = active_runs(self.root, now=NOW, stale_after_s=30.0)[0]
        self.assertFalse(r.stale)

    def test_now_defaults_to_real_clock(self):
        # With no injected now, a fresh updated_at (relative to wall clock) is
        # not stale. Use a tiny-age status built off real now.
        real_now = _dt.datetime.now(_dt.timezone.utc)
        fresh = _iso(real_now)
        obj = json.loads(_status("r", phase="running"))
        obj["updated_at"] = fresh
        _write(self.runs / "r" / "status.json", json.dumps(obj))
        r = active_runs(self.root)[0]  # now=None → real clock
        self.assertFalse(r.stale)


class TestGracefulSkip(LiveBase):
    def test_garbage_json_skipped(self):
        _write(self.runs / "good" / "status.json", _status("good"))
        _write(self.runs / "garbage" / "status.json", "{not json at all,,,")
        _write(self.runs / "empty" / "status.json", "")
        _write(self.runs / "torn" / "status.json", _status("torn")[:40])  # truncated
        rows = active_runs(self.root, now=NOW)
        self.assertEqual({r.run_id for r in rows}, {"good"})

    def test_missing_required_fields_skipped(self):
        # An object that parses but lacks phase/run_id is skipped, not crashed.
        _write(self.runs / "good" / "status.json", _status("good"))
        _write(self.runs / "nophase" / "status.json",
               json.dumps({"schema": "craftbench.livestatus/v1"}))
        _write(self.runs / "notobject" / "status.json", json.dumps([1, 2, 3]))
        rows = active_runs(self.root, now=NOW)
        self.assertEqual({r.run_id for r in rows}, {"good"})

    def test_bad_updated_at_not_stale_not_crash(self):
        # Unparseable updated_at on a running row → tolerated, just not stale.
        obj = json.loads(_status("r", phase="running"))
        obj["updated_at"] = "not-a-timestamp"
        _write(self.runs / "r" / "status.json", json.dumps(obj))
        rows = active_runs(self.root, now=NOW)
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0].stale)


class TestTailEvents(LiveBase):
    def setUp(self) -> None:
        super().setUp()
        self.run_dir = self.runs / "r1"
        _write(self.run_dir / "events.jsonl", EVENTS_JSONL)

    def test_tail_from_zero_returns_all(self):
        evs = tail_events(self.run_dir, 0)
        self.assertEqual([e["seq"] for e in evs], [1, 41, 42, 60])
        self.assertEqual(evs[1]["type"], "tool_call")
        self.assertEqual(evs[1]["tool"], "generate_cpp_file")

    def test_tail_incremental_by_seq(self):
        evs = tail_events(self.run_dir, 41)
        self.assertEqual([e["seq"] for e in evs], [42, 60])

    def test_tail_after_last_returns_empty(self):
        self.assertEqual(tail_events(self.run_dir, 60), [])
        self.assertEqual(tail_events(self.run_dir, 999), [])

    def test_accepts_run_id_against_repo_root_dir(self):
        # When given a bare run_id, it resolves runs/<run_id>/events.jsonl
        # relative to a runs-rooted dir. Verify the directory form is the
        # canonical one (a path to the run dir).
        evs = tail_events(str(self.run_dir), 41)
        self.assertEqual([e["seq"] for e in evs], [42, 60])

    def test_partial_last_line_tolerated(self):
        # A torn final line (writer mid-append) must be skipped, earlier ones kept.
        torn = EVENTS_JSONL + '{"ts":"2026-06-04T11:59:00Z","seq":61,"type":"too'
        _write(self.run_dir / "events.jsonl", torn)
        evs = tail_events(self.run_dir, 42)
        self.assertEqual([e["seq"] for e in evs], [60])  # 61 dropped (torn)

    def test_blank_and_garbage_lines_skipped(self):
        mixed = (
            '{"seq":1,"type":"phase","phase":"running"}\n'
            '\n'
            'not json\n'
            '{"seq":2,"type":"finish"}\n'
        )
        _write(self.run_dir / "events.jsonl", mixed)
        evs = tail_events(self.run_dir, 0)
        self.assertEqual([e["seq"] for e in evs], [1, 2])

    def test_line_without_seq_skipped(self):
        # A parseable object lacking seq can't be ordered → skip it.
        mixed = (
            '{"seq":5,"type":"phase"}\n'
            '{"type":"noise"}\n'
            '{"seq":6,"type":"finish"}\n'
        )
        _write(self.run_dir / "events.jsonl", mixed)
        evs = tail_events(self.run_dir, 0)
        self.assertEqual([e["seq"] for e in evs], [5, 6])

    def test_missing_events_file_returns_empty(self):
        self.assertEqual(tail_events(self.runs / "nope", 0), [])


class TestPureStdlib(unittest.TestCase):
    """live.py must be pure stdlib and must NOT import textual/fastapi nor the
    frozen ``model.py``/``collect.py``.

    Two checks, because the package ``__init__`` *eagerly* imports ``model`` and
    ``collect`` — so a live ``sys.modules`` probe after importing the package
    would false-positive on the frozen modules even though ``live.py`` itself
    doesn't touch them (mirrors the documented trap in ``test_collect.py``):

    1. A FRESH subprocess imports ``live`` and asserts textual/fastapi never load.
    2. ``live.py``'s OWN source must not import the frozen modules — checked by
       inspecting the module's globals (``model``/``collect`` would appear there
       if it did ``from . import model`` / ``import ...collect``).
    """

    def test_no_textual_or_fastapi_pulled_in(self):
        import subprocess
        import sys as _sys
        repo_root = Path(__file__).resolve().parents[3]
        code = (
            "import sys\n"
            "from tools.dashboard.live import active_runs, tail_events, LiveRun\n"
            "assert 'textual' not in sys.modules, 'live pulled in textual'\n"
            "assert 'fastapi' not in sys.modules, 'live pulled in fastapi'\n"
            "assert callable(active_runs) and callable(tail_events)\n"
        )
        proc = subprocess.run(
            [_sys.executable, "-c", code],
            cwd=str(repo_root), capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_live_does_not_import_frozen_model_or_collect(self):
        import importlib

        live = importlib.import_module("tools.dashboard.live")
        ns = vars(live)
        # If live.py did `from .model import ...` / `from .collect import ...`
        # the bound name OR the submodule would surface in its namespace.
        self.assertNotIn("model", ns, "live.py imports the frozen model.py")
        self.assertNotIn("collect", ns, "live.py imports the frozen collect.py")
        # Belt-and-suspenders: scan the source text for the forbidden imports.
        src = Path(live.__file__).read_text(encoding="utf-8")
        for token in ("import textual", "import fastapi",
                      "from .model", "from .collect",
                      "import tools.dashboard.model",
                      "import tools.dashboard.collect"):
            self.assertNotIn(token, src, f"live.py source contains '{token}'")


if __name__ == "__main__":
    unittest.main()

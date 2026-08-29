"""Unit tests for aura_rig.driver — SSE parse, drive_agent (seam), tree safety.

Fully offline: the /api/chat HTTP is an injected ``post_sse`` seam returning
canned SSE byte chunks; the filesystem helpers run on a temp tree.
"""

import json
import os
import shutil
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aura_rig import driver  # noqa: E402


# A canned /api/chat SSE stream (Aura's UI-message-stream shape: tool-input-start
# / tool-input-available / tool-output-available / text-delta / finishReason).
_CHAT_EVENTS = [
    {"type": "tool-input-start", "toolCallId": "c1", "toolName": "edit_cpp_file"},
    {"type": "tool-input-available", "toolCallId": "c1", "input": {"path": "A.cpp"}},
    {"type": "tool-output-available", "toolCallId": "c1", "output": {"ok": True}},
    {"type": "tool-input-start", "toolCallId": "c2", "toolName": "compile_blueprint"},
    {"type": "tool-input-available", "toolCallId": "c2", "input": {"bp": "BP_X"}},
    {"type": "tool-output-available", "toolCallId": "c2",
     "output": {"isError": True, "msg": "boom"}},
    {"type": "text-delta", "delta": "All "},
    {"type": "text-delta", "delta": "done."},
    {"type": "finish", "finishReason": "stop",
     "messageMetadata": {"totalUsage": {"inputTokens": 5, "outputTokens": 9}}},
]


def _sse_bytes(events) -> list:
    """Frame events as SSE 'data:' chunks (split across chunk boundaries)."""
    out = []
    for e in events:
        out.append(("data: " + json.dumps(e) + "\n").encode())
    out.append(b"data: [DONE]\n")
    return out


def _fake_post_sse(events):
    def _post(url, body, headers, timeout):
        # Record the body so tests can assert the model KEY + activeTool.
        _post.last = {"url": url, "body": body, "headers": headers}
        return iter(_sse_bytes(events))
    _post.last = None
    return _post


class TestParseChatStream(unittest.TestCase):
    def test_reconstructs_calls_and_text(self):
        dr = driver.parse_chat_stream(_CHAT_EVENTS)
        self.assertEqual(dr.tool_calls, 2)
        self.assertEqual(dr.tool_names, ["edit_cpp_file", "compile_blueprint"])
        self.assertEqual(dr.by_tool, {"edit_cpp_file": 1, "compile_blueprint": 1})
        self.assertEqual(dr.final_text, "All done.")
        self.assertEqual(dr.finish_reason, "stop")
        self.assertEqual(dr.calls[0]["input"], {"path": "A.cpp"})
        self.assertEqual(dr.calls[1]["output"], {"isError": True, "msg": "boom"})
        self.assertEqual(dr.usage, [{"inputTokens": 5, "outputTokens": 9}])

    def test_empty_stream(self):
        dr = driver.parse_chat_stream([])
        self.assertEqual(dr.tool_calls, 0)
        self.assertEqual(dr.final_text, "")
        self.assertIsNone(dr.finish_reason)


class TestIterSSE(unittest.TestCase):
    def test_handles_chunk_boundaries(self):
        # Split one event across two byte chunks.
        chunks = [b'data: {"type":"x",', b'"v":1}\n', b"data: [DONE]\n"]
        evs = list(driver.iter_sse_events(chunks))
        self.assertEqual(evs, [{"type": "x", "v": 1}])

    def test_skips_non_data_and_bad_json(self):
        chunks = [b"event: ping\n", b"data: not json\n", b'data: {"ok":1}\n']
        self.assertEqual(list(driver.iter_sse_events(chunks)), [{"ok": 1}])


class TestDriveAgent(unittest.TestCase):
    def test_drive_writes_trace_and_returns_result(self):
        with TemporaryDirectory() as td:
            run_dir = Path(td)
            post = _fake_post_sse(_CHAT_EVENTS)
            dr = driver.drive_agent(
                "Make it log.", task_id="t0", ts=123, model_key="sonnet-4.6",
                ceiling_s=10, run_dir=run_dir, post_sse=post, token="tok",
                log=lambda m: None,
            )
            self.assertEqual(dr.tool_calls, 2)
            self.assertEqual(dr.thread, "cb-graded-t0-123")
            # The POST body pins the KEY and activeTool.
            self.assertEqual(post.last["body"]["model"], "sonnet-4.6")
            self.assertTrue(post.last["body"]["activeTool"])
            self.assertEqual(post.last["headers"]["Authorization"], "Bearer tok")
            # Artifacts written.
            self.assertTrue((run_dir / "trace.jsonl").exists())
            self.assertTrue((run_dir / "trace.md").exists())
            md = (run_dir / "trace.md").read_text(encoding="utf-8")
            self.assertIn("edit_cpp_file", md)
            self.assertIn("All done.", md)
            # Raw trace.jsonl has one line per event (minus [DONE]).
            lines = (run_dir / "trace.jsonl").read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), len(_CHAT_EVENTS))

    def test_drive_survives_post_exception(self):
        def boom(url, body, headers, timeout):
            raise ConnectionError("editor died")
        with TemporaryDirectory() as td:
            dr = driver.drive_agent(
                "p", task_id="t", ts=1, model_key="sonnet-4.6", ceiling_s=5,
                run_dir=Path(td), post_sse=boom, token="x", log=lambda m: None)
            self.assertEqual(dr.tool_calls, 0)


class TestTaskSpec(unittest.TestCase):
    def test_scrubbed_prompt_strips_quoting(self):
        with TemporaryDirectory() as td:
            task = Path(td) / "t.md"
            task.write_text(
                "# Task\n\n## Prompt given to the agent\n\n"
                "> Make the actor log a message\n> on begin play.\n\n"
                "## Verifier specification\n\nSECRET ANSWER KEY\n")
            p = driver.scrubbed_prompt(task)
            self.assertIn("Make the actor log a message", p)
            self.assertIn("on begin play.", p)
            self.assertNotIn("SECRET ANSWER KEY", p)
            self.assertNotIn(">", p)

    def test_task_map_parse(self):
        with TemporaryDirectory() as td:
            task = Path(td) / "t.md"
            task.write_text("uses /Game/Maps/L_SpawnSequence and Content/Maps/L_SpawnSequence.umap")
            self.assertEqual(driver.task_map(task), "L_SpawnSequence")

    def test_task_map_none(self):
        with TemporaryDirectory() as td:
            task = Path(td) / "t.md"
            task.write_text("no map here")
            self.assertIsNone(driver.task_map(task))

    def test_task_map_multifixture_fallback(self):
        # Multi-fixture tasks declare maps only in a `## Verifier fixtures`
        # block — task_map must fall back to the FIRST fixture map so the
        # agent gets the right level opened (else NO_DELIVERABLE).
        with TemporaryDirectory() as td:
            task = Path(td) / "t.md"
            task.write_text(
                "## Verifier fixtures\n\n"
                "- L_GasLaunch :: AGasLaunchFunctionalTest\n"
                "- L_GasLaunchControl :: AGasLaunchControlFunctionalTest\n")
            self.assertEqual(driver.task_map(task), "L_GasLaunch")

    def test_task_map_foldered_umap_path(self):
        # Post-migration layout: Content/Maps/<task-id>/<map>.umap — the
        # regex tolerates one folder segment (incl. hyphens) before L_.
        with TemporaryDirectory() as td:
            task = Path(td) / "t.md"
            task.write_text(
                "uses Content/Maps/t0-sanity-log-on-beginplay/L_SanityTask.umap")
            self.assertEqual(driver.task_map(task), "L_SanityTask")

    def test_task_map_foldered_game_path(self):
        with TemporaryDirectory() as td:
            task = Path(td) / "t.md"
            task.write_text("open /Game/Maps/gp-timer-task/L_TimerTask please")
            self.assertEqual(driver.task_map(task), "L_TimerTask")


class TestMapPackagePath(unittest.TestCase):
    """map_package_path discovers the live project's umap location
    (root wins, else the one-level folder glob, else the flat fallback)."""

    def _project(self, root: Path) -> Path:
        proj = root / "CraftBenchTemplate"
        (proj / "Content" / "Maps").mkdir(parents=True)
        return proj

    def test_root_umap_yields_flat_path(self):
        with TemporaryDirectory() as td:
            proj = self._project(Path(td))
            (proj / "Content" / "Maps" / "L_SanityTask.umap").write_bytes(b"x")
            self.assertEqual(
                driver.map_package_path("L_SanityTask", project=proj),
                "/Game/Maps/L_SanityTask")

    def test_foldered_umap_yields_foldered_path(self):
        with TemporaryDirectory() as td:
            proj = self._project(Path(td))
            folder = proj / "Content" / "Maps" / "t0-sanity"
            folder.mkdir()
            (folder / "L_SanityTask.umap").write_bytes(b"x")
            self.assertEqual(
                driver.map_package_path("L_SanityTask", project=proj),
                "/Game/Maps/t0-sanity/L_SanityTask")

    def test_root_wins_over_folder(self):
        with TemporaryDirectory() as td:
            proj = self._project(Path(td))
            (proj / "Content" / "Maps" / "L_X.umap").write_bytes(b"x")
            folder = proj / "Content" / "Maps" / "some-task"
            folder.mkdir()
            (folder / "L_X.umap").write_bytes(b"x")
            self.assertEqual(
                driver.map_package_path("L_X", project=proj),
                "/Game/Maps/L_X")

    def test_missing_umap_falls_back_to_flat(self):
        with TemporaryDirectory() as td:
            proj = self._project(Path(td))
            self.assertEqual(
                driver.map_package_path("L_Nowhere", project=proj),
                "/Game/Maps/L_Nowhere")


class TestTreeSafety(unittest.TestCase):
    def _project(self, root: Path) -> Path:
        proj = root / "CraftBenchTemplate"
        src = proj / driver.SRC_REL
        src.mkdir(parents=True)
        (src / "A.cpp").write_text("orig A\n")
        (src / "sub").mkdir()
        (src / "sub" / "B.h").write_text("orig B\n")
        return proj

    def test_backup_then_restore_reverts_edits_and_deletes_new(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            proj = self._project(root)
            backup = root / "backup"
            n = driver.backup_tree(proj, backup)
            self.assertEqual(n, 2)

            # Agent edits A.cpp and creates C.cpp.
            (proj / driver.SRC_REL / "A.cpp").write_text("AGENT EDIT\n")
            (proj / driver.SRC_REL / "C.cpp").write_text("AGENT NEW\n")

            restored, deleted = driver.restore_tree(proj, backup)
            self.assertEqual(restored, 2)
            self.assertEqual(deleted, 1)
            self.assertEqual((proj / driver.SRC_REL / "A.cpp").read_text(encoding="utf-8"), "orig A\n")
            self.assertFalse((proj / driver.SRC_REL / "C.cpp").exists())

    def test_snapshot_diff_detects_new_and_changed(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            proj = self._project(root)
            src = proj / driver.SRC_REL
            before = driver.snapshot(src, repo=root)
            # Change A, add C.
            import time as _t
            _t.sleep(0.01)
            (src / "A.cpp").write_text("changed bigger content here\n")
            (src / "C.cpp").write_text("new\n")
            after = driver.snapshot(src, repo=root)
            new, chg = driver.diff_deliverable(before, after)
            self.assertTrue(any(k.endswith("C.cpp") for k in new))
            self.assertTrue(any(k.endswith("A.cpp") for k in chg))


class TestVerdict(unittest.TestCase):
    def test_verdict_mapping(self):
        self.assertEqual(driver.verdict_for_exit(0), "PASS")
        self.assertEqual(driver.verdict_for_exit(1), "FAIL")
        self.assertEqual(driver.verdict_for_exit(3), "SUBSTRATE-REJECT")
        self.assertEqual(driver.verdict_for_exit(4), "SANDBOX-REJECT")
        self.assertEqual(driver.verdict_for_exit(9), "exit9")


class TestGradeTaskResolution(unittest.TestCase):
    """grade() resolves the task spec through the dual-layout resolver — a set
    task by BARE id now resolves (the old literal f"tasks/{id}.md" pointed at a
    nonexistent root spec), folder-form specs resolve, and a missing/ambiguous
    id exits with the candidate list."""

    def setUp(self):
        self._td = TemporaryDirectory()
        self.repo = Path(self._td.name)
        (self.repo / "tasks" / "bp-g2").mkdir(parents=True)
        (self.repo / "tasks" / "bp-g2" / "gp-thing.md").write_text("# t\n")
        folder = self.repo / "tasks" / "concept-1" / "gp-folder"
        folder.mkdir(parents=True)
        (folder / "task.md").write_text("# f\n")
        # Keep grade()'s Windows short-workdir pinning inside the temp tree.
        self._wd_env = os.environ.get("CRAFTBENCH_WD_ROOT")
        os.environ["CRAFTBENCH_WD_ROOT"] = str(self.repo / "wd")

    def tearDown(self):
        if self._wd_env is None:
            os.environ.pop("CRAFTBENCH_WD_ROOT", None)
        else:
            os.environ["CRAFTBENCH_WD_ROOT"] = self._wd_env
        self._td.cleanup()

    def _grade(self, task_id):
        captured = {}

        class _CP:
            returncode = 0
            stdout = ""

        def fake_runner(cmd, cwd=None, capture_output=True, text=True,
                        timeout=None, env=None):
            captured["cmd"] = cmd
            captured["cwd"] = cwd
            return _CP()

        code, _out = driver.grade(task_id, repo=self.repo, runner=fake_runner,
                                  log=lambda m: None)
        return code, captured

    def _task_arg(self, captured):
        cmd = captured["cmd"]
        return cmd[cmd.index("--task") + 1]

    def test_bare_set_task_id_resolves(self):
        code, captured = self._grade("gp-thing")
        self.assertEqual(code, 0)
        self.assertEqual(self._task_arg(captured), "tasks/bp-g2/gp-thing.md")
        # The verifier subprocess still runs with cwd=repo (--task is repo-relative).
        self.assertEqual(captured["cwd"], str(self.repo))

    def test_set_qualified_and_folder_form_resolve(self):
        _, captured = self._grade("bp-g2/gp-thing")
        self.assertEqual(self._task_arg(captured), "tasks/bp-g2/gp-thing.md")
        _, captured = self._grade("concept-1/gp-folder")
        self.assertEqual(self._task_arg(captured), "tasks/concept-1/gp-folder/task.md")

    def test_missing_id_exits(self):
        with self.assertRaises(SystemExit) as cm:
            self._grade("nope")
        self.assertIn("no task spec found", str(cm.exception))

    def test_ambiguous_id_exits_listing_candidates(self):
        dup = self.repo / "tasks" / "concept-1" / "gp-thing"  # 2nd set defines it
        dup.mkdir(parents=True)
        (dup / "task.md").write_text("# dup\n")
        with self.assertRaises(SystemExit) as cm:
            self._grade("gp-thing")
        msg = str(cm.exception)
        self.assertIn("ambiguous", msg)
        self.assertIn("tasks/bp-g2/gp-thing.md", msg)
        self.assertIn("tasks/concept-1/gp-thing/task.md", msg)


class TestGradeVisibleCaptureAndSurfacing(unittest.TestCase):
    """grade()'s phase-3 surface: --visible/--capture composition (kwargs beat
    env, env beats nothing), the optional ``out`` dict that surfaces the graded
    workdir + copied artifacts + parsed report WITHOUT changing the (exit_code,
    stdout) return shape, and the end-of-grade workdir retention pass."""

    # CB_WORKDIR_RETENTION / CB_WARM_CACHE / CB_PREVIEW are popped alongside the
    # rest because each one silently RE-AIMS the retention pass (mode, warm-slot
    # refusal, the "none"->"slim" preview downgrade) — a developer who exported
    # one in their shell must not be able to flip these verdicts.
    _ENV = ("CB_VISIBLE", "CB_CAPTURE", "CRAFTBENCH_WD_ROOT", "CB_GRADE_FROM_LIVE",
            "CB_WORKDIR_RETENTION", "CB_WARM_CACHE", "CB_PREVIEW")

    def setUp(self):
        self._td = TemporaryDirectory()
        self.repo = Path(self._td.name)
        (self.repo / "tasks").mkdir(parents=True)
        (self.repo / "tasks" / "t0.md").write_text("# t\n")
        self._saved = {k: os.environ.pop(k, None) for k in self._ENV}
        os.environ["CRAFTBENCH_WD_ROOT"] = str(self.repo / "wd")

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self._td.cleanup()

    def _grade(self, stdout="", out=None, run_dir=None, **kw):
        captured = {}

        def fake_runner(cmd, cwd=None, capture_output=True, text=True,
                        timeout=None, env=None):
            captured["cmd"] = cmd

            class _CP:
                returncode = 0

            cp = _CP()
            cp.stdout = stdout
            return cp

        code, _ = driver.grade("t0", repo=self.repo, runner=fake_runner,
                               run_dir=run_dir, out=out, log=lambda m: None, **kw)
        return code, captured["cmd"]

    def test_default_no_flags(self):
        _, cmd = self._grade()
        self.assertNotIn("--visible", cmd)
        self.assertNotIn("--capture", cmd)

    def test_kwargs_add_flags(self):
        _, cmd = self._grade(visible=True, capture=True)
        self.assertIn("--visible", cmd)
        self.assertIn("--capture", cmd)

    def test_env_defaults_flags_when_kwargs_omitted(self):
        os.environ["CB_VISIBLE"] = "1"
        os.environ["CB_CAPTURE"] = "1"
        _, cmd = self._grade()
        self.assertIn("--visible", cmd)
        self.assertIn("--capture", cmd)

    def test_grade_from_live_env_forwards_substrate_flag(self):
        # CB_GRADE_FROM_LIVE=1 is the maintainer escape hatch for grading a
        # not-yet-committed substrate fix; default (unset) must stay HEAD.
        _, cmd = self._grade()
        self.assertNotIn("--substrate-from-live", cmd)
        os.environ["CB_GRADE_FROM_LIVE"] = "1"
        _, cmd = self._grade()
        self.assertIn("--substrate-from-live", cmd)

    def test_explicit_false_beats_env(self):
        os.environ["CB_VISIBLE"] = "1"
        os.environ["CB_CAPTURE"] = "1"
        _, cmd = self._grade(visible=False, capture=False)
        self.assertNotIn("--visible", cmd)
        self.assertNotIn("--capture", cmd)

    def test_out_surfaces_workdir_artifacts_and_report(self):
        # A fake graded workdir: <wd>/out/report.json + <wd>/out/artifacts/*.png
        wd = self.repo / "graded-wd"
        out_dir = wd / "out"
        (out_dir / "artifacts").mkdir(parents=True)
        (out_dir / "report.json").write_text(
            json.dumps({"overall": "pass", "layers": {"L1": {"status": "pass"}}}))
        (out_dir / "artifacts" / "shot1.png").write_bytes(b"\x89PNG")
        (out_dir / "artifacts" / "shot2.png").write_bytes(b"\x89PNG")
        run_dir = self.repo / "run"
        run_dir.mkdir()

        gout = {}
        code, _cmd = self._grade(
            stdout=f"json report: {(out_dir / 'report.json')}\n",
            out=gout, run_dir=run_dir)
        self.assertEqual(code, 0)
        self.assertEqual(gout["graded_workdir"], str(wd))
        self.assertEqual(gout["artifacts"],
                         ["artifacts/shot1.png", "artifacts/shot2.png"])
        self.assertTrue((run_dir / "artifacts" / "shot1.png").exists())
        self.assertTrue((run_dir / "report.json").exists())
        self.assertEqual(gout["report"]["overall"], "pass")

    def test_out_defaults_when_no_report_line(self):
        gout = {}
        run_dir = self.repo / "run2"
        run_dir.mkdir()
        self._grade(stdout="no marker", out=gout, run_dir=run_dir)
        self.assertEqual(gout["artifacts"], [])
        self.assertIsNone(gout["report"])
        # graded_workdir may still carry the Windows pinned prediction (or None
        # on POSIX) — it must at least be present as a key.
        self.assertIn("graded_workdir", gout)

    # -- workdir retention (the end-of-grade reclaim) ----------------------- #

    def _stub_fs_cleanup(self, **members):
        """Replace workdir_retention's LAZY fs_cleanup seam with a stub exposing
        ``members`` — the deleters live in the verifier package, and no unit test
        should need it on sys.path (let alone a real 5.54 GB workdir). Everything
        ABOVE the seam — mode resolution and every refusal — stays the real code."""
        from aura_rig import workdir_retention
        old = workdir_retention._fs_cleanup
        stub = SimpleNamespace(**members)
        workdir_retention._fs_cleanup = lambda: stub
        self.addCleanup(setattr, workdir_retention, "_fs_cleanup", old)
        return stub

    def _graded_wd(self, name, *, artifacts=()):
        """A fake graded workdir UNDER the wd-root (the tests' CRAFTBENCH_WD_ROOT),
        carrying an L1-pass report — i.e. one that passes every apply() refusal."""
        wd = self.repo / "wd" / name
        out_dir = wd / "out"
        (out_dir / "artifacts").mkdir(parents=True)
        (out_dir / "report.json").write_text(
            json.dumps({"overall": "pass", "layers": {"L1": {"status": "pass"}}}))
        (out_dir / "l1_build.log").write_text("build ok\n", encoding="utf-8")
        for a in artifacts:
            (out_dir / "artifacts" / a).write_bytes(b"\x89PNG")
        return wd

    def test_retention_runs_AFTER_the_artifact_copies_never_before(self):
        # THE regression test for the ordering rule. The run's only evidence —
        # report.json / l1_build.log / the --capture sweep — lives INSIDE the
        # workdir retention is about to strip, so the reclaim may only happen once
        # grade() has copied it all out. The injected slim is maximally hostile
        # (it deletes the ENTIRE workdir), so anything still present in run_dir
        # afterwards provably left the workdir BEFORE retention ran.
        wd = self._graded_wd("ordering", artifacts=("shot1.png", "shot2.png"))
        run_dir = self.repo / "run-order"
        run_dir.mkdir()
        slimmed = []

        def _slim(workdir, log=None):
            slimmed.append(str(workdir))
            shutil.rmtree(workdir)
            return SimpleNamespace(reclaimed_bytes=4_720_000_000, refused=False)

        self._stub_fs_cleanup(slim_workdir=_slim)

        gout = {}
        self._grade(stdout=f"json report: {wd / 'out' / 'report.json'}\n",
                    out=gout, run_dir=run_dir)

        self.assertEqual(slimmed, [str(wd)])        # retention really ran, on the wd
        self.assertFalse(wd.exists())               # ...and really destroyed it
        self.assertTrue((run_dir / "report.json").exists())
        self.assertTrue((run_dir / "l1_build.log").exists())
        self.assertTrue((run_dir / "artifacts" / "shot1.png").exists())
        self.assertEqual(gout["artifacts"],
                         ["artifacts/shot1.png", "artifacts/shot2.png"])
        self.assertEqual(gout["report"]["overall"], "pass")
        self.assertEqual(gout["workdir_retention"]["mode"], "slim")   # the default
        self.assertEqual(gout["workdir_retention"]["reclaimed_bytes"], 4_720_000_000)

    def test_graded_workdir_is_None_once_retention_deleted_the_dir(self):
        # Mode "none" removes the workdir outright. WITHOUT the existence guard the
        # run would still RECORD it, and cb._referenced_workdirs reads any
        # graded_workdir reference as "KEEP" — so a dead path would be protected
        # from `cb clean --workdirs` forever. Mirrors run.py:842.
        os.environ["CB_WORKDIR_RETENTION"] = "none"
        wd = self._graded_wd("doomed")
        run_dir = self.repo / "run-none"
        run_dir.mkdir()

        def _rmtree(workdir):
            shutil.rmtree(workdir, ignore_errors=True)
            return True

        self._stub_fs_cleanup(robust_rmtree=_rmtree)

        gout = {}
        self._grade(stdout=f"json report: {wd / 'out' / 'report.json'}\n",
                    out=gout, run_dir=run_dir)
        self.assertFalse(wd.exists())
        self.assertEqual(gout["workdir_retention"]["mode"], "none")
        self.assertIsNone(gout["graded_workdir"])
        # ...and the evidence still made it out first (same ordering rule).
        self.assertTrue((run_dir / "report.json").exists())

    def test_graded_workdir_is_None_when_the_workdir_never_materialized(self):
        # The guard is not retention-specific: a workdir a crash/reboot took out
        # between the grade and this write must not be recorded either. Retention
        # itself REFUSES here (nothing to reclaim) rather than erroring.
        ghost = self.repo / "wd" / "ghost"
        run_dir = self.repo / "run-ghost"
        run_dir.mkdir()
        gout = {}
        self._grade(stdout=f"json report: {ghost / 'out' / 'report.json'}\n",
                    out=gout, run_dir=run_dir)
        self.assertIsNone(gout["graded_workdir"])
        self.assertEqual(gout["workdir_retention"]["reason"], "workdir_missing")


# TestRunGradedResolveTask lived here until the 2026-08-28 public-release cut.
# It covered `run_graded._resolve_task`'s ambiguous-id message (the one that
# lists `bp-g2/twin` and `concept-1/twin` rather than saying "task not found").
# `aura_rig/run_graded.py` was the aura-product lane's spine and is not in this
# release. The behaviour itself is NOT lost: the set-qualified resolve is
# `aura_rig/tasks.py`'s job — it is the "single source of truth shared by the
# eval task-resolver ... the interactive [picker] and the resolve CLI"
# (tasks.py:12), whose ambiguity hint is at tasks.py:283 — and it is covered by
# tests/test_tasks.py. What went away was a duplicate assertion against a
# now-deleted caller, not the rule.


class TestProjectRel(unittest.TestCase):
    """driver.project_rel — multi-substrate dir resolution + validation
    (PROJECT_REL stays the default-substrate constant for back-compat)."""

    def _fake_repo(self, td: Path):
        for name in ("CraftBenchTemplate", "ThirdPersonTemplate"):
            sub = td / "UE-projects" / name
            sub.mkdir(parents=True)
            (sub / f"{name}.uproject").write_text("{}", encoding="utf-8")
        # A non-substrate dir (no .uproject) must NOT count as available.
        (td / "UE-projects" / "NotAProject").mkdir()
        return td

    def test_default_matches_the_constant(self):
        with TemporaryDirectory() as td:
            repo = self._fake_repo(Path(td))
            self.assertEqual(driver.project_rel(repo=repo), driver.PROJECT_REL)

    def test_known_substrates_resolve(self):
        with TemporaryDirectory() as td:
            repo = self._fake_repo(Path(td))
            self.assertEqual(driver.project_rel("CraftBenchTemplate", repo=repo),
                             "UE-projects/CraftBenchTemplate")
            self.assertEqual(driver.project_rel("ThirdPersonTemplate", repo=repo),
                             "UE-projects/ThirdPersonTemplate")

    def test_unknown_substrate_raises_listing_available(self):
        with TemporaryDirectory() as td:
            repo = self._fake_repo(Path(td))
            with self.assertRaises(ValueError) as cm:
                driver.project_rel("LyraStarter", repo=repo)
            msg = str(cm.exception)
            self.assertIn("LyraStarter", msg)
            self.assertIn("CraftBenchTemplate", msg)
            self.assertIn("ThirdPersonTemplate", msg)
            self.assertNotIn("NotAProject", msg)

    def test_uses_module_repo_by_default(self):
        with TemporaryDirectory() as td:
            repo = self._fake_repo(Path(td))
            old = driver.REPO
            driver.REPO = repo
            try:
                self.assertEqual(driver.project_rel("ThirdPersonTemplate"),
                                 "UE-projects/ThirdPersonTemplate")
                with self.assertRaises(ValueError):
                    driver.project_rel("Nope")
            finally:
                driver.REPO = old

    def test_src_rel_reads_game_module_with_fallback(self):
        with TemporaryDirectory() as td:
            repo = self._fake_repo(Path(td))
            # No manifest -> fall back to the substrate dir name.
            self.assertEqual(driver.src_rel("CraftBenchTemplate", repo=repo),
                             driver.SRC_REL)
            # Manifest game_module wins.
            (repo / "UE-projects" / "ThirdPersonTemplate" / "AGENT_WRITABLE.json"
             ).write_text('{"game_module": "TPGame"}', encoding="utf-8")
            self.assertEqual(driver.src_rel("ThirdPersonTemplate", repo=repo),
                             "Source/TPGame")


if __name__ == "__main__":
    unittest.main()

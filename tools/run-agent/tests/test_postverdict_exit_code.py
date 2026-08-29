"""A NON-GATING post-verdict step must not be able to author the exit code.

THE MEASURED BUG (2026-08-18 local time; run dirs are UTC-stamped,
which is why the id below reads 20260819), run
``runs/aura-mcp/20260819-004238-t1-dawn-fog-lighting-rig-aura-mcp-claude-sonnet-5``:

    result.json      overall = PASS   (L1 pass 310s, L2I pass 14/14)
    console          "Result: PASS  (agent 333.0s | verify 326.6s...)"
    then             PermissionError: [WinError 32] ... run.py:921
                       shutil.copy2(backup / rel, project_dir / rel)
    batch recorded   eval exit=1

That copy2 lives in ``_run_live_project``'s ``finally`` — the post-verdict
restore of the live writable area, which runs after grading is completely over.
An exception raised in a ``finally`` DISCARDS the pending ``return 0``, so it
propagated out of ``main()``, ``sys.exit(main())`` never received a value, and
CPython exited the process with 1. Every script that reads rc — the overnight
batch included — scored a certified PASS as a failed rep. Nothing in the run
bundle distinguishes that from a rep that genuinely failed to run.

WHAT THESE TESTS PIN, and what they deliberately do NOT:

  * a failing post-verdict step leaves the verdict-derived exit code alone
    (0 on PASS), and
  * every GENUINELY-GATING non-zero return still fires: 2 (transport error /
    no edits), 3 (verifier FAIL), 4 (live-run lock busy, hygiene stuck).
    Narrowing those would be far worse than the bug being fixed here, so half
    of this file exists to alarm if a future "make it robust" change swallows
    one of them.
  * the failure is still LOUD and RECORDED. "Non-gating" means it must not
    rewrite a verdict, never that it may pass in silence: a half-restored live
    tree is real contamination, and the refusal belongs to the NEXT run's
    pre-flight (dirty-substrate gate / live-hygiene quarantine, both exit 4),
    where it can still stop a bad measurement.
"""

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

import run as run_mod  # noqa: E402
import fairness as _fairness  # noqa: E402


#: The exact exception the measured run died on. Windows raises it whenever a
#: surviving editor still holds a .uasset/.umap the restore wants to overwrite.
WINERROR_32 = PermissionError(
    32, "The process cannot access the file because it is being used by "
        "another process")


def _mktree():
    """A minimal live-substrate shape: one pre-existing writable file."""
    root = Path(tempfile.mkdtemp(prefix="cb-postverdict-"))
    project = root / "substrate"
    src = project / "Source/CraftBenchTemplate"
    src.mkdir(parents=True)
    (src / "A.cpp").write_bytes(b"orig-A")
    (src / "B.cpp").write_bytes(b"orig-B")
    (project / "AGENT_WRITABLE.json").write_text(
        json.dumps({"writable": ["Source/CraftBenchTemplate/"]}),
        encoding="utf-8")
    run_dir = root / "run"
    run_dir.mkdir()
    return root, project, run_dir


def _writable_files_fn(project):
    prefix = "Source/CraftBenchTemplate/"

    def _fn():
        return [p for p in project.rglob("*")
                if p.is_file()
                and p.relative_to(project).as_posix().startswith(prefix)]
    return _fn


class TestRestoreNeverRaises(unittest.TestCase):
    """``_restore_live_writable`` — the containment itself."""

    def setUp(self):
        self.root, self.project, self.run_dir = _mktree()
        self.backup = self.run_dir / "live_backup"
        self.pre_rels = set()
        for p in _writable_files_fn(self.project)():
            rel = p.relative_to(self.project).as_posix()
            dst = self.backup / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(p.read_bytes())
            self.pre_rels.add(rel)

    def _restore(self):
        buf_out, buf_err = io.StringIO(), io.StringIO()
        with redirect_stdout(buf_out), redirect_stderr(buf_err):
            out = run_mod._restore_live_writable(
                self.project, self.backup, self.pre_rels,
                _writable_files_fn(self.project), run_dir=self.run_dir)
        return out, buf_out.getvalue() + buf_err.getvalue()

    def test_clean_restore_reverts_edits_and_removes_agent_files(self):
        (self.project / "Source/CraftBenchTemplate/A.cpp").write_bytes(b"agent")
        (self.project / "Source/CraftBenchTemplate/New.cpp").write_bytes(b"new")
        out, _ = self._restore()
        self.assertTrue(out["ok"])
        self.assertEqual(out["restored"], 2)
        self.assertEqual(out["removed"], 1)
        self.assertEqual(
            (self.project / "Source/CraftBenchTemplate/A.cpp").read_bytes(),
            b"orig-A")
        self.assertFalse(
            (self.project / "Source/CraftBenchTemplate/New.cpp").exists())

    def test_a_locked_file_does_not_raise(self):
        # THE regression: this is the call that exited the process with 1.
        real = run_mod.shutil.copy2

        def _copy2(src, dst, *a, **kw):
            if Path(src).name == "A.cpp":
                raise WINERROR_32
            return real(src, dst, *a, **kw)

        with mock.patch.object(run_mod.shutil, "copy2", _copy2):
            out, _ = self._restore()
        self.assertFalse(out["ok"])
        self.assertEqual([f["rel"] for f in out["failed_restore"]],
                         ["Source/CraftBenchTemplate/A.cpp"])

    def test_one_locked_file_does_not_abandon_the_rest(self):
        # The pre-fix loop stopped at the FIRST failure, so every file after it
        # in iteration order stayed at the agent's bytes — a contaminated tree
        # AND a crashed process from one lock.
        (self.project / "Source/CraftBenchTemplate/A.cpp").write_bytes(b"agent")
        (self.project / "Source/CraftBenchTemplate/B.cpp").write_bytes(b"agent")
        real = run_mod.shutil.copy2

        def _copy2(src, dst, *a, **kw):
            if Path(src).name == "A.cpp":
                raise WINERROR_32
            return real(src, dst, *a, **kw)

        with mock.patch.object(run_mod.shutil, "copy2", _copy2):
            out, _ = self._restore()
        self.assertEqual(out["restored"], 1)
        self.assertEqual(
            (self.project / "Source/CraftBenchTemplate/B.cpp").read_bytes(),
            b"orig-B")

    def test_an_undeletable_agent_file_does_not_raise(self):
        (self.project / "Source/CraftBenchTemplate/New.cpp").write_bytes(b"new")
        with mock.patch.object(Path, "unlink",
                               side_effect=WINERROR_32):
            out, _ = self._restore()
        self.assertFalse(out["ok"])
        self.assertEqual([f["rel"] for f in out["failed_remove"]],
                         ["Source/CraftBenchTemplate/New.cpp"])

    def test_an_unwalkable_tree_does_not_raise(self):
        # The rglob runs over a tree an editor may still be writing, so the WALK
        # can raise too — without containment the bug just moves one line up.
        def _boom():
            raise OSError("tree vanished mid-walk")

        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(buf):
            out = run_mod._restore_live_writable(
                self.project, self.backup, self.pre_rels, _boom,
                run_dir=self.run_dir)
        self.assertFalse(out["ok"])
        self.assertIn("tree vanished mid-walk", out["enumerate_error"])
        # ...and the pre-run files are still put back: the walk only decides
        # which AGENT-CREATED files to remove.
        self.assertEqual(out["restored"], 2)

    def test_a_deleted_parent_dir_is_recreated(self):
        # An agent that deleted a folder used to make every file under it
        # unrestorable (copy2 onto a missing parent raises).
        import shutil as _sh
        _sh.rmtree(self.project / "Source/CraftBenchTemplate")
        out, _ = self._restore()
        self.assertTrue(out["ok"])
        self.assertEqual(
            (self.project / "Source/CraftBenchTemplate/A.cpp").read_bytes(),
            b"orig-A")

    def test_failure_is_loud_and_recorded_not_silent(self):
        # Fail-closed is preserved by the NEXT run's gates, which need this
        # evidence; silence here would be the permissive-fake version of the fix.
        real = run_mod.shutil.copy2

        def _copy2(src, dst, *a, **kw):
            if Path(src).name == "A.cpp":
                raise WINERROR_32
            return real(src, dst, *a, **kw)

        with mock.patch.object(run_mod.shutil, "copy2", _copy2):
            _, text = self._restore()
        self.assertIn("NOT fully restored", text)
        self.assertIn("Source/CraftBenchTemplate/A.cpp", text)
        self.assertIn(str(self.backup), text)   # where the next run self-heals from
        recorded = json.loads(
            (self.run_dir / "live_restore.json").read_text(encoding="utf-8"))
        self.assertFalse(recorded["ok"])
        self.assertEqual([f["rel"] for f in recorded["failed_restore"]],
                         ["Source/CraftBenchTemplate/A.cpp"])

    def test_a_clean_restore_is_recorded_too(self):
        # A run whose bundle has NO live_restore.json predates the check; a
        # present-and-true one is the only positive evidence of a clean tree.
        self._restore()
        recorded = json.loads(
            (self.run_dir / "live_restore.json").read_text(encoding="utf-8"))
        self.assertTrue(recorded["ok"])
        self.assertEqual(recorded["expected"], 2)


class TestReportingCannotRaise(unittest.TestCase):
    """The error HANDLER must not become the new post-verdict raise.

    THE BLIND SPOT THIS CLOSES: every other test in this file drives the
    restore under ``redirect_stderr(io.StringIO())``. StringIO accepts any
    unicode, so those tests are structurally incapable of reaching the encoding
    hazard — they are evidence for containment of copy2/unlink/rglob and for
    nothing else. The tests here use a stream whose codec REJECTS what the
    report contains, and ``test_the_pre_fix_report_shape_raises_on_it``
    constructs the pre-fix statement so "fixed" is a measured difference rather
    than an assertion about code that was never exercised.

    SCOPE, measured rather than assumed (see ``run._report_line``): CPython's
    own ``sys.stderr`` is errors='backslashreplace' and would NOT have raised;
    the exposure is a REPLACED stderr — a tee/capture wrapper, a test driver,
    anything strict. That is exactly the stream constructed below.

    DISCRIMINATION, measured 2026-08-18 by running this class against the
    pre-fix run.py in a staged tree: 5 of the 7 ERRORED (4 with
    ``UnicodeEncodeError: 'ascii' codec can't encode character '—' in
    position 64`` out of ``run.py`` line 748, 1 with the raising log sink
    escaping through ``say``); 7 of 7 pass against the fixed run.py. The two
    that passed both ways are the guards below — they deliberately touch no
    harness code, they only prove the stream and the pre-fix statement really
    do reject.
    """

    #: A real Windows WinError-32 message on a Japanese system. Chosen over an
    #: invented string because the recurring cause here IS a locked file, and
    #: the harness runs on whatever locale the bench box has.
    LOCKED_JA = ("別のプロセスが使用中"
                 "のため、プロセスは"
                 "ファイルにアクセス"
                 "できません。")

    def setUp(self):
        self.root, self.project, self.run_dir = _mktree()
        self.backup = self.run_dir / "live_backup"
        self.pre_rels = set()
        for p in _writable_files_fn(self.project)():
            rel = p.relative_to(self.project).as_posix()
            dst = self.backup / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(p.read_bytes())
            self.pre_rels.add(rel)

    @staticmethod
    def _ascii_strict():
        """A stderr whose codec cannot take the report's own punctuation."""
        return io.TextIOWrapper(io.BytesIO(), encoding="ascii",
                                errors="strict", newline="")

    @staticmethod
    def _text(stream):
        stream.flush()
        return stream.buffer.getvalue().decode("ascii", "replace")

    # ---- the discriminating guards ---------------------------------------

    def test_the_stream_under_test_really_rejects(self):
        # Without this, the two "does not crash" tests below could be passing
        # on a stream that silently accepts everything, i.e. proving nothing.
        s = self._ascii_strict()
        with self.assertRaises(UnicodeEncodeError):
            s.write("—")            # the em-dash the report itself uses
        with self.assertRaises(UnicodeEncodeError):
            self._ascii_strict().write(self.LOCKED_JA)

    def test_the_pre_fix_report_shape_raises_on_it(self):
        # The pre-fix statements, verbatim. Measured 2026-08-18: the FIRST of
        # them raised `UnicodeEncodeError: 'ascii' codec can't encode character
        # '—' in position 64` — the block died on its own em-dash, before
        # any path or OS message was reached. This is the case the fix removes.
        item = {"rel": "Source/CraftBenchTemplate/A.cpp",
                "error": f"PermissionError: {self.LOCKED_JA}"}
        s = self._ascii_strict()
        with self.assertRaises(UnicodeEncodeError):
            print(f"ERROR: the live writable area was NOT fully restored "
                  f"(1 file(s) — the recurring cause is WinError 32)",
                  file=s)
        s2 = self._ascii_strict()
        with self.assertRaises(UnicodeEncodeError):
            print(f"  NOT RESTORED  {item['rel']} — {item['error']}",
                  file=s2)

    # ---- what the function must now do on that same stream ---------------

    def test_a_localized_os_message_does_not_crash_the_report(self):
        def _copy2(src, dst, *a, **kw):
            raise PermissionError(32, self.LOCKED_JA)

        err = self._ascii_strict()
        with mock.patch.object(run_mod.shutil, "copy2", _copy2), \
                redirect_stdout(io.StringIO()), redirect_stderr(err):
            out = run_mod._restore_live_writable(
                self.project, self.backup, self.pre_rels,
                _writable_files_fn(self.project), run_dir=self.run_dir)
        self.assertFalse(out["ok"])
        self.assertEqual(len(out["failed_restore"]), 2)
        # Degraded, but still emitted and still naming the file: the point of
        # the fallback is a weaker line, never a silent one.
        text = self._text(err)
        self.assertIn("NOT fully restored", text)
        self.assertIn("Source/CraftBenchTemplate/A.cpp", text)

    def test_a_non_ascii_path_does_not_crash_the_report(self):
        name = "Ünrestored.cpp"     # a name an agent can genuinely create
        try:
            (self.project / "Source/CraftBenchTemplate" / name).write_bytes(b"x")
        except (OSError, UnicodeError) as exc:   # pragma: no cover
            self.skipTest(f"filesystem will not hold a non-ASCII name: {exc}")
        err = self._ascii_strict()
        with mock.patch.object(Path, "unlink", side_effect=WINERROR_32), \
                redirect_stdout(io.StringIO()), redirect_stderr(err):
            out = run_mod._restore_live_writable(
                self.project, self.backup, self.pre_rels,
                _writable_files_fn(self.project), run_dir=self.run_dir)
        self.assertFalse(out["ok"])
        self.assertEqual([f["rel"] for f in out["failed_remove"]],
                         [f"Source/CraftBenchTemplate/{name}"])
        text = self._text(err)
        self.assertIn("NOT REMOVED", text)
        # backslashreplace keeps the name identifiable on an ASCII console.
        self.assertIn("nrestored.cpp", text)

    def test_the_evidence_file_lands_even_when_the_console_cannot_take_it(self):
        # A dropped/degraded console line must not be the only record — the
        # next run's operator reads live_restore.json, which is explicit UTF-8.
        def _copy2(src, dst, *a, **kw):
            raise PermissionError(32, self.LOCKED_JA)

        err = self._ascii_strict()
        with mock.patch.object(run_mod.shutil, "copy2", _copy2), \
                redirect_stdout(io.StringIO()), redirect_stderr(err):
            run_mod._restore_live_writable(
                self.project, self.backup, self.pre_rels,
                _writable_files_fn(self.project), run_dir=self.run_dir)
        recorded = json.loads(
            (self.run_dir / "live_restore.json").read_text(encoding="utf-8"))
        self.assertFalse(recorded["ok"])
        self.assertIn(self.LOCKED_JA, recorded["failed_restore"][0]["error"])

    def test_a_stream_that_refuses_everything_still_does_not_raise(self):
        # Last resort: even the ASCII-escaped byte write can fail (a closed
        # stream). Losing the line is acceptable; raising is not.
        class _Dead:
            encoding = "ascii"

            def write(self, _s):
                raise ValueError("I/O operation on closed file")

        def _copy2(src, dst, *a, **kw):
            raise WINERROR_32

        with mock.patch.object(run_mod.shutil, "copy2", _copy2), \
                redirect_stdout(io.StringIO()), redirect_stderr(_Dead()):
            out = run_mod._restore_live_writable(
                self.project, self.backup, self.pre_rels,
                _writable_files_fn(self.project), run_dir=self.run_dir)
        self.assertFalse(out["ok"])
        recorded = json.loads(
            (self.run_dir / "live_restore.json").read_text(encoding="utf-8"))
        self.assertEqual(len(recorded["failed_restore"]), 2)

    def test_a_raising_log_sink_does_not_escape(self):
        # `say` is injectable, so the "does not raise" claim has to cover a
        # caller-supplied sink too, not just the two OS calls.
        def _boom(_msg):
            raise RuntimeError("log sink is closed")

        err = self._ascii_strict()
        with redirect_stdout(io.StringIO()), redirect_stderr(err):
            out = run_mod._restore_live_writable(
                self.project, self.backup, self.pre_rels,
                _writable_files_fn(self.project), run_dir=self.run_dir,
                log=_boom)
        self.assertTrue(out["ok"])
        self.assertIn("log sink raised", self._text(err))


class _AgentResult:
    """Minimal AgentResult stand-in — only the fields the live path reads."""

    def __init__(self, exit_code=0, num_turns=7, tool_use_count=24,
                 tokens_in=1000, tokens_out=500):
        self.exit_code = exit_code
        self.num_turns = num_turns
        self.tool_use_count = tool_use_count
        self.mcp_tool_use_count = tool_use_count
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out
        self.duration_s = 333.0
        self.transcript = ""
        self.models_used = ["claude-sonnet-5"]
        self.summary = "transport error"

    def to_json(self):
        return "{}"


class TestLiveProjectExitCode(unittest.TestCase):
    """End-to-end through ``_run_live_project``: what the process exits with.

    Everything outside the function under test is substituted (adapter, lock,
    hygiene, verifier subprocess, result writer) so the ONLY thing these
    assertions can be measuring is the return-value contract.
    """

    def setUp(self):
        self.root, self.project, self.run_dir = _mktree()
        self.released = []

    def _args(self, model="aura-mcp:claude-sonnet-5", defer_editor=False):
        return SimpleNamespace(
            substrate_root=self.project, model=model,
            task=Path("tasks/bp/t1-dawn-fog-lighting-rig/task.md"),
            max_turns=200, timeout=2400, ue_root="Q:/UE_5.8",
            visible=False, capture=False, preamble_sha=None,
            defer_editor=defer_editor)

    def _run(self, *, verifier_rc=0, overall="PASS", agent=None,
             lock=None, hygiene_stuck=(), restore_explodes=True,
             model="aura-mcp:claude-sonnet-5", defer_editor=False, extra=()):
        """Drive _run_live_project with the whole world stubbed out."""
        agent = agent or _AgentResult()
        backup_dir = self.run_dir / "live_backup"
        real_copy2 = run_mod.shutil.copy2

        def _copy2(src, dst, *a, **kw):
            # Explode ONLY on the post-verdict restore (backup -> live tree),
            # never on the pre-run backup (live tree -> backup). This is the
            # exact direction the measured WinError 32 fired in.
            if restore_explodes and backup_dir in Path(src).parents:
                raise WINERROR_32
            return real_copy2(src, dst, *a, **kw)

        def _adapter_run(**kw):
            (self.project / "Source/CraftBenchTemplate/A.cpp").write_bytes(
                b"agent-edit")
            return agent

        def _acquire(_path):
            if lock is not None:
                raise lock
            return lambda: self.released.append(True)

        hygiene = SimpleNamespace(
            stuck=list(hygiene_stuck),
            as_dict=lambda: {"stuck": list(hygiene_stuck)})

        patches = [
            mock.patch.object(run_mod.shutil, "copy2", _copy2),
            mock.patch.object(run_mod, "acquire_live_run_lock", _acquire),
            mock.patch.object(run_mod, "quarantine_untracked_writable",
                              lambda *a, **kw: hygiene),
            mock.patch.object(run_mod, "ensure_aura_client_port",
                              lambda *a, **kw: None),
            mock.patch.object(run_mod, "make_adapter",
                              lambda *a, **kw: SimpleNamespace(
                                  name="stub", run=_adapter_run)),
            mock.patch.object(run_mod, "subprocess", SimpleNamespace(
                run=lambda *a, **kw: SimpleNamespace(
                    returncode=verifier_rc, stdout="", stderr=""))),
            mock.patch.object(run_mod, "verdict_from_verifier",
                              lambda rc, out: overall),
            mock.patch.object(run_mod, "_load_verifier_report",
                              lambda *a, **kw: {"overall": overall}),
            mock.patch.object(run_mod, "_collect_artifacts",
                              lambda *a, **kw: []),
            mock.patch.object(run_mod, "_apply_retention",
                              lambda *a, **kw: None),
            mock.patch.object(run_mod, "_verifier_workdir_args",
                              lambda *a, **kw: []),
            mock.patch.object(run_mod, "_verifier_workdir",
                              lambda *a, **kw: None),
            mock.patch.object(run_mod, "_write_result", lambda *a, **kw: None),
            *extra,
        ]
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(buf):
            for p in patches:
                p.start()
            try:
                rc = run_mod._run_live_project(
                    self._args(model, defer_editor), "run-id", self.run_dir,
                    "PROMPT")
            finally:
                for p in reversed(patches):
                    p.stop()
        return rc, buf.getvalue()

    # ---- the property this whole file exists for -------------------------

    def test_pass_survives_an_exploding_post_verdict_restore(self):
        rc, text = self._run()
        self.assertEqual(rc, 0, "a PASS whose post-verdict cleanup failed must "
                                "still exit 0 — this is the 2026-08-18 bug")
        self.assertIn("Result: PASS", text)
        self.assertIn("NOT fully restored", text)   # loud, not silent

    def test_the_live_run_lock_is_still_released(self):
        # Pre-fix, the raising copy2 skipped release_lock() entirely.
        self._run()
        self.assertEqual(self.released, [True])

    def test_a_failing_fairness_restore_also_leaves_the_code_alone(self):
        # The other post-verdict step in the same finally. unreal-mcp is the
        # backend that stages the answer key, and its restore is called twice
        # (pre-snapshot, then the finally safety net) — only the second one,
        # which is genuinely post-verdict, is made to fail here.
        calls = {"n": 0}

        def _restore(state, project_dir):
            calls["n"] += 1
            if calls["n"] >= 2:
                raise WINERROR_32

        extra = [
            # A REAL FairnessState, not a namespace with four of its eleven
            # fields. The namespace version broke the moment production read
            # a field it did not carry (`project_dir`, via _persist_state) --
            # and it broke as an ERROR in an unrelated assertion, which is the
            # expensive way to learn that a double has drifted. The dataclass
            # cannot drift: a new field arrives with its default.
            mock.patch.object(run_mod, "stage_fairness_hide",
                              lambda *a, **kw: _fairness.FairnessState(
                                  backup_root=self.project / ".cb-fairness-backup")),
            mock.patch.object(run_mod, "stage_task_isolation_hide",
                              lambda *a, **kw: None),
            mock.patch.object(run_mod, "stage_task_tree_isolation_hide",
                              lambda *a, **kw: None),
            mock.patch.object(run_mod, "stage_config_overlay_apply",
                              lambda *a, **kw: None),
            mock.patch.object(run_mod, "stage_fairness_restore", _restore),
        ]
        rc, text = self._run(model="unreal-mcp:claude-sonnet-5",
                             restore_explodes=False, extra=extra)
        self.assertEqual(rc, 0)
        self.assertIn("fairness restore failed", text)

    # ---- --defer-editor: the DRIVE owns the editor -----------------------

    def test_the_editor_is_stopped_before_anything_restores(self):
        """The reorder is only safe if the STOP moves too.

        Deferring the START past the hide means this cell never indexes the
        209-213 folders the restore puts back, so the restore becomes the
        trigger for a full UWorld-loading pass. What runs in the next ~50 s is
        collect_submission, the verifier and _restore_live_writable — and that
        last one never raises and leaves the agent's bytes in the live tree on
        WinError. A cheap retryable abort would have become a silent restore
        corruption on a graded cell.
        """
        from aura_rig import stack as _stack
        order = []
        extra = [
            mock.patch.object(run_mod, "_start_drive_editor",
                              lambda *a, **kw: None),
            mock.patch.object(_stack, "shutdown_drive_editor",
                              lambda *a, **kw: (order.append("stop"), True)[1]),
            mock.patch.object(run_mod, "stage_fairness_restore",
                              lambda *a, **kw: order.append("restore")),
        ]
        rc, _ = self._run(restore_explodes=False, defer_editor=True, extra=extra)
        self.assertEqual(rc, 0)
        self.assertEqual(order[:1], ["stop"],
                         "the editor was still up when a restore ran")
        self.assertIn("restore", order)

    def test_an_editor_that_never_comes_up_is_non_graded_and_still_restores(self):
        """An editor failure now happens POST-hide, so it must (a) stay out of
        every pass-rate — the grid cell has to remain open for a re-run, which
        sweep_mcp_lanes.sh decides with is_graded_verdict — and (b) still put
        the hidden trees back."""
        from adapters.base import VERDICT_EDITOR_NOT_READY, is_graded_verdict
        from aura_rig import stack as _stack
        wrote, restored = {}, []
        extra = [
            mock.patch.object(run_mod, "_start_drive_editor",
                              lambda *a, **kw: "editor :30010 did not bind"),
            # The `finally` teardown must not depend on this box's process
            # table (or reach a kill path) inside a unit test.
            mock.patch.object(_stack, "shutdown_drive_editor",
                              lambda *a, **kw: True),
            mock.patch.object(run_mod, "_write_result",
                              lambda rd, a, rid, ar, vr, overall, **kw:
                              wrote.__setitem__("overall", overall)),
            mock.patch.object(run_mod, "stage_fairness_restore",
                              lambda *a, **kw: restored.append(True)),
        ]
        rc, text = self._run(restore_explodes=False, defer_editor=True,
                             extra=extra)
        self.assertEqual(rc, 4)
        self.assertEqual(wrote.get("overall"), VERDICT_EDITOR_NOT_READY)
        self.assertFalse(is_graded_verdict(wrote.get("overall")))
        self.assertTrue(restored, "the fairness hide was left in place")
        self.assertIn("Non-graded", text)

    # ---- the gating returns must all survive the fix ---------------------

    def test_verifier_fail_still_returns_3(self):
        rc, _ = self._run(verifier_rc=1, overall="FAIL")
        self.assertEqual(rc, 3)

    def test_transport_error_still_returns_2(self):
        rc, _ = self._run(agent=_AgentResult(exit_code=1, num_turns=0,
                                             tool_use_count=0, tokens_in=0,
                                             tokens_out=0))
        self.assertEqual(rc, 2)

    def test_no_edits_still_returns_2(self):
        # An agent that ran but changed nothing: the snapshot is empty.
        extra = [mock.patch.object(
            run_mod, "make_adapter",
            lambda *a, **kw: SimpleNamespace(
                name="stub", run=lambda **kw2: _AgentResult()))]
        rc, _ = self._run(extra=extra)
        self.assertEqual(rc, 2)

    def test_lock_busy_still_returns_4(self):
        rc, _ = self._run(lock=run_mod.LiveRunLockBusy("held"))
        self.assertEqual(rc, 4)

    def test_stuck_hygiene_still_returns_4(self):
        rc, _ = self._run(hygiene_stuck=["Source/CraftBenchTemplate/A.cpp"])
        self.assertEqual(rc, 4)

    def test_a_real_crash_in_the_drive_still_propagates(self):
        # Containment must not turn a genuine mid-drive fault into a quiet
        # verdict. The finally logs and returns; the ORIGINAL exception is what
        # reaches the caller (pre-fix, the finally's own raise replaced it and
        # the real cause was lost from the traceback).
        def _boom(**kw):
            raise RuntimeError("adapter blew up mid-drive")

        extra = [mock.patch.object(
            run_mod, "make_adapter",
            lambda *a, **kw: SimpleNamespace(name="stub", run=_boom))]
        with self.assertRaises(RuntimeError) as ctx:
            self._run(extra=extra)
        self.assertIn("mid-drive", str(ctx.exception))




if __name__ == "__main__":
    unittest.main()

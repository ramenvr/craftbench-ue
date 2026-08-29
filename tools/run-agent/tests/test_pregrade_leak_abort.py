"""A cell that read verifier source must not buy a build and an editor session.

The gate creates no new non-graded route — ``leak_audit --void`` voids exactly
these cells after the fact — it only moves the decision ahead of the spend.
What is pinned, on BOTH arms:
  * the verifier subprocess is NEVER launched;
  * the verdict is FAIRNESS-BREACH and NOT graded, and the gate sits ahead of
    the empty-submission branch, whose FAIL_NO_EDITS IS graded;
  * the void record is stamped, so a reader of result.json alone learns why;
  * the fairness restore, the live writable restore and the lock release all
    still run, and the workspace lane's substrate copy is torn down — the abort
    takes no shortcut through cleanup;
  * the deliverable survives in ``submission/``: the abort skips the grade and
    the ``finally`` reverts the live tree, so this is the only copy left;
  * a transcript with EXPOSURE only (a park path in a tool result, which
    ``leak_audit`` warns on rather than voiding) is still GRADED — otherwise the
    gate would be a denominator opt-out any drive could take with one `ls`.
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

import leak_audit  # noqa: E402
import run as run_mod  # noqa: E402
from adapters.base import is_graded_verdict  # noqa: E402


#: The task these tests drive, and the leaked text, DISCOVERED together.
#:
#: Until 2026-08-24 the leak fixture was `SetCheckpointSchedule({1.0f, 2.0f})` —
#: a name of the fixture BASE class's public API, which appears in 66 of 117
#: task specs and 219 docs because DATASET.md Tier 1 publishes the
#: checkpoint-schedule shape for every task on purpose. This gate voids
#: PRE-GRADE, so those markers made it a denominator opt-out a drive could take
#: with one `Read`. The marker set is now PER-TASK.
#:
#: Discovered rather than named, and that is the load-bearing part: with a
#: hardcoded pair, the next change to the marker rule leaves this suite GREEN
#: while it measures nothing. It already would have — `gp-glide-stamina-bp`, the
#: task this suite used to name, yields no matchable marker under the current
#: rule (its distinctive assertions are inherited from the base class, which is
#: subtracted on purpose).
def _a_task_with_a_marker():
    repo = Path(__file__).resolve().parents[3]
    for spec in sorted(repo.glob("tasks/*/*/task.md")):
        rel = spec.relative_to(repo)
        marks = leak_audit.own_fixture_markers(Path("."), spec_path=rel)
        if marks:
            return rel, marks[0]
    return None, None


LEAK_TASK, LEAK_MARKER = _a_task_with_a_marker()
assert LEAK_MARKER, ("no task in the corpus yields a fixture marker, so this "
                     "suite cannot test the gate it exists for")

#: A tool result that served fixture BODY text. `fairness._STUB_BODY` is a
#: single comment line, so no marker can appear in a stubbed fixture — seeing
#: one means something served pre-stub bytes.
LEAKED = json.dumps({
    "role": "tool_result", "name": "query_unreal_project_assets",
    "content": "FinishTest(EFunctionalTestResult::Failed, TEXT(\"%s\"));"
               % LEAK_MARKER,
})
#: Exposure without consumption: the park's NAME shows up in a directory
#: listing. leak_audit classifies this `park` and deliberately does not void.
EXPOSED = json.dumps({
    "role": "tool_result", "name": "grep",
    "content": "C:/cb/.cb-fairness-hidden__tasks/",
})
CLEAN = json.dumps({"role": "tool_result", "name": "grep", "content": "no hits"})


class _AgentResult:
    def __init__(self, transcript):
        self.exit_code = 0
        self.num_turns = 9
        self.tool_use_count = 21
        self.mcp_tool_use_count = 21
        self.tokens_in, self.tokens_out = 12000, 3000
        self.duration_s = 1740.0
        self.transcript = transcript
        self.summary = "done"
        self.tool_names = ["grep"]
        self.cost_usd = 0.42
        self.models_used = ["claude-sonnet-5"]

    def to_json(self):
        return json.dumps({"duration_s": self.duration_s})


class TestPreGradeLeakAbort(unittest.TestCase):

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="cb-pregrade-"))
        self.project = self.root / "substrate"
        (self.project / "Source/CraftBenchTemplate").mkdir(parents=True)
        (self.project / "Source/CraftBenchTemplate/A.cpp").write_bytes(b"orig")
        (self.project / "AGENT_WRITABLE.json").write_text(
            json.dumps({"writable": ["Source/CraftBenchTemplate/"]}),
            encoding="utf-8")
        self.run_dir = self.root / "run"
        self.run_dir.mkdir()
        self.verifier_calls = []
        self.released = []
        self.restores = []

    def _args(self):
        return SimpleNamespace(
            substrate_root=self.project, model="aura-mcp:claude-sonnet-5",
            task=LEAK_TASK,
            max_turns=200, timeout=3600, ue_root="Q:/UE_5.8",
            visible=False, capture=False, preamble_sha=None)

    def _run(self, transcript, edits=True):
        agent = _AgentResult(transcript)

        def _adapter_run(**kw):
            if edits:
                (self.project / "Source/CraftBenchTemplate/A.cpp").write_bytes(
                    b"agent-edit")
            return agent

        def _verifier(argv, *a, **kw):
            # The same seam carries the provenance `git` calls; only the grade
            # is being counted here.
            if str(run_mod.VERIFIER) in argv:
                self.verifier_calls.append(argv)
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        hygiene = SimpleNamespace(stuck=[], as_dict=lambda: {"stuck": []})
        patches = [
            mock.patch.object(run_mod, "acquire_live_run_lock",
                              lambda _p: lambda: self.released.append(True)),
            mock.patch.object(run_mod, "quarantine_untracked_writable",
                              lambda *a, **kw: hygiene),
            mock.patch.object(run_mod, "ensure_aura_client_port",
                              lambda *a, **kw: None),
            mock.patch.object(run_mod, "make_adapter",
                              lambda *a, **kw: SimpleNamespace(
                                  name="stub", run=_adapter_run)),
            mock.patch.object(run_mod, "stage_fairness_hide",
                              lambda *a, **kw: SimpleNamespace(
                                  stubbed_rels=[], isolated_rels=[],
                                  isolated_dirs=[], applied_config=[],
                                  repo_hidden=[], index_hidden=[])),
            mock.patch.object(run_mod, "stage_task_isolation_hide",
                              lambda *a, **kw: None),
            mock.patch.object(run_mod, "stage_task_tree_isolation_hide",
                              lambda *a, **kw: None),
            mock.patch.object(run_mod, "stage_config_overlay_apply",
                              lambda *a, **kw: None),
            mock.patch.object(run_mod, "stage_repo_answer_hide",
                              lambda *a, **kw: None),
            mock.patch.object(run_mod, "stage_index_cache_hide",
                              lambda *a, **kw: None),
            mock.patch.object(run_mod, "stage_generated_code_hide",
                              lambda *a, **kw: None),
            mock.patch.object(run_mod, "stage_fairness_restore",
                              lambda *a, **kw: self.restores.append(True)),
            mock.patch.object(run_mod, "subprocess",
                              SimpleNamespace(run=_verifier)),
            mock.patch.object(run_mod, "verdict_from_verifier",
                              lambda rc, out: "PASS"),
            mock.patch.object(run_mod, "_load_verifier_report",
                              lambda *a, **kw: {"overall": "PASS"}),
            mock.patch.object(run_mod, "_collect_artifacts",
                              lambda *a, **kw: []),
            mock.patch.object(run_mod, "_apply_retention",
                              lambda *a, **kw: None),
            mock.patch.object(run_mod, "_verifier_workdir_args",
                              lambda *a, **kw: []),
            mock.patch.object(run_mod, "_verifier_workdir",
                              lambda *a, **kw: None),
        ]
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(buf):
            for p in patches:
                p.start()
            try:
                rc = run_mod._run_live_project(
                    self._args(), "run-id", self.run_dir, "PROMPT")
            finally:
                for p in reversed(patches):
                    p.stop()
        return rc, buf.getvalue()

    def _record(self):
        return json.loads(
            (self.run_dir / "result.json").read_text(encoding="utf-8"))

    # ---- the leaked cell -------------------------------------------------

    def test_a_leaked_cell_never_reaches_the_verifier(self):
        rc, text = self._run(LEAKED)
        self.assertEqual(self.verifier_calls, [],
                         "a cell no denominator can use must not pay for a "
                         "build and an editor session")
        self.assertEqual(rc, 2)
        self.assertIn("read verifier source", text)

    def test_the_verdict_is_fairness_breach_and_not_graded(self):
        self._run(LEAKED)
        rec = self._record()
        self.assertEqual(rec["overall"], "FAIRNESS-BREACH")
        self.assertFalse(is_graded_verdict(rec["overall"]))
        self.assertIsNone(rec["verifier"])

    def test_the_void_is_stamped_with_the_reason(self):
        self._run(LEAKED)
        rec = self._record()
        from leak_audit import read_void
        void = read_void(rec)
        self.assertIsNotNone(void)
        self.assertIn("leak_audit", void["reason"])
        # A pre-grade void has no graded verdict to name.
        self.assertIsNone(void["verdict_before"])

    def test_cleanup_still_runs_on_the_abort(self):
        self._run(LEAKED)
        self.assertTrue(self.restores, "fairness restore was skipped")
        self.assertEqual(self.released, [True], "live-run lock was not released")
        self.assertEqual(
            (self.project / "Source/CraftBenchTemplate/A.cpp").read_bytes(),
            b"orig", "the live writable area was left at the agent's bytes")
        self.assertTrue((self.run_dir / "live_restore.json").is_file())

    def test_the_deliverable_survives_as_evidence(self):
        # The finally reverts the live tree, so submission/ is the only copy of
        # what the drive produced — and a breach is exactly the run someone
        # wants to read.
        self._run(LEAKED)
        kept = self.run_dir / "submission/Source/CraftBenchTemplate/A.cpp"
        self.assertTrue(kept.is_file())
        self.assertEqual(kept.read_bytes(), b"agent-edit")

    def test_a_leaked_cell_that_edited_nothing_is_still_not_graded(self):
        # FAIL_NO_EDITS is a MODEL_OUTCOME verdict, so an empty submission from
        # a contaminated drive would otherwise bank in the denominator.
        rc, _ = self._run(LEAKED, edits=False)
        self.assertEqual(rc, 2)
        rec = self._record()
        self.assertEqual(rec["overall"], "FAIRNESS-BREACH")
        self.assertFalse(is_graded_verdict(rec["overall"]))
        self.assertIsNotNone(leak_audit.read_void(rec))

    # ---- what must NOT abort --------------------------------------------

    def test_exposure_alone_is_still_graded(self):
        # leak_audit warns on a park path in a tool result rather than voiding:
        # every instance measured so far was a directory listing. Voiding here
        # would hand any drive a denominator opt-out for one `ls`.
        rc, text = self._run(EXPOSED)
        self.assertEqual(len(self.verifier_calls), 1)
        self.assertEqual(rc, 0)
        self.assertEqual(self._record()["overall"], "PASS")
        self.assertIn("EXPOSED", text)

    def test_a_clean_cell_is_untouched(self):
        rc, _ = self._run(CLEAN)
        self.assertEqual(len(self.verifier_calls), 1)
        self.assertEqual(rc, 0)
        self.assertEqual(self._record()["overall"], "PASS")


class TestPreGradeLeakAbortWorkspaceLane(unittest.TestCase):
    """The same gate on the other arm — `main()`'s materialized-copy lane.

    Kept separate from the live-lane class because only this arm can strand a
    substrate copy: its abort has to repeat step 7's teardown by hand.
    """

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="cb-pregrade-ws-"))
        self.ws = self.root / "workspace"
        (self.ws / "project").mkdir(parents=True)
        (self.ws / "prompt.md").write_text("PROMPT", encoding="utf-8")
        self.run_dir = self.root / "run"
        self.verifier_calls = []

    def _run(self, transcript, staged):
        agent = _AgentResult(transcript)
        workspace = SimpleNamespace(root=self.ws, project_dir=self.ws / "project",
                                    prompt_path=self.ws / "prompt.md")
        args = SimpleNamespace(
            # The DISCOVERED task, so this lane and LEAKED cannot drift apart.
            task=run_mod.REPO_ROOT / LEAK_TASK,
            model="claude-p:claude-sonnet-5", run_dir=self.root / "runs",
            substrate_root=self.root / "substrate", allow_dirty_substrate=True,
            live_project=False, workspace=None, skip_plugins=False,
            prepare_only=False, no_preflight=True, keep_workspace=False,
            max_turns=200, timeout=3600, ue_root="Q:/UE_5.8",
            visible=False, capture=False, preamble_sha=None)

        def _verifier(argv, *a, **kw):
            if str(run_mod.VERIFIER) in argv:
                self.verifier_calls.append(argv)
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        patches = [
            mock.patch.object(run_mod, "parse_args", lambda: args),
            mock.patch.object(run_mod, "extract_agent_visible_prompt",
                              lambda *a, **kw: "PROMPT"),
            mock.patch.object(run_mod, "build_workspace",
                              lambda **kw: workspace),
            mock.patch.object(run_mod, "_write_manifest", lambda *a, **kw: None),
            mock.patch.object(run_mod, "make_adapter",
                              lambda *a, **kw: SimpleNamespace(
                                  name="stub", run=lambda **kw: agent)),
            mock.patch.object(run_mod, "snapshot_submission",
                              lambda *a, **kw: staged),
            mock.patch.object(run_mod, "subprocess",
                              SimpleNamespace(run=_verifier)),
            mock.patch.object(run_mod, "verdict_from_verifier",
                              lambda rc, out: "PASS"),
            mock.patch.object(run_mod, "_load_verifier_report",
                              lambda *a, **kw: {"overall": "PASS"}),
            mock.patch.object(run_mod, "_collect_artifacts", lambda *a, **kw: []),
            mock.patch.object(run_mod, "_apply_retention", lambda *a, **kw: None),
            mock.patch.object(run_mod, "_verifier_workdir_args",
                              lambda *a, **kw: []),
            mock.patch.object(run_mod, "_verifier_workdir", lambda *a, **kw: None),
        ]
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(buf):
            for p in patches:
                p.start()
            try:
                rc = run_mod.main()
            finally:
                for p in reversed(patches):
                    p.stop()
        run_dir = next((args.run_dir).iterdir())
        return rc, json.loads((run_dir / "result.json").read_text(encoding="utf-8"))

    def test_a_leaked_cell_that_edited_nothing_is_still_not_graded(self):
        rc, rec = self._run(LEAKED, staged=[])
        self.assertEqual(rc, 2)
        self.assertEqual(rec["overall"], "FAIRNESS-BREACH")
        self.assertFalse(is_graded_verdict(rec["overall"]))
        self.assertEqual(self.verifier_calls, [])

    def test_the_abort_does_not_strand_the_substrate_copy(self):
        self._run(LEAKED, staged=["Source/CraftBenchTemplate/A.cpp"])
        self.assertFalse(self.ws.exists())

    def test_a_clean_cell_is_untouched(self):
        rc, rec = self._run(CLEAN, staged=["Source/CraftBenchTemplate/A.cpp"])
        self.assertEqual(rc, 0)
        self.assertEqual(rec["overall"], "PASS")
        self.assertEqual(len(self.verifier_calls), 1)


class TestDetectorFailsOpen(unittest.TestCase):
    """A detector that cannot answer is not evidence of a breach.

    It gates a grade, so a broken audit must cost a run nothing: the post-hoc
    sweep still reads the finished bundle.
    """

    def test_a_raising_audit_does_not_gate(self):
        buf = io.StringIO()
        with mock.patch.object(run_mod.leak_audit, "audit",
                               side_effect=OSError("transcript vanished")):
            self.assertIsNone(run_mod._answer_key_leak(
                Path("."), log=buf.write))
        self.assertIn("leak audit skipped", buf.getvalue())

    def test_a_missing_transcript_does_not_gate(self):
        root = Path(tempfile.mkdtemp(prefix="cb-pregrade-empty-"))
        self.assertIsNone(run_mod._answer_key_leak(root, log=lambda _m: None))


if __name__ == "__main__":
    unittest.main()

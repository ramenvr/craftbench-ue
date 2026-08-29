"""Unit tests for aura_rig.benchwizard — the `cb bench` interactive wizard.

Pure-offline: a throwaway tasks/ tree + an injected input/out (the
test_taskpicker _Script pattern), so the tasks -> models -> params -> confirm
flow is exercised without a terminal. TestCmdBenchWizardRouting covers the
cmd_bench seam (TTY gate, sentinels, --wizard/--resume interplay) with the
wizard stubbed.
"""

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aura_rig import benchwizard as bw          # noqa: E402
from aura_rig import model_keys                 # noqa: E402
from aura_rig.bench import parse_task_spec      # noqa: E402
from aura_rig.matrix import parse_models        # noqa: E402

_MD = "# {id}\n\n## Primary concept\n{c}\n\n## Prompt given to the agent\n{p}\n\n## Verifier layers used\n{l}\n"


def _write(path: Path, id, c="concept", p="prompt", l="L1, L2"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_MD.format(id=id, c=c, p=p, l=l), encoding="utf-8")


def _mk_repo(root: Path) -> Path:
    t = root / "tasks"
    _write(t / "alpha.md", "alpha")          # root set, list index 1
    _write(t / "wave" / "beta.md", "beta")   # index 2
    _write(t / "wave" / "gamma.md", "gamma")  # index 3
    return root


class _Script:
    """Feeds a fixed answer list to input_fn and captures everything printed."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.out = []

    def inp(self, _prompt):
        return self.answers.pop(0)

    def write(self, s):
        self.out.append(s)


_KEYS = sorted(model_keys.KEY_TO_WIRE)


def _key_no(key: str) -> str:
    """1-based menu index of an Aura key in the wizard's sorted list."""
    return str(_KEYS.index(key) + 1)


class TestWizardFlow(unittest.TestCase):
    def _run(self, repo, answers, **kw):
        s = _Script(answers)
        res = bw.run_wizard(repo, input_fn=s.inp, out=s.write, **kw)
        return res, "\n".join(s.out)

    def test_happy_path_two_tasks_two_aura_models(self):
        with tempfile.TemporaryDirectory() as td:
            res, out = self._run(_mk_repo(Path(td)), [
                "2 3", "",                                   # tasks: beta+gamma, done
                "1",                                         # backend: aura-product
                f"{_key_no('opus-4.8')} {_key_no('sonnet-5')}", "",  # two keys, done
                "",                                          # add another backend? No
                "", "",                                      # repeat (default 1), ceiling (900)
                "y",                                         # run it
            ])
        self.assertIsNotNone(res)
        self.assertEqual(res.task, "beta,gamma")
        self.assertEqual(res.model, "opus-4.8,sonnet-5")     # sorted-key row order
        self.assertEqual((res.repeat, res.ceiling), (1, 900))
        self.assertIn("cb bench --model opus-4.8,sonnet-5 --task beta,gamma "
                      "--repeat 1 --ceiling 900", out)
        self.assertIn("= 4 cell(s)", out)                    # 2 models x 2 tasks x 1 rep

    def test_toggle_untoggle(self):
        with tempfile.TemporaryDirectory() as td:
            res, _ = self._run(_mk_repo(Path(td)),
                               ["1", "1", "2", "", "", "", "y"],
                               preset_model="claude-p:opus")
        self.assertEqual(res.task, "beta")                   # 1 on, 1 off, 2 on

    def test_range_toggle(self):
        with tempfile.TemporaryDirectory() as td:
            res, _ = self._run(_mk_repo(Path(td)), ["2-3", "", "", "", "y"],
                               preset_model="claude-p:opus")
        self.assertEqual(res.task, "beta,gamma")

    def test_select_all(self):
        with tempfile.TemporaryDirectory() as td:
            res, _ = self._run(_mk_repo(Path(td)), ["a", "", "", "", "y"],
                               preset_model="claude-p:opus")
        self.assertEqual(res.task, "alpha,beta,gamma")

    def test_done_with_none_reprompts(self):
        with tempfile.TemporaryDirectory() as td:
            res, out = self._run(_mk_repo(Path(td)), ["", "1", "", "", "", "y"],
                                 preset_model="claude-p:opus")
        self.assertEqual(res.task, "alpha")
        self.assertIn("select at least one", out)

    def test_invalid_token_reprompts(self):
        with tempfile.TemporaryDirectory() as td:
            res, out = self._run(_mk_repo(Path(td)), ["x 99", "1", "", "", "", "y"],
                                 preset_model="claude-p:opus")
        self.assertEqual(res.task, "alpha")
        self.assertIn("numbers toggle", out)

    def test_quit_at_tasks(self):
        with tempfile.TemporaryDirectory() as td:
            res, _ = self._run(_mk_repo(Path(td)), ["q"])
        self.assertIsNone(res)

    def test_quit_at_backend(self):
        with tempfile.TemporaryDirectory() as td:
            res, _ = self._run(_mk_repo(Path(td)), ["1", "", "q"])
        self.assertIsNone(res)

    def test_quit_at_model_list(self):
        with tempfile.TemporaryDirectory() as td:
            res, _ = self._run(_mk_repo(Path(td)), ["1", "", "1", "q"])
        self.assertIsNone(res)

    def test_quit_at_params(self):
        with tempfile.TemporaryDirectory() as td:
            res, _ = self._run(_mk_repo(Path(td)), ["1", "", "q"],
                               preset_model="claude-p:opus")
        self.assertIsNone(res)

    def test_decline_at_confirm(self):
        with tempfile.TemporaryDirectory() as td:
            res, out = self._run(_mk_repo(Path(td)), ["1", "", "", "", "n"],
                                 preset_model="claude-p:opus")
        self.assertIsNone(res)
        self.assertIn("declined", out)
        self.assertIn("cb bench --model claude-p:opus", out)  # escape hatch printed

    def test_mixed_backend_accumulation(self):
        with tempfile.TemporaryDirectory() as td:
            res, out = self._run(_mk_repo(Path(td)), [
                "1", "",                                   # task alpha
                "1", _key_no("opus-4.8"), "",              # aura: opus-4.8
                "y",                                       # add another backend
                "2", "1", "", "",                          # claude-p: alias opus, done, no free entry
                "",                                        # no third backend
                "", "",                                    # params defaults
                "y",
            ])
        self.assertEqual(res.model, "opus-4.8,claude-p:opus")
        self.assertIn("slug: claude-p:opus", out)          # slug-grammar teaching line
        self.assertIn("models so far: opus-4.8, claude-p:opus", out)

    def test_repeat_default_multi_model_is_1(self):
        with tempfile.TemporaryDirectory() as td:
            res, _ = self._run(_mk_repo(Path(td)), ["1", "", "", "", "y"],
                               preset_model="opus-4.8,claude-p:opus")
        self.assertEqual(res.repeat, 1)

    def test_repeat_default_single_model_is_3(self):
        with tempfile.TemporaryDirectory() as td:
            res, _ = self._run(_mk_repo(Path(td)), ["1", "", "", "", "y"],
                               preset_model="claude-p:opus")
        self.assertEqual(res.repeat, 3)

    def test_params_reject_junk(self):
        with tempfile.TemporaryDirectory() as td:
            res, out = self._run(_mk_repo(Path(td)),
                                 ["0", "-2", "abc", "5", "", "y"],
                                 preset_model="claude-p:opus", preset_task="t0")
        self.assertEqual(res.repeat, 5)
        self.assertIn("positive integer", out)

    def test_openrouter_free_entry_composes_slug_and_requires_slash(self):
        with tempfile.TemporaryDirectory() as td:
            res, out = self._run(_mk_repo(Path(td)), [
                "1", "",                     # task
                "3", "",                     # backend openrouter, no checkbox picks
                "gpt-5",                     # rejected: no '/'
                "openai/gpt-5",              # accepted
                "",                          # no more backends
                "", "", "y",
            ])
        self.assertEqual(res.model, "openrouter:openai/gpt-5")
        self.assertIn("<provider>/<model>", out)
        self.assertEqual(parse_models(res.model), ["openrouter:openai/gpt-5"])

    def test_claude_p_free_entry(self):
        with tempfile.TemporaryDirectory() as td:
            res, _ = self._run(_mk_repo(Path(td)), [
                "1", "",
                "2", "", "claude-sonnet-4-6",   # no checkbox picks, free entry
                "",
                "", "", "y",
            ])
        self.assertEqual(res.model, "claude-p:claude-sonnet-4-6")

    def test_preset_task_skips_task_stage(self):
        with tempfile.TemporaryDirectory() as td:
            res, out = self._run(_mk_repo(Path(td)),
                                 ["1", _key_no("sonnet-5"), "", "", "", "", "y"],
                                 preset_task="t0")
        self.assertEqual(res.task, "t0")
        self.assertIn("using --task t0 (given)", out)

    def test_result_round_trips_through_parsers(self):
        with tempfile.TemporaryDirectory() as td:
            res, _ = self._run(_mk_repo(Path(td)), [
                "2 3", "", "1",
                f"{_key_no('opus-4.8')} {_key_no('sonnet-5')}", "",
                "", "", "", "y",
            ])
        self.assertEqual(parse_models(res.model), ["opus-4.8", "sonnet-5"])
        self.assertEqual(parse_task_spec(res.task, res.repeat),
                         [("beta", 1), ("gamma", 1)])

    def test_claude_p_choices_derive_from_key_to_wire(self):
        choices = bw._claude_p_choices()
        for wire in model_keys.KEY_TO_WIRE.values():
            if wire.startswith("claude-"):
                self.assertIn(wire, choices)

    def test_no_tasks_returns_none(self):
        with tempfile.TemporaryDirectory() as td:
            res, out = self._run(Path(td), [])
        self.assertIsNone(res)
        self.assertIn("no tasks", out)


class TestCmdBenchWizardRouting(unittest.TestCase):
    """The cmd_bench seam: TTY gate, sentinels, --wizard/--resume interplay.
    The wizard itself is stubbed; ctx.py_exe=None makes cmd_bench exit 1 at the
    harness-Python gate right AFTER the wizard seam, so no UE/stack is touched."""

    def setUp(self):
        import aura_rig.cb as _cb
        self._cb = _cb
        self._orig_tty = _cb._stdio_is_tty
        self._orig_wizard = bw.run_wizard

    def tearDown(self):
        self._cb._stdio_is_tty = self._orig_tty
        bw.run_wizard = self._orig_wizard

    def _ctx(self, td):
        return types.SimpleNamespace(
            paths=types.SimpleNamespace(craftbench=Path(td)),
            py_exe=None, ue=None)

    def _args(self, **kw):
        base = dict(model=self._cb._DEFAULT_MODEL, task=self._cb._DEFAULT_TASK,
                    repeat=3, ceiling=900, resume=None, no_preflight=True)
        base.update(kw)
        return types.SimpleNamespace(**base)

    def _stub_forbidden(self):
        def _boom(*a, **k):
            raise AssertionError("wizard must not run in this scenario")
        bw.run_wizard = _boom

    def test_bare_non_tty_no_wizard(self):
        self._cb._stdio_is_tty = lambda: False
        self._stub_forbidden()
        with tempfile.TemporaryDirectory() as td:
            args = self._args()
            rc = self._cb.cmd_bench(self._ctx(td), args)
        self.assertEqual(rc, 1)                       # the py_exe gate, not the wizard
        self.assertEqual(args.model, self._cb._DEFAULT_MODEL)

    def test_bare_tty_uses_wizard_result(self):
        self._cb._stdio_is_tty = lambda: True
        bw.run_wizard = lambda repo, **kw: bw.WizardResult(
            model="claude-p:opus", task="t0", repeat=1, ceiling=600)
        with tempfile.TemporaryDirectory() as td:
            args = self._args()
            rc = self._cb.cmd_bench(self._ctx(td), args)
        self.assertEqual(rc, 1)                       # continues into the classic flow
        self.assertEqual((args.model, args.task, args.repeat, args.ceiling),
                         ("claude-p:opus", "t0", 1, 600))

    def test_explicit_model_skips_wizard(self):
        self._cb._stdio_is_tty = lambda: True
        self._stub_forbidden()
        with tempfile.TemporaryDirectory() as td:
            rc = self._cb.cmd_bench(self._ctx(td), self._args(model="claude-p:opus"))
        self.assertEqual(rc, 1)

    def test_explicit_task_skips_wizard(self):
        self._cb._stdio_is_tty = lambda: True
        self._stub_forbidden()
        with tempfile.TemporaryDirectory() as td:
            rc = self._cb.cmd_bench(self._ctx(td), self._args(task="t0"))
        self.assertEqual(rc, 1)

    def test_wizard_flag_forces_and_prefills(self):
        self._cb._stdio_is_tty = lambda: True
        seen = {}

        def _stub(repo, **kw):
            seen.update(kw)
            return bw.WizardResult(model="claude-p:opus", task="t0",
                                   repeat=1, ceiling=900)
        bw.run_wizard = _stub
        with tempfile.TemporaryDirectory() as td:
            rc = self._cb.cmd_bench(self._ctx(td),
                                    self._args(wizard=True, model="claude-p:opus"))
        self.assertEqual(rc, 1)
        self.assertEqual(seen.get("preset_model"), "claude-p:opus")
        self.assertIsNone(seen.get("preset_task"))

    def test_wizard_none_aborts_rc0(self):
        self._cb._stdio_is_tty = lambda: True
        bw.run_wizard = lambda repo, **kw: None
        with tempfile.TemporaryDirectory() as td:
            rc = self._cb.cmd_bench(self._ctx(td), self._args())
        self.assertEqual(rc, 0)

    def test_wizard_flag_non_tty_fails_rc2(self):
        self._cb._stdio_is_tty = lambda: False
        self._stub_forbidden()
        with tempfile.TemporaryDirectory() as td:
            rc = self._cb.cmd_bench(self._ctx(td), self._args(wizard=True))
        self.assertEqual(rc, 2)

    def test_wizard_plus_resume_fails_rc2(self):
        self._cb._stdio_is_tty = lambda: True
        self._stub_forbidden()
        with tempfile.TemporaryDirectory() as td:
            rc = self._cb.cmd_bench(self._ctx(td),
                                    self._args(wizard=True, resume="__latest__"))
        self.assertEqual(rc, 2)

    def test_resume_never_wizards(self):
        # --resume suppresses the wizard, so an UNREADABLE resume dir must REFUSE
        # (rc 2) rather than fall through to the flag defaults. Those defaults are
        # opus-4.8 x t0 x 3, and with the wizard suppressed nothing else would ask
        # — that combination silently spent ~3x on a resume (2026-07-25). rc was 1
        # (the later py_exe gate) before the plan restore landed.
        self._cb._stdio_is_tty = lambda: True
        self._stub_forbidden()
        with tempfile.TemporaryDirectory() as td:
            args = self._args(resume="nope")
            rc = self._cb.cmd_bench(self._ctx(td), args)
        self.assertEqual(rc, 2)
        self.assertEqual(args.model, self._cb._DEFAULT_MODEL)  # never re-planned

    def test_resume_with_explicit_plan_is_allowed_through(self):
        # Restating the plan is the documented workaround for an UNREADABLE
        # PLAN (corrupt bench.json), so it must NOT refuse: it proceeds to the
        # classic flow and stops at the py_exe gate (rc 1). The target itself
        # must still QUALIFY (a dir with a readable bench.json) — a MISSING
        # bench.json refuses regardless, there is nothing to resume there.
        self._cb._stdio_is_tty = lambda: True
        self._stub_forbidden()
        with tempfile.TemporaryDirectory() as td:
            bench_dir = Path(td) / "bench-20260805-000000"
            bench_dir.mkdir()
            (bench_dir / "bench.json").write_text("{not json", encoding="utf-8")
            rc = self._cb.cmd_bench(
                self._ctx(td),
                self._args(resume=str(bench_dir), model="claude-p:opus", task="t0"))
        self.assertEqual(rc, 1)

    def test_resume_restores_the_plan_from_bench_json(self):
        self._cb._stdio_is_tty = lambda: True
        self._stub_forbidden()
        with tempfile.TemporaryDirectory() as td:
            bench_dir = Path(td) / "bench-20260725-000000"
            bench_dir.mkdir()
            (bench_dir / "bench.json").write_text(json.dumps({
                "models": ["claude-p:sonnet-5"],
                "task_specs": [{"task_id": "flagship/t0", "reps": 12}],
                "reps": [],
            }), encoding="utf-8")
            args = self._args(resume=str(bench_dir))
            rc = self._cb.cmd_bench(self._ctx(td), args)
        self.assertEqual(rc, 1)                       # the py_exe gate, not a refusal
        # (a bare Aura key would now be REFUSED with 2 before that gate)
        self.assertEqual(args.model, "claude-p:sonnet-5")      # NOT the opus-4.8 default
        self.assertEqual(args.task, "flagship/t0:12")


if __name__ == "__main__":
    unittest.main()

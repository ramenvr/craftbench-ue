"""Unit tests for aura_rig.taskpicker — the scripted numbered-menu flow.

Pure-offline: a throwaway tasks/ tree + an injected input/out, so the whole
sets -> tasks -> detail -> confirm loop is exercised without a terminal.
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aura_rig import taskpicker  # noqa: E402

_MD = "# {id}\n\n## Primary concept\n{c}\n\n## Prompt given to the agent\n{p}\n\n## Verifier layers used\n{l}\n"


def _write(path: Path, id, c="concept", p="prompt", l="L1, L2"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_MD.format(id=id, c=c, p=p, l=l), encoding="utf-8")


def _mk_repo(root: Path) -> Path:
    t = root / "tasks"
    _write(t / "alpha.md", "alpha")
    _write(t / "concept-1" / "beta.md", "beta")
    _write(t / "internal-1" / "gamma.md", "gamma")
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


class TestPicker(unittest.TestCase):
    def _run(self, repo, answers):
        s = _Script(answers)
        chosen = taskpicker.pick(repo, input_fn=s.inp, out=s.write)
        return chosen, "\n".join(s.out)

    def test_select_set_task_and_confirm(self):
        with tempfile.TemporaryDirectory() as td:
            # sets: root(1) concept-1(2) internal-1(3); pick concept-1, task beta, confirm
            chosen, out = self._run(_mk_repo(Path(td)), ["2", "1", "y"])
            self.assertEqual(chosen, "beta")
            self.assertIn("concept-1", out)
            self.assertIn("cb eval --task beta", out)

    def test_quit_at_sets(self):
        with tempfile.TemporaryDirectory() as td:
            chosen, _ = self._run(_mk_repo(Path(td)), ["q"])
            self.assertIsNone(chosen)

    def test_back_from_tasks_then_quit(self):
        with tempfile.TemporaryDirectory() as td:
            chosen, _ = self._run(_mk_repo(Path(td)), ["1", "b", "q"])
            self.assertIsNone(chosen)

    def test_decline_run_relists_then_quit(self):
        with tempfile.TemporaryDirectory() as td:
            # concept-1, beta, decline (n) -> back to task list, back (b), quit (q)
            chosen, _ = self._run(_mk_repo(Path(td)), ["2", "1", "n", "b", "q"])
            self.assertIsNone(chosen)

    def test_bad_input_reprompts_then_selects(self):
        with tempfile.TemporaryDirectory() as td:
            # junk + out-of-range at the set menu, then valid; then task + confirm
            chosen, out = self._run(_mk_repo(Path(td)), ["x", "9", "1", "1", "y"])
            self.assertEqual(chosen, "alpha")
            self.assertIn("?", out)  # reprompt hint shown

    def test_no_tasks_returns_none(self):
        with tempfile.TemporaryDirectory() as td:
            chosen, out = self._run(Path(td), [])
            self.assertIsNone(chosen)
            self.assertIn("no tasks", out)


if __name__ == "__main__":
    unittest.main()

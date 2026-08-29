"""Drift guards for aura_rig.cli_help — the ONE registry behind the grouped
overview, per-command help, and tab completion.

Run from tools/run-agent:  py -3.12 -m unittest tests.test_cli_help -v
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aura_rig import cli_help  # noqa: E402
from aura_rig import cb as _cb  # noqa: E402


class TestRegistryDrift(unittest.TestCase):
    def test_every_dispatch_command_has_help(self):
        # __complete is machine-facing and deliberately undocumented.
        hidden = {"__complete"}
        missing = set(_cb._DISPATCH) - hidden - set(cli_help.COMMANDS)
        self.assertFalse(missing, f"dispatch commands without a help entry: {missing}")

    def test_every_help_entry_is_dispatchable(self):
        ghosts = set(cli_help.COMMANDS) - set(_cb._DISPATCH)
        self.assertFalse(ghosts, f"help entries for non-commands: {ghosts}")

    def test_every_registry_flag_exists_on_the_parser(self):
        parser_flags = {opt for a in _cb.build_parser()._actions
                        for opt in a.option_strings}
        for c in cli_help.COMMANDS.values():
            for flag, _desc in c.flags:
                self.assertIn(flag, parser_flags,
                              f"cb help {c.name} names {flag!r} which the parser lacks")

    def test_every_command_has_a_group(self):
        for c in cli_help.COMMANDS.values():
            self.assertIn(c.group, cli_help.GROUPS, c.name)


class TestPositionalRegistryDrift(unittest.TestCase):
    """`Cmd.positional` is the ONLY statement of which commands read the flat
    parser's two shared positionals. If it drifts from what the dispatch
    functions actually read, `cb <cmd> <word>` starts silently ignoring the
    word again (the 2026-07-25 `cb eval <task-id>` → graded-the-default bug)."""

    def _handler_source(self, command: str) -> str:
        import inspect
        return inspect.getsource(_cb._DISPATCH[command])

    def test_declared_arity_matches_what_the_handler_reads(self):
        for command in _cb._DISPATCH:
            src = self._handler_source(command)
            reads_1 = "args.outputs" in src
            reads_2 = "gen_outputs" in src
            declared = _cb._positional_metavars(command)
            self.assertEqual(
                reads_1, len(declared) >= 1,
                f"`cb {command}` {'reads' if reads_1 else 'ignores'} args.outputs but "
                f"declares {declared!r} — a stray word will be "
                f"{'rejected wrongly' if declared else 'silently swallowed'}")
            self.assertEqual(
                reads_2, len(declared) >= 2,
                f"`cb {command}` positional[2] drift: reads={reads_2} declared={declared!r}")

    def test_hidden_commands_are_exactly_the_undocumented_ones(self):
        # _HIDDEN_POSITIONAL exists only because these two have no registry
        # entry; if one gains documentation the arity must move to the registry.
        self.assertEqual(set(_cb._HIDDEN_POSITIONAL),
                         set(_cb._DISPATCH) - set(cli_help.COMMANDS))

    def test_metavars_are_nonempty_strings(self):
        for c in cli_help.COMMANDS.values():
            for mv in c.positional:
                self.assertTrue(mv.strip(), c.name)


class TestStrayPositionalGuard(unittest.TestCase):
    def _args(self, argv):
        return _cb.build_parser().parse_args(argv)

    def test_bare_task_id_after_eval_is_refused_with_the_task_flag_hint(self):
        err = _cb.reject_stray_positionals(self._args(["eval", "t1-physics-drop-and-rest"]))
        self.assertIsNotNone(err, "cb eval <task-id> must not be silently ignored")
        self.assertIn("t1-physics-drop-and-rest", err)
        self.assertIn("--task t1-physics-drop-and-rest", err)

    def test_refuses_on_discriminate_wip_and_lint_too(self):
        for command in ("discriminate", "wip", "lint"):
            err = _cb.reject_stray_positionals(self._args([command, "some-task"]))
            self.assertIsNotNone(err, command)
            self.assertIn(f"--task some-task", err)

    def test_consuming_commands_accept_their_positionals(self):
        # batch-gen went with the product lane and is no longer a command.
        for argv in (["batch-eval", "subs/"],
                     ["review", "runs/x"], ["completions", "bash"],
                     ["__complete", "flags", "eval"]):
            self.assertIsNone(_cb.reject_stray_positionals(self._args(argv)), argv)

    def test_extra_beyond_declared_arity_is_refused(self):
        err = _cb.reject_stray_positionals(self._args(["review", "runs/x", "stray"]))
        self.assertIsNotNone(err)
        self.assertIn("stray", err)

    def test_bare_command_is_fine(self):
        for command in ("eval", "smoke", "lint", "batch-eval"):
            self.assertIsNone(_cb.reject_stray_positionals(self._args([command])), command)

    def test_main_exits_2_without_touching_the_machine(self):
        # _Ctx (UE probe / stack resolution) must never run for a refused argv.
        import unittest.mock as mock
        with mock.patch.object(_cb, "_Ctx", side_effect=AssertionError("_Ctx ran")):
            self.assertEqual(_cb.main(["eval", "t1-physics-drop-and-rest"]), 2)


class TestRendering(unittest.TestCase):
    def test_overview_lists_every_group_and_command(self):
        text = cli_help.render_overview()
        for g in cli_help.GROUPS:
            self.assertIn(g, text)
        for name in cli_help.COMMANDS:
            self.assertIn(f"  {name}", text)
        self.assertIn("cb help <command>", text)

    def test_command_help_has_flags_and_example(self):
        text = cli_help.render_command("eval")
        self.assertIn("cb eval", text)
        self.assertIn("--task", text)
        self.assertIn("example:", text)

    def test_unknown_command_help_names_the_known_set(self):
        text = cli_help.render_command("no-such-cmd")
        self.assertIn("no help for", text)
        self.assertIn("eval", text)


class TestComplete(unittest.TestCase):
    def test_commands_mode(self):
        cands = cli_help.complete("commands", "", Path("."))
        self.assertIn("eval", cands)
        self.assertIn("help", cands)
        self.assertNotIn("__complete", cands)

    def test_flags_mode_scopes_to_command(self):
        cands = cli_help.complete("flags", "eval", Path("."))
        self.assertIn("--task", cands)
        self.assertIn("--help", cands)
        self.assertNotIn("--references", cands)      # batch-eval's flag, not eval's

    def test_task_ids_mode_scans_folder_layout(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "tasks" / "wave1" / "t1-x").mkdir(parents=True)
            (repo / "tasks" / "wave1" / "t1-x" / "task.md").write_text("x", encoding="utf-8")
            cands = cli_help.complete("task-ids", "", repo)
        self.assertEqual(cands, ["t1-x", "wave1/t1-x"])

    def test_models_mode_has_backends_and_aura_keys(self):
        cands = cli_help.complete("models", "", Path("."))
        self.assertIn("claude-p", cands)
        self.assertTrue(any(c.startswith("openrouter") for c in cands))

    def test_unknown_mode_is_empty_not_error(self):
        self.assertEqual(cli_help.complete("nope", "", Path(".")), [])


class TestMainRouting(unittest.TestCase):
    def test_help_command_scoped(self):
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = _cb.main(["help", "eval"])
        self.assertEqual(rc, 0)
        self.assertIn("cb eval", buf.getvalue())
        self.assertIn("--task", buf.getvalue())

    def test_command_dash_dash_help_scoped(self):
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = _cb.main(["smoke", "--help"])
        self.assertEqual(rc, 0)
        self.assertIn("cb smoke", buf.getvalue())
        self.assertIn("--agent", buf.getvalue())


if __name__ == "__main__":
    unittest.main()

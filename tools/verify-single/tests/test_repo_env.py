"""repo_env — the .env loader that closes the no-cb grade path's guardrail gap.

The documented direct invocation (``python3 tools/verify-single/run_task.py …``,
the repo conventions *Common commands*) read no ``.env``, so ``CRAFTBENCH_L1_MAX_PARALLEL``
never applied and L1 hit C3859/exit 6 on a 32 GB box while every cb-fronted run
of the SAME grade passed.
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import repo_env


def _repo_with_env(tc: unittest.TestCase, body: str) -> Path:
    td = tempfile.TemporaryDirectory()
    tc.addCleanup(td.cleanup)
    root = Path(td.name)
    (root / ".env").write_text(body, encoding="utf-8")
    return root


class TestDotenvValue(unittest.TestCase):
    def test_inline_comment_is_stripped(self):
        # The 2026-07-24 class: the cap was silently dropped by the comment.
        self.assertEqual(repo_env.dotenv_value("2 # tested up to 4"), "2")

    def test_hash_inside_quotes_is_kept(self):
        self.assertEqual(repo_env.dotenv_value('"pa#ss" # note'), "pa#ss")

    def test_plain_and_padded(self):
        self.assertEqual(repo_env.dotenv_value("  4  "), "4")

    def test_unterminated_quote_keeps_legacy_behavior(self):
        self.assertEqual(repo_env.dotenv_value('"oops'), "oops")


class TestParseDotenv(unittest.TestCase):
    def test_only_the_craftbench_namespace(self):
        found = repo_env.parse_dotenv(
            "AURA_PASSWORD=secret\n"
            "CRAFTBENCH_L1_MAX_PARALLEL=2\n"
            "OPENROUTER_API_KEY=sk-xyz\n"
        )
        self.assertEqual(found, {"CRAFTBENCH_L1_MAX_PARALLEL": "2"})

    def test_commented_out_defaults_stay_inactive(self):
        # .env.example ships exactly this shape; a commented default must not
        # become an active one.
        self.assertEqual(repo_env.parse_dotenv("#CRAFTBENCH_ALLOW_UBA=1\n"), {})

    def test_blank_value_is_not_an_assignment(self):
        self.assertEqual(repo_env.parse_dotenv("CRAFTBENCH_ALLOW_UBA=\n"), {})

    def test_last_assignment_wins(self):
        found = repo_env.parse_dotenv(
            "CRAFTBENCH_L1_MAX_PARALLEL=2\nCRAFTBENCH_L1_MAX_PARALLEL=4\n")
        self.assertEqual(found["CRAFTBENCH_L1_MAX_PARALLEL"], "4")


class TestLoadRepoEnv(unittest.TestCase):
    def test_applies_the_cap_the_c3859_incident_needed(self):
        root = _repo_with_env(self, "CRAFTBENCH_L1_MAX_PARALLEL=2 # 32 GB box\n")
        env = {}
        applied = repo_env.load_repo_env(root, env=env)
        self.assertEqual(env["CRAFTBENCH_L1_MAX_PARALLEL"], "2")
        self.assertEqual(applied, {"CRAFTBENCH_L1_MAX_PARALLEL": "2"})

    def test_explicit_env_wins(self):
        root = _repo_with_env(self, "CRAFTBENCH_L1_MAX_PARALLEL=2\n")
        env = {"CRAFTBENCH_L1_MAX_PARALLEL": "8"}
        applied = repo_env.load_repo_env(root, env=env)
        self.assertEqual(env["CRAFTBENCH_L1_MAX_PARALLEL"], "8")
        self.assertEqual(applied, {}, "an operator's one-off override must survive")

    def test_blank_existing_value_is_filled(self):
        root = _repo_with_env(self, "CRAFTBENCH_L1_MAX_PARALLEL=2\n")
        env = {"CRAFTBENCH_L1_MAX_PARALLEL": "   "}
        repo_env.load_repo_env(root, env=env)
        self.assertEqual(env["CRAFTBENCH_L1_MAX_PARALLEL"], "2")

    def test_missing_dotenv_is_a_noop(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.assertEqual(repo_env.load_repo_env(Path(td.name), env={}), {})

    def test_defaults_to_os_environ(self):
        root = _repo_with_env(self, "CRAFTBENCH_ALLOW_UBA=1\n")
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CRAFTBENCH_ALLOW_UBA", None)
            repo_env.load_repo_env(root)
            self.assertEqual(os.environ["CRAFTBENCH_ALLOW_UBA"], "1")

    def test_aura_creds_never_leak_into_the_verifier(self):
        root = _repo_with_env(self, 'AURA_PASSWORD="secret"\nCRAFTBENCH_ALLOW_UBA=1\n')
        env = {}
        repo_env.load_repo_env(root, env=env)
        self.assertNotIn("AURA_PASSWORD", env)


class TestEndToEndThroughL1(unittest.TestCase):
    """The loader is only useful if the layer that reads the var sees it."""

    def test_loaded_cap_reaches_the_ubt_flag(self):
        from layers import l1_build
        root = _repo_with_env(self, "CRAFTBENCH_L1_MAX_PARALLEL=2\n")
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CRAFTBENCH_L1_MAX_PARALLEL", None)
            self.assertEqual(l1_build._max_parallel_actions_args(), [],
                             "precondition: no cap before the load")
            repo_env.load_repo_env(root)
            self.assertEqual(l1_build._max_parallel_actions_args(),
                             ["-MaxParallelActions=2"])


class TestLockstepWithTheRigParser(unittest.TestCase):
    """``aura_rig.stack._dotenv_value`` is a second copy of these semantics (the
    rig cannot import this tree). If they diverge, `cb`-fronted and direct runs
    disagree about the same .env line — silently, and only on the tricky ones."""

    TRICKY = (
        "2 # tested up to 4",
        '"pa#ss" # note',
        "  4  ",
        '"oops',
        "",
        "plain",
        'quoted"mid',
        "trailing#nospace",
    )

    def test_both_parsers_agree(self):
        import sys
        rig = Path(__file__).resolve().parents[2] / "run-agent"   # tools/run-agent
        if not (rig / "aura_rig" / "stack.py").exists():   # verifier-only checkout
            self.skipTest("run-agent tree not present")
        sys.path.insert(0, str(rig))
        try:
            from aura_rig import stack
        except Exception as exc:                            # noqa: BLE001
            self.skipTest(f"aura_rig not importable here: {exc}")
        finally:
            sys.path.remove(str(rig))
        for raw in self.TRICKY:
            self.assertEqual(repo_env.dotenv_value(raw), stack._dotenv_value(raw),
                             f"dotenv parsers diverged on {raw!r}")


if __name__ == "__main__":
    unittest.main()

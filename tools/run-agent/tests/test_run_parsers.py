"""Unit tests for run.py helper parsers (no orchestration logic)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Import the parser helpers from run.py without executing main().
import importlib.util
RUN_PY = Path(__file__).resolve().parents[1] / "run.py"
spec = importlib.util.spec_from_file_location("run_module", RUN_PY)
run_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_module)


SAMPLE_VERIFIER_STDOUT_PASS = """\
sandbox: accepted 2 file(s), 0 violations
CraftBench verifier report
  task_id   : gp-spawn-sequence
  ue_version: 5.7.4
  duration  : 218.5s
  L1  : PASS    [exit=0, warn=0]
  L2  : PASS    [exit=0, tests=1/1]
  overall   : PASS
json report: /var/folders/k6/.../report.json
"""

SAMPLE_VERIFIER_STDOUT_FAIL = """\
sandbox: accepted 2 file(s), 0 violations
CraftBench verifier report
  L1  : PASS
  L2  : FAIL    [exit=1, tests=0/1]
  overall   : FAIL
json report: /var/folders/.../report.json
"""


class TestParseVerifierOverall(unittest.TestCase):
    def test_parses_pass(self):
        self.assertEqual(run_module._parse_verifier_overall(SAMPLE_VERIFIER_STDOUT_PASS), "PASS")

    def test_parses_fail(self):
        self.assertEqual(run_module._parse_verifier_overall(SAMPLE_VERIFIER_STDOUT_FAIL), "FAIL")

    def test_returns_harness_error_when_marker_missing(self):
        # UPDATED (verdict-taxonomy): this used to assert "FAIL". Defaulting to
        # FAIL invented a measurement — no report.json AND no rendered
        # ``overall`` line means the verifier never stated a verdict, so the run
        # must be non-graded (HARNESS-ERROR), not scored against the agent.
        self.assertEqual(
            run_module._parse_verifier_overall("nothing relevant here"),
            "HARNESS-ERROR",
        )


class TestParseVerifierReportMissing(unittest.TestCase):
    def test_returns_none_when_temp_path_gone(self):
        # The marker is present but the path no longer exists on disk.
        stdout = "json report: /tmp/does-not-exist-xyz/report.json\n"
        self.assertIsNone(run_module._parse_verifier_report(stdout))

    def test_returns_none_when_no_marker(self):
        self.assertIsNone(run_module._parse_verifier_report("no marker line"))


class TestLoadVerifierReport(unittest.TestCase):
    """The verifier:null fix — run.py passes --report-json <run_dir>/report.json
    and _load_verifier_report reads THAT file directly, with the legacy
    stdout-scrape as the only fallback."""

    def test_prefers_pinned_report_in_run_dir(self):
        import json
        import tempfile
        from pathlib import Path as P
        with tempfile.TemporaryDirectory() as td:
            run_dir = P(td)
            (run_dir / "report.json").write_text(
                json.dumps({"overall": "pass", "layers": {"L1": {"status": "pass"}}}),
                encoding="utf-8")
            # The stdout points at a DEAD workdir path — must not matter.
            report = run_module._load_verifier_report(
                run_dir, "json report: /tmp/gone-xyz/report.json\n")
            self.assertEqual(report["overall"], "pass")

    def test_falls_back_to_stdout_scrape(self):
        import json
        import tempfile
        from pathlib import Path as P
        with tempfile.TemporaryDirectory() as td:
            run_dir = P(td)  # NO pinned report.json here
            elsewhere = P(td) / "wd-out"
            elsewhere.mkdir()
            (elsewhere / "report.json").write_text(
                json.dumps({"overall": "fail"}), encoding="utf-8")
            report = run_module._load_verifier_report(
                run_dir, f"json report: {elsewhere / 'report.json'}\n")
            self.assertEqual(report["overall"], "fail")

    def test_none_when_nothing_available(self):
        import tempfile
        from pathlib import Path as P
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(
                run_module._load_verifier_report(P(td), "no marker"))


class TestSubstrateRootDerivation(unittest.TestCase):
    """--substrate-root default derives from the task spec's 'substrate:'
    front-matter field; an explicitly passed flag always wins."""

    _BASE = ["--task", "t.md", "--model", "claude-p:sonnet", "--ue-root", "/UE"]

    def _spec(self, td, substrate=None, task_id="tp-z"):
        from pathlib import Path as P
        lines = ["---", f"id: {task_id}"]
        if substrate:
            lines.append(f"substrate: {substrate}")
        lines += ["layers: [L1]", "---", "", "## Prompt given to the agent", "x", ""]
        p = P(td) / "task.md"
        p.write_text("\n".join(lines), encoding="utf-8")
        return p

    def test_derives_from_front_matter(self):
        import tempfile
        from pathlib import Path as P
        with tempfile.TemporaryDirectory() as td:
            spec = self._spec(td, "ThirdPersonTemplate")
            root = run_module.derive_substrate_root(spec, repo_root=P("/x"))
            self.assertEqual(root, P("/x") / "UE-projects" / "ThirdPersonTemplate")

    def test_legacy_alias_template_maps_to_default(self):
        import tempfile
        from pathlib import Path as P
        with tempfile.TemporaryDirectory() as td:
            spec = self._spec(td, "template")
            root = run_module.derive_substrate_root(spec, repo_root=P("/x"))
            self.assertEqual(root, P("/x") / "UE-projects" / "CraftBenchTemplate")

    def test_omitted_field_and_unreadable_spec_fall_back_to_default(self):
        import tempfile
        from pathlib import Path as P
        with tempfile.TemporaryDirectory() as td:
            spec = self._spec(td)  # no substrate key -> spec-level default
            self.assertEqual(
                run_module.derive_substrate_root(spec, repo_root=P("/x")),
                P("/x") / "UE-projects" / "CraftBenchTemplate")
            self.assertEqual(
                run_module.derive_substrate_root(P(td) / "missing.md",
                                                 repo_root=P("/x")),
                P("/x") / "UE-projects" / "CraftBenchTemplate")

    def test_parse_args_omitted_flag_derives_explicit_flag_wins(self):
        import tempfile
        from pathlib import Path as P
        with tempfile.TemporaryDirectory() as td:
            spec = self._spec(td, "ThirdPersonTemplate")
            base = ["--task", str(spec), "--model", "claude-p:sonnet",
                    "--ue-root", "/UE"]
            args = run_module.parse_args(base)
            self.assertEqual(
                args.substrate_root,
                run_module.REPO_ROOT / "UE-projects" / "ThirdPersonTemplate")
            args = run_module.parse_args(
                base + ["--substrate-root", "/elsewhere/MySub"])
            self.assertEqual(args.substrate_root, P("/elsewhere/MySub"))

    def test_parse_args_unparseable_task_keeps_default(self):
        args = run_module.parse_args(self._BASE)
        self.assertEqual(args.substrate_root, run_module.DEFAULT_SUBSTRATE)


class TestRunArgparseAdditions(unittest.TestCase):
    """--visible/--capture flags + the --keep alias of --keep-workspace."""

    _BASE = ["--task", "t.md", "--model", "claude-p:sonnet", "--ue-root", "/UE"]

    def test_defaults_off(self):
        args = run_module.parse_args(self._BASE)
        self.assertFalse(args.visible)
        self.assertFalse(args.capture)
        self.assertFalse(args.keep_workspace)

    def test_visible_capture_parse(self):
        args = run_module.parse_args(self._BASE + ["--visible", "--capture"])
        self.assertTrue(args.visible)
        self.assertTrue(args.capture)

    def test_keep_aliases_keep_workspace(self):
        args = run_module.parse_args(self._BASE + ["--keep"])
        self.assertTrue(args.keep_workspace)
        args = run_module.parse_args(self._BASE + ["--keep-workspace"])
        self.assertTrue(args.keep_workspace)

    def test_verifier_mode_args(self):
        args = run_module.parse_args(self._BASE + ["--visible", "--capture"])
        self.assertEqual(run_module._verifier_mode_args(args),
                         ["--visible", "--capture"])
        args = run_module.parse_args(self._BASE)
        self.assertEqual(run_module._verifier_mode_args(args), [])


class TestCollectArtifacts(unittest.TestCase):
    def test_copies_out_dir_artifacts_into_run_dir(self):
        import tempfile
        from pathlib import Path as P
        with tempfile.TemporaryDirectory() as td:
            base = P(td)
            out_dir = base / "verifier_out"
            (out_dir / "artifacts").mkdir(parents=True)
            (out_dir / "artifacts" / "a.png").write_bytes(b"png")
            run_dir = base / "run"
            run_dir.mkdir()
            rels = run_module._collect_artifacts(out_dir, run_dir)
            self.assertEqual(rels, ["artifacts/a.png"])
            self.assertTrue((run_dir / "artifacts" / "a.png").exists())

    def test_noop_when_out_dir_unknown_or_empty(self):
        import tempfile
        from pathlib import Path as P
        with tempfile.TemporaryDirectory() as td:
            run_dir = P(td)
            self.assertEqual(run_module._collect_artifacts(None, run_dir), [])
            self.assertEqual(
                run_module._collect_artifacts(P(td) / "nope", run_dir), [])


class TestDefaultRunRoot(unittest.TestCase):
    """Default runs land in a per-backend folder (runs/<backend>/), mirroring
    runs/aura-product/; the backend is the slug part before ':'."""

    def test_backend_folder_from_slug(self):
        root = run_module.DEFAULT_RUN_DIR
        self.assertEqual(run_module._default_run_root("claude-p:sonnet"),
                         root / "claude-p")
        self.assertEqual(
            run_module._default_run_root("openrouter:openai/gpt-4o-mini"),
            root / "openrouter")
        self.assertEqual(run_module._default_run_root("unreal-mcp"),
                         root / "unreal-mcp")
        self.assertEqual(
            run_module._default_run_root("aura-mcp:claude-sonnet-4-6"),
            root / "aura-mcp")

    def test_degenerate_slug_never_flattens(self):
        # Even a broken slug must not scatter runs at the runs/ root.
        self.assertEqual(run_module._default_run_root(":x"),
                         run_module.DEFAULT_RUN_DIR / "unknown")

    def test_separator_in_backend_token_flattened(self):
        # 'openai/gpt-4o' (forgot the openrouter: prefix) must stay ONE level
        # deep — a two-level runs/openai/gpt-4o/ would be invisible to the
        # one-container-level layout consumers.
        self.assertEqual(run_module._default_run_root("openai/gpt-4o"),
                         run_module.DEFAULT_RUN_DIR / "openai_gpt-4o")


if __name__ == "__main__":
    unittest.main()

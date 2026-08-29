"""Tests for the per-task deadline/action-budget parser and the
pinning-metadata collector (T020 + T021)."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_PARENT = _HERE.parent
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))

from pinning import (  # noqa: E402
    PinningResolutionError,
    collect_pinning,
    detect_engine_version,
    git_revision_for,
)
from run_task import (  # noqa: E402
    apply_randomization,
    parse_task_spec,
    resolve_randomization_tokens,
)


# ---------------------------------------------------------------------------
# T020 — deadline + action_budget parsing
# ---------------------------------------------------------------------------


def _write_minimal_task(path: Path, extra: str = "") -> None:
    path.write_text(
        "# t-test-deadline\n\n"
        "## Task ID and metadata\n\n"
        "- task_id: t-test-deadline\n"
        "- substrate: template\n\n"
        "## Verifier layers used\n\n"
        "L1\n\n"
        f"{extra}",
        encoding="utf-8",
    )


class DeadlineActionBudgetParser(unittest.TestCase):
    def test_defaults_applied_when_sections_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "task.md"
            _write_minimal_task(p)
            spec = parse_task_spec(p)
            self.assertEqual(spec.deadline_s, 600.0)
            self.assertEqual(spec.action_budget, 30)

    def test_deadline_section_overrides_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "task.md"
            _write_minimal_task(
                p,
                extra="## Deadline\n\n300 (this task is fast)\n",
            )
            spec = parse_task_spec(p)
            self.assertEqual(spec.deadline_s, 300.0)
            self.assertEqual(spec.action_budget, 30)  # default still applied

    def test_action_budget_section_overrides_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "task.md"
            _write_minimal_task(
                p,
                extra="## Action budget\n\n50\n",
            )
            spec = parse_task_spec(p)
            self.assertEqual(spec.action_budget, 50)
            self.assertEqual(spec.deadline_s, 600.0)

    def test_both_sections_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "task.md"
            _write_minimal_task(
                p,
                extra=(
                    "## Deadline\n\n1200\n\n"
                    "## Action budget\n\n100\n"
                ),
            )
            spec = parse_task_spec(p)
            self.assertEqual(spec.deadline_s, 1200.0)
            self.assertEqual(spec.action_budget, 100)

    def test_unparseable_section_falls_back_to_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "task.md"
            _write_minimal_task(
                p,
                extra="## Deadline\n\nfast (no number here)\n",
            )
            spec = parse_task_spec(p)
            self.assertEqual(spec.deadline_s, 600.0)


# ---------------------------------------------------------------------------
# T078 — randomization tokens
# ---------------------------------------------------------------------------


class RandomizationParser(unittest.TestCase):
    def test_no_section_returns_empty_tuple(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "task.md"
            _write_minimal_task(p)
            spec = parse_task_spec(p)
            self.assertEqual(spec.randomization, ())

    def test_parses_kebab_case_identifiers_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "task.md"
            _write_minimal_task(
                p,
                extra=(
                    "## Randomization\n\n"
                    "- log-tag — substituted into the agent's expected log string\n"
                    "- actor-tag — substituted into the placed actor's tag name\n"
                    "- jump-velocity — bogus param\n"
                ),
            )
            spec = parse_task_spec(p)
            self.assertEqual(
                spec.randomization,
                ("log-tag", "actor-tag", "jump-velocity"),
            )

    def test_dedupes_repeated_tokens_preserving_first_seen(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "task.md"
            _write_minimal_task(
                p,
                extra=(
                    "## Randomization\n\n"
                    "- log-tag\n"
                    "- actor-tag\n"
                    "- log-tag — duplicate (should drop)\n"
                ),
            )
            spec = parse_task_spec(p)
            self.assertEqual(spec.randomization, ("log-tag", "actor-tag"))

    def test_skips_non_kebab_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "task.md"
            _write_minimal_task(
                p,
                extra=(
                    "## Randomization\n\n"
                    "Surrounding prose is fine and ignored.\n"
                    "- log-tag\n"
                    "- NOT_KEBAB — uppercase, skipped\n"
                    "- 1starts-with-digit — also skipped\n"
                    "- actor-tag\n"
                ),
            )
            spec = parse_task_spec(p)
            self.assertEqual(spec.randomization, ("log-tag", "actor-tag"))


class RandomizationResolver(unittest.TestCase):
    def test_deterministic_for_same_run_id(self) -> None:
        toks = ("log-tag", "actor-tag")
        a = resolve_randomization_tokens(toks, run_id="run-xyz")
        b = resolve_randomization_tokens(toks, run_id="run-xyz")
        self.assertEqual(a, b)

    def test_different_for_different_run_ids(self) -> None:
        toks = ("log-tag", "actor-tag")
        a = resolve_randomization_tokens(toks, run_id="run-A")
        b = resolve_randomization_tokens(toks, run_id="run-B")
        self.assertNotEqual(a, b)

    def test_hex_length_default_8(self) -> None:
        toks = ("log-tag", "actor-tag", "jump-velocity")
        out = resolve_randomization_tokens(toks, run_id="run-len")
        for v in out.values():
            self.assertEqual(len(v), 8)
            int(v, 16)  # must parse as hex

    def test_custom_length_respected(self) -> None:
        toks = ("log-tag",)
        out = resolve_randomization_tokens(toks, run_id="run-len2", length=16)
        self.assertEqual(len(out["log-tag"]), 16)

    def test_empty_tokens_yields_empty_dict(self) -> None:
        self.assertEqual(resolve_randomization_tokens((), run_id="x"), {})

    def test_per_token_values_differ_within_one_run(self) -> None:
        toks = ("a-x", "b-y", "c-z")
        out = resolve_randomization_tokens(toks, run_id="r")
        # All three should be distinct (8 hex chars from sha256(run_id|token));
        # collision probability ~negligible.
        self.assertEqual(len(set(out.values())), 3)


class RandomizationApplier(unittest.TestCase):
    """Tests for ``apply_randomization`` — the file-rewrite step that
    substitutes ``<<token-name>>`` / ``<<TOKEN_NAME>>`` patterns in a
    cloned substrate workdir with per-run hex values.
    """

    def _planted_workdir(self, root: Path) -> None:
        """Plant a small set of test files including skip-dirs."""
        (root / "a.cpp").write_text(
            'UE_LOG(LogTemp, Display, TEXT("<<log-tag>>"));', encoding="utf-8"
        )
        (root / "b.cpp").write_text(
            "// expected: <<LOG_TAG>>\nint x = 1;", encoding="utf-8"
        )
        (root / "c.cpp").write_text("// no tokens here", encoding="utf-8")
        (root / "d.cpp").write_text(
            "// two: <<actor-tag>> and <<LOG_TAG>>", encoding="utf-8"
        )
        (root / "Binaries").mkdir()
        (root / "Binaries" / "should-skip.cpp").write_text(
            "// <<log-tag>>", encoding="utf-8"
        )
        (root / "ThirdParty").mkdir()
        (root / "ThirdParty" / "vendor.cpp").write_text(
            "// <<log-tag>>", encoding="utf-8"
        )

    def test_substitutes_kebab_and_snake_upper_to_same_value(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._planted_workdir(root)
            tokens = resolve_randomization_tokens(
                ("log-tag", "actor-tag"), run_id="run-A"
            )
            counts = apply_randomization(root, tokens)
            self.assertEqual(counts["log-tag"], 3)  # a + b + d
            self.assertEqual(counts["actor-tag"], 1)  # d
            self.assertEqual(
                (root / "a.cpp").read_text(),
                f'UE_LOG(LogTemp, Display, TEXT("{tokens["log-tag"]}"));',
            )
            self.assertEqual(
                (root / "b.cpp").read_text(),
                f"// expected: {tokens['log-tag']}\nint x = 1;",
            )
            self.assertEqual(
                (root / "d.cpp").read_text(),
                f"// two: {tokens['actor-tag']} and {tokens['log-tag']}",
            )

    def test_skips_unmodified_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._planted_workdir(root)
            tokens = resolve_randomization_tokens(("log-tag",), run_id="r")
            mtime_before = (root / "c.cpp").stat().st_mtime
            apply_randomization(root, tokens)
            # c.cpp has no tokens; should not be rewritten.
            self.assertEqual(
                (root / "c.cpp").read_text(), "// no tokens here"
            )
            self.assertEqual(mtime_before, (root / "c.cpp").stat().st_mtime)

    def test_skips_binaries_thirdparty_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._planted_workdir(root)
            tokens = resolve_randomization_tokens(("log-tag",), run_id="r")
            apply_randomization(root, tokens)
            self.assertEqual(
                (root / "Binaries" / "should-skip.cpp").read_text(),
                "// <<log-tag>>",
            )
            self.assertEqual(
                (root / "ThirdParty" / "vendor.cpp").read_text(),
                "// <<log-tag>>",
            )

    def test_empty_token_map_is_noop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._planted_workdir(root)
            counts = apply_randomization(root, {})
            self.assertEqual(counts, {})
            # Source files untouched (still contain raw token text)
            self.assertIn("<<log-tag>>", (root / "a.cpp").read_text())

    def test_deterministic_per_run_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root1 = Path(tmp) / "r1"
            root2 = Path(tmp) / "r2"
            root1.mkdir()
            root2.mkdir()
            for r in (root1, root2):
                self._planted_workdir(r)
            tokens = resolve_randomization_tokens(("log-tag",), run_id="same")
            apply_randomization(root1, tokens)
            apply_randomization(root2, tokens)
            self.assertEqual(
                (root1 / "a.cpp").read_text(),
                (root2 / "a.cpp").read_text(),
            )


# ---------------------------------------------------------------------------
# T021 — pinning collector
# ---------------------------------------------------------------------------


def _init_mini_git_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "--allow-empty", "-m", "init"],
        cwd=root, check=True,
    )


class GitRevisionLookup(unittest.TestCase):
    def test_returns_none_when_path_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            _init_mini_git_repo(tmp_p)
            self.assertIsNone(
                git_revision_for(tmp_p / "nonexistent", repo_root=tmp_p)
            )

    def test_returns_sha_for_tracked_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            _init_mini_git_repo(tmp_p)
            f = tmp_p / "file.txt"
            f.write_text("hi", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(tmp_p), "add", "file.txt"], check=True
            )
            subprocess.run(
                ["git", "-c", "user.email=t@t", "-c", "user.name=t",
                 "-C", str(tmp_p), "commit", "-q", "-m", "add"],
                check=True,
            )
            sha = git_revision_for(f, repo_root=tmp_p)
            self.assertIsNotNone(sha)
            self.assertEqual(len(sha), 40)


class EngineVersionDetection(unittest.TestCase):
    def test_returns_none_when_ue_root_none(self) -> None:
        self.assertIsNone(detect_engine_version(None))

    def test_returns_none_when_build_version_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(detect_engine_version(Path(tmp)))

    def test_reads_major_minor_patch_from_build_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            (tmp_p / "Engine" / "Build").mkdir(parents=True)
            (tmp_p / "Engine" / "Build" / "Build.version").write_text(
                json.dumps({"MajorVersion": 5, "MinorVersion": 7, "PatchVersion": 1}),
                encoding="utf-8",
            )
            self.assertEqual(detect_engine_version(tmp_p), "5.7.1")


class CollectPinning(unittest.TestCase):
    def _setup_repo(self, root: Path) -> None:
        _init_mini_git_repo(root)
        # Plant a substrate dir, task file, verifier dir.
        (root / "UE-projects" / "Mini").mkdir(parents=True)
        (root / "UE-projects" / "Mini" / "Mini.uproject").write_text("{}")
        (root / "tasks").mkdir()
        (root / "tasks" / "t.md").write_text("# t\n")
        (root / "tools" / "verify-single").mkdir(parents=True)
        (root / "tools" / "verify-single" / "run_task.py").write_text("# v")
        # Commit everything.
        subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t",
             "-C", str(root), "commit", "-q", "-m", "seed"],
            check=True,
        )
        # And the engine "install".
        (root / "ue" / "Engine" / "Build").mkdir(parents=True)
        (root / "ue" / "Engine" / "Build" / "Build.version").write_text(
            json.dumps({"MajorVersion": 5, "MinorVersion": 7, "PatchVersion": 1}),
            encoding="utf-8",
        )

    def test_strict_success_returns_all_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            self._setup_repo(tmp_p)
            result = collect_pinning(
                repo_root=tmp_p,
                substrate_dir=tmp_p / "UE-projects" / "Mini",
                task_path=tmp_p / "tasks" / "t.md",
                verifier_dirs=(tmp_p / "tools" / "verify-single",),
                ue_root=tmp_p / "ue",
                harness_id="filesystem@1.0",
                model_id="anthropic/claude-sonnet-4-6",
                strict=True,
            )
            self.assertEqual(result.engine_version, "5.7.1")
            self.assertEqual(result.harness_id, "filesystem@1.0")
            self.assertEqual(result.model_id, "anthropic/claude-sonnet-4-6")
            self.assertEqual(len(result.substrate_revision), 40)
            self.assertEqual(len(result.task_set_revision), 40)
            self.assertEqual(len(result.verifier_revision), 40)

    def test_strict_raises_when_missing_harness_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            self._setup_repo(tmp_p)
            with self.assertRaises(PinningResolutionError) as ctx:
                collect_pinning(
                    repo_root=tmp_p,
                    substrate_dir=tmp_p / "UE-projects" / "Mini",
                    task_path=tmp_p / "tasks" / "t.md",
                    verifier_dirs=(tmp_p / "tools" / "verify-single",),
                    ue_root=tmp_p / "ue",
                    harness_id="",
                    model_id="x",
                    strict=True,
                )
            self.assertIn("harness_id", ctx.exception.missing)

    def test_strict_raises_when_engine_version_unresolved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            self._setup_repo(tmp_p)
            with self.assertRaises(PinningResolutionError) as ctx:
                collect_pinning(
                    repo_root=tmp_p,
                    substrate_dir=tmp_p / "UE-projects" / "Mini",
                    task_path=tmp_p / "tasks" / "t.md",
                    verifier_dirs=(tmp_p / "tools" / "verify-single",),
                    ue_root=None,  # no UE install
                    harness_id="x",
                    model_id="y",
                    strict=True,
                )
            self.assertIn("engine_version", ctx.exception.missing)

    def test_non_strict_substitutes_placeholders(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            self._setup_repo(tmp_p)
            result = collect_pinning(
                repo_root=tmp_p,
                substrate_dir=tmp_p / "UE-projects" / "Mini",
                task_path=tmp_p / "tasks" / "t.md",
                verifier_dirs=(tmp_p / "tools" / "verify-single",),
                ue_root=None,
                harness_id="",
                model_id="",
                strict=False,
            )
            self.assertEqual(result.engine_version, "unknown")
            self.assertEqual(result.harness_id, "unknown")
            self.assertEqual(result.model_id, "unknown")


if __name__ == "__main__":
    unittest.main()

"""Allow-list extraction + zero-answer-key-leakage tests for prompt_extract.

These tests use the real shipped tasks as fixtures (no synthetic fixtures —
the real specs are the contract). If a future task spec adds a new
answer-leaking section, this test must catch it.
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prompt_extract import extract_agent_visible_prompt  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parents[3]
TASKS = {
    "t0": REPO_ROOT / "tasks/cpp/t0-sanity-log-on-beginplay/task.md",
    "gp_spawner": REPO_ROOT / "tasks/cpp/gp-spawner-population/task.md",
}

DROPPED_HEADERS = (
    "## Task ID and metadata",
    "## Primary concept",
    "## Verifier layers used",
    "## Verifier specification",
    "## Verifier fixtures",
    "## Reference solution metadata",
    "## Anti-gaming notes",
)

LEAKAGE_SUBSTRINGS = (
    "AssertEqual_Int",
    "DispatchBeginPlay",
    "BindLogListener",
    "FTimerManager",
    "FApp::SetFixedDeltaTime",
    "EFunctionalTestResult",
    "CountTag",
    "SetCheckpointSchedule",
    "Over-spawn (loop bug)",
)


class TestSectionsKept(unittest.TestCase):
    def test_t0_contains_user_facing_prompt(self):
        out = extract_agent_visible_prompt(TASKS["t0"])
        self.assertIn("CRAFTBENCH_SANITY_OK", out)
        self.assertIn("exactly once", out)

    def test_t0_contains_workspace_state(self):
        out = extract_agent_visible_prompt(TASKS["t0"])
        self.assertIn("SanityActor.h", out)
        self.assertIn("FunctionalTesting", out)

    def test_gp_spawner_contains_user_facing_prompt(self):
        out = extract_agent_visible_prompt(TASKS["gp_spawner"])
        self.assertIn("exactly **five**", out)
        self.assertIn("SpawnedMinion", out)

    def test_gp_spawner_contains_workspace_state(self):
        out = extract_agent_visible_prompt(TASKS["gp_spawner"])
        self.assertIn("SpawnerActor.h", out)


class TestSectionsDropped(unittest.TestCase):
    def test_no_dropped_section_headers_present(self):
        for tag, path in TASKS.items():
            with self.subTest(task=tag):
                out = extract_agent_visible_prompt(path)
                for header in DROPPED_HEADERS:
                    self.assertNotIn(header, out, f"{tag} leaked {header!r}")


class TestNoLeakageSubstrings(unittest.TestCase):
    def test_verifier_internal_vocab_not_present(self):
        for tag, path in TASKS.items():
            with self.subTest(task=tag):
                out = extract_agent_visible_prompt(path)
                for s in LEAKAGE_SUBSTRINGS:
                    self.assertNotIn(s, out, f"{tag} leaked {s!r}")


class TestMissingSectionRaises(unittest.TestCase):
    def test_raises_on_missing_prompt_section(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write("# Task with no prompt section\n\n## Other\n\nbody\n")
            tmp_path = Path(f.name)
        try:
            with self.assertRaises(ValueError):
                extract_agent_visible_prompt(tmp_path)
        finally:
            tmp_path.unlink()


if __name__ == "__main__":
    unittest.main()

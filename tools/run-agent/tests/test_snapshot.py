"""snapshot_submission round-trip: build workspace, mutate writable files,
assert only mutated files are staged at substrate-relative paths.
"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from snapshot import snapshot_submission  # noqa: E402
from workspace import build_workspace  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parents[3]
SUBSTRATE = REPO_ROOT / "UE-projects/CraftBenchTemplate"
AGENT_WRITABLE = SUBSTRATE / "AGENT_WRITABLE.json"


class TestSnapshot(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="run-agent-test-"))
        self.ws = build_workspace(
            substrate_root=SUBSTRATE,
            agent_writable_json=AGENT_WRITABLE,
            prompt_text="task",
            run_id="snap-test",
            root_dir=self.tmp,
        )
        self.submission_dir = self.tmp / "submission"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_no_edits_returns_empty(self):
        staged = snapshot_submission(self.ws, self.submission_dir, SUBSTRATE)
        self.assertEqual(staged, [])

    def _first_text_writable(self):
        # The writable set now includes binary .uasset assets (Content/Tasks/);
        # pick a text source file so read_text/write_text round-trips.
        return next(
            p for p in self.ws.writable_files
            if p.is_file() and p.suffix in (".cpp", ".h", ".cs")
        )

    def test_single_writable_edit_staged(self):
        target = self._first_text_writable()
        target.write_text(target.read_text(encoding="utf-8") + "\n// agent change\n")

        staged = snapshot_submission(self.ws, self.submission_dir, SUBSTRATE)

        self.assertEqual(len(staged), 1)
        rel = target.relative_to(self.ws.project_dir).as_posix()
        expected_dst = self.submission_dir / rel
        self.assertTrue(expected_dst.exists())
        self.assertIn("// agent change", expected_dst.read_text(encoding="utf-8"))

    def test_readonly_edit_not_staged_even_if_modified(self):
        readonly_target = next(
            p for p in self.ws.readonly_files
            if p.is_file() and p.suffix in (".cs", ".cpp", ".h")
        )
        readonly_target.write_text(readonly_target.read_text(encoding="utf-8") + "\n// sneaky\n")

        staged = snapshot_submission(self.ws, self.submission_dir, SUBSTRATE)
        self.assertEqual(staged, [])

    def test_new_writable_file_staged(self):
        # Agent could legitimately create a new file under a writable prefix
        # (e.g. a helper header). Snapshot RE-WALKS the project_dir, so it picks
        # the file up WITHOUT it being pre-registered in writable_files — this is
        # the gp-flight-mode regression (agent created GA_FlyAbility/FlyingCharacter
        # from scratch; the old build-time list missed them → empty submission).
        writable_dir = self._first_text_writable().parent
        new_file = writable_dir / "AgentHelper.h"
        new_file.write_text("// new file from agent\n")
        # NOTE: deliberately NOT appended to self.ws.writable_files — discovery
        # must come from the re-walk, exactly as in a real agent run.

        staged = snapshot_submission(self.ws, self.submission_dir, SUBSTRATE)
        self.assertEqual(len(staged), 1)
        self.assertEqual(staged[0].name, "AgentHelper.h")

    def test_created_then_edited_files_both_staged(self):
        # The full gp-flight-mode shape: a brand-new module of several files,
        # none pre-existing in the substrate, none registered at build time.
        writable_dir = self._first_text_writable().parent
        created = []
        for name, body in [
            ("GA_FlyAbility.h", "// header\n"),
            ("GA_FlyAbility.cpp", "// impl\n"),
            ("FlyingCharacter.h", "// header\n"),
            ("FlyingCharacter.cpp", "// impl\n"),
        ]:
            f = writable_dir / name
            f.write_text(body)
            created.append(name)

        staged = snapshot_submission(self.ws, self.submission_dir, SUBSTRATE)
        self.assertEqual(sorted(p.name for p in staged), sorted(created))

    def test_created_file_outside_writable_prefix_not_staged(self):
        # A file the agent drops outside the writable prefixes (e.g. at project
        # root) must NOT be staged even though it's new.
        stray = self.ws.project_dir / "STRAY_NOTE.txt"
        stray.write_text("not a submission\n")
        staged = snapshot_submission(self.ws, self.submission_dir, SUBSTRATE)
        self.assertEqual(staged, [])


if __name__ == "__main__":
    unittest.main()

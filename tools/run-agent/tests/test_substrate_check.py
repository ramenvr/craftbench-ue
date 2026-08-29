"""Substrate-integrity check: detects dirty tracked files, ignores untracked.

Uses a temporary git repo as fixture — no dependency on the real substrate
state of the host repo (which is intentionally WIP in CraftBench).
"""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from substrate_check import check_substrate_clean  # noqa: E402


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


class TestCheckSubstrateClean(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="substrate-check-test-"))
        # Init a tiny git repo with one tracked file under "substrate/".
        _git("init", "-q", "-b", "main", cwd=self.tmp)
        _git("config", "user.email", "test@example.com", cwd=self.tmp)
        _git("config", "user.name", "test", cwd=self.tmp)
        self.substrate = self.tmp / "substrate"
        self.substrate.mkdir()
        (self.substrate / "level.umap").write_bytes(b"pristine umap bytes")
        (self.substrate / "main.cpp").write_text("// pristine source\n")
        _git("add", "-A", cwd=self.tmp)
        _git("commit", "-q", "-m", "init", cwd=self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_clean_returns_empty(self):
        self.assertEqual(check_substrate_clean(self.substrate), [])

    def test_modified_tracked_file_detected(self):
        (self.substrate / "level.umap").write_bytes(b"mutated umap bytes!!")
        dirty = check_substrate_clean(self.substrate)
        self.assertEqual(len(dirty), 1)
        self.assertIn("level.umap", dirty[0])
        self.assertTrue(dirty[0].startswith(" M"), f"unexpected status: {dirty[0]!r}")

    def test_deleted_tracked_file_detected(self):
        (self.substrate / "main.cpp").unlink()
        dirty = check_substrate_clean(self.substrate)
        self.assertEqual(len(dirty), 1)
        self.assertIn("main.cpp", dirty[0])

    def test_untracked_file_ignored(self):
        # An agent-readable build artefact or scratch file shouldn't trip the
        # check — only mutations of tracked files matter.
        (self.substrate / "scratch.txt").write_text("not tracked\n")
        self.assertEqual(check_substrate_clean(self.substrate), [])

    def test_not_in_git_repo_returns_empty(self):
        # Use /tmp itself (no .git anywhere upward in a sandbox).
        plain = Path(tempfile.mkdtemp(prefix="not-a-repo-"))
        try:
            self.assertEqual(check_substrate_clean(plain), [])
        finally:
            shutil.rmtree(plain, ignore_errors=True)

    def test_skip_subtree_changes_ignored(self):
        # Files under SKIP_SUBTREES (Binaries/Intermediate/DerivedDataCache/Saved)
        # change every time UE runs and shouldn't trip the integrity check.
        (self.substrate / "Saved").mkdir()
        saved_cfg = self.substrate / "Saved" / "config.ini"
        saved_cfg.write_text("[init]\n")
        intermediate = self.substrate / "Intermediate"
        intermediate.mkdir()
        intermediate_file = intermediate / "build.tmp"
        intermediate_file.write_text("artefact\n")
        _git("add", "-A", cwd=self.tmp)
        _git("commit", "-q", "-m", "add saved+intermediate", cwd=self.tmp)

        # Now mutate both — should be filtered out.
        saved_cfg.write_text("[init]\nmutated=1\n")
        intermediate_file.write_text("rebuilt artefact\n")

        dirty = check_substrate_clean(self.substrate)
        self.assertEqual(dirty, [], f"unexpected dirty entries: {dirty}")

    def test_skip_subtree_filter_still_flags_real_changes(self):
        # Adding noise in SKIP_SUBTREES must not mask a real Content/Maps change.
        (self.substrate / "Saved").mkdir()
        (self.substrate / "Saved" / "noise.txt").write_text("a\n")
        _git("add", "-A", cwd=self.tmp)
        _git("commit", "-q", "-m", "add noise", cwd=self.tmp)

        # Now: mutate both noise AND the eval-relevant .umap.
        (self.substrate / "Saved" / "noise.txt").write_text("changed\n")
        (self.substrate / "level.umap").write_bytes(b"different bytes!")

        dirty = check_substrate_clean(self.substrate)
        self.assertEqual(len(dirty), 1)
        self.assertIn("level.umap", dirty[0])

    def test_uproject_suffix_filtered(self):
        # UE rewrites the .uproject on every project open without changing
        # the eval-relevant content — should not trip the integrity check.
        uproject = self.substrate / "MyProject.uproject"
        uproject.write_text('{"FileVersion":3}\n')
        _git("add", "-A", cwd=self.tmp)
        _git("commit", "-q", "-m", "add .uproject", cwd=self.tmp)

        uproject.write_text('{"FileVersion":3,"_lastOpened":"now"}\n')
        self.assertEqual(check_substrate_clean(self.substrate), [])

    def test_plugins_subtree_filtered(self):
        # Plugins/ is the active-dev area (Aura) and routinely changes.
        plugins = self.substrate / "Plugins" / "MyPlugin"
        plugins.mkdir(parents=True)
        (plugins / "MyPlugin.uplugin").write_text('{"FileVersion":3}\n')
        _git("add", "-A", cwd=self.tmp)
        _git("commit", "-q", "-m", "add plugin", cwd=self.tmp)

        (plugins / "MyPlugin.uplugin").write_text('{"FileVersion":3,"updated":1}\n')
        self.assertEqual(check_substrate_clean(self.substrate), [])


if __name__ == "__main__":
    unittest.main()

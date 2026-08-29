"""Unit tests for provenance._git_dirty tri-state + the copy-era dirty backfill.

_git_dirty read ONLY stdout, and a failed git (exit 128 in a non-repo dir)
prints nothing there — so every copy-era scratch stamped
plugin_repo_dirty=False off its non-repo Plugins/ parent while the rig sat
dirty (2026-08-05 glide-bp matrix). These tests pin the tri-state against
REAL temp git repos (True dirty / False clean / None git-failed) and the
genius_provenance backfill that resolves a copy's dirty against its marker
SOURCE repo.

Run from tools/run-agent:  py -3 -m unittest tests.test_provenance_git_dirty -v
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aura_rig import provenance  # noqa: E402

_HAS_GIT = shutil.which("git") is not None
# The backfill fires only when the scratch's Plugins/ parent probe is UNKNOWN;
# a temp dir nested inside some enclosing repo would probe clean instead.
_TMP_IN_REPO = _HAS_GIT and subprocess.run(
    ["git", "-C", tempfile.gettempdir(), "rev-parse", "--git-dir"],
    capture_output=True, text=True, timeout=15).returncode == 0


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args],
                   capture_output=True, text=True, timeout=30, check=True)


def _mk_rig_repo(root: Path) -> Path:
    """A real repo with a committed Aura/Source/f.cpp (the aura-plugin shape)."""
    rig = root / "rig"
    (rig / "Aura" / "Source").mkdir(parents=True)
    (rig / "Aura" / "Source" / "f.cpp").write_text("int x = 1;\n")
    (rig / "README.md").write_text("rig\n")
    _git(rig, "init", "-q")
    _git(rig, "add", "-A")
    _git(rig, "-c", "user.email=cb@test", "-c", "user.name=cb",
         "commit", "-qm", "seed")
    return rig


def _head(repo: Path) -> str:
    r = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                       capture_output=True, text=True, timeout=15, check=True)
    return r.stdout.strip()


def _mk_project(root: Path, marker: dict) -> Path:
    """Copy-era scratch: Plugins/Aura is a real dir anchored by the marker."""
    aura = root / "proj" / "Plugins" / "Aura"
    aura.mkdir(parents=True)
    (aura / "Aura.uplugin").write_text(
        json.dumps({"VersionName": "0.15.5"}), encoding="utf-8")
    (aura / ".cb-plugin-provenance.json").write_text(
        json.dumps(marker), encoding="utf-8")
    return root / "proj"


@unittest.skipUnless(_HAS_GIT, "git not on PATH")
class TestGitDirtyTriState(unittest.TestCase):
    def test_dirty_tracked_subtree_is_true(self):
        with tempfile.TemporaryDirectory() as d:
            rig = _mk_rig_repo(Path(d))
            (rig / "Aura" / "Source" / "f.cpp").write_text("int x = 2;\n")
            self.assertIs(provenance._git_dirty(rig, "Aura"), True)

    def test_clean_subtree_is_false(self):
        with tempfile.TemporaryDirectory() as d:
            rig = _mk_rig_repo(Path(d))
            self.assertIs(provenance._git_dirty(rig, "Aura"), False)

    def test_dirt_outside_the_subpath_is_false(self):
        with tempfile.TemporaryDirectory() as d:
            rig = _mk_rig_repo(Path(d))
            (rig / "README.md").write_text("moved\n")
            self.assertIs(provenance._git_dirty(rig, "Aura"), False)
            self.assertIs(provenance._git_dirty(rig, "."), True)

    def test_untracked_only_stays_false(self):
        # --untracked-files=no: dirty means MODIFIED TRACKED content.
        with tempfile.TemporaryDirectory() as d:
            rig = _mk_rig_repo(Path(d))
            (rig / "Aura" / "Source" / "new.cpp").write_text("int y;\n")
            self.assertIs(provenance._git_dirty(rig, "Aura"), False)

    def test_git_failure_is_none_not_false(self):
        # git -C <missing dir> exits 128 with EMPTY stdout — the exact shape
        # the old stdout-only read scored as "clean".
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(provenance._git_dirty(Path(d) / "missing"))


class TestGitDirtyExitCodeSeam(unittest.TestCase):
    """Exit-code interpretation via the injected runner (no git needed)."""

    class _R:
        def __init__(self, out: str, rc: int) -> None:
            self.stdout = out
            self.returncode = rc

    def test_nonzero_exit_is_none_even_with_empty_stdout(self):
        r = lambda *a, **k: self._R("", 128)
        self.assertIsNone(provenance._git_dirty(Path("/x"), "Aura", r))

    def test_zero_exit_empty_stdout_is_false(self):
        r = lambda *a, **k: self._R("", 0)
        self.assertIs(provenance._git_dirty(Path("/x"), "Aura", r), False)

    def test_zero_exit_with_status_lines_is_true(self):
        r = lambda *a, **k: self._R(" M Aura/Source/f.cpp\n", 0)
        self.assertIs(provenance._git_dirty(Path("/x"), "Aura", r), True)

    def test_runner_exception_is_none(self):
        def boom(*a, **k):
            raise OSError("no git")
        self.assertIsNone(provenance._git_dirty(Path("/x"), "Aura", boom))


@unittest.skipUnless(_HAS_GIT, "git not on PATH")
@unittest.skipIf(_TMP_IN_REPO, "tempdir sits inside a git repo")
class TestCopyEraDirtyBackfill(unittest.TestCase):
    def test_dirty_source_repo_backfills_true(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            rig = _mk_rig_repo(root)
            sha = _head(rig)
            proj = _mk_project(root, {"src": str(rig / "Aura"),
                                      "genius_sha": sha, "copied_at": "t"})
            (rig / "Aura" / "Source" / "f.cpp").write_text("int x = 2;\n")
            out = provenance.genius_provenance(
                proj, environ={"CB_GENIUS": str(rig)})
        self.assertIs(out["plugin_repo_dirty"], True)
        self.assertEqual(out["plugin_repo_sha"], sha)
        self.assertIs(out["split"], False)

    def test_clean_source_repo_backfills_false(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            rig = _mk_rig_repo(root)
            proj = _mk_project(root, {"src": str(rig / "Aura"),
                                      "genius_sha": _head(rig),
                                      "copied_at": "t"})
            out = provenance.genius_provenance(
                proj, environ={"CB_GENIUS": str(rig)})
        self.assertIs(out["plugin_repo_dirty"], False)

    def test_moved_rig_head_declines_to_none(self):
        # Source HEAD no longer matches the copy-time sha: probing it would
        # describe a DIFFERENT tree, so dirty stays honestly unknown.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            rig = _mk_rig_repo(root)
            proj = _mk_project(root, {"src": str(rig / "Aura"),
                                      "genius_sha": "0" * 40,
                                      "copied_at": "t"})
            (rig / "Aura" / "Source" / "f.cpp").write_text("int x = 2;\n")
            out = provenance.genius_provenance(
                proj, environ={"CB_GENIUS": str(rig)})
        self.assertIsNone(out["plugin_repo_dirty"])


if __name__ == "__main__":
    unittest.main()

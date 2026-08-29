"""Cross-platform tests for additive per-run task isolation (no UE required).

Covers task_layout.stage_flat_scaffolds_active_only (absorbed from staging.py) — the disposable-workdir stager that removes
foreign-task scaffold decoys while keeping the active task's scaffold and all untagged
shared infra. Crucially asserts the stager NEVER walks or touches Plugins/ (the live
Aura junction): only .h/.cpp pairs under Source/CraftBenchTemplate/ are eligible, and
a symlinked Plugins/ tree survives a staging pass untouched.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_PARENT = _HERE.parent
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))

import task_layout as staging  # noqa: E402  (absorbed into task_layout, C0)

_WRITABLE_REL = "Source/CraftBenchTemplate"


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _can_symlink() -> bool:
    """True if this process can create a symlink in a fresh temp dir.

    On Windows, symlink creation needs either Developer Mode or the
    SeCreateSymbolicLinkPrivilege; probe rather than assume.
    """
    probe = Path(tempfile.mkdtemp(prefix="symprobe-"))
    try:
        target = probe / "target"
        target.mkdir()
        link = probe / "link"
        try:
            os.symlink(target, link, target_is_directory=True)
        except (OSError, NotImplementedError, AttributeError):
            return False
        return link.is_symlink()
    finally:
        __import__("shutil").rmtree(probe, ignore_errors=True)


class _StagingFixture(unittest.TestCase):
    """A disposable workdir laid out like a cloned substrate."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="stagetest-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        self.src = self.tmp / _WRITABLE_REL

    def _make_standard_tree(self) -> None:
        """SpawnHostActor (gp-spawn-sequence), TaskActor (gp-timer-delayed-destroy),
        BaseInfra (untagged shared infra)."""
        _write(self.src / "SpawnHostActor.h", "// for task gp-spawn-sequence\n")
        _write(self.src / "SpawnHostActor.cpp", "// for task gp-spawn-sequence\n")
        _write(self.src / "TaskActor.h", "// for task gp-timer-delayed-destroy\n")
        _write(self.src / "TaskActor.cpp", "// for task gp-timer-delayed-destroy\n")
        _write(self.src / "BaseInfra.h", "// shared infra, no tag\n")
        _write(self.src / "BaseInfra.cpp", "// shared infra, no tag\n")


class TestStaging(_StagingFixture):
    def test_keeps_only_active_scaffold(self) -> None:
        self._make_standard_tree()
        removed = staging.stage_flat_scaffolds_active_only(self.tmp, "gp-spawn-sequence")
        self.assertEqual(removed, ["TaskActor.cpp", "TaskActor.h"])
        # Active task's scaffold + untagged infra remain.
        self.assertTrue((self.src / "SpawnHostActor.h").exists())
        self.assertTrue((self.src / "SpawnHostActor.cpp").exists())
        self.assertTrue((self.src / "BaseInfra.h").exists())
        self.assertTrue((self.src / "BaseInfra.cpp").exists())
        # Foreign task's scaffold is gone.
        self.assertFalse((self.src / "TaskActor.h").exists())
        self.assertFalse((self.src / "TaskActor.cpp").exists())

    def test_set_qualified_id_resolves(self) -> None:
        # Set-qualified ids (forward and backslash) must resolve to the bare id.
        for qualified in ("bp-g2/gp-spawn-sequence", "bp-g2\\gp-spawn-sequence"):
            with self.subTest(qualified=qualified):
                # Fresh tree per subTest (staging mutates in place).
                __import__("shutil").rmtree(self.src, ignore_errors=True)
                self._make_standard_tree()
                removed = staging.stage_flat_scaffolds_active_only(self.tmp, qualified)
                self.assertEqual(removed, ["TaskActor.cpp", "TaskActor.h"])
                self.assertTrue((self.src / "SpawnHostActor.h").exists())
                self.assertTrue((self.src / "BaseInfra.h").exists())
                self.assertFalse((self.src / "TaskActor.h").exists())

    def test_untagged_never_removed(self) -> None:
        _write(self.src / "BaseInfra.h", "// shared infra, no tag\n")
        _write(self.src / "BaseInfra.cpp", "// shared infra, no tag\n")
        _write(self.src / "OtherShared.h", "// also untagged\n")
        _write(self.src / "OtherShared.cpp", "// also untagged\n")
        removed = staging.stage_flat_scaffolds_active_only(self.tmp, "gp-spawn-sequence")
        self.assertEqual(removed, [])
        self.assertTrue((self.src / "BaseInfra.h").exists())
        self.assertTrue((self.src / "BaseInfra.cpp").exists())
        self.assertTrue((self.src / "OtherShared.h").exists())
        self.assertTrue((self.src / "OtherShared.cpp").exists())

    @unittest.skipUnless(_can_symlink(), "cannot create symlinks in this environment")
    def test_no_plugins_traversal(self) -> None:
        # A real Plugins/Aura symlink (the live junction hazard) must survive staging
        # untouched: never walked, never unlinked, never in the removed list.
        self._make_standard_tree()
        # Build a sibling target dir with a decoy-tagged scaffold inside it; if the
        # stager wrongly traversed the symlink it could match/unlink this.
        aura_target = self.tmp / "_aura_real"
        _write(aura_target / "Decoy.h", "// for task gp-timer-delayed-destroy\n")
        _write(aura_target / "Decoy.cpp", "// for task gp-timer-delayed-destroy\n")
        plugins_dir = self.tmp / "Plugins"
        plugins_dir.mkdir(parents=True, exist_ok=True)
        link = plugins_dir / "Aura"
        os.symlink(aura_target, link, target_is_directory=True)
        self.assertTrue(link.is_symlink())

        removed = staging.stage_flat_scaffolds_active_only(self.tmp, "gp-spawn-sequence")

        # Standard-tree foreign scaffold removed; nothing under Plugins/ touched.
        self.assertEqual(removed, ["TaskActor.cpp", "TaskActor.h"])
        self.assertTrue(link.is_symlink(), "Plugins/Aura symlink must survive staging")
        self.assertTrue((aura_target / "Decoy.h").exists())
        self.assertTrue((aura_target / "Decoy.cpp").exists())
        self.assertFalse(any("Plugins/" in r or r.startswith("Plugins") for r in removed))

    def test_missing_src_dir_returns_empty(self) -> None:
        # No Source/CraftBenchTemplate/ at all -> no-op, empty list.
        empty = Path(tempfile.mkdtemp(prefix="stageempty-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(empty, ignore_errors=True))
        removed = staging.stage_flat_scaffolds_active_only(empty, "gp-spawn-sequence")
        self.assertEqual(removed, [])


if __name__ == "__main__":
    unittest.main()

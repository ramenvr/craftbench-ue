"""Unit tests for the per-task UE config overlay (B7) — no UE required.

Covers the three primitives of ``config_overlay``:
  * discover — folder-form specs map ue-config/*.ini fragments; flat specs
    and folders without ue-config/ are a {} no-op.
  * apply — marker-headed APPEND onto Config/<IniName>.ini (creating the file
    and the Config dir when absent), trailing newline ensured.
  * revert — byte-identical restore of pre-apply bytes, incl. deleting files
    the apply created (the live-drive undo path; verifier staging never calls
    it because its workdir is disposable).
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_VERIFY = _HERE.parent
if str(_VERIFY) not in sys.path:
    sys.path.insert(0, str(_VERIFY))

import config_overlay  # noqa: E402


class _OverlayTree(unittest.TestCase):
    """A temp task folder (spec + ue-config/) and a temp substrate Config/."""

    TASK_ID = "gp-tag-gated-door"

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="cb-cfg-overlay-"))
        self.addCleanup(
            lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        # Folder-form task with two fragments.
        self.task_dir = self.tmp / "tasks" / "concept-1" / self.TASK_ID
        self.spec = self.task_dir / "task.md"
        self.spec.parent.mkdir(parents=True)
        self.spec.write_text("# Door\n\n## Verifier layers used\nL1, L2\n",
                             encoding="utf-8")
        uc = self.task_dir / "ue-config"
        uc.mkdir()
        # NO trailing newline on purpose — apply must add one.
        (uc / "DefaultGameplayTags.ini").write_text(
            "[/Script/GameplayTags.GameplayTagsSettings]\n"
            '+GameplayTagList=(Tag="Task.Door.Open")',
            encoding="utf-8")
        (uc / "DefaultEngine.ini").write_text(
            "[/Script/Engine.Engine]\nbSmoothFrameRate=False\n",
            encoding="utf-8")
        # Substrate Config/ with ONE pre-existing target (the other is created).
        self.config_dir = self.tmp / "substrate" / "Config"
        self.config_dir.mkdir(parents=True)
        self.engine_ini = self.config_dir / "DefaultEngine.ini"
        self.engine_ini.write_bytes(b"[/Script/Engine.Engine]\nExisting=1\n")


class TestDiscover(_OverlayTree):
    def test_folder_form_maps_ini_fragments(self) -> None:
        frags = config_overlay.discover(self.spec)
        self.assertEqual(sorted(frags),
                         ["DefaultEngine.ini", "DefaultGameplayTags.ini"])
        self.assertEqual(frags["DefaultEngine.ini"],
                         self.task_dir / "ue-config" / "DefaultEngine.ini")

    def test_non_ini_entries_ignored(self) -> None:
        uc = self.task_dir / "ue-config"
        (uc / "NOTES.md").write_text("not config\n", encoding="utf-8")
        (uc / "subdir").mkdir()
        frags = config_overlay.discover(self.spec)
        self.assertEqual(sorted(frags),
                         ["DefaultEngine.ini", "DefaultGameplayTags.ini"])

    def test_flat_spec_is_noop(self) -> None:
        flat = self.tmp / "tasks" / "concept-1" / "flat-task.md"
        flat.write_text("# Flat\n", encoding="utf-8")
        # Even with a sibling ue-config/ dir, a flat spec never picks one up.
        self.assertEqual(config_overlay.discover(flat), {})

    def test_folder_without_ue_config_is_noop(self) -> None:
        bare = self.tmp / "tasks" / "concept-1" / "no-cfg" / "task.md"
        bare.parent.mkdir(parents=True)
        bare.write_text("# Bare\n", encoding="utf-8")
        self.assertEqual(config_overlay.discover(bare), {})


class TestApply(_OverlayTree):
    def _apply(self):
        return config_overlay.apply(
            self.config_dir, config_overlay.discover(self.spec), self.TASK_ID)

    def test_append_preserves_original_and_adds_marker(self) -> None:
        original = self.engine_ini.read_bytes()
        self._apply()
        text = self.engine_ini.read_text(encoding="utf-8")
        self.assertTrue(text.startswith(original.decode("utf-8")),
                        "append must not disturb the pre-existing content")
        self.assertIn(
            f"\n; CraftBench per-task overlay: {self.TASK_ID}\n", text)
        self.assertIn("bSmoothFrameRate=False", text)

    def test_missing_target_created_with_marker_block(self) -> None:
        self._apply()
        tags = self.config_dir / "DefaultGameplayTags.ini"
        self.assertTrue(tags.exists())
        self.assertEqual(
            tags.read_text(encoding="utf-8"),
            f"\n; CraftBench per-task overlay: {self.TASK_ID}\n"
            "[/Script/GameplayTags.GameplayTagsSettings]\n"
            '+GameplayTagList=(Tag="Task.Door.Open")\n',
        )

    def test_fragment_missing_trailing_newline_gets_one(self) -> None:
        self._apply()
        raw = (self.config_dir / "DefaultGameplayTags.ini").read_bytes()
        self.assertTrue(raw.endswith(b"\n"),
                        "fragment without trailing newline must gain one")
        self.assertFalse(raw.endswith(b"\n\n"),
                         "exactly one trailing newline is added")

    def test_applied_fragments_record_created_and_original_bytes(self) -> None:
        original = self.engine_ini.read_bytes()
        applied = {a.ini_name: a for a in self._apply()}
        self.assertFalse(applied["DefaultEngine.ini"].created)
        self.assertEqual(applied["DefaultEngine.ini"].original_bytes, original)
        self.assertTrue(applied["DefaultGameplayTags.ini"].created)
        self.assertIsNone(applied["DefaultGameplayTags.ini"].original_bytes)

    def test_missing_config_dir_created(self) -> None:
        fresh = self.tmp / "substrate2" / "Config"  # does not exist yet
        applied = config_overlay.apply(
            fresh, config_overlay.discover(self.spec), self.TASK_ID)
        self.assertEqual(len(applied), 2)
        self.assertTrue((fresh / "DefaultEngine.ini").exists())
        self.assertTrue(all(a.created for a in applied))


class TestRevert(_OverlayTree):
    def test_round_trip_byte_identical_and_created_deleted(self) -> None:
        original = self.engine_ini.read_bytes()
        applied = config_overlay.apply(
            self.config_dir, config_overlay.discover(self.spec), self.TASK_ID)
        self.assertNotEqual(self.engine_ini.read_bytes(), original)
        config_overlay.revert(self.config_dir, applied)
        self.assertEqual(self.engine_ini.read_bytes(), original,
                         "pre-existing ini must be restored byte-identically")
        self.assertFalse(
            (self.config_dir / "DefaultGameplayTags.ini").exists(),
            "a target the apply CREATED must be deleted by revert")

    def test_revert_idempotent(self) -> None:
        original = self.engine_ini.read_bytes()
        applied = config_overlay.apply(
            self.config_dir, config_overlay.discover(self.spec), self.TASK_ID)
        config_overlay.revert(self.config_dir, applied)
        config_overlay.revert(self.config_dir, applied)  # second call: no raise
        self.assertEqual(self.engine_ini.read_bytes(), original)
        self.assertFalse((self.config_dir / "DefaultGameplayTags.ini").exists())

    def test_revert_empty_list_is_noop(self) -> None:
        before = self.engine_ini.read_bytes()
        config_overlay.revert(self.config_dir, [])
        self.assertEqual(self.engine_ini.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()

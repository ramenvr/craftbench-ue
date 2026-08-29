"""Unit tests for map_locator — flat vs one-level-foldered .umap discovery.

No UE needed: everything is exercised against temp-dir substrate skeletons.
Covers the full resolution rule (exactly-one-candidate resolves in either
layout, ANY duplicate basename raises, missing -> None) plus the MapLocation
coordinate values (package_path / automation_prefix) for both layouts.
(Scaffolders are retired 2026-07: a missing binary is graded FAIL by the
caller — there is no scaffolder_path helper anymore.)

Regression anchor (2026-08-08, bp-g2 scale-up I0.5b): "root always wins" was a
SILENT first-match. ``L_GlideStamina.umap`` and ``L_PoisonStack.umap`` are flat
at ``Content/Maps/`` while the other seven ThirdPerson maps are foldered, so a
new task committing ``Content/Maps/<new-id>/L_GlideStamina.umap`` would have
been graded against the old flat map with no diagnostic anywhere.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

# Make the verify package importable when running this file directly.
_HERE = Path(__file__).resolve().parent
_VERIFY = _HERE.parent
if str(_VERIFY) not in sys.path:
    sys.path.insert(0, str(_VERIFY))

from map_locator import (  # noqa: E402
    DuplicateMapBasenameError,
    MapLocation,
    locate_map,
)


def _drop_umap(substrate: Path, *rel_parts: str) -> Path:
    """Create Content/Maps/<rel_parts...> with fake binary content."""
    umap = substrate / "Content" / "Maps"
    for part in rel_parts:
        umap = umap / part
    umap.parent.mkdir(parents=True, exist_ok=True)
    umap.write_bytes(b"\x00fake umap")
    return umap


class TestLocateMap(unittest.TestCase):
    def test_root_hit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dropped = _drop_umap(root, "L_SanityTask.umap")
            loc = locate_map(root, "L_SanityTask")
            self.assertIsInstance(loc, MapLocation)
            self.assertTrue(loc.umap_path.is_absolute())
            self.assertTrue(loc.umap_path.samefile(dropped))
            self.assertEqual(loc.package_path, "/Game/Maps/L_SanityTask")
            self.assertEqual(loc.automation_prefix, "")

    def test_folder_hit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dropped = _drop_umap(
                root, "t0-sanity-log-on-beginplay", "L_SanityTask.umap"
            )
            loc = locate_map(root, "L_SanityTask")
            self.assertIsNotNone(loc)
            self.assertTrue(loc.umap_path.is_absolute())
            self.assertTrue(loc.umap_path.samefile(dropped))
            self.assertEqual(
                loc.package_path,
                "/Game/Maps/t0-sanity-log-on-beginplay/L_SanityTask",
            )
            self.assertEqual(
                loc.automation_prefix, "t0-sanity-log-on-beginplay"
            )

    def test_flat_plus_foldered_is_ambiguous_not_a_silent_root_win(self) -> None:
        # THE scale bug. Before 2026-08-08 this returned the FLAT map and said
        # nothing, so `some-task`'s fixture would have run in the wrong world
        # and reported an ordinary L2 FAIL against the model.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _drop_umap(root, "L_TimerTask.umap")
            _drop_umap(root, "some-task", "L_TimerTask.umap")
            with self.assertRaises(DuplicateMapBasenameError) as cm:
                locate_map(root, "L_TimerTask")
            msg = str(cm.exception)
            self.assertIn("L_TimerTask", msg)
            self.assertIn("some-task", msg)
            self.assertIn("Content/Maps", msg,
                          "the flat copy must be NAMED, not just counted")

    def test_historical_flat_pair_collides_with_a_new_task_folder(self) -> None:
        # The concrete shape this guards: L_GlideStamina / L_PoisonStack are
        # flat; a scale-up task that folders a map of the same name is a bug.
        for map_name in ("L_GlideStamina", "L_PoisonStack"):
            with self.subTest(map_name=map_name):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    _drop_umap(root, f"{map_name}.umap")
                    _drop_umap(root, "gp-new-family-bp", f"{map_name}.umap")
                    with self.assertRaises(DuplicateMapBasenameError):
                        locate_map(root, map_name)

    def test_flat_layout_task_still_resolves(self) -> None:
        # "Do not break the flat-layout tasks": a lone flat map, with OTHER
        # tasks foldered beside it, resolves exactly as it always did.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            flat = _drop_umap(root, "L_GlideStamina.umap")
            _drop_umap(root, "tp2-sprint-stamina", "L_TpSprint.umap")
            _drop_umap(root, "t2-npc-follows-player", "L_NpcFollow.umap")
            loc = locate_map(root, "L_GlideStamina")
            self.assertTrue(loc.umap_path.samefile(flat))
            self.assertEqual(loc.package_path, "/Game/Maps/L_GlideStamina")
            self.assertEqual(loc.automation_prefix, "")

    def test_duplicate_error_is_a_valueerror_for_legacy_callers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _drop_umap(root, "task-a", "L_Dupe.umap")
            _drop_umap(root, "task-b", "L_Dupe.umap")
            with self.assertRaises(ValueError):
                locate_map(root, "L_Dupe")

    def test_duplicate_error_carries_machine_readable_facts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _drop_umap(root, "task-a", "L_Dupe.umap")
            _drop_umap(root, "task-b", "L_Dupe.umap")
            with self.assertRaises(DuplicateMapBasenameError) as cm:
                locate_map(root, "L_Dupe")
            err = cm.exception
            self.assertEqual(err.map_name, "L_Dupe")
            self.assertEqual(
                sorted(p.parent.name for p in err.paths), ["task-a", "task-b"]
            )

    def test_multi_folder_ambiguity_raises_naming_folders(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _drop_umap(root, "task-a", "L_Dupe.umap")
            _drop_umap(root, "task-b", "L_Dupe.umap")
            with self.assertRaises(ValueError) as cm:
                locate_map(root, "L_Dupe")
            msg = str(cm.exception)
            self.assertIn("task-a", msg)
            self.assertIn("task-b", msg)
            self.assertIn("L_Dupe", msg)

    def test_missing_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Even with the Maps dir present but empty.
            (root / "Content" / "Maps").mkdir(parents=True)
            self.assertIsNone(locate_map(root, "L_Nowhere"))

    def test_missing_maps_dir_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(locate_map(Path(tmp), "L_Nowhere"))

    def test_other_basenames_in_folders_do_not_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _drop_umap(root, "some-task", "L_Other.umap")
            self.assertIsNone(locate_map(root, "L_Wanted"))


class TestScaffolderRetirement(unittest.TestCase):
    def test_scaffolder_path_helper_is_gone(self) -> None:
        # Scaffolders retired 2026-07: the module must not grow the helper back.
        import map_locator
        self.assertFalse(hasattr(map_locator, "scaffolder_path"))


if __name__ == "__main__":
    unittest.main()

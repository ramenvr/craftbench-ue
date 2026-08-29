"""The warm slot's ENGINE-BUILD key (no UE required).

A slot's ``Binaries/`` + ``Intermediate/Build/`` are object files produced by
one particular engine build. The meta's ``ue_version`` is a version TRIPLE, so
an in-place engine rebuild that bumps only the changelist left every slot valid
and handed the next verify a cache the current toolchain never produced.
"""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_HERE = Path(__file__).resolve().parent
_PARENT = _HERE.parent
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))

import build_warm_baseline  # noqa: E402
import warm_cache  # noqa: E402

WRITABLE = ("Source/CraftBenchTemplate/", "Content/Tasks/")


def _version(patch: int, changelist: int) -> dict:
    return {"MajorVersion": 5, "MinorVersion": 8, "PatchVersion": patch,
            "Changelist": changelist}


class TestEngineBuildKey(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="warm-engine-"))
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))
        self.slot = self.tmp / "pool" / "slot-0"
        build = warm_cache.slot_substrate_dir(self.slot)
        (build / "Intermediate" / "Build").mkdir(parents=True)
        (build / "Intermediate" / "Build" / "a.obj").write_text("obj")
        (build / "Binaries" / "Win64").mkdir(parents=True)
        (build / "Binaries" / "Win64" / "Mod.dll").write_text("dll")
        warm_cache.snapshot_dir(self.slot).mkdir(parents=True)
        warm_cache.write_meta(self.slot, {
            "schema": warm_cache.SCHEMA,
            "substrate_tree_sha": "abc123",
            "ue_version": "5.8.1",
            "writable_prefixes": list(WRITABLE),
        })
        self._stamp_slot(_version(1, 55116800))

    def _stamp_slot(self, version: dict) -> None:
        """Write UBT's own record of the engine that built the slot's binaries."""
        binaries = warm_cache.slot_substrate_dir(self.slot) / "Binaries" / "Win64"
        for name in ("CraftBenchTemplate.target", "CraftBenchTemplateEditor.target"):
            (binaries / name).write_text(json.dumps({"Version": version}),
                                        encoding="utf-8")

    def _engine(self, version: dict | None) -> Path:
        root = self.tmp / "UE_5.8"
        (root / "Engine" / "Build").mkdir(parents=True, exist_ok=True)
        if version is not None:
            (root / "Engine" / "Build" / "Build.version").write_text(
                json.dumps(version), encoding="utf-8")
        return root

    def _is_valid(self, ue_root):
        return warm_cache.is_valid(self.slot, substrate_tree_sha="abc123",
                                  ue_version="5.8.1", ue_root=ue_root)

    def test_same_triple_new_changelist_is_a_miss(self) -> None:
        ok, reason = self._is_valid(self._engine(_version(1, 56057345)))
        self.assertFalse(ok, "a rebuilt engine must invalidate the cache")
        self.assertIn("engine build", reason)

    def test_matching_engine_build_is_valid(self) -> None:
        ok, reason = self._is_valid(self._engine(_version(1, 55116800)))
        self.assertTrue(ok, reason)

    def test_unreadable_build_version_is_a_miss(self) -> None:
        ok, reason = self._is_valid(self._engine(None))
        self.assertFalse(ok, "an unnameable engine must never be trusted")
        self.assertIn("engine build", reason)

    def test_slot_with_no_target_record_is_a_miss(self) -> None:
        for target in (warm_cache.slot_substrate_dir(self.slot) / "Binaries"
                       ).rglob("*.target"):
            target.unlink()
        ok, reason = self._is_valid(self._engine(_version(1, 55116800)))
        self.assertFalse(ok, "an unattributable cache must never be trusted")
        self.assertIn("engine build", reason)

    def test_try_acquire_any_carries_the_engine_down_to_is_valid(self) -> None:
        slot, reason = warm_cache.try_acquire_any(
            self.slot.parent, substrate_tree_sha="abc123", ue_version="5.8.1",
            writable_prefixes=WRITABLE,
            ue_root=self._engine(_version(1, 56057345)),
        )
        if slot is not None:
            slot.release()
        self.assertIsNone(slot, "a stale-engine slot must not be acquired")
        self.assertIn("engine build", reason)


class TestPrimerSuppliesTheEngine(unittest.TestCase):
    """`cb warm-prime` must ask the engine-build question, not just the triple.

    Without it the primer calls a stale-engine slot "already current" and skips
    the one rebuild that would heal it — the pool then has no way back except
    --force.
    """

    def test_primer_passes_ue_root_to_is_valid(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="warm-primer-"))
        self.addCleanup(lambda: shutil.rmtree(tmp, ignore_errors=True))
        if not warm_cache.substrate_tree_sha(
                build_warm_baseline.REPO_ROOT / "UE-projects" / "CraftBenchTemplate",
                repo_root=build_warm_baseline.REPO_ROOT):
            self.skipTest("substrate has no git tree SHA here")
        seen: list = []

        def _fake_is_valid(slot_dir, **kw):
            seen.append(kw)
            return True, "valid"

        with mock.patch.object(warm_cache, "is_valid", _fake_is_valid), \
                contextlib.redirect_stdout(io.StringIO()):
            rc = build_warm_baseline.main([
                "--substrate", "CraftBenchTemplate",
                "--ue-root", str(tmp / "UE_5.8"),
                "--warm-cache-dir", str(tmp / "pool"),
                "--slots", "1",
            ])
        self.assertEqual(rc, 0)
        self.assertTrue(seen, "the primer never validated a slot")
        self.assertIsNotNone(seen[0].get("ue_root"),
                             "the primer must name the engine it is priming for")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

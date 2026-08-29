"""Offline tests for the path-stable L1 warm build cache (no UE required).

Covers the two correctness-critical operations of a warm slot:
  * reset_to_pristine — restores the agent-writable dirs from the snapshot
    (dropping the previous submission) while KEEPING Intermediate/Binaries, so
    one verify can't leak into the next.
  * bump_overlaid — the gate: every overlaid source ends up strictly newer than
    every cached artifact, so UBT recompiles the agent's delta (else a broken
    submission could reuse a baseline .obj and falsely PASS).
Plus the slot lock (one verify per slot) and baseline validity/invalidation.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_HERE = Path(__file__).resolve().parent
_PARENT = _HERE.parent
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))

import warm_cache  # noqa: E402

OLD = 1_000_000.0  # definitively in the past


def _write(path: Path, text: str, mtime: float | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def _mktemp() -> Path:
    return Path(tempfile.mkdtemp(prefix="warmtest-"))


class _SlotFixture(unittest.TestCase):
    """A baseline dir laid out like build_warm_baseline produces it."""

    WRITABLE = ("Source/CraftBenchTemplate/", "Content/Tasks/")

    def setUp(self) -> None:
        self.tmp = _mktemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        self.bdir = self.tmp / "CraftBenchTemplate"
        self.build = warm_cache.slot_substrate_dir(self.bdir)
        self.snap = warm_cache.snapshot_dir(self.bdir)
        # Built outputs (the cache), stamped old.
        _write(self.build / "Intermediate" / "Build" / "a.obj", "obj", OLD)
        _write(self.build / "Binaries" / "Win64" / "Mod.dll", "dll", OLD)
        # Pristine substrate source files + their snapshot.
        _write(self.build / "Source" / "CraftBenchTemplate" / "Sanity.cpp", "pristine", OLD)
        _write(self.snap / "Source" / "CraftBenchTemplate" / "Sanity.cpp", "pristine", OLD)
        # Config/ is VERIFIER-mutable (the B7 per-task config overlay appends to
        # it at staging) — snapshotted at prime time like the writable dirs.
        _write(self.build / "Config" / "DefaultEngine.ini", "[/Script/Engine]\n", OLD)
        _write(self.snap / "Config" / "DefaultEngine.ini", "[/Script/Engine]\n", OLD)
        warm_cache.write_meta(self.bdir, {
            "schema": warm_cache.SCHEMA,
            "substrate_tree_sha": "abc123",
            "ue_version": "5.7.4",
            "writable_prefixes": list(self.WRITABLE),
        })

    def _slot(self) -> warm_cache.WarmSlot:
        slot, reason = warm_cache.try_acquire(
            self.bdir, substrate_tree_sha="abc123", ue_version="5.7.4",
            writable_prefixes=self.WRITABLE, ue_root=None,
        )
        self.assertIsNotNone(slot, reason)
        self.addCleanup(slot.release)
        return slot


class TestReset(_SlotFixture):
    def test_removes_agent_added_file_and_keeps_cache(self) -> None:
        slot = self._slot()
        # Simulate a previous submission: an agent-added file in the writable dir.
        added = self.build / "Source" / "CraftBenchTemplate" / "AgentActor.cpp"
        _write(added, "agent code")
        slot.reset_to_pristine()
        self.assertFalse(added.exists(), "agent-added file must be removed by reset")
        # Pristine file restored; cache untouched.
        self.assertTrue((self.build / "Source" / "CraftBenchTemplate" / "Sanity.cpp").exists())
        self.assertTrue((self.build / "Intermediate" / "Build" / "a.obj").exists())
        self.assertTrue((self.build / "Binaries" / "Win64" / "Mod.dll").exists())

    def test_restores_edited_pristine_file(self) -> None:
        slot = self._slot()
        sanity = self.build / "Source" / "CraftBenchTemplate" / "Sanity.cpp"
        sanity.write_text("AGENT EDITED THIS", encoding="utf-8")
        slot.reset_to_pristine()
        self.assertEqual(sanity.read_text(encoding="utf-8"), "pristine")

    def test_reset_stats(self) -> None:
        slot = self._slot()
        st = slot.reset_to_pristine()
        # Source/CraftBenchTemplate/ and the verifier-mutable Config/ are
        # snapshotted -> restored; Content/Tasks/ has no snapshot and doesn't
        # exist -> neither restored nor removed.
        self.assertEqual(st.prefixes_restored, 2)


class TestConfigReset(_SlotFixture):
    """B7 — verifies can append a per-task config overlay onto Config/*.ini,
    so the slot must reset Config/ to pristine each verify (SCHEMA v3)."""

    def test_overlay_appended_ini_restored_to_pristine(self) -> None:
        slot = self._slot()
        ini = self.build / "Config" / "DefaultEngine.ini"
        with open(ini, "a", encoding="utf-8") as fh:
            fh.write("\n; CraftBench per-task overlay: some-task\nOverlay=1\n")
        slot.reset_to_pristine()
        self.assertEqual(ini.read_text(encoding="utf-8"), "[/Script/Engine]\n",
                         "an overlay-appended ini must reset to pristine")

    def test_overlay_created_ini_removed(self) -> None:
        slot = self._slot()
        created = self.build / "Config" / "DefaultGameplayTags.ini"
        _write(created, "; CraftBench per-task overlay: some-task\n+Tag=X\n")
        slot.reset_to_pristine()
        self.assertFalse(created.exists(),
                         "an overlay-created ini must be removed by reset")
        self.assertTrue((self.build / "Config" / "DefaultEngine.ini").exists())

    def test_bump_leaves_config_ini_mtimes(self) -> None:
        # Config/ is NOT a compile input: the correctness-gate bump must not
        # churn its mtimes (only the writable-prefix sources are bumped).
        slot = self._slot()
        slot.bump_writable_sources()
        ini = self.build / "Config" / "DefaultEngine.ini"
        self.assertAlmostEqual(ini.stat().st_mtime, OLD, delta=2.0)


class TestSchemaV4(unittest.TestCase):
    """SCHEMA is bumped whenever the SNAPSHOT CONTRACT changes, so a baseline
    built under the old contract auto-invalidates to a cold build rather than
    being reset by a rule it was not built for.

    - 2->3: Config/ joined the snapshot, so a pre-B7 baseline (whose snapshot
      lacks Config/) could otherwise leak one verify's ini overlay into the next.
    - 3->4: the ANTI-CONTAMINATION reset. The snapshot now captures the whole
      tree minus COMPILER_CACHE_KEEP and the reset DELETES anything absent from
      it. A v3 snapshot holds only the writable prefixes, so running the v4 reset
      against one would delete Source/, Content/, Saved/ and the .uproject —
      everything it never captured. The bump is what makes that unreachable.

    The exact-value pin is deliberate: a bump must be a decision someone makes
    on purpose, with the reason written down here, not a number that drifts."""

    def test_schema_is_4(self) -> None:
        self.assertEqual(warm_cache.SCHEMA, 4)

    def test_verifier_mutable_prefixes_include_config(self) -> None:
        self.assertIn("Config/", warm_cache.VERIFIER_MUTABLE_PREFIXES)


class TestOldSchemaInvalid(_SlotFixture):
    def test_schema2_baseline_misses(self) -> None:
        meta = warm_cache.read_meta(self.bdir)
        meta["schema"] = 2
        warm_cache.write_meta(self.bdir, meta)
        ok, reason = warm_cache.is_valid(
            self.bdir, substrate_tree_sha="abc123", ue_version="5.7.4",
            ue_root=None)
        self.assertFalse(ok)
        self.assertIn("schema", reason)


class TestBumpWritableSources(_SlotFixture):
    def test_reverted_pristine_source_is_bumped(self) -> None:
        """The gate that the overlaid-only bump MISSED: a reset-restored pristine
        file the agent did NOT overlay (e.g. an empty submission) keeps its old
        snapshot mtime — older than the previous leg's .obj. bump_writable_sources
        must still bump it newer so UBT recompiles it (no stale-obj false pass)."""
        slot = self._slot()
        sanity = self.build / "Source" / "CraftBenchTemplate" / "Sanity.cpp"
        self.assertLess(sanity.stat().st_mtime, OLD + 1.0)  # starts old, like a fresh reset
        slot.bump_writable_sources()
        newest_artifact = max(
            warm_cache._newest_mtime(self.build / d) for d in warm_cache._CACHED_DIRS
        )
        self.assertGreater(
            sanity.stat().st_mtime, newest_artifact,
            "a reverted pristine source must be bumped newer than every cached .obj",
        )

    def test_overlaid_added_file_also_bumped(self) -> None:
        slot = self._slot()
        added = "Source/CraftBenchTemplate/AgentActor.cpp"
        _write(self.build / added, "agent code", OLD - 500.0)  # worst case
        slot.bump_writable_sources()
        newest_artifact = max(
            warm_cache._newest_mtime(self.build / d) for d in warm_cache._CACHED_DIRS
        )
        self.assertGreater((self.build / added).stat().st_mtime, newest_artifact)

    def test_cached_artifact_mtimes_preserved(self) -> None:
        slot = self._slot()
        slot.bump_writable_sources()
        obj = self.build / "Intermediate" / "Build" / "a.obj"
        self.assertAlmostEqual(obj.stat().st_mtime, OLD, delta=2.0)


class TestSlotLock(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = _mktemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))

    def test_second_acquire_fails_until_release(self) -> None:
        p = self.tmp / "slot.lock"
        a = warm_cache.SlotLock(p)
        b = warm_cache.SlotLock(p)
        self.assertTrue(a.acquire())
        self.assertFalse(b.acquire(), "a second holder must not acquire a held lock")
        a.release()
        self.assertTrue(b.acquire(), "lock should be acquirable after release")
        b.release()


class TestTryAcquire(_SlotFixture):
    def test_busy_slot_returns_none(self) -> None:
        first = self._slot()  # holds the lock
        second, reason = warm_cache.try_acquire(
            self.bdir, substrate_tree_sha="abc123", ue_version="5.7.4",
            writable_prefixes=self.WRITABLE, ue_root=None,
        )
        self.assertIsNone(second)
        self.assertIn("busy", reason)

    def test_stale_tree_sha_returns_none(self) -> None:
        slot, reason = warm_cache.try_acquire(
            self.bdir, substrate_tree_sha="DIFFERENT", ue_version="5.7.4",
            writable_prefixes=self.WRITABLE, ue_root=None,
        )
        self.assertIsNone(slot)
        self.assertIn("tree SHA", reason)


def _make_valid_slot(slot_dir: Path, tree_sha: str = "abc123", ue: str = "5.7.4",
                     writable=("Source/CraftBenchTemplate/",)) -> None:
    """Lay out a minimally-valid slot (cache dirs + snapshot + meta) on disk."""
    build = warm_cache.slot_substrate_dir(slot_dir)
    (build / "Intermediate").mkdir(parents=True)
    (build / "Binaries").mkdir(parents=True)
    _write(build / "Source" / "CraftBenchTemplate" / "S.cpp", "p", OLD)
    _write(warm_cache.snapshot_dir(slot_dir) / "Source" / "CraftBenchTemplate" / "S.cpp", "p", OLD)
    warm_cache.write_meta(slot_dir, {
        "schema": warm_cache.SCHEMA, "substrate_tree_sha": tree_sha,
        "ue_version": ue, "writable_prefixes": list(writable),
    })


class TestPool(unittest.TestCase):
    WRITABLE = ("Source/CraftBenchTemplate/",)

    def setUp(self) -> None:
        self.tmp = _mktemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        self.root = self.tmp / "CraftBenchTemplate"
        _make_valid_slot(warm_cache.slot_path(self.root, 0))
        _make_valid_slot(warm_cache.slot_path(self.root, 1))
        self._held: list = []
        self.addCleanup(lambda: [s.release() for s in self._held])

    def _acquire_any(self):
        slot, reason = warm_cache.try_acquire_any(
            self.root, substrate_tree_sha="abc123", ue_version="5.7.4",
            writable_prefixes=self.WRITABLE, ue_root=None)
        if slot is not None:
            self._held.append(slot)
        return slot, reason

    def test_discovers_slots_in_order(self) -> None:
        dirs = warm_cache.discover_slot_dirs(self.root)
        self.assertEqual([d.name for d in dirs], ["slot-0", "slot-1"])

    def test_two_concurrent_acquire_distinct_slots(self) -> None:
        a, _ = self._acquire_any()
        b, _ = self._acquire_any()
        self.assertIsNotNone(a)
        self.assertIsNotNone(b)
        self.assertNotEqual(a.slot_dir, b.slot_dir, "two verifies must land on different slots")

    def test_third_acquire_misses_when_pool_full(self) -> None:
        self._acquire_any()
        self._acquire_any()
        c, reason = self._acquire_any()
        self.assertIsNone(c)
        self.assertIn("busy", reason)

    def test_empty_pool_misses(self) -> None:
        slot, reason = warm_cache.try_acquire_any(
            self.tmp / "nopool", substrate_tree_sha="abc123", ue_version="5.7.4",
            writable_prefixes=self.WRITABLE, ue_root=None)
        self.assertIsNone(slot)
        self.assertIn("no warm pool", reason)

    def test_stale_pool_misses(self) -> None:
        slot, reason = warm_cache.try_acquire_any(
            self.root, substrate_tree_sha="DIFFERENT", ue_version="5.7.4",
            writable_prefixes=self.WRITABLE, ue_root=None)
        self.assertIsNone(slot)


class TestIsValid(_SlotFixture):
    def test_valid(self) -> None:
        ok, reason = warm_cache.is_valid(self.bdir, substrate_tree_sha="abc123",
                                    ue_version="5.7.4", ue_root=None)
        self.assertTrue(ok, reason)

    def test_miss_uncommitted(self) -> None:
        ok, reason = warm_cache.is_valid(self.bdir, substrate_tree_sha=None,
                                    ue_version="5.7.4", ue_root=None)
        self.assertFalse(ok)
        self.assertIn("not committed", reason)

    def test_miss_ue_version(self) -> None:
        ok, reason = warm_cache.is_valid(self.bdir, substrate_tree_sha="abc123",
                                    ue_version="5.7.5", ue_root=None)
        self.assertFalse(ok)
        self.assertIn("UE version", reason)

    def test_miss_missing_snapshot(self) -> None:
        import shutil

        shutil.rmtree(self.snap)
        ok, reason = warm_cache.is_valid(self.bdir, substrate_tree_sha="abc123",
                                    ue_version="5.7.4", ue_root=None)
        self.assertFalse(ok)
        self.assertIn("snapshot", reason)

    def test_miss_missing_binaries(self) -> None:
        import shutil

        shutil.rmtree(self.build / "Binaries")
        ok, reason = warm_cache.is_valid(self.bdir, substrate_tree_sha="abc123",
                                    ue_version="5.7.4", ue_root=None)
        self.assertFalse(ok)
        self.assertIn("Binaries", reason)


class TestMakeSnapshot(unittest.TestCase):
    def test_snapshots_existing_prefixes_only(self) -> None:
        tmp = _mktemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(tmp, ignore_errors=True))
        build = tmp / "build"
        _write(build / "Source" / "CraftBenchTemplate" / "X.cpp", "x")
        # Content/Tasks/ intentionally absent.
        n = warm_cache.make_snapshot(
            build, tmp / "snapshot", ("Source/CraftBenchTemplate/", "Content/Tasks/")
        )
        self.assertEqual(n, 1)
        self.assertTrue((tmp / "snapshot" / "Source" / "CraftBenchTemplate" / "X.cpp").exists())

    def test_config_captured_without_being_a_writable_prefix(self) -> None:
        # Config/ is auto-included (VERIFIER_MUTABLE_PREFIXES): the caller only
        # passes the manifest's writable prefixes, yet the snapshot must still
        # capture Config/ so per-verify resets can undo the B7 overlay.
        tmp = _mktemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(tmp, ignore_errors=True))
        build = tmp / "build"
        _write(build / "Source" / "CraftBenchTemplate" / "X.cpp", "x")
        _write(build / "Config" / "DefaultEngine.ini", "[/Script/Engine]\n")
        n = warm_cache.make_snapshot(
            build, tmp / "snapshot", ("Source/CraftBenchTemplate/",)
        )
        self.assertEqual(n, 2)
        self.assertTrue(
            (tmp / "snapshot" / "Config" / "DefaultEngine.ini").exists())

    def test_duplicate_prefix_does_not_crash(self) -> None:
        # Content/Tasks/ legitimately appears in BOTH writable and asset_writable;
        # the concatenated list has a duplicate that must not crash copytree.
        tmp = _mktemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(tmp, ignore_errors=True))
        build = tmp / "build"
        _write(build / "Content" / "Tasks" / "t.uasset", "t")
        n = warm_cache.make_snapshot(
            build, tmp / "snapshot", ("Content/Tasks/", "Content/Tasks/")
        )
        self.assertEqual(n, 1)
        self.assertTrue((tmp / "snapshot" / "Content" / "Tasks" / "t.uasset").exists())


class TestDefaultCacheRootIsCanonical(unittest.TestCase):
    """FAILURE-LOG 2026-07-25 — same 8.3 short-name class as the cold mkdtemp
    workdir, one layer up.

    A warm slot dir becomes the UE project path AND the parent of the
    ``out/l2_report`` dir handed to the editor as ``-ReportExportPath`` — the
    exact path role that scored ``cb batch-eval --references all`` 0/15 when it
    carried ``SHORT~1``. Every input to ``default_cache_root`` is an env string
    a Windows host can hand us in short form, so the helper canonicalizes.
    (Second reason: UBT's cache is path-bound — primer and verifier must spell
    the slot path identically or the warm build is thrown away.)
    """

    def test_env_override_is_resolved(self) -> None:
        raw = Path(tempfile.mkdtemp(prefix="warmtest-canon-"))
        self.addCleanup(
            lambda: __import__("shutil").rmtree(raw, ignore_errors=True))
        # A relative-component spelling stands in for the 8.3 alias on every
        # platform: .resolve() must collapse it, .absolute() alone would not.
        spelling = raw / "pool" / ".." / "pool"
        with mock.patch.dict(os.environ, {"CB_WARM_CACHE_DIR": str(spelling)}):
            got = warm_cache.default_cache_root()
        self.assertEqual(got, (raw / "pool").resolve())
        self.assertEqual(got, got.resolve())

    @unittest.skipUnless(os.name == "nt", "8.3 short names are a Windows-only concept")
    def test_env_override_expands_an_8dot3_component(self) -> None:
        import ctypes
        import re as _re
        import shutil as _shutil

        long_root = Path(tempfile.mkdtemp(prefix="warmtest-8dot3-probe-")).resolve()
        self.addCleanup(lambda: _shutil.rmtree(long_root, ignore_errors=True))
        buf = ctypes.create_unicode_buffer(1024)
        n = ctypes.windll.kernel32.GetShortPathNameW(str(long_root), buf, 1024)
        short = buf.value if n else ""
        if not short or not _re.search(r"~[0-9]", short):
            self.skipTest("8.3 short-name generation is disabled on this volume")

        with mock.patch.dict(os.environ, {"CB_WARM_CACHE_DIR": short}):
            got = warm_cache.default_cache_root()
        self.assertFalse(
            any(_re.search(r"~[0-9]", seg) for seg in got.parts),
            f"warm cache root {got} still carries an 8.3 short component - a slot "
            "under it would spell -ReportExportPath the way that scored 0/15",
        )
        self.assertEqual(got, long_root)


if __name__ == "__main__":
    unittest.main()

"""The UBT build lock — and above all, that it can never change a verdict.

Every test here is about MONOTONICITY. The lock exists to remove a false FAIL
(Build.bat's mutex is keyed on the engine install, so unrelated projects contend
and the loser returns exit 1 with no compile errors — reproduced 2026-07-31 with
submission sha 583ebb4839a9 passing quiet and failing contended).

An adversarial review rejected the obvious design, where failing to take the lock
produces a non-graded verdict: that hands the model under test a denominator
opt-out requiring no submission content at all — one detached process holding the
lock is enough. So the contract is "wait, then build anyway", and these tests
exist to keep it that way.
"""
import os
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import unittest
from pathlib import Path

_VERIFY = Path(__file__).resolve().parent.parent
if str(_VERIFY) not in sys.path:
    sys.path.insert(0, str(_VERIFY))

import build_lock  # noqa: E402


class TestLockPathKeying(unittest.TestCase):
    def test_same_engine_different_spelling_collides(self):
        """Two processes pointed at one engine by different spellings MUST share
        a lock — otherwise the lock silently does nothing for exactly the pair of
        runs most likely to collide."""
        a = build_lock.lock_path_for(Path("Q:/UE_5.8"))
        b = build_lock.lock_path_for(Path("q:\\UE_5.8"))
        self.assertEqual(a, b)

    def test_different_engines_do_not_collide(self):
        a = build_lock.lock_path_for(Path("Q:/UE_5.8"))
        b = build_lock.lock_path_for(Path("Q:/UE_5.9"))
        self.assertNotEqual(a, b)


class TestMonotonicity(unittest.TestCase):
    """The lock must never prevent a build. These are the security tests."""

    def test_acquires_when_free(self):
        with build_lock.ubt_build_lock(Path("Q:/UE_test_free")) as outcome:
            self.assertTrue(outcome.held)
            self.assertEqual(outcome.reason, "acquired")

    def test_timeout_still_enters_the_body(self):
        """THE core property: a lock we could not take does not stop the build."""
        ue = Path("Q:/UE_test_busy")
        holder_entered = threading.Event()
        release = threading.Event()

        def hold():
            with build_lock.ubt_build_lock(ue, timeout=0) as o:
                if o.held:
                    holder_entered.set()
                    release.wait(10)

        t = threading.Thread(target=hold, daemon=True)
        t.start()
        self.assertTrue(holder_entered.wait(5), "holder never acquired")
        try:
            ran = False
            with build_lock.ubt_build_lock(ue, timeout=0.5) as outcome:
                ran = True                      # <-- the build happens regardless
            self.assertTrue(ran, "the body MUST run even when the lock is busy")
            self.assertFalse(outcome.held)
            self.assertEqual(outcome.reason, "timeout")
        finally:
            release.set()
            t.join(10)

    def test_hostile_lock_path_still_enters_the_body(self):
        """A DIRECTORY planted at the lock path makes open() raise. Without the
        guard that reaches run_task's crash trap and becomes exit 7 —
        a non-graded verdict an agent could trigger at will."""
        tmp = Path(tempfile.mkdtemp(prefix="cb-hostile-"))
        ue = Path("Q:/UE_test_hostile")
        real = build_lock.lock_path_for(ue)
        try:
            # Force the lock path to be a directory.
            real.parent.mkdir(parents=True, exist_ok=True)
            if real.exists() and real.is_file():
                real.unlink()
            real.mkdir(parents=True, exist_ok=True)
            ran = False
            with build_lock.ubt_build_lock(ue, timeout=0.2) as outcome:
                ran = True
            self.assertTrue(ran, "a hostile lock path must not stop the build")
            self.assertFalse(outcome.held)
            self.assertTrue(outcome.reason.startswith("unavailable"))
        finally:
            try:
                real.rmdir()
            except OSError:
                pass
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_disable_switch_still_enters_the_body(self):
        prev = os.environ.get(build_lock.ENV_DISABLE)
        os.environ[build_lock.ENV_DISABLE] = "1"
        try:
            ran = False
            with build_lock.ubt_build_lock(Path("Q:/UE_test_off")) as outcome:
                ran = True
            self.assertTrue(ran)
            self.assertFalse(outcome.held)
            self.assertEqual(outcome.reason, "disabled")
        finally:
            if prev is None:
                os.environ.pop(build_lock.ENV_DISABLE, None)
            else:
                os.environ[build_lock.ENV_DISABLE] = prev

    def test_body_exceptions_propagate_and_release(self):
        ue = Path("Q:/UE_test_raise")
        with self.assertRaises(RuntimeError):
            with build_lock.ubt_build_lock(ue, timeout=0):
                raise RuntimeError("boom")
        # Released despite the exception — the next acquire succeeds.
        with build_lock.ubt_build_lock(ue, timeout=0) as o:
            self.assertTrue(o.held)


class TestCrossProcessExclusion(unittest.TestCase):
    """The lock must actually exclude ACROSS processes — that is its whole job,
    and an in-process test cannot show it."""

    def test_second_process_is_excluded_then_proceeds(self):
        ue = "Q:/UE_test_xproc"
        script = textwrap.dedent(f"""
            import sys, time
            sys.path.insert(0, r"{_VERIFY}")
            import build_lock
            from pathlib import Path
            with build_lock.ubt_build_lock(Path(r"{ue}"), timeout=0) as o:
                print("HELD" if o.held else "FREE", flush=True)
                time.sleep(3)
        """)
        proc = subprocess.Popen(
            [sys.executable, "-c", script],
            stdout=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
        )
        try:
            first = proc.stdout.readline().strip()
            if first != "HELD":
                self.skipTest(f"helper did not acquire (got {first!r})")
            t0 = time.monotonic()
            with build_lock.ubt_build_lock(Path(ue), timeout=0.5) as outcome:
                waited = time.monotonic() - t0
            # Excluded by the OTHER process...
            self.assertFalse(outcome.held)
            # ...but it waited, and then proceeded anyway.
            self.assertGreaterEqual(waited, 0.4)
            self.assertEqual(outcome.reason, "timeout")
        finally:
            proc.kill()
            proc.wait(10)

    def test_lock_dies_with_the_process(self):
        """A hard-killed run must not wedge the box — no stale-lock recovery
        step should ever be needed."""
        ue = "Q:/UE_test_death"
        script = textwrap.dedent(f"""
            import sys, time
            sys.path.insert(0, r"{_VERIFY}")
            import build_lock
            from pathlib import Path
            with build_lock.ubt_build_lock(Path(r"{ue}"), timeout=0) as o:
                print("HELD" if o.held else "FREE", flush=True)
                time.sleep(60)
        """)
        proc = subprocess.Popen(
            [sys.executable, "-c", script],
            stdout=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
        )
        try:
            if proc.stdout.readline().strip() != "HELD":
                self.skipTest("helper did not acquire")
            proc.kill()
            proc.wait(10)
            time.sleep(0.3)
            with build_lock.ubt_build_lock(Path(ue), timeout=2.0) as outcome:
                self.assertTrue(outcome.held, "lock survived its holder's death")
        finally:
            if proc.poll() is None:
                proc.kill()


class TestTimeoutResolution(unittest.TestCase):
    def setUp(self):
        self._prev = os.environ.get(build_lock.ENV_TIMEOUT)

    def tearDown(self):
        if self._prev is None:
            os.environ.pop(build_lock.ENV_TIMEOUT, None)
        else:
            os.environ[build_lock.ENV_TIMEOUT] = self._prev

    def test_default(self):
        os.environ.pop(build_lock.ENV_TIMEOUT, None)
        self.assertEqual(build_lock.resolve_timeout(), build_lock.DEFAULT_TIMEOUT_S)

    def test_garbage_falls_back_rather_than_raising(self):
        os.environ[build_lock.ENV_TIMEOUT] = "not-a-number"
        self.assertEqual(build_lock.resolve_timeout(), build_lock.DEFAULT_TIMEOUT_S)

    def test_negative_normalises_to_no_wait(self):
        os.environ[build_lock.ENV_TIMEOUT] = "-5"
        self.assertEqual(build_lock.resolve_timeout(), 0.0)


class TestNotesAreAdvisoryOnly(unittest.TestCase):
    def test_quiet_acquire_says_nothing(self):
        """No note when there was no contention — the L1 notes list is read by
        humans and a per-run 'lock ok' line would be noise."""
        self.assertIsNone(
            build_lock.BuildLockOutcome(True, 0.01, "acquired", None).note)

    def test_timeout_note_states_the_verdict_is_unchanged(self):
        note = build_lock.BuildLockOutcome(False, 900.0, "timeout", None).note
        self.assertIn("built anyway", note)
        self.assertIn("unchanged", note)


class TestWiredIntoL1(unittest.TestCase):
    """Source pins: the lock must wrap the build, and nothing may branch a
    verdict on it."""

    def test_l1_wraps_the_build_window(self):
        src = (_VERIFY / "layers" / "l1_build.py").read_text(encoding="utf-8")
        self.assertIn("ubt_build_lock(ue_root", src)
        i_lock = src.index("ubt_build_lock(ue_root")
        i_job = src.index("resource_job(memory_limit_mb=L1_MEM_MB")
        i_run = src.index("_run_one_target(")
        self.assertLess(i_lock, i_job)   # lock outside the job object
        self.assertLess(i_job, i_run)    # both outside the actual spawn

    def test_no_verdict_branches_on_the_lock(self):
        """`held` may be reported, never used to decide status/exit_code."""
        src = (_VERIFY / "layers" / "l1_build.py").read_text(encoding="utf-8")
        for bad in ("if _blk.held", "if not _blk.held", "_blk.held and",
                    "if outcome.held"):
            self.assertNotIn(bad, src)

    def test_primer_locks_the_slot_before_destroying_it(self):
        """`cb warm-prime --force` used to rmtree a slot a verify was compiling
        in, with no lock at all."""
        src = (_VERIFY / "build_warm_baseline.py").read_text(encoding="utf-8")
        i_acquire = src.index("_slot_lock.acquire()")
        i_rmtree = src.index("shutil.rmtree(slot_dir")
        self.assertLess(i_acquire, i_rmtree)


if __name__ == "__main__":
    unittest.main()


class TestAntiContaminationReset(unittest.TestCase):
    """The keep-list is the contract: ONLY the compiler cache survives a reset.

    Inspecting a real slot after a night of runs found 119 MB of
    `Intermediate/CachedAssetRegistry` and all of `Saved/` carrying from one
    task's grade into the next — and L2I grades by introspecting the asset
    registry. These tests exist so that cannot come back.
    """

    def setUp(self):
        import warm_cache
        self.wc = warm_cache
        self.slot = Path(tempfile.mkdtemp(prefix="cb-anticontam-"))
        self.build = self.slot / "build"
        for rel, body in [
            ("Source/Mod/A.cpp", "int a;"),
            ("Content/Tasks/keep.uasset", "asset"),
            ("Config/DefaultEngine.ini", "[x]"),
            ("Binaries/Win64/Editor.dll", "binary"),
            ("Intermediate/Build/obj.o", "object"),
            ("Intermediate/CachedAssetRegistry/reg.bin", "REGISTRY"),
            ("Intermediate/ShaderAutogen/s.ush", "shader"),
            ("Saved/Logs/run.log", "log"),
        ]:
            p = self.build / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body, encoding="utf-8")
        self.wc.make_snapshot(self.build, self.wc.snapshot_dir(self.slot))

    def tearDown(self):
        import shutil as _sh
        _sh.rmtree(self.slot, ignore_errors=True)

    def _slot(self):
        return self.wc.WarmSlot(
            slot_dir=self.slot, substrate_path=self.build,
            out_dir=self.slot / "out", writable_prefixes=("Source/Mod/",),
            _lock=self.wc.SlotLock(self.slot / "unused.lock"),
        )

    def test_registry_cache_does_not_survive_a_reset(self):
        """THE one that matters: a previous task's asset registry must not be
        visible to the next task's L2I."""
        reg = self.build / "Intermediate" / "CachedAssetRegistry" / "reg.bin"
        reg.write_text("CONTAMINATED BY TASK 1", encoding="utf-8")
        (self.build / "Intermediate" / "CachedAssetRegistry" / "extra.bin").write_text(
            "leftover", encoding="utf-8")
        self._slot().reset_to_pristine()
        self.assertEqual(reg.read_text(encoding="utf-8"), "REGISTRY")
        self.assertFalse(
            (self.build / "Intermediate" / "CachedAssetRegistry" / "extra.bin").exists(),
            "a file created by the previous verify survived the reset")

    def test_saved_does_not_survive_a_reset(self):
        stray = self.build / "Saved" / "CraftBench" / "shot_cp01.png"
        stray.parent.mkdir(parents=True, exist_ok=True)
        stray.write_bytes(b"previous run's screenshot")
        self._slot().reset_to_pristine()
        self.assertFalse(stray.exists(),
                         "a previous run's capture artifact survived into the next")

    def test_compiler_cache_DOES_survive(self):
        """The whole point of a warm slot — kept because it is a pure function
        of the source, which the fingerprint independently certifies."""
        obj = self.build / "Intermediate" / "Build" / "obj.o"
        obj.write_text("freshly compiled", encoding="utf-8")
        self._slot().reset_to_pristine()
        self.assertTrue(obj.exists())
        self.assertEqual(obj.read_text(encoding="utf-8"), "freshly compiled")
        self.assertTrue((self.build / "Binaries" / "Win64" / "Editor.dll").exists())

    def test_unanticipated_new_directory_is_removed(self):
        """A path no one listed must be reset by DEFAULT. This is the property
        that makes the guarantee total rather than a list someone maintains."""
        novel = self.build / "SomeFutureUEDir" / "state.bin"
        novel.parent.mkdir(parents=True, exist_ok=True)
        novel.write_text("invented by a future engine", encoding="utf-8")
        self._slot().reset_to_pristine()
        self.assertFalse(novel.exists())

    def test_agent_edit_to_source_is_reverted(self):
        src = self.build / "Source" / "Mod" / "A.cpp"
        src.write_text("int hacked;", encoding="utf-8")
        self._slot().reset_to_pristine()
        self.assertEqual(src.read_text(encoding="utf-8"), "int a;")

    def test_schema_bumped_so_v3_slots_cannot_be_reset_by_v4(self):
        """A v3 snapshot holds only the writable prefixes; the v4 reset would
        delete Source/, Content/ and the .uproject it never captured."""
        self.assertGreaterEqual(self.wc.SCHEMA, 4)
        ok, why = self.wc.is_valid(self.slot, substrate_tree_sha="x", ue_version="5.8",
                                  ue_root=None)
        self.assertFalse(ok)


class TestCompileInputClassification(unittest.TestCase):
    """A compile input is decided by LOCATION, never by extension.

    The original rule was an extension allowlist, and it failed unsafely: an
    agent may submit ANY file, so a compile input whose extension was not listed
    (`.ixx`, `.mm`, anything a future UE adds) hashed as absent, the mtime bump
    was skipped, and UBT — told nothing had changed — reported "Target is up to
    date" and linked a binary without the submitted code. A false PASS produced
    by a guess about file naming.
    """

    def setUp(self):
        import warm_cache
        self.wc = warm_cache

    def test_any_file_under_Source_is_a_compile_input(self):
        for rel in ("Source/Mod/A.cpp", "Source/Mod/A.ixx", "Source/Mod/A.mm",
                    "Source/Mod/Mod.Build.cs", "Source/Mod/NOTES",
                    "Plugins/Foo/Source/Bar.cpp"):
            self.assertTrue(self.wc._is_compile_input(rel), rel)

    def test_content_is_never_a_compile_input(self):
        """This is what preserves the win: a discrimination row's legs differ
        only in .uasset bytes and must stay on the fast path."""
        for rel in ("Content/Tasks/x/a.uasset", "Content/Maps/t/L_X.umap",
                    "Content/Tasks/x/weird.newformat"):
            self.assertFalse(self.wc._is_compile_input(rel), rel)

    def test_source_must_be_a_directory_component_not_a_substring(self):
        self.assertFalse(self.wc._is_compile_input("Content/SourceArt/tex.png"))

    def test_a_file_literally_named_Source_is_not_a_directory(self):
        self.assertFalse(self.wc._is_compile_input("Content/Tasks/Source"))

    def test_config_is_left_to_UBT(self):
        """UBT invalidates its own makefile on an ini change and re-decides —
        observed live. Pre-empting that call is not ours to make."""
        self.assertFalse(self.wc._is_compile_input("Config/DefaultEngine.ini"))



class TestPerFileBump(unittest.TestCase):
    """Bump only what CHANGED, not the whole tree.

    The whole-tree bump was correct but far too coarse: on a t0 eval the agent
    changed TWO files and UBT recompiled 28 actions, because the harness had
    claimed all 53 were new. The warm grade came in at 1.35x where an unchanged
    tree gets 26x.

    We only claim WHICH FILES CHANGED. UBT still owns what must therefore be
    rebuilt -- making a changed header look new is enough, its dependency graph
    cascades to every dependent.
    """

    def setUp(self):
        import warm_cache
        self.wc = warm_cache
        self.root = Path(tempfile.mkdtemp(prefix="cb-perfile-"))
        (self.root / "Source" / "Mod").mkdir(parents=True)
        (self.root / "Content" / "Tasks").mkdir(parents=True)
        for n, body in (("A.cpp", "a"), ("B.cpp", "b"), ("C.h", "c")):
            (self.root / "Source" / "Mod" / n).write_text(body, encoding="utf-8")
        (self.root / "Content" / "Tasks" / "x.uasset").write_bytes(b"asset")
        self.prefixes = ("Source/Mod/", "Content/Tasks/")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.root, ignore_errors=True)

    def _hashes(self):
        return self.wc.compile_input_hashes(self.root, self.prefixes)

    def test_hashes_cover_source_only(self):
        h = self._hashes()
        self.assertEqual(set(h), {"Source/Mod/A.cpp", "Source/Mod/B.cpp",
                                  "Source/Mod/C.h"})

    def test_only_the_edited_file_is_reported_changed(self):
        built = self._hashes()
        (self.root / "Source" / "Mod" / "B.cpp").write_text("EDITED",
                                                            encoding="utf-8")
        self.assertEqual(
            self.wc.changed_compile_inputs(self._hashes(), built),
            ["Source/Mod/B.cpp"])

    def test_nothing_changed_means_nothing_to_bump(self):
        built = self._hashes()
        self.assertEqual(self.wc.changed_compile_inputs(self._hashes(), built), [])

    def test_an_asset_edit_changes_nothing(self):
        """The property that preserves the 26x on discrimination legs, whose
        variants differ ONLY in .uasset bytes."""
        built = self._hashes()
        (self.root / "Content" / "Tasks" / "x.uasset").write_bytes(b"different")
        self.assertEqual(self.wc.changed_compile_inputs(self._hashes(), built), [])

    def test_a_new_source_file_counts_as_changed(self):
        built = self._hashes()
        (self.root / "Source" / "Mod" / "New.cpp").write_text("n", encoding="utf-8")
        self.assertIn("Source/Mod/New.cpp",
                      self.wc.changed_compile_inputs(self._hashes(), built))

    def test_unknown_provenance_bumps_EVERYTHING(self):
        """A slot primed before per-file hashes, or a build that never finished,
        cannot attribute its objects -- so every file must look new. The old
        whole-tree behaviour, and the safe direction."""
        cur = self._hashes()
        self.assertEqual(self.wc.changed_compile_inputs(cur, None), sorted(cur))
        self.assertEqual(self.wc.changed_compile_inputs(cur, {}), sorted(cur))

    def test_state_round_trips_per_file_hashes(self):
        slot = self.root / "slot"
        h = self._hashes()
        self.wc.write_binaries_state(slot, "sha", compile_fingerprint="fp",
                                     compile_files=h)
        self.assertEqual(self.wc.read_compile_files(slot), h)

    def test_incomplete_build_has_no_per_file_provenance(self):
        slot = self.root / "slot"
        self.wc.write_binaries_state(slot, "sha", compile_fingerprint=None)
        self.assertIsNone(self.wc.read_compile_files(slot))

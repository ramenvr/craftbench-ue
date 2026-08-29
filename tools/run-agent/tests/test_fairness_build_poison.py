"""Issue 11: an agent recompile while fixtures are stubbed must not brick the box.

The defect, measured on the bench host 2026-08-22: `_STUB_BODY` is a bare
comment, which is valid C++, so a mid-drive `recompile_unreal_project` baked
the stubs into `UnrealEditor-CraftBenchTests.dll` (49,152 bytes against
837,632 for a real build). The engine then loads the verifier module, cannot
initialise it, and calls EngineExit -- so NO editor starts, on either
substrate, for any lane. Nine consecutive cells died at ~2 min each while the
stack log blamed "crash on startup", and CraftBenchTemplate carried the same
poisoned bytes for three days unnoticed.

The SOURCES restore correctly. Only the build PRODUCTS are poisoned, which is why
nothing that inspects the source tree can see it.

What these tests pin, one clause each:

  * the rewrite is DETECTED and the products invalidated (including
    Intermediate/Build -- deleting the DLL alone was measured insufficient,
    because UHT's cached parse of the base class also dated from stub time);
  * an UNTOUCHED build is left ALONE. This is the expensive half to get wrong:
    invalidating unconditionally forces a full editor rebuild on every cell,
    which costs more wall clock than the bug does;
  * a failed invalidation leaves the marker, and the marker makes the project
    refuse to drive -- the crash path, where no restore ran at all;
  * the baseline survives a persist/load round trip, because the crash path is
    the one that matters and it reads the state back off disk;
  * a missing baseline SKIPS the check rather than assuming a rewrite. An absent
    baseline is not evidence.

No editor, no UE, no build, no tokens.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fairness  # noqa: E402
from fairness import (  # noqa: E402
    BUILD_POISON_MARKER,
    FairnessState,
    build_poison_marker_path,
    module_build_fingerprint,
    stage_fairness_hide,
    stage_fairness_restore,
    verifier_build_suspect,
)

_DLL_REL = "Binaries/Win64/UnrealEditor-CraftBenchTests.dll"
_UHT_REL = "Intermediate/Build/Win64/x64/Editor/Inc/CraftBenchTests/Gen.h"


def _project(tmp: Path, *, dll_bytes: bytes = b"REAL-BUILD" * 200) -> Path:
    """A substrate with one fixture source, one module DLL and a UHT cache."""
    proj = tmp / "UE-projects" / "ThirdPerson"
    fixtures = proj / "Source" / "CraftBenchTests"
    fixtures.mkdir(parents=True)
    (fixtures / "CraftBenchFunctionalTest.h").write_text(
        "class ACraftBenchFunctionalTest { void Secret(); };\n", encoding="utf-8")
    (fixtures / "CraftBenchFunctionalTest.cpp").write_text(
        "void ACraftBenchFunctionalTest::Secret() { /* the answer */ }\n",
        encoding="utf-8")
    dll = proj / _DLL_REL
    dll.parent.mkdir(parents=True)
    dll.write_bytes(dll_bytes)
    # The manifest a real build always writes beside its DLLs. Without it the
    # engine cannot find the game module at all -- it raises a modal dialog and,
    # headless, exits a few seconds in (measured 2026-08-26, every aura-mcp cell
    # on gp-glide-stamina-cpp). So a fixture with a DLL and no manifest models a
    # state that cannot exist on a fit project, and "a fit project is not
    # refused" asserted against it was asserting the wrong thing.
    (dll.parent / "UnrealEditor.modules").write_text(
        json.dumps({"BuildId": "test", "Modules": {"CraftBenchTests": dll.name}}),
        encoding="utf-8")
    uht = proj / _UHT_REL
    uht.parent.mkdir(parents=True)
    uht.write_text("// UHT cached parse\n", encoding="utf-8")
    return proj


class TestDetectAndInvalidate(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.proj = _project(self.tmp)
        self.run_dir = self.tmp / "run"
        self.run_dir.mkdir()

    def test_a_rebuild_during_the_hide_is_detected_and_invalidated(self):
        state = stage_fairness_hide(self.proj, self.run_dir)
        self.assertTrue(state.module_build_fp, "no baseline was captured")
        # The agent recompiles: the DLL is REPLACED with a stub-sized one.
        (self.proj / _DLL_REL).write_bytes(b"STUBBED")
        stage_fairness_restore(state, self.proj)
        self.assertFalse((self.proj / _DLL_REL).exists(),
                         "the poisoned DLL survived the restore")
        self.assertFalse((self.proj / "Intermediate" / "Build").exists(),
                         "Intermediate/Build survived — UHT's cached parse of "
                         "the base class would fail the next build")

    def test_the_SOURCES_still_come_back(self):
        # The invalidation must not be bought with a worse regression.
        before = (self.proj / "Source/CraftBenchTests/"
                             "CraftBenchFunctionalTest.cpp").read_text(
            encoding="utf-8")
        state = stage_fairness_hide(self.proj, self.run_dir)
        stubbed = (self.proj / "Source/CraftBenchTests/"
                              "CraftBenchFunctionalTest.cpp").read_text(
            encoding="utf-8")
        self.assertNotIn("the answer", stubbed)
        (self.proj / _DLL_REL).write_bytes(b"STUBBED")
        stage_fairness_restore(state, self.proj)
        after = (self.proj / "Source/CraftBenchTests/"
                            "CraftBenchFunctionalTest.cpp").read_text(
            encoding="utf-8")
        self.assertEqual(before, after)

    def test_an_UNTOUCHED_build_is_left_alone(self):
        # The expensive half. Invalidating unconditionally would force a full
        # editor rebuild on every cell.
        state = stage_fairness_hide(self.proj, self.run_dir)
        stage_fairness_restore(state, self.proj)
        self.assertTrue((self.proj / _DLL_REL).exists(),
                        "a clean run's build products were destroyed")
        self.assertTrue((self.proj / _UHT_REL).exists())

    def test_a_missing_baseline_skips_the_check_instead_of_assuming_a_rewrite(self):
        state = FairnessState(backup_root=self.run_dir / "fairness_backup")
        state.backup_root.mkdir(parents=True)
        self.assertIsNone(state.module_build_fp)
        stage_fairness_restore(state, self.proj)
        self.assertTrue((self.proj / _DLL_REL).exists(),
                        "an absent baseline was treated as evidence of a rewrite")

    def test_a_never_built_checkout_that_gets_BUILT_is_detected(self):
        """The false-NEGATIVE twin of the test below, and the state this fix's
        own remediation creates: _invalidate_module_build DELETES the artifacts,
        so the very next cell baselines as "". A truthiness guard would skip the
        check there — disabling detection exactly one cell after an agent proved
        it rebuilds mid-drive.
        """
        proj = self.tmp / "bare2"
        (proj / "Source" / "CraftBenchTests").mkdir(parents=True)
        (proj / "Source/CraftBenchTests/X.cpp").write_text(
            "void f(){}", encoding="utf-8")
        rd = self.tmp / "run3"
        rd.mkdir()
        state = stage_fairness_hide(proj, rd)
        self.assertEqual(state.module_build_fp, "",
                         "a project with no artifacts must baseline as empty")
        # The agent recompiles while the fixtures are stubbed, from nothing.
        dll = proj / _DLL_REL
        dll.parent.mkdir(parents=True, exist_ok=True)
        dll.write_bytes(b"STUBBED")
        stage_fairness_restore(state, proj)
        self.assertFalse(dll.exists(),
                         "a build that appeared DURING the hide was not "
                         "invalidated: an empty baseline disabled the check")

    def test_a_never_built_checkout_does_not_false_positive(self):
        proj = self.tmp / "bare"
        (proj / "Source" / "CraftBenchTests").mkdir(parents=True)
        (proj / "Source/CraftBenchTests/X.cpp").write_text("void f(){}\n",
                                                           encoding="utf-8")
        self.assertEqual(module_build_fingerprint(proj), "")
        rd = self.tmp / "run2"
        rd.mkdir()
        state = stage_fairness_hide(proj, rd)
        stage_fairness_restore(state, proj)   # must not raise
        self.assertIsNone(verifier_build_suspect(proj))


class TestTheMarkerAndTheRefusal(unittest.TestCase):
    """The crash path: no restore ran, so only the marker can stop the next cell."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.proj = _project(self.tmp)

    def test_a_fit_project_is_not_refused(self):
        self.assertIsNone(verifier_build_suspect(self.proj))

    def test_the_marker_refuses_the_project_and_says_what_to_delete(self):
        build_poison_marker_path(self.proj).write_text(
            json.dumps({"reason": "dll: WinError 32"}), encoding="utf-8")
        why = verifier_build_suspect(self.proj)
        self.assertIsNotNone(why)
        self.assertIn(BUILD_POISON_MARKER, why)
        self.assertIn("Intermediate/Build", why.replace("\\", "/"))
        self.assertIn("WinError 32", why)      # the specific cause survives

    def test_a_corrupt_marker_still_refuses(self):
        # Fail CLOSED: an unreadable marker is not permission to drive.
        build_poison_marker_path(self.proj).write_text("{not json",
                                                       encoding="utf-8")
        self.assertIsNotNone(verifier_build_suspect(self.proj))

    def test_a_failed_invalidation_writes_the_marker(self):
        run_dir = self.tmp / "run"
        run_dir.mkdir()
        state = stage_fairness_hide(self.proj, run_dir)
        (self.proj / _DLL_REL).write_bytes(b"STUBBED")

        # Simulate an editor still holding a handle: invalidation reports failure.
        real = fairness._invalidate_module_build
        try:
            fairness._invalidate_module_build = (
                lambda pd, log=None: (False, ["dll: WinError 32"]))
            stage_fairness_restore(state, self.proj)
        finally:
            fairness._invalidate_module_build = real

        self.assertTrue(build_poison_marker_path(self.proj).is_file(),
                        "a failed invalidation left no marker, so the next cell "
                        "would inherit the poisoned build silently")
        self.assertIsNotNone(verifier_build_suspect(self.proj))


class TestTheBaselineSurvivesACrash(unittest.TestCase):
    def test_persist_then_load_round_trips_the_baseline(self):
        tmp = Path(tempfile.mkdtemp())
        proj = _project(tmp)
        run_dir = tmp / "run"
        run_dir.mkdir()
        state = stage_fairness_hide(proj, run_dir)
        self.assertTrue(state.module_build_fp)

        # What crash recovery does: rebuild the state from the leftover backup.
        loaded = fairness.load_fairness_state(state.backup_root)
        self.assertEqual(loaded.module_build_fp, state.module_build_fp,
                         "the baseline did not survive the persist/load round "
                         "trip, so the CRASH path — the one that poisoned the "
                         "box — cannot detect the rewrite")


class TestSymbolParkIsNotMistakenForARebuild(unittest.TestCase):
    """Issue 12's park must not trip issue 11's rebuild detector.

    This is the bug the first cut of the park actually had. The .pdb was inside
    the fingerprint globs, so the hide-time baseline (taken with the .pdb parked)
    and the restore-time reading (taken with it back) differed BY THE PARK, and
    every clean run would have read as "the agent rebuilt the module" and paid a
    full editor rebuild — minutes per cell, for nothing. Caught before shipping;
    pinned here so the coupling cannot come back.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.proj = _project(self.tmp)
        self.run_dir = self.tmp / "run"
        self.run_dir.mkdir()

    def test_the_pdb_is_parked_during_the_agent_phase(self):
        pdb = self.proj / "Binaries/Win64/UnrealEditor-CraftBenchTests.pdb"
        pdb.parent.mkdir(parents=True, exist_ok=True)
        pdb.write_bytes(b"SOURCE PATHS AND TOLERANCES" * 50)
        state = stage_fairness_hide(self.proj, self.run_dir)
        self.assertFalse(pdb.exists(), "the .pdb was still readable by the agent")
        self.assertTrue(state.parked_symbols, "nothing recorded as parked")

    def test_it_comes_back_on_restore(self):
        pdb = self.proj / "Binaries/Win64/UnrealEditor-CraftBenchTests.pdb"
        pdb.parent.mkdir(parents=True, exist_ok=True)
        before = b"SOURCE PATHS AND TOLERANCES" * 50
        pdb.write_bytes(before)
        state = stage_fairness_hide(self.proj, self.run_dir)
        stage_fairness_restore(state, self.proj)
        self.assertTrue(pdb.exists())
        self.assertEqual(before, pdb.read_bytes())

    def test_a_CLEAN_run_does_NOT_invalidate_the_build(self):
        # THE regression this class exists for. Park, restore, and the DLL and
        # Intermediate/Build must both survive: nothing was rebuilt.
        pdb = self.proj / "Binaries/Win64/UnrealEditor-CraftBenchTests.pdb"
        pdb.parent.mkdir(parents=True, exist_ok=True)
        pdb.write_bytes(b"symbols")
        state = stage_fairness_hide(self.proj, self.run_dir)
        stage_fairness_restore(state, self.proj)
        self.assertTrue((self.proj / _DLL_REL).exists(),
                        "a clean run destroyed the build products — the park was "
                        "read as a rebuild")
        self.assertTrue((self.proj / "Intermediate" / "Build").exists())

    def test_the_fingerprint_ignores_the_pdb_entirely(self):
        # Structural, not behavioural: the decoupling is the property, so assert
        # it directly rather than only through its consequence.
        pdb = self.proj / "Binaries/Win64/UnrealEditor-CraftBenchTests.pdb"
        pdb.parent.mkdir(parents=True, exist_ok=True)
        pdb.write_bytes(b"a")
        fp_with = module_build_fingerprint(self.proj)
        pdb.unlink()
        fp_without = module_build_fingerprint(self.proj)
        self.assertEqual(fp_with, fp_without)

    def test_a_REBUILD_is_still_caught_with_the_pdb_in_play(self):
        # The park must not blunt the detector either.
        pdb = self.proj / "Binaries/Win64/UnrealEditor-CraftBenchTests.pdb"
        pdb.parent.mkdir(parents=True, exist_ok=True)
        pdb.write_bytes(b"symbols")
        state = stage_fairness_hide(self.proj, self.run_dir)
        (self.proj / _DLL_REL).write_bytes(b"STUBBED")     # the agent recompiled
        stage_fairness_restore(state, self.proj)
        self.assertFalse((self.proj / _DLL_REL).exists(),
                         "the poisoned DLL survived")

    def test_a_project_with_no_pdb_parks_nothing_and_still_works(self):
        state = stage_fairness_hide(self.proj, self.run_dir)
        self.assertEqual([], state.parked_symbols)
        stage_fairness_restore(state, self.proj)   # must not raise

    def test_the_parked_list_round_trips_through_the_state_file(self):
        # The crash path again: a run killed mid-drive must be able to put the
        # .pdb back from the persisted recipe.
        pdb = self.proj / "Binaries/Win64/UnrealEditor-CraftBenchTests.pdb"
        pdb.parent.mkdir(parents=True, exist_ok=True)
        pdb.write_bytes(b"symbols")
        state = stage_fairness_hide(self.proj, self.run_dir)
        loaded = fairness.load_fairness_state(state.backup_root)
        self.assertEqual(state.parked_symbols, loaded.parked_symbols)
        stage_fairness_restore(loaded, self.proj)
        self.assertTrue(pdb.exists())


if __name__ == "__main__":
    unittest.main()

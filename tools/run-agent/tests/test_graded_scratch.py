"""Unit tests for graded_scratch — the disposable single-task drive project.

Fully offline: a fake substrate tree + an injected copy_substrate_fn stand in
for the git-archive materialization. Verifies the composition invariants the
drive gate relies on: only the active task's files exist, the tests module
carries ONLY base classes (no fixtures — no answer key in the agent-visible
tree), AGENT_WRITABLE.json is absent, recomposition resets extras (the crash
story: nothing to heal), and verify_staged catches every refuse-to-drive
condition.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aura_rig import graded_scratch  # noqa: E402


def _fake_substrate(root: Path) -> Path:
    sub = root / "UE-projects" / "CraftBenchTemplate"
    files = {
        "CraftBenchTemplate.uproject": "{}",
        # asset_writable armed like the real manifest — every existing
        # verify_staged==[] assertion below co-verifies the shared-asset-dir
        # police never false-positives on a clean compose.
        "AGENT_WRITABLE.json": json.dumps({
            "writable": ["Source/CraftBenchTemplate/", "Content/Tasks/"],
            "asset_writable": ["Content/Tasks/", "Content/Blueprints/",
                               "Content/Abilities/",
                               "Content/Generated_Materials/",
                               "Content/Generated_Audio/"],
        }),
        # base infra (untagged) + one flat foreign scaffold + active foldered
        "Source/CraftBenchTemplate/CraftBenchCharacter.h": "// shared infra",
        "Source/CraftBenchTemplate/SpawnerActor.h": "// for task gp-spawner-population.",
        "Source/CraftBenchTemplate/SpawnerActor.cpp": "// for task gp-spawner-population.",
        "Source/CraftBenchTemplate/Tasks/t0-x/T0Actor.h": "// for task t0-x.",
        # tests module: base allowlist + a flat fixture + a foldered fixture
        "Source/CraftBenchTests/CraftBenchTests.Build.cs": "// module",
        "Source/CraftBenchTests/CraftBenchFunctionalTest.cpp": "// base class",
        "Source/CraftBenchTests/GasLaunchFunctionalTest.cpp": "// flat fixture",
        "Source/CraftBenchTests/Tasks/t0-x/T0Fixture.cpp": "// for task t0-x.",
        # content: per-task dirs + flat map + engine dir
        "Content/Maps/t0-x/L_T0.umap": "bin",
        "Content/Maps/gp-y/L_Y.umap": "bin",
        "Content/Maps/L_Flat.umap": "bin",
        "Content/Maps/Developers/scratch.uasset": "bin",
        "Config/DefaultEngine.ini": "[/Script/EngineSettings.GameMapsSettings]\n",
    }
    for rel, body in files.items():
        p = sub / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    return sub


def _copy_fn_for(sub: Path):
    def _copy(src, dest):
        shutil.copytree(sub, dest)
    return _copy


class TestCompose(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cb-gsc-"))
        self.repo = self.tmp / "repo"
        self.sub = _fake_substrate(self.repo)
        self.scratch = self.tmp / "CraftBenchGraded"
        self.logs = []

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _compose(self, task="t0-x"):
        return graded_scratch.compose(
            task, repo=self.repo, scratch_dir=self.scratch,
            copy_substrate_fn=_copy_fn_for(self.sub), log=self.logs.append)

    def test_compose_stages_active_only(self):
        self._compose()
        s = self.scratch
        # Active task's files present; foreign gone (dirs + flat scaffolds).
        self.assertTrue((s / "Source/CraftBenchTemplate/Tasks/t0-x/T0Actor.h").exists())
        self.assertTrue((s / "Source/CraftBenchTemplate/CraftBenchCharacter.h").exists())
        self.assertFalse((s / "Source/CraftBenchTemplate/SpawnerActor.h").exists())
        self.assertFalse((s / "Content/Maps/gp-y").exists())
        self.assertTrue((s / "Content/Maps/t0-x/L_T0.umap").exists())
        self.assertTrue((s / "Content/Maps/L_Flat.umap").exists())        # flat kept
        self.assertTrue((s / "Content/Maps/Developers").is_dir())         # engine kept
        # Tests module: base only — NO fixtures at all (answer key never
        # reaches the agent-visible tree).
        self.assertTrue((s / "Source/CraftBenchTests/CraftBenchFunctionalTest.cpp").exists())
        self.assertFalse((s / "Source/CraftBenchTests/GasLaunchFunctionalTest.cpp").exists())
        self.assertFalse((s / "Source/CraftBenchTests/Tasks").exists())
        # No writable manifest in the agent-visible tree; marker written.
        self.assertFalse((s / "AGENT_WRITABLE.json").exists())
        self.assertEqual(graded_scratch.staged_marker(s)["task_id"], "t0-x")
        self.assertEqual(graded_scratch.verify_staged("t0-x", s), [])

    def test_recompose_resets_agent_edits_and_switches_task(self):
        self._compose()
        # Simulate a prior drive: agent created a file + edited a scaffold.
        junk = self.scratch / "Source/CraftBenchTemplate/AgentNew.cpp"
        junk.write_text("// agent leftovers", encoding="utf-8")
        (self.scratch / "Source/CraftBenchTemplate/Tasks/t0-x/T0Actor.h").write_text(
            "// EDITED", encoding="utf-8")
        # Recompose for a DIFFERENT task: extras deleted, tree exact.
        self._compose(task="gp-spawner-population")
        self.assertFalse(junk.exists())
        self.assertFalse(
            (self.scratch / "Source/CraftBenchTemplate/Tasks/t0-x").exists())
        self.assertTrue(
            (self.scratch / "Source/CraftBenchTemplate/SpawnerActor.h").exists())
        self.assertEqual(
            graded_scratch.verify_staged("gp-spawner-population", self.scratch), [])

    def test_build_state_survives_recompose(self):
        self._compose()
        binaries = self.scratch / "Binaries" / "Win64"
        binaries.mkdir(parents=True)
        (binaries / "UnrealEditor-CraftBenchTemplate.dll").write_bytes(b"\x00")
        self._compose(task="gp-spawner-population")
        self.assertTrue(
            (binaries / "UnrealEditor-CraftBenchTemplate.dll").exists(),
            "Binaries/ lives outside the staged trees and must persist")

    def test_verify_staged_catches_problems(self):
        self._compose()
        # Wrong task.
        self.assertTrue(graded_scratch.verify_staged("gp-other", self.scratch))
        # Foreign per-task dir survivor.
        (self.scratch / "Content/Maps/gp-z").mkdir(parents=True)
        probs = graded_scratch.verify_staged("t0-x", self.scratch)
        self.assertTrue(any("gp-z" in p for p in probs))
        shutil.rmtree(self.scratch / "Content/Maps/gp-z")
        # Fixture leak into the tests module.
        leak = self.scratch / "Source/CraftBenchTests/SneakyFixture.cpp"
        leak.write_text("// leaked", encoding="utf-8")
        probs = graded_scratch.verify_staged("t0-x", self.scratch)
        self.assertTrue(any("SneakyFixture" in p for p in probs))
        leak.unlink()
        # Manifest present.
        (self.scratch / "AGENT_WRITABLE.json").write_text("{}", encoding="utf-8")
        probs = graded_scratch.verify_staged("t0-x", self.scratch)
        self.assertTrue(any("AGENT_WRITABLE" in p for p in probs))

    def test_no_marker_refuses(self):
        self.assertTrue(graded_scratch.verify_staged("t0-x", self.scratch))

    def _compose_with_spec(self, spec_text, task="t0-x"):
        spec = self.tmp / "task.md"
        spec.write_text(spec_text, encoding="utf-8")
        return graded_scratch.compose(
            task, repo=self.repo, scratch_dir=self.scratch,
            task_spec_path=spec,
            copy_substrate_fn=_copy_fn_for(self.sub), log=self.logs.append)

    def test_spec_prunes_foreign_root_maps(self):
        # Extra flat maps: one the spec names, one foreign, one shared-infra.
        for rel in ("Content/Maps/L_Named.umap",
                    "Content/Maps/L_RenderProbe.umap"):
            (self.sub / rel).write_text("bin", encoding="utf-8")
        self._compose_with_spec(
            "## Verifier fixtures\n\n- L_Named :: AT0Fixture\n")
        s = self.scratch
        self.assertTrue((s / "Content/Maps/L_Named.umap").exists())
        self.assertTrue((s / "Content/Maps/L_RenderProbe.umap").exists())
        self.assertFalse((s / "Content/Maps/L_Flat.umap").exists())  # foreign
        self.assertTrue((s / "Content/Maps/t0-x/L_T0.umap").exists())
        marker = graded_scratch.staged_marker(s)
        self.assertEqual(marker["removed"]["root_maps"], 1)
        self.assertEqual(sorted(marker["root_maps_kept"]),
                         ["L_Named", "L_RenderProbe"])
        self.assertEqual(graded_scratch.verify_staged("t0-x", s), [])

    def test_verify_staged_catches_foreign_root_map(self):
        self._compose_with_spec("no maps named here\n")
        smuggled = self.scratch / "Content/Maps/L_Smuggled.umap"
        smuggled.parent.mkdir(parents=True, exist_ok=True)
        smuggled.write_text("bin", encoding="utf-8")
        probs = graded_scratch.verify_staged("t0-x", self.scratch)
        self.assertTrue(any("L_Smuggled" in p for p in probs))

    def test_no_spec_keeps_flat_maps_and_skips_the_gate(self):
        # Fail-safe: without a spec the compose keeps root maps (unchanged
        # legacy behavior) and the marker carries no keep-set to police.
        self._compose()
        self.assertTrue((self.scratch / "Content/Maps/L_Flat.umap").exists())
        self.assertNotIn("root_maps_kept", graded_scratch.staged_marker(self.scratch))
        self.assertEqual(graded_scratch.verify_staged("t0-x", self.scratch), [])


def _fake_second_substrate(root: Path) -> Path:
    """A SECOND substrate (the ThirdPersonTemplate shape): own .uproject +
    game module, same verifier-module name (CraftBenchTests)."""
    sub = root / "UE-projects" / "ThirdPersonTemplate"
    files = {
        "ThirdPersonTemplate.uproject": "{}",
        "AGENT_WRITABLE.json": "{\"writable\": [], \"game_module\": \"ThirdPersonTemplate\"}",
        "Source/ThirdPersonTemplate/TPCharacter.h": "// shared infra",
        "Source/CraftBenchTests/CraftBenchTests.Build.cs": "// module",
        "Source/CraftBenchTests/CraftBenchFunctionalTest.cpp": "// base class",
        "Content/Maps/tp-z/L_TP.umap": "bin",
        "Content/Maps/gp-y/L_Y.umap": "bin",
        "Config/DefaultEngine.ini": "[/Script/EngineSettings.GameMapsSettings]\n",
    }
    for rel, body in files.items():
        p = sub / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    return sub


def _write_spec(repo: Path, task_id: str, substrate: str = None) -> Path:
    """A minimal v2 front-matter task spec (folder-per-task layout).
    ``substrate=None`` omits the key (the spec-level default applies)."""
    lines = ["---", f"id: {task_id}"]
    if substrate:
        lines.append(f"substrate: {substrate}")
    lines += ["layers: [L1]", "---", "", "## Prompt given to the agent", "do it", ""]
    p = repo / "tasks" / "flagship" / task_id / "task.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


class TestMultiSubstrateCompose(unittest.TestCase):
    """compose() clones the ACTIVE task's substrate (spec front matter), the
    marker records it, the root .uproject is substrate-derived (stale
    other-substrate .uproject removed on recompose), and verify_staged flags
    a marker-vs-requested substrate mismatch + a stale .uproject."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cb-gsc-ms-"))
        self.repo = self.tmp / "repo"
        self.sub1 = _fake_substrate(self.repo)          # CraftBenchTemplate
        self.sub2 = _fake_second_substrate(self.repo)   # ThirdPersonTemplate
        self.spec1 = _write_spec(self.repo, "t0-x")     # default substrate
        self.spec2 = _write_spec(self.repo, "tp-z", "ThirdPersonTemplate")
        self.scratch = self.tmp / "CraftBenchGraded"
        self.logs = []

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _compose(self, task, spec):
        return graded_scratch.compose(
            task, repo=self.repo, scratch_dir=self.scratch, task_spec_path=spec,
            copy_substrate_fn=lambda src, dest: shutil.copytree(src, dest),
            log=self.logs.append)

    def test_substrate_switch_swaps_uproject_and_records_marker(self):
        # Task A on the default substrate.
        self._compose("t0-x", self.spec1)
        self.assertTrue((self.scratch / "CraftBenchTemplate.uproject").exists())
        marker = graded_scratch.staged_marker(self.scratch)
        self.assertEqual(marker["substrate"], "CraftBenchTemplate")
        self.assertEqual(marker["uproject"], "CraftBenchTemplate.uproject")
        self.assertEqual(
            graded_scratch.verify_staged("t0-x", self.scratch,
                                         substrate="CraftBenchTemplate"), [])
        # Task B on the SECOND substrate: recomposition is the reset.
        self._compose("tp-z", self.spec2)
        self.assertTrue((self.scratch / "ThirdPersonTemplate.uproject").exists())
        self.assertFalse(
            (self.scratch / "CraftBenchTemplate.uproject").exists(),
            "the stale other-substrate .uproject must be REMOVED on recompose")
        marker = graded_scratch.staged_marker(self.scratch)
        self.assertEqual(marker["substrate"], "ThirdPersonTemplate")
        self.assertEqual(marker["uproject"], "ThirdPersonTemplate.uproject")
        # Trees swapped wholesale (delete_extras mirror).
        self.assertTrue(
            (self.scratch / "Source/ThirdPersonTemplate/TPCharacter.h").exists())
        self.assertFalse(
            (self.scratch / "Source/CraftBenchTemplate").exists())
        self.assertEqual(
            graded_scratch.verify_staged("tp-z", self.scratch,
                                         substrate="ThirdPersonTemplate"), [])

    def test_verify_staged_flags_substrate_mismatch(self):
        self._compose("tp-z", self.spec2)
        probs = graded_scratch.verify_staged("tp-z", self.scratch,
                                             substrate="CraftBenchTemplate")
        self.assertTrue(any("substrate" in p for p in probs), probs)

    def test_verify_staged_flags_stale_uproject(self):
        self._compose("tp-z", self.spec2)
        (self.scratch / "CraftBenchTemplate.uproject").write_text(
            "{}", encoding="utf-8")
        probs = graded_scratch.verify_staged("tp-z", self.scratch,
                                             substrate="ThirdPersonTemplate")
        self.assertTrue(
            any("stale" in p and "CraftBenchTemplate.uproject" in p for p in probs),
            probs)

    def test_default_substrate_when_spec_path_none(self):
        self.assertEqual(graded_scratch.substrate_for(None), "CraftBenchTemplate")
        self.assertEqual(graded_scratch.substrate_for(self.spec1),
                         "CraftBenchTemplate")
        self.assertEqual(graded_scratch.substrate_for(self.spec2),
                         "ThirdPersonTemplate")

    def test_unknown_substrate_raises_listing_available(self):
        bad = _write_spec(self.repo, "gp-bad", "NoSuchTemplate")
        with self.assertRaises(ValueError) as cm:
            self._compose("gp-bad", bad)
        msg = str(cm.exception)
        self.assertIn("NoSuchTemplate", msg)
        self.assertIn("CraftBenchTemplate", msg)
        self.assertIn("ThirdPersonTemplate", msg)


class TestSharedAssetDirPolice(unittest.TestCase):
    """The Content/Blueprints contamination class (the motivating leak,
    reshaped for the scratch flow): an asset a prior run authored under a
    SHARED asset_writable dir (where Aura's bp/material/audio sub-agents
    default) must never ride a same-task repeat into the next run's
    snapshot/grade. compose records the policed dirs + the base's own legit
    assets in the marker; verify_staged flags leftovers; ensure_composed
    heals a matching-but-dirty scratch by recomposing (recompose IS the
    reset); a LOCKED leftover makes compose refuse loudly."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cb-gsc-shared-"))
        self.repo = self.tmp / "repo"
        self.sub = _fake_substrate(self.repo)
        # The base itself COMMITS one legit asset under a shared dir — the
        # kept-set must accept it while flagging anything else.
        committed = self.sub / "Content" / "Blueprints" / "BP_Committed.uasset"
        committed.parent.mkdir(parents=True, exist_ok=True)
        committed.write_text("bin", encoding="utf-8")
        self.scratch = self.tmp / "CraftBenchGraded"
        self.logs = []

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _compose(self, task="t0-x"):
        return graded_scratch.compose(
            task, repo=self.repo, scratch_dir=self.scratch,
            copy_substrate_fn=_copy_fn_for(self.sub), log=self.logs.append)

    def _ensure(self, task="t0-x", **kw):
        return graded_scratch.ensure_composed(
            task, repo=self.repo, scratch_dir=self.scratch,
            copy_substrate_fn=_copy_fn_for(self.sub), log=self.logs.append,
            **kw)

    def _locked(self, path):
        """Hold ``path`` open (no FILE_SHARE_DELETE — the live-editor case)
        with the retry backoff neutralized."""
        import contextlib
        from aura_rig import stack as _stack

        @contextlib.contextmanager
        def _cm():
            with open(path, "rb"), \
                    mock.patch.object(_stack.time, "sleep", lambda s: None):
                yield
        return _cm()

    def _leak(self, rel="Content/Blueprints/BP_Announcer.uasset"):
        p = self.scratch / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("stale asset authored by run N-1", encoding="utf-8")
        return p

    def _composes_logged(self):
        return sum("composed graded scratch" in ln for ln in self.logs)

    def test_marker_records_dirs_and_kept_assets(self):
        self._compose()
        marker = graded_scratch.staged_marker(self.scratch)
        self.assertEqual(marker["shared_asset_dirs"],
                         ["Content/Abilities", "Content/Blueprints",
                          "Content/Generated_Audio",
                          "Content/Generated_Materials"])
        self.assertEqual(marker["shared_assets_kept"],
                         ["Content/Blueprints/BP_Committed.uasset"])
        self.assertEqual(graded_scratch.verify_staged("t0-x", self.scratch), [])

    def test_leaked_asset_is_flagged(self):
        # The exact observed leak: Content/Blueprints/BP_Announcer.uasset.
        self._compose()
        self._leak()
        probs = graded_scratch.verify_staged("t0-x", self.scratch)
        self.assertTrue(
            any("survived staging" in p
                and "Content/Blueprints/BP_Announcer.uasset" in p
                for p in probs), probs)

    def test_umap_leak_is_flagged(self):
        self._compose()
        self._leak("Content/Abilities/L_Rogue.umap")
        probs = graded_scratch.verify_staged("t0-x", self.scratch)
        self.assertTrue(
            any("Content/Abilities/L_Rogue.umap" in p for p in probs), probs)

    def test_non_asset_files_are_ignored(self):
        # Only .uasset/.umap can ride into a graded submission (the manifest
        # allowance governs asset files only) — incidental editor files must
        # not false-positive the gate.
        self._compose()
        self._leak("Content/Blueprints/notes.txt")
        self.assertEqual(graded_scratch.verify_staged("t0-x", self.scratch), [])

    def test_active_task_content_tasks_asset_is_clean(self):
        # Content/Tasks/<active-id>/ is per-task territory (its own gate), not
        # a shared dir — a convention-correct deliverable never trips this.
        self._compose()
        p = self.scratch / "Content" / "Tasks" / "t0-x" / "WBP_Widget.uasset"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("legit in-progress deliverable", encoding="utf-8")
        self.assertEqual(graded_scratch.verify_staged("t0-x", self.scratch), [])

    def test_recompose_wipes_the_leak(self):
        self._compose()
        leak = self._leak()
        self._compose()  # recomposition IS the reset
        self.assertFalse(leak.exists())
        self.assertTrue(
            (self.scratch / "Content/Blueprints/BP_Committed.uasset").exists(),
            "the base's own committed asset must survive the reset")
        self.assertEqual(graded_scratch.verify_staged("t0-x", self.scratch), [])

    def test_ensure_composed_heals_a_dirty_same_task_repeat(self):
        # THE closed window: same-task repeat used to skip the recompose on a
        # marker match, riding the stale asset into the snapshot and grade.
        self._compose()
        leak = self._leak()
        n = self._composes_logged()
        problems = self._ensure()
        self.assertEqual(problems, [])
        self.assertFalse(leak.exists(), "the heal recompose must wipe the leak")
        self.assertTrue(any("DIRTY on a same-task repeat" in ln
                            for ln in self.logs), self.logs)
        self.assertEqual(self._composes_logged(), n + 1)

    def test_ensure_composed_skips_recompose_when_clean(self):
        # The marker-match fast path survives for CLEAN same-task repeats
        # (the live editor may hold Content files open).
        self._compose()
        n = self._composes_logged()
        self.assertEqual(self._ensure(), [])
        self.assertEqual(self._composes_logged(), n)

    def test_ensure_composed_recomposes_on_task_switch(self):
        self._compose()
        self._leak()
        problems = self._ensure("gp-spawner-population")
        self.assertEqual(problems, [])
        marker = graded_scratch.staged_marker(self.scratch)
        self.assertEqual(marker["task_id"], "gp-spawner-population")
        self.assertFalse(
            (self.scratch / "Content/Blueprints/BP_Announcer.uasset").exists())

    @unittest.skipUnless(sys.platform == "win32",
                         "POSIX allows unlinking an open file")
    def test_compose_refuses_when_a_locked_leftover_defeats_the_reset(self):
        # A live editor's handle on the leftover defeats delete_extras — the
        # old sweep swallowed that silently and the contaminated scratch
        # graded. compose must now refuse (pre-spend), naming the survivor.
        self._compose()
        leak = self._leak()
        with self._locked(leak):
            with self.assertRaises(OSError) as cm:
                self._compose()
        msg = str(cm.exception)
        self.assertIn("survived delete_extras", msg)
        self.assertIn("BP_Announcer.uasset", msg)

    def test_manifest_without_asset_writable_disarms_the_gate(self):
        # Fail-safe (the root_maps_kept pattern): a substrate manifest with no
        # asset_writable arms nothing — pre-manifest fixtures keep the old
        # behavior instead of refusing to compose.
        (self.sub / "AGENT_WRITABLE.json").write_text(
            '{"writable": []}', encoding="utf-8")
        self._compose()
        self.assertNotIn("shared_asset_dirs",
                         graded_scratch.staged_marker(self.scratch))
        self._leak()
        self.assertEqual(graded_scratch.verify_staged("t0-x", self.scratch), [])

    def test_corrupt_manifest_fails_open_but_warns(self):
        (self.sub / "AGENT_WRITABLE.json").write_text(
            "{not json", encoding="utf-8")
        self._compose()
        self.assertNotIn("shared_asset_dirs",
                         graded_scratch.staged_marker(self.scratch))
        self.assertTrue(any("not valid JSON" in ln for ln in self.logs),
                        self.logs)

    def test_pre_upgrade_marker_is_a_mismatch(self):
        # A marker written by PRE-feature code (no schema key) must NOT
        # grandfather the leak through: ensure_composed treats it as a
        # mismatch, recomposes once, and the upgraded marker arms the gate.
        self._compose()
        marker = graded_scratch.staged_marker(self.scratch)
        for key in ("schema", "shared_asset_dirs", "shared_assets_kept"):
            marker.pop(key, None)
        (self.scratch / ".cb-staged").write_text(
            json.dumps(marker), encoding="utf-8")
        leak = self._leak()
        self.assertEqual(self._ensure(), [])
        self.assertFalse(leak.exists(),
                         "the schema-mismatch recompose must wipe the leak")
        self.assertEqual(
            graded_scratch.staged_marker(self.scratch).get("schema"),
            graded_scratch._MARKER_SCHEMA)

    @unittest.skipUnless(sys.platform == "win32",
                         "POSIX allows unlinking an open file")
    def test_failed_compose_leaves_no_marker(self):
        # The old marker is invalidated BEFORE the first mutation, so an
        # aborted compose can never leave a matching marker beside a
        # half-reset tree for ensure_composed to fast-path over.
        self._compose()
        leak = self._leak()
        with self._locked(leak):
            with self.assertRaises(OSError):
                self._compose()
        self.assertIsNone(graded_scratch.staged_marker(self.scratch))

    def test_compose_clears_the_aura_sandbox_store(self):
        # The sandbox-FS COW store is RUN state living under build state:
        # a leftover store would be Accept-all'd into the NEXT run's Content
        # post-gate. compose clears it; the rest of Intermediate/ survives.
        self._compose()
        store = (self.scratch / "Intermediate" / "Sandboxes" / "AuraSandbox"
                 / "Sandbox" / "Game" / "Blueprints")
        store.mkdir(parents=True)
        (store / "BP_Smuggled.uasset").write_text("cow", encoding="utf-8")
        build_state = self.scratch / "Intermediate" / "Build" / "x.obj"
        build_state.parent.mkdir(parents=True)
        build_state.write_text("obj", encoding="utf-8")
        self._compose()
        self.assertFalse((self.scratch / "Intermediate" / "Sandboxes").exists())
        self.assertTrue(build_state.exists(),
                        "build state outside the store must persist")

    def test_on_heal_fires_only_on_the_heal_path(self):
        calls = []
        self._compose()
        self._ensure(on_heal=calls.append)
        self.assertEqual(calls, [], "clean match must not invoke on_heal")
        self._leak()
        self._ensure(on_heal=calls.append)
        self.assertEqual(len(calls), 1)
        self.assertTrue(any("BP_Announcer" in p for p in calls[0]), calls)


if __name__ == "__main__":
    unittest.main()

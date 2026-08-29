"""Cross-rep contamination defenses — the 2026-08-07 false-FAIL fix.

THE INCIDENT (bench-20260807-015524, both reps opus-5 on the shared scratch):
rep 1 (``gp-glide-stamina-cpp``) authored
``Content/Tasks/gp-glide-stamina-bp/GA_Glide.uasset`` and then died
EDITOR-GONE with an EMPTY deliverable of its own; rep 2 — a DIFFERENT task
(``gp-poison-dot-stack-cpp``) — swept that orphan into its submission, UE
refused to compile it in the poison substrate, and the automation test
returned Result={Fail}. Poison's own behavior was byte-identical to the
committed reference PASS. A harness leftover was charged to a model.

Two layers are tested here, both offline on temp trees:

  L1  graded_scratch.reset_agent_writable — a PRE-DRIVE reset that runs
      however the previous rep ended, plus the provenance fact it records.
  L2  aura_rig.task_scope — the task-scoped sweep rule (what may be excluded
      from a submission, and, just as load-bearing, what may NOT), and the
      "foreign asset compile errors present" note on the grade side.

The end-to-end replay of the incident (a drive that writes a foreign asset,
run through the whole graded route) lived here until the 2026-08-28 public
release: it drove ``run_graded_product_scratch``, which is aura-product-only
machinery, and went out with that lane. The two layers above are what the
three shipped arms (claude-p / aura-mcp / unreal-mcp) actually rely on, and
they are still covered offline.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aura_rig import graded_scratch, task_scope, tasks  # noqa: E402


_MANIFEST = {
    "substrate": "ThirdPerson",
    "game_module": "ThirdPerson",
    "writable": ["Source/ThirdPerson/", "Content/Tasks/"],
    "asset_writable": ["Content/Tasks/", "Content/Blueprints/",
                       "Content/__ExternalActors__/Tasks/"],
    "deny": ["Source/CraftBenchTests/", "Content/Maps/", "Plugins/"],
}

# The incident's two ids, verbatim — the fixtures are the real shapes.
GRADED = "cpp/gp-poison-dot-stack-cpp"
GRADED_BARE = "gp-poison-dot-stack-cpp"
FOREIGN = "gp-glide-stamina-bp"
FOREIGN_ASSET = "Content/Tasks/gp-glide-stamina-bp/GA_Glide.uasset"


def _fake_repo(root: Path) -> Path:
    """A minimal repo: two task specs (the spec layout IS the id source) and a
    ThirdPerson substrate carrying the real manifest shape."""
    for tid in (GRADED_BARE, FOREIGN):
        spec = root / "tasks" / "bp-g2" / tid / "task.md"
        spec.parent.mkdir(parents=True, exist_ok=True)
        spec.write_text(f"---\nid: {tid}\nlayers: [L1, L2]\n---\n\n"
                        f"# {tid}\n\n## Prompt given to the agent\n\nDo it.\n",
                        encoding="utf-8")
    sub = root / "UE-projects" / "ThirdPerson"
    sub.mkdir(parents=True, exist_ok=True)
    (sub / "AGENT_WRITABLE.json").write_text(json.dumps(_MANIFEST),
                                             encoding="utf-8")
    return root


class TestKnownTaskIds(unittest.TestCase):
    """The id set the whole rule keys on must come from the spec layout."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cb-scope-ids-"))
        self.repo = _fake_repo(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_ids_are_derived_from_the_spec_tree(self):
        self.assertEqual(tasks.bare_task_ids(self.repo), {GRADED_BARE, FOREIGN})
        # Drop a new task folder in: it is known with no registry edit.
        new = self.repo / "tasks" / "bp-g2" / "gp-newly-dropped" / "task.md"
        new.parent.mkdir(parents=True)
        new.write_text("---\nid: gp-newly-dropped\n---\n# x\n", encoding="utf-8")
        self.assertIn("gp-newly-dropped", tasks.bare_task_ids(self.repo))


class TestSweepRule(unittest.TestCase):
    """What the task-scoped sweep excludes — and everything it must not."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cb-scope-"))
        self.repo = _fake_repo(self.tmp)
        self.spec = self.repo / "tasks" / "bp-g2" / GRADED_BARE / "task.md"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _partition(self, rels, spec=None):
        return task_scope.partition(
            rels, graded_id=GRADED, repo=self.repo, substrate="ThirdPerson",
            spec_path=self.spec if spec is None else spec)

    def test_planted_foreign_leftover_is_excluded_and_recorded(self):
        # THE incident, byte-for-byte: the orphan Blueprint plus the poison
        # run's four real C++ files (Windows separators, as the snapshot
        # keys arrive).
        own = [f"Source\\ThirdPerson\\Tasks\\{GRADED_BARE}\\CraftBenchPoisonAbility.cpp",
               f"Source\\ThirdPerson\\Tasks\\{GRADED_BARE}\\CraftBenchPoisonAbility.h",
               f"Source\\ThirdPerson\\Tasks\\{GRADED_BARE}\\CraftBenchPoisonCharacter.cpp",
               f"Source\\ThirdPerson\\Tasks\\{GRADED_BARE}\\CraftBenchPoisonCharacter.h"]
        sc = self._partition([FOREIGN_ASSET.replace("/", "\\")] + own)
        self.assertEqual(sc.status, "scoped")
        self.assertEqual(sc.kept, own, "the graded task's own files must survive")
        self.assertEqual([f.as_dict() for f in sc.foreign],
                         [{"path": FOREIGN_ASSET, "owner": FOREIGN}],
                         "the foreign leftover must be recorded, never silent")

    def test_own_task_asset_is_kept(self):
        own_asset = f"Content/Tasks/{GRADED_BARE}/GE_Poison.uasset"
        sc = self._partition([own_asset])
        self.assertEqual(sc.kept, [own_asset])
        self.assertEqual(sc.foreign, [])

    def test_task_agnostic_paths_are_kept(self):
        # Whole-module sources and the SHARED asset roots belong to nobody in
        # particular — a sub-agent authoring into Content/Blueprints/ is normal.
        rels = ["Source/ThirdPerson/ThirdPersonCharacter.cpp",
                "Content/Blueprints/BP_Helper.uasset"]
        sc = self._partition(rels)
        self.assertEqual(sc.kept, rels)
        self.assertEqual(sc.foreign, [])

    def test_sandbox_violation_paths_are_never_excluded(self):
        # Deny prefixes are the SANDBOX's business (exit 4). Excluding them
        # here would mask a genuine violation — the one way this belt could
        # do real harm.
        rels = [f"Content/Maps/{FOREIGN}/L_Glide.umap",
                f"Source/CraftBenchTests/Tasks/{FOREIGN}/GlideFixture.cpp"]
        sc = self._partition(rels)
        self.assertEqual(sc.kept, rels)
        self.assertEqual(sc.foreign, [])

    def test_unknown_folder_is_kept_never_excluded_on_a_guess(self):
        rel = "Content/Tasks/my-scratch-folder/BP_Thing.uasset"
        sc = self._partition([rel])
        self.assertEqual(sc.kept, [rel])
        self.assertEqual(sc.foreign, [])

    def test_graded_prompt_targeting_another_folder_keeps_it(self):
        spec = self.tmp / "targeting.md"
        spec.write_text(
            f"# t\n\n## Prompt given to the agent\n\nExtend the asset in "
            f"Content/Tasks/{FOREIGN}/.\n", encoding="utf-8")
        sc = self._partition([FOREIGN_ASSET], spec=spec)
        self.assertEqual(sc.kept, [FOREIGN_ASSET])
        self.assertEqual(sc.foreign, [])

    def test_missing_manifest_disarms_the_belt_and_says_so(self):
        (self.repo / "UE-projects" / "ThirdPerson"
         / "AGENT_WRITABLE.json").unlink()
        sc = self._partition([FOREIGN_ASSET])
        self.assertEqual(sc.status, "unverified")
        self.assertEqual(sc.kept, [FOREIGN_ASSET])
        self.assertEqual(sc.foreign, [])

    def test_ofpa_mirror_of_a_foreign_task_is_foreign(self):
        rel = f"Content/__ExternalActors__/Tasks/{FOREIGN}/A/B/x.uasset"
        sc = self._partition([rel])
        self.assertEqual(sc.kept, [])
        self.assertEqual(sc.foreign[0].owner, FOREIGN)


class TestForeignCompileErrorNote(unittest.TestCase):
    """The grade-side note: loud on contamination, silent otherwise."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cb-note-"))
        self.repo = _fake_repo(self.tmp)
        self.known = tasks.bare_task_ids(self.repo)
        # Verbatim from the incident's l2_pie.log (localized compiler text —
        # the matcher keys on path STRUCTURE, never on message wording).
        self.log = (
            "[2026.08.07-02.17.55:522][390]LogBlueprint: Error: [AssetLog]"
            "C:\\cb\\wd\\e1e85ee3fd\\ThirdPerson\\Content\\Tasks\\"
            "gp-glide-stamina-bp\\GA_Glide.uasset\uff1a[\u7f16\u8bd1\u5668]"
            "\u6b64\u84dd\u56fe\uff08\u81ea\u8eab\uff09\u5e76\u975e\u662f\u4e00"
            "\u4e2a Character\n"
            "[2026.08.07-02.17.57:616][ 92]LogAutomationController: Error: "
            "LogBlueprint: [AssetLog]C:\\cb\\wd\\e1e85ee3fd\\ThirdPerson\\"
            "Content\\Tasks\\gp-glide-stamina-bp\\GA_Glide.uasset\uff1a"
            "Get CharacterMovement\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _errors(self, text):
        return task_scope.foreign_asset_errors(
            text, graded_id=GRADED, known_ids=self.known)

    def test_fires_on_a_foreign_asset_compile_error(self):
        hit = self._errors(self.log)
        self.assertIsNotNone(hit)
        self.assertEqual(hit["owners"], [FOREIGN])
        self.assertIn("contamination", hit["note"])

    def test_silent_on_the_graded_task_s_own_asset(self):
        own = self.log.replace(FOREIGN, GRADED_BARE)
        self.assertIsNone(self._errors(own),
                          "an agent's OWN broken Blueprint is a model failure "
                          "and must never be excused as contamination")

    def test_silent_on_an_unrelated_l2_failure(self):
        self.assertIsNone(self._errors(
            "LogAutomationController: Error: Test Result={Fail}\n"
            "LogBlueprint: Display: compiling\n"))

    def test_silent_when_l2_passed(self):
        run_dir = self.tmp / "run"
        run_dir.mkdir()
        (run_dir / "l2_pie.log").write_text(self.log, encoding="utf-8")
        passed = {"layers": {"L2": {"status": "pass"}}}
        self.assertIsNone(task_scope.contamination_note(
            run_dir / "l2_pie.log", graded_id=GRADED, repo=self.repo,
            report=passed, verdict="PASS", known_ids=self.known))

    def test_fires_through_contamination_note_when_l2_failed(self):
        run_dir = self.tmp / "run2"
        run_dir.mkdir()
        (run_dir / "l2_pie.log").write_text(self.log, encoding="utf-8")
        failed = {"layers": {"L1": {"status": "pass"},
                             "L2": {"status": "fail"}}}
        hit = task_scope.contamination_note(
            run_dir / "l2_pie.log", graded_id=GRADED, repo=self.repo,
            report=failed, verdict="FAIL", known_ids=self.known)
        self.assertEqual(hit["owners"], [FOREIGN])

    def test_missing_log_is_not_a_crash(self):
        self.assertIsNone(task_scope.contamination_note(
            self.tmp / "nope.log", graded_id=GRADED, repo=self.repo,
            report=None, verdict="FAIL", known_ids=self.known))


def _substrate(root: Path) -> Path:
    """A ThirdPerson-shaped substrate with two per-task content folders."""
    sub = root / "UE-projects" / "ThirdPerson"
    files = {
        "ThirdPerson.uproject": "{}",
        "AGENT_WRITABLE.json": json.dumps(_MANIFEST),
        "Source/ThirdPerson/ThirdPersonCharacter.h": "// shared infra",
        f"Source/ThirdPerson/Tasks/{GRADED_BARE}/PoisonActor.h":
            f"// for task {GRADED_BARE}.",
        f"Source/ThirdPerson/Tasks/{FOREIGN}/GlideActor.h":
            f"// for task {FOREIGN}.",
        "Source/CraftBenchTests/CraftBenchTests.Build.cs": "// module",
        "Source/CraftBenchTests/CraftBenchFunctionalTest.cpp": "// base class",
        f"Content/Tasks/{GRADED_BARE}/GE_Poison.uasset": "poison-bytes",
        f"Content/Tasks/{FOREIGN}/GA_Glide.uasset": "glide-bytes",
        f"Content/Maps/{GRADED_BARE}/L_PoisonStack.umap": "bin",
        f"Content/Maps/{FOREIGN}/L_GlideStamina.umap": "bin",
        "Config/DefaultEngine.ini": "[x]\n",
    }
    for rel, body in files.items():
        p = sub / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    return sub


class TestPreDriveReset(unittest.TestCase):
    """Level 1: the scratch is baseline-pristine before EVERY drive, however
    the previous rep ended."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cb-reset-"))
        self.repo = self.tmp / "repo"
        self.sub = _substrate(self.repo)
        self.spec = self.repo / "tasks" / "bp-g2" / GRADED_BARE / "task.md"
        self.spec.parent.mkdir(parents=True, exist_ok=True)
        self.spec.write_text(
            "---\n"
            f"id: {GRADED_BARE}\n"
            "substrate: ThirdPerson\n"
            "layers: [L1, L2]\n"
            'fixtures: ["L_PoisonStack :: APoisonTest"]\n'
            "---\n\n"
            f"# {GRADED_BARE}\n", encoding="utf-8")
        self.scratch = self.tmp / "CraftBenchGraded"
        self.logs = []

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _copy_fn(self):
        def _copy(src, dest):
            shutil.copytree(self.sub, dest)
        return _copy

    def _compose(self, task=GRADED_BARE):
        return graded_scratch.compose(
            task, repo=self.repo, scratch_dir=self.scratch,
            task_spec_path=self.spec,
            copy_substrate_fn=self._copy_fn(), log=self.logs.append)

    def _reset(self, task=GRADED_BARE):
        return graded_scratch.reset_agent_writable(
            task, repo=self.repo, scratch_dir=self.scratch,
            task_spec_path=self.spec,
            copy_substrate_fn=self._copy_fn(), log=self.logs.append)

    def test_fresh_compose_is_pristine(self):
        self._compose()
        marker = graded_scratch.staged_marker(self.scratch)
        self.assertIn("writable_baseline", marker)
        self.assertEqual(marker["writable_roots"],
                         ["Content/Blueprints", "Content/Tasks",
                          "Content/__ExternalActors__/Tasks",
                          "Source/ThirdPerson"])
        # The baseline covers the whole writable surface, content-keyed.
        self.assertIn(f"Content/Tasks/{GRADED_BARE}/GE_Poison.uasset",
                      marker["writable_baseline"])
        self.assertEqual(self._reset(),
                         {"status": "pristine", "residue": []})

    def test_abnormal_prior_rep_leftover_is_reset_before_the_drive(self):
        # A rep that ended abnormally (EDITOR-GONE) ran NO post-drive cleanup:
        # its bytes are simply still there when the next rep starts.
        self._compose()
        orphan = self.scratch / "Content/Tasks" / FOREIGN / "GA_Glide.uasset"
        orphan.parent.mkdir(parents=True, exist_ok=True)
        orphan.write_text("glide-bytes", encoding="utf-8")
        stray = self.scratch / "Source/ThirdPerson/AgentScratch.cpp"
        stray.write_text("// half-written", encoding="utf-8")

        res = self._reset()

        self.assertEqual(res["status"], "reset-2-paths")
        self.assertEqual(
            res["residue"],
            ["extra Content/Tasks/gp-glide-stamina-bp/GA_Glide.uasset",
             "extra Source/ThirdPerson/AgentScratch.cpp"])
        self.assertFalse(orphan.exists(), "the orphan must be gone PRE-drive")
        self.assertFalse(orphan.parent.exists(),
                         "and its empty foreign folder pruned with it")
        self.assertFalse(stray.exists())
        # Idempotent: the very next call sees a clean tree.
        self.assertEqual(self._reset()["status"], "pristine")

    def test_modified_baseline_file_escalates_to_a_recompose(self):
        self._compose()
        edited = self.scratch / "Source/ThirdPerson/Tasks" / GRADED_BARE / "PoisonActor.h"
        edited.write_text("// EDITED by a prior rep", encoding="utf-8")
        res = self._reset()
        self.assertEqual(res["status"], "reset-1-paths")
        self.assertEqual(res["residue"],
                         [f"modified Source/ThirdPerson/Tasks/{GRADED_BARE}/"
                          f"PoisonActor.h"])
        self.assertEqual(edited.read_text(encoding="utf-8"),
                         f"// for task {GRADED_BARE}.")
        self.assertEqual(self._reset()["status"], "pristine")

    def test_deleted_baseline_file_is_restored(self):
        self._compose()
        gone = self.scratch / "Content/Tasks" / GRADED_BARE / "GE_Poison.uasset"
        gone.unlink()
        res = self._reset()
        self.assertEqual(res["status"], "reset-1-paths")
        self.assertTrue(gone.exists())

    def test_build_state_outside_the_writable_area_is_untouched(self):
        # The reset owns the AGENT-writable surface only: build state
        # (Binaries/Intermediate) survives by design — an incremental rebuild
        # per rep is the whole reason the scratch persists.
        self._compose()
        dll = self.scratch / "Binaries" / "Win64" / "UnrealEditor-ThirdPerson.dll"
        dll.parent.mkdir(parents=True)
        dll.write_bytes(b"\x00")
        self.assertEqual(self._reset()["status"], "pristine")
        self.assertTrue(dll.exists())

    def test_no_manifest_reports_unverified_not_pristine(self):
        # A disarmed gate must never read as a clean one.
        (self.sub / "AGENT_WRITABLE.json").unlink()
        self._compose()
        self.assertNotIn("writable_baseline",
                         graded_scratch.staged_marker(self.scratch))
        res = self._reset()
        self.assertEqual(res, {"status": "unverified", "residue": []})
        self.assertTrue(any("UNVERIFIED" in ln for ln in self.logs))

    def test_pre_v3_marker_reads_as_unverified_and_recomposes(self):
        self._compose()
        marker_path = self.scratch / graded_scratch._MARKER
        old = json.loads(marker_path.read_text(encoding="utf-8"))
        old["schema"] = 2
        old.pop("writable_baseline", None)
        old.pop("writable_roots", None)
        marker_path.write_text(json.dumps(old), encoding="utf-8")
        self.assertIsNone(graded_scratch.pristine_residue(self.scratch))
        self.assertEqual(self._reset()["status"], "unverified")
        # ensure_composed treats the stale schema as a mismatch and upgrades it.
        graded_scratch.ensure_composed(
            GRADED_BARE, repo=self.repo, scratch_dir=self.scratch,
            task_spec_path=self.spec,
            copy_substrate_fn=self._copy_fn(), log=self.logs.append)
        self.assertEqual(self._reset()["status"], "pristine")


if __name__ == "__main__":
    unittest.main()

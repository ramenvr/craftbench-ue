"""Per-task CONTENT staging tests (content_staging.py) — no UE required.

Covers: ownership derivation from task specs (front-matter AND the legacy
regex derivation; per-substrate map attribution so the two glide variants'
shared ``L_GlideStamina`` basename never cross-attributes), the fail-open
contract (unparseable spec / unclaimed content / shared maps / derivation
error => KEEP or stage full), the concrete exclusion sets for a
CraftBenchTemplate bp-g2-style task vs a ThirdPerson task (maps + Content/
Tasks baselines + OFPA mirrors), the --full-substrate / CB_FULL_SUBSTRATE
escape hatch, and the report provenance (content_staging block, round-trip).
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_PARENT = _HERE.parent
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))

import content_staging as cs  # noqa: E402
import run_task  # noqa: E402
from report import Report, HostInfo, report_from_dict  # noqa: E402
from spec import TaskSpec, Fixture, parse_task_file  # noqa: E402


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _fm_spec(
    task_id: str,
    substrate: str,
    *,
    fixtures: tuple[str, ...] = (),
    l2i: bool = False,
) -> str:
    lines = [
        "---",
        f"id: {task_id}",
        f"substrate: {substrate}",
    ]
    layers = ["L1"]
    if fixtures:
        layers.append("L2")
    if l2i:
        layers.append("L2I")
    lines.append(f"layers: [{', '.join(layers)}]")
    if fixtures:
        entries = ", ".join(f'"{f}"' for f in fixtures)
        lines.append(f"fixtures: [{entries}]")
    if l2i:
        lines.append(f"introspect: [{task_id.replace('-', '_')}.py]")
    lines += ["---", "", f"# {task_id}", "", "Prompt body."]
    return "\n".join(lines) + "\n"


class StagingFixtureMixin:
    """A tasks tree + two fake substrate workdirs shared by the test classes."""

    def setUp(self) -> None:  # noqa: N802 (unittest naming)
        self._tmp = tempfile.TemporaryDirectory(prefix="cbstage-")
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.tasks_root = root / "tasks"

        # --- task specs (front matter unless noted) ------------------------
        _write(
            self.tasks_root / "flagship" / "t0-sanity" / "task.md",
            # "template" exercises the run_task alias -> CraftBenchTemplate.
            _fm_spec("t0-sanity", "template",
                     fixtures=("L_SanityTask :: ASanityFunctionalTest",)),
        )
        _write(
            self.tasks_root / "bp-g2" / "gp-poison" / "task.md",
            _fm_spec("gp-poison", "CraftBenchTemplate",
                     fixtures=("L_PoisonStack :: APoisonFunctionalTest",)),
        )
        _write(
            self.tasks_root / "bp-g2" / "gp-glide" / "task.md",
            _fm_spec("gp-glide", "CraftBenchTemplate",
                     fixtures=("L_GlideStamina :: AGlideStaminaFunctionalTest",)),
        )
        # Blueprint variant: SAME map basename, DIFFERENT substrate.
        _write(
            self.tasks_root / "bp-g2" / "gp-glide-bp" / "task.md",
            _fm_spec("gp-glide-bp", "ThirdPerson",
                     fixtures=("L_GlideStamina :: AGlideStaminaFunctionalTest",),
                     l2i=True),
        )
        # ThirdPerson asset-deliverable task (no map, L2I only).
        _write(
            self.tasks_root / "kp" / "t1-chase" / "task.md",
            _fm_spec("t1-chase", "ThirdPerson", l2i=True),
        )
        # LEGACY spec (no front matter): map ownership via the prose regex
        # derivation; substrate defaults to "template".
        _write(
            self.tasks_root / "wave1" / "t1-legacy-crafting" / "task.md",
            "\n".join([
                "# t1-legacy-crafting",
                "",
                "## Task ID and metadata",
                "- task_id: t1-legacy-crafting",
                "",
                "## Verifier layers used",
                "- L1",
                "- L2",
                "",
                "The committed map `Content/Maps/L_CraftingQueue.umap` holds "
                "the fixture `ACraftingQueueFunctionalTest`.",
            ]) + "\n",
        )
        # UNPARSEABLE spec (unknown layer token) — must be fail-open.
        _write(
            self.tasks_root / "bad" / "broken-task" / "task.md",
            "---\nid: broken-task\nsubstrate: CraftBenchTemplate\n"
            "layers: [L99]\n---\n\n# broken\n",
        )

        # --- CraftBenchTemplate workdir substrate --------------------------
        self.template_wd = root / "wd-template" / "CraftBenchTemplate"
        c = self.template_wd / "Content"
        _write(c / "Maps" / "L_PoisonStack.umap", "bin")
        _write(c / "Maps" / "L_GlideStamina.umap", "bin")
        _write(c / "Maps" / "L_GlideStamina_BuiltData.uasset", "bin")
        _write(c / "Maps" / "L_CraftingQueue.umap", "bin")  # legacy-claimed
        _write(c / "Maps" / "L_Orphan.umap", "bin")  # claimed by NO task
        _write(c / "Maps" / "t0-sanity" / "L_SanityTask.umap", "bin")
        _write(c / "Maps" / "_scratch" / "L_Whatever.umap", "bin")  # unclaimed
        _write(c / "Characters" / "hero.uasset", "bin")  # non-task content
        _write(c / "Tasks" / "gp-poison" / "baseline.uasset", "bin")
        _write(c / "Tasks" / "t0-sanity" / "baseline.uasset", "bin")
        _write(c / "Tasks" / "_runreport" / "x.uasset", "bin")  # not an id
        _write(c / "Tasks" / "broken-task" / "y.uasset", "bin")  # unparseable
        _write(self.template_wd / "Source" / "CraftBenchTemplate" / "A.cpp", "int x;")
        _write(self.template_wd / "Source" / "CraftBenchTests" / "F.cpp", "int y;")

        # --- ThirdPerson workdir substrate ---------------------------------
        self.tp_wd = root / "wd-tp" / "ThirdPerson"
        t = self.tp_wd / "Content"
        _write(t / "Maps" / "L_GlideStamina.umap", "bin")  # gp-glide-bp's
        _write(t / "Tasks" / "t1-chase" / "baseline.uasset", "bin")
        _write(t / "Tasks" / "gp-glide-bp" / "bp.uasset", "bin")
        _write(t / "__ExternalActors__" / "Tasks" / "t1-chase" / "a.uasset", "bin")
        _write(t / "__ExternalObjects__" / "Tasks" / "t1-chase" / "o.uasset", "bin")
        for ofpa in ("__ExternalActors__", "__ExternalObjects__"):
            _write(t / ofpa / "Maps" / "gp-glide-bp" / "L_GlideStamina"
                   / "A" / "active.uasset", "active")
            _write(t / ofpa / "Maps" / "t1-chase" / "L_Chase"
                   / "F" / "foreign.uasset", "foreign")
            # Unknown immediate names remain fail-open and staged.
            _write(t / ofpa / "Maps" / "_scratch" / "L_Unknown"
                   / "U" / "unknown.uasset", "unknown")
        _write(t / "__ExternalActors__" / "ThirdPerson" / "lvl.uasset", "bin")
        _write(t / "Characters" / "manny.uasset", "bin")

    # Convenience -----------------------------------------------------------
    def _task(self, task_id: str) -> TaskSpec:
        for p in self.tasks_root.rglob("task.md"):
            if p.parent.name == task_id.split("/")[-1]:
                spec = parse_task_file(p)
                if spec.task_id == task_id:
                    return spec
        raise AssertionError(f"test task {task_id} not found")

    def _stage(self, wd: Path, task_id: str, substrate: str) -> cs.StagingResult:
        return cs.stage_per_task_content(
            wd, self._task(task_id), self.tasks_root, substrate,
            substrate_alias=run_task._substrate_dir_name,
        )


class TestOwnershipDerivation(StagingFixtureMixin, unittest.TestCase):
    def test_map_ownership_is_per_substrate(self) -> None:
        own = cs.derive_content_ownership(
            self.tasks_root, "CraftBenchTemplate",
            substrate_alias=run_task._substrate_dir_name,
        )
        # Template-side L_GlideStamina is owned by gp-glide ONLY — the -bp
        # variant claims the SAME basename on ThirdPerson and must not
        # cross-attribute (that is the substring/shared-basename trap).
        self.assertEqual(own.map_owners.get("L_GlideStamina"), {"gp-glide"})
        self.assertEqual(own.map_owners.get("L_PoisonStack"), {"gp-poison"})
        self.assertEqual(own.map_owners.get("L_SanityTask"), {"t0-sanity"})

        tp = cs.derive_content_ownership(
            self.tasks_root, "ThirdPerson",
            substrate_alias=run_task._substrate_dir_name,
        )
        self.assertEqual(tp.map_owners.get("L_GlideStamina"), {"gp-glide-bp"})

    def test_legacy_spec_contributes_map_via_regex_derivation(self) -> None:
        own = cs.derive_content_ownership(
            self.tasks_root, "CraftBenchTemplate",
            substrate_alias=run_task._substrate_dir_name,
        )
        self.assertEqual(
            own.map_owners.get("L_CraftingQueue"), {"t1-legacy-crafting"}
        )

    def test_task_ids_span_all_substrates(self) -> None:
        own = cs.derive_content_ownership(
            self.tasks_root, "CraftBenchTemplate",
            substrate_alias=run_task._substrate_dir_name,
        )
        # Id-named dirs belong to their task wherever they appear, so the id
        # set is cross-substrate.
        self.assertIn("t1-chase", own.task_ids)
        self.assertIn("gp-glide-bp", own.task_ids)

    def test_unparseable_spec_is_fail_open_and_noted(self) -> None:
        own = cs.derive_content_ownership(
            self.tasks_root, "CraftBenchTemplate",
            substrate_alias=run_task._substrate_dir_name,
        )
        self.assertNotIn("broken-task", own.task_ids)
        self.assertTrue(any("broken-task" in n for n in own.notes))

    def test_empty_tasks_root_raises(self) -> None:
        empty = Path(self._tmp.name) / "empty-tasks"
        empty.mkdir()
        with self.assertRaises(cs.OwnershipError):
            cs.derive_content_ownership(empty, "CraftBenchTemplate")
        with self.assertRaises(cs.OwnershipError):
            cs.derive_content_ownership(
                Path(self._tmp.name) / "nonexistent", "CraftBenchTemplate"
            )


class TestTemplateExclusions(StagingFixtureMixin, unittest.TestCase):
    """Grading a bp-g2-style CraftBenchTemplate task (gp-poison)."""

    def setUp(self) -> None:
        super().setUp()
        self.result = self._stage(
            self.template_wd, "gp-poison", "CraftBenchTemplate"
        )
        self.c = self.template_wd / "Content"

    def test_mode_and_excluded_list(self) -> None:
        self.assertEqual(self.result.mode, "per-task")
        self.assertEqual(
            set(self.result.excluded),
            {
                "Content/Maps/L_GlideStamina.umap",
                "Content/Maps/L_GlideStamina_BuiltData.uasset",
                "Content/Maps/L_CraftingQueue.umap",
                "Content/Maps/t0-sanity",
                "Content/Tasks/t0-sanity",
            },
        )

    def test_own_map_and_baseline_kept(self) -> None:
        self.assertTrue((self.c / "Maps" / "L_PoisonStack.umap").exists())
        self.assertTrue((self.c / "Tasks" / "gp-poison" / "baseline.uasset").exists())

    def test_other_tasks_content_removed(self) -> None:
        self.assertFalse((self.c / "Maps" / "L_GlideStamina.umap").exists())
        self.assertFalse((self.c / "Maps" / "L_GlideStamina_BuiltData.uasset").exists())
        self.assertFalse((self.c / "Maps" / "t0-sanity").exists())
        self.assertFalse((self.c / "Tasks" / "t0-sanity").exists())

    def test_unattributable_content_kept(self) -> None:
        # Fail-open: claimed by NO spec => KEEP, wherever it sits.
        self.assertTrue((self.c / "Maps" / "L_Orphan.umap").exists())
        self.assertTrue((self.c / "Maps" / "_scratch" / "L_Whatever.umap").exists())
        self.assertTrue((self.c / "Characters" / "hero.uasset").exists())
        self.assertTrue((self.c / "Tasks" / "_runreport" / "x.uasset").exists())
        # broken-task's spec did not parse => its id is unknown => KEEP.
        self.assertTrue((self.c / "Tasks" / "broken-task" / "y.uasset").exists())

    def test_source_tree_untouched(self) -> None:
        self.assertTrue(
            (self.template_wd / "Source" / "CraftBenchTemplate" / "A.cpp").exists()
        )
        self.assertTrue(
            (self.template_wd / "Source" / "CraftBenchTests" / "F.cpp").exists()
        )


class TestThirdPersonExclusions(StagingFixtureMixin, unittest.TestCase):
    def test_grading_the_bp_variant_keeps_its_shared_basename_map(self) -> None:
        result = self._stage(self.tp_wd, "gp-glide-bp", "ThirdPerson")
        t = self.tp_wd / "Content"
        self.assertEqual(result.mode, "per-task")
        # Its own flat map survives even though a same-named map exists on the
        # OTHER substrate under a different owner.
        self.assertTrue((t / "Maps" / "L_GlideStamina.umap").exists())
        self.assertTrue((t / "Tasks" / "gp-glide-bp" / "bp.uasset").exists())
        # The kp- task's baseline AND both OFPA mirrors go.
        self.assertFalse((t / "Tasks" / "t1-chase").exists())
        self.assertFalse((t / "__ExternalActors__" / "Tasks" / "t1-chase").exists())
        self.assertFalse((t / "__ExternalObjects__" / "Tasks" / "t1-chase").exists())
        self.assertTrue(
            (t / "__ExternalActors__/Maps/gp-glide-bp/L_GlideStamina/A/active.uasset")
            .exists())
        self.assertTrue(
            (t / "__ExternalObjects__/Maps/gp-glide-bp/L_GlideStamina/A/active.uasset")
            .exists())
        self.assertFalse((t / "__ExternalActors__/Maps/t1-chase").exists())
        self.assertFalse((t / "__ExternalObjects__/Maps/t1-chase").exists())
        # Non-task OFPA + template content stay.
        self.assertTrue(
            (t / "__ExternalActors__" / "ThirdPerson" / "lvl.uasset").exists()
        )
        self.assertTrue(
            (t / "__ExternalActors__/Maps/_scratch/L_Unknown/U/unknown.uasset")
            .exists())
        self.assertTrue((t / "Characters" / "manny.uasset").exists())

    def test_grading_the_l2i_task_keeps_its_baseline_and_ofpa(self) -> None:
        result = self._stage(self.tp_wd, "t1-chase", "ThirdPerson")
        t = self.tp_wd / "Content"
        self.assertEqual(
            set(result.excluded),
            {
                "Content/Maps/L_GlideStamina.umap",
                "Content/Tasks/gp-glide-bp",
                "Content/__ExternalActors__/Maps/gp-glide-bp",
                "Content/__ExternalObjects__/Maps/gp-glide-bp",
            },
        )
        self.assertTrue((t / "Tasks" / "t1-chase" / "baseline.uasset").exists())
        self.assertTrue(
            (t / "__ExternalActors__" / "Tasks" / "t1-chase" / "a.uasset").exists()
        )
        self.assertTrue(
            (t / "__ExternalObjects__" / "Tasks" / "t1-chase" / "o.uasset").exists()
        )
        self.assertTrue(
            (t / "__ExternalActors__/Maps/t1-chase/L_Chase/F/foreign.uasset")
            .exists())
        self.assertTrue(
            (t / "__ExternalObjects__/Maps/t1-chase/L_Chase/F/foreign.uasset")
            .exists())


class TestSharedAndAmbiguousMaps(StagingFixtureMixin, unittest.TestCase):
    def test_map_shared_with_the_graded_task_is_kept(self) -> None:
        # A second template task also claims L_PoisonStack: grading gp-poison
        # must still keep it (the graded task is among the owners).
        _write(
            self.tasks_root / "bp-g2" / "gp-poison-extra" / "task.md",
            _fm_spec("gp-poison-extra", "CraftBenchTemplate",
                     fixtures=("L_PoisonStack :: APoisonFunctionalTest",)),
        )
        self._stage(self.template_wd, "gp-poison", "CraftBenchTemplate")
        self.assertTrue(
            (self.template_wd / "Content" / "Maps" / "L_PoisonStack.umap").exists()
        )

    def test_map_shared_by_two_other_tasks_is_still_excluded(self) -> None:
        # Multiple owners, NONE of them the graded task -> positively not
        # ours -> excluded.
        _write(
            self.tasks_root / "bp-g2" / "gp-glide-extra" / "task.md",
            _fm_spec("gp-glide-extra", "CraftBenchTemplate",
                     fixtures=("L_GlideStamina :: AGlideStaminaFunctionalTest",)),
        )
        result = self._stage(self.template_wd, "gp-poison", "CraftBenchTemplate")
        self.assertIn("Content/Maps/L_GlideStamina.umap", result.excluded)

    def test_derivation_error_stages_full_substrate_with_note(self) -> None:
        before = sorted(
            p.relative_to(self.template_wd).as_posix()
            for p in self.template_wd.rglob("*") if p.is_file()
        )
        result = cs.stage_per_task_content(
            self.template_wd,
            self._task("gp-poison"),
            Path(self._tmp.name) / "no-such-tasks-root",
            "CraftBenchTemplate",
        )
        after = sorted(
            p.relative_to(self.template_wd).as_posix()
            for p in self.template_wd.rglob("*") if p.is_file()
        )
        self.assertEqual(result.mode, "full")
        self.assertEqual(result.excluded, ())
        self.assertTrue(any("fail-open" in n for n in result.notes))
        self.assertEqual(before, after)  # nothing was deleted


class TestEscapeHatch(unittest.TestCase):
    def test_env_and_flag_resolution(self) -> None:
        self.assertFalse(cs.full_substrate_requested(False, {}))
        self.assertTrue(cs.full_substrate_requested(True, {}))
        for truthy in ("1", "true", "YES", "on"):
            self.assertTrue(
                cs.full_substrate_requested(False, {"CB_FULL_SUBSTRATE": truthy})
            )
        for falsy in ("", "0", "false", "off", "no"):
            self.assertFalse(
                cs.full_substrate_requested(False, {"CB_FULL_SUBSTRATE": falsy})
            )

    def test_parser_accepts_full_substrate_flag(self) -> None:
        p = run_task.build_parser()
        args = p.parse_args(
            ["--task", "t.md", "--submission", "s", "--ue-root", "ue"]
        )
        self.assertFalse(args.full_substrate)
        args = p.parse_args(
            ["--task", "t.md", "--submission", "s", "--ue-root", "ue",
             "--full-substrate"]
        )
        self.assertTrue(args.full_substrate)


class TestProvenance(unittest.TestCase):
    def test_staging_result_to_dict_shape(self) -> None:
        r = cs.StagingResult(
            mode="per-task",
            excluded=("Content/Maps/L_X.umap", "Content/Tasks/other"),
            notes=("note-a",),
        )
        d = r.to_dict()
        self.assertEqual(d["mode"], "per-task")
        self.assertEqual(d["excluded_count"], 2)
        self.assertEqual(
            d["excluded"], ["Content/Maps/L_X.umap", "Content/Tasks/other"]
        )
        self.assertEqual(d["notes"], ["note-a"])
        # Full mode with nothing excluded stays compact.
        d2 = cs.StagingResult(mode="full").to_dict()
        self.assertEqual(d2, {"mode": "full", "excluded_count": 0})

    def _report(self, staging: dict | None) -> Report:
        return Report(
            task_id="t0",
            submission_sha="0" * 64,
            layers={},
            overall="pass",
            duration_seconds=1.0,
            ue_version="5.8.0",
            host=HostInfo(os="windows", arch="AMD64"),
            content_staging=staging,
        )

    def test_report_records_and_round_trips_content_staging(self) -> None:
        staging = cs.StagingResult(
            mode="per-task", excluded=("Content/Maps/L_X.umap",)
        ).to_dict()
        rep = self._report(staging)
        d = rep.to_dict()
        self.assertEqual(d["content_staging"]["mode"], "per-task")
        self.assertEqual(d["content_staging"]["excluded_count"], 1)
        back = report_from_dict(d)
        self.assertEqual(back.content_staging, staging)
        self.assertIn("staging   : per-task content (1 entry excluded)",
                      rep.render_text())

    def test_report_omits_block_when_absent(self) -> None:
        rep = self._report(None)
        self.assertNotIn("content_staging", rep.to_dict())
        self.assertNotIn("staging", rep.render_text())


class TestSpecMapNames(unittest.TestCase):
    def test_all_derivation_channels_contribute(self) -> None:
        spec = TaskSpec(
            task_id="x",
            substrate="CraftBenchTemplate",
            layers=("L1", "L2"),
            fixtures=(
                Fixture("L_A", "AAFunctionalTest"),
                Fixture("L_B", "ABFunctionalTest"),
            ),
            map_name="L_Legacy",
            l3_fixtures=(Fixture("L_Render", "ARenderFunctionalTest"),),
        )
        self.assertEqual(
            cs._spec_map_names(spec), {"L_A", "L_B", "L_Legacy", "L_Render"}
        )


if __name__ == "__main__":
    unittest.main()

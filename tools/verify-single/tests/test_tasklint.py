"""Unit tests for tasklint (the static, no-UE task-spec linter), spec v2.

Everything here runs without a UE install: rules are exercised against
synthetic task specs + a fake substrate tree in a tempdir, plus golden
checks against the real flagship tasks (which must lint error-free).
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_HERE = Path(__file__).resolve().parent
_VERIFY = _HERE.parent
if str(_VERIFY) not in sys.path:
    sys.path.insert(0, str(_VERIFY))

from tasklint import (  # noqa: E402
    ERROR,
    WARN,
    LintContext,
    discover_specs,
    find_repo_root,
    is_task_spec,
    lint_task,
    main,
)
import tasklint  # noqa: E402

REPO_ROOT = _VERIFY.parents[1]


# --------------------------------------------------------------------------- #
# Spec-text scaffolding                                                        #
# --------------------------------------------------------------------------- #

# Spec v2: restricted front-matter block + markdown body. Only the prompt +
# workspace sections are agent-visible; Anti-gaming notes stays an H2 so the
# linter can count its bullets.
GOOD_SPEC = """---
id: {task_id}
substrate: CraftBenchTemplate
set: demo-set
tier: T1
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_DemoTask :: ADemoFunctionalTest"]
---

# Demo task

## Prompt given to the agent

> When the game starts, the marked object must announce itself exactly once
> within the first two seconds, and never again afterwards.

## Workspace state pre-task

- Substrate baseline, no additions

## Verifier specification

Checkpoint at t=2.0s asserts the announcement count == 1.

## Anti-gaming notes

- Hardcoded pass: defeated by checkpoint count.
- Constant announce spam: count must be exactly 1.
- Wrong-window announce: t=0 checkpoint must read 0.
"""

# Legacy H2-format spec (no front matter) — must parse via the fallback and
# earn exactly one "legacy format, migrate" WARN.
LEGACY_SPEC = """# Demo task

## Task ID and metadata

- task_id: {task_id}
- tier: T1
- capability_bucket: Gameplay Programming
- category: gameplay
- set: demo-set
- substrate: template

## Prompt given to the agent

> When the game starts, the marked object must announce itself exactly once
> within the first two seconds, and never again afterwards.

## Workspace state pre-task

- Substrate baseline, no additions

## Verifier layers used

L1, L2

## Verifier fixtures

- L_DemoTask :: ADemoFunctionalTest

## Verifier specification

Checkpoint at t=2.0s asserts the announcement count == 1.

## Anti-gaming notes

- Hardcoded pass: defeated by checkpoint count.
- Constant announce spam: count must be exactly 1.
- Wrong-window announce: t=0 checkpoint must read 0.
"""


def _write_fake_repo(root: Path, *, task_id: str = "demo-task",
                     with_fixture: bool = True, with_map: bool = True,
                     fixture_in_task_folder: bool = False,
                     with_reference: bool = True,
                     with_manifest: bool = True,
                     spec_text: str = GOOD_SPEC) -> Path:
    """Materialize the minimal repo shape the file-existence rules consult.

    Folder-per-task layout: tasks/<set>/<task-id>/task.md (with the
    folder-local reference/ solution + the substrate's AGENT_WRITABLE.json
    the reference-sandbox rule consults).
    """
    task_dir = root / "tasks" / "demo-set" / task_id
    task_dir.mkdir(parents=True)
    spec = task_dir / "task.md"
    spec.write_text(spec_text.format(task_id=task_id), encoding="utf-8")

    if with_reference:
        ref_src = task_dir / "reference" / "Source" / "CraftBenchTemplate" / "Tasks" / task_id
        ref_src.mkdir(parents=True)
        (ref_src / "DemoActor.cpp").write_text("// ref impl", encoding="utf-8")
        # A task shipping a reference must also ship the oracle proving that
        # reference discriminates (discrimination-required, 2026-08-13), so the
        # "clean spec" fixture carries a minimal compliant package.
        disc = task_dir / "discrimination"
        disc.mkdir(parents=True, exist_ok=True)
        (disc / "MATRIX.md").write_text(
            "# Discrimination matrix - demo\n\n"
            "## Matrix\n\n"
            "| Submission | Overall | Fails at | Expected substring | Notes |\n"
            "|---|---|---|---|---|\n"
            "| `../reference` | PASS | - | - | all green |\n"
            "| empty | FAIL | `thing` | `THING_MISSING path=` | fans out |\n\n"
            "## Requirements table (checklist section 7)\n\n"
            "| # | Prompt requirement | Asserted | Named failure substring |\n"
            "|---|---|---|---|\n"
            "| 1 | a thing exists | fully | `THING_MISSING path=` |\n",
            encoding="utf-8")

    (root / "tools" / "verify-single" / "introspect").mkdir(parents=True)

    sub = root / "UE-projects" / "CraftBenchTemplate"
    tests_dir = sub / "Source" / "CraftBenchTests"
    tests_dir.mkdir(parents=True)
    if with_manifest:
        (sub / "AGENT_WRITABLE.json").write_text(json.dumps({
            "substrate": "CraftBenchTemplate",
            "game_module": "CraftBenchTemplate",
            "writable": ["Source/CraftBenchTemplate/", "Content/Tasks/"],
            "deny": ["Source/CraftBenchTests/", "Content/Maps/"],
        }), encoding="utf-8")
    if with_fixture:
        fx_dir = (tests_dir / "Tasks" / task_id) if fixture_in_task_folder \
            else tests_dir
        fx_dir.mkdir(parents=True, exist_ok=True)
        (fx_dir / "DemoFunctionalTest.h").write_text(
            "class ADemoFunctionalTest {};", encoding="utf-8")
        (fx_dir / "DemoFunctionalTest.cpp").write_text(
            "// impl", encoding="utf-8")
    maps = sub / "Content" / "Maps"
    maps.mkdir(parents=True)
    if with_map:
        (maps / "L_DemoTask.umap").write_bytes(b"\x00binary")
    return spec


class _FakeRepoCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def lint(self, spec: Path):
        return lint_task(spec, LintContext(repo_root=self.root))

    def rules(self, result, severity=None):
        return [f.rule for f in result.findings
                if severity is None or f.severity == severity]


class TestCleanSpec(_FakeRepoCase):
    def test_good_spec_has_no_errors(self):
        spec = _write_fake_repo(self.root)
        r = self.lint(spec)
        self.assertEqual(r.errors, 0, [f.message for f in r.findings])
        self.assertTrue(r.ok())

    def test_good_spec_ok_strict_when_no_warns(self):
        spec = _write_fake_repo(self.root)
        r = self.lint(spec)
        self.assertEqual(r.warnings, 0, [f.message for f in r.findings])
        self.assertTrue(r.ok(strict=True))

    def test_v2_spec_is_not_flagged_legacy(self):
        spec = _write_fake_repo(self.root)
        r = self.lint(spec)
        self.assertNotIn("legacy-format", self.rules(r))


class TestFrontMatterRules(_FakeRepoCase):
    def test_legacy_spec_gets_single_migrate_warn(self):
        spec = _write_fake_repo(self.root, spec_text=LEGACY_SPEC)
        r = self.lint(spec)
        legacy = [f for f in r.findings if f.rule == "legacy-format"]
        self.assertEqual(len(legacy), 1)
        self.assertEqual(legacy[0].severity, WARN)
        self.assertIn("legacy format, migrate", legacy[0].message)
        # A well-formed legacy spec with fixture + map on disk stays error-free.
        self.assertEqual(r.errors, 0,
                         [f.message for f in r.findings if f.severity == ERROR])

    def test_malformed_front_matter_is_error(self):
        text = GOOD_SPEC.replace("layers: [L1, L2]", "layers [L1, L2]")
        spec = _write_fake_repo(self.root, spec_text=text)
        r = self.lint(spec)
        self.assertIn("parseable", self.rules(r, ERROR))

    def test_unclosed_front_matter_is_error(self):
        text = "---\nid: {task_id}\nlayers: [L1]\n\n## Prompt given to the agent\n\nBody.\n"
        spec = _write_fake_repo(self.root, spec_text=text)
        r = self.lint(spec)
        self.assertIn("parseable", self.rules(r, ERROR))

    def test_l2_without_fixtures_in_front_matter_is_error(self):
        # The v2 parser itself enforces the L2 -> fixtures invariant.
        text = GOOD_SPEC.replace(
            'fixtures: ["L_DemoTask :: ADemoFunctionalTest"]\n', "")
        spec = _write_fake_repo(self.root, spec_text=text)
        r = self.lint(spec)
        self.assertIn("parseable", self.rules(r, ERROR))


class TestStructuralRules(_FakeRepoCase):
    def test_task_id_folder_mismatch_is_error(self):
        text = GOOD_SPEC.replace("id: {task_id}", "id: other-name")
        spec = _write_fake_repo(self.root, spec_text=text)
        r = self.lint(spec)
        self.assertIn("task-id-folder", self.rules(r, ERROR))

    def test_missing_prompt_section_is_error(self):
        text = GOOD_SPEC.replace("## Prompt given to the agent",
                                 "## Renamed prompt")
        spec = _write_fake_repo(self.root, spec_text=text)
        r = self.lint(spec)
        self.assertIn("prompt-required", self.rules(r, ERROR))

    def test_unimplemented_layer_is_warn(self):
        text = GOOD_SPEC.replace("layers: [L1, L2]", "layers: [L1, L2, L4]")
        spec = _write_fake_repo(self.root, spec_text=text)
        r = self.lint(spec)
        self.assertIn("layers-valid", self.rules(r, WARN))
        self.assertNotIn("layers-valid", self.rules(r, ERROR))

    def test_legacy_l2_without_any_fixture_hint_is_error(self):
        text = LEGACY_SPEC.replace(
            "## Verifier fixtures\n\n- L_DemoTask :: ADemoFunctionalTest\n\n",
            "")
        # Scrub every map/class token so the legacy derivation cannot recover
        # a (map, class) pair from prose.
        spec = _write_fake_repo(self.root, spec_text=text)
        r = self.lint(spec)
        self.assertIn("l2-fixtures", self.rules(r, ERROR))

    def test_missing_anti_gaming_section_is_error(self):
        text = GOOD_SPEC.replace("## Anti-gaming notes", "## Renamed notes")
        spec = _write_fake_repo(self.root, spec_text=text)
        r = self.lint(spec)
        self.assertIn("anti-gaming-count", self.rules(r, ERROR))

    def test_anti_gaming_below_three_is_error(self):
        text = GOOD_SPEC[:GOOD_SPEC.index("- Hardcoded pass")] + (
            "- Hardcoded pass: defeated by checkpoint count.\n")
        spec = _write_fake_repo(self.root, spec_text=text)
        r = self.lint(spec)
        self.assertIn("anti-gaming-count", self.rules(r, ERROR))

    def test_anti_gaming_above_five_is_NOT_flagged(self):
        """The >5 upper bound was RETIRED 2026-08-17 (owner instruction).

        It was this rule's only BLOCKING branch, and it punished authors for
        writing MORE anti-gaming analysis than a rule of thumb — against a count
        the 2026-08-11 requirements-table decision had already stripped of
        meaning. Inverted rather than deleted: re-adding the bound fails here and
        sends the author to the reasoning."""
        extra = "".join(f"- Extra gaming mode {i}: defense.\n" for i in range(4))
        spec = _write_fake_repo(self.root, spec_text=GOOD_SPEC + extra)
        r = self.lint(spec)
        self.assertNotIn("anti-gaming-count", self.rules(r, WARN))
        self.assertNotIn("anti-gaming-count", self.rules(r, ERROR))

    def test_the_anti_gaming_FLOOR_still_holds(self):
        """The n<3 ERROR is a DIFFERENT check and deliberately survives: it
        catches a spec shipping no anti-gaming analysis at all. Retiring the
        upper bound must not be read as retiring the floor."""
        text = GOOD_SPEC[:GOOD_SPEC.index("- Hardcoded pass")] + (
            "- Only one entry: defeated by checkpoint count.\n")
        spec = _write_fake_repo(self.root, spec_text=text)
        self.assertIn("anti-gaming-count", self.rules(self.lint(spec), ERROR))

class TestPromptJargonRetired(_FakeRepoCase):
    """`prompt-jargon` was RETIRED 2026-08-17 on the owner's instruction.

    It asked a human to confirm a word was behaviour rather than a class name,
    so the corpus-ledger tool parked every hit in an OWNER-EYES verdict that NO amount
    of task work could clear. Of its three live hits, one was owner-ruled KEEP
    (decision Q9) and the other two leaked through the task IDS, not the prose —
    tracked now as the decision-Q15 renames that actually fix them.

    This class replaces the three tests that asserted the rule fired. It exists
    so a well-meaning re-add trips a test that explains why it went."""

    def test_the_rule_is_not_registered(self):
        import tasklint
        self.assertFalse([f for f in tasklint._RULES if "jargon" in f.__name__],
                         "prompt-jargon was retired — do not re-register it")

    def test_a_prompt_full_of_class_names_is_no_longer_flagged(self):
        text = GOOD_SPEC.replace(
            "the marked object must announce itself",
            "extend ATaskActor so UStaticMesh announces itself in BeginPlay")
        spec = _write_fake_repo(self.root, spec_text=text)
        self.assertNotIn("prompt-jargon",
                         [f.rule for f in self.lint(spec).findings])


class TestFileExistenceRules(_FakeRepoCase):
    def _external_map_fixture(self):
        spec = _write_fake_repo(
            self.root, with_map=False, task_id="demo-task")
        map_path = (self.root / "UE-projects/CraftBenchTemplate/Content/Maps"
                    / "demo-task/L_DemoTask.umap")
        map_path.parent.mkdir(parents=True)
        map_path.write_bytes(
            b"package WorldExternalActorsReferences package "
            b"/Game/__ExternalActors__/Maps/demo-task/L_DemoTask/A/AA/Actor")
        return spec, map_path

    def _tracked(self, map_path: Path, assets: tuple[Path, ...] = ()):
        map_rel = map_path.relative_to(self.root).as_posix()
        asset_rels = [p.relative_to(self.root).as_posix() for p in assets]

        def _files(_repo_root, pattern):
            if pattern == "*.umap":
                return [map_rel]
            if pattern == "*.uasset":
                return asset_rels
            return []

        return mock.patch.object(
            tasklint.inventory, "tracked_files", side_effect=_files)

    def test_missing_fixture_source_is_error(self):
        spec = _write_fake_repo(self.root, with_fixture=False)
        r = self.lint(spec)
        self.assertIn("fixture-source-exists", self.rules(r, ERROR))

    def test_fixture_in_per_task_subfolder_is_found(self):
        # Per-task convention: Source/CraftBenchTests/Tasks/<task-id>/.
        spec = _write_fake_repo(self.root, fixture_in_task_folder=True)
        r = self.lint(spec)
        self.assertNotIn("fixture-source-exists", self.rules(r, ERROR))

    def test_fixture_found_by_content_scan_when_filename_differs(self):
        spec = _write_fake_repo(self.root, with_fixture=False)
        tests_dir = (self.root / "UE-projects" / "CraftBenchTemplate"
                     / "Source" / "CraftBenchTests")
        (tests_dir / "WeirdName.h").write_text(
            "UCLASS()\nclass ADemoFunctionalTest : public X {};",
            encoding="utf-8")
        r = self.lint(spec)
        self.assertNotIn("fixture-source-exists", self.rules(r, ERROR))

    def test_missing_map_binary_is_error(self):
        # Scaffolders are RETIRED: a missing committed .umap is a hard ERROR.
        spec = _write_fake_repo(self.root, with_map=False)
        r = self.lint(spec)
        self.assertIn("map-binary-exists", self.rules(r, ERROR))

    def test_scaffolder_does_not_rescue_missing_binary(self):
        # A leftover Tools/scaffold_*.py must NOT downgrade the finding —
        # there is no re-bake path anymore.
        spec = _write_fake_repo(self.root, with_map=False)
        tools_dir = (self.root / "UE-projects" / "CraftBenchTemplate"
                     / "Tools")
        tools_dir.mkdir(parents=True)
        (tools_dir / "scaffold_L_DemoTask.py").write_text(
            "# retired scaffolder", encoding="utf-8")
        r = self.lint(spec)
        self.assertIn("map-binary-exists", self.rules(r, ERROR))

    def test_map_binary_in_per_task_folder_is_found(self):
        spec = _write_fake_repo(self.root, with_map=False,
                                task_id="demo-task")
        per_task = (self.root / "UE-projects" / "CraftBenchTemplate"
                    / "Content" / "Maps" / "demo-task")
        per_task.mkdir(parents=True)
        (per_task / "L_DemoTask.umap").write_bytes(b"\x00binary")
        r = self.lint(spec)
        self.assertNotIn("map-binary-exists", self.rules(r, ERROR))

    def test_external_actor_reference_requires_actor_mirror(self):
        spec, map_path = self._external_map_fixture()
        with self._tracked(map_path):
            r = self.lint(spec)
        findings = [f for f in r.findings
                    if f.rule == "map-side-packages-tracked"]
        self.assertEqual(len(findings), 1)
        self.assertIn("WorldExternalActorsReferences", findings[0].message)
        self.assertIn(
            "Content/__ExternalActors__/Maps/demo-task/L_DemoTask",
            findings[0].message)

    def test_every_present_external_side_package_must_be_tracked(self):
        spec, map_path = self._external_map_fixture()
        content = self.root / "UE-projects/CraftBenchTemplate/Content"
        actor = (content / "__ExternalActors__/Maps/demo-task/L_DemoTask"
                 / "A/AA/Actor.uasset")
        obj = (content / "__ExternalObjects__/Maps/demo-task/L_DemoTask"
               / "O/OO/Object.uasset")
        for p in (actor, obj):
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"package")
        with self._tracked(map_path, (actor,)):
            r = self.lint(spec)
        findings = [f for f in r.findings
                    if f.rule == "map-side-packages-tracked"]
        self.assertEqual(len(findings), 1)
        self.assertIn("NOT TRACKED BY GIT", findings[0].message)
        self.assertIn("Object.uasset", findings[0].message)
        self.assertNotIn("Actor.uasset", findings[0].message)

    def test_present_side_package_is_checked_even_without_reference_marker(self):
        spec, map_path = self._external_map_fixture()
        map_path.write_bytes(b"ordinary non-OFPA package")
        side = (self.root / "UE-projects/CraftBenchTemplate/Content"
                / "__ExternalObjects__/Maps/demo-task/L_DemoTask"
                / "O/OO/OrphanSide.uasset")
        side.parent.mkdir(parents=True)
        side.write_bytes(b"package")
        with self._tracked(map_path):
            r = self.lint(spec)
        findings = [f for f in r.findings
                    if f.rule == "map-side-packages-tracked"]
        self.assertEqual(len(findings), 1)
        self.assertIn("OrphanSide.uasset", findings[0].message)
        self.assertNotIn("WorldExternalActorsReferences", findings[0].message)

    def test_tracked_external_mirrors_are_clean(self):
        spec, map_path = self._external_map_fixture()
        content = self.root / "UE-projects/CraftBenchTemplate/Content"
        actor = (content / "__ExternalActors__/Maps/demo-task/L_DemoTask"
                 / "A/AA/Actor.uasset")
        obj = (content / "__ExternalObjects__/Maps/demo-task/L_DemoTask"
               / "O/OO/Object.uasset")
        for p in (actor, obj):
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"package")
        with self._tracked(map_path, (actor, obj)):
            r = self.lint(spec)
        self.assertNotIn("map-side-packages-tracked", self.rules(r, ERROR))
        self.assertNotIn("map-binary-exists", self.rules(r, ERROR))

    def test_missing_introspect_script_is_error(self):
        text = GOOD_SPEC.replace("layers: [L1, L2]",
                                 "layers: [L1, L2, L2I]\n"
                                 "introspect: [introspect_nope.py]")
        spec = _write_fake_repo(self.root, spec_text=text)
        r = self.lint(spec)
        self.assertIn("introspect-script-exists", self.rules(r, ERROR))

    def test_present_introspect_script_is_clean(self):
        text = GOOD_SPEC.replace("layers: [L1, L2]",
                                 "layers: [L1, L2, L2I]\n"
                                 "introspect: [introspect_ok.py]")
        spec = _write_fake_repo(self.root, spec_text=text)
        (self.root / "tools" / "verify-single" / "introspect"
         / "introspect_ok.py").write_text("# ok", encoding="utf-8")
        r = self.lint(spec)
        self.assertNotIn("introspect-script-exists", self.rules(r, ERROR))


class TestReferenceSolutionRule(_FakeRepoCase):
    """References live folder-local at tasks/<set>/<id>/reference/ — absent is
    a WARN; a file outside the substrate's agent-writable set is an ERROR
    (grading it exits 4, so lint must catch it statically)."""

    def test_missing_reference_is_warn(self):
        spec = _write_fake_repo(self.root, with_reference=False)
        r = self.lint(spec)
        refs = [f for f in r.findings if f.rule == "reference-solution"]
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0].severity, WARN)
        self.assertIn("no reference solution", refs[0].message)

    def test_clean_reference_has_no_reference_findings(self):
        spec = _write_fake_repo(self.root)
        r = self.lint(spec)
        self.assertNotIn("reference-solution", self.rules(r))
        self.assertNotIn("reference-sandbox", self.rules(r))

    def test_reference_outside_writable_is_error(self):
        spec = _write_fake_repo(self.root)
        evil = (spec.parent / "reference" / "Source" / "CraftBenchTests"
                / "EvilFixtureEdit.h")
        evil.parent.mkdir(parents=True)
        evil.write_text("// tampering with the verifier module",
                        encoding="utf-8")
        r = self.lint(spec)
        errs = [f for f in r.findings
                if f.rule == "reference-sandbox" and f.severity == ERROR]
        self.assertEqual(len(errs), 1)
        self.assertIn("EvilFixtureEdit.h", errs[0].message)

    def test_scan_skipped_without_substrate_manifest(self):
        # tasklint must keep working on substrate-less checkouts: no
        # AGENT_WRITABLE.json -> no scan, no crash, no false ERROR.
        spec = _write_fake_repo(self.root, with_manifest=False)
        evil = (spec.parent / "reference" / "Source" / "CraftBenchTests"
                / "EvilFixtureEdit.h")
        evil.parent.mkdir(parents=True)
        evil.write_text("// would violate, but no manifest to scan against",
                        encoding="utf-8")
        r = self.lint(spec)
        self.assertNotIn("reference-sandbox", self.rules(r))


class TestDiscovery(_FakeRepoCase):
    def test_is_task_spec_accepts_v2_and_legacy_rejects_docs(self):
        spec = _write_fake_repo(self.root)  # v2 front matter
        legacy_dir = self.root / "tasks" / "demo-set" / "legacy-task"
        legacy_dir.mkdir(parents=True)
        legacy = legacy_dir / "task.md"
        legacy.write_text(LEGACY_SPEC.format(task_id="legacy-task"),
                          encoding="utf-8")
        doc = self.root / "tasks" / "CATALOG.md"
        doc.write_text("# Catalog\n\nA doc, not a spec.", encoding="utf-8")
        self.assertTrue(is_task_spec(spec))
        self.assertTrue(is_task_spec(legacy))
        self.assertFalse(is_task_spec(doc))
        found = discover_specs(self.root / "tasks")
        self.assertIn(spec, found)
        self.assertIn(legacy, found)
        self.assertNotIn(doc, found)

    def test_is_task_spec_tolerates_bom_and_whitespace(self):
        # Lockstep with spec.parse_front_matter: a BOM'd / space-padded '---'
        # opener still counts as a v2 spec, so it stays in --all discovery.
        d = self.root / "tasks" / "demo-set" / "bom-task"
        d.mkdir(parents=True)
        bom = d / "task.md"
        bom.write_text("﻿---\nid: bom-task\nlayers: [L1]\n---\nbody\n",
                       encoding="utf-8")
        self.assertTrue(is_task_spec(bom))
        padded = d / "padded.md"
        padded.write_text("---  \nid: padded\nlayers: [L1]\n---\nbody\n",
                          encoding="utf-8")
        self.assertTrue(is_task_spec(padded))

    def test_find_repo_root(self):
        _write_fake_repo(self.root)
        deep = self.root / "tools" / "verify-single"
        self.assertEqual(find_repo_root(deep), self.root)


class TestCli(_FakeRepoCase):
    def _main(self, argv):
        """Run main() with stdout captured (keeps the test run readable)."""
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(argv)
        return rc, buf.getvalue()

    def test_exit_zero_on_clean(self):
        spec = _write_fake_repo(self.root)
        rc, _ = self._main([str(spec), "--repo-root", str(self.root)])
        self.assertEqual(rc, 0)

    def test_exit_one_on_error(self):
        spec = _write_fake_repo(self.root, with_fixture=False)
        rc, _ = self._main([str(spec), "--repo-root", str(self.root)])
        self.assertEqual(rc, 1)

    def test_strict_promotes_warns(self):
        # A legacy-format spec is warn-only when everything else is in place.
        spec = _write_fake_repo(self.root, spec_text=LEGACY_SPEC)
        self.assertEqual(
            self._main([str(spec), "--repo-root", str(self.root)])[0], 0)
        self.assertEqual(
            self._main([str(spec), "--repo-root", str(self.root),
                        "--strict"])[0], 1)

    def test_json_output_shape(self):
        spec = _write_fake_repo(self.root, with_fixture=False)
        rc, out = self._main([str(spec), "--repo-root", str(self.root),
                              "--json"])
        self.assertEqual(rc, 1)
        payload = json.loads(out)
        self.assertFalse(payload["ok"])
        self.assertEqual(len(payload["results"]), 1)
        rules = {f["rule"] for f in payload["results"][0]["findings"]}
        self.assertIn("fixture-source-exists", rules)

    def test_usage_error_without_targets(self):
        self.assertEqual(main(["--repo-root", str(self.root)]), 2)

    def test_explicit_non_spec_md_is_skipped_not_errored(self):
        # The PR gate passes touched paths verbatim — a docs file under
        # tasks/ must SKIP (exit 0), not error-storm.
        _write_fake_repo(self.root)
        doc = self.root / "tasks" / "NOTES.md"
        doc.write_text("# Working notes\n\nNot a spec.", encoding="utf-8")
        rc, out = self._main([str(doc), "--repo-root", str(self.root)])
        self.assertEqual(rc, 0)
        self.assertIn("SKIP", out)


@unittest.skipUnless(
    (REPO_ROOT / "tasks" / "cpp" / "t0-sanity-log-on-beginplay"
     / "task.md").is_file(),
    "real repo task set not present")
class TestGoldenAgainstRealRepo(unittest.TestCase):
    """The flagship tasks must lint error-free against the real substrate —
    this is the drift alarm: if a fixture is renamed or a map binary
    vanishes, these golden checks fail before any UE session does."""

    def _lint_real(self, rel: str):
        return lint_task(REPO_ROOT / rel, LintContext(repo_root=REPO_ROOT))

    def test_t0_sanity_lints_error_free(self):
        r = self._lint_real("tasks/cpp/t0-sanity-log-on-beginplay/task.md")
        self.assertEqual(
            r.errors, 0,
            [f.message for f in r.findings if f.severity == ERROR])

    def test_t0_sanity_bp_lints_error_free(self):
        r = self._lint_real(
            "tasks/bp/t0-sanity-bp-log-on-beginplay/task.md")
        self.assertEqual(
            r.errors, 0,
            [f.message for f in r.findings if f.severity == ERROR])


class TestMatrixRowUnbacked(unittest.TestCase):
    """`matrix-row-unbacked` — a variant ROW with no directory on disk.

    THE MEASUREMENT THAT MOTIVATED IT (2026-08-17): `cb discriminate --task
    bp/t1-blueprint-graph-on-beginplay` printed **discriminated: YES, exit 0**
    after running two legs — its reference and its empty — while the MATRIX
    rows and the corpus ledger (since removed) both credited it with FOUR variant
    legs. The runner discovers legs from DISK, so the four rows cost no wrong
    verdict; they cost EVIDENCE, and the artifact a reviewer reads to judge
    readiness said the opposite of the truth.
    """

    def _matrix(self, root, body):
        # _write_fake_repo returns the SPEC path, not the task dir.
        task_dir = _write_fake_repo(root).parent
        (task_dir / "discrimination" / "MATRIX.md").write_text(
            body, encoding="utf-8")
        return task_dir

    _HEADER = ("| Submission | Overall | Fails at | Expected substring | Notes |\n"
               "|---|---|---|---|---|\n"
               "| `../reference` | PASS | - | - | all green |\n"
               "| empty | FAIL | `thing` | `THING_MISSING path=` | fans out |\n")

    def _findings(self, task_dir):
        import tasklint
        spec = task_dir / "task.md"
        ctx = tasklint.LintContext(repo_root=task_dir.parents[2])
        res = tasklint.lint_task(spec, ctx)
        return [f for f in res.findings if f.rule == "matrix-row-unbacked"]

    def test_an_undisclosed_row_with_no_directory_is_flagged(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            task_dir = self._matrix(root, "# m\n\n## Matrix\n\n" + self._HEADER +
                                    "| `ghost-leg/` | FAIL | cp0 | `GONE` | note |\n")
            f = self._findings(task_dir)
            self.assertEqual(1, len(f), f)
            self.assertIn("ghost-leg", f[0].message)

    def test_a_row_whose_directory_exists_is_silent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            task_dir = self._matrix(root, "# m\n\n## Matrix\n\n" + self._HEADER +
                                    "| `real-leg/` | FAIL | cp0 | `GONE` | note |\n")
            (task_dir / "discrimination" / "real-leg").mkdir()
            self.assertEqual([], self._findings(task_dir))

    def test_a_DISCLOSED_unbacked_row_is_silent(self):
        """Disclosure is rewarded: gp-poison-dot-stack-bp names its two
        unauthored legs in the row itself, and a check that fires on a sentence
        explaining why it should not fire trains people to ignore it (the
        nuisance mode `check_matrix_status_staleness` records)."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            task_dir = self._matrix(
                root, "# m\n\n## Matrix\n\n" + self._HEADER +
                "| `planned-leg/` | FAIL | cp0 | `GONE` | "
                "**UNAUTHORED - absent from disk**, never run on this task |\n")
            self.assertEqual([], self._findings(task_dir))

    def test_prose_in_a_NON_submission_table_mints_no_phantom_leg(self):
        """The precision test. Real corpus rows that used to mint phantom
        labels through `parse_matrix`: a calibration row `| B/D (4 applies) |`,
        a requirements row naming `Content/Tasks/...`, and prose reading
        "not a corrupt/partial file set". None has a message/substring column
        AND a classifying row, so `_submission_tables` excludes all three."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            task_dir = self._matrix(
                root, "# m\n\n## Matrix\n\n" + self._HEADER +
                "\n## Calibration\n\n"
                "| Leg | drop | preset | shape |\n|---|---|---|---|\n"
                "| B/D (4 applies) | 24.5 | 100 | cap |\n"
                "\n## Requirements table\n\n"
                "| # | Prompt requirement | Asserted | Enforcing gate |\n"
                "|---|---|---|---|\n"
                "| 1 | a level under `Content/Tasks/demo/` | fully | `MISSING` |\n"
                "| 2 | it loads (not a corrupt/partial file set) | fully | `BAD` |\n")
            self.assertEqual([], self._findings(task_dir))

    def test_the_rule_is_registered(self):
        """A rule that is written but not registered protects nothing."""
        import tasklint
        self.assertIn(tasklint._rule_matrix_row_unbacked, tasklint._RULES)


_TP_SPEC = GOOD_SPEC.replace("substrate: CraftBenchTemplate",
                             "substrate: ThirdPerson")


class TestGameModeSuppliesPlayer(unittest.TestCase):
    """``game-mode-no-player-controller`` — a task game mode with no controller.

    THE INCIDENT (2026-08-17): four ThirdPerson maps could not be played by hand.
    Naming a task game mode REPLACES ``GlobalDefaultGameMode``, so each mode that
    set ``DefaultPawnClass`` and omitted ``PlayerControllerClass`` left the player
    on a bare ``APlayerController`` — no ``DefaultMappingContexts``, no mapping
    context applied, no keypress reaching the pawn.

    **Why this must be a lint rule and cannot be a fixture assertion.** Every L2
    fixture drives its pawn with ``AddMovementInput`` and never presses a key, so a
    map with a dead keyboard graded byte-identically to a working one. No verdict
    channel can see it; only a human pressing a key can. And a human audit found
    four while a static sweep of the same directory found five.
    """

    def _repo(self, tmp, *, spec_text, gamemode_h=None, gamemode_cpp=None,
              substrate_dir="ThirdPerson", module="ThirdPerson"):
        root = Path(tmp)
        spec = _write_fake_repo(root, spec_text=spec_text)
        task_id = spec.parent.name
        if gamemode_h is not None:
            d = (root / "UE-projects" / substrate_dir / "Source" / module
                 / "Tasks" / task_id)
            d.mkdir(parents=True, exist_ok=True)
            (d / "DemoGameMode.h").write_text(gamemode_h, encoding="utf-8")
            if gamemode_cpp is not None:
                (d / "DemoGameMode.cpp").write_text(gamemode_cpp, encoding="utf-8")
        return spec

    def _findings(self, spec):
        import tasklint
        ctx = tasklint.LintContext(repo_root=spec.parents[3])
        return [f for f in tasklint.lint_task(spec, ctx).findings
                if f.rule == "game-mode-no-player-controller"]

    _GM_H = ("#pragma once\nclass ADemoGameMode : public AGameModeBase\n"
             "{\n\tADemoGameMode();\n};\n")

    def test_missing_player_controller_class_warns(self):
        with tempfile.TemporaryDirectory() as td:
            spec = self._repo(
                td, spec_text=_TP_SPEC, gamemode_h=self._GM_H,
                gamemode_cpp="ADemoGameMode::ADemoGameMode()\n{\n"
                             "\tDefaultPawnClass = ADemoCharacter::StaticClass();\n}\n")
            f = self._findings(spec)
            self.assertEqual(1, len(f), f)
            self.assertIn("DemoGameMode", f[0].message)
            self.assertEqual("warn", f[0].severity,
                             "must be WARN: a task may legitimately forbid input "
                             "(t2-hud-layout-and-countdown's prompt does)")

    def test_setting_it_is_silent(self):
        """The fix registers as fixed — this is what the four repaired modes look like."""
        with tempfile.TemporaryDirectory() as td:
            spec = self._repo(
                td, spec_text=_TP_SPEC, gamemode_h=self._GM_H,
                gamemode_cpp="ADemoGameMode::ADemoGameMode()\n{\n"
                             "\tDefaultPawnClass = ADemoCharacter::StaticClass();\n"
                             "\tPlayerControllerClass = ControllerFinder.Class;\n}\n")
            self.assertEqual([], self._findings(spec))

    def test_empty_constructor_warns(self):
        """AHudGameMode's actual shape — supplies neither pawn nor controller."""
        with tempfile.TemporaryDirectory() as td:
            spec = self._repo(td, spec_text=_TP_SPEC, gamemode_h=self._GM_H,
                              gamemode_cpp="ADemoGameMode::ADemoGameMode()\n{\n}\n")
            self.assertEqual(1, len(self._findings(spec)))

    def test_header_with_no_cpp_warns(self):
        """A header with no companion .cpp cannot set anything."""
        with tempfile.TemporaryDirectory() as td:
            spec = self._repo(td, spec_text=_TP_SPEC, gamemode_h=self._GM_H)
            self.assertEqual(1, len(self._findings(spec)))

    def test_a_non_gamemode_class_is_ignored(self):
        """Precision: only a class DERIVING from a game-mode base replaces the
        default. A task's Character header must not be dragged in."""
        with tempfile.TemporaryDirectory() as td:
            spec = self._repo(
                td, spec_text=_TP_SPEC,
                gamemode_h="#pragma once\nclass ADemoCharacter : public ACharacter\n{};\n",
                gamemode_cpp="ADemoCharacter::ADemoCharacter()\n{\n}\n")
            self.assertEqual([], self._findings(spec))

    def test_an_explicit_no_drivable_pawn_disclosure_discharges_the_rule(self):
        """Disclosure is rewarded, and the rule's own MESSAGE promises this escape.

        A check whose remedy text describes something with no effect is worse than
        no check: it sends an author to do work that changes nothing. Caught the
        same day the rule shipped, when the warning demoted
        `t2-hud-layout-and-countdown` out of SETTLED even though its package is
        complete (reference + empty + 3 variants) and its prompt forbids input.
        """
        with tempfile.TemporaryDirectory() as td:
            disclosed = _TP_SPEC.replace(
                "## Workspace state pre-task",
                "## Workspace state pre-task\n\nThis map deliberately has "
                "no drivable pawn: the prompt forbids input.\n")
            spec = self._repo(
                td, spec_text=disclosed, gamemode_h=self._GM_H,
                gamemode_cpp="ADemoGameMode::ADemoGameMode()\n{\n}\n")
            self.assertEqual([], self._findings(spec))

    def test_the_disclosure_must_be_the_exact_phrase(self):
        """Guard on the pair above: a vague gesture at the topic must NOT silence
        it, or the escape becomes an accident waiting to happen."""
        with tempfile.TemporaryDirectory() as td:
            vague = _TP_SPEC.replace(
                "## Workspace state pre-task",
                "## Workspace state pre-task\n\nThere is no pawn to drive here "
                "and input is not used.\n")
            spec = self._repo(
                td, spec_text=vague, gamemode_h=self._GM_H,
                gamemode_cpp="ADemoGameMode::ADemoGameMode()\n{\n}\n")
            self.assertEqual(1, len(self._findings(spec)),
                             "only the exact phrase may discharge the rule")

    def test_the_hud_task_disclosure_is_live_on_the_real_tree(self):
        """END-TO-END: the one real task that legitimately has no drivable pawn
        carries the disclosure, so the corpus is lint-clean for a stated reason
        rather than a silenced one."""
        spec = (REPO_ROOT / "tasks" / "cpp" / "t2-hud-layout-and-countdown"
                / "task.md")
        if not spec.is_file():
            self.skipTest("t2-hud-layout-and-countdown not present")
        self.assertIn("no drivable pawn",
                      spec.read_text(encoding="utf-8", errors="replace").lower())

    def test_craftbenchtemplate_is_out_of_scope(self):
        """On CraftBenchTemplate the GlobalDefaultGameMode is a bare
        GameModeBase with no controller, pawn or IMC, so there is nothing to
        inherit and firing there would be noise on every task."""
        with tempfile.TemporaryDirectory() as td:
            spec = self._repo(
                td, spec_text=GOOD_SPEC, gamemode_h=self._GM_H,
                gamemode_cpp="ADemoGameMode::ADemoGameMode()\n{\n}\n",
                substrate_dir="CraftBenchTemplate", module="CraftBenchTemplate")
            self.assertEqual([], self._findings(spec))

    def test_the_four_repaired_modes_stay_repaired(self):
        """END-TO-END REGRESSION GUARD on the 2026-08-17 play-lane fix (f52e0ea).

        Runs the real rule over the real repo. If anyone reverts a
        PlayerControllerClass line from one of the four modes the brief named,
        this fails — which is the only automated protection those lines have,
        since no verifier layer can observe a dead keyboard.
        """
        tasks = (REPO_ROOT / "UE-projects" / "ThirdPerson" / "Source"
                 / "ThirdPerson" / "Tasks")
        if not tasks.is_dir():
            self.skipTest("ThirdPerson substrate not present")
        for gm in ("t2-ladder-climb-volume/LadderGameMode",
                   "t2-npc-follows-player/FollowGameMode",
                   "t2-weapon-fire-animation-on-trigger/FireGameMode",
                   "tp2-sprint-stamina/SprintGameMode"):
            with self.subTest(game_mode=gm):
                body = (tasks / f"{gm}.cpp")
                self.assertTrue(body.is_file(), f"{gm}.cpp is missing")
                self.assertIn(
                    "PlayerControllerClass",
                    body.read_text(encoding="utf-8", errors="replace"),
                    f"{gm} lost its PlayerControllerClass — the map is "
                    f"unplayable by hand again and NO gate will tell you")

    def test_the_rule_is_registered(self):
        """A rule that is written but not registered protects nothing."""
        import tasklint
        self.assertIn(tasklint._rule_game_mode_supplies_player, tasklint._RULES)


if __name__ == "__main__":
    unittest.main()

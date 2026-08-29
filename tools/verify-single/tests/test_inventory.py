"""inventory — the hand-maintained docs vs what git tracks.

Regression anchor: on 2026-07-25 the committed
``t2-homing-projectile/L_HomingProjectile.umap`` had no ``docs/MAPS.md`` row,
MAPS.md claimed "14 committed binaries" against a real 15, and CATALOG.md
repeated the 14 — with nothing checking any of it.

Every test builds a throwaway git repo, so these assert on real ``git ls-files``
output rather than a mock (the original bug was a pathspec that under-listed).
"""
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

import inventory

#: The live repo, for the end-to-end form of the staleness rule.
_REPO_ROOT = Path(__file__).resolve().parents[3]   # tests/ -> verify-single/ -> tools/ -> REPO


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(root), check=True,
                   capture_output=True, text=True, errors="replace")


def _repo(tc: unittest.TestCase, maps=(), *, maps_doc="", catalog="",
          specs=()) -> Path:
    """A committed throwaway repo. ``maps`` are repo-relative .umap paths."""
    td = tempfile.TemporaryDirectory()
    tc.addCleanup(td.cleanup)
    root = Path(td.name)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    for rel in maps:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"\x00umap")
    for rel, body in (("docs/MAPS.md", maps_doc), ("tasks/CATALOG.md", catalog),
                      ):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    (root / "tools" / "verify-single").mkdir(parents=True, exist_ok=True)
    for task_id in specs:
        spec = root / "tasks" / "set" / task_id / "task.md"
        spec.parent.mkdir(parents=True, exist_ok=True)
        # Spec-lint-CLEAN on purpose (prompt section + 3 anti-gaming entries):
        # the integration tests below assert on the exit code, so a fixture
        # spec with its own findings would mask what inventory contributes.
        spec.write_text(
            f"---\nid: {task_id}\nlayers: [L1]\n---\n\n"
            f"# {task_id}\n\n"
            "## Prompt given to the agent\n\n"
            "> When play begins the actor must settle within two seconds.\n\n"
            "## Anti-gaming notes\n\n"
            "- Hardcoded end state — the fixture samples an intermediate checkpoint.\n"
            "- No motion at all — checkpoint 0 asserts displacement began.\n"
            "- Teleport instead of travel — per-checkpoint deltas are bounded.\n",
            encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "seed")
    return root


TEMPLATE_MAPS = (
    "UE-projects/CraftBenchTemplate/Content/Maps/L_Flat.umap",
    "UE-projects/CraftBenchTemplate/Content/Maps/t1-x/L_Foldered.umap",
)


class TestGroundTruth(unittest.TestCase):
    def test_finds_flat_and_foldered_maps(self):
        # The original checker used the pathspec `.../Maps/**/*.umap`, and git's
        # `**/` does not match zero directories — so every FLAT map went
        # missing and the count came out low. Both layouts must be seen.
        root = _repo(self, TEMPLATE_MAPS)
        maps = inventory.committed_task_maps(root)
        self.assertEqual(maps, {"CraftBenchTemplate": ["L_Flat", "L_Foldered"]})

    def test_groups_by_substrate(self):
        root = _repo(self, (*TEMPLATE_MAPS,
                            "UE-projects/ThirdPerson/Content/Maps/tp0/L_TpSanity.umap"))
        maps = inventory.committed_task_maps(root)
        self.assertEqual(sorted(maps), ["CraftBenchTemplate", "ThirdPerson"])
        self.assertEqual(maps["ThirdPerson"], ["L_TpSanity"])

    def test_substrate_shipped_levels_are_not_inventory(self):
        # ThirdPerson's own template levels live outside Content/Maps/.
        root = _repo(self, (*TEMPLATE_MAPS,
                            "UE-projects/ThirdPerson/Content/ThirdPerson/Lvl_ThirdPerson.umap",
                            "UE-projects/ThirdPerson/Content/Variant_Combat/Lvl_Combat.umap"))
        maps = inventory.committed_task_maps(root)
        self.assertNotIn("ThirdPerson", maps)

    def test_uncommitted_map_is_not_counted(self):
        root = _repo(self, TEMPLATE_MAPS)
        stray = root / "UE-projects/CraftBenchTemplate/Content/Maps/L_Untracked.umap"
        stray.write_bytes(b"\x00umap")
        maps = inventory.committed_task_maps(root)
        self.assertNotIn("L_Untracked", maps["CraftBenchTemplate"],
                         "committed binary is the only map source — untracked is not inventory")

    def test_no_git_degrades_to_none(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.assertIsNone(inventory.committed_task_maps(Path(td.name)))


class TestMapMembership(unittest.TestCase):
    def test_committed_map_with_no_row_is_an_error(self):
        root = _repo(self, TEMPLATE_MAPS,
                     maps_doc="| Map |\n|---|\n| `L_Flat` |\n")
        found = inventory.check_map_membership(root)
        msgs = [f.message for f in found if f.severity == "error"]
        self.assertTrue(any("L_Foldered" in m for m in msgs), msgs)
        self.assertFalse(any("L_Flat" in m for m in msgs), msgs)

    def test_table_row_for_a_deleted_map_is_an_error(self):
        root = _repo(self, TEMPLATE_MAPS,
                     maps_doc="| Map |\n|---|\n| `L_Flat` |\n| `L_Foldered` |\n"
                              "| `L_Retired` |\n")
        msgs = [f.message for f in inventory.check_map_membership(root)]
        self.assertTrue(any("L_Retired" in m for m in msgs), msgs)

    def test_prose_naming_a_retired_map_is_NOT_flagged(self):
        # MAPS.md legitimately says "`L_GasLaunch` + `L_GasLaunchControl` were
        # deleted 2026-07-21". Flagging that would train authors to ignore the rule.
        root = _repo(self, TEMPLATE_MAPS,
                     maps_doc="`L_GasLaunch` + `L_GasLaunchControl` were deleted.\n\n"
                              "| Map |\n|---|\n| `L_Flat` |\n| `L_Foldered` |\n")
        self.assertEqual(inventory.check_map_membership(root), [])

    def test_clean_repo_has_no_findings(self):
        root = _repo(self, TEMPLATE_MAPS,
                     maps_doc="| Map |\n|---|\n| `L_Flat` |\n| `L_Foldered` |\n")
        self.assertEqual(inventory.check_map_membership(root), [])


class TestTaskMembership(unittest.TestCase):
    def test_uncatalogued_task_is_an_error(self):
        root = _repo(self, TEMPLATE_MAPS, catalog="listed: t-known\n",
                     specs=("t-known", "t-missing"))
        msgs = [f.message for f in inventory.check_task_membership(root)]
        self.assertTrue(any("t-missing" in m for m in msgs), msgs)
        self.assertFalse(any("t-known" in m for m in msgs), msgs)

    def test_shorter_id_is_not_satisfied_by_a_longer_ids_row(self):
        # THE historical collision pair, verbatim. Between 2026-08-03 and the
        # 2026-08-06 `-cpp` rename these two ids coexisted, and the RAW
        # SUBSTRING check reported `gp-glide-stamina` present purely because
        # `gp-glide-stamina-bp` had a row. Both directions of the pair are
        # exercised so the anchor cannot regress on one side only.
        for pair in (("gp-glide-stamina", "gp-glide-stamina-bp"),
                     ("gp-poison-dot-stack", "gp-poison-dot-stack-bp")):
            short, long_ = pair
            with self.subTest(short=short):
                root = _repo(
                    self, TEMPLATE_MAPS,
                    # CATALOG's real shape: backticked ids in a table cell.
                    catalog=f"| validated | 1 | `{long_}` | ROADMAP |\n",
                    specs=pair)
                msgs = [f.message
                        for f in inventory.check_task_membership(root)]
                self.assertTrue(
                    any(short in m for m in msgs),
                    f"{short} has no CATALOG row and must be flagged, but the "
                    f"substring check read it off `{long_}`: {msgs}")
                self.assertFalse(
                    any(long_ in m and short not in m for m in msgs),
                    f"{long_} IS listed and must not be flagged: {msgs}")

    def test_word_boundary_alone_would_not_have_fixed_it(self):
        # Guard against a "fix" that swaps `in` for `\b...\b`: `-` is a
        # NON-word char, so `\bgp-glide-stamina\b` still matches inside
        # `gp-glide-stamina-bp`. This test fails for a \b-based implementation
        # exactly as it did for the substring one.
        import re as _re
        catalog = "| `gp-glide-stamina-bp` |\n"
        self.assertIsNotNone(
            _re.search(r"\bgp-glide-stamina\b", catalog),
            "premise: a naive \\b DOES match inside the longer hyphenated id")
        self.assertFalse(inventory._mentions(catalog, "gp-glide-stamina"))
        self.assertTrue(inventory._mentions(catalog, "gp-glide-stamina-bp"))

    def test_longer_id_is_not_satisfied_by_a_shorter_ids_row(self):
        # The mirror image: a doc naming only `gp-glide-stamina` must not
        # satisfy `gp-glide-stamina-bp` either.
        root = _repo(self, TEMPLATE_MAPS, catalog="- `gp-glide-stamina`\n",
                     specs=("gp-glide-stamina", "gp-glide-stamina-bp"))
        msgs = [f.message for f in inventory.check_task_membership(root)]
        self.assertTrue(any("gp-glide-stamina-bp" in m for m in msgs), msgs)

    def test_ids_named_in_prose_paths_and_cells_all_count(self):
        # An anchored match must not become a table-cell-only match: CATALOG
        # names ids backticked in cells, backticked in prose, and bare inside
        # repo paths. All three are legitimate.
        root = _repo(
            self, TEMPLATE_MAPS,
            catalog=("| validated | 1 | `t-in-cell` | x |\n\n"
                     "Authored beside tasks/bp-g2/t-in-path/task.md.\n\n"
                     "> Scope: the `t-in-prose` port, plus t-bare-word.\n"),
            specs=("t-in-cell", "t-in-path", "t-in-prose", "t-bare-word"))
        self.assertEqual(inventory.check_task_membership(root), [])


class TestCountClaims(unittest.TestCase):
    def test_wrong_substrate_scoped_map_count_is_an_error(self):
        root = _repo(self, TEMPLATE_MAPS,
                     maps_doc="14 committed binaries under "
                              "`UE-projects/CraftBenchTemplate/Content/Maps/`:\n")
        errs = [f for f in inventory.check_count_claims(root) if f.severity == "error"]
        self.assertTrue(any("claims 14" in f.message and "real count is 2" in f.message
                            for f in errs), [f.message for f in errs])

    def test_right_count_passes(self):
        root = _repo(self, TEMPLATE_MAPS,
                     maps_doc="2 committed binaries under "
                              "`UE-projects/CraftBenchTemplate/Content/Maps/`:\n")
        self.assertEqual(
            [f for f in inventory.check_count_claims(root)
             if f.severity == "error" and "MAPS" in str(f.message)], [])

    def test_task_count_claims(self):
        root = _repo(self, TEMPLATE_MAPS,
                     catalog="**15 task specs** in four directories.\n",
                     specs=("a", "b"))
        errs = [f.message for f in inventory.check_count_claims(root)
                if f.severity == "error"]
        # ONE anchored CATALOG claim. There were two until the second — a
        # different phrasing ("the <N>-task tree") of the same number in the
        # same file — went with the generated status block.
        self.assertEqual(len(errs), 1, errs)
        self.assertTrue(all("real count is 2" in m for m in errs), errs)

    def test_missing_anchor_warns_rather_than_silently_passing(self):
        root = _repo(self, TEMPLATE_MAPS, maps_doc="no count here\n")
        warns = [f for f in inventory.check_count_claims(root) if f.severity == "warn"]
        self.assertTrue(warns, "a reworded doc must be visible, not silently unchecked")


class TestLintIntegration(unittest.TestCase):
    def test_inventory_errors_fail_the_full_sweep(self):
        import tasklint
        root = _repo(self, TEMPLATE_MAPS,
                     maps_doc="| Map |\n|---|\n| `L_Flat` |\n",   # L_Foldered missing
                     specs=("a",), catalog="a\n")
        rc = tasklint.main(["--all", "--repo-root", str(root)])
        self.assertEqual(rc, 1, "a committed map with no MAPS.md row must fail cb lint")

    def test_no_inventory_opts_out(self):
        import tasklint
        root = _repo(self, TEMPLATE_MAPS,
                     maps_doc="| Map |\n|---|\n| `L_Flat` |\n",
                     specs=("a",), catalog="a\n")
        self.assertEqual(tasklint.main(["--all", "--repo-root", str(root),
                                        "--no-inventory"]), 0)

    def test_narrowed_lint_skips_inventory(self):
        # `cb lint --task <id>` passes explicit spec paths; it must stay about
        # that spec and not fail on unrelated repo-wide doc drift.
        import tasklint
        root = _repo(self, TEMPLATE_MAPS,
                     maps_doc="| Map |\n|---|\n", specs=("a",), catalog="a\n")
        spec = root / "tasks" / "set" / "a" / "task.md"
        self.assertEqual(tasklint.main([str(spec), "--repo-root", str(root)]), 0)


# TestMatrixStatusStalenessWordBoundary stood here until the public release.
# It exercised inventory.check_matrix_status_staleness, which was removed with
# ROADMAP.md -- see the note in inventory.py.


if __name__ == "__main__":
    unittest.main()

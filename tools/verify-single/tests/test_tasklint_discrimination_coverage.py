"""Unit tests for tasklint's ``discrimination-coverage`` gold-set rule.

The rule under test: for a task named on the EXPLICIT gold-set list
(``tools/verify-single/gold_set.txt``), every ``## Anti-gaming notes`` entry
must name EITHER (a) a committed ``discrimination/<variant>/`` directory, OR
(b) an inherited/argued justification carrying a pointer that resolves on disk.

Three properties these tests exist to PIN, because getting any of them wrong
re-creates a rule that was explicitly rejected (the g2 scale-up plan
I0.3 / §6 item 9):

  1. It is NOT count-equality. ``TestNotCountEquality`` builds a task with 5
     notes and a single variant dir and requires it to stay clean.
  2. It lands as WARN, from a module-level constant, because CI runs
     ``tasklint --all`` before every unit suite and an ERROR would mask them.
  3. It is opt-in BY NAME. An identical, wholly-uncovered spec that is not on
     the list must produce no finding at all.

Everything runs on a synthetic repo in a tempdir; no UE, no network.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_VERIFY = _HERE.parent
if str(_VERIFY) not in sys.path:
    sys.path.insert(0, str(_VERIFY))

import tasklint  # noqa: E402
from tasklint import (  # noqa: E402
    ERROR,
    WARN,
    DISCRIMINATION_COVERAGE_SEVERITY,
    LintContext,
    lint_task,
)

_RULE = "discrimination-coverage"
_SET = "demo-set"
_TASK = "gp-demo-cpp"

# L1-only so no fixture/map is needed; the coverage rule only reads the
# anti-gaming section + the task folder.
_SPEC_HEAD = """---
id: {task_id}
substrate: CraftBenchTemplate
set: demo-set
tier: T1
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1]
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

{notes}
"""

# Three notes, each naming a committed variant directory the fixtures below
# actually create.
NOTES_ALL_COVERED = """\
1. **Hardcoded pass.** *Defense*: the checkpoint count gate; the committed
   `discrimination/hardcoded/` variant FAILs by name.
2. **Constant spam.** *Defense*: count must be exactly 1 — see
   `discrimination/spam/`.
3. **Wrong window.** *Defense*: the t=0 checkpoint must read 0
   (`discrimination/wrong-window/`).
"""

NOTES_ONE_UNCOVERED = """\
1. **Hardcoded pass.** *Defense*: the checkpoint count gate; the committed
   `discrimination/hardcoded/` variant FAILs by name.
2. **Constant spam.** *Defense*: count must be exactly 1 — see
   `discrimination/spam/`.
3. **Wrong window.** *Defense*: the t=0 checkpoint must read 0. Nobody has
   ever run this one and this sentence does not say so.
"""

NOTES_NONE_COVERED = """\
1. **Hardcoded pass.** *Defense*: the checkpoint count gate.
2. **Constant spam.** *Defense*: count must be exactly 1.
3. **Wrong window.** *Defense*: the t=0 checkpoint must read 0.
"""

# Note 3's defense is inherited from the sibling task and says where it is
# proven — a pointer that resolves on disk. That is full coverage under (b).
NOTES_INHERITED = """\
1. **Hardcoded pass.** *Defense*: the checkpoint count gate; the committed
   `discrimination/hardcoded/` variant FAILs by name.
2. **Constant spam.** *Defense*: count must be exactly 1 — see
   `discrimination/spam/`.
3. **Wrong window.** *Defense* (inherited from the C++ original): the t=0
   checkpoint gate is byte-identical there and is proven by
   `tasks/demo-set/gp-demo-cpp/discrimination/wrong-window/`.
"""

# Same shape, but the inheritance claim carries no pointer at all.
NOTES_INHERITED_NO_POINTER = """\
1. **Hardcoded pass.** *Defense*: the checkpoint count gate; the committed
   `discrimination/hardcoded/` variant FAILs by name.
2. **Constant spam.** *Defense*: count must be exactly 1 — see
   `discrimination/spam/`.
3. **Wrong window.** *Defense* (inherited): the t=0 checkpoint must read 0.
"""

# Cites a variant directory that was never committed.
NOTES_DANGLING = """\
1. **Hardcoded pass.** *Defense*: `discrimination/hardcoded/`.
2. **Constant spam.** *Defense*: `discrimination/spam/`.
3. **Wrong window.** *Defense*: the staged `discrimination/never-authored/`
   variant.
"""

# Five notes, ONE committed variant, every note covered: the case a
# count-equality rule would (wrongly) fire on.
NOTES_FIVE_ONE_VARIANT = """\
1. **Hardcoded pass.** *Defense*: the committed `discrimination/hardcoded/`
   variant FAILs by name.
2. **Constant spam.** *Defense* (inherited): proven by
   `discrimination/hardcoded/`, same gate, opposite direction.
3. **Wrong window.** *Defense* (argued): the derivation is written out in
   `notes.md` in this task folder.
4. **Skip the deliverable.** *Defense* (inherited): the structural gate is
   proven by `tasks/demo-set/gp-demo-bp/discrimination/bp-decoy/`.
5. **Subclass the scaffold.** *Defense* (inherited): the derivation gate is
   proven on the twin, `gp-demo-bp`.
"""


def _build_repo(root: Path, *, notes: str, variants=("hardcoded", "spam",
                                                     "wrong-window"),
                gold=(f"{_SET}/{_TASK}",), task_id: str = _TASK,
                extra_files=()) -> Path:
    """Materialize the minimal tree the coverage rule consults."""
    task_dir = root / "tasks" / _SET / task_id
    task_dir.mkdir(parents=True)
    spec = task_dir / "task.md"
    spec.write_text(_SPEC_HEAD.format(task_id=task_id, notes=notes),
                    encoding="utf-8")
    for v in variants:
        vdir = task_dir / "discrimination" / v
        vdir.mkdir(parents=True, exist_ok=True)
        # A variant is a SUBMISSION OVERLAY, so it always carries at least one
        # file. The rule requires that (2026-08-08): without a non-empty check,
        # `mkdir` was the cheapest possible way to satisfy the gold bar -
        # cheaper than the note-deletion loophole the rule rejects
        # count-equality for. Empty-dir behaviour is asserted separately.
        (vdir / "Source" / "Sub" / f"{v}.cpp").parent.mkdir(
            parents=True, exist_ok=True)
        (vdir / "Source" / "Sub" / f"{v}.cpp").write_text(
            "// one-delta overlay\n", encoding="utf-8")
    (task_dir / "reference").mkdir(exist_ok=True)

    verify = root / "tools" / "verify-single"
    verify.mkdir(parents=True, exist_ok=True)
    if gold is not None:
        (verify / "gold_set.txt").write_text(
            "# gold set\n" + "\n".join(gold) + "\n", encoding="utf-8")

    # The substrate dir must exist or an unrelated rule ERRORs; harmless here.
    (root / "UE-projects" / "CraftBenchTemplate" / "Source").mkdir(parents=True)

    for rel in extra_files:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("stub", encoding="utf-8")
    return spec


class _Case(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def coverage_findings(self, spec: Path):
        r = lint_task(spec, LintContext(repo_root=self.root))
        return [f for f in r.findings if f.rule == _RULE]


class TestSeverityContract(_Case):
    """Constraint (2): the severity is a module-level constant and it lands as
    WARN, because CI runs `tasklint --all` BEFORE every unit suite and a red
    lint step masks every suite downstream."""

    def test_constant_is_warn_on_landing(self):
        self.assertEqual(DISCRIMINATION_COVERAGE_SEVERITY, WARN)

    def test_findings_use_the_constant_not_a_literal(self):
        spec = _build_repo(self.root, notes=NOTES_NONE_COVERED)
        found = self.coverage_findings(spec)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].severity, DISCRIMINATION_COVERAGE_SEVERITY)

    def test_uncovered_gold_task_does_not_fail_the_lint(self):
        # Non-strict exit must stay 0: an ERROR here would gate CI.
        spec = _build_repo(self.root, notes=NOTES_NONE_COVERED)
        r = lint_task(spec, LintContext(repo_root=self.root))
        self.assertEqual([f.message for f in r.findings
                          if f.severity == ERROR and f.rule == _RULE], [])


class TestCoverage(_Case):
    def test_full_coverage_passes(self):
        spec = _build_repo(self.root, notes=NOTES_ALL_COVERED)
        self.assertEqual(self.coverage_findings(spec), [])

    def test_uncovered_note_warns_and_names_it(self):
        spec = _build_repo(self.root, notes=NOTES_ONE_UNCOVERED)
        found = self.coverage_findings(spec)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].severity, WARN)
        self.assertIn("1 of 3", found[0].message)
        self.assertIn("note 3", found[0].message)
        # ...and does NOT accuse the two covered notes.
        self.assertNotIn("note 1", found[0].message)
        self.assertNotIn("note 2", found[0].message)

    def test_every_note_uncovered_is_one_aggregated_finding(self):
        spec = _build_repo(self.root, notes=NOTES_NONE_COVERED)
        found = self.coverage_findings(spec)
        self.assertEqual(len(found), 1)
        self.assertIn("3 of 3", found[0].message)

    def test_backticked_bare_variant_name_counts(self):
        notes = ("1. Hardcoded: see `hardcoded`.\n"
                 "2. Spam: see `spam`.\n"
                 "3. Window: see `wrong-window`.\n")
        spec = _build_repo(self.root, notes=notes)
        self.assertEqual(self.coverage_findings(spec), [])

    def test_variant_dir_that_is_not_committed_is_reported(self):
        spec = _build_repo(self.root, notes=NOTES_DANGLING,
                           variants=("hardcoded", "spam"))
        found = self.coverage_findings(spec)
        msgs = " || ".join(f.message for f in found)
        self.assertIn("never-authored", msgs)
        self.assertIn("NOT committed", msgs)

    def test_message_is_ascii(self):
        # MATRIX substring greps read these logs back as cp1252.
        spec = _build_repo(self.root, notes=NOTES_ONE_UNCOVERED)
        for f in self.coverage_findings(spec):
            f.message.encode("ascii")  # raises if a non-ASCII char slipped in


class TestInheritedJustification(_Case):
    """Branch (b): a `-bp` twin legitimately inherits its C++ original's
    behavioral variants. Inheritance is coverage — but only WITH a pointer."""

    def test_inherited_note_with_resolvable_pointer_counts_as_covered(self):
        spec = _build_repo(self.root, notes=NOTES_INHERITED)
        self.assertEqual(self.coverage_findings(spec), [])

    def test_inherited_note_without_a_pointer_is_uncovered(self):
        spec = _build_repo(self.root, notes=NOTES_INHERITED_NO_POINTER)
        found = self.coverage_findings(spec)
        self.assertEqual(len(found), 1)
        self.assertIn("note 3", found[0].message)

    def test_cross_task_variant_pointer_resolves(self):
        # The real shape: gp-*-bp cites gp-*-cpp's committed variant.
        notes = ("1. Hardcoded: `discrimination/hardcoded/`.\n"
                 "2. Spam: `discrimination/spam/`.\n"
                 "3. Window: *Defense* (inherited) — `discrimination/twin-only/`"
                 " on the C++ original.\n")
        spec = _build_repo(self.root, notes=notes,
                           variants=("hardcoded", "spam"))
        twin = (self.root / "tasks" / _SET / "gp-demo-bp" / "discrimination"
                / "twin-only")
        twin.mkdir(parents=True)
        (twin / "overlay.cpp").write_text("// x", encoding="utf-8")
        self.assertEqual(self.coverage_findings(spec), [])

    def test_pointer_to_a_sibling_task_id_resolves(self):
        notes = ("1. Hardcoded: `discrimination/hardcoded/`.\n"
                 "2. Spam: `discrimination/spam/`.\n"
                 "3. Window: *Defense* (inherited) from `gp-demo-bp`.\n")
        spec = _build_repo(self.root, notes=notes,
                           variants=("hardcoded", "spam"))
        (self.root / "tasks" / _SET / "gp-demo-bp").mkdir(parents=True)
        self.assertEqual(self.coverage_findings(spec), [])


class TestNotCountEquality(_Case):
    """Constraint (1): the REJECTED design is `len(variants) == len(notes)`.
    It fires on 8 of 8 current bp-g2 tasks, outlaws the `-bp` inheritance law,
    and makes deleting an honest note the cheapest way to go green. This test
    fails if anyone re-introduces it."""

    def test_five_notes_one_variant_all_covered_is_clean(self):
        spec = _build_repo(self.root, notes=NOTES_FIVE_ONE_VARIANT,
                           variants=("hardcoded",),
                           extra_files=(f"tasks/{_SET}/{_TASK}/notes.md",))
        decoy = (self.root / "tasks" / _SET / "gp-demo-bp" / "discrimination"
                 / "bp-decoy")
        decoy.mkdir(parents=True)
        (decoy / "overlay.cpp").write_text("// x", encoding="utf-8")
        self.assertEqual(self.coverage_findings(spec), [])

    def test_deleting_an_honest_note_does_not_buy_coverage(self):
        # Trimming 3 notes to 2 leaves the same uncovered note uncovered.
        trimmed = "\n".join(NOTES_ONE_UNCOVERED.splitlines()[2:])
        spec = _build_repo(self.root, notes=trimmed)
        found = self.coverage_findings(spec)
        self.assertEqual(len(found), 1)
        self.assertIn("1 of 2", found[0].message)

    def test_extra_uncited_variants_do_not_grant_blanket_coverage(self):
        spec = _build_repo(self.root, notes=NOTES_NONE_COVERED,
                           variants=("hardcoded", "spam", "wrong-window",
                                     "spare-a", "spare-b"))
        found = self.coverage_findings(spec)
        self.assertEqual(len(found), 1)
        self.assertIn("3 of 3", found[0].message)


class TestOptIn(_Case):
    """Constraint (3): opt-in BY NAME. Never by set, never by heuristic."""

    def test_task_not_on_the_list_is_untouched(self):
        spec = _build_repo(self.root, notes=NOTES_NONE_COVERED,
                           gold=("demo-set/some-other-task",))
        self.assertEqual(self.coverage_findings(spec), [])

    def test_missing_gold_list_makes_the_rule_inert(self):
        spec = _build_repo(self.root, notes=NOTES_NONE_COVERED, gold=None)
        self.assertEqual(self.coverage_findings(spec), [])

    def test_empty_gold_list_makes_the_rule_inert(self):
        spec = _build_repo(self.root, notes=NOTES_NONE_COVERED, gold=())
        self.assertEqual(self.coverage_findings(spec), [])

    def test_bare_task_id_entry_matches(self):
        spec = _build_repo(self.root, notes=NOTES_NONE_COVERED, gold=(_TASK,))
        self.assertEqual(len(self.coverage_findings(spec)), 1)

    def test_set_qualified_entry_matches(self):
        spec = _build_repo(self.root, notes=NOTES_NONE_COVERED,
                           gold=(f"{_SET}/{_TASK}",))
        self.assertEqual(len(self.coverage_findings(spec)), 1)

    def test_comments_and_blank_lines_are_ignored_in_the_list(self):
        spec = _build_repo(self.root, notes=NOTES_NONE_COVERED,
                           gold=("", "   # not-a-task", f"  {_TASK}  # why"))
        self.assertEqual(len(self.coverage_findings(spec)), 1)

    def test_sibling_task_in_the_same_set_is_not_swept_in(self):
        # Being next door to a gold task is not membership.
        _build_repo(self.root, notes=NOTES_ALL_COVERED)
        other_dir = self.root / "tasks" / _SET / "gp-demo-bp"
        other_dir.mkdir(parents=True)
        other = other_dir / "task.md"
        other.write_text(
            _SPEC_HEAD.format(task_id="gp-demo-bp", notes=NOTES_NONE_COVERED),
            encoding="utf-8")
        self.assertEqual(self.coverage_findings(other), [])


class TestSingleAntiGamingParser(_Case):
    """`_rule_anti_gaming` (count) and the coverage rule (per-entry text) must
    share ONE grammar — a second parser is exactly the drift tasklint's design
    note forbids."""

    def test_entry_count_matches_the_count_rule(self):
        from spec import _split_h2_sections
        spec = _build_repo(self.root, notes=NOTES_FIVE_ONE_VARIANT)
        sections = _split_h2_sections(spec.read_text(encoding="utf-8"))
        self.assertEqual(len(tasklint._anti_gaming_entries(sections)), 5)
        r = lint_task(spec, LintContext(repo_root=self.root))
        self.assertNotIn("anti-gaming-count",
                         [f.rule for f in r.findings if f.severity == ERROR])

    def test_entries_carry_their_continuation_lines(self):
        from spec import _split_h2_sections
        spec = _build_repo(self.root, notes=NOTES_ALL_COVERED)
        sections = _split_h2_sections(spec.read_text(encoding="utf-8"))
        entries = tasklint._anti_gaming_entries(sections)
        self.assertEqual(len(entries), 3)
        # Note 1's variant pointer sits on its SECOND line; a line-only
        # splitter would drop it and manufacture a false uncovered note.
        self.assertIn("discrimination/hardcoded/", entries[0])

    def test_indented_sub_bullets_are_not_counted_as_entries(self):
        from spec import _split_h2_sections
        notes = ("1. Hardcoded: `discrimination/hardcoded/`.\n"
                 "   - sub-point that is not its own note\n"
                 "2. Spam: `discrimination/spam/`.\n"
                 "3. Window: `discrimination/wrong-window/`.\n")
        spec = _build_repo(self.root, notes=notes)
        sections = _split_h2_sections(spec.read_text(encoding="utf-8"))
        self.assertEqual(len(tasklint._anti_gaming_entries(sections)), 3)
        self.assertEqual(self.coverage_findings(spec), [])


@unittest.skipUnless(
    (Path(tasklint.__file__).resolve().parents[2] / "tasks" / "cpp"
     / "gp-poison-dot-stack-cpp" / "task.md").is_file(),
    "real repo task set not present")
class TestGoldenAgainstRealRepo(unittest.TestCase):
    """Drift alarm on the shipped gold set. These assert the DIRECTION of the
    signal, not a frozen count: the rule must fire on the tasks the plan says
    are argued-not-run, must stay silent on non-listed tasks, and must never
    turn a shipping spec red."""

    REPO = Path(tasklint.__file__).resolve().parents[2]

    def _lint(self, rel: str):
        return lint_task(self.REPO / rel, LintContext(repo_root=self.REPO))

    def _coverage(self, rel: str):
        return [f for f in self._lint(rel).findings if f.rule == _RULE]

    def test_gold_set_file_exists_and_lists_the_four_gold_tasks(self):
        gold = tasklint._load_gold_set(self.REPO)
        for tid in ("gp-glide-stamina-cpp", "gp-glide-stamina-bp",
                    "gp-poison-dot-stack-cpp", "gp-poison-dot-stack-bp"):
            self.assertTrue(
                any(g == tid or g.endswith(f"/{tid}") for g in gold),
                f"{tid} missing from tools/verify-single/gold_set.txt")

    def test_glide_cpp_coverage_is_reported_at_the_right_severity(self):
        """glide-cpp is the task the scale-up is actively hardening, so this
        must NOT pin a coverage COUNT.

        It originally asserted `"6 of 6"` — the exact defect (F4: six notes,
        zero variants) that T1.0 exists to remove. Authoring the five one-delta
        variants on 2026-08-08 therefore *broke the test by fixing the repo*, a
        golden test that ratchets against its own project's progress. Assert
        the mechanism instead: a finding is produced, at the WARN-phase
        severity, and it names notes rather than counting them."""
        found = self._coverage("tasks/cpp/gp-glide-stamina-cpp/task.md")
        # ZERO findings is the SUCCESS state and must not fail this test.
        # Rewritten 2026-08-10 after it broke for the second time by the task
        # being FIXED: once every note cited a committed variant, the rule
        # correctly went silent and an assertTrue(found) turned that into a red
        # suite. A golden test that ratchets against its own project's progress
        # is worse than no test. Assert the MECHANISM instead - whatever it
        # emits is at the WARN-phase severity and names notes rather than
        # counting them.
        for f in found:
            self.assertEqual(f.severity, DISCRIMINATION_COVERAGE_SEVERITY)
            self.assertIn("note", f.message,
                          f"coverage finding must name the notes: {f.message}")

    def test_poison_cpp_credits_its_committed_variants(self):
        """Asserts the MECHANISM, never a coverage count or a remaining gap.

        THIRD OCCURRENCE of one bad shape, and the last: this test has now broken
        twice by the repo IMPROVING. It first asserted `"3 of 6"`, which authoring
        `permanent-drain/` on 2026-08-08 invalidated. It was then relaxed to
        `uncovered > 0` -- "expected this task to still have gaps" -- and on
        2026-08-17 Wave 1 of the review-iteration campaign closed the last of them,
        so the rule correctly went silent and `assertTrue(found)` turned that
        SUCCESS into a red suite. The sibling `test_glide_cpp_...` above records the
        same lesson in its own words: "a golden test that ratchets against its own
        project's progress is worse than no test."

        The properties this used to guard are NOT lost -- they live on synthetic
        fixtures where the corpus cannot move them: `test_uncovered_note_warns_and_
        names_it`, `test_every_note_uncovered_is_one_aggregated_finding`,
        `test_inherited_note_without_a_pointer_is_uncovered`,
        `test_deleting_an_honest_note_does_not_buy_coverage` and
        `test_extra_uncited_variants_do_not_grant_blanket_coverage`. That is where a
        not-blind / not-vacuous invariant belongs; a live task is the wrong anchor
        for it, because fixing the task is the goal.

        ZERO findings is the SUCCESS state here and must not fail."""
        found = self._coverage("tasks/cpp/gp-poison-dot-stack-cpp/task.md")
        for f in found:
            self.assertEqual(f.severity, DISCRIMINATION_COVERAGE_SEVERITY)
            self.assertIn("note", f.message,
                          f"coverage finding must name the notes: {f.message}")

    def test_non_gold_bp_g2_task_is_untouched(self):
        self.assertEqual(
            self._coverage("tasks/cpp/gp-crafting-queue/task.md"), [])

    def test_rule_adds_no_errors_to_any_gold_task(self):
        for tid in ("gp-glide-stamina-cpp", "gp-glide-stamina-bp",
                    "gp-poison-dot-stack-cpp", "gp-poison-dot-stack-bp"):
            r = self._lint(f"tasks/bp-g2/{tid}/task.md")
            self.assertEqual(
                [f.message for f in r.findings
                 if f.rule == _RULE and f.severity == ERROR], [],
                f"{tid}: coverage rule must not ERROR while it is WARN-phase")

    def test_no_gold_task_cites_an_uncommitted_variant_dir(self):
        for tid in ("gp-glide-stamina-cpp", "gp-glide-stamina-bp",
                    "gp-poison-dot-stack-cpp", "gp-poison-dot-stack-bp"):
            msgs = [f.message for f in self._coverage(f"tasks/bp-g2/{tid}/task.md")
                    if "NOT committed" in f.message]
            self.assertEqual(msgs, [], f"{tid} points at a missing variant dir")


class TestCheapWaysToGoGreen(_Case):
    """The three loopholes closed 2026-08-08, each pinned so it cannot reopen.

    A coverage rule is only worth its CI slot if satisfying it costs the same
    as doing the work. Each test below is a way the first cut could be
    satisfied with nothing reviewable at all."""

    def test_an_empty_variant_dir_does_not_count(self):
        """`mkdir` was cheaper than the note-deletion loophole the rule's own
        header rejects count-equality for."""
        spec = _build_repo(self.root, notes=NOTES_ALL_COVERED,
                           variants=("hardcoded", "spam"))
        (self.root / "tasks" / _SET / _TASK / "discrimination"
         / "wrong-window").mkdir(parents=True)
        msgs = [f.message for f in self.coverage_findings(spec)]
        self.assertTrue(
            any("wrong-window" in m for m in msgs),
            f"an EMPTY variant dir satisfied the gold bar: {msgs}")

    def test_a_variant_under_an_unrelated_task_does_not_count(self):
        """The cross-task hit exists only for the `-cpp`/`-bp` inheritance law.
        Repo-wide, any gold task could be covered by a same-named dir under a
        task it has nothing to do with."""
        spec = _build_repo(self.root, notes=NOTES_ALL_COVERED,
                           variants=("hardcoded", "spam"))
        alien = (self.root / "tasks" / "other-set" / "gp-unrelated"
                 / "discrimination" / "wrong-window")
        alien.mkdir(parents=True)
        (alien / "overlay.cpp").write_text("// x", encoding="utf-8")
        msgs = [f.message for f in self.coverage_findings(spec)]
        self.assertTrue(
            any("wrong-window" in m for m in msgs),
            f"an UNRELATED task's variant satisfied the gold bar: {msgs}")

    def test_an_untracked_variant_dir_does_not_count(self):
        """`committed` must mean git, not the filesystem: grading materializes
        from git HEAD, so an untracked dir never reaches a grade OR a reviewer.
        Needs a real repo — the other tests run outside one and take the
        documented filesystem fallback."""
        import subprocess
        def git(*a):
            return subprocess.run(["git", *a], cwd=str(self.root),
                                  capture_output=True, text=True, timeout=30)
        if git("init", "-q").returncode != 0:
            self.skipTest("git unavailable")
        git("config", "user.email", "t@t"); git("config", "user.name", "t")
        spec = _build_repo(self.root, notes=NOTES_ALL_COVERED,
                           variants=("hardcoded", "spam", "wrong-window"))
        # Commit everything EXCEPT the wrong-window variant.
        git("add", "-A")
        git("reset", "-q", "--",
            f"tasks/{_SET}/{_TASK}/discrimination/wrong-window")
        if git("commit", "-qm", "fixture").returncode != 0:
            self.skipTest("git commit unavailable in this environment")
        tasklint._tracked_dirs_with_files.cache_clear()
        msgs = [f.message for f in self.coverage_findings(spec)]
        self.assertTrue(
            any("wrong-window" in m for m in msgs),
            f"an UNTRACKED variant dir satisfied the gold bar: {msgs}")


if __name__ == "__main__":
    unittest.main()

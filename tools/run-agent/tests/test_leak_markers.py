"""The `fixture` tier must void a real leak and NOTHING an agent may legally read.

WHY THIS FILE EXISTS. Until 2026-08-24 the tier's marker set was three names of
the fixture base class's public API:

    FIXTURE = ("setcheckpointschedule", "oncheckpoint(", "acraftbenchfunctionaltest")

Those are correct-looking and measurably wrong. On this tree they appear in **66
of 117 task specs** and **219 docs** — `DATASET.md` Tier 1 publishes "the
verification method ... checkpoint schedule shape" for every task on purpose —
and in `Intermediate/Build/**/UHT/*.generated.h`, which the hide does not cover,
so a warm workdir tripped them too.

A later change turned that from an annotation into a spend: `run._answer_key_leak` gates
PRE-GRADE on the `fixture` class alone, so a false hit destroys a graded cell
before the build. A drive could take it with one `Read` — a denominator opt-out,
which is the one thing the harness must never offer. The staged-workspace design
reached the same conclusion independently (§5.3) and made re-scoping a
precondition of migrating the MCP lanes, because that compose KEEPS the base
classes an agent may then legitimately read.

Both directions are pinned, because only one of them is loud:

  * detecting too LITTLE banks a contaminated cell — bad, and still caught by the
    post-hoc `leak_audit --void` sweep;
  * detecting too MUCH destroys a correct cell and looks exactly like a working
    detector, which is why every "must NOT void" case below is spelled out
    against real repo material rather than a synthetic string.

Stdlib only. No UE, no editor, no tokens.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import leak_audit  # noqa: E402

REPO = _ROOT.parents[1]


def _tool_result(text: str) -> str:
    return json.dumps({"role": "tool_result", "name": "grep", "content": text})


class _RunDir:
    """A minimal run dir: a transcript, and optionally a prompt and result."""

    def __init__(self, lines, prompt=None, task=None):
        self.tmp = Path(tempfile.mkdtemp(prefix="cb-marker-"))
        (self.tmp / "agent_transcript.jsonl").write_text(
            "\n".join(lines) + "\n", encoding="utf-8")
        if prompt is not None:
            (self.tmp / "prompt.md").write_text(prompt, encoding="utf-8")
        if task is not None:
            (self.tmp / "result.json").write_text(
                json.dumps({"task": str(task)}), encoding="utf-8")

    @property
    def path(self):
        return self.tmp


class TestTheRetiredMarkersCannotFireAgain(unittest.TestCase):
    """The regression itself: those three strings must no longer void anything."""

    RETIRED = ("SetCheckpointSchedule", "OnCheckpoint(", "ACraftBenchFunctionalTest")

    def test_the_global_marker_set_is_empty(self):
        self.assertEqual((), leak_audit.FIXTURE)

    def test_reading_the_base_class_api_no_longer_voids(self):
        for s in self.RETIRED:
            rd = _RunDir([_tool_result(
                "void AGlideFunctionalTest::PrepareTest() { %s }" % s)])
            self.assertNotIn("fixture", leak_audit.audit(rd.path),
                             "%r still voids; it appears in 66 of 117 specs" % s)

    def test_a_real_spec_body_does_not_void(self):
        # Not a synthetic string: the actual bytes of a shipped task spec, which
        # DATASET.md Tier 1 publishes for every task including held-out ones.
        specs = [p for p in sorted(REPO.glob("tasks/*/*/task.md"))
                 if any(s.lower() in p.read_text(encoding="utf-8",
                                                 errors="replace").lower()
                        for s in self.RETIRED)]
        self.assertTrue(specs, "no spec quotes the fixture API — re-point this test")
        body = specs[0].read_text(encoding="utf-8", errors="replace")
        rd = _RunDir([_tool_result(body)])
        self.assertNotIn("fixture", leak_audit.audit(rd.path))


class TestPerRunMarkersAreDerivedFromTheTask(unittest.TestCase):
    def _a_task_with_markers(self):
        for spec in sorted(REPO.glob("tasks/*/*/task.md")):
            m = leak_audit.own_fixture_markers(Path("."), spec_path=spec)
            if m:
                return spec, m
        return None, ()

    def test_a_real_task_yields_real_markers(self):
        spec, marks = self._a_task_with_markers()
        self.assertIsNotNone(spec, "no task yielded a marker — the derivation "
                                  "is broken, and a broken derivation reads as "
                                  "a clean repo")
        for m in marks:
            self.assertGreaterEqual(len(m), leak_audit.MARKER_MIN_LEN)

    def test_the_marker_actually_voids_when_served(self):
        spec, marks = self._a_task_with_markers()
        rd = _RunDir([_tool_result("FinishTest(Failed, TEXT(\"%s\"))" % marks[0])],
                     task=spec)
        hits = leak_audit.audit(rd.path, spec_path=spec)
        self.assertIn("fixture", hits,
                      "the task's own fixture text did not void — the tier is "
                      "now detecting nothing at all")

    def test_no_spec_means_no_markers_rather_than_a_guess(self):
        self.assertEqual((), leak_audit.own_fixture_markers(Path(tempfile.mkdtemp())))

    def test_an_unparseable_matrix_yields_nothing(self):
        d = Path(tempfile.mkdtemp())
        task = d / "tasks" / "bp" / "t-x"
        task.mkdir(parents=True)
        (task / "task.md").write_text("not a spec", encoding="utf-8")
        (task / "discrimination").mkdir()
        (task / "discrimination" / "MATRIX.md").write_text(
            "| broken", encoding="utf-8")
        self.assertEqual((), leak_audit.own_fixture_markers(
            d, spec_path=task / "task.md"))

    def test_the_post_hoc_path_reads_the_spec_out_of_result_json(self):
        spec, marks = self._a_task_with_markers()
        rd = _RunDir([_tool_result("x")], task=spec)
        self.assertEqual(marks, leak_audit.own_fixture_markers(rd.path))


class TestNothingTheAgentMayReadCanVoid(unittest.TestCase):
    """The loud direction, measured against real repo material."""

    def test_the_base_class_allowlist_is_subtracted(self):
        # 10 tasks inherit an assertion string from the base class, which the
        # staged compose KEEPS. Reading it is legal, so it cannot be evidence.
        base = "\n".join(
            p.read_text(encoding="utf-8", errors="replace").lower()
            for n in leak_audit.BASE_FIXTURE_NAMES
            for p in REPO.glob("UE-projects/*/Source/CraftBenchTests/**/" + n))
        self.assertTrue(base, "base classes not found — re-point this test")
        leaked = []
        for spec in sorted(REPO.glob("tasks/*/*/task.md")):
            for m in leak_audit.own_fixture_markers(Path("."), spec_path=spec):
                if m in base:
                    leaked.append((spec.parent.name, m[:48]))
        self.assertEqual([], leaked[:5])

    def test_the_runs_own_prompt_is_subtracted(self):
        spec = None
        for s in sorted(REPO.glob("tasks/*/*/task.md")):
            if leak_audit.own_fixture_markers(Path("."), spec_path=s):
                spec = s
                break
        marks = leak_audit.own_fixture_markers(Path("."), spec_path=spec)
        rd = _RunDir([_tool_result("x")],
                     prompt="Do the thing. " + marks[0] + " is required.",
                     task=spec)
        self.assertNotIn(marks[0],
                         leak_audit.own_fixture_markers(rd.path, spec_path=spec),
                         "a string the harness itself put in the prompt can "
                         "void the cell")

    def test_no_marker_in_the_whole_corpus_appears_in_visible_substrate_text(self):
        """The repo-wide sweep, so a future task cannot add a generic marker.

        This is the measurement the length floor was chosen from: at 20 chars one
        marker (`with no mesh assigned`) still matched ordinary substrate source;
        at 24 none did.
        """
        keep = set(leak_audit.BASE_FIXTURE_NAMES)
        chunks = []
        for p in REPO.glob("UE-projects/*/**/*"):
            if not p.is_file():
                continue
            rel = p.relative_to(REPO).as_posix()
            if any(x in rel for x in ("/Intermediate/", "/Binaries/", "/Saved/")):
                continue
            if "/Source/CraftBenchTests/" in rel and p.name not in keep:
                continue
            if p.suffix.lower() not in (".h", ".cpp", ".cs", ".ini", ".md",
                                        ".json", ".uproject", ".txt"):
                continue
            try:
                chunks.append(p.read_text(encoding="utf-8", errors="replace").lower())
            except OSError:
                pass
        visible = "\n".join(chunks)
        self.assertGreater(len(visible), 1_000_000,
                           "the visible corpus did not load, so a green result "
                           "would mean nothing")
        offenders = []
        covered = 0
        for spec in sorted(REPO.glob("tasks/*/*/task.md")):
            marks = leak_audit.own_fixture_markers(Path("."), spec_path=spec)
            if marks:
                covered += 1
            offenders += [(spec.parent.name, m[:48]) for m in marks
                          if m in visible]
        self.assertEqual([], offenders[:5],
                         "these markers void on a legal read of substrate source")
        # Coverage is asserted too: a marker set that voids nothing has no false
        # positives either, and would pass every test above.
        self.assertGreaterEqual(covered, 90,
                                "only %d tasks carry a marker; the derivation "
                                "has regressed" % covered)


class TestTheRepoReadsAreCachedWithoutSharingAnswers(unittest.TestCase):
    """The two repo-wide reads are memoised; the memo must be keyed per repo.

    WHY THE CACHE EXISTS. `audit()` derives markers per RUN, and both reads glob
    the substrate. Measured 2026-08-25: 35 ms per uncached call, ~10 s for the
    corpus guard below alone, and a 127-run `leak_audit_sweep` paid it 127 times.
    The bench host reported the merged suite running roughly 6x the dev box's
    wall-clock and attributed it here; the cache takes the per-call cost to
    8 ms.

    WHY IT IS SOUND. The graded substrate is materialised from git HEAD BEFORE
    the process starts and is not written during a run, so `UE-projects/**` is
    invariant for the life of an interpreter.

    WHY THIS TEST. A memo keyed on the wrong thing is worse than no memo: it
    would serve one tree's fixture text as another's, and the marker set decides
    whether a graded cell is VOIDED. That failure is silent and looks exactly
    like a working detector.
    """

    def test_two_different_repos_do_not_share_a_cached_answer(self):
        real = leak_audit._base_fixture_text(REPO)
        self.assertTrue(real, "the real repo yielded no base-class text")

        empty = Path(tempfile.mkdtemp(prefix="cb-emptyrepo-"))
        self.assertEqual("", leak_audit._base_fixture_text(empty),
                         "a repo with no substrate was served another repo's "
                         "base-class text")
        # ...and the real one is still right afterwards, i.e. the second call
        # did not evict or overwrite the first.
        self.assertEqual(real, leak_audit._base_fixture_text(REPO))

    def test_fixture_literals_are_keyed_on_the_class_not_just_the_repo(self):
        seen = {}
        for spec in sorted(REPO.glob("tasks/*/*/task.md")):
            for cls in leak_audit._fixture_classes(spec, REPO):
                lits = leak_audit._fixture_fail_literals(REPO, cls)
                if lits:
                    seen[cls] = tuple(lits)
            if len(seen) >= 3:
                break
        self.assertGreaterEqual(len(seen), 2,
                                "fewer than two fixture classes yielded "
                                "literals; this test cannot discriminate")
        # Distinct classes must not have been collapsed onto one cache entry.
        self.assertGreater(len({v for v in seen.values()}), 1,
                           "different fixture classes returned identical "
                           "literals — the memo key is missing the class")


class TestTheFixtureHalfIsActuallyReachable(unittest.TestCase):
    """The marker set has TWO sources; this pins that the second one runs.

    THE BUG, shipped 2026-08-24 and found 2026-08-25. `own_fixture_markers`
    unions MATRIX substrings with the `TEXT("…")` literals inside the task's own
    `FinishTest(EFunctionalTestResult::Failed, …)` calls. The second half read
    its source through `_read`, which LOWERCASES — while both regexes are
    case-sensitive UE spellings (`FinishTest`, `EFunctionalTestResult::Failed`,
    `TEXT(`). Measured on `AdditemStackFunctionalTest.cpp`: 10 blocks against
    the raw text, **0** against the lowercased text. So the fixture half matched
    nothing from the day it shipped and every marker came from the MATRIX alone.

    Nothing failed. Coverage was 92 tasks either way, and the false-positive
    sweep was clean either way, because a half that contributes nothing cannot
    contribute a false positive. That is exactly the repo's most common defect
    class — a mechanism that exists and is unreachable — and it is invisible to
    every test that only asks "are the markers correct?"

    So this asks the other question: does the fixture half CONTRIBUTE? With it
    working, coverage is 98 tasks and 606 markers; without it, 92 and ~1-2 each.
    """

    def test_some_markers_come_from_a_fixture_body_and_not_from_the_matrix(self):
        from aura_rig.discriminate import parse_matrix

        fixture_sourced = 0
        checked = 0
        for spec in sorted(REPO.glob("tasks/*/*/task.md")):
            marks = set(leak_audit.own_fixture_markers(Path("."), spec_path=spec))
            if not marks:
                continue
            checked += 1
            mx = spec.parent / "discrimination" / "MATRIX.md"
            from_matrix = set()
            if mx.is_file():
                try:
                    for row in parse_matrix(
                            mx.read_text(encoding="utf-8",
                                         errors="replace")).values():
                        from_matrix |= {str(x).strip().lower()
                                        for x in (getattr(row, "substrings", ())
                                                  or ())}
                except Exception:
                    pass
            if marks - from_matrix:
                fixture_sourced += 1
        self.assertGreater(checked, 50, "too few covered tasks to conclude")
        self.assertGreater(
            fixture_sourced, 20,
            "no marker in the corpus came from a fixture BODY — the fixture "
            "half is unreachable again (check that its source is read "
            "case-preserved; `_read` lowercases and the regexes do not)")

    def test_the_regexes_are_case_sensitive_so_the_input_must_not_be_folded(self):
        # The mechanism of the original bug, pinned directly: feeding lowercased
        # text to these patterns yields nothing, so any future caller that
        # reaches for `_read` here reintroduces it.
        src = next(REPO.glob("UE-projects/*/Source/CraftBenchTests/**/"
                             "*FunctionalTest.cpp"), None)
        self.assertIsNotNone(src, "no fixture source found")
        raw = src.read_text(encoding="utf-8", errors="replace")
        while raw and not leak_audit._FINISHTEST_FAILED_RE.findall(raw):
            src = next(REPO.glob("UE-projects/*/Source/CraftBenchTests/**/"
                                 "*FunctionalTest.cpp"), None)
            break
        blocks_raw = leak_audit._FINISHTEST_FAILED_RE.findall(raw)
        if not blocks_raw:
            self.skipTest("the first fixture source has no Failed FinishTest")
        self.assertEqual(
            [], leak_audit._FINISHTEST_FAILED_RE.findall(raw.lower()),
            "the pattern matched lowercased text, so this guard no longer "
            "describes the hazard it was written for")

    def test_a_caller_cannot_mutate_the_cached_list(self):
        # The literals are handed out to build a candidate list the caller then
        # extends. Returning the cached object itself would let one run's
        # candidates leak into the next run's markers.
        spec = next((s for s in sorted(REPO.glob("tasks/*/*/task.md"))
                     if leak_audit._fixture_classes(s, REPO)), None)
        self.assertIsNotNone(spec, "no task declares an L2 fixture")
        cls = leak_audit._fixture_classes(spec, REPO)[0]
        first = leak_audit._fixture_fail_literals(REPO, cls)
        first.append("POISON")
        self.assertNotIn("POISON", leak_audit._fixture_fail_literals(REPO, cls),
                         "the cache handed out its own mutable list")


class TestExposureStillWarnsRatherThanVoiding(unittest.TestCase):
    def test_a_park_path_alone_is_not_a_fixture_hit(self):
        rd = _RunDir([_tool_result("C:/cb/.cb-fairness-hidden__tasks/")])
        hits = leak_audit.audit(rd.path)
        self.assertIn("park", hits)
        self.assertNotIn("fixture", hits)


if __name__ == "__main__":
    unittest.main()

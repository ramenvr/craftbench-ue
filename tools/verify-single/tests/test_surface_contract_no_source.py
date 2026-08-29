"""The surface half of a ``-bp`` task: the answer must not be written in C++.

WHY A NEW CHECK RATHER THAN AN EXISTENCE TEST. Every other L2I check on a ``-bp``
task looks for a NEW NATIVE CLASS, so the submission shape that defeats all of
them is an IN-PLACE EDIT of a shipped scaffold ``.cpp`` -- which is exactly the
shape of the committed ``-cpp`` reference. With an empty Blueprint beside it, such
a submission passed every structural check while L1 compiled the C++ and L2 graded
it, and the run reported the Blueprint surface. Nothing in the runner noticed.

These tests pin the gate in BOTH directions, because a gate that cannot pass is as
useless as one that cannot fail, and this repo has already shipped one unfailable
dead gate (``--strict-warnings``) without noticing for weeks.

No editor, no UE install, no tokens: ``run_l2_introspect`` takes ``_editor_binary``
and ``_run_editor`` as injectable seams, and the surface check is a pure function
of the accepted-path list, so the fake editor only has to emit a verdict block.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_VERIFY = Path(__file__).resolve().parent.parent
if str(_VERIFY) not in sys.path:
    sys.path.insert(0, str(_VERIFY))

from layers.l2_introspect import (  # noqa: E402
    INTEGRITY_JSON_END,
    INTEGRITY_JSON_START,
    INTROSPECT_JSON_END,
    INTROSPECT_JSON_START,
    run_l2_introspect,
    source_submission_paths,
)

_SURFACE_CHECK = "no_source_submitted"


def _verdict(checks, *, integrity=True):
    """The editor's stdout for one L2I run.

    ``integrity`` adds a CLEAN asset-integrity block. It has to be there whenever
    the submission carries a ``Content/`` package, because the layer then wraps
    the task script in the integrity bootstrap and treats a MISSING block as a
    verifier fault (status ``error``, no checks) -- correctly, but without it
    these tests would never reach the surface check at all.
    """
    parts = []
    if integrity:
        parts += [INTEGRITY_JSON_START,
                  json.dumps({"violations": []}),
                  INTEGRITY_JSON_END]
    parts += [INTROSPECT_JSON_START,
              json.dumps({"checks": checks}),
              INTROSPECT_JSON_END,
              ""]
    return "\n".join(parts)


_OK_VERDICT = _verdict([{"id": "task_check", "passed": True}])


def _fake_run(verdict_text, exit_code=0):
    def _run(*, cmd, env, log_path, timeout_seconds, extra_markers=()):
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(verdict_text, encoding="utf-8")
        return (exit_code, True)
    return _run


class _Base(unittest.TestCase):
    def run_l2i(self, submitted, *, forbid=True, verdict=_OK_VERDICT):
        tmp = Path(tempfile.mkdtemp())
        editor = tmp / "UnrealEditor-Cmd"
        editor.write_text("#!/bin/sh\n", encoding="utf-8")
        script = tmp / "introspect_task.py"
        script.write_text("# introspect\n", encoding="utf-8")
        return run_l2_introspect(
            ue_root=tmp,
            project_path=tmp / "X.uproject",
            introspect_script=script,
            log_path=tmp / "out" / "l2_introspect.log",
            submitted_assets=list(submitted),
            forbid_source_submissions=forbid,
            _editor_binary=lambda _root: editor,
            _run_editor=_fake_run(verdict),
        )

    def surface_check(self, res):
        found = [c for c in res.checks if c.id == _SURFACE_CHECK]
        self.assertEqual(
            len(found), 1,
            "expected exactly one %s check, got %r"
            % (_SURFACE_CHECK, [c.id for c in res.checks]))
        return found[0]


class TestTheGateHolds(_Base):
    def test_blueprint_only_submission_passes_and_the_check_is_RECORDED(self):
        # Recorded even when it holds. A gate that leaves no trace on the happy
        # path cannot be distinguished from a gate that never ran.
        res = self.run_l2i(["Content/Tasks/t/BP_A.uasset"])
        self.assertTrue(self.surface_check(res).passed)
        self.assertEqual(res.status, "pass")

    def test_assets_maps_and_config_are_not_source(self):
        res = self.run_l2i([
            "Content/Tasks/t/BP_A.uasset",
            "Content/Maps/t/L_A.umap",
            "Config/DefaultEngine.ini",
        ])
        self.assertTrue(self.surface_check(res).passed)

    def test_an_empty_submission_passes_the_surface_check(self):
        # Empty is a wrong ANSWER, and the empty leg is meant to fail on the
        # behaviour gates -- not here. If the surface check failed on it, every
        # empty leg would fail for the wrong reason and prove nothing.
        res = self.run_l2i([])
        self.assertTrue(self.surface_check(res).passed)


class TestTheGateFires(_Base):
    def test_a_cpp_file_fails_the_leg(self):
        res = self.run_l2i(["Content/Tasks/t/BP_A.uasset",
                            "Source/ThirdPerson/Answer.cpp"])
        self.assertFalse(self.surface_check(res).passed)
        self.assertEqual(res.status, "fail")

    def test_a_compile_input_OUTSIDE_source_still_fails(self):
        # Location alone cannot be the test: L1 compiles a .cpp the module globs
        # wherever it sits.
        res = self.run_l2i(["Content/Tasks/t/Sneaky.cpp"])
        self.assertFalse(self.surface_check(res).passed)

    def test_a_non_code_file_UNDER_source_still_fails(self):
        # Extension alone cannot be the test either: a Build.cs carries no graded
        # logic of its own but changes what L1 compiles.
        self.assertFalse(self.surface_check(
            self.run_l2i(["Source/ThirdPerson/ThirdPerson.Build.cs"])).passed)
        self.assertFalse(self.surface_check(
            self.run_l2i(["Source/Some.uplugin"])).passed)

    def test_the_failing_detail_NAMES_the_files(self):
        # Otherwise the reader has to go back to the sandbox log to learn which
        # file lost them the leg.
        detail = self.surface_check(
            self.run_l2i(["Source/A.cpp", "Source/B.h"])).detail
        self.assertIn("Source/A.cpp", detail)
        self.assertIn("Source/B.h", detail)

    def test_the_shape_that_defeats_every_other_check(self):
        # An in-place edit of a shipped scaffold .cpp plus an empty Blueprint:
        # no new native class for a sweep to find, so this gate is the only one
        # that sees it.
        res = self.run_l2i([
            "Source/ThirdPerson/Tasks/t1-x-cpp/ScreenTintActor.cpp",
            "Content/Tasks/t1-x-bp/BP_Empty.uasset",
        ])
        self.assertFalse(self.surface_check(res).passed)
        self.assertEqual(res.status, "fail")


class TestNormalisation(_Base):
    def test_windows_separators(self):
        res = self.run_l2i(["Source\\ThirdPerson\\Answer.cpp"])
        self.assertFalse(self.surface_check(res).passed)

    def test_leading_dot_slash(self):
        res = self.run_l2i(["./Source/ThirdPerson/Answer.cpp"])
        self.assertFalse(self.surface_check(res).passed)

    def test_a_dotted_directory_is_not_mangled_by_the_prefix_strip(self):
        # `lstrip("./")` strips a CHARACTER SET, so it would turn
        # ".staging/a.uasset" into "staging/a.uasset". Harmless on that path, but
        # the same bug applied to ".Source/x.cpp" is a silent exemption, so the
        # normalisation is pinned rather than assumed.
        res = self.run_l2i(["Content/.staging/BP_A.uasset"])
        self.assertTrue(self.surface_check(res).passed)


class TestItStaysOffTheOtherSurface(_Base):
    def test_a_cpp_surface_task_gets_NO_surface_check(self):
        # On a -cpp task, submitted C++ IS the correct answer. The check must be
        # ABSENT rather than present-and-passing, so no reader can mistake it for
        # "the surface was verified" on a task where it was not.
        res = self.run_l2i(["Source/ThirdPerson/Answer.cpp"], forbid=False)
        self.assertEqual([c for c in res.checks if c.id == _SURFACE_CHECK], [])
        self.assertEqual(res.status, "pass")


class TestHarnessFaultsStayHarnessFaults(_Base):
    def test_a_dead_verdict_channel_is_NOT_turned_into_a_graded_fail(self):
        # A verifier fault must not be scored against the model, even when the
        # submission would also have failed the surface check.
        res = self.run_l2i(["Source/A.cpp"], verdict="the script crashed\n")
        self.assertEqual(res.status, "error")
        self.assertEqual(res.checks, [])


class TestSourceSubmissionPaths(unittest.TestCase):
    def test_sorted_and_deduplicated(self):
        self.assertEqual(
            source_submission_paths(["Source/B.cpp", "Source/A.cpp",
                                     "Source/A.cpp"]),
            ["Source/A.cpp", "Source/B.cpp"])

    def test_every_compile_extension_is_covered(self):
        for ext in (".cpp", ".h", ".hpp", ".cc", ".cxx", ".inl", ".cs"):
            self.assertEqual(source_submission_paths(["Content/x" + ext]),
                             ["Content/x" + ext], ext)

    def test_case_insensitive_extension(self):
        self.assertEqual(source_submission_paths(["Content/X.CPP"]),
                         ["Content/X.CPP"])

    def test_empty_and_none(self):
        self.assertEqual(source_submission_paths(None), [])
        self.assertEqual(source_submission_paths([""]), [])


class TestTheRealBpTasksAreNotBrokenByThis(unittest.TestCase):
    """The gate must not fail a CORRECT answer, checked against the real tree.

    Measured before shipping it: seven ``-bp`` tasks DO carry source files, and
    every one of them sits in a ``discrimination/`` variant leg deliberately named
    ``cpp-solve`` / ``cpp-solve-with-bp`` / ``cpp-only`` -- submissions whose whole
    purpose is to be caught. No ``reference/`` tree carries any. This test keeps
    that true, so a reference that grows a ``.cpp`` fails HERE rather than in a
    graded run three weeks later.
    """

    def test_no_bp_reference_tree_carries_a_compile_input(self):
        repo = _VERIFY.parent.parent
        bp = repo / "tasks" / "bp"
        if not bp.is_dir():
            self.skipTest("no tasks/bp in this checkout")
        offenders = []
        for task_dir in sorted(bp.iterdir()):
            ref = task_dir / "reference"
            if not ref.is_dir():
                continue
            rels = [str(p.relative_to(ref)) for p in ref.rglob("*") if p.is_file()]
            hits = source_submission_paths(rels)
            if hits:
                offenders.append("%s: %s" % (task_dir.name, ", ".join(hits[:4])))
        self.assertEqual([], offenders,
                         "a -bp reference now carries source, which the surface "
                         "check would fail as a graded answer:\n  "
                         + "\n  ".join(offenders))


class TestTheGateIsActuallyReachable(unittest.TestCase):
    """Where the gate CANNOT run, and a ratchet so that set only shrinks.

    The check lives in the L2I layer, so a ``-bp`` task that declares no
    ``## Verifier introspection`` script never runs it -- the layer is not
    invoked at all. That is an invisible gap: the task grades green, the report
    shows no surface check, and nothing says the contract went unchecked. This
    repo has already shipped one gate that could not fail and did not notice for
    weeks, so the gap is PINNED rather than left to be rediscovered.

    Measured 2026-08-21: 20 of 25 ``-bp`` tasks have L2I and are gated; the five
    below do not. Adding a ``-bp`` task without L2I fails here, and giving one of
    these five an L2I script ALSO fails here -- delete its entry, the list only
    shrinks.
    """

    #: -bp tasks with no L2I script, so no surface gate. Shrink only.
    UNGATED = {
        "gp-additem-stack-fix-bp",
        "gp-door-hitch-fix-bp",
        "t0-sanity-bp-log-on-beginplay",
        "t1-blueprint-event-to-action",
        "t1-blueprint-graph-on-beginplay",
    }

    def test_the_ungated_bp_tasks_are_exactly_the_known_set(self):
        repo = _VERIFY.parent.parent
        bp = repo / "tasks" / "bp"
        if not bp.is_dir():
            self.skipTest("no tasks/bp in this checkout")
        sys.path.insert(0, str(_VERIFY))
        from spec import parse_task_file

        ungated, unparsable = set(), []
        for task_dir in sorted(bp.iterdir()):
            if not task_dir.is_dir() or task_dir.name == "_shared":
                continue
            f = task_dir / "task.md"
            if not f.is_file():
                continue
            try:
                task = parse_task_file(f)
            except Exception as exc:  # noqa: BLE001
                # Reported, never silently skipped: an unparsable spec is also
                # an ungated one, and swallowing it would make this test pass
                # for the wrong reason.
                unparsable.append("%s: %s" % (task_dir.name, exc))
                continue
            if not (getattr(task, "introspect_scripts", ()) or ()):
                ungated.add(task_dir.name)

        self.assertEqual([], unparsable)
        newly = sorted(ungated - self.UNGATED)
        self.assertEqual([], newly,
                         "these -bp tasks declare no L2I script, so the "
                         "no-source surface gate cannot run on them: %s" % newly)
        fixed = sorted(self.UNGATED - ungated)
        self.assertEqual([], fixed,
                         "these now HAVE an L2I script and are gated -- delete "
                         "them from UNGATED, the ratchet only shrinks: %s" % fixed)


if __name__ == "__main__":
    unittest.main()

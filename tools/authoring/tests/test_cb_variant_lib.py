"""Tests for cb_variant_lib — the Wave 2b authoring machinery.

Runnable OFF-BOX, with no UE install and no editor:

    py -3.12 -m unittest discover -v tools/authoring/tests

That is the point of the library not importing ``unreal``. The three things it
does are each capable of silently producing a bad discrimination leg — exec'ing a
reference author's ``main()``, harvesting a leg that does not isolate, or
harvesting one whose detail text lacks the substring the MATRIX credits — and none
of those is visible in the committed result. So they are tested here rather than
discovered later by a `[BAD]` leg in a measured run.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cb_variant_lib as lib  # noqa: E402


class TestLoadReferenceHelpers(unittest.TestCase):
    """Shape A (bare trailing ``main()``) and Shape B (``__main__`` guard)."""

    def _write(self, body):
        d = tempfile.mkdtemp()
        p = Path(d) / "author_reference.py"
        p.write_text(body, encoding="utf-8")
        return str(p)

    def test_shape_a_bare_main_is_stripped_and_not_run(self):
        p = self._write(
            "SIDE_EFFECTS = []\n"
            "HELPER = 41\n"
            "def helper():\n    return 42\n"
            "def main():\n    SIDE_EFFECTS.append('AUTHORED THE REFERENCE')\n"
            "\n\nmain()\n")
        ns = lib.load_reference_helpers(p, ["helper", "HELPER"])
        self.assertEqual(42, ns["helper"]())
        self.assertEqual(41, ns["HELPER"])
        self.assertEqual([], ns["SIDE_EFFECTS"],
                         "main() must NOT run — it would author the reference "
                         "and harvest over the variant")

    def test_shape_b_guarded_main_is_inert(self):
        p = self._write(
            "SIDE_EFFECTS = []\n"
            "def helper():\n    return 7\n"
            "def main():\n    SIDE_EFFECTS.append('AUTHORED')\n"
            "\n\nif __name__ == \"__main__\":\n    main()\n")
        ns = lib.load_reference_helpers(p, ["helper"])
        self.assertEqual(7, ns["helper"]())
        self.assertEqual([], ns["SIDE_EFFECTS"])

    def test_shape_b_with_single_quotes_is_recognised(self):
        p = self._write(
            "def helper():\n    return 1\n"
            "def main():\n    raise AssertionError('ran')\n"
            "\nif __name__ == '__main__':\n    main()\n")
        self.assertEqual(1, lib.load_reference_helpers(p, ["helper"])["helper"]())

    def test_an_unrecognised_tail_REFUSES(self):
        """The load-bearing refusal: exec'ing an unknown shape could author a
        reference over a variant, which needs a git checkout to undo."""
        p = self._write("def main():\n    pass\n\nmain()  # trailing comment\n")
        with self.assertRaises(lib.AuthoringError) as cm:
            lib.load_reference_helpers(p, [])
        self.assertIn("refusing to exec it blind", str(cm.exception))

    def test_missing_required_name_raises(self):
        p = self._write("def main():\n    pass\n\nmain()\n")
        with self.assertRaises(lib.AuthoringError) as cm:
            lib.load_reference_helpers(p, ["set_prop"])
        self.assertIn("set_prop", str(cm.exception))

    def test_missing_file_raises(self):
        with self.assertRaises(lib.AuthoringError):
            lib.load_reference_helpers(os.path.join(tempfile.mkdtemp(), "nope.py"), [])


class TestAcceptance(unittest.TestCase):
    """A leg may be harvested only if it isolates EXACTLY its target check."""

    def v(self, **kw):
        return dict(kw)

    def test_exact_single_failure_with_the_substring_is_accepted(self):
        vec = self.v(a=(True, "OK"), b=(False, "WIDGET_WRONG value=3"), c=(True, "OK"))
        ok, why = lib.acceptance(vec, "b", "WIDGET_WRONG value=")
        self.assertTrue(ok, why)

    def test_extra_failures_are_REFUSED(self):
        """Membership is not enough. A leg failing its target AND others is
        credited at the MATRIX's substring while actually dying elsewhere —
        indistinguishable in the report from a clean isolation."""
        vec = self.v(a=(False, "OTHER"), b=(False, "WIDGET_WRONG value=3"))
        ok, why = lib.acceptance(vec, "b", "WIDGET_WRONG value=")
        self.assertFalse(ok)
        self.assertIn("wanted exactly", why)

    def test_no_failure_at_all_is_REFUSED(self):
        vec = self.v(a=(True, "OK"), b=(True, "OK"))
        ok, why = lib.acceptance(vec, "b", "X")
        self.assertFalse(ok)
        self.assertIn("wanted exactly", why)

    def test_right_check_but_WRONG_SUBSTRING_is_REFUSED(self):
        """The wrong-reason-credit guard: the leg does isolate, but the MATRIX
        would credit a substring the failure text never contains."""
        vec = self.v(b=(False, "WIDGET_ABSENT path=/Game/x"))
        ok, why = lib.acceptance(vec, "b", "WIDGET_WRONG value=")
        self.assertFalse(ok)
        self.assertIn("wrong-reason credit", why)

    def test_unknown_target_check_is_REFUSED_with_the_available_ids(self):
        vec = self.v(a=(True, "OK"))
        ok, why = lib.acceptance(vec, "typo_check", "X")
        self.assertFalse(ok)
        self.assertIn("not in the grader's vector", why)
        self.assertIn("a", why)

    def test_a_DECLARED_cascade_is_accepted(self):
        """Some graders fan out by design — kp_anim_track_bake's check 5 reports
        `ANIMBAKE_NO_VARYING_TRACK (check 4 failed)` whenever check 4 fails, so no
        leg can isolate check 4 alone. Refusing those would mean refusing to probe
        them at all."""
        vec = self.v(c4=(False, "ANIMBAKE_ALL_NEW_TRACKS_FLAT x"),
                     c5=(False, "ANIMBAKE_NO_VARYING_TRACK (check 4 failed)"),
                     c2=(True, "OK"))
        ok, why = lib.acceptance(vec, "c4", "ANIMBAKE_ALL_NEW_TRACKS_FLAT",
                                 cascades=("c5",))
        self.assertTrue(ok, why)

    def test_an_UNDECLARED_extra_failure_is_still_REFUSED(self):
        """The whole point: declaring one cascade must not blanket-permit others."""
        vec = self.v(c4=(False, "FLAT"), c5=(False, "cascade"),
                     c2=(False, "SOMETHING UNFORESEEN"))
        ok, why = lib.acceptance(vec, "c4", "FLAT", cascades=("c5",))
        self.assertFalse(ok)
        self.assertIn("wanted exactly", why)
        self.assertIn("c2", why)

    def test_a_declared_cascade_that_does_NOT_fail_is_REFUSED(self):
        """Equality, not permission: if the cascade did not fire, the leg is not
        behaving as its table claims and the table is what a reviewer trusts."""
        vec = self.v(c4=(False, "FLAT"), c5=(True, "OK"))
        ok, why = lib.acceptance(vec, "c4", "FLAT", cascades=("c5",))
        self.assertFalse(ok)

    def test_a_misspelled_cascade_id_is_REFUSED(self):
        """A renamed check would otherwise silently widen what the leg may fail."""
        vec = self.v(c4=(False, "FLAT"), c5=(False, "cascade"))
        ok, why = lib.acceptance(vec, "c4", "FLAT", cascades=("c5_typo",))
        self.assertFalse(ok)
        self.assertIn("not in the grader's vector", why)

    def test_score(self):
        self.assertEqual((2, 3), lib.score(
            {"a": (True, ""), "b": (False, ""), "c": (True, "")}))


class TestHarvest(unittest.TestCase):
    def test_copies_every_named_asset(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sub = root / "substrate"
            sub.mkdir()
            for n in ("A_One", "A_Two"):
                (sub / (n + ".uasset")).write_bytes(b"payload-" + n.encode())
            task = root / "task"
            dst = lib.harvest(str(task), "my-leg", "demo-task",
                              ("A_One", "A_Two"), str(sub))
            out = Path(dst)
            self.assertEqual(
                out, task / "discrimination" / "my-leg" / "Content" / "Tasks" / "demo-task")
            self.assertEqual(b"payload-A_One", (out / "A_One.uasset").read_bytes())
            self.assertEqual(b"payload-A_Two", (out / "A_Two.uasset").read_bytes())

    def test_a_missing_saved_asset_RAISES_rather_than_partially_harvesting(self):
        """A partial harvest commits a leg missing an asset, which grades as a
        different failure than the one intended — a silent wrong-reason credit."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sub = root / "substrate"
            sub.mkdir()
            (sub / "A_One.uasset").write_bytes(b"x")
            with self.assertRaises(lib.AuthoringError) as cm:
                lib.harvest(str(root / "task"), "leg", "demo",
                            ("A_One", "A_Missing"), str(sub))
            self.assertIn("A_Missing", str(cm.exception))


class TestGradeVector(unittest.TestCase):
    """In-process grading for tasks whose reference author cannot supply it.

    Testable off-box because the library never imports ``unreal`` — the fake
    graders below are plain Python emitting the same verdict block the real ones do.
    """

    def _grader(self, body):
        d = tempfile.mkdtemp()
        p = Path(d) / "fake_grader.py"
        p.write_text(body, encoding="utf-8")
        return str(p)

    _BLOCK = ('def main():\n'
              '    print("CRAFTBENCH-INTROSPECT-JSON-START")\n'
              '    print(\'{"checks": [{"id": "a", "passed": true, "detail": "OK"},'
              ' {"id": "b", "passed": false, "detail": "WIDGET_WRONG v=3"}]}\')\n'
              '    print("CRAFTBENCH-INTROSPECT-JSON-END")\n')

    def test_returns_the_vector_shape(self):
        vec, err = lib.grade_vector(self._grader(self._BLOCK))
        self.assertIsNone(err)
        self.assertEqual({"a": (True, "OK"), "b": (False, "WIDGET_WRONG v=3")}, vec)

    def test_the_entry_guard_must_not_fire(self):
        """If __name__ were __main__ the grader would print to the real stdout and
        the block would never reach the buffer."""
        body = self._BLOCK + ('\nif __name__ == "__main__":\n'
                              '    raise AssertionError("entry guard fired")\n')
        vec, err = lib.grade_vector(self._grader(body))
        self.assertIsNone(err, err)
        self.assertIn("b", vec)

    def test_a_grader_that_raises_is_reported_not_propagated(self):
        vec, err = lib.grade_vector(self._grader(
            'def main():\n    raise ValueError("boom")\n'))
        self.assertIsNone(vec)
        self.assertIn("boom", err)

    def test_no_verdict_block_is_reported(self):
        vec, err = lib.grade_vector(self._grader('def main():\n    print("hi")\n'))
        self.assertIsNone(vec)
        self.assertIn("no CRAFTBENCH-INTROSPECT-JSON block", err)

    def test_missing_main_is_reported(self):
        vec, err = lib.grade_vector(self._grader('X = 1\n'))
        self.assertIsNone(vec)
        self.assertIn("no main()", err)

    def test_missing_file_is_reported(self):
        vec, err = lib.grade_vector(os.path.join(tempfile.mkdtemp(), "nope.py"))
        self.assertIsNone(vec)
        self.assertIn("not found", err)


class TestCallWithReboundGlobals(unittest.TestCase):
    """Retarget a reference author's proven harvest() instead of rewriting it."""

    def _ns(self):
        ns = {"DEST": "/reference", "seen": []}
        code = ("def harvest():\n"
                "    seen.append(DEST)\n"
                "    return DEST\n")
        exec(compile(code, "<fake author>", "exec"), ns)
        return ns

    def test_rebinds_for_the_call_and_restores_after(self):
        ns = self._ns()
        got = lib.call_with_rebound_globals(ns, "harvest", DEST="/variant/leg-a")
        self.assertEqual("/variant/leg-a", got)
        self.assertEqual(["/variant/leg-a"], ns["seen"])
        self.assertEqual("/reference", ns["DEST"],
                         "must restore, or a later call in the same boot writes "
                         "into a variant directory")

    def test_restores_even_when_the_callee_raises(self):
        ns = self._ns()
        exec(compile("def boom():\n    raise ValueError(DEST)\n",
                     "<fake author>", "exec"), ns)
        with self.assertRaises(ValueError):
            lib.call_with_rebound_globals(ns, "boom", DEST="/variant")
        self.assertEqual("/reference", ns["DEST"])

    def test_rebinding_an_undefined_name_RAISES(self):
        """A renamed constant would otherwise be ignored and the harvest would
        quietly write into reference/ — overwriting the reference with a variant."""
        ns = self._ns()
        with self.assertRaises(lib.AuthoringError) as cm:
            lib.call_with_rebound_globals(ns, "harvest", REFERENCE_DIR="/x")
        self.assertIn("REFERENCE_DIR", str(cm.exception))

    def test_unknown_function_raises(self):
        with self.assertRaises(lib.AuthoringError):
            lib.call_with_rebound_globals(self._ns(), "nope", DEST="/x")


class TestAgainstTheRealCorpus(unittest.TestCase):
    """End-to-end: every committed reference author must be loadable.

    This is the test that would have caught the tail-shape split before it cost a
    debugging cycle — two corpus files use the guard form and two use the bare
    call, and a loader handling only one shape silently authors a reference.
    """

    def test_every_reference_author_in_the_repo_loads_without_running(self):
        repo = Path(__file__).resolve().parents[3]
        authors = sorted(repo.glob("tasks/*/*/aids/author_reference.py"))
        if not authors:
            self.skipTest("no reference authors on disk")
        shapes = {"bare": 0, "guarded": 0}
        for a in authors:
            lines = [l for l in a.read_text(encoding="utf-8").splitlines()]
            while lines and not lines[-1].strip():
                lines.pop()
            with self.subTest(author=str(a.relative_to(repo))):
                if lines[-1].strip() == "main()":
                    shapes["bare"] += 1
                elif lib._has_main_guard(lines):
                    shapes["guarded"] += 1
                else:
                    self.fail(
                        "unrecognised tail %r — cb_variant_lib would refuse this "
                        "file, so its task cannot use the shared authoring lane"
                        % lines[-1])
        self.assertGreater(sum(shapes.values()), 0)
        # Both shapes really are present in the corpus; if one ever disappears
        # this still passes, but the counts document why both are supported.
        print("\n  reference-author tail shapes: %s" % shapes)


if __name__ == "__main__":
    unittest.main()

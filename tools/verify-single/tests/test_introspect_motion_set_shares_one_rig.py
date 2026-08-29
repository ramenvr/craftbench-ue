"""Offline oracle for the kp-motion-set-shares-one-rig grader — no UE required.

Simulates every leg of `discrimination/MATRIX.md` against a fake ``unreal``
module and joins the result against the REAL `discriminate.parse_matrix` and the
REAL matrix file, so the thing under test is the grader `cb discriminate` will
actually run, not a paraphrase of it.

WHAT THIS PINS, and why each one is here rather than assumed:

  * THE CONSTANT DENOMINATOR — 7 checks on every leg, including the untouched
    baseline, the empty submission, and a no-``unreal`` import. A submission
    must not be able to improve its reported ``tests_passed/tests_run`` by
    making checks unreachable.
  * THE CENTRAL DESIGN CLAIM — that duplicating the shipped Mannequin assets
    scores 3/7 rather than 7/7. Verified live on 2026-08-14 (all three
    duplicates report the stock rig); pinned here so a later edit to the grader
    cannot quietly undo it. Without the task-owned rig this leg would be a full
    pass, which is the entire reason the rig is shipped.
  * EVERY MATRIX SUBSTRING IS ACTUALLY PRINTED, on the leg and check the matrix
    blames. A row naming a string the grader cannot emit turns a correct FAIL
    into a wrong-reason FAIL and condemns a sound task for a typo.
  * NO UNCREDITED TOKEN APPEARS IN ANY MATRIX ROW — a broken probe must never be
    creditable as a variant's named failure.
  * THE ONE SUBTLE CONTROL-FLOW RULE: ``get_first_anim_reference`` returning
    None is a SUCCESSFUL answer ("no segment"), not an unavailable route. If the
    grader fell through to its fallback there, a real empty-action FAIL would be
    laundered into an uncredited probe error.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
_VERIFY = _TESTS.parent
_REPO = _VERIFY.parents[1]
_RUN_AGENT = _REPO / "tools" / "run-agent"
for _p in (str(_VERIFY), str(_RUN_AGENT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from aura_rig.discriminate import parse_matrix  # noqa: E402

TASK_ID = "kp-motion-set-shares-one-rig"
GRADER = _VERIFY / "introspect" / "kp_motion_set_shares_one_rig.py"
MATRIX = _REPO / "tasks" / "python" / TASK_ID / "discrimination" / "MATRIX.md"

DIR = "/Game/Tasks/" + TASK_ID
RIG = DIR + "/SK_TaskRig"
CLIP = DIR + "/A_TaskMotion"
MONTAGE = DIR + "/AM_TaskAction"
ANIMBP = DIR + "/ABP_TaskLogic"
STOCK_RIG = "/Game/Characters/Mannequins/Meshes/SK_Mannequin"
STOCK_CLIP = "/Game/Characters/Mannequins/Anims/Unarmed/MM_Idle"


# --------------------------------------------------------------------------- #
# a fake `unreal` just rich enough to be wrong in the ways that matter          #
# --------------------------------------------------------------------------- #

class _BlockUnrealImport:
    """A meta-path finder that makes ``import unreal`` raise ImportError.

    POPPING sys.modules IS NOT ENOUGH, and that distinction is the point
    (flagged in code review). It only works where `unreal` is unimportable —
    i.e. on CI and a dev box. Run the same test inside UE's own Python, where
    `unreal` IS importable, and the grader takes its NORMAL path while the test
    still asserts on the no-unreal branch: a test that quietly stops testing what
    it names. Blocking the import makes the branch reachable everywhere.
    """

    def find_spec(self, name, path=None, target=None):
        if name == "unreal":
            raise ImportError("blocked by test")
        return None

    def __enter__(self):
        self._saved = sys.modules.pop("unreal", None)
        sys.meta_path.insert(0, self)
        return self

    def __exit__(self, *exc):
        try:
            sys.meta_path.remove(self)
        except ValueError:
            pass
        if self._saved is not None:
            sys.modules["unreal"] = self._saved
        else:
            sys.modules.pop("unreal", None)
        return False


class _Obj:
    def __init__(self, path):
        self._path = path

    def get_path_name(self):
        return self._path + "." + self._path.rsplit("/", 1)[-1]


class _Asset(_Obj):
    def __init__(self, path, cls, anchor=None, plays="__unset__"):
        super().__init__(path)
        self._cls, self._anchor, self._plays = cls, anchor, plays

    def get_class(self):
        return types.SimpleNamespace(get_name=lambda: self._cls)

    def get_editor_property(self, name):
        if name in ("skeleton", "target_skeleton"):
            # Only the property its own type carries, so a grader that probes
            # the wrong one still resolves through the other.
            want = "target_skeleton" if self._cls == "AnimBlueprint" else "skeleton"
            return _Obj(self._anchor) if (name == want and self._anchor) else None
        raise Exception("no property %r" % name)

    def get_first_anim_reference(self):
        if self._plays == "__unset__":
            raise Exception("route unavailable")
        return _Obj(self._plays) if self._plays else None


def _fake_unreal(world):
    m = types.ModuleType("unreal")

    class _EAL:
        @staticmethod
        def load_asset(path):
            return world.get(path)

    m.EditorAssetLibrary = _EAL
    m.log = lambda *a, **k: None
    return m


def _run(world):
    """Load the grader with a fake `unreal` and return (checks, passed, total)."""
    real = sys.modules.get("unreal")
    sys.modules["unreal"] = _fake_unreal(world)
    try:
        spec = importlib.util.spec_from_file_location("_msg", GRADER)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            mod.main()
        text = buf.getvalue()
    finally:
        if real is not None:
            sys.modules["unreal"] = real
        else:
            sys.modules.pop("unreal", None)
    body = text.split("CRAFTBENCH-INTROSPECT-JSON-START")[1]
    body = body.split("CRAFTBENCH-INTROSPECT-JSON-END")[0].strip()
    checks = json.loads(body)["checks"]
    return checks, sum(1 for c in checks if c["passed"]), len(checks), text


# --------------------------------------------------------------------------- #
# the legs                                                                     #
# --------------------------------------------------------------------------- #

def world_reference():
    return {
        RIG: _Asset(RIG, "Skeleton"),
        CLIP: _Asset(CLIP, "AnimSequence", anchor=RIG),
        MONTAGE: _Asset(MONTAGE, "AnimMontage", anchor=RIG, plays=CLIP),
        ANIMBP: _Asset(ANIMBP, "AnimBlueprint", anchor=RIG),
    }


def world_empty():
    return {RIG: _Asset(RIG, "Skeleton")}


def world_duplicated():
    """The cheapest wrong answer: stock assets copied under the right names."""
    return {
        RIG: _Asset(RIG, "Skeleton"),
        CLIP: _Asset(CLIP, "AnimSequence", anchor=STOCK_RIG),
        MONTAGE: _Asset(MONTAGE, "AnimMontage", anchor=STOCK_RIG, plays=STOCK_CLIP),
        ANIMBP: _Asset(ANIMBP, "AnimBlueprint", anchor=STOCK_RIG),
    }


class TestLegs(unittest.TestCase):
    def test_reference_scores_7_of_7(self):
        checks, ok, total, _ = _run(world_reference())
        self.assertEqual((7, 7), (ok, total),
                         [c for c in checks if not c["passed"]])

    def test_empty_scores_0_of_7(self):
        checks, ok, total, _ = _run(world_empty())
        self.assertEqual((0, 7), (ok, total))

    def test_duplicating_the_shipped_set_scores_3_of_7(self):
        """THE CENTRAL DESIGN CLAIM.

        Names and classes are right, so C1-C3 pass; every rig reference is the
        stock one, so C4-C6 fail; and the duplicated action plays the stock
        clip, so C7 fails. Without the task-owned rig this would be 7/7.
        """
        checks, ok, total, _ = _run(world_duplicated())
        self.assertEqual((3, 7), (ok, total))
        by = {c["id"]: c for c in checks}
        for cid in ("clip_present", "montage_present", "animbp_present"):
            self.assertTrue(by[cid]["passed"], cid)
        for cid in ("clip_uses_task_rig", "montage_uses_task_rig",
                    "animbp_uses_task_rig"):
            self.assertFalse(by[cid]["passed"], cid)
            self.assertIn("MOTIONSET_WRONG_RIG", by[cid]["detail"])
        self.assertFalse(by["montage_plays_the_clip"]["passed"])

    def test_wrong_classes_under_the_right_names_fail(self):
        w = world_reference()
        w[CLIP] = _Asset(CLIP, "StaticMesh", anchor=RIG)
        checks, _, _, _ = _run(w)
        by = {c["id"]: c for c in checks}
        self.assertFalse(by["clip_present"]["passed"])
        self.assertIn("MOTIONSET_WRONG_CLASS", by["clip_present"]["detail"])

    def test_an_empty_action_fails_the_link_and_is_NOT_an_uncredited_error(self):
        """`get_first_anim_reference` -> None is an ANSWER, not a dead route."""
        w = world_reference()
        w[MONTAGE] = _Asset(MONTAGE, "AnimMontage", anchor=RIG, plays=None)
        checks, ok, _, _ = _run(w)
        by = {c["id"]: c for c in checks}
        self.assertFalse(by["montage_plays_the_clip"]["passed"])
        self.assertIn("MOTIONSET_LINK_WRONG", by["montage_plays_the_clip"]["detail"])
        self.assertNotIn("MOTIONSET_LINK_READ_ERROR",
                         by["montage_plays_the_clip"]["detail"],
                         "a real empty-action FAIL was laundered into an "
                         "uncredited probe error")
        self.assertEqual(6, ok)


class TestConstantDenominator(unittest.TestCase):
    """7 on EVERY leg — the anti-gaming property of the score itself."""

    def test_every_leg_reports_seven(self):
        for name, w in (("reference", world_reference()),
                        ("empty", world_empty()),
                        ("duplicated", world_duplicated())):
            with self.subTest(leg=name):
                _, _, total, _ = _run(w)
                self.assertEqual(7, total)

    def test_no_unreal_import_still_reports_seven_zeros(self):
        """Forces the grader's ``except ImportError`` branch EVERYWHERE.

        See _BlockUnrealImport: popping sys.modules alone leaves this test
        silently passing on the normal path inside UE's own Python.
        """
        import contextlib
        import io
        with _BlockUnrealImport():
            spec = importlib.util.spec_from_file_location("_msg_nounreal", GRADER)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            self.assertIsNone(mod.unreal, "the grader must see no unreal module")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                mod.main()
        body = buf.getvalue().split("CRAFTBENCH-INTROSPECT-JSON-START")[1]
        checks = json.loads(
            body.split("CRAFTBENCH-INTROSPECT-JSON-END")[0].strip())["checks"]
        self.assertEqual(7, len(checks))
        self.assertTrue(all(not c["passed"] for c in checks))

class TestMatrixJoin(unittest.TestCase):
    """Join against the REAL matrix file and the REAL parser."""

    def setUp(self):
        self.rows = parse_matrix(MATRIX.read_text(encoding="utf-8"))

    def test_matrix_parses_to_exactly_the_three_legs(self):
        # montage-plays-the-wrong-clip was authored 2026-08-18 (4882733) and this
        # set was not updated with it.
        self.assertEqual({"reference", "empty", "duplicate-the-shipped-set",
                          "montage-plays-the-wrong-clip"},
                         set(self.rows))
        self.assertTrue(self.rows["reference"].expect_pass)

    def test_every_negative_leg_substring_is_actually_printed(self):
        worlds = {"empty": world_empty(),
                  "duplicate-the-shipped-set": world_duplicated()}
        for label, w in worlds.items():
            with self.subTest(leg=label):
                _, _, _, text = _run(w)
                for sub in self.rows[label].substrings:
                    self.assertIn(sub, text,
                                  "%s: MATRIX substring never printed" % label)

    def test_no_uncredited_token_is_a_CREDITABLE_substring(self):
        """The invariant is about what `cb discriminate` GREPS FOR, not about
        what the prose may mention.

        Scoped deliberately to the substrings `parse_matrix` actually returns.
        An earlier draft of this test forbade the tokens anywhere in the file
        and failed on the parser-traps section, which NAMES them precisely to
        document that they are uncreditable — the documentation is the point,
        so a file-wide ban would have punished the right behaviour.
        """
        spec = importlib.util.spec_from_file_location("_msg_tok", GRADER)
        mod = importlib.util.module_from_spec(spec)
        sys.modules.pop("unreal", None)
        spec.loader.exec_module(mod)
        self.assertTrue(mod.UNCREDITED_TOKENS, "the token tuple must not be empty")
        for label, row in self.rows.items():
            for sub in row.substrings:
                for tok in mod.UNCREDITED_TOKENS:
                    self.assertNotIn(
                        tok, sub,
                        "leg %r names %r, a verifier-side probe token: a broken "
                        "probe would be credited as this variant's named "
                        "failure" % (label, tok))


if __name__ == "__main__":
    unittest.main()

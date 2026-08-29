"""Offline oracle for the kp-character-boom-and-movement grader — no UE required.

Simulates every leg of `discrimination/MATRIX.md` against a fake ``unreal`` and
joins the result to the REAL `discriminate.parse_matrix` on the REAL matrix file.

WHAT THIS ROW'S TESTS EXIST TO PROTECT, which is unusual enough to state:

The sheet framed R24 as "build the component hierarchy from scratch". That is
NOT gradable — the substrate's shipped `BP_ThirdPersonCharacter` already has a
`CameraBoom` -> `FollowCamera` rig, so a duplicate satisfies any structural
check. The discrimination therefore rests entirely on the MOVEMENT VALUES
(shipped: 500/500/2048; required: 900/700/1024), and
`test_duplicate_of_the_stock_character_fails` is the test that keeps that true.

Two readback facts, both measured on 2026-08-14 and both pinned below because a
grader that got either wrong would fail conforming work:

  * component names come back SUFFIXED (`TaskCam` -> `TaskCam_GEN_VARIABLE`);
  * the tree carries INHERITED components (`CollisionCylinder`, `Arrow`,
    `CharacterMesh0`) in every submission, including an empty-rig one.
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

TASK_ID = "kp-character-boom-and-movement"
GRADER = _VERIFY / "introspect" / "kp_character_boom_and_movement.py"
MATRIX = _REPO / "tasks" / "python" / TASK_ID / "discrimination" / "MATRIX.md"
BP_PATH = "/Game/Tasks/%s/BP_TaskChar" % TASK_ID

# Every submission inherits these from ACharacter — see the module docstring.
INHERITED = ("CollisionCylinder", "Arrow", "CharacterMesh0")
REF_MOVE = {"max_walk_speed": 900.0, "jump_z_velocity": 700.0,
            "max_acceleration": 1024.0}
STOCK_MOVE = {"max_walk_speed": 500.0, "jump_z_velocity": 500.0,
              "max_acceleration": 2048.0}


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


class _Node:
    """One subobject. `parent` is a NAME, resolved through a fresh handle.

    MIMICS UE ON PURPOSE (hardened 2026-08-14 after review). The first cut of
    this fake returned the IDENTICAL Python object from `get_parent_handle`, so
    a grader that compared `str(handle)` passed here and could never pass in a
    real editor: UE's `GetParentHandle` is a void-with-out-param UFUNCTION, so
    Python materializes a BRAND-NEW wrapper, and UE's struct `__str__` embeds
    that wrapper's own ADDRESS (`PyWrapperStruct.cpp:807`). The fake was the
    only reason a handle-identity bug looked correct.

    So `__str__` below carries `id(self)`, and `_Lib.get_parent_handle` returns a
    FRESH object every call. Any grader that resolves parents by stringifying or
    identity-comparing handles now fails here, exactly as it would in UE.
    """

    def __init__(self, name, cls, parent):
        self.name, self.cls, self.parent = name, cls, parent

    def __str__(self):                      # noqa: D105 - mirrors UE's format
        return "<Struct 'SubobjectDataHandle' (0x%x) {}>" % id(self)

    __repr__ = __str__


class _Char:
    """Stands in for the generated class's default object."""

    def __init__(self, movement):
        self._mv = movement

    def get_editor_property(self, name):
        if name == "character_movement":
            return types.SimpleNamespace(
                get_editor_property=lambda k: self._mv[k])
        raise Exception("no property %r" % name)


def _fake_unreal(nodes, movement, *, is_character=True, bp_present=True):
    m = types.ModuleType("unreal")
    bp = object() if bp_present else None

    class _EAL:
        @staticmethod
        def load_asset(path):
            return bp

    class Character:  # the isinstance target
        pass

    cdo = _Char(movement)
    if is_character:
        cdo.__class__ = type("_CharCDO", (Character,), dict(_Char.__dict__))
        cdo = cdo.__class__(movement)

    class _Lib:
        @staticmethod
        def get_data(h):
            return h

        @staticmethod
        def get_object(d):
            if d.name is None:
                return None
            return types.SimpleNamespace(
                get_name=lambda n=d.name: n,
                get_class=lambda c=d.cls: types.SimpleNamespace(
                    get_name=lambda: c))

        @staticmethod
        def get_parent_handle(d):
            # A FRESH wrapper for the same logical subobject — never the object
            # already in `nodes`. This is what UE does and what makes a
            # handle-identity scheme fail.
            for n in nodes:
                if n.name == d.parent:
                    return _Node(n.name, n.cls, n.parent)
            raise Exception("no parent")

        @staticmethod
        def is_handle_valid(h):
            return h is not None

    class _Sub:
        @staticmethod
        def k2_gather_subobject_data_for_blueprint(_bp):
            return list(nodes)

    m.EditorAssetLibrary = _EAL
    m.SubobjectDataBlueprintFunctionLibrary = _Lib
    m.Character = Character
    m.get_engine_subsystem = lambda _t: _Sub
    m.SubobjectDataSubsystem = object
    m.load_object = lambda _o, _p: object()
    m.get_default_object = lambda _c: cdo
    m.log = lambda *a, **k: None
    return m


def _run(nodes, movement, **kw):
    real = sys.modules.get("unreal")
    sys.modules["unreal"] = _fake_unreal(nodes, movement, **kw)
    try:
        spec = importlib.util.spec_from_file_location("_cr", GRADER)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        import contextlib
        import io
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


def _tree(*extra):
    """The inherited components every submission has, plus whatever is added."""
    nodes = [_Node("Default__BP_TaskChar_C", "BP_TaskChar_C", None)]
    nodes += [_Node(n, "SceneComponent", "Default__BP_TaskChar_C")
              for n in INHERITED]
    nodes += list(extra)
    return nodes


def ref_nodes():
    """The reference — note the _GEN_VARIABLE suffixes the engine really adds."""
    return _tree(
        _Node("TaskBoom_GEN_VARIABLE", "SpringArmComponent", "Default__BP_TaskChar_C"),
        _Node("TaskCam_GEN_VARIABLE", "CameraComponent", "TaskBoom_GEN_VARIABLE"))


def stock_nodes():
    return _tree(
        _Node("CameraBoom", "SpringArmComponent", "Default__BP_TaskChar_C"),
        _Node("FollowCamera", "CameraComponent", "CameraBoom"))


class TestLegs(unittest.TestCase):
    def test_reference_is_6_of_6(self):
        checks, ok, total, _ = _run(ref_nodes(), REF_MOVE)
        self.assertEqual((6, 6), (ok, total), [c for c in checks if not c["passed"]])

    def test_empty_is_0_of_6(self):
        _, ok, total, _ = _run([], REF_MOVE, bp_present=False)
        self.assertEqual((0, 6), (ok, total))

    def test_duplicate_of_the_stock_character_fails(self):
        """THE ROW'S WHOLE CLAIM.

        The shipped character already has an arm-and-camera rig, so if the
        movement values did not discriminate, one `duplicate_asset` call would
        pass this task.
        """
        checks, ok, _, _ = _run(stock_nodes(), STOCK_MOVE)
        by = {c["id"]: c for c in checks}
        self.assertTrue(by["blueprint_present"]["passed"])
        self.assertTrue(by["derives_from_character"]["passed"])
        self.assertFalse(by["movement_values_exact"]["passed"])
        self.assertIn("CHARRIG_MOVEMENT_WRONG", by["movement_values_exact"]["detail"])
        self.assertFalse(by["movement_untouched_defaults_absent"]["passed"])
        self.assertIn("CHARRIG_MOVEMENT_STILL_STOCK",
                      by["movement_untouched_defaults_absent"]["detail"])
        # its components are named CameraBoom/FollowCamera, so the stems miss too
        self.assertFalse(by["boom_component_present"]["passed"])
        self.assertEqual(2, ok)

    def test_parents_are_DEREFERENCED_not_handle_compared(self):
        """THE BLOCKER THIS PINS (caught in review, 2026-08-14).

        The first cut of this grader built ``{str(handle): stem}`` from the
        gathered handles and looked a parent up as
        ``by_handle[str(get_parent_handle(d))]``. That cannot work in UE:
        ``GetParentHandle`` is a void-with-out-param UFUNCTION so Python
        materializes a FRESH wrapper, and UE's struct ``__str__`` embeds that
        wrapper's own ADDRESS (``PyWrapperStruct.cpp:807``). Every lookup would
        have missed, ``parent`` would be ``None`` for every component, and
        ``camera_parented_to_boom`` could NEVER pass — an unwinnable task
        scoring every conforming submission 5/6, blamed on the agent.

        The fake in this file is deliberately hostile to that scheme (fresh
        wrapper, address-bearing ``__str__``), so this test is what makes the
        distinction observable at all. Measured: the pre-fix route scores 4/6
        here with ``CHARRIG_CAMERA_WRONG_PARENT ... got=None``.
        """
        checks, ok, total, _ = _run(ref_nodes(), REF_MOVE)
        by = {c["id"]: c for c in checks}
        self.assertTrue(
            by["camera_parented_to_boom"]["passed"],
            "the reference's camera IS on the boom; a grader that compares "
            "handles instead of dereferencing them fails here exactly as it "
            "would in a real editor")
        self.assertEqual((6, 6), (ok, total))

    def test_wrong_component_TYPES_under_the_right_names_fail(self):
        """The prompt says an arm and a camera, so the classes are graded.

        An earlier cut collected each class into the row and then never read it,
        so two bare SceneComponents named TaskBoom/TaskCam scored 6/6 while
        anti-gaming note 3 claimed the tree walk defended against exactly that.
        """
        nodes = _tree(
            _Node("TaskBoom_GEN_VARIABLE", "SceneComponent", "Default__BP_TaskChar_C"),
            _Node("TaskCam_GEN_VARIABLE", "SceneComponent", "TaskBoom_GEN_VARIABLE"))
        checks, _, _, _ = _run(nodes, REF_MOVE)
        by = {c["id"]: c for c in checks}
        self.assertFalse(by["boom_component_present"]["passed"])
        self.assertIn("CHARRIG_BOOM_WRONG_CLASS", by["boom_component_present"]["detail"])
        self.assertFalse(by["camera_parented_to_boom"]["passed"])
        self.assertIn("CHARRIG_CAMERA_WRONG_CLASS",
                      by["camera_parented_to_boom"]["detail"])

    def test_a_SUBCLASS_of_the_required_type_is_accepted(self):
        """Suffix match, not equality — the prompt names a behaviour, not a class.

        Penalising a subclass would be the same mistake as an exact-name check:
        a false FAIL on a legitimate answer.
        """
        nodes = _tree(
            _Node("TaskBoom_GEN_VARIABLE", "MyCustomSpringArmComponent",
                  "Default__BP_TaskChar_C"),
            _Node("TaskCam_GEN_VARIABLE", "MyCustomCameraComponent",
                  "TaskBoom_GEN_VARIABLE"))
        checks, _, _, _ = _run(nodes, REF_MOVE)
        by = {c["id"]: c for c in checks}
        self.assertTrue(by["boom_component_present"]["passed"])
        self.assertTrue(by["camera_parented_to_boom"]["passed"])

    def test_a_boom_off_the_root_fails_where_the_prompt_says_it_should(self):
        """"an extendable arm attached at the character's root" is now checked."""
        nodes = _tree(
            _Node("TaskBoom_GEN_VARIABLE", "SpringArmComponent", "CharacterMesh0"),
            _Node("TaskCam_GEN_VARIABLE", "CameraComponent", "TaskBoom_GEN_VARIABLE"))
        checks, _, _, _ = _run(nodes, REF_MOVE)
        by = {c["id"]: c for c in checks}
        self.assertFalse(by["boom_component_present"]["passed"])
        self.assertIn("CHARRIG_BOOM_WRONG_PARENT", by["boom_component_present"]["detail"])

    def test_the_GEN_VARIABLE_suffix_must_not_break_a_correct_rig(self):
        """An exact-name comparison would FAIL conforming work — the F5 shape."""
        checks, ok, _, _ = _run(ref_nodes(), REF_MOVE)
        by = {c["id"]: c for c in checks}
        self.assertTrue(by["boom_component_present"]["passed"],
                        "TaskBoom_GEN_VARIABLE must satisfy the TaskBoom stem")
        self.assertTrue(by["camera_parented_to_boom"]["passed"])

    def test_a_flat_rig_fails_on_the_PARENT_not_on_existence(self):
        nodes = _tree(
            _Node("TaskBoom_GEN_VARIABLE", "SpringArmComponent", "Default__BP_TaskChar_C"),
            _Node("TaskCam_GEN_VARIABLE", "CameraComponent", "Default__BP_TaskChar_C"))
        checks, _, _, _ = _run(nodes, REF_MOVE)
        by = {c["id"]: c for c in checks}
        self.assertTrue(by["boom_component_present"]["passed"],
                        "the boom exists; only the camera's parent is wrong")
        self.assertFalse(by["camera_parented_to_boom"]["passed"])
        self.assertIn("CHARRIG_CAMERA_WRONG_PARENT",
                      by["camera_parented_to_boom"]["detail"])

    def test_a_partial_tune_names_every_remaining_wrong_field(self):
        move = dict(REF_MOVE, jump_z_velocity=500.0)
        checks, _, _, _ = _run(ref_nodes(), move)
        by = {c["id"]: c for c in checks}
        self.assertFalse(by["movement_values_exact"]["passed"])
        self.assertIn("jump_z_velocity", by["movement_values_exact"]["detail"])
        self.assertFalse(by["movement_untouched_defaults_absent"]["passed"],
                         "a field left at the shipped value must name that cause")

    def test_inherited_components_alone_are_not_a_rig(self):
        """Nothing counts components — the base class supplies three for free."""
        checks, _, _, _ = _run(_tree(), REF_MOVE)
        by = {c["id"]: c for c in checks}
        self.assertFalse(by["boom_component_present"]["passed"])
        self.assertFalse(by["camera_parented_to_boom"]["passed"])
        self.assertTrue(by["movement_values_exact"]["passed"],
                        "the movement half is independent of the rig half")


class TestConstantDenominator(unittest.TestCase):
    def test_every_leg_reports_six(self):
        for name, nodes, move, kw in (
                ("reference", ref_nodes(), REF_MOVE, {}),
                ("stock-dup", stock_nodes(), STOCK_MOVE, {}),
                ("empty", [], REF_MOVE, {"bp_present": False}),
                ("bare", _tree(), REF_MOVE, {})):
            with self.subTest(leg=name):
                _, _, total, _ = _run(nodes, move, **kw)
                self.assertEqual(6, total)

    def test_no_unreal_import_reports_six_zeros(self):
        """Forces the grader's ``except ImportError`` branch EVERYWHERE.

        See _BlockUnrealImport: popping sys.modules alone leaves this test
        silently passing on the normal path inside UE's own Python.
        """
        import contextlib
        import io
        with _BlockUnrealImport():
            spec = importlib.util.spec_from_file_location("_cr_nounreal", GRADER)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            self.assertIsNone(mod.unreal, "the grader must see no unreal module")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                mod.main()
        body = buf.getvalue().split("CRAFTBENCH-INTROSPECT-JSON-START")[1]
        checks = json.loads(
            body.split("CRAFTBENCH-INTROSPECT-JSON-END")[0].strip())["checks"]
        self.assertEqual(6, len(checks))
        self.assertTrue(all(not c["passed"] for c in checks))

class TestMatrixJoin(unittest.TestCase):
    def setUp(self):
        self.rows = parse_matrix(MATRIX.read_text(encoding="utf-8"))

    def test_matrix_parses_to_the_declared_legs(self):
        # tuned-but-wrong-values was authored 2026-08-18 (c0bc42a) and this set
        # was not updated with it, so the join has been asserting a stale corpus.
        self.assertEqual({"reference", "empty", "duplicate-the-stock-character",
                          "tuned-but-wrong-values"},
                         set(self.rows))
        self.assertTrue(self.rows["reference"].expect_pass)

    def test_every_negative_substring_is_actually_printed(self):
        worlds = {
            "empty": ([], REF_MOVE, {"bp_present": False}),
            "duplicate-the-stock-character": (stock_nodes(), STOCK_MOVE, {}),
        }
        for label, (nodes, move, kw) in worlds.items():
            with self.subTest(leg=label):
                _, _, _, text = _run(nodes, move, **kw)
                for sub in self.rows[label].substrings:
                    self.assertIn(sub, text, "%s: substring never printed" % label)

    def test_no_uncredited_token_is_a_creditable_substring(self):
        spec = importlib.util.spec_from_file_location("_cr_tok", GRADER)
        mod = importlib.util.module_from_spec(spec)
        sys.modules.pop("unreal", None)
        spec.loader.exec_module(mod)
        self.assertTrue(mod.UNCREDITED_TOKENS)
        for label, row in self.rows.items():
            for sub in row.substrings:
                for tok in mod.UNCREDITED_TOKENS:
                    self.assertNotIn(tok, sub, "leg %r names probe token %r" % (label, tok))


if __name__ == "__main__":
    unittest.main()

"""Offline oracle for the two `-bp` variant L2I graders.

No editor, no UE install, no tokens. A minimal fake ``unreal`` module models the
reflection surface `gp_glide_stamina_bp.py` / `gp_poison_dot_stack_bp.py`
actually use, so every leg can be simulated and joined against the REAL
``layers/l2_introspect`` parser.

WHY THIS EXISTS. The three original checks (`task_folder_exists`,
`bp_pawn_present`, `bp_pawn_grants_bp_ability`) are all EXISTENCE checks: they
prove a conforming Blueprint is *present*, never that it is the pawn L2 actually
grades. ``ResolveAgentPawnClass``
(``Source/CraftBenchTests/CraftBenchPawnFunctionalTest.cpp:63-149``) enumerates
NATIVE subclasses BEFORE Blueprint ones, and ``Source/CraftBenchTemplate/`` is
agent-writable (``AGENT_WRITABLE.json``), so a C++ solve shipped ALONGSIDE a
conforming Blueprint wins resolution — L2 grades the C++ while L2I grades the
Blueprint and BOTH layers pass, on a submission whose prompt says *"Do not add
or modify any C++ source for this task."* That is the decoy hole each task.md
documents under Anti-gaming note 2. ``resolved_pawn_is_blueprint`` closes it.

What this pins:
  * the denominator is a fixed per-task constant on every leg — the empty submission scores
    **0/4**, so the new check is not a dead gate (it is not satisfied by doing
    nothing);
  * the decoy leg (native pawn + conforming Blueprint) scores 3/4 = FAIL, and
    the three checks it passes are exactly the three that existed before — i.e.
    this file also pins the SHAPE of the bug it fixes;
  * a broken reflection sweep FAILS CLOSED rather than passing on an empty
    sweep, which is the direction that would silently re-open the hole;
  * both `-bp` scripts behave identically (they differ only in TASK_DIR).

The fake is deliberately dumb: it models asset presence, generated classes with
a super chain, CDOs with a GrantedAbilities array, and the module-level
reflection namespace ``dir(unreal)`` sweeps. It cannot prove the UE API names
are right — only a live editor does that — but it does prove the grader's LOGIC.
"""
import importlib.util
import sys
import types
import unittest
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
_VERIFY = _TESTS.parent

sys.path.insert(0, str(_VERIFY))

from layers.l2_introspect import parse_introspect_verdict  # noqa: E402

SCAFFOLD = "CraftBenchCharacter"
SCAFFOLD_PATH = "/Script/CraftBenchTemplate.CraftBenchCharacter"
# Per-task: the glide task grew a 5th check 2026-08-04 (pawn_visibly_represented
# — the invisible-deliverable gate; all 9 matrix reps shipped meshless pawns);
# poison keeps the original four.
# poison went 4 -> 5 on 2026-08-11 with `effect_is_blueprint`: the three
# native guards rejected a C++ pawn and a C++ ability but not a C++
# UGameplayEffect, which is where this task's graded behaviour lives
# (period, duration, Health modifier, stacking policy). A fixed
# denominator is the POINT of this test, so a new check must move the
# constant DELIBERATELY, in the same change that adds it.
EXPECTED_TOTAL = {"gp-glide-stamina-bp": 5, "gp-poison-dot-stack-bp": 5}
POOL_MESH = "/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple.SKM_Manny_Simple"

SCRIPTS = {
    "gp-glide-stamina-bp": _VERIFY / "introspect" / "gp_glide_stamina_bp.py",
    "gp-poison-dot-stack-bp": _VERIFY / "introspect" / "gp_poison_dot_stack_bp.py",
}


# --------------------------------------------------------------------------- #
# the fake unreal module                                                       #
# --------------------------------------------------------------------------- #

class _Class:
    """Models an ``unreal.Class`` handle (native or BlueprintGeneratedClass).

    A reflected handle in UE Python answers ``static_class()`` with the UClass;
    modelling that as identity is enough for the script's use of it.
    """

    def __init__(self, path, super_cls=None, granted=(), mesh_path=None):
        self._path = path
        self._super = super_cls
        self.granted = list(granted)
        # Path of the SkeletalMesh asset assigned on the pawn's inherited mesh
        # component, or None for the meshless (pre-2026-08-04) shape. The
        # component itself is ALWAYS present — ACharacter constructs it — which
        # is exactly the distinction pawn_visibly_represented grades.
        self.mesh_path = mesh_path

    def static_class(self):
        return self

    def get_path_name(self):
        return self._path

    def get_name(self):
        return self._path.rsplit(".", 1)[-1]

    def get_super_class(self):
        return self._super


class _CDO:
    def __init__(self, cls):
        self._cls = cls

    def get_editor_property(self, name):
        if name == "granted_abilities":
            return self._cls.granted
        if name == "mesh":
            return _MeshComponent(self._cls.mesh_path)
        raise AttributeError(name)


class _MeshComponent:
    """The inherited USkeletalMeshComponent: always present; the assigned
    SkeletalMesh asset may be None (the meshless shape)."""

    def __init__(self, mesh_path):
        self._mesh_path = mesh_path

    def get_editor_property(self, name):
        if name in ("skeletal_mesh_asset", "skeletal_mesh"):
            if self._mesh_path is None:
                return None
            return _Class(self._mesh_path)
        raise AttributeError(name)


def _make_unreal(*, assets=(), blueprints=None, natives=(), scaffold_visible=True):
    """Build a fake ``unreal`` module.

    ``assets``    — object paths ``list_assets`` returns for the task dir.
    ``blueprints``— {package_path: _Class} that ``load_blueprint_class`` resolves.
    ``natives``   — extra ``_Class`` objects reflected into the namespace, which
                    is how an agent-authored C++ pawn shows up.
    ``scaffold_visible`` — when False the scaffold is reachable by name but NOT
                    by the ``dir()`` sweep, i.e. the sweep is broken.
    """
    blueprints = blueprints or {}
    mod = types.ModuleType("unreal")
    scaffold = _Class(SCAFFOLD_PATH)

    class _EditorAssetLibrary:
        @staticmethod
        def does_directory_exist(_d):
            return bool(assets)

        @staticmethod
        def list_assets(_d, recursive=True):  # noqa: ARG004 — signature fidelity
            return list(assets)

        @staticmethod
        def load_blueprint_class(path):
            return blueprints.get(path)

    class _MathLibrary:
        @staticmethod
        def class_is_child_of(cls, parent):
            cur = cls
            while cur is not None:
                if cur is parent:
                    return True
                cur = cur.get_super_class()
            return False

    mod.EditorAssetLibrary = _EditorAssetLibrary
    mod.MathLibrary = _MathLibrary
    mod.get_default_object = _CDO
    mod.load_object = lambda _outer, _path: None
    mod.log = lambda _msg: None
    # A handful of unrelated reflected names, so the sweep has to filter rather
    # than get the right answer by having nothing else to look at.
    mod.Actor = _Class("/Script/Engine.Actor")
    mod.Vector = "not a class at all"
    # The engine base `effect_is_blueprint` anchors on. Its PRESENCE is the
    # sweep's fail-closed self-test, so omitting it here made the reference
    # score a false FAIL — the same "the fake did not model the world the
    # script inspects" trap the mesh handle above exists for.
    mod.GameplayEffect = _Class("/Script/GameplayAbilities.GameplayEffect")
    if scaffold_visible:
        setattr(mod, SCAFFOLD, scaffold)
    else:
        # Reachable by getattr (so _scaffold_class works) but invisible to
        # dir() — the exact shape of a reflection sweep that silently returns
        # nothing.
        mod.__dict__["_hidden_scaffold"] = scaffold

        class _Hiding(types.ModuleType):
            def __getattr__(self, name):
                if name == SCAFFOLD:
                    return scaffold
                raise AttributeError(name)

            def __dir__(self):
                return [n for n in self.__dict__ if n != "_hidden_scaffold"]

        mod.__class__ = _Hiding
    for n in natives:
        setattr(mod, n.get_name(), n)
    return mod, scaffold


def _bp(path, super_cls, granted=(), mesh_path=None):
    return _Class(path + "." + path.rsplit("/", 1)[-1] + "_C", super_cls, granted,
                  mesh_path=mesh_path)


def _run(script_path, fake):
    """Exec the introspect script against a fake ``unreal`` and return
    {check_id: passed} plus the parsed (passed, total) the REAL layer sees."""
    saved = sys.modules.get("unreal")
    sys.modules["unreal"] = fake
    try:
        spec = importlib.util.spec_from_file_location("_bp_introspect", script_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            mod.main()
        text = buf.getvalue()
    finally:
        if saved is None:
            sys.modules.pop("unreal", None)
        else:
            sys.modules["unreal"] = saved
    parsed = parse_introspect_verdict(text)
    states = {c.id: c.passed for c in parsed.checks}
    # The layer scores a fixed denominator: every declared check, reached or not.
    score = types.SimpleNamespace(
        total=len(parsed.checks),
        passed=sum(1 for c in parsed.checks if c.passed),
        found=parsed.found,
    )
    return states, score, text


# --------------------------------------------------------------------------- #
# the legs                                                                     #
# --------------------------------------------------------------------------- #

def _legs(task_id):
    """(name, fake-builder) for each discrimination leg, per task id."""
    task_dir = "/Game/Tasks/%s" % task_id
    pawn_pkg = "%s/BP_Pawn" % task_dir
    ability_path = "%s/GA_Thing.GA_Thing_C" % task_dir

    def empty():
        return _make_unreal()

    def reference():
        scaffold = _Class(SCAFFOLD_PATH)
        ability = _Class(ability_path)
        pawn = _bp(pawn_pkg, scaffold, granted=[ability], mesh_path=POOL_MESH)
        fake, real_scaffold = _make_unreal(
            assets=["%s.BP_Pawn" % pawn_pkg],
            blueprints={pawn_pkg: pawn},
        )
        pawn._super = real_scaffold
        return fake, real_scaffold

    def cpp_solve():
        # C++ pawn only: no Blueprint deliverable at all.
        fake, scaffold = _make_unreal()
        native = _Class("/Script/CraftBenchTemplate.MyPawn", scaffold)
        setattr(fake, "MyPawn", native)
        return fake, scaffold

    def cpp_solve_with_bp():
        # THE DECOY: a conforming Blueprint AND a C++ pawn that steals L2's
        # pawn resolution. Passes the three original checks.
        ability = _Class(ability_path)
        pawn = _bp(pawn_pkg, None, granted=[ability], mesh_path=POOL_MESH)
        fake, scaffold = _make_unreal(
            assets=["%s.BP_Pawn" % pawn_pkg],
            blueprints={pawn_pkg: pawn},
        )
        pawn._super = scaffold
        setattr(fake, "MyPawn", _Class("/Script/CraftBenchTemplate.MyPawn", scaffold))
        return fake, scaffold

    def broken_sweep():
        ability = _Class(ability_path)
        pawn = _bp(pawn_pkg, None, granted=[ability], mesh_path=POOL_MESH)
        fake, scaffold = _make_unreal(
            assets=["%s.BP_Pawn" % pawn_pkg],
            blueprints={pawn_pkg: pawn},
            scaffold_visible=False,
        )
        pawn._super = scaffold
        return fake, scaffold

    return {
        "empty": empty,
        "reference": reference,
        "cpp-solve": cpp_solve,
        "cpp-solve-with-bp": cpp_solve_with_bp,
        "broken-sweep": broken_sweep,
    }


class TestBpVariantResolution(unittest.TestCase):

    def _states(self, task_id, leg):
        fake = _legs(task_id)[leg]()
        fake = fake[0] if isinstance(fake, tuple) else fake
        return _run(SCRIPTS[task_id], fake)

    def test_denominator_is_fixed_on_every_leg(self):
        """A fixed denominator: every check runs, on every leg, both tasks."""
        for task_id in SCRIPTS:
            for leg in _legs(task_id):
                with self.subTest(task=task_id, leg=leg):
                    _, verdict, _ = self._states(task_id, leg)
                    self.assertEqual(verdict.total, EXPECTED_TOTAL[task_id])

    def test_empty_submission_scores_zero(self):
        """The dead-gate audit: doing NOTHING must score 0/4, so the new check
        is not satisfied by failing the task."""
        for task_id in SCRIPTS:
            with self.subTest(task=task_id):
                states, verdict, _ = self._states(task_id, "empty")
                self.assertEqual(verdict.passed, 0, states)

    def test_reference_scores_the_full_denominator(self):
        """A Blueprint-only deliverable is not false-failed by the new check."""
        for task_id in SCRIPTS:
            with self.subTest(task=task_id):
                states, verdict, _ = self._states(task_id, "reference")
                self.assertEqual(verdict.passed, EXPECTED_TOTAL[task_id], states)

    def test_cpp_solve_fails(self):
        """No Blueprint at all — fails everything, including the new check."""
        for task_id in SCRIPTS:
            with self.subTest(task=task_id):
                states, verdict, _ = self._states(task_id, "cpp-solve")
                self.assertEqual(verdict.passed, 0, states)
                self.assertFalse(states["resolved_pawn_is_blueprint"])

    def test_decoy_passes_every_older_check_and_fails_only_the_newest(self):
        """The bug this patch fixes, pinned in both directions.

        A C++ solve shipped next to a conforming Blueprint satisfies EVERY check
        that existed before — which is why it used to grade PASS — and is caught
        by ``resolved_pawn_is_blueprint`` alone.
        """
        for task_id in SCRIPTS:
            with self.subTest(task=task_id):
                states, verdict, _ = self._states(task_id, "cpp-solve-with-bp")
                self.assertTrue(states["task_folder_exists"], states)
                self.assertTrue(states["bp_pawn_present"], states)
                self.assertTrue(states["bp_pawn_grants_bp_ability"], states)
                self.assertFalse(states["resolved_pawn_is_blueprint"], states)
                self.assertEqual(verdict.passed, EXPECTED_TOTAL[task_id] - 1)

    def test_meshless_pawn_fails_only_the_visibility_check(self):
        """The invisible-deliverable shape (every 2026-08-04 matrix rep): a
        conforming Blueprint with NO SkeletalMesh assigned fails
        pawn_visibly_represented and nothing else. Glide-only — poison has no
        visibility check."""
        task_id = "gp-glide-stamina-bp"
        task_dir = "/Game/Tasks/%s" % task_id
        pawn_pkg = "%s/BP_Pawn" % task_dir
        ability = _Class("%s/GA_Thing.GA_Thing_C" % task_dir)
        pawn = _bp(pawn_pkg, None, granted=[ability], mesh_path=None)
        fake, scaffold = _make_unreal(
            assets=["%s.BP_Pawn" % pawn_pkg], blueprints={pawn_pkg: pawn})
        pawn._super = scaffold
        states, verdict, text = _run(SCRIPTS[task_id], fake)
        self.assertFalse(states["pawn_visibly_represented"], states)
        self.assertEqual(verdict.passed, EXPECTED_TOTAL[task_id] - 1, states)
        self.assertIn("SkeletalMesh=None", text)

    def test_non_pool_mesh_fails_the_visibility_check(self):
        """A mesh the agent authored under its own writable path does not count
        — the check is POOL-anchored (task.md anti-gaming note 6)."""
        task_id = "gp-glide-stamina-bp"
        task_dir = "/Game/Tasks/%s" % task_id
        pawn_pkg = "%s/BP_Pawn" % task_dir
        ability = _Class("%s/GA_Thing.GA_Thing_C" % task_dir)
        pawn = _bp(pawn_pkg, None, granted=[ability],
                   mesh_path="%s/SK_Fake.SK_Fake" % task_dir)
        fake, scaffold = _make_unreal(
            assets=["%s.BP_Pawn" % pawn_pkg], blueprints={pawn_pkg: pawn})
        pawn._super = scaffold
        states, verdict, _ = _run(SCRIPTS[task_id], fake)
        self.assertFalse(states["pawn_visibly_represented"], states)
        self.assertEqual(verdict.passed, EXPECTED_TOTAL[task_id] - 1, states)

    def test_decoy_detail_names_the_offending_cpp_class(self):
        """The FAIL detail has to tell a human WHICH C++ class stole resolution,
        or the verdict is unactionable."""
        for task_id in SCRIPTS:
            with self.subTest(task=task_id):
                _, _, text = self._states(task_id, "cpp-solve-with-bp")
                self.assertIn("/Script/CraftBenchTemplate.MyPawn", text)

    def test_broken_sweep_fails_closed(self):
        """If the reflection sweep cannot even see the scaffold it must FAIL,
        never pass on an empty sweep — passing would silently re-open the hole
        on any future UE API change."""
        for task_id in SCRIPTS:
            with self.subTest(task=task_id):
                states, _, _ = self._states(task_id, "broken-sweep")
                self.assertFalse(states["resolved_pawn_is_blueprint"], states)


if __name__ == "__main__":
    unittest.main()

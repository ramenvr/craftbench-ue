"""Tests for the shared `-bp` twin L2I library — the defects it carried.

THIS FILE EXISTS BECAUSE THERE WERE NO TESTS AT ALL for
`introspect/_bp_variant_lib.py`, which is exactly how both defects survived while
feeding five tasks. Each test below is written so it FAILS against the old
behaviour; where that matters most the docstring names the old code.

The first two defects, both FALSE_FAIL (a correct submission graded wrong):

  1. `assigned_mesh_path` read ONLY the ACharacter-inherited `mesh` component, so
     a submission that assigned the mannequin to its OWN skeletal mesh component
     — which the prompt permits, and which the L2 fixture's own checkpoint-0 gate
     accepts — was graded as having no mesh.
  2. `find_bp_pawn` graded the FIRST derived Blueprint in ASSET-REGISTRY ORDER, so
     a submission that left a second derived pawn in the folder had a coin flip
     decide which one carried the verdict.

The third defect points the OPPOSITE way (decision Q7, 2026-08-16, section 3
below): BOTH ability-count gate sites (`_pawn_satisfies` and run_checks'
`bp_pawn_grants_bp_ability`) tested raw `len()` over the GrantedAbilities list,
so one Blueprint ability granted twice satisfied `min_bp_abilities=2` — a gate
measuring >= 1 while the spec docstring, the task's verifier section, and its
MATRIX all say DISTINCT. Now `distinct_class_count` (unique class paths) is the
gate at both sites; the detail strings keep the RAW list as evidence.

`_bp_variant_lib` imports `unreal` lazily inside `_ue()`, per call, so the fakes
here are installed in `sys.modules` and every entry point picks them up.
"""

from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_INTROSPECT = _HERE.parent / "introspect"
if str(_INTROSPECT) not in sys.path:
    sys.path.insert(0, str(_INTROSPECT))


# --------------------------------------------------------------------------- #
# fakes                                                                        #
# --------------------------------------------------------------------------- #

class _Asset:
    def __init__(self, path):
        self._path = path

    def get_path_name(self):
        return self._path


class _Component:
    """A mesh component. `prop` picks which property name holds the asset, so the
    UE 5.1 SkeletalMesh -> SkeletalMeshAsset rename stays covered."""

    def __init__(self, mesh_path=None, prop="skeletal_mesh_asset"):
        self._mesh = _Asset(mesh_path) if mesh_path else None
        self._prop = prop

    def get_editor_property(self, name):
        if name == self._prop:
            return self._mesh
        if name in ("skeletal_mesh_asset", "skeletal_mesh"):
            return None
        raise AttributeError(name)


class _Cdo:
    def __init__(self, inherited=None, own=(), granted=()):
        self._inherited = inherited
        self._own = list(own)
        self._granted = list(granted)

    def get_editor_property(self, name):
        if name == "mesh":
            return self._inherited
        if name == "granted_abilities":
            return self._granted
        raise AttributeError(name)

    def get_components_by_class(self, _cls):
        # The engine returns the inherited component here too when it exists.
        return ([self._inherited] if self._inherited is not None else []) + self._own


class _FakeUnreal(types.ModuleType):
    SkeletalMeshComponent = object()

    def __init__(self, cdos):
        super().__init__("unreal")
        self._cdos = cdos          # {class_token: _Cdo}

    def get_default_object(self, cls):
        return self._cdos[cls]


class _Installed:
    """Context manager installing a fake `unreal` for the duration."""

    def __init__(self, cdos):
        self.mod = _FakeUnreal(cdos)

    def __enter__(self):
        self._prev = sys.modules.get("unreal")
        sys.modules["unreal"] = self.mod
        return self.mod

    def __exit__(self, *a):
        if self._prev is None:
            sys.modules.pop("unreal", None)
        else:
            sys.modules["unreal"] = self._prev
        return False


class _Spec:
    min_bp_abilities = 1
    pool_prefix = "/Game/Characters/"


# --------------------------------------------------------------------------- #
# 1. the mesh widening                                                         #
# --------------------------------------------------------------------------- #

class AssignedMeshPathTest(unittest.TestCase):
    def _run(self, cdo):
        import _bp_variant_lib as lib
        with _Installed({"C": cdo}):
            return lib.assigned_mesh_path("C")

    def test_inherited_mesh_component_still_works(self):
        """The ordinary case must be byte-identical to the old behaviour."""
        got = self._run(_Cdo(inherited=_Component("/Game/Characters/SKM_Manny")))
        self.assertEqual((True, "/Game/Characters/SKM_Manny"), got)

    def test_the_LEGACY_property_name_still_works(self):
        got = self._run(_Cdo(inherited=_Component("/Game/Characters/SKM_Manny",
                                                  prop="skeletal_mesh")))
        self.assertEqual((True, "/Game/Characters/SKM_Manny"), got)

    def test_an_OWN_component_carrying_the_mesh_is_now_found(self):
        """THE FALSE_FAIL. Old code read only `mesh` and returned (True, None),
        failing a submission that did exactly what the prompt asked."""
        cdo = _Cdo(inherited=_Component(None),
                   own=[_Component("/Game/Characters/SKM_Quinn")])
        self.assertEqual((True, "/Game/Characters/SKM_Quinn"), self._run(cdo))

    def test_an_own_component_is_found_when_there_is_no_inherited_one(self):
        cdo = _Cdo(inherited=None, own=[_Component("/Game/Characters/SKM_Quinn")])
        self.assertEqual((True, "/Game/Characters/SKM_Quinn"), self._run(cdo))

    def test_no_mesh_anywhere_still_FAILS(self):
        """The gate must not have been widened into uselessness."""
        cdo = _Cdo(inherited=_Component(None), own=[_Component(None)])
        self.assertEqual((True, None), self._run(cdo))

    def test_no_component_at_all_reports_no_component(self):
        self.assertEqual((False, None), self._run(_Cdo(inherited=None, own=[])))

    def test_the_inherited_component_WINS_when_both_carry_a_mesh(self):
        """Determinism: the same submission must always name the same asset."""
        cdo = _Cdo(inherited=_Component("/Game/Characters/SKM_Manny"),
                   own=[_Component("/Game/Characters/SKM_Quinn")])
        self.assertEqual((True, "/Game/Characters/SKM_Manny"), self._run(cdo))


# --------------------------------------------------------------------------- #
# 2. the ordering dependence                                                   #
# --------------------------------------------------------------------------- #

def _good(tag="/Game/Tasks/x/GA_Thing_C"):
    return _Cdo(inherited=_Component("/Game/Characters/SKM_Manny"),
                granted=[_Asset(tag)])


def _bad_no_mesh(tag="/Game/Tasks/x/GA_Thing_C"):
    return _Cdo(inherited=_Component(None), granted=[_Asset(tag)])


def _bad_no_ability():
    return _Cdo(inherited=_Component("/Game/Characters/SKM_Manny"), granted=[])


class BestPawnTest(unittest.TestCase):
    def _pick(self, cdos, order):
        import _bp_variant_lib as lib
        with _Installed(cdos):
            cands = [(k, "/Game/Tasks/x/%s" % k) for k in order]
            return lib._best_pawn(cands, _Spec())

    def test_the_conforming_pawn_is_graded_even_when_it_is_SECOND(self):
        """THE FALSE_FAIL. Old code took candidates[0] unconditionally, so this
        submission was graded on its leftover pawn and failed."""
        cls, path = self._pick({"A": _bad_no_mesh(), "B": _good()}, ["A", "B"])
        self.assertEqual("B", cls)
        self.assertEqual("/Game/Tasks/x/B", path)

    def test_it_is_graded_when_it_is_FIRST_too(self):
        cls, _ = self._pick({"A": _good(), "B": _bad_no_mesh()}, ["A", "B"])
        self.assertEqual("A", cls)

    def test_registry_ORDER_no_longer_changes_the_outcome(self):
        cdos = {"A": _bad_no_ability(), "B": _good()}
        self.assertEqual("B", self._pick(cdos, ["A", "B"])[0])
        self.assertEqual("B", self._pick(cdos, ["B", "A"])[0])

    def test_when_NONE_conforms_the_first_is_still_returned(self):
        """So a FAIL's detail line names a real pawn and its real shortfall,
        exactly as before, rather than degrading to 'none'."""
        cls, _ = self._pick({"A": _bad_no_mesh(), "B": _bad_no_ability()},
                            ["A", "B"])
        self.assertEqual("A", cls)

    def test_no_candidates_yields_none(self):
        self.assertEqual((None, None), self._pick({}, []))

    def test_a_NATIVE_ability_still_disqualifies_a_candidate(self):
        """The anti-gaming gate must survive the widening: a pawn granting a C++
        ability must not become gradable just by being the only one."""
        cdos = {"A": _Cdo(inherited=_Component("/Game/Characters/SKM_Manny"),
                          granted=[_Asset("/Script/ThirdPerson.GA_Native")]),
                "B": _good()}
        self.assertEqual("B", self._pick(cdos, ["A", "B"])[0])


# --------------------------------------------------------------------------- #
# 3. the duplicate-ability dedup (decision Q7, 2026-08-16)                     #
# --------------------------------------------------------------------------- #

GA_DMG = "/Game/Tasks/x/GA_Damage.GA_Damage_C"
GA_HEAL = "/Game/Tasks/x/GA_Heal.GA_Heal_C"


def _pawn(granted):
    return _Cdo(inherited=_Component("/Game/Characters/SKM_Manny"),
                granted=[_Asset(p) for p in granted])


class _SpecMin2(_Spec):
    min_bp_abilities = 2


class DistinctAbilityCountTest(unittest.TestCase):
    """Site 1: `_pawn_satisfies`. The discrimination pair measures BOTH
    directions (the two-direction pattern): the duplicate leg FAILS the new code and
    PASSED the old (`len([dup, dup]) == 2 >= 2`); the distinct leg passes both,
    proving the dedup did not over-tighten."""

    def _satisfies(self, cdo, spec):
        import _bp_variant_lib as lib
        with _Installed({"C": cdo}):
            return lib._pawn_satisfies("C", spec)

    def test_a_DUPLICATE_pair_no_longer_satisfies_min_2(self):
        """THE DISCRIMINATION LEG. Old code tested
        `len(bp_abilities) < spec.min_bp_abilities` over the raw list, so
        [GA_Damage, GA_Damage] satisfied min=2. Distinct paths count 1 < 2."""
        self.assertFalse(self._satisfies(_pawn([GA_DMG, GA_DMG]), _SpecMin2()))

    def test_a_DISTINCT_pair_still_satisfies_min_2(self):
        """The other direction: two genuinely different classes still pass."""
        self.assertTrue(self._satisfies(_pawn([GA_DMG, GA_HEAL]), _SpecMin2()))

    def test_min_1_families_are_untouched_by_duplicates(self):
        """Every min=1 family (all but health-attribute-ops) is unchanged: a
        duplicated single ability is still >= 1 distinct."""
        self.assertTrue(self._satisfies(_pawn([GA_DMG, GA_DMG]), _Spec()))

    def test_distinct_class_count_is_a_set_count(self):
        import _bp_variant_lib as lib
        self.assertEqual(0, lib.distinct_class_count([]))
        self.assertEqual(1, lib.distinct_class_count([GA_DMG, GA_DMG, GA_DMG]))
        self.assertEqual(2, lib.distinct_class_count([GA_DMG, GA_HEAL, GA_DMG]))


class RunChecksGateDedupTest(unittest.TestCase):
    """Site 2: run_checks' own `bp_pawn_grants_bp_ability` gate repeated the
    raw `len()`, so fixing `_pawn_satisfies` alone would leave the emitted
    verdict wrong. This drives the real `run_checks` path (reflection seams
    stubbed at the lib's own function boundary) and reads the check dict the
    layer would parse."""

    def _gate(self, granted, min_n):
        import _bp_variant_lib as lib
        spec = lib.BpVariantSpec("/Game/Tasks/x", "Base",
                                 min_bp_abilities=min_n)
        cdo = _pawn(granted)
        stubs = {
            "task_folder_assets": lambda d: (True, ["/Game/Tasks/x/BP.BP"]),
            "resolve_native_class": lambda name, module=None: object(),
            "find_bp_pawns": lambda assets, base, name: (
                [("C", "/Game/Tasks/x/BP")], ["/Game/Tasks/x/BP"]),
            "native_subclasses": lambda base, name, exempt: ([], True, set()),
        }
        saved = {k: getattr(lib, k) for k in stubs}
        for k, v in stubs.items():
            setattr(lib, k, v)
        try:
            with _Installed({"C": cdo}):
                checks = lib.run_checks(spec)
        finally:
            for k, v in saved.items():
                setattr(lib, k, v)
        return {c["id"]: c for c in checks}["bp_pawn_grants_bp_ability"]

    def test_the_gate_FAILS_a_duplicate_pair_at_min_2(self):
        """THE DISCRIMINATION LEG at the verdict site: this exact check emitted
        passed=True under the old raw count."""
        self.assertFalse(self._gate([GA_DMG, GA_DMG], 2)["passed"])

    def test_the_gate_still_PASSES_a_distinct_pair_at_min_2(self):
        self.assertTrue(self._gate([GA_DMG, GA_HEAL], 2)["passed"])

    def test_the_detail_still_prints_the_RAW_duplicated_entries(self):
        """Evidence preservation (the Q7 answer's own condition): the GATE
        counts unique paths but the printed list stays raw, so a FAIL's detail
        shows the duplication itself rather than a deduped view of it."""
        got = self._gate([GA_DMG, GA_DMG], 2)
        self.assertFalse(got["passed"])
        self.assertEqual(2, got["detail"].count(GA_DMG))
        self.assertIn("DISTINCT", got["detail"])


class FindBpPawnsTest(unittest.TestCase):
    """`find_bp_pawn` is kept as a thin wrapper; both must agree."""

    def test_the_wrapper_returns_the_first_of_the_list(self):
        import _bp_variant_lib as lib
        seen = {"n": 0}

        def fake_generated_class(path):
            seen["n"] += 1
            return "cls:" + path

        orig_gen, orig_der = lib.generated_class, lib.derives_from
        lib.generated_class = fake_generated_class
        lib.derives_from = lambda cls, base, name: cls.endswith(("A", "B"))
        try:
            found, probed = lib.find_bp_pawns(
                ["/Game/Tasks/x/A.A", "/Game/Tasks/x/B.B", "/Game/Tasks/x/C.C"],
                None, "Base")
            self.assertEqual(["/Game/Tasks/x/A", "/Game/Tasks/x/B"],
                             [p for _, p in found])
            self.assertEqual(3, len(probed))
            cls, path, _ = lib.find_bp_pawn(
                ["/Game/Tasks/x/A.A", "/Game/Tasks/x/B.B"], None, "Base")
            self.assertEqual("/Game/Tasks/x/A", path)
        finally:
            lib.generated_class, lib.derives_from = orig_gen, orig_der


if __name__ == "__main__":
    unittest.main()

"""Offline oracle for `t1_mud_wade_bp.py`.

No editor, no UE install, no tokens. Only the probe seams are faked (asset
listing, generated-class lookup, the abstract read, the native sweep), so the
booleans under test are the shipped ones.

WHY THIS EXISTS. This leg's L2I reproduces `ResolveGradedBlueprintClass`
(`Source/CraftBenchTests/CraftBenchFunctionalTest.cpp:682-696`) — a DIFFERENT
resolver from the one `test_introspect_bp_variant_resolution.py` covers
(`ResolveAgentPawnClass`, the `gp-*-bp` pawn lane) — and the detail that resolver
gets right and a naive reproduction gets wrong is ORDER: it `continue`s on
`CLASS_Abstract` BEFORE testing whether it already has a chosen class. So an
abstract intermediate Blueprint shipped beside one concrete Blueprint resolves to
exactly one class and is GRADED NORMALLY. The first cut of this grader counted raw
candidates, which reported three of six checks failed on exactly that submission —
a false FAIL charged to the model on a run the harness graded correctly. `case 4`
below is that submission and it must score the full denominator.

What this pins:
  * the denominator is a CONSTANT 6 on every leg, including an empty submission,
    so no check is silently absent from a failing run;
  * the correct reference is the ONLY shape that scores 6/6;
  * an abstract intermediate beside a concrete answer scores 6/6 too, because
    that is what the fixture grades — the regression guard for the false FAIL;
  * abstract-ONLY is a NAMED failure (`answer_is_instantiable`), not a silent
    one: the resolver returns nullptr there, the C++ scaffold is graded, and the
    run otherwise looks exactly like a submission that did nothing;
  * an unreadable abstract flag and a reflection sweep blind to the base class
    both fail CLOSED — the direction that would otherwise re-open the hole;
  * a native subclass shipped beside a conforming Blueprint still fails, which is
    the surface question the whole leg exists to ask.

The fake cannot prove the UE API names are right — only a live editor does that.
It proves the grader's LOGIC.
"""
import importlib.util
import io
import json
import sys
import unittest
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
_VERIFY = _TESTS.parent
_SCRIPT = _VERIFY / "introspect" / "t1_mud_wade_bp.py"

EXPECTED_TOTAL = 6

#: A fixed denominator is the POINT of this file. A new check must move this
#: constant DELIBERATELY, in the same change that adds it.
EXPECTED_CHECK_IDS = (
    "deliverable_folder_has_assets",
    "exactly_one_blueprint_answer",
    "answer_is_instantiable",
    "answer_is_in_the_declared_folder",
    "no_native_subclass_delivered",
    "no_cpp_task_folder_for_this_leg",
)

_SCAFFOLD_SENTINEL = object()   # stands in for the resolved native UClass


def _load_script():
    """A FRESH module object per case, so patched seams never leak between them."""
    sys.path.insert(0, str(_VERIFY / "introspect"))
    try:
        spec = importlib.util.spec_from_file_location(
            "_mud_wade_bp_under_test", _SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path.remove(str(_VERIFY / "introspect"))


class _FakeClass:
    def __init__(self, name):
        self._name = name

    def get_name(self):
        return self._name


def run_case(bp_paths, abstract_map, *, native=(), swept_ok=True,
             cpp_dir=False, scaffold_resolves=True):
    """Drive the real ``main()`` over a faked project state.

    ``bp_paths``   package paths of Blueprints deriving from the scaffold.
    ``abstract_map`` path -> True / False / None (None = probe could not read it).
    """
    mod = _load_script()

    mod.bpl.resolve_native_class = (
        lambda name, *a, **k: _SCAFFOLD_SENTINEL if scaffold_resolves else None)

    def task_folder_assets(directory):
        # The library returns OBJECT paths (/Game/x/BP_Y.BP_Y); the script is
        # responsible for stripping them back to package paths, so hand it the
        # object-path form it will really see.
        if directory == "/Game/Tasks":
            under = list(bp_paths)
        else:
            under = [p for p in bp_paths
                     if p.startswith(directory.rstrip("/") + "/")]
        return bool(under), [p + "." + p.rsplit("/", 1)[-1] for p in under]

    mod.bpl.task_folder_assets = task_folder_assets
    mod.bpl.generated_class = (
        lambda path: _FakeClass(path.rsplit("/", 1)[-1] + "_C"))
    mod.bpl.derives_from = lambda cls, base, base_name: True
    mod.bpl.native_subclasses = (
        lambda base, name, exempt: (list(native), swept_ok, []))
    # _blueprint_asset just carries the path through to the abstract probe.
    mod._blueprint_asset = lambda path: path
    mod._is_abstract = lambda path: abstract_map.get(path)
    mod._forbidden_cpp_dir_state = lambda: (cpp_dir, True)

    buf = io.StringIO()
    real_stdout = sys.stdout
    sys.stdout = buf
    try:
        mod.main()
    finally:
        sys.stdout = real_stdout

    lines = buf.getvalue().splitlines()
    payload = json.loads(lines[lines.index(mod.INTROSPECT_JSON_START) + 1])
    return payload["checks"]


def ids_passed(checks):
    return {c["id"]: c["passed"] for c in checks}


TASK_DIR = "/Game/Tasks/t1-mud-wade-bp"
CONCRETE = TASK_DIR + "/BP_MudWader"
ABSTRACT = TASK_DIR + "/BP_MudWaderBase"
MISFILED = "/Game/Tasks/some-other-task/BP_Sneaky"


class TestMudWadeBpIntrospect(unittest.TestCase):

    def test_task_dir_matches_the_spec(self):
        """The declared folder is the task id, never a name guess."""
        mod = _load_script()
        self.assertEqual(mod.TASK_DIR, TASK_DIR)
        self.assertEqual(mod.SCAFFOLD_CLASS_NAME, "MudHeroCharacter")
        # Exempt by EXACT /Script/ path, never by name.
        self.assertEqual(mod._SCAFFOLD_EXEMPT,
                         ("/Script/ThirdPerson.MudHeroCharacter",))

    def test_denominator_is_constant_across_every_shape(self):
        for label, checks in (
                ("reference", run_case([CONCRETE], {CONCRETE: False})),
                ("empty", run_case([], {})),
                ("abstract only", run_case([ABSTRACT], {ABSTRACT: True})),
                ("probe failed", run_case([CONCRETE], {CONCRETE: None})),
                ("two concrete", run_case([CONCRETE, MISFILED],
                                          {CONCRETE: False, MISFILED: False})),
        ):
            with self.subTest(label):
                self.assertEqual(len(checks), EXPECTED_TOTAL)
                self.assertEqual(tuple(c["id"] for c in checks),
                                 EXPECTED_CHECK_IDS)

    def test_reference_scores_the_full_denominator(self):
        r = ids_passed(run_case([CONCRETE], {CONCRETE: False}))
        self.assertTrue(all(r.values()), r)

    def test_abstract_intermediate_beside_concrete_still_passes(self):
        """THE REGRESSION GUARD. The resolver skips the abstract candidate BEFORE
        its ambiguity check, so it resolves one class and grades normally. A
        grader that counts raw candidates FAILs three checks here — on a run the
        harness graded correctly, with the model wearing it."""
        r = ids_passed(run_case([ABSTRACT, CONCRETE],
                                {ABSTRACT: True, CONCRETE: False}))
        self.assertTrue(all(r.values()), r)

    def test_abstract_only_is_a_named_failure(self):
        r = ids_passed(run_case([ABSTRACT], {ABSTRACT: True}))
        self.assertFalse(r["answer_is_instantiable"])
        self.assertFalse(r["exactly_one_blueprint_answer"])
        # And it is distinguishable from an empty submission: the folder DOES
        # hold an asset, so a reader can tell "shipped something unusable" from
        # "shipped nothing".
        self.assertTrue(r["deliverable_folder_has_assets"])

    def test_empty_submission_fails_the_surface_checks(self):
        r = ids_passed(run_case([], {}))
        self.assertFalse(r["deliverable_folder_has_assets"])
        self.assertFalse(r["exactly_one_blueprint_answer"])
        self.assertFalse(r["answer_is_in_the_declared_folder"])

    def test_two_concrete_candidates_fail(self):
        """Two resolvable candidates make the FIXTURE raise a
        HARNESS-PRECONDITION rather than grade, so it is a defect here too."""
        r = ids_passed(run_case([CONCRETE, MISFILED],
                                {CONCRETE: False, MISFILED: False}))
        self.assertFalse(r["exactly_one_blueprint_answer"])
        self.assertFalse(r["answer_is_in_the_declared_folder"])

    def test_unreadable_abstract_flag_fails_closed(self):
        r = ids_passed(run_case([CONCRETE], {CONCRETE: None}))
        self.assertFalse(r["exactly_one_blueprint_answer"])
        self.assertFalse(r["answer_is_instantiable"])

    def test_native_subclass_beside_a_conforming_blueprint_fails(self):
        """The surface question: a native subclass is a C++ answer, and on a
        PLACED-actor task it is what the map would instantiate."""
        r = ids_passed(run_case([CONCRETE], {CONCRETE: False},
                                native=["MudHeroCharacterFast"]))
        self.assertTrue(r["exactly_one_blueprint_answer"])
        self.assertFalse(r["no_native_subclass_delivered"])

    def test_native_sweep_blind_to_the_base_class_fails_closed(self):
        """`swept_ok` is the library's own fail-closed self-test: a sweep that
        cannot see the base class proves nothing about subclasses of it."""
        r = ids_passed(run_case([CONCRETE], {CONCRETE: False}, swept_ok=False))
        self.assertFalse(r["no_native_subclass_delivered"])

    def test_forbidden_cpp_task_folder_fails(self):
        r = ids_passed(run_case([CONCRETE], {CONCRETE: False}, cpp_dir=True))
        self.assertFalse(r["no_cpp_task_folder_for_this_leg"])

    def test_misfiled_answer_reads_as_misfiled(self):
        r = ids_passed(run_case([MISFILED], {MISFILED: False}))
        self.assertTrue(r["exactly_one_blueprint_answer"])
        self.assertFalse(r["answer_is_in_the_declared_folder"])
        self.assertFalse(r["deliverable_folder_has_assets"])

    def test_unresolvable_scaffold_is_a_harness_fault_not_a_verdict(self):
        """The verifier cannot see the class the task is defined against, so it
        must say so loudly instead of emitting a graded-looking 1/6."""
        checks = run_case([CONCRETE], {CONCRETE: False},
                          scaffold_resolves=False)
        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0]["id"], "scaffold_class_resolvable")
        self.assertFalse(checks[0]["passed"])


if __name__ == "__main__":
    unittest.main()

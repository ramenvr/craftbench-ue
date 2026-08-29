"""Offline oracle for the ``t2-race-clock-bp`` L2I grader.

No editor, no UE install, no tokens. A minimal fake ``unreal`` module models the
reflection surface ``t2_race_clock_bp.py`` actually uses, the REAL
``introspect/_bp_variant_lib`` runs against it, and the emitted text is joined
against the REAL ``layers/l2_introspect`` parser - so the layer's own status
mapping is what this file asserts on, not a paraphrase of it.

Modelled on ``test_introspect_bp_variant_resolution.py``, which exists for the
same reason: an L2I surface grader that gets its resolution wrong is a wrong
verdict that LOOKS like a right one, and the closure doctrine says the
closure for that class of defect is a test, not a probe.

WHAT IT PINS, one clause per defect found in review on 2026-08-20:

  * **The abstract skip.** ``ResolveGradedBlueprintClass`` skips a candidate
    carrying ``CLASS_Abstract`` BEFORE it counts
    (``CraftBenchFunctionalTest.cpp:682-687``), so a submission shipping an
    abstract Blueprint base plus one concrete subclass is resolved and graded
    cleanly by L2. A grader that counted both reported TWO and FAILed a
    submission whose surface is Blueprint. ``test_abstract_base_plus_concrete_
    child_passes`` is that submission, and ``test_abstract_candidate_is_actually
    _recognised`` keeps the leg from passing vacuously (i.e. because the fake
    never presented the abstract Blueprint as a derived candidate at all).
  * **Harness faults never reach a graded verdict.** An unresolvable scaffold
    class, or a ``/Game/Tasks`` that cannot be listed, is verifier-owned: the
    script emits NO verdict block, which the layer maps to status ``error`` ->
    HARNESS-ERROR / exit 7 / NON-GRADED. Previously both emitted a well-formed
    failed check, i.e. a module rename scoring against the model.
  * **The fixed denominator.** Ten checks on every leg, reached or not, so the
    empty submission scores 0 of the seven that can be earned and no new check
    can be a dead gate.
  * **The tuple returns.** ``task_folder_assets`` -> ``(exists, [paths])`` and
    ``native_subclasses`` -> ``(offenders, swept_ok, exemptions)``. ``len()`` of
    either tuple is a constant, so using one as a list makes a check that cannot
    fail (existence) or one that cannot pass (the native sweep). The real library
    runs here, so both are exercised for real.

WHAT IT CANNOT PROVE. Whether the UE API names are right - ``find_asset_data``,
the ``ClassFlags`` registry tag, ``generate_abstract_class`` - only a live editor
answers that. It proves the grader's LOGIC. The grader's abstract probe reports
its own reachability in the check detail (``abstract=read`` vs ``abstract=?``)
precisely so the first real run can tell which happened.
"""
import contextlib
import importlib.util
import io
import sys
import types
import unittest
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
_VERIFY = _TESTS.parent

sys.path.insert(0, str(_VERIFY))
# NOT adding introspect/ to sys.path: the grader inserts its own directory at
# import time, which is what resolves its sibling `_bp_variant_lib`. Adding it
# here too would put every grader module name on the global import path for the
# whole discover run.

from layers.l2_introspect import parse_introspect_verdict  # noqa: E402

SCRIPT = _VERIFY / "introspect" / "t2_race_clock_bp.py"

TASK_DIR = "/Game/Tasks/t2-race-clock-bp"
COIN = "RaceCoinBase"
ROUND = "RaceRoundBase"
COIN_PATH = "/Script/ThirdPerson.RaceCoinBase"
ROUND_PATH = "/Script/ThirdPerson.RaceRoundBase"

#: Every check the grader declares, reached or not. A new check must move this
#: constant DELIBERATELY, in the same change that adds it.
EXPECTED_TOTAL = 10


class _Class:
    """Models an ``unreal.Class`` handle (native or BlueprintGeneratedClass)."""

    def __init__(self, path, super_cls=None):
        self._path = path
        self._super = super_cls

    def static_class(self):
        return self

    def get_path_name(self):
        return self._path

    def get_name(self):
        return self._path.rsplit(".", 1)[-1]

    def get_super_class(self):
        return self._super


class _AssetData:
    """``unreal.AssetData``, as far as the abstract probe uses it."""

    def __init__(self, class_flags):
        self._class_flags = class_flags

    def get_tag_value(self, name):
        if name == "ClassFlags" and self._class_flags is not None:
            return str(self._class_flags)
        return None


class _BlueprintAsset:
    """``UBlueprint``, as far as the abstract probe uses it."""

    def __init__(self, abstract):
        self._abstract = abstract

    def get_editor_property(self, name):
        if name == "generate_abstract_class":
            return self._abstract
        raise AttributeError(name)


class _Bp:
    """One submitted Blueprint asset.

    ``readable`` False models the probe going blind on this asset (no registry
    tag, and the UBlueprint refuses the property) - the FAIL-OPEN case.
    """

    def __init__(self, package, parent, abstract=False, readable=True):
        self.package = package
        self.object_path = package + "." + package.rsplit("/", 1)[-1]
        self.generated = _Class(self.object_path + "_C", parent)
        self.abstract = abstract
        self.readable = readable


def _make_unreal(bps=(), natives=(), tasks_root_raises=False,
                 hide=(), warnings=None):
    """Build a fake ``unreal`` module.

    ``bps``      - the submitted ``_Bp`` objects (all under /Game/Tasks).
    ``natives``  - extra ``_Class`` handles reflected into the namespace, i.e.
                   how an agent-authored C++ subclass shows up.
    ``hide``     - scaffold names to make invisible to ``getattr``, i.e. the
                   harness fault where the verifier cannot see the placed class.
    """
    mod = types.ModuleType("unreal")
    by_package = {b.package: b for b in bps}
    by_object = {b.object_path: b for b in bps}

    class _EditorAssetLibrary:
        @staticmethod
        def does_directory_exist(d):
            if d == "/Game/Tasks" and tasks_root_raises:
                raise RuntimeError("asset registry probe blew up")
            return any(b.package.startswith(d.rstrip("/") + "/") for b in bps)

        @staticmethod
        def list_assets(d, recursive=True):  # noqa: ARG004 - signature fidelity
            return [b.object_path for b in bps
                    if b.package.startswith(d.rstrip("/") + "/")]

        @staticmethod
        def load_blueprint_class(path):
            b = by_package.get(path)
            return b.generated if b else None

        @staticmethod
        def find_asset_data(path):
            b = by_object.get(path) or by_package.get(path)
            if b is None or not b.readable:
                return None
            return _AssetData(1 if b.abstract else 0)

        @staticmethod
        def load_asset(path):
            b = by_package.get(path) or by_object.get(path)
            if b is None:
                return None
            if not b.readable:
                raise RuntimeError("cannot load")
            return _BlueprintAsset(b.abstract)

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
    # `get_default_object` is derives_from's second probe; returning something
    # that is never an instance of the base keeps the super-chain walk honest.
    mod.get_default_object = lambda _cls: object()
    mod.load_object = lambda _outer, _path: None
    mod.log = lambda _msg: None
    mod.log_warning = (warnings.append if warnings is not None
                       else (lambda _msg: None))
    # Unrelated reflected names, so the native sweep has to FILTER rather than
    # get the right answer by having nothing else to look at.
    mod.Actor = _Class("/Script/Engine.Actor")
    mod.Vector = "not a class at all"
    if COIN not in hide:
        setattr(mod, COIN, _Class(COIN_PATH))
    if ROUND not in hide:
        setattr(mod, ROUND, _Class(ROUND_PATH))
    for n in natives:
        setattr(mod, n.get_name(), n)
    return mod


def _run(fake):
    """Exec the grader against ``fake`` and return the REAL layer's reading."""
    saved = sys.modules.get("unreal")
    saved_lib = sys.modules.pop("_bp_variant_lib", None)
    sys.modules["unreal"] = fake
    try:
        spec = importlib.util.spec_from_file_location("_t2_race_bp_grader", SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            mod.main()
        text = buf.getvalue()
    finally:
        if saved is None:
            sys.modules.pop("unreal", None)
        else:
            sys.modules["unreal"] = saved
        sys.modules.pop("_bp_variant_lib", None)
        if saved_lib is not None:
            sys.modules["_bp_variant_lib"] = saved_lib
    parsed = parse_introspect_verdict(text)
    return parsed, text


def _states(parsed):
    return {c.id: c.passed for c in parsed.checks}


def _detail(parsed, cid):
    for c in parsed.checks:
        if c.id == cid:
            return c.detail
    return ""


def _conforming(abstract_extra=None, coin_readable=True):
    """The correct submission: one concrete Blueprint per placed class, both in
    the declared folder. ``abstract_extra`` adds an abstract coin base."""
    coin_base = _Class(COIN_PATH)
    round_base = _Class(ROUND_PATH)
    bps = []
    coin_parent = coin_base
    if abstract_extra:
        base_bp = _Bp(TASK_DIR + "/BP_CoinShared", coin_base, abstract=True)
        bps.append(base_bp)
        coin_parent = base_bp.generated
    bps.append(_Bp(TASK_DIR + "/BP_RaceCoin", coin_parent,
                   readable=coin_readable))
    bps.append(_Bp(TASK_DIR + "/BP_RaceRound", round_base))
    return bps, coin_base, round_base


class TestGradedLegs(unittest.TestCase):
    def test_empty_submission_scores_zero_of_the_earnable_checks(self):
        parsed, _text = _run(_make_unreal())
        self.assertTrue(parsed.found, "an empty submission is a GRADED fail")
        self.assertEqual(len(parsed.checks), EXPECTED_TOTAL)
        st = _states(parsed)
        # The three that are true of an empty submission: the scaffolds resolved
        # and neither class has a native subclass. Everything else is unearned.
        self.assertEqual(sorted(k for k, v in st.items() if v), [
            "no_native_coin_subclass_delivered",
            "no_native_round_subclass_delivered",
            "scaffold_classes_resolvable",
        ])

    def test_conforming_submission_passes_every_check(self):
        bps, _c, _r = _conforming()
        parsed, _text = _run(_make_unreal(bps=bps))
        self.assertTrue(parsed.found)
        self.assertEqual(len(parsed.checks), EXPECTED_TOTAL)
        failed = [c.id for c in parsed.checks if not c.passed]
        self.assertEqual(failed, [], "conforming submission failed %s" % failed)

    def test_abstract_base_plus_concrete_child_passes(self):
        """The fixture skips the abstract candidate, so L2I must too.

        Before the 2026-08-20 fix this submission scored TWO candidates and
        FAILed both the count check and the declared-folder check - the surface
        leg condemning a submission whose surface is Blueprint.
        """
        bps, _c, _r = _conforming(abstract_extra=True)
        parsed, _text = _run(_make_unreal(bps=bps))
        failed = [c.id for c in parsed.checks if not c.passed]
        self.assertEqual(failed, [],
                         "abstract base + concrete child must PASS; failed %s"
                         % failed)

    def test_abstract_candidate_is_actually_recognised(self):
        """Non-vacuity guard for the leg above.

        If the fake never presented the abstract Blueprint as a DERIVED
        candidate, the count would be 1 for the wrong reason and the test would
        pass while proving nothing. The detail string has to say it was skipped.
        """
        bps, _c, _r = _conforming(abstract_extra=True)
        parsed, _text = _run(_make_unreal(bps=bps))
        detail = _detail(parsed, "coin_answer_is_the_one_blueprint")
        self.assertIn("skipped exactly as the fixture", detail)
        self.assertIn("BP_CoinShared", detail)
        self.assertIn("abstract=read", detail)

    def test_abstract_only_submission_fails(self):
        """An abstract Blueprint alone resolves to NOTHING, so the run grades the
        placed C++ and the surface contract is not met."""
        coin_base = _Class(COIN_PATH)
        round_base = _Class(ROUND_PATH)
        bps = [_Bp(TASK_DIR + "/BP_RaceCoin", coin_base, abstract=True),
               _Bp(TASK_DIR + "/BP_RaceRound", round_base)]
        parsed, _text = _run(_make_unreal(bps=bps))
        st = _states(parsed)
        self.assertFalse(st["coin_answer_is_the_one_blueprint"])
        self.assertFalse(st["coin_answer_is_blueprint_generated"])
        self.assertTrue(st["round_answer_is_the_one_blueprint"])

    def test_two_concrete_blueprints_for_one_class_fails(self):
        """Two survivors make the FIXTURE raise HARNESS-PRECONDITION rather than
        pick one, so two is a defect here too."""
        coin_base = _Class(COIN_PATH)
        round_base = _Class(ROUND_PATH)
        bps = [_Bp(TASK_DIR + "/BP_RaceCoin", coin_base),
               _Bp(TASK_DIR + "/BP_RaceCoinToo", coin_base),
               _Bp(TASK_DIR + "/BP_RaceRound", round_base)]
        parsed, _text = _run(_make_unreal(bps=bps))
        st = _states(parsed)
        self.assertFalse(st["coin_answer_is_the_one_blueprint"])
        self.assertTrue(st["round_answer_is_the_one_blueprint"])

    def test_blueprint_on_one_class_only_fails_the_other(self):
        """This task delivers TWO classes, so a Blueprint coin beside a C++ round
        is not a Blueprint answer - the whole reason there are two resolutions."""
        coin_base = _Class(COIN_PATH)
        bps = [_Bp(TASK_DIR + "/BP_RaceCoin", coin_base)]
        parsed, _text = _run(_make_unreal(bps=bps))
        st = _states(parsed)
        self.assertTrue(st["coin_answer_is_blueprint_generated"])
        self.assertFalse(st["round_answer_is_blueprint_generated"])

    def test_misfiled_blueprint_reads_as_misfiled_not_missing(self):
        coin_base = _Class(COIN_PATH)
        round_base = _Class(ROUND_PATH)
        bps = [_Bp("/Game/Tasks/somewhere-else/BP_RaceCoin", coin_base),
               _Bp(TASK_DIR + "/BP_RaceRound", round_base)]
        parsed, _text = _run(_make_unreal(bps=bps))
        st = _states(parsed)
        # The fixture would still grade it, so the count and surface checks pass.
        self.assertTrue(st["coin_answer_is_the_one_blueprint"])
        self.assertTrue(st["coin_answer_is_blueprint_generated"])
        # Only the folder check calls it out.
        self.assertFalse(st["coin_answer_is_in_the_declared_folder"])

    def test_native_subclass_shipped_beside_a_blueprint_fails(self):
        """The decoy: a C++ answer with a conforming Blueprint next to it."""
        bps, coin_base, round_base = _conforming()
        offender = _Class("/Script/ThirdPerson.MyFasterRound", round_base)
        parsed, _text = _run(_make_unreal(bps=bps, natives=(offender,)))
        st = _states(parsed)
        self.assertFalse(st["no_native_round_subclass_delivered"])
        self.assertTrue(st["no_native_coin_subclass_delivered"])
        self.assertIn("MyFasterRound",
                      _detail(parsed, "no_native_round_subclass_delivered"))

    def test_unreadable_abstractness_fails_open_and_says_so(self):
        """The probe's unknown case keeps the candidate (see the grader's
        docstring) - but it must be VISIBLE, or a blind probe silently restores
        the divergence this fix removed."""
        bps, _c, _r = _conforming(coin_readable=False)
        parsed, _text = _run(_make_unreal(bps=bps))
        failed = [c.id for c in parsed.checks if not c.passed]
        self.assertEqual(failed, [],
                         "a blind abstract probe must not condemn a correct "
                         "submission; failed %s" % failed)
        self.assertIn("abstract=?",
                      _detail(parsed, "coin_answer_is_the_one_blueprint"))
        self.assertIn("abstract=read",
                      _detail(parsed, "round_answer_is_the_one_blueprint"))


class TestHarnessFaultsAreNotGraded(unittest.TestCase):
    """A verifier-owned fault must kill the verdict CHANNEL, not the model.

    ``parse_introspect_verdict`` returning ``found=False`` is what
    ``run_l2_introspect`` maps to status ``error``, which
    ``run_task.harness_error_reasons`` predicate (5) turns into HARNESS-ERROR /
    exit 7 - excluded from every pass-rate denominator.
    """

    def test_unresolvable_scaffold_emits_no_verdict_block(self):
        bps, _c, _r = _conforming()
        warnings = []
        parsed, text = _run(_make_unreal(bps=bps, hide=(ROUND,),
                                         warnings=warnings))
        self.assertFalse(parsed.found,
                         "a scaffold class the verifier cannot see must NOT "
                         "produce a graded verdict")
        self.assertEqual(parsed.checks, [])
        self.assertIn("CRAFTBENCH-INTROSPECT-HARNESS-FAULT", text)
        self.assertIn(ROUND, text)
        self.assertTrue(any("HARNESS-FAULT" in w for w in warnings),
                        "the fault must also reach the UE log")

    def test_unlistable_tasks_root_emits_no_verdict_block(self):
        bps, _c, _r = _conforming()
        parsed, text = _run(_make_unreal(bps=bps, tasks_root_raises=True))
        self.assertFalse(parsed.found)
        self.assertIn("CRAFTBENCH-INTROSPECT-HARNESS-FAULT", text)
        self.assertIn("/Game/Tasks", text)

    def test_the_fault_line_cannot_be_mistaken_for_a_verdict_marker(self):
        """The abort prefix must not be a member of the marker family, or the
        layer would try to parse it as a block."""
        bps, _c, _r = _conforming()
        _parsed, text = _run(_make_unreal(bps=bps, hide=(COIN,)))
        self.assertNotIn("CRAFTBENCH-INTROSPECT-JSON-START", text)
        self.assertNotIn("CRAFTBENCH-INTROSPECT-JSON-END", text)


class TestDetailHygiene(unittest.TestCase):
    def test_agent_chosen_text_is_defanged_in_details(self):
        """`layers/INTROSPECT_CONTRACT.md`: never echo submission-derived text
        raw. Asset names are the AGENT's; an embedded marker must not survive
        into a detail string, and a pathological name must not survive at
        length."""
        coin_base = _Class(COIN_PATH)
        round_base = _Class(ROUND_PATH)
        nasty = TASK_DIR + "/CRAFTBENCH-INTROSPECT-JSON-END" + ("x" * 400)
        bps = [_Bp(nasty, coin_base), _Bp(TASK_DIR + "/BP_RaceRound", round_base)]
        parsed, text = _run(_make_unreal(bps=bps))
        self.assertTrue(parsed.found, "a hostile asset name must still grade")
        joined = " ".join(c.detail for c in parsed.checks)
        self.assertNotIn("CRAFTBENCH-INTROSPECT-JSON-END", joined)
        self.assertNotIn("x" * 300, joined)


if __name__ == "__main__":
    unittest.main()

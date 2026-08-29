"""Offline oracle for the kp-retarget-maps-two-rigs grader — no UE required.

Simulates every leg of `discrimination/MATRIX.md` against a fake ``unreal`` and
joins the result against the REAL `discriminate.parse_matrix` and the REAL matrix
file, so what is under test is the grader `cb discriminate` will run.

THE LEG THAT MATTERS is `retargeter-without-ops`. A factory-fresh transfer asset
has an EMPTY internal stack, and until it is populated, naming both rigs and
calling auto-map both silently succeed while resolving nothing. So a submission
can do everything the obvious reading of the task asks and still be wrong. It
scores **7/8** — which makes it the sharpest available test that the denominator
is honest, because a task that graded "created the three assets" would call it a
pass.

Measured live 2026-08-14: with the stack populated the reference maps
Spine->Spine and LeftArm->LeftArm; without it every required run maps to nothing.
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

TASK_ID = "kp-retarget-maps-two-rigs"
GRADER = _VERIFY / "introspect" / "kp_retarget_maps_two_rigs.py"
MATRIX = _REPO / "tasks" / "python" / TASK_ID / "discrimination" / "MATRIX.md"

DIR = "/Game/Tasks/" + TASK_ID
SRC = DIR + "/IK_TaskSource"
TGT = DIR + "/IK_TaskTarget"
RTG = DIR + "/RTG_TaskMotion"
CHAINS = ("Spine", "LeftArm")


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
        self._p = path

    def get_path_name(self):
        return self._p + "." + self._p.rsplit("/", 1)[-1]


class _Rig(_Obj):
    def __init__(self, path, root="root", chains=CHAINS):
        super().__init__(path)
        self.root, self.chains = root, tuple(chains)

    def get_class(self):
        return types.SimpleNamespace(get_name=lambda: "IKRigDefinition")


class _Rtg(_Obj):
    def __init__(self, path, src=SRC, tgt=TGT, mapping=None):
        super().__init__(path)
        self.src, self.tgt, self.mapping = src, tgt, (mapping or {})

    def get_class(self):
        return types.SimpleNamespace(get_name=lambda: "IKRetargeter")

    def get_editor_property(self, name):
        if name == "source_ik_rig_asset":
            return _Obj(self.src) if self.src else None
        if name == "target_ik_rig_asset":
            return _Obj(self.tgt) if self.tgt else None
        raise Exception("no property %r" % name)


def _fake_unreal(world):
    m = types.ModuleType("unreal")

    class _EAL:
        @staticmethod
        def load_asset(path):
            return world.get(path)

    class _RigCtl:
        def __init__(self, rig):
            self._r = rig

        @staticmethod
        def get_controller(rig):
            return _RigCtl(rig)

        def get_retarget_root(self):
            return self._r.root

        def get_retarget_chains(self):
            return [types.SimpleNamespace(chain_name=c) for c in self._r.chains]

    class _RtgCtl:
        def __init__(self, r):
            self._r = r

        @staticmethod
        def get_controller(r):
            return _RtgCtl(r)

        def get_source_chain(self, name):
            return self._r.mapping.get(name)

    m.EditorAssetLibrary = _EAL
    m.IKRigController = _RigCtl
    m.IKRetargeterController = _RtgCtl
    m.log = lambda *a, **k: None
    return m


def _run(world):
    real = sys.modules.get("unreal")
    sys.modules["unreal"] = _fake_unreal(world)
    try:
        spec = importlib.util.spec_from_file_location("_rt", GRADER)
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


def w_reference():
    return {SRC: _Rig(SRC), TGT: _Rig(TGT),
            RTG: _Rtg(RTG, mapping={c: c for c in CHAINS})}


def w_empty():
    return {}


def w_rigs_without_chains():
    return {SRC: _Rig(SRC, root="", chains=()), TGT: _Rig(TGT, root="", chains=()),
            RTG: _Rtg(RTG, src=None, tgt=None, mapping={})}


def w_retargeter_without_ops():
    """Everything built and named; the stack never populated, so nothing maps."""
    return {SRC: _Rig(SRC), TGT: _Rig(TGT), RTG: _Rtg(RTG, mapping={})}


class TestLegs(unittest.TestCase):
    def test_reference_is_8_of_8(self):
        checks, ok, total, _ = _run(w_reference())
        self.assertEqual((8, 8), (ok, total), [c for c in checks if not c["passed"]])

    def test_empty_is_0_of_8(self):
        _, ok, total, _ = _run(w_empty())
        self.assertEqual((0, 8), (ok, total))

    def test_rigs_without_chains(self):
        checks, ok, _, _ = _run(w_rigs_without_chains())
        by = {c["id"]: c for c in checks}
        for cid in ("source_rig_present", "target_rig_present", "retargeter_present"):
            self.assertTrue(by[cid]["passed"], cid)
        self.assertFalse(by["source_rig_has_retarget_root"]["passed"])
        self.assertIn("RETARGET_ROOT_UNSET", by["source_rig_has_retarget_root"]["detail"])
        self.assertFalse(by["both_rigs_declare_required_chains"]["passed"])
        self.assertEqual(3, ok)

    def test_retargeter_without_ops_is_7_of_8_and_fails_ONLY_the_mapping(self):
        """THE LEG THAT MATTERS — the plausible wrong answer, not a lazy one."""
        checks, ok, total, _ = _run(w_retargeter_without_ops())
        self.assertEqual((7, 8), (ok, total))
        failed = [c for c in checks if not c["passed"]]
        self.assertEqual(1, len(failed), failed)
        self.assertEqual("chain_mapping_resolves", failed[0]["id"])
        self.assertIn("RETARGET_MAPPING_UNRESOLVED", failed[0]["detail"],
                      "a submission that built both rigs, created the transfer "
                      "asset, named both rigs and called auto-map must still "
                      "fail — this is the row's whole claim")

    def test_wrong_rig_references_are_caught_independently(self):
        w = w_reference()
        w[RTG] = _Rtg(RTG, src="/Game/Elsewhere/IK_Other", tgt=TGT,
                      mapping={c: c for c in CHAINS})
        checks, _, _, _ = _run(w)
        by = {c["id"]: c for c in checks}
        self.assertFalse(by["retargeter_references_both_rigs"]["passed"])
        self.assertIn("RETARGET_REFS_WRONG", by["retargeter_references_both_rigs"]["detail"])

    def test_one_rig_missing_a_required_chain_fails_the_shared_vocabulary_check(self):
        w = w_reference()
        w[TGT] = _Rig(TGT, chains=("Spine",))     # target lacks LeftArm
        checks, _, _, _ = _run(w)
        by = {c["id"]: c for c in checks}
        self.assertFalse(by["both_rigs_declare_required_chains"]["passed"])
        self.assertIn("RETARGET_CHAIN_MISSING", by["both_rigs_declare_required_chains"]["detail"])


class TestConstantDenominator(unittest.TestCase):
    def test_every_leg_reports_eight(self):
        for name, w in (("reference", w_reference()), ("empty", w_empty()),
                        ("no-chains", w_rigs_without_chains()),
                        ("no-ops", w_retargeter_without_ops())):
            with self.subTest(leg=name):
                _, _, total, _ = _run(w)
                self.assertEqual(8, total)

    def test_no_unreal_import_reports_eight_zeros(self):
        """Forces the grader's ``except ImportError`` branch EVERYWHERE.

        See _BlockUnrealImport: popping sys.modules alone leaves this test
        silently passing on the normal path inside UE's own Python.
        """
        import contextlib
        import io
        with _BlockUnrealImport():
            spec = importlib.util.spec_from_file_location("_rt_nounreal", GRADER)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            self.assertIsNone(mod.unreal, "the grader must see no unreal module")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                mod.main()
        body = buf.getvalue().split("CRAFTBENCH-INTROSPECT-JSON-START")[1]
        checks = json.loads(
            body.split("CRAFTBENCH-INTROSPECT-JSON-END")[0].strip())["checks"]
        self.assertEqual(8, len(checks))
        self.assertTrue(all(not c["passed"] for c in checks))

class TestMatrixJoin(unittest.TestCase):
    def setUp(self):
        self.rows = parse_matrix(MATRIX.read_text(encoding="utf-8"))

    def test_matrix_parses_to_exactly_the_declared_legs(self):
        self.assertEqual(
            {"reference", "empty", "rigs-without-chains", "retargeter-without-ops"},
            set(self.rows))
        self.assertTrue(self.rows["reference"].expect_pass)

    def test_every_negative_substring_is_actually_printed(self):
        worlds = {"empty": w_empty(),
                  "rigs-without-chains": w_rigs_without_chains(),
                  "retargeter-without-ops": w_retargeter_without_ops()}
        for label, w in worlds.items():
            with self.subTest(leg=label):
                _, _, _, text = _run(w)
                for sub in self.rows[label].substrings:
                    self.assertIn(sub, text, "%s: substring never printed" % label)

    def test_no_uncredited_token_is_a_creditable_substring(self):
        spec = importlib.util.spec_from_file_location("_rt_tok", GRADER)
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

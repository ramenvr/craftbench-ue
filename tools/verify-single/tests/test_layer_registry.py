"""Pluggable layer protocol + run_layers orchestration.

Covers the three things that were inconsistent before the refactor and are now
first-class: selection (applies), gating policy, and dependency short-circuit.
Loop logic is tested with stub layers (no UE); the real adapters' selection
predicates are tested with a stub context.
"""
from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_VERIFY = _HERE.parent
if str(_VERIFY) not in sys.path:
    sys.path.insert(0, str(_VERIFY))

from report import LayerReport  # noqa: E402
from layers.base import Layer, LayerContext  # noqa: E402
from layers.registry import (  # noqa: E402
    REGISTRY,
    L1Layer,
    L2Layer,
    L2IntrospectLayer,
    R2Layer,
    task_l2_rhi_args,
    run_layers,
)


def _ctx(**over) -> LayerContext:
    task = types.SimpleNamespace(
        layers=over.pop("layers", ("L1",)),
        introspect_scripts=over.pop("introspect_scripts", ()),
        raw_text=over.pop("raw_text", ""),
        map_name=None, fixtures=(), task_id="demo",
    )
    args = types.SimpleNamespace(r2=over.pop("r2", False))
    manifest = types.SimpleNamespace(writable=("Source/CraftBenchTemplate/",), game_module="CraftBenchTemplate")
    return LayerContext(
        task=task, args=args, project_path=Path("/x.uproject"),
        workdir_substrate=Path("/x"), out_dir=Path("/out"),
        manifest=manifest, substrate_src=Path("/s"),
        requested_layers=set(over.pop("requested_layers", {"L1"})),
    )


class StubLayer:
    """A fake Layer recording whether run() was called."""
    def __init__(self, key, *, gating=True, order=0, requires=(), status="pass", advisory=None):
        self.key, self.gating, self.order, self.requires = key, gating, order, requires
        self._status, self._advisory = status, advisory
        self.ran = False

    def applies(self, ctx): return True

    def run(self, ctx):
        self.ran = True
        if self._advisory is not None:
            ctx.advisory_out[self.key] = self._advisory
        return LayerReport(status=self._status, notes=[f"{self.key} ran"])


class TestRegistryMetadata(unittest.TestCase):
    def test_keys_order_gating_requires(self):
        by_key = {l.key: l for l in REGISTRY}
        self.assertEqual(set(by_key), {"ART", "L1", "L2", "L3", "L2I", "R2"})
        self.assertTrue(by_key["L1"].gating and by_key["L2"].gating and by_key["L2I"].gating)
        self.assertTrue(by_key["ART"].gating)                    # deterministic floor
        self.assertTrue(by_key["L3"].gating)                     # render structural gate
        self.assertEqual(by_key["L3"].requires, ("L1",))
        self.assertFalse(by_key["R2"].gating)                    # advisory
        self.assertEqual(by_key["ART"].requires, ())
        self.assertLess(by_key["ART"].order, by_key["L1"].order)  # runs early
        self.assertEqual(by_key["L2"].requires, ("L1",))
        self.assertEqual(by_key["L2I"].requires, ("L1",))
        self.assertEqual(by_key["R2"].requires, ())
        orders = [l.order for l in REGISTRY]
        self.assertEqual(orders, sorted(orders))                 # ascending

    def test_layers_conform_to_protocol(self):
        for l in REGISTRY:
            self.assertIsInstance(l, Layer)


class TestApplies(unittest.TestCase):
    def test_l1_l2_by_token(self):
        self.assertTrue(L1Layer().applies(_ctx(requested_layers={"L1", "L2"})))
        self.assertTrue(L2Layer().applies(_ctx(requested_layers={"L1", "L2"})))
        self.assertFalse(L2Layer().applies(_ctx(requested_layers={"L1"})))

    def test_l2i_by_section_presence_not_token(self):
        # L2I is triggered by introspect scripts, NOT an L-token.
        self.assertFalse(L2IntrospectLayer().applies(_ctx(introspect_scripts=())))
        self.assertTrue(L2IntrospectLayer().applies(_ctx(introspect_scripts=("x.py",))))

    def test_r2_by_flag_and_rubric(self):
        self.assertFalse(R2Layer().applies(_ctx(r2=False, raw_text="## R2 advisory rubric\n{}")))
        self.assertFalse(R2Layer().applies(_ctx(r2=True, raw_text="no rubric here")))
        self.assertTrue(R2Layer().applies(_ctx(r2=True, raw_text="## R2 advisory rubric\n{}")))

    def test_task_l2_rhi_args_are_closed_and_d3d11_only(self):
        self.assertIsNone(task_l2_rhi_args(types.SimpleNamespace(rhi="null")))
        self.assertIsNone(task_l2_rhi_args(types.SimpleNamespace(rhi="real")))
        self.assertEqual(
            task_l2_rhi_args(types.SimpleNamespace(rhi="d3d11")), ["-d3d11"]
        )


class TestRunLayersLoop(unittest.TestCase):
    def test_gating_layers_drive_layers_out_advisory_routes_aside(self):
        reg = [
            StubLayer("L1", order=10),
            StubLayer("R2", gating=False, order=40, advisory={"advisory_score": 0.5, "gating": False}),
        ]
        layers_out, advisory = run_layers(_ctx(), registry=reg)
        self.assertEqual(set(layers_out), {"L1"})           # advisory NOT in layers_out
        self.assertEqual(advisory["R2"]["advisory_score"], 0.5)

    def test_dependency_short_circuit_skips_dependents(self):
        l1 = StubLayer("L1", order=10, status="fail")
        l2 = StubLayer("L2", order=20, requires=("L1",))
        l2i = StubLayer("L2I", order=30, requires=("L1",))
        layers_out, _ = run_layers(_ctx(), registry=[l1, l2, l2i])
        self.assertEqual(layers_out["L1"].status, "fail")
        self.assertEqual(layers_out["L2"].status, "skipped")
        self.assertEqual(layers_out["L2I"].status, "skipped")
        self.assertIn("short-circuited: L1 did not pass", layers_out["L2"].notes)
        self.assertFalse(l2.ran and l2i.ran)                # dependents never executed

    def test_l2i_runs_even_when_l2_fails(self):
        # L2I requires only L1, NOT L2 — preserves pre-refactor behavior.
        reg = [
            StubLayer("L1", order=10, status="pass"),
            StubLayer("L2", order=20, requires=("L1",), status="fail"),
            StubLayer("L2I", order=30, requires=("L1",), status="pass"),
        ]
        layers_out, _ = run_layers(_ctx(), registry=reg)
        self.assertEqual(layers_out["L2"].status, "fail")
        self.assertEqual(layers_out["L2I"].status, "pass")  # still ran

    def test_missing_dependency_not_run_means_no_short_circuit(self):
        # L1 not in registry -> L2 has no failed dep -> runs (matches l1=None path).
        l2 = StubLayer("L2", order=20, requires=("L1",))
        layers_out, _ = run_layers(_ctx(), registry=[l2])
        self.assertTrue(l2.ran)
        self.assertEqual(layers_out["L2"].status, "pass")


class TestLayerDurationFill(unittest.TestCase):
    """Every layer carries a duration, including the ones that never set one.

    L2I reported `duration_seconds: None` in every report ever written, which is
    why the pathological 300s introspect timeout could only be identified by
    reading logs. run_layers now fills the gap for any layer that does not
    measure itself.
    """

    def test_layer_without_self_measurement_gets_a_duration(self):
        layers_out, _ = run_layers(_ctx(), registry=[StubLayer("L2I", order=30)])
        self.assertIsNotNone(layers_out["L2I"].duration_seconds)
        self.assertGreaterEqual(layers_out["L2I"].duration_seconds, 0.0)

    def test_self_measured_duration_is_not_overwritten(self):
        """L1/L2 time the subprocess ALONE — a tighter number than this loop's
        wall clock. The precise one wins; the two are not interchangeable."""

        class SelfTimed(StubLayer):
            def run(self, ctx):
                self.ran = True
                return LayerReport(status="pass", duration_seconds=144.5)

        layers_out, _ = run_layers(_ctx(), registry=[SelfTimed("L1", order=10)])
        self.assertEqual(layers_out["L1"].duration_seconds, 144.5)

    def test_short_circuited_layer_is_not_billed_time_it_never_spent(self):
        l1 = StubLayer("L1", order=10, status="fail")
        l2 = StubLayer("L2", order=20, requires=("L1",))
        layers_out, _ = run_layers(_ctx(), registry=[l1, l2])
        self.assertEqual(layers_out["L2"].status, "skipped")
        self.assertFalse(l2.ran)
        self.assertIsNone(layers_out["L2"].duration_seconds)


if __name__ == "__main__":
    unittest.main()



class TestL2IRetryOnNoVerdict(unittest.TestCase):
    """One bounded, MONOTONE retry when the verdict channel produces nothing.

    Observed 2026-08-03 under a 3-way concurrent grade: the editor completed
    engine init and emitted no verdict block, so the leg became HARNESS-ERROR
    and was lost. The cause was never isolated, which is why the repair is
    cause-agnostic: a retry can only turn "no verdict" into "a verdict". It
    cannot manufacture a PASS or a FAIL, and the model under test gains nothing
    by provoking one -- it is graded either way.
    """

    def setUp(self):
        import tempfile
        import layers.l2_introspect as li
        import layers.registry as reg
        self.li, self.reg = li, reg
        self._real_fn = li.run_l2_introspect
        self._real_root = reg._VERIFY
        self.tmp = Path(tempfile.mkdtemp(prefix="cb-l2i-retry-"))
        (self.tmp / "introspect").mkdir()
        (self.tmp / "introspect" / "probe.py").write_text("x", encoding="utf-8")
        (self.tmp / "out").mkdir()
        reg._VERIFY = self.tmp
        self.calls = []

    def tearDown(self):
        import shutil
        self.li.run_l2_introspect = self._real_fn
        self.reg._VERIFY = self._real_root
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _result(self, status, exit_code=None, total=0, passed=0):
        return types.SimpleNamespace(
            status=status, exit_code=exit_code, total=total,
            passed_count=passed, checks=[], notes=[],
            log_path=Path("/x.log"), result_source="none",
        )

    def _run(self, results):
        def fake(**kw):
            self.calls.append(kw)
            return results[min(len(self.calls) - 1, len(results) - 1)]
        self.li.run_l2_introspect = fake

        ctx = _ctx(introspect_scripts=("probe.py",))
        ctx.args = types.SimpleNamespace(
            r2=False, ue_root=Path("/ue"), use_nullrhi=True)
        ctx.out_dir = self.tmp / "out"
        return L2IntrospectLayer().run(ctx)

    def test_error_is_retried_once_and_a_verdict_wins(self):
        rep = self._run([self._result("error", exit_code=1),
                         self._result("pass", exit_code=0, total=5, passed=5)])
        self.assertEqual(len(self.calls), 2, "the retry did not fire")
        self.assertEqual(rep.status, "pass")
        self.assertTrue(any("retried once" in n for n in rep.notes))

    def test_the_first_failure_log_is_kept_for_diagnosis(self):
        """A retry that overwrites its own evidence hides the problem it papers
        over -- the two attempts must land in different files."""
        self._run([self._result("error", exit_code=1),
                   self._result("pass", exit_code=0, total=1, passed=1)])
        self.assertNotEqual(self.calls[0]["log_path"], self.calls[1]["log_path"])
        self.assertIn("retry", self.calls[1]["log_path"].name)

    def test_a_governed_timeout_is_NOT_retried(self):
        """124 stays graded on purpose -- a submission that hangs the editor
        must not get to cost two full timeouts."""
        rep = self._run([self._result("error", exit_code=124)])
        self.assertEqual(len(self.calls), 1, "124 must not be retried")
        # NOT asserted as "error": this lineage still collapses an L2I error to
        # "fail" (a two-way collapse in registry.py). The three-way collapse that
        # keeps "error" distinct -- so a broken GRADER is not scored against the
        # MODEL -- is a separate fix that has not reached this branch. The
        # contract under test here is only that 124 is not retried.
        self.assertNotEqual(rep.status, "pass")

    def test_a_passing_run_is_never_retried(self):
        self._run([self._result("pass", exit_code=0, total=3, passed=3)])
        self.assertEqual(len(self.calls), 1)

    def test_a_failing_but_READABLE_verdict_is_never_retried(self):
        """status=fail means the grader spoke and the answer was no. Retrying
        that would be re-rolling a real verdict."""
        self._run([self._result("fail", exit_code=0, total=5, passed=2)])
        self.assertEqual(len(self.calls), 1)

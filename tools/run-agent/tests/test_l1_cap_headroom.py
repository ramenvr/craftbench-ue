"""The L1 parallel cap must narrow when commit headroom is thin — never widen.

THE INCIDENT, measured 2026-08-24. A `cb discriminate` leg began with 10.6 GB of
free commit against envgate's 10 GB floor. The preflight WARNED and let it run,
which is correct — it is a PRE-SPEND gate and cannot see a mid-build collapse.
The leg's L1 then died with `fatal error C1060` (compiler out of heap) three
times, all inside ENGINE headers and none in task code, at cap 4. The verdict
recorded was `reference FAIL(skipped)`: the SUBMISSION failing. The same task, on
the same commit, PASSED at cap 2 in 1113 s — LESS wall-clock than the cap-4
attempt that failed.

So the repo's "cap 4 passes, cap 6 fails deterministically on this box" holds
only for an IDLE box. Under load cap 4 dies too, which a constant cannot express.
The graded route already applied a `min(cap, 2)` floor because its stack
stayed up during grading; this is that instinct made data-driven and given to
the path that had none.

Both directions are pinned, because the failure modes are opposite and only one
is loud:

  * too HIGH a cap turns a resource death into a recorded model failure — silent,
    and what happened;
  * too LOW a cap costs wall-clock on every healthy leg, and this helper must
    never impose one when headroom is fine, nor ever RAISE what the operator set.

Stdlib only. No UE, no editor, no tokens.
"""
from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aura_rig import stack_guard as sg  # noqa: E402

FLOOR = 10.0


class TestThinHeadroomNarrows(unittest.TestCase):
    def test_todays_exact_case_becomes_cap_2(self):
        # 10.6 GB free, floor 10, operator cap 4 -> the run that died C1060.
        self.assertEqual(2, sg.l1_cap_for_headroom(10.6, FLOOR, 4))

    def test_just_under_two_floors_is_thin(self):
        self.assertEqual(2, sg.l1_cap_for_headroom(19.9, FLOOR, 4))

    def test_at_two_floors_is_not_thin(self):
        # The band edge is stated explicitly so it cannot drift silently.
        self.assertEqual(4, sg.l1_cap_for_headroom(20.0, FLOOR, 4))

    def test_deep_pressure_still_only_narrows_to_2(self):
        # Below the floor the PREFLIGHT blocks the run outright; this helper is
        # not the place to invent a third band.
        self.assertEqual(2, sg.l1_cap_for_headroom(1.0, FLOOR, 8))


class TestAmpleHeadroomIsLeftAlone(unittest.TestCase):
    def test_the_operator_cap_survives_when_headroom_is_ample(self):
        self.assertEqual(4, sg.l1_cap_for_headroom(30.5, FLOOR, 4))

    def test_it_never_raises_a_low_operator_cap(self):
        for free in (30.5, 100.0, 12.0, None):
            self.assertEqual(1, sg.l1_cap_for_headroom(free, FLOOR, 1),
                             f"raised the operator's cap at free={free}")

    def test_a_high_operator_cap_is_honoured_on_a_quiet_box(self):
        # The helper is a safety narrowing, not a policy on what the operator
        # may choose when there is room.
        self.assertEqual(8, sg.l1_cap_for_headroom(100.0, FLOOR, 8))


class TestUnknownAndUnsetAreTreatedAsDangerous(unittest.TestCase):
    def test_unmeasurable_headroom_narrows_rather_than_assuming_fine(self):
        self.assertEqual(2, sg.l1_cap_for_headroom(None, FLOOR, 4))

    def test_an_unset_operator_cap_becomes_2_not_unset(self):
        # Repo convention: an UNSET cap is the dangerous value — UBT picks its own (6
        # here) and L1 dies deterministically; a fresh worktree once returned
        # 15/15 references FAIL for exactly this.
        self.assertEqual(2, sg.l1_cap_for_headroom(100.0, FLOOR, None))
        self.assertEqual(2, sg.l1_cap_for_headroom(100.0, FLOOR, 0))
        self.assertEqual(2, sg.l1_cap_for_headroom(100.0, FLOOR, -3))

    def test_a_garbage_reading_narrows_rather_than_raising(self):
        self.assertEqual(2, sg.l1_cap_for_headroom("lots", FLOOR, 4))  # type: ignore[arg-type]


class TestTheEnvWrapper(unittest.TestCase):
    def test_it_sets_the_variable_from_the_injected_probes(self):
        env = sg.l1_cap_env(env={"PATH": "x"},
                            read_free=lambda: 10.6,
                            floor=lambda: FLOOR,
                            operator=lambda: 4)
        self.assertEqual("2", env["CRAFTBENCH_L1_MAX_PARALLEL"])
        self.assertEqual("x", env["PATH"], "the caller's env must be preserved")

    def test_ample_headroom_passes_the_operator_cap_through(self):
        env = sg.l1_cap_env(env={}, read_free=lambda: 40.0,
                            floor=lambda: FLOOR, operator=lambda: 4)
        self.assertEqual("4", env["CRAFTBENCH_L1_MAX_PARALLEL"])

    def test_a_probe_that_raises_leaves_the_env_untouched(self):
        # Fail-open in the ONE direction that matters: never hand the build a
        # guessed cap because a probe broke.
        def boom():
            raise OSError("no such counter")

        env = sg.l1_cap_env(env={"CRAFTBENCH_L1_MAX_PARALLEL": "4"},
                            read_free=boom, floor=lambda: FLOOR,
                            operator=lambda: 4)
        self.assertEqual("4", env["CRAFTBENCH_L1_MAX_PARALLEL"])

    def test_it_returns_a_copy_not_the_caller_s_dict(self):
        src = {"PATH": "x"}
        env = sg.l1_cap_env(env=src, read_free=lambda: 40.0,
                            floor=lambda: FLOOR, operator=lambda: 4)
        self.assertNotIn("CRAFTBENCH_L1_MAX_PARALLEL", src)
        self.assertIn("CRAFTBENCH_L1_MAX_PARALLEL", env)


class TestItIsActuallyUsed(unittest.TestCase):
    def test_discriminate_passes_an_env_to_run_task(self):
        # A guard nothing calls is the defect; `cb discriminate` is precisely
        # the path that HAD no floor while the graded route did.
        src = (Path(__file__).resolve().parents[1]
               / "aura_rig" / "discriminate.py").read_text(encoding="utf-8")
        self.assertIn("l1_cap_env()", src)
        self.assertIn("env=_env", src)

    def test_it_is_read_per_leg_not_once_per_sweep(self):
        # Headroom moves DURING a sweep: on 2026-08-24 it fell from 15.1 GB to
        # 8.1 GB across two legs, so a cap resolved once at construction would
        # have been stale by the leg that died.
        src = (Path(__file__).resolve().parents[1]
               / "aura_rig" / "discriminate.py").read_text(encoding="utf-8")
        body = src[src.index("def make_run_task_runner"):]
        self.assertIn("l1_cap_env()", body,
                      "the cap must be resolved inside the per-leg runner")

    def test_the_helper_documents_the_measurement_it_came_from(self):
        doc = inspect.getdoc(sg.l1_cap_for_headroom) or ""
        self.assertIn("C1060", doc)


if __name__ == "__main__":
    unittest.main()

"""Unit tests for the verifier's NON-GRADED harness-error state (exit 7).

Two findings are pinned here.

FINDING 1 — the vacuous PASS. ``overall`` was
``all(lr.status == "pass" for lr in layers_out.values())`` and ``all({})`` is
True, so a spec naming only L4/L5 (both in spec.RECOGNIZED_LAYERS, neither
implemented in the registry) produced ``layers_out == {}``, graded PASS, and
exited 0 with ``"layers": {}`` in report.json. Nothing was built, nothing was
run, and the submission was certified.

FINDING 2 — there was no "the harness could not answer" state at the verifier
boundary, so every such run had to be squeezed into PASS/FAIL. Exit 7 is that
state, and it is NON-GRADED (adapters.base keeps HARNESS-ERROR out of
GRADED_VERDICTS).

The load-bearing test in this file is
``TestSkippedDiscriminator.test_l2_skipped_after_l1_FAIL_stays_graded``: the
registry emits ``status="skipped"`` for EVERY dependent of a failed layer, so
"L2 is skipped" is also the shape of an ordinary agent compile failure. Keying
the harness-error on that status alone would move every compile failure in the
benchmark out of the denominator. The discriminator is therefore the DEPENDENCY,
never the note prose (the two skip producers differ only in their notes text).

No UE, no network, no subprocess.

    py -3 -m unittest tools.verify-single.tests.test_verdict_taxonomy
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_VERIFY = _HERE.parent
if str(_VERIFY) not in sys.path:
    sys.path.insert(0, str(_VERIFY))

import run_task  # noqa: E402
from layers.base import LayerContext  # noqa: E402
from layers.registry import REGISTRY  # noqa: E402
from report import LayerReport  # noqa: E402
from run_task import harness_error_reasons  # noqa: E402
from spec import IMPLEMENTED_LAYERS, RECOGNIZED_LAYERS  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]


def _lr(status: str, **kw) -> LayerReport:
    return LayerReport(status=status, **kw)


def _spec_context(task) -> LayerContext:
    """The minimal LayerContext an ``applies()`` predicate reads.

    ``applies()`` is deliberately cheap on every registered layer: the gating
    ones read either ``ctx.requested_layers`` (L1, L2 — L-token-triggered) or
    one parsed field of ``ctx.task`` (ART -> ``artifact_path``, L3 ->
    ``l3_fixtures``, L2I -> ``introspect_scripts``). None of them touches the
    filesystem, launches anything, or reads the manifest, so the paths below are
    inert placeholders and this stays a no-UE, no-subprocess unit test.

    ``requested_layers`` is the spec's own ``layers:`` list because that is what
    ``run_task.main`` defaults it to when ``--layers`` is not passed, and a
    certified run never passes ``--layers``.
    """
    return LayerContext(
        task=task,
        args=argparse.Namespace(r2=False),
        project_path=Path("unused.uproject"),
        workdir_substrate=Path("unused"),
        out_dir=Path("unused"),
        manifest=None,
        substrate_src=Path("unused"),
        requested_layers=set(task.layers),
    )


def _landing_gating_keys(task) -> list:
    """The gating layer keys that would actually reach ``layers_out`` for this
    spec, in registry order — i.e. ``run_layers``' own selection step, minus the
    dependency short-circuit (which needs run results, not just the spec)."""
    ctx = _spec_context(task)
    return [
        layer.key
        for layer in sorted(REGISTRY, key=lambda l: l.order)
        if layer.gating and layer.applies(ctx)
    ]


def landability_violations(task) -> list:
    """Ways ``task``'s declared gating layers would NOT land in ``layers_out``.

    Empty == the spec is landable. This is the whole gate; the sweep below runs
    it over every spec on disk and ``TestLandabilityAssertionHasTeeth`` runs the
    SAME function over hand-built bad specs, so the teeth test cannot drift away
    from what the sweep actually enforces.

    Three checks, all registry-driven:

    (a) every declared token that is not advisory names an IMPLEMENTED gating
        layer. A recognized-but-unimplemented token (L4/L5) is the one shape
        ``harness_error_reasons`` cannot see: predicate (2) is keyed on
        ``k in requires_by_key``, so an unregistered key never appears in
        ``missing``, and predicate (1) needs ``layers_out`` to be EMPTY, which a
        co-declared L1 prevents. ``layers: [L1, L2, L4]`` would grade a clean
        PASS with L4 silently dropped.
    (b) that layer's own ``applies()`` is satisfied BY THIS SPEC, so the gate
        really reaches ``layers_out`` — the direct negation of predicate (2).
    (c) at least one gating layer lands, so predicate (1)'s vacuous-PASS shape
        is unreachable for this spec.
    """
    gating = {layer.key: layer for layer in REGISTRY if layer.gating}
    advisory = {layer.key for layer in REGISTRY if not layer.gating}
    ctx = _spec_context(task)
    out = []
    for key in task.layers:
        if key in advisory:
            continue            # R2: gating=False, never lands by construction
        if key not in gating:
            out.append(
                f"{key} is a recognized token that no registry layer claims, so "
                "it can never land in layers_out and NO harness_error_reasons "
                "predicate reports it — the grade is silently narrower than the "
                "spec declares"
            )
            continue
        if not gating[key].applies(ctx):
            out.append(
                f"{key} is declared but its applies() is False on this spec: the "
                "declared gate would silently not run (predicate 2)"
            )
    if not _landing_gating_keys(task):
        out.append("no gating layer lands: `overall` would be a vacuous PASS")
    return out


# --------------------------------------------------------------------------- #
# (1) the reference shape — the all-references gate must be untouched          #
# --------------------------------------------------------------------------- #

class TestReferencePassShapeNeverFires(unittest.TestCase):
    """C5: no predicate may fire on the shape a reference PASS produces.

    For the L1+L2 specs (every spec until 2026-07-27, and still the large
    majority) that shape is exactly {L1: pass exit 0, L2: pass}. The sweep test
    below generalizes the claim to whatever gating layers a spec declares."""

    def test_reference_pass_shape_has_no_reasons(self):
        layers_out = {
            "L1": _lr("pass", exit_code=0, warnings_in_agent_files=0),
            "L2": _lr("pass", exit_code=0, tests_run=1, tests_passed=1),
        }
        self.assertEqual(harness_error_reasons(layers_out, ("L1", "L2")), [])

    def test_reference_pass_shape_multi_fixture(self):
        layers_out = {
            "L1": _lr("pass", exit_code=0),
            "L2": _lr("pass", exit_code=0, tests_run=2, tests_passed=2),
        }
        self.assertEqual(harness_error_reasons(layers_out, ("L1", "L2")), [])

    def test_every_shipping_spec_declares_only_landable_gating_layers(self):
        """The structural half of the C5 argument, read off the specs on disk.

        INTENT (unchanged): a shipping spec must not declare a gating layer that
        cannot LAND in ``layers_out`` — that is precisely what predicate (2)
        reports — so the guard is provably inert on the reference sweep.

        The assertion is now REGISTRY-DRIVEN rather than an equality against
        ``("L1","L2")``. For every spec: each declared token that names an
        implemented gating layer must have that layer's own ``applies()``
        satisfied by the spec (so it really reaches ``layers_out``), at least one
        gating layer must land (predicate (1)'s vacuous-PASS shape is
        unreachable), and ``harness_error_reasons`` must be silent for the PASS
        shape the spec produces.

        Why it changed (2026-07-27): the equality was true of all 15 specs, but
        it also asserted away the very check its own message asked for — "a spec
        declaring another gating layer needs its trigger checked against
        predicate (2)" — and it hard-blocked every ``[L1, L2I]`` spec the kp-
        lane authors, the first of which is
        ``tasks/bp/t1-hero-blueprint-copy-with-flashlight``. The trigger is
        now CHECKED instead of forbidden. Its teeth are pinned by
        ``TestLandabilityAssertionHasTeeth`` below: a spec that declares a layer
        it cannot trigger still fails this test.
        """
        specs = sorted((REPO_ROOT / "tasks").glob("*/*/task.md"))
        self.assertGreaterEqual(len(specs), 15, f"found only {len(specs)} specs")
        for path in specs:
            task = run_task.parse_task_spec(path)
            with self.subTest(spec=str(path.relative_to(REPO_ROOT))):
                # (a)+(b)+(c): every declared gating layer really lands.
                self.assertEqual(landability_violations(task), [])
                # (d) and harness_error_reasons is CLEAN for this spec's own
                #     layer tuple, on the PASS shape its landing layers produce.
                landed = _landing_gating_keys(task)
                self.assertEqual(
                    harness_error_reasons(
                        {k: _lr("pass", exit_code=0) for k in landed},
                        task.layers,
                    ),
                    [],
                )

    def test_the_shipping_l2i_specs_really_land_their_L2I_gate(self):
        """§9.1's other half: don't just STOP forbidding L2I — demonstrate it.

        For every on-disk spec declaring L2I, the registry layer's own
        ``applies()`` must be satisfied, so ``L2I`` genuinely appears in
        ``layers_out`` and predicate (2) has nothing to report. This is the
        assertion that would have caught the pilot
        (``tasks/bp/t1-hero-blueprint-copy-with-flashlight``) shipping with a
        ``layers:`` line its ``## Verifier introspection`` section did not back.
        """
        l2i_specs = [
            p for p in sorted((REPO_ROOT / "tasks").glob("*/*/task.md"))
            if "L2I" in run_task.parse_task_spec(p).layers
        ]
        self.assertTrue(
            l2i_specs,
            "no shipping spec declares L2I — the landability sweep has silently "
            "degraded to the (L1, L2) coverage the old equality already had",
        )
        for path in l2i_specs:
            with self.subTest(spec=str(path.relative_to(REPO_ROOT))):
                task = run_task.parse_task_spec(path)
                self.assertTrue(task.introspect_scripts, "L2I declared, no grader")
                self.assertIn("L2I", _landing_gating_keys(task))
                self.assertEqual(
                    harness_error_reasons(
                        {k: _lr("pass", exit_code=0)
                         for k in _landing_gating_keys(task)},
                        task.layers,
                    ),
                    [],
                )

    def test_the_shipping_layer_tuples_are_visible(self):
        """Inventory, not a gate — the sweep above no longer pins one tuple, so
        record what is actually on disk. Kept assertion-light on purpose: adding
        an ``[L1, L2I]`` task must not require editing this file."""
        tuples = sorted({
            tuple(run_task.parse_task_spec(p).layers)
            for p in (REPO_ROOT / "tasks").glob("*/*/task.md")
        })
        self.assertIn(("L1", "L2"), tuples)
        for t in tuples:
            self.assertIn("L1", t, f"a spec declares {t} with no build layer")


class TestLandabilityAssertionHasTeeth(unittest.TestCase):
    """Proof that replacing the ``== ("L1","L2")`` equality did not replace a
    gate with a tautology. Two independent layers now stop an unlandable spec.
    """

    class _StubSpec:
        """Only the fields the gating ``applies()`` predicates read."""
        def __init__(self, layers, introspect_scripts=()):
            self.layers = tuple(layers)
            self.introspect_scripts = tuple(introspect_scripts)

    def test_declared_but_untriggerable_layer_is_caught(self):
        # `layers: [L1, L2I]` with NO introspect script: L2I.applies() is False,
        # so the declared gate would silently not run.
        bad = self._StubSpec(("L1", "L2I"))
        gating = {layer.key: layer for layer in REGISTRY if layer.gating}
        self.assertFalse(gating["L2I"].applies(_spec_context(bad)))
        self.assertEqual(_landing_gating_keys(bad), ["L1"])
        # The sweep's OWN gate rejects it...
        self.assertTrue(landability_violations(bad))
        # ...and that is exactly the shape predicate (2) reports.
        self.assertTrue(
            harness_error_reasons({"L1": _lr("pass", exit_code=0)}, bad.layers)
        )

    def test_a_recognized_but_unimplemented_layer_is_caught(self):
        """The hole the ``== ("L1","L2")`` equality closed by accident.

        ``L4``/``L5`` are in ``spec.RECOGNIZED_LAYERS`` (so they parse) and in no
        registry layer (so they never land). With ``L1`` co-declared, layers_out
        is non-empty, so predicate (1) is silent; and predicate (2) only looks at
        keys the registry knows, so it is silent too. Nothing in
        ``harness_error_reasons`` reports it — the sweep must.
        """
        bad = self._StubSpec(("L1", "L2", "L4"))
        self.assertIn("L4", RECOGNIZED_LAYERS)
        self.assertNotIn("L4", IMPLEMENTED_LAYERS)
        self.assertNotIn("L4", {layer.key for layer in REGISTRY})
        # Neither runtime predicate sees it: this run grades a clean PASS.
        self.assertEqual(
            harness_error_reasons(
                {"L1": _lr("pass", exit_code=0), "L2": _lr("pass")}, bad.layers
            ),
            [],
        )
        # The sweep is the only thing standing between that spec and a grade
        # silently missing a declared gate.
        violations = landability_violations(bad)
        self.assertTrue(violations)
        self.assertIn("L4", violations[0])

    def test_a_triggerable_l2i_spec_is_clean(self):
        good = self._StubSpec(("L1", "L2I"), introspect_scripts=("grader.py",))
        self.assertEqual(landability_violations(good), [])
        self.assertEqual(_landing_gating_keys(good), ["L1", "L2I"])
        self.assertEqual(
            harness_error_reasons(
                {"L1": _lr("pass", exit_code=0), "L2I": _lr("pass")}, good.layers
            ),
            [],
        )

    def test_the_parser_also_refuses_the_unlandable_shape(self):
        """Belt to the sweep's braces: spec.py rejects `L2I` with no
        `introspect:` list at parse time, so the bad spec cannot even reach the
        runner. The sweep still checks it, because that parser rule is the ONLY
        thing making L2I landability free — L3/ART have no equivalent."""
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "task.md"
            path.write_text(
                "---\nid: unlandable\nsubstrate: FakeSub\nlayers: [L1, L2I]\n---\n"
                "\n## Prompt given to the agent\n\n> Do the thing.\n",
                encoding="utf-8",
            )
            with self.assertRaises(Exception):
                run_task.parse_task_spec(path)


# --------------------------------------------------------------------------- #
# (2) finding 1 — empty / incomplete gating set                               #
# --------------------------------------------------------------------------- #

class TestEmptyOrIncompleteGatingSet(unittest.TestCase):
    def test_empty_layers_out_is_a_harness_error(self):
        reasons = harness_error_reasons({}, ("L4", "L5"))
        self.assertEqual(len(reasons), 1)
        self.assertIn("vacuous PASS", reasons[0])

    def test_l4_l5_are_recognized_but_not_implemented(self):
        # The exact precondition that produces layers_out == {}: the tokens
        # parse, so the spec is valid, but no layer claims them.
        for tok in ("L4", "L5"):
            self.assertIn(tok, RECOGNIZED_LAYERS)
            self.assertNotIn(tok, IMPLEMENTED_LAYERS)

    def test_requested_gating_token_that_produced_no_key(self):
        reasons = harness_error_reasons({"L1": _lr("pass", exit_code=0)}, ("L1", "L2"))
        self.assertEqual(len(reasons), 1)
        self.assertIn("L2", reasons[0])
        self.assertIn("silently dropped", reasons[0])

    def test_section_triggered_layer_declared_but_not_triggered(self):
        # --layers L1,L2I on a task with no introspect scripts: L2I applies()
        # is False, so the declared gate silently does not run.
        reasons = harness_error_reasons({"L1": _lr("pass", exit_code=0)}, ("L1", "L2I"))
        self.assertTrue(any("L2I" in r for r in reasons))

    def test_advisory_layer_token_is_never_reported_missing(self):
        # R2 is gating=False: it can never land in layers_out by construction,
        # so a `layers:` list mentioning it must not trip predicate (2).
        layers_out = {"L1": _lr("pass", exit_code=0), "L2": _lr("pass")}
        self.assertEqual(harness_error_reasons(layers_out, ("L1", "L2", "R2")), [])

    def test_unimplemented_tokens_alongside_real_ones_are_not_missing(self):
        # L4/L5 are not gating layers in the registry, so with L1+L2 present
        # there is nothing to report — the run WAS measured.
        layers_out = {"L1": _lr("pass", exit_code=0), "L2": _lr("pass")}
        self.assertEqual(
            harness_error_reasons(layers_out, ("L1", "L2", "L4", "L5")), []
        )

    def test_extra_layer_beyond_the_request_is_fine(self):
        # L2I is section-triggered, so it can land without being requested.
        layers_out = {
            "L1": _lr("pass", exit_code=0),
            "L2": _lr("pass"),
            "L2I": _lr("pass"),
        }
        self.assertEqual(harness_error_reasons(layers_out, ("L1", "L2")), [])


# --------------------------------------------------------------------------- #
# (3) the skipped discriminator — the blocking defect of the rejected design   #
# --------------------------------------------------------------------------- #

class TestSkippedDiscriminator(unittest.TestCase):
    def test_l2_skipped_after_l1_FAIL_stays_graded(self):
        """THE regression guard. registry.run_layers emits skipped for every
        dependent of a failed layer, so this is the shape of "the agent's C++
        does not compile". It MUST remain a graded FAIL."""
        layers_out = {
            "L1": _lr("fail", exit_code=1),
            "L2": _lr("skipped", notes=["short-circuited: L1 did not pass"]),
        }
        self.assertEqual(harness_error_reasons(layers_out, ("L1", "L2")), [])

    def test_l2_skipped_after_l1_PASS_stays_graded_BY_DECISION(self):
        """A zero-test L2 with L1 passing stays a GRADED FAIL — deliberately.

        This predicate was written, reviewed, and then REMOVED (2026-07-26). It
        is too broad by one case: an agent whose code compiles and then CRASHES
        the PIE editor also lands on tests_run==0 -> status="skipped" with L1
        passing, so routing this to HARNESS-ERROR would move crash-failures out
        of the pass-rate denominator — rewarding crashing over failing an
        assertion, and contradicting the "ambiguity resolves toward GRADED" rule
        that keeps L1 exit 124 graded.

        Separating the two needs `L2Result.result_source` ("none" == the editor
        never produced an automation result), which `LayerReport` does not carry.
        See the (4) comment block in run_task.harness_error_reasons.

        If you are here because you re-added the predicate: this test failing is
        the intended alarm. Export result_source first, then narrow the predicate
        to result_source != "none" — do not simply widen it again.
        """
        layers_out = {
            "L1": _lr("pass", exit_code=0),
            "L2": _lr("skipped", exit_code=0, tests_run=0, tests_passed=0),
        }
        self.assertEqual(harness_error_reasons(layers_out, ("L1", "L2")), [])

    def test_discriminator_ignores_note_prose_entirely(self):
        """Same statuses, swapped notes: the verdict must not move. The two
        skip producers differ ONLY in their notes text, so a textual
        discriminator would flip both of these the wrong way."""
        short_circuit_note = ["short-circuited: L1 did not pass"]
        no_tests_note = [
            "no tests counted; check that the test filter matches a "
            "discoverable test (see README known assumptions)"
        ]
        # L1 FAILED but carries the "no tests counted" prose -> still graded.
        self.assertEqual(
            harness_error_reasons(
                {"L1": _lr("fail", exit_code=1),
                 "L2": _lr("skipped", notes=no_tests_note)},
                ("L1", "L2"),
            ),
            [],
        )
        # L1 PASSED but carries the short-circuit prose -> still graded, because
        # the zero-test predicate is deliberately not implemented (see
        # test_l2_skipped_after_l1_PASS_stays_graded_BY_DECISION). The point this
        # case still makes: the note prose is irrelevant either way.
        self.assertEqual(
            harness_error_reasons(
                {"L1": _lr("pass", exit_code=0),
                 "L2": _lr("skipped", notes=short_circuit_note)},
                ("L1", "L2"),
            ),
            [],
        )

    def test_l2i_skipped_after_l1_fail_stays_graded(self):
        layers_out = {
            "L1": _lr("fail", exit_code=1),
            "L2": _lr("skipped"),
            "L2I": _lr("skipped"),
        }
        self.assertEqual(harness_error_reasons(layers_out, ("L1", "L2")), [])

    def test_skipped_with_absent_dependency_stays_graded_BY_DECISION(self):
        # `--layers L2` with no L1. Same decision as the L1-PASS case above: the
        # zero-test predicate is not implemented, so this stays graded rather
        # than becoming a non-graded harness error.
        layers_out = {"L2": _lr("skipped", tests_run=0)}
        self.assertEqual(harness_error_reasons(layers_out, ("L2",)), [])

    def test_l2_fail_is_never_a_harness_error(self):
        layers_out = {
            "L1": _lr("pass", exit_code=0),
            "L2": _lr("fail", exit_code=1, tests_run=1, tests_passed=0),
        }
        self.assertEqual(harness_error_reasons(layers_out, ("L1", "L2")), [])


# --------------------------------------------------------------------------- #
# (4) L1 exit codes — 127 routes, 124 deliberately does NOT                    #
# --------------------------------------------------------------------------- #

class TestL1ExitCodeRouting(unittest.TestCase):
    def test_l1_exit_127_is_a_harness_error(self):
        # l1_build synthesizes 127 on FileNotFoundError launching UBT / the
        # editor binary, and flags the provenance. The flag is required because
        # the code alone is not: Build.cs is agent-writable, so a submission can
        # exit the build tool with any status (test_l1_spawn_fault.py).
        layers_out = {
            "L1": _lr("fail", exit_code=127, build_tool_never_ran=True),
            "L2": _lr("skipped", notes=["short-circuited: L1 did not pass"]),
        }
        reasons = harness_error_reasons(layers_out, ("L1", "L2"))
        self.assertEqual(len(reasons), 1)
        self.assertIn("exit 127", reasons[0])

    def test_the_asymmetry_is_an_executable_claim(self):
        self.assertIn(run_task.L1_EXIT_EXEC_FAILED, run_task.L1_HARNESS_ERROR_EXITS)
        self.assertNotIn(run_task.L1_EXIT_TIMEOUT, run_task.L1_HARNESS_ERROR_EXITS)
        self.assertEqual(run_task.L1_EXIT_TIMEOUT, 124)
        self.assertEqual(run_task.L1_EXIT_EXEC_FAILED, 127)

    def test_l1_exit_124_stays_a_graded_fail(self):
        """DELIBERATE ASYMMETRY. 124 is the governed build timeout, and a
        pathological submission CAN hang a compile (runaway template
        instantiation). Routing it to the non-graded state would hand every
        agent an opt-out of the denominator: hang the build, be excluded
        instead of scored. Ambiguity resolves toward GRADED."""
        layers_out = {
            "L1": _lr("fail", exit_code=124),
            "L2": _lr("skipped", notes=["short-circuited: L1 did not pass"]),
        }
        self.assertEqual(harness_error_reasons(layers_out, ("L1", "L2")), [])

    def test_ordinary_compile_failure_stays_a_graded_fail(self):
        layers_out = {
            "L1": _lr("fail", exit_code=6),   # UBT's own build-failure code
            "L2": _lr("skipped", notes=["short-circuited: L1 did not pass"]),
        }
        self.assertEqual(harness_error_reasons(layers_out, ("L1", "L2")), [])

    def test_l1_pass_with_exit_127_impossible_shape_not_flagged(self):
        # Defensive: the predicate is anchored on "did not pass" too, so a
        # (nonsensical) passing L1 is never reported.
        layers_out = {"L1": _lr("pass", exit_code=127), "L2": _lr("pass")}
        self.assertEqual(harness_error_reasons(layers_out, ("L1", "L2")), [])


# --------------------------------------------------------------------------- #
# (4b) L2I status="error" — a broken GRADER is not a model failure            #
# --------------------------------------------------------------------------- #

class TestL2IntrospectErrorRouting(unittest.TestCase):
    """``layers/l2_introspect.py`` distinguishes a THIRD status, "error", as its
    fail-safe: no verdict block, malformed JSON, no ``checks`` list, editor
    binary absent — plus the registry's own "the verifier-owned script file is
    MISSING". Until 2026-07-27 ``registry.L2IntrospectLayer`` collapsed all of
    them to "fail", so a typo in a grader NOBODY let the agent touch was scored
    against the agent. That is the exact condition the verdict contract forbids.
    """

    def test_l2i_error_is_a_harness_error(self):
        layers_out = {
            "L1": _lr("pass", exit_code=0),
            "L2I": _lr("error", exit_code=127,
                       notes=["hero_check.py: MISSING verifier script at ..."]),
        }
        reasons = harness_error_reasons(layers_out, ("L1", "L2I"))
        self.assertEqual(len(reasons), 1)
        self.assertIn("L2I status=error", reasons[0])

    def test_l2i_error_dominates_a_real_l2_fail(self):
        """An incomplete gate must not certify: if any verdict channel died the
        run is not a measurement, even when a sibling layer did measure."""
        layers_out = {
            "L1": _lr("pass", exit_code=0),
            "L2": _lr("fail", exit_code=1, tests_run=1, tests_passed=0),
            "L2I": _lr("error", exit_code=1),
        }
        self.assertTrue(harness_error_reasons(layers_out, ("L1", "L2", "L2I")))

    def test_l2i_error_exit_124_stays_a_graded_fail(self):
        """DELIBERATE ASYMMETRY, the twin of L1's. 124 is the governed timeout,
        and agent C++ IS linked into the editor L2I launches, so a pathological
        submission can hang it. Routing it to the non-graded state would hand
        every agent an opt-out of the denominator."""
        layers_out = {
            "L1": _lr("pass", exit_code=0),
            "L2I": _lr("error", exit_code=124, notes=["editor run failed: timeout"]),
        }
        self.assertEqual(harness_error_reasons(layers_out, ("L1", "L2I")), [])

    def test_the_l2i_asymmetry_is_an_executable_claim(self):
        self.assertEqual(run_task.LAYER_STATUS_ERROR, "error")
        self.assertIn(run_task.L1_EXIT_TIMEOUT, run_task.LAYER_ERROR_GRADED_EXITS)
        self.assertNotIn(
            run_task.L1_EXIT_EXEC_FAILED, run_task.LAYER_ERROR_GRADED_EXITS
        )

    def test_l2i_fail_is_never_a_harness_error(self):
        """The whole point of keeping "error" separate: a grader that RAN and
        found the asset wrong is a graded FAIL and must stay one."""
        layers_out = {
            "L1": _lr("pass", exit_code=0),
            "L2I": _lr("fail", tests_run=7, tests_passed=5),
        }
        self.assertEqual(harness_error_reasons(layers_out, ("L1", "L2I")), [])

    def test_l2i_skipped_error_free_shapes_are_untouched(self):
        for status in ("pass", "skipped"):
            with self.subTest(status=status):
                layers_out = {"L1": _lr("pass", exit_code=0), "L2I": _lr(status)}
                self.assertEqual(harness_error_reasons(layers_out, ("L1", "L2I")), [])

    def test_predicate_is_keyed_on_status_not_on_the_layer_key(self):
        """A second layer adopting the same fail-safe needs no edit here."""
        layers_out = {"L1": _lr("error", exit_code=127)}
        self.assertTrue(
            any("L1 status=error" in r
                for r in harness_error_reasons(layers_out, ("L1",)))
        )

    def test_advisory_layer_error_is_ignored(self):
        """R2 is gating=False, so even an "error" from it cannot move a verdict.
        (It never lands in layers_out, but the predicate is belt-and-braces.)"""
        layers_out = {
            "L1": _lr("pass", exit_code=0),
            "L2": _lr("pass"),
            "R2": _lr("error"),
        }
        self.assertEqual(harness_error_reasons(layers_out, ("L1", "L2", "R2")), [])


class TestL2IntrospectLayerEmitsError(unittest.TestCase):
    """The other half of fix A: the registry must PRODUCE the "error" status
    (and the exit code the carve-out reads) instead of collapsing to "fail"."""

    def _ctx(self, scripts):
        from layers.base import LayerContext

        class _Task:
            introspect_scripts = tuple(scripts)

        class _Args:
            ue_root = Path("no-such-ue")
            use_nullrhi = True

        return LayerContext(
            task=_Task(), args=_Args(), project_path=Path("x.uproject"),
            workdir_substrate=Path("."), out_dir=Path("."),
            manifest=None, substrate_src=Path("."), requested_layers={"L1", "L2I"},
        )

    def test_missing_script_yields_error_not_fail(self):
        from layers.registry import L2IntrospectLayer

        rep = L2IntrospectLayer().run(
            self._ctx(["definitely_not_a_real_grader__fix_a.py"])
        )
        self.assertEqual(rep.status, "error")
        self.assertNotEqual(rep.status, "fail")   # the bug being fixed
        self.assertEqual(rep.exit_code, 127)
        self.assertTrue(any("MISSING verifier script" in n for n in rep.notes))

    def test_that_report_reaches_a_harness_error_verdict(self):
        from layers.registry import L2IntrospectLayer

        rep = L2IntrospectLayer().run(
            self._ctx(["definitely_not_a_real_grader__fix_a.py"])
        )
        layers_out = {"L1": _lr("pass", exit_code=0), "L2I": rep}
        self.assertTrue(harness_error_reasons(layers_out, ("L1", "L2I")))


# --------------------------------------------------------------------------- #
# (4c) end to end: an L2I task with a broken grader exits 7, NOT 1            #
# --------------------------------------------------------------------------- #

_L2I_SPEC = """\
---
id: l2i-broken-grader-probe
substrate: FakeSub
layers: [L2I]
introspect: [definitely_not_a_real_grader__fix_a.py]
---

## Prompt given to the agent

> Do the thing.
"""


class TestL2IntrospectErrorEndToEnd(unittest.TestCase):
    """No UE needed: the MISSING-script branch returns before any editor is
    launched, and L1 is not requested so nothing builds."""

    def _fixture(self, tmp: Path):
        substrate = tmp / "UE-projects" / "FakeSub"
        (substrate / "Source" / "FakeSub").mkdir(parents=True)
        (substrate / "FakeSub.uproject").write_text(
            json.dumps({"FileVersion": 3, "EngineAssociation": "5.8",
                        "Plugins": []}),
            encoding="utf-8",
        )
        (substrate / "AGENT_WRITABLE.json").write_text(
            json.dumps(_MANIFEST), encoding="utf-8"
        )
        spec_path = tmp / "task.md"
        spec_path.write_text(_L2I_SPEC, encoding="utf-8")
        submission = tmp / "sub"
        submission.mkdir()
        return spec_path, substrate, submission

    def test_broken_grader_exits_7_not_1(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            spec_path, substrate, submission = self._fixture(tmp)
            report_json = tmp / "report.json"
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                rc = run_task.main([
                    "--task", str(spec_path),
                    "--submission", str(submission),
                    "--ue-root", str(tmp / "no-ue"),
                    "--substrate-overlay", str(substrate),
                    "--substrate-from-live",
                    "--report-json", str(report_json),
                ])

            self.assertEqual(rc, run_task.EXIT_HARNESS_ERROR)
            self.assertNotEqual(rc, run_task.EXIT_FAIL)   # the bug being fixed
            self.assertIn("harness could not grade this run", err.getvalue())

            data = json.loads(report_json.read_text(encoding="utf-8"))
            self.assertEqual(data["overall"], run_task.OVERALL_HARNESS_ERROR)
            self.assertEqual(data["layers"]["L2I"]["status"], "error")
            # NOT graded: the string every rate-computing consumer allowlists.
            self.assertNotIn(data["overall"], ("pass", "fail"))


# --------------------------------------------------------------------------- #
# (5) exit-code taxonomy constants                                            #
# --------------------------------------------------------------------------- #

class TestExitCodeTaxonomy(unittest.TestCase):
    def test_constants(self):
        self.assertEqual(run_task.EXIT_PASS, 0)
        self.assertEqual(run_task.EXIT_FAIL, 1)
        self.assertEqual(run_task.EXIT_USAGE, 2)
        self.assertEqual(run_task.EXIT_SANDBOX_REJECT, 4)
        self.assertEqual(run_task.EXIT_NO_UPROJECT, 5)
        self.assertEqual(run_task.EXIT_HARNESS_ERROR, 7)

    def test_no_constant_claims_3_or_6(self):
        """3 is RETIRED-AND-RESERVED (the removed hash-manifest reject); 6 is
        UBT's own build-failure code and docs/harness-tour/02-verify-single.md
        documents that this process never emits it."""
        claimed = {
            v for k, v in vars(run_task).items()
            if k.startswith("EXIT_") and isinstance(v, int)
        }
        self.assertNotIn(3, claimed)
        self.assertNotIn(6, claimed)

    def test_harness_error_code_cannot_collide_with_posix_conventions(self):
        # 124 timeout / 126 not-executable / 127 not-found / 128+N signal.
        self.assertLess(run_task.EXIT_HARNESS_ERROR, 124)

    def test_overall_string(self):
        self.assertEqual(run_task.OVERALL_HARNESS_ERROR, "harness-error")
        # Uppercased (adapters.base._overall_from_report_json) it must be the
        # shared verdict string, so the report route and the exit-code route
        # cannot disagree.
        self.assertEqual(run_task.OVERALL_HARNESS_ERROR.upper(), "HARNESS-ERROR")


# --------------------------------------------------------------------------- #
# (6) cli() — the uncaught-exception trap                                     #
# --------------------------------------------------------------------------- #

class TestCliCrashTrap(unittest.TestCase):
    def setUp(self) -> None:
        self._main = run_task.main

    def tearDown(self) -> None:
        run_task.main = self._main

    def test_uncaught_exception_becomes_exit_7_not_1(self):
        def boom(argv=None):
            raise RuntimeError("kaboom")

        run_task.main = boom
        err = io.StringIO()
        with redirect_stderr(err):
            rc = run_task.cli([])
        self.assertEqual(rc, run_task.EXIT_HARNESS_ERROR)
        self.assertNotEqual(rc, run_task.EXIT_FAIL)
        self.assertIn("kaboom", err.getvalue())          # traceback preserved
        self.assertIn("HARNESS-ERROR", err.getvalue())

    def test_normal_return_codes_pass_through(self):
        for code in (0, 1, 2, 4, 5):
            run_task.main = lambda argv=None, _c=code: _c
            self.assertEqual(run_task.cli([]), code)

    def test_systemexit_is_not_swallowed(self):
        def bail(argv=None):
            raise SystemExit(3)

        run_task.main = bail
        with self.assertRaises(SystemExit):
            run_task.cli([])

    def test_keyboard_interrupt_is_not_swallowed(self):
        def interrupt(argv=None):
            raise KeyboardInterrupt

        run_task.main = interrupt
        with self.assertRaises(KeyboardInterrupt):
            run_task.cli([])


# --------------------------------------------------------------------------- #
# (7) end-to-end: main() on an L4/L5-only spec (finding 1, no UE needed)       #
# --------------------------------------------------------------------------- #

_SPEC = """\
---
id: harness-error-probe
substrate: FakeSub
layers: [L4, L5]
---

## Prompt given to the agent

> Do the thing.
"""

_MANIFEST = {
    "substrate": "FakeSub",
    "game_module": "FakeSub",
    "writable": ["Source/FakeSub/"],
    "deny": ["Source/FakeSubTests/"],
}


class TestEmptyGatingSetEndToEnd(unittest.TestCase):
    """A spec naming ONLY unimplemented layers used to exit 0 / PASS with
    ``"layers": {}``. It must now exit 7 with overall "harness-error".

    Reaches the layer stage with no UE install: --substrate-from-live copies a
    stub substrate (no git needed), the submission is empty (sandbox-clean), and
    no layer applies, so nothing tries to build or launch an editor.
    """

    def _fixture(self, tmp: Path) -> tuple[Path, Path, Path]:
        substrate = tmp / "UE-projects" / "FakeSub"
        (substrate / "Source" / "FakeSub").mkdir(parents=True)
        (substrate / "FakeSub.uproject").write_text(
            json.dumps({"FileVersion": 3, "EngineAssociation": "5.8",
                        "Plugins": []}),
            encoding="utf-8",
        )
        (substrate / "AGENT_WRITABLE.json").write_text(
            json.dumps(_MANIFEST), encoding="utf-8"
        )
        spec_path = tmp / "task.md"
        spec_path.write_text(_SPEC, encoding="utf-8")
        submission = tmp / "sub"
        submission.mkdir()
        return spec_path, substrate, submission

    def test_exit_7_and_harness_error_report(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            spec_path, substrate, submission = self._fixture(tmp)
            report_json = tmp / "report.json"
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                rc = run_task.main([
                    "--task", str(spec_path),
                    "--submission", str(submission),
                    "--ue-root", str(tmp / "no-ue"),
                    "--substrate-overlay", str(substrate),
                    "--substrate-from-live",
                    "--report-json", str(report_json),
                ])

            self.assertEqual(rc, run_task.EXIT_HARNESS_ERROR)
            self.assertNotEqual(rc, run_task.EXIT_PASS)   # the vacuous PASS is gone
            self.assertIn("harness could not grade this run", err.getvalue())

            data = json.loads(report_json.read_text(encoding="utf-8"))
            self.assertEqual(data["overall"], run_task.OVERALL_HARNESS_ERROR)
            self.assertEqual(data["layers"], {})          # the finding-1 signature
            self.assertIn("HARNESS-ERROR", out.getvalue())

    def test_report_overall_is_not_pass_or_fail(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            spec_path, substrate, submission = self._fixture(tmp)
            report_json = tmp / "report.json"
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                run_task.main([
                    "--task", str(spec_path),
                    "--submission", str(submission),
                    "--ue-root", str(tmp / "no-ue"),
                    "--substrate-overlay", str(substrate),
                    "--substrate-from-live",
                    "--report-json", str(report_json),
                ])
            overall = json.loads(report_json.read_text(encoding="utf-8"))["overall"]
            self.assertNotIn(overall, ("pass", "fail"))
            # Every "did it pass?" consumer keeps working unchanged.
            self.assertFalse(overall.upper() == "PASS")


if __name__ == "__main__":
    unittest.main()


class TestRhiUnavailableIsAMachineFault(unittest.TestCase):
    """Predicate (4b): the GPU refused the editor a resource.

    The broad version of this predicate — "L2 skipped while its dependencies
    passed" — is DELIBERATELY not implemented, because an agent whose code
    compiles and then crashes PIE lands on the identical shape (L1 pass,
    tests_run 0, status skipped) and excusing that would reward crashing over
    failing an assertion.

    An RHI allocation refusal is the one case that cannot be manufactured by
    submission content: agent C++ runs in gameplay and does not allocate render
    targets. So this carve-out is keyed on that structural signal alone, and the
    tests below exist mostly to pin what it must NOT rescue.
    """

    def _reasons(self, **l2kw):
        l2 = _lr("skipped", tests_run=0, exit_code=3, **l2kw)
        return harness_error_reasons(
            {"L1": _lr("pass", exit_code=0), "L2": l2}, ("L1", "L2"))

    def test_gpu_refusal_with_no_result_is_a_harness_error(self):
        # The measured 2026-08-10 rep: L1 passed both targets, the model shipped
        # 4 files, the test STARTED, then CreateCommittedResource failed.
        rs = self._reasons(rhi_unavailable=True)
        self.assertTrue(any("GPU refused" in r for r in rs), rs)

    def test_a_crashed_editor_WITHOUT_the_gpu_signal_stays_GRADED(self):
        # THE load-bearing test. Same shape, no RHI signal — this is the agent
        # crashing PIE, and it must keep counting against the model.
        self.assertEqual(self._reasons(rhi_unavailable=False), [])
        self.assertEqual(self._reasons(), [])

    def test_a_governed_timeout_stays_GRADED_even_with_the_gpu_signal(self):
        # 124 is the governed timeout; a pathological submission can hang the
        # editor, so it must not become an exit from the denominator.
        l2 = _lr("skipped", tests_run=0, exit_code=124, rhi_unavailable=True)
        rs = harness_error_reasons(
            {"L1": _lr("pass", exit_code=0), "L2": l2}, ("L1", "L2"))
        self.assertEqual([r for r in rs if "GPU refused" in r], [])

    def test_a_gpu_hiccup_that_STILL_produced_results_stays_GRADED(self):
        # A complete result set is a real verdict regardless of what the log
        # says about the GPU.
        l2 = _lr("fail", tests_run=1, tests_passed=0, exit_code=3,
                 rhi_unavailable=True)
        rs = harness_error_reasons(
            {"L1": _lr("pass", exit_code=0), "L2": l2}, ("L1", "L2"))
        self.assertEqual([r for r in rs if "GPU refused" in r], [])


class TestRhiDetector(unittest.TestCase):

    def test_detects_the_markers_a_refused_allocation_prints(self):
        from layers.l2_pie import _rhi_unavailable
        for marker in ("CreateCommittedResource", "OutOfVideoMemory",
                       "DXGI_ERROR_DEVICE_REMOVED"):
            with self.subTest(marker=marker):
                self.assertTrue(_rhi_unavailable(f"LogD3D12RHI: Error: {marker} failed"))

    def test_a_healthy_log_is_not_flagged(self):
        from layers.l2_pie import _rhi_unavailable
        self.assertFalse(_rhi_unavailable(
            "LogAutomationController: Test Completed. Result={Success}"))


class TestQueuedNeverStartedIsAMachineFault(unittest.TestCase):
    """Predicate (4c): the editor exited before starting a test it had QUEUED.

    Same doctrine as (4b) and held to the same bar — it must name a condition
    the submission cannot manufacture. The queue line proves our filter
    matched; everything between it and `Test Started` is harness-side, and no
    submission code has executed yet. The agent-reachable neighbour is
    started-THEN-died, which stays graded.
    """

    def _reasons(self, **l2kw):
        l2 = _lr("skipped", tests_run=0, exit_code=1, **l2kw)
        return harness_error_reasons(
            {"L1": _lr("pass", exit_code=0), "L2": l2}, ("L1", "L2"))

    def test_queued_but_never_started_is_a_harness_error(self):
        # Measured 2026-08-11 (…-20260811-010729): L1 passed both targets, the
        # model shipped 4 files over 43 tool calls, and L2 queued the test then
        # quit 2ms later while the worker was still being discovered.
        rs = self._reasons(queued_never_started=True)
        self.assertTrue(any("QUEUED" in r for r in rs), rs)

    def test_a_crashed_editor_WITHOUT_the_signal_stays_GRADED(self):
        """THE load-bearing test, same as its (4b) twin: an agent that crashes
        PIE lands on the identical shape and must keep counting."""
        self.assertEqual(self._reasons(queued_never_started=False), [])
        self.assertEqual(self._reasons(), [])

    def test_a_governed_timeout_stays_GRADED_even_with_the_signal(self):
        l2 = _lr("skipped", tests_run=0, exit_code=124, queued_never_started=True)
        rs = harness_error_reasons(
            {"L1": _lr("pass", exit_code=0), "L2": l2}, ("L1", "L2"))
        self.assertEqual([r for r in rs if "QUEUED" in r], [])

    def test_a_run_that_STILL_produced_results_stays_GRADED(self):
        l2 = _lr("fail", tests_run=1, tests_passed=0, exit_code=1,
                 queued_never_started=True)
        rs = harness_error_reasons(
            {"L1": _lr("pass", exit_code=0), "L2": l2}, ("L1", "L2"))
        self.assertEqual([r for r in rs if "QUEUED" in r], [])


class TestQueuedNeverStartedDetector(unittest.TestCase):
    """Pinned against the REAL logs of the run that exposed this, and against
    two PASSing reps of the same task — the whole point is that it separates
    them."""

    FAILING = (
        "[2026.08.11-01.23.06:101][  0]Automation: RunTests="
        "'Project.Functional Tests.Maps.L_GlideStamina.GlideStaminaFunctionalTest' Queued.\n"
        "[2026.08.11-01.23.06:103][  1]Automation: Quit Command Queued.\n"
        "[2026.08.11-01.23.06:872][302]LogAutomationWorker: Received FindWorkersMessage\n"
    )
    HEALTHY = FAILING + (
        "[2026.08.11-01.23.10:000][  5]LogFunctionalTest: Display: Test Started\n"
        "[2026.08.11-01.23.40:000][900]Test Completed. Result=Passed\n"
    )

    def test_queued_then_quit_before_starting_is_detected(self):
        from layers.l2_pie import _queued_never_started
        self.assertTrue(_queued_never_started(self.FAILING))

    def test_a_test_that_actually_started_is_NOT_flagged(self):
        from layers.l2_pie import _queued_never_started
        self.assertFalse(_queued_never_started(self.HEALTHY))

    def test_a_log_that_never_queued_at_all_is_NOT_flagged(self):
        """A different fault — filter miss, or the editor dying during startup
        (the GPU retry of the measured run never reached the queue line). It
        must keep the existing 'check your filter' note rather than borrow
        this one."""
        from layers.l2_pie import _queued_never_started
        self.assertFalse(_queued_never_started(
            "LogModuleManager: InternalLoadLibrary: 'AutomationController'\n"))
        self.assertFalse(_queued_never_started(""))

    def test_queued_zero_match_is_filter_error_not_machine_fault(self):
        """The engine prints Queued before resolving a RunTests filter.

        A zero-match filter must not borrow the measured controller-race
        exemption and leave the graded denominator.
        """
        from layers.l2_pie import _queued_never_started
        zero_match = self.FAILING + (
            "LogAutomationCommandLine: Error: No automation tests matched "
            "'Project.Functional Tests.Maps.L_Wrong.MissingTest'\n"
        )
        self.assertFalse(_queued_never_started(zero_match))


class TestHarnessPreconditionRouting(unittest.TestCase):
    """(4d) A fixture that finished through ``EFunctionalTestResult::Error``.

    That enum means the HARNESS could not set the test up. The soundness of
    routing on it rests on the 2026-08-14 corpus audit
    (the ::Error tag audit): every ``::Error`` whose guard read
    agent-writable state was retagged ``::Failed`` — 19 sites over 12 tasks —
    so a submission can no longer manufacture one and exit the denominator.
    """

    def _reasons(self, **l2kw):
        l2 = _lr("skipped", tests_run=0, exit_code=1, **l2kw)
        return harness_error_reasons(
            {"L1": _lr("pass", exit_code=0), "L2": l2}, ("L1", "L2"))

    def test_an_error_finish_is_a_harness_error(self):
        rs = self._reasons(harness_precondition=True)
        self.assertTrue(any("EFunctionalTestResult::Error" in r for r in rs), rs)

    def test_without_the_signal_the_run_stays_GRADED(self):
        """The load-bearing negative, as with (4b)/(4c): the same shape without
        the structural signal is an ordinary model failure and must keep
        counting."""
        self.assertEqual(self._reasons(harness_precondition=False), [])
        self.assertEqual(self._reasons(), [])

    def test_a_governed_timeout_stays_GRADED_even_with_the_signal(self):
        l2 = _lr("skipped", tests_run=0, exit_code=124, harness_precondition=True)
        rs = harness_error_reasons(
            {"L1": _lr("pass", exit_code=0), "L2": l2}, ("L1", "L2"))
        self.assertEqual([r for r in rs if "EFunctionalTestResult::Error" in r], [])

    def test_a_run_that_STILL_produced_results_stays_GRADED(self):
        """If a real graded outcome accompanied the Error, ambiguity resolves
        toward GRADED and we leave the run alone."""
        l2 = _lr("fail", tests_run=1, tests_passed=0, exit_code=1,
                 harness_precondition=True)
        rs = harness_error_reasons(
            {"L1": _lr("pass", exit_code=0), "L2": l2}, ("L1", "L2"))
        self.assertEqual([r for r in rs if "EFunctionalTestResult::Error" in r], [])

    def test_a_layer_the_registry_does_not_gate_on_is_ignored(self):
        """Same guard as its siblings: the loop skips any key not in the REGISTRY's
        gating set (``_gating_layer_requires``), which is independent of what the
        caller requested — so a non-gating layer carrying the signal cannot void a
        run. Verified that (4b) and (4c) behave identically here."""
        bogus = _lr("skipped", tests_run=0, exit_code=1, harness_precondition=True)
        rs = harness_error_reasons(
            {"L1": _lr("pass", exit_code=0), "ZZ-NOT-A-GATE": bogus}, ("L1",))
        self.assertEqual([r for r in rs if "EFunctionalTestResult::Error" in r], [])


class TestHarnessPreconditionDetector(unittest.TestCase):
    """The detector must key on the ENUM token UE prints, not on prose.

    Precision matters more than recall in this one direction: a false positive
    removes a run from the graded denominator, which favours the submission.
    """

    def test_an_error_finish_is_detected(self):
        from layers.l2_pie import _harness_precondition
        self.assertTrue(_harness_precondition(
            "LogFunctionalTest: Display: FinishTest TestResult=Error. "
            "HARNESS-PRECONDITION: PrepareTest: no UWorld available"))

    def test_the_other_three_enum_values_are_not(self):
        from layers.l2_pie import _harness_precondition
        for value in ("Passed", "Failed", "Skipped"):
            with self.subTest(value=value):
                self.assertFalse(_harness_precondition(
                    f"LogFunctionalTest: Display: FinishTest TestResult={value}."))

    def test_prose_mentioning_the_token_is_not_enough(self):
        """The `FinishTest ` anchor is what stops agent output from tripping it."""
        from layers.l2_pie import _harness_precondition
        self.assertFalse(_harness_precondition(
            "LogTemp: Warning: my submission printed TestResult=Error on purpose"))

    def test_an_unrelated_rhi_error_line_is_not_enough(self):
        from layers.l2_pie import _harness_precondition
        self.assertFalse(_harness_precondition(
            "LogD3D12RHI: Error: CreateCommittedResource(...) failed"))

    def test_the_word_boundary_rejects_a_longer_token(self):
        from layers.l2_pie import _harness_precondition
        self.assertFalse(_harness_precondition("FinishTest TestResult=ErrorSomething"))

    def test_the_engine_format_requires_the_trailing_period(self):
        """AFunctionalTest::FinishTest formats `"FinishTest TestResult=%s. %s"`
        (FunctionalTest.cpp:471), so the period after the enum is guaranteed.
        Requiring it is a tightening derived from engine source, and it rejects a
        near-miss a looser pattern would accept."""
        from layers.l2_pie import _harness_precondition
        self.assertTrue(_harness_precondition("FinishTest TestResult=Error."))
        self.assertFalse(_harness_precondition("FinishTest TestResult=Error"))
        self.assertFalse(_harness_precondition("FinishTest TestResult=Error-ish"))

    def test_a_message_after_the_period_still_matches(self):
        """The engine appends the fixture's message; an empty one is also valid."""
        from layers.l2_pie import _harness_precondition
        self.assertTrue(_harness_precondition(
            "FinishTest TestResult=Error. HARNESS-PRECONDITION: no UWorld available"))
        self.assertTrue(_harness_precondition("FinishTest TestResult=Error. "))

    def test_the_signal_is_documented_as_spoofable_not_as_a_trust_boundary(self):
        """A submission CAN emit a look-alike line — agent C++ shares this process
        and this log. This test does not assert the hole is closed (it is not); it
        pins the two things that BOUND it, so a future edit cannot quietly remove
        them and leave the overclaim behind.

        1. The consuming predicate requires tests_run == 0, so a spoofing
           submission must also produce no graded result — it has to break its own
           run to use the exploit.
        2. The docstring must not claim the signal is unspoofable.
        """
        from layers import l2_pie
        doc = l2_pie._harness_precondition.__doc__ or ""
        self.assertIn("not a trust boundary", doc)
        self.assertNotIn("cannot be spoofed", doc)
        # A spoofed line alongside a real graded result must NOT void the run.
        l2 = _lr("fail", tests_run=1, tests_passed=0, exit_code=1,
                 harness_precondition=True)
        rs = harness_error_reasons(
            {"L1": _lr("pass", exit_code=0), "L2": l2}, ("L1", "L2"))
        self.assertEqual([r for r in rs if "EFunctionalTestResult::Error" in r], [])

    def test_the_match_is_case_sensitive(self):
        """The engine emission is fixed-case: LexToString returns literally
        FString("Error") (FunctionalTest.cpp:118-119) into a literal format
        string, and log_text is read raw. IGNORECASE bought nothing and cost
        precision on a predicate whose job is to be precise, since a false
        positive removes a run from the graded denominator."""
        from layers.l2_pie import _harness_precondition
        self.assertTrue(_harness_precondition("FinishTest TestResult=Error."))
        for spoofish in ("FinishTest TestResult=error.",
                         "FinishTest TestResult=ERROR.",
                         "finishtest TestResult=Error."):
            with self.subTest(text=spoofish):
                self.assertFalse(_harness_precondition(spoofish))

"""Concrete verification-layer adapters + the run_layers loop.

Each adapter wraps an EXISTING runner (run_l1 / run_l2 / run_l2_introspect /
_maybe_run_r2). The per-layer logic is RELOCATED here verbatim from
run_task.main() — not rewritten — so behavior is preserved exactly; the 85-test
verify-single suite is the guardrail.

run_layers() iterates REGISTRY in order: applies() -> dependency short-circuit
-> run(). Gating layers land in ``layers_out`` (and drive ``overall``); advisory
layers populate ``ctx.advisory_out`` instead (R2 -> report.r2_advisory).

Helpers that live in run_task (derive_test_filter, _DT_LEGS_BY_TASK,
_maybe_run_r2) are imported LAZILY inside the adapters to avoid an import cycle
(run_task imports run_layers lazily inside main()).
"""
from __future__ import annotations

import shutil
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_VERIFY = Path(__file__).resolve().parent.parent
if str(_VERIFY) not in sys.path:
    sys.path.insert(0, str(_VERIFY))

# "Which surface does this task's answer have to be written in?" has exactly ONE
# implementation, in tools/runlib/run_identity.py, and the id's suffix wins over
# the basket there (the 2026-08-20 owner decision: moving a spec between sets must
# not relabel a surface). Bridged onto sys.path by DIRECTORY -- the same pattern
# dashboard/collect.py uses -- rather than copied, so a rename
# over there breaks this loudly instead of leaving two answers to drift apart.
_RUNLIB = _VERIFY.parent / "runlib"
if str(_RUNLIB) not in sys.path:
    sys.path.insert(0, str(_RUNLIB))

from report import LayerReport  # noqa: E402
from layers.base import Layer, LayerContext  # noqa: E402
from run_identity import surface_of  # noqa: E402


def task_l2_rhi_args(task) -> Optional[List[str]]:
    """Return the narrowly validated runtime RHI switches for a task."""
    return ["-d3d11"] if getattr(task, "rhi", "null") == "d3d11" else None


def collect_screenshots(
    workdir_substrate: Path, out_dir: Path, label: str = ""
) -> List[str]:
    """Sweep fixture screenshots into the run's artifact dir.

    Globs ``<workdir_substrate>/Saved/CraftBench/*.png`` (the substrate-side
    ``-CraftBenchCapture`` drop point), copies each into ``<out_dir>/artifacts/``
    — prefixing the filename with ``label`` when given (e.g. ``"fps20_"`` for a
    dt leg) — and returns the run-dir-relative paths (``"artifacts/<name>"``,
    POSIX separators) in sorted order. Returns ``[]`` (and creates nothing)
    when no screenshots exist, so the default no-capture path is untouched.
    """
    shot_dir = workdir_substrate / "Saved" / "CraftBench"
    if not shot_dir.exists():
        return []
    shots = sorted(shot_dir.glob("*.png"))
    if not shots:
        return []
    artifacts_dir = out_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    rel_paths: List[str] = []
    for src in shots:
        name = f"{label}{src.name}" if label else src.name
        shutil.copy2(src, artifacts_dir / name)
        rel_paths.append(f"artifacts/{name}")
    return sorted(rel_paths)


class ArtifactLayer:
    """Deterministic 'deliverable present' floor: passes iff the task's declared
    artifact exists and is non-empty in the applied workspace. Gives advisory-
    heavy tasks (e.g. summarize-project, whose substance is judged by R2) a real,
    non-vacuous gate. Declared via the unified block: ``- ART (artifact: <path>)``.
    Opt-in — does not run unless a task declares an artifact_path."""

    key, gating, order, requires = "ART", True, 8, ()

    def applies(self, ctx: LayerContext) -> bool:
        return bool(getattr(ctx.task, "artifact_path", None))

    def run(self, ctx: LayerContext) -> LayerReport:
        rel = ctx.task.artifact_path
        target = ctx.workdir_substrate / rel
        if target.is_file() and target.stat().st_size > 0:
            return LayerReport(status="pass", tests_run=1, tests_passed=1,
                               notes=[f"artifact {rel}: present, {target.stat().st_size} bytes"])
        return LayerReport(status="fail", tests_run=1, tests_passed=0,
                           notes=[f"artifact {rel}: MISSING or empty"])


class L1Layer:
    key, gating, order, requires = "L1", True, 10, ()

    def applies(self, ctx: LayerContext) -> bool:
        return "L1" in ctx.requested_layers

    def run(self, ctx: LayerContext) -> LayerReport:
        from layers.l1_build import run_l1
        a = ctx.args
        l1 = run_l1(
            ue_root=a.ue_root,
            project_path=ctx.project_path,
            game_module=ctx.manifest.game_module,
            log_path=ctx.out_dir / "l1_build.log",
            agent_writable_prefixes=ctx.agent_prefixes,
        )
        status = l1.status
        notes = list(l1.notes)
        if a.strict_warnings and l1.warning_count_agent_files > 0 and status == "pass":
            status = "fail"
            notes.append(
                f"--strict-warnings: {l1.warning_count_agent_files} "
                "warning(s) in agent-writable files"
            )
        return LayerReport(
            status=status,
            log=str(l1.log_path),
            exit_code=l1.exit_code,
            duration_seconds=round(l1.duration_seconds, 2),
            warnings_in_agent_files=l1.warning_count_agent_files,
            build_tool_never_ran=l1.build_tool_never_ran,
            notes=notes,
        )


class L2Layer:
    key, gating, order, requires = "L2", True, 20, ("L1",)

    def applies(self, ctx: LayerContext) -> bool:
        return "L2" in ctx.requested_layers

    def run(self, ctx: LayerContext) -> LayerReport:
        from layers.l2_pie import run_l2
        from map_locator import locate_map
        from run_task import derive_test_filter, _DT_LEGS_BY_TASK
        a, task, out_dir = ctx.args, ctx.task, ctx.out_dir

        # 5a) Every test .umap must already exist as a committed binary in the
        # workdir substrate copy (multi-fixture tasks list each leg's map in
        # spec order; legacy single-fixture falls back to [task.map_name]).
        # Scaffolders are retired (2026-07): a missing binary is an explicit
        # FAIL — the runner never re-bakes a map.
        map_notes: List[str] = []
        if task.fixtures:
            maps_needed = list(dict.fromkeys(f.map_name for f in task.fixtures))
        elif task.map_name:
            maps_needed = [task.map_name]
        else:
            maps_needed = []

        # Discover where each map actually lives (flat Content/Maps/ or one
        # folder deep). A miss is a hard FAIL, not a scaffold fallback.
        located = {}
        for map_name in maps_needed:
            loc = locate_map(ctx.workdir_substrate, map_name)
            located[map_name] = loc
            if loc is None:
                return LayerReport(
                    status="fail",
                    notes=map_notes
                    + [
                        f"map binary missing: {map_name} — maps ship as "
                        "committed binaries; scaffolders retired 2026-07"
                    ],
                )
            map_notes.append(f"map {map_name}: {loc.package_path}")

        if task.task_id == (
                "t3-the-run-resumes-at-the-latest-marker-without-paying-twice"):
            from layers.l2_run_resume import run_protocol_layer
            return run_protocol_layer(ctx, map_notes)

        if task.task_id == (
                "t3-the-old-world-cannot-complete-into-the-new-one"):
            from layers.l2_epoch_travel import run_epoch_travel_layer
            return run_epoch_travel_layer(ctx, map_notes)

        if task.task_id == "t3-every-player-sees-the-same-door-state":
            from layers.l2_replicated_door import run_replicated_door_layer
            return run_replicated_door_layer(ctx, map_notes)

        if task.task_id == "t3-dash-responds-now-and-converges-later":
            from layers.l2_predicted_dash import run_predicted_dash_layer
            return run_predicted_dash_layer(ctx, map_notes)

        # Leg-count guard: PASS additionally requires that the number of tests
        # the automation session actually ran equals the number of declared
        # fixtures (legacy single-fixture derivation expects exactly 1) —
        # mirrors the dt-leg count check below so a silently dropped leg can
        # never grade as PASS. An explicit --test-filter is an operator debug
        # override that may legitimately narrow (or widen) the leg set, so the
        # guard is disabled — certified runs never pass --test-filter.
        if a.test_filter:
            expected_test_count = None
            map_notes.append("explicit --test-filter: leg-count guard disabled")
        else:
            expected_test_count = len(task.fixtures) if task.fixtures else 1

        def prefix_for_map(name: str) -> str:
            if name not in located:
                located[name] = locate_map(ctx.workdir_substrate, name)
            loc = located[name]
            return loc.automation_prefix if loc else ""

        map_package_path = None
        if task.map_name:
            if task.map_name not in located:
                located[task.map_name] = locate_map(
                    ctx.workdir_substrate, task.map_name
                )
            loc = located[task.map_name]
            if loc is not None:
                map_package_path = loc.package_path

        test_filter = derive_test_filter(
            task, explicit=a.test_filter, prefix_for_map=prefix_for_map
        )
        # Opt-in screenshot capture (--capture): forward the substrate hook to
        # every PIE leg and sweep Saved/CraftBench/*.png into out_dir/artifacts/.
        # Default-off => byte-identical behavior to before.
        capture = getattr(a, "capture", False)
        # DD-9: prefer the per-task spec legs (TaskSpec.fps_legs); fall
        # back to the legacy _DT_LEGS_BY_TASK dict for un-migrated tasks.
        dt_legs = task.fps_legs or _DT_LEGS_BY_TASK.get(task.task_id, ())
        if dt_legs:
            # Framerate-independence: same fixture at each fixed dt in its own
            # PIE process; ALL legs must pass (fail-fast).
            leg_results: List[Tuple[int, object]] = []
            for fps in dt_legs:
                leg = run_l2(
                    ue_root=a.ue_root,
                    project_path=ctx.project_path,
                    test_filter=test_filter,
                    log_path=out_dir / f"l2_fps{fps}.log",
                    report_dir=out_dir / f"l2_report_fps{fps}",
                    map_name=task.map_name,
                    map_package_path=map_package_path,
                    use_nullrhi=a.use_nullrhi,
                    extra_args=task_l2_rhi_args(task),
                    fps=fps,
                    capture=capture,
                    expected_test_count=expected_test_count,
                )
                leg_results.append((fps, leg))
                if capture:
                    shots = collect_screenshots(
                        ctx.workdir_substrate, out_dir, label=f"fps{fps}_"
                    )
                    if shots:
                        ctx.advisory_out.setdefault("visual_artifacts", []).extend(shots)
                if leg.status != "pass":
                    break  # fail-fast; remaining legs are moot
            l2 = leg_results[-1][1]
            if len(leg_results) == len(dt_legs) and all(r.status == "pass" for _, r in leg_results):
                combined_status = "pass"
            elif any(r.status == "fail" for _, r in leg_results):
                combined_status = "fail"
            else:
                combined_status = "skipped"
            return LayerReport(
                status=combined_status,
                log=str(l2.log_path),
                exit_code=l2.exit_code,
                duration_seconds=round(sum(r.duration_seconds for _, r in leg_results), 2),
                tests_run=sum(r.tests_run for _, r in leg_results),
                tests_passed=sum(r.tests_passed for _, r in leg_results),
                notes=map_notes
                + [
                    f"dt leg fps={fps}: {r.status} ({r.tests_passed}/{r.tests_run})"
                    for fps, r in leg_results
                ]
                + [n for _, r in leg_results for n in r.notes
                   if ("leg dropped" in str(n)) or ("fixture over-count" in str(n))]
                + [f"filter: {test_filter}", f"dt_legs: {dt_legs}"],
            )

        report_dir = out_dir / "l2_report"
        l2 = run_l2(
            ue_root=a.ue_root,
            project_path=ctx.project_path,
            test_filter=test_filter,
            log_path=out_dir / "l2_pie.log",
            report_dir=report_dir,
            map_name=task.map_name,
            map_package_path=map_package_path,
            use_nullrhi=a.use_nullrhi,
            extra_args=task_l2_rhi_args(task),
            capture=capture,
            expected_test_count=expected_test_count,
        )
        # Fallback: if every test was skipped (commonly -nullrhi rejecting a test
        # that needs a viewport), retry once without -nullrhi. Skipped under
        # --capture: use_nullrhi is already False there, so the retry is moot.
        #
        # READ THE CONDITION CAREFULLY — it is broader than the sentence above.
        # `tests_skipped == 0` means NOTHING was actually skipped, so this fires
        # on ANY zero-result L2, not only on "a test needs a viewport": a crashed
        # editor, a stalled automation queue and a genuine viewport rejection all
        # land here and all get re-run on the GPU.
        #
        # THE RETRY IS NOT FREE. It drops `-nullrhi`, so a GRADED run that should
        # never touch a GPU suddenly does — and on 2026-08-10 that is exactly how
        # a rep died: the retry's editor hit `LogD3D12RHI: Error:
        # CreateCommittedResource(...) failed` (video-memory exhaustion) mid-test,
        # produced zero tests, and the empty result graded as a MODEL FAIL.
        # `pressure.py` guards COMMIT (RAM) and has no GPU band at all, so
        # nothing sees this coming.
        if (
            a.use_nullrhi
            and not capture
            and l2.status == "skipped"
            and l2.tests_skipped == 0
        ):
            # Keep the FIRST attempt's log. It used to be overwritten because both
            # calls wrote `l2_pie.log`, which made the primary failure — why did
            # -nullrhi produce nothing? — permanently undiagnosable: by the time
            # anyone looked, only the retry's log existed. That is the question
            # that actually matters, since the retry is a workaround, not a fix.
            nullrhi_log = out_dir / "l2_pie_nullrhi.log"
            try:
                if l2.log_path and Path(l2.log_path).exists():
                    shutil.copyfile(l2.log_path, nullrhi_log)
            except OSError:
                pass  # diagnostics are best-effort; never fail a grade over them
            l2.notes.append("no tests discovered under -nullrhi; retrying with full RHI")
            # Carry the FIRST attempt's structural machine-fault signals across
            # the retry, because `l2` is about to be REPLACED wholesale and they
            # would otherwise be discarded with it.
            #
            # Measured 2026-08-11 (…-20260811-010729) and it made the guard dead
            # code for its own founding case: the -nullrhi attempt queued the
            # test and quit before starting it (queued_never_started True), the
            # GPU retry then died even earlier — before reaching the queue line
            # at all — so the retry's own flag was False and the run graded FAIL
            # against the model anyway. The question predicate (4c) answers is
            # "did the harness's exit race the controller on THIS grade", and
            # either attempt doing so is a yes.
            first_queued_never_started = l2.queued_never_started
            first_rhi_unavailable = l2.rhi_unavailable
            first_harness_precondition = l2.harness_precondition
            first_editor_never_started = l2.editor_never_started
            l2 = run_l2(
                ue_root=a.ue_root,
                project_path=ctx.project_path,
                test_filter=test_filter,
                log_path=out_dir / "l2_pie.log",
                report_dir=report_dir,
                map_name=task.map_name,
                map_package_path=map_package_path,
                use_nullrhi=False,
                extra_args=task_l2_rhi_args(task),
                capture=capture,
                expected_test_count=expected_test_count,
            )
            l2.notes.insert(0, "fell back to full RHI on first retry")
            l2.notes.insert(1, f"the -nullrhi attempt's log is preserved at {nullrhi_log.name} "
                               "— read THAT to learn why the headless run produced nothing; "
                               "l2_pie.log below is the GPU retry")
            l2.notes.insert(2, "NB this verdict came from a NON-HEADLESS retry: `-nullrhi` was "
                               "dropped, so it ran against a real GPU and is not the "
                               "certified headless environment")
            # OR, never overwrite: the retry finding no fault does not unmake one
            # the first attempt recorded.
            if first_queued_never_started and not l2.queued_never_started:
                l2.queued_never_started = True
                l2.notes.append("the -nullrhi attempt queued the test and exited before "
                                "starting it; that signal is carried onto this verdict")
            if first_rhi_unavailable and not l2.rhi_unavailable:
                l2.rhi_unavailable = True
                l2.notes.append("the -nullrhi attempt showed a GPU resource refusal; that "
                                "signal is carried onto this verdict")
            if first_harness_precondition and not l2.harness_precondition:
                l2.harness_precondition = True
                l2.notes.append("the -nullrhi attempt finished a fixture through "
                                "EFunctionalTestResult::Error (a harness precondition); "
                                "that signal is carried onto this verdict")
            # Same OR-never-overwrite doctrine. The measured 2026-08-17 instance
            # had BOTH legs empty, so carrying it forward was not what rescued
            # that run — but the asymmetric case is the one to protect: a
            # -nullrhi leg that produced nothing followed by a GPU retry that
            # DOES write a log would otherwise let the retry's non-empty log
            # unmake the first leg's finding, and the run would grade against
            # the model on the strength of the attempt we already know is not
            # the certified headless environment.
            if first_editor_never_started and not l2.editor_never_started:
                l2.editor_never_started = True
                l2.notes.append("the -nullrhi attempt produced a zero-byte log and "
                                "exited non-zero — the editor never started; that "
                                "signal is carried onto this verdict")
        if capture:
            shots = collect_screenshots(ctx.workdir_substrate, out_dir)
            if shots:
                ctx.advisory_out.setdefault("visual_artifacts", []).extend(shots)

        return LayerReport(
            status=l2.status,
            log=str(l2.log_path),
            exit_code=l2.exit_code,
            duration_seconds=round(l2.duration_seconds, 2),
            rhi_unavailable=l2.rhi_unavailable,
            queued_never_started=l2.queued_never_started,
            harness_precondition=l2.harness_precondition,
            editor_never_started=l2.editor_never_started,
            tests_run=l2.tests_run,
            tests_passed=l2.tests_passed,
            notes=map_notes
            + list(l2.notes)
            + [f"filter: {test_filter}", f"result_source: {l2.result_source}"],
        )


# L2I exit codes that must NOT be retried. 124 is the governed timeout, which
# run_task.LAYER_ERROR_GRADED_EXITS keeps GRADED precisely because a pathological
# submission can hang the editor its C++ is linked into; retrying would let that
# submission cost two full timeouts instead of one.
_L2I_NO_RETRY_EXITS = frozenset({124})


class L2IntrospectLayer:
    key, gating, order, requires = "L2I", True, 30, ("L1",)

    def applies(self, ctx: LayerContext) -> bool:
        # Section-triggered, not L-token-triggered (a "## Verifier introspection"
        # section yields a non-empty introspect_scripts tuple).
        return bool(ctx.task.introspect_scripts)

    def run(self, ctx: LayerContext) -> LayerReport:
        from layers.l2_introspect import run_l2_introspect
        a, task, out_dir = ctx.args, ctx.task, ctx.out_dir
        introspect_root = _VERIFY / "introspect"
        li_checks: List[str] = []
        li_total = li_passed = 0
        li_statuses: List[str] = []
        li_last_log = None
        # Exit code of the FIRST script whose verdict channel died, propagated
        # onto the LayerReport so run_task.harness_error_reasons can apply the
        # governed-timeout (124) carve-out. Populated on the error path only, so
        # a pass/fail L2I report.json stays byte-identical to before.
        li_error_exit: Optional[int] = None
        for script_name in task.introspect_scripts:
            script_path = introspect_root / script_name
            if not script_path.exists():
                li_statuses.append("error")
                # 127 = "could not execute the verifier at all", the same code
                # l1_build/l2_introspect synthesize for a missing binary. No
                # editor was launched, so no submission content is implicated.
                if li_error_exit is None:
                    li_error_exit = 127
                li_checks.append(f"{script_name}: MISSING verifier script at {script_path}")
                continue
            log_li = out_dir / f"l2_introspect_{Path(script_name).stem}.log"
            _kwargs = dict(
                ue_root=a.ue_root,
                project_path=ctx.project_path,
                introspect_script=script_path,
                use_nullrhi=a.use_nullrhi,
                submitted_assets=list(getattr(ctx, "submitted_files", ()) or ()),
                # A -bp task's answer must be a Blueprint, so submitted C++ is a
                # graded failure rather than a lesser answer -- see
                # l2_introspect.run_l2_introspect for why it is graded and not
                # refused. Derived from the id suffix, never from the basket dir.
                forbid_source_submissions=(surface_of(task.task_id) == "bp"),
                allow_redirectors=list(
                    getattr(task, "allow_redirectors", ()) or ()
                ),
            )
            ir = run_l2_introspect(log_path=log_li, **_kwargs)
            # ONE bounded retry when the verdict channel produced nothing.
            #
            # Observed 2026-08-03 under a 3-way concurrent grade: the editor
            # completed engine init and then emitted no verdict block at all —
            # L2I error, exit 1, 0 checks -> the whole leg became HARNESS-ERROR
            # and was lost. The cause was never isolated (no OOM, no crash
            # trace), which is exactly why the repair is cause-agnostic.
            #
            # RETRYING IS MONOTONE, and that is the entire argument for it: a
            # second attempt can only turn "no verdict" into "a verdict". It
            # cannot manufacture a PASS (the grader either runs correctly or
            # produces nothing again) and it cannot manufacture a FAIL. Nor is
            # it gameable — the submission is graded either way, so the model
            # under test gains nothing by provoking a retry. Contrast routing
            # this to a new non-graded state, which would hand out a denominator
            # opt-out.
            #
            # EXCEPT on a governed timeout. Exit 124 is deliberately GRADED (a
            # pathological submission CAN hang the editor its C++ is linked
            # into), so retrying would merely let such a submission cost two
            # full timeouts instead of one. Ambiguity resolves toward doing the
            # work once and grading it.
            if ir.status == "error" and ir.exit_code not in _L2I_NO_RETRY_EXITS:
                # A distinct log so the FIRST failure survives for diagnosis —
                # a retry that silently overwrites its own evidence would hide
                # the systematic problem it is papering over.
                retry_log = out_dir / f"l2_introspect_{Path(script_name).stem}.retry.log"
                retry = run_l2_introspect(log_path=retry_log, **_kwargs)
                li_checks.append(
                    f"{script_name}: no verdict on attempt 1 "
                    f"(exit {ir.exit_code}); retried once -> {retry.status}. "
                    f"First attempt's log kept at {log_li.name}"
                )
                # Keep the retry either way: on success it is the verdict, and on
                # a second failure it is the fresher evidence.
                ir = retry
            li_statuses.append(ir.status)
            if ir.status == "error" and li_error_exit is None:
                li_error_exit = ir.exit_code
            li_total += ir.total
            li_passed += ir.passed_count
            li_last_log = str(ir.log_path)
            for c in ir.checks:
                li_checks.append(
                    f"{script_name}:{c.id}: {'PASS' if c.passed else 'FAIL'}"
                    + (f" — {c.detail}" if c.detail else "")
                )
            if ir.status != "pass":
                li_checks.extend(f"{script_name} note: {n}" for n in ir.notes)
        # Three-way collapse, NOT two. l2_introspect distinguishes a third
        # status — "error", its fail-safe for "no verdict block / malformed JSON
        # / no checks list" (INTROSPECT_CONTRACT.md) — and the registry adds a
        # fourth producer of it above (MISSING verifier script). Every one of
        # those is a VERIFIER-owned artifact being wrong, so folding them into
        # "fail" (what this line did until 2026-07-27) graded a harness fault as
        # a model failure. It is propagated verbatim instead; run_task's
        # harness_error_reasons predicate (5) routes it to exit 7 (HARNESS-ERROR,
        # non-graded), except for the governed timeout, which stays graded.
        #
        # "error" DOMINATES "fail": if any script's verdict channel died the
        # grade is incomplete, and a partial gate must not certify — the same
        # fail-safe direction l2_introspect itself takes.
        if any(s == "error" for s in li_statuses):
            li_status = "error"
        elif li_statuses and all(s == "pass" for s in li_statuses):
            li_status = "pass"
        else:
            li_status = "fail"
        return LayerReport(
            status=li_status,
            log=li_last_log,
            exit_code=li_error_exit,
            tests_run=li_total,
            tests_passed=li_passed,
            notes=li_checks,
        )


def _l3_test_filter(map_name: str, test_class: str, prefix: str = "") -> str:
    """UE automation filter for an L3 fixture (UE strips the leading 'A').

    ``prefix`` is the map's automation-prefix segment
    (map_locator.MapLocation.automation_prefix): "" for root maps (today's
    form, unchanged), "<folder>" for one-level-foldered maps
    (``Maps.<folder>.<Map>.<Class>``).
    """
    cls = test_class[1:] if test_class.startswith("A") else test_class
    seg = f"{prefix}.{map_name}" if prefix else map_name
    return f"Project.Functional Tests.Maps.{seg}.{cls}"


class L3RenderLayer:
    """Render-context structural verification + screenshot, via REAL-RHI PIE.

    For tasks whose pass condition involves a VISIBLE artifact (a widget renders,
    a particle spawns, a material reads on a mesh). Runs a PIE AFunctionalTest
    (run_l2) with use_nullrhi=False so the scene ACTUALLY renders — the engine
    ticks every frame, so the fixture can capture the PIE viewport with content
    (a one-shot editor-Python capture renders black: no frame advances). The
    fixture asserts structural predicates (the deterministic GATE) and captures a
    screenshot to <workdir>/Saved/CraftBench/*.png, which this layer hands to the
    R2 visual-advisory track. Pixel/SSIM stays OUT of the gate per FR-020d.

    Declared via the unified block: ``- L3 (fixtures: <map> :: <AScreenshotFixture>)``.
    The fixture is a verifier-only ACraftBenchFunctionalTest subclass in
    Source/CraftBenchTests/ (see RenderProbeFunctionalTest as the template).
    """

    key, gating, order, requires = "L3", True, 25, ("L1",)

    def applies(self, ctx: LayerContext) -> bool:
        return bool(getattr(ctx.task, "l3_fixtures", ()))

    def run(self, ctx: LayerContext) -> LayerReport:
        from layers.l2_pie import run_l2
        from map_locator import locate_map
        a, task, out_dir = ctx.args, ctx.task, ctx.out_dir
        statuses: List[str] = []
        notes: List[str] = []
        total = passed = 0
        last_log = None
        for fx in task.l3_fixtures:
            # Discover where the fixture map actually lives (flat or one
            # folder deep). Mirrors L2Layer: a miss is an explicit hard FAIL —
            # maps ship as committed binaries, scaffolders retired 2026-07.
            loc = locate_map(ctx.workdir_substrate, fx.map_name)
            if loc is None:
                return LayerReport(
                    status="fail",
                    notes=notes
                    + [
                        f"map binary missing: {fx.map_name} — maps ship as "
                        "committed binaries; scaffolders retired 2026-07"
                    ],
                )
            test_filter = _l3_test_filter(
                fx.map_name,
                fx.test_class,
                prefix=loc.automation_prefix,
            )
            res = run_l2(
                ue_root=a.ue_root,
                project_path=ctx.project_path,
                test_filter=test_filter,
                log_path=out_dir / f"l3_{fx.map_name}.log",
                report_dir=out_dir / f"l3_report_{fx.map_name}",
                map_name=fx.map_name,
                map_package_path=loc.package_path,
                use_nullrhi=False,   # REAL RHI — the PIE scene must actually render
                capture=getattr(a, "capture", False),
                # Each L3 leg runs exactly ONE declared fixture; the guard
                # forces an over-count (filter collision) to FAIL, not PASS.
                expected_test_count=1,
            )
            statuses.append(res.status)
            total += res.tests_run
            passed += res.tests_passed
            last_log = str(res.log_path)
            notes.append(f"{fx.map_name}::{fx.test_class}: {res.status} "
                         f"({res.tests_passed}/{res.tests_run})")
            notes.extend(str(n) for n in res.notes[:3])
        # Collect the screenshot artifacts the fixtures wrote (R2 visual track).
        # collect_screenshots copies them into out_dir/artifacts/ and returns
        # run-dir-relative "artifacts/<name>" paths. Written under BOTH advisory
        # keys: "visual_artifacts" (the unified sweep key run_task folds into
        # report.artifacts) and the pre-existing "L3_visual" (kept for
        # back-compat with existing consumers of the L3 advisory key).
        shots = collect_screenshots(ctx.workdir_substrate, out_dir)
        if shots:
            ctx.advisory_out.setdefault("visual_artifacts", []).extend(shots)
            ctx.advisory_out.setdefault("L3_visual", []).extend(shots)
            notes.extend(f"screenshot: {s}" for s in shots)
        else:
            notes.append("no screenshot captured")
        status = "pass" if statuses and all(s == "pass" for s in statuses) else "fail"
        return LayerReport(
            status=status, log=last_log, tests_run=total, tests_passed=passed, notes=notes,
        )


class R2Layer:
    """NON-GATING advisory judge. Its rich advisory block goes to
    ctx.advisory_out['R2'] (→ report.r2_advisory), never to layers_out, so it
    can't touch the certified overall."""

    key, gating, order, requires = "R2", False, 40, ()

    def applies(self, ctx: LayerContext) -> bool:
        return bool(getattr(ctx.args, "r2", False)) and "## R2 advisory rubric" in ctx.task.raw_text

    def run(self, ctx: LayerContext) -> LayerReport:
        from run_task import _maybe_run_r2
        advisory = _maybe_run_r2(ctx.args, ctx.task, ctx.substrate_src, ctx.out_dir)
        if advisory is not None:
            ctx.advisory_out["R2"] = advisory
        ok = bool(advisory) and advisory.get("status") != "error"
        return LayerReport(
            status="pass" if ok else "skipped",
            notes=["R2 advisory (non-gating)" if ok else "R2 advisory unavailable"],
        )


# Registry — append a Layer here to add a verification method. Order ascends.
REGISTRY: List[Layer] = [
    ArtifactLayer(), L1Layer(), L2Layer(), L3RenderLayer(), L2IntrospectLayer(), R2Layer(),
]


def run_layers(
    ctx: LayerContext,
    registry: List[Layer] = None,
) -> Tuple[Dict[str, LayerReport], Dict[str, dict]]:
    """Run every applicable layer in order; return (gating layers, advisory payloads).

    Dependency short-circuit: a layer whose ``requires`` includes a layer that
    ran but did not PASS is emitted as "skipped" (gating) / skipped silently
    (advisory) without running. ``overall`` is computed by the caller over the
    returned gating ``layers_out`` only. ``registry`` is injectable for tests.
    """
    if registry is None:
        registry = REGISTRY
    layers_out: Dict[str, LayerReport] = {}
    for layer in sorted(registry, key=lambda l: l.order):
        if not layer.applies(ctx):
            continue
        failed_dep = next(
            (k for k in layer.requires if k in layers_out and layers_out[k].status != "pass"),
            None,
        )
        if failed_dep is not None:
            if layer.gating:
                layers_out[layer.key] = LayerReport(
                    status="skipped",
                    notes=[f"short-circuited: {failed_dep} did not pass"],
                )
            continue
        ctx.prior = dict(layers_out)
        _t0 = time.monotonic()
        report = layer.run(ctx)
        _elapsed = time.monotonic() - _t0
        # Fill the duration for layers that do not measure themselves (L2I, L3,
        # R2 — all of which reported None, so L2I's cost was invisible in every
        # report ever written). L1/L2 DO self-measure, and their number is the
        # tighter one (the UBT / editor subprocess alone, excluding this loop's
        # adapter overhead), so theirs is left untouched rather than overwritten
        # — the two are not interchangeable and the more precise one wins.
        if report.duration_seconds is None:
            report.duration_seconds = round(_elapsed, 2)
        if layer.gating:
            layers_out[layer.key] = report
    return layers_out, dict(ctx.advisory_out)

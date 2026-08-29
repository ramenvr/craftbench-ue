#!/usr/bin/env python3
"""Verifier-noise stability harness — the (b)->0 gate.

CraftBench has exactly two variance sources and they must never be conflated
(the verdict-stability notes sections 1, 2b, 3):

  (a) AGENT stochasticity — same prompt -> different deliverable -> legitimately
      different verdict. This is the SIGNAL; report it as a pass-RATE over N.
  (b) VERIFIER flakiness — the SAME FIXED deliverable -> different verdict across
      runs. This is NOISE and must be ~0. It is the testable invariant.

This tool measures (b). It grades ONE FIXED reference-solution directory N times
(default N=5) by invoking ``run_task.py`` as a subprocess with a DISTINCT
``--report-json`` per run, then asserts across the N reports:

  (i)   all ``submission_sha`` are IDENTICAL — proves the deliverable was truly
        fixed. A constant reference dir is a pure byte-copy (``--harness
        filesystem``, no model call), so a differing sha means the *input itself*
        drifted (a setup bug), not a verifier flake.
  (ii)  all ``overall`` are IDENTICAL.
  (iii) all per-layer ``tests_passed`` / ``tests_run`` are IDENTICAL — catches a
        flip that nets out to the same ``overall``.

ACCEPTANCE: variance == 0 -> exit 0. ANY disagreement on a constant
``submission_sha`` is a **P0 VERIFIER BUG** — never an agent result -> nonzero
exit + a printed P0 banner. A non-constant ``submission_sha`` is a distinct
**deliverable-not-fixed** error (the experiment is invalid, not the verifier).

The tool REQUIRES a UE install to actually grade, so it is a budgeted/scheduled
CI job, NOT per-PR. See README.md.

The grading invocation is factored behind an injectable ``grade_once`` callable
so the acceptance logic is unit-testable with NO UE: tests feed canned report
dicts. ``main()`` wires the live subprocess binding.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

_HERE = Path(__file__).resolve().parent
REPO_ROOT = _HERE.parents[1]
_RUN_TASK = REPO_ROOT / "tools" / "verify-single" / "run_task.py"

# Exit codes (distinct so CI can attribute the failure class).
EXIT_STABLE = 0            # variance == 0 — the (b)->0 gate held
EXIT_VERIFIER_BUG = 1      # P0: same fixed deliverable, disagreeing verdict
EXIT_DELIVERABLE_DRIFT = 2  # the input itself was not fixed (setup invalid)
EXIT_USAGE = 3             # could not run N times (subprocess / parse failure)

# A grade_once callable: (run_index, report_json_path) -> parsed report dict.
GradeOnce = Callable[[int, Path], Dict[str, Any]]


# --------------------------------------------------------------------------- #
# Per-layer flip-rate model
# --------------------------------------------------------------------------- #
@dataclass
class LayerFlip:
    """Run-to-run disagreement for one layer, attributable to its noise class."""

    layer: str
    # Each tuple is the per-run observation in run order.
    statuses: List[str] = field(default_factory=list)            # L2I error-vs-pass
    exit_codes: List[Optional[int]] = field(default_factory=list)  # L1 exit-code flips
    test_counts: List[Tuple[Optional[int], Optional[int]]] = field(default_factory=list)  # L2 band flips

    def _flip_rate(self, observations: List[Any]) -> float:
        """Fraction of runs that disagree with the modal (most common) value.

        0.0 == every run agreed. Keyed on the dominant value so a single
        outlier among N reads as 1/N, not 0.5.
        """
        present = [o for o in observations if o is not None]
        if len(present) <= 1:
            return 0.0
        modal_value, modal_count = Counter(present).most_common(1)[0]
        disagreeing = len(present) - modal_count
        return disagreeing / len(present)

    @property
    def status_flip_rate(self) -> float:
        """L2I-style error-vs-pass flip rate."""
        return self._flip_rate(self.statuses)

    @property
    def exit_flip_rate(self) -> float:
        """L1-style exit-code flip rate."""
        return self._flip_rate(self.exit_codes)

    @property
    def count_flip_rate(self) -> float:
        """L2-style band/count flip rate (tests_passed/tests_run pair)."""
        return self._flip_rate(self.test_counts)

    @property
    def flipped(self) -> bool:
        return (
            self.status_flip_rate > 0.0
            or self.exit_flip_rate > 0.0
            or self.count_flip_rate > 0.0
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "layer": self.layer,
            "status_flip_rate": round(self.status_flip_rate, 4),
            "exit_flip_rate": round(self.exit_flip_rate, 4),
            "count_flip_rate": round(self.count_flip_rate, 4),
            "flipped": self.flipped,
            "statuses": list(self.statuses),
            "exit_codes": list(self.exit_codes),
            "test_counts": [list(tc) for tc in self.test_counts],
        }


@dataclass
class StabilityResult:
    """Outcome of an N-run verifier-noise check."""

    n: int
    submission_shas: List[str]
    overalls: List[str]
    layer_flips: Dict[str, LayerFlip]
    exit_code: int
    messages: List[str] = field(default_factory=list)

    @property
    def deliverable_fixed(self) -> bool:
        return len(set(self.submission_shas)) <= 1

    @property
    def overall_stable(self) -> bool:
        return len(set(self.overalls)) <= 1

    @property
    def layers_stable(self) -> bool:
        return not any(f.flipped for f in self.layer_flips.values())

    @property
    def stable(self) -> bool:
        return self.exit_code == EXIT_STABLE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "n": self.n,
            "exit_code": self.exit_code,
            "stable": self.stable,
            "deliverable_fixed": self.deliverable_fixed,
            "overall_stable": self.overall_stable,
            "layers_stable": self.layers_stable,
            "submission_shas": list(self.submission_shas),
            "overalls": list(self.overalls),
            "layer_flips": {k: v.to_dict() for k, v in self.layer_flips.items()},
            "messages": list(self.messages),
        }


# --------------------------------------------------------------------------- #
# Acceptance logic (pure — operates on already-collected report dicts)
# --------------------------------------------------------------------------- #
def _build_layer_flips(reports: List[Dict[str, Any]]) -> Dict[str, LayerFlip]:
    """Collect per-layer observations across the N reports.

    A layer ABSENT from a given report contributes ``None`` for that run, so
    "ran on run A but not run B" surfaces as a status flip rather than being
    silently dropped.
    """
    layer_names: List[str] = []
    seen = set()
    for rep in reports:
        for name in rep.get("layers", {}).keys():
            if name not in seen:
                seen.add(name)
                layer_names.append(name)

    flips: Dict[str, LayerFlip] = {name: LayerFlip(layer=name) for name in layer_names}
    for rep in reports:
        layers = rep.get("layers", {})
        for name in layer_names:
            body = layers.get(name)
            flip = flips[name]
            if body is None:
                flip.statuses.append(None)
                flip.exit_codes.append(None)
                flip.test_counts.append((None, None))
                continue
            flip.statuses.append(body.get("status"))
            flip.exit_codes.append(body.get("exit_code"))
            flip.test_counts.append((body.get("tests_passed"), body.get("tests_run")))
    return flips


def evaluate(reports: List[Dict[str, Any]]) -> StabilityResult:
    """Apply the three-part acceptance gate to N collected reports.

    Precedence (so the operator sees the most fundamental fault first):
      1. fewer than 2 reports -> usage error (cannot assess stability).
      2. non-constant submission_sha -> DELIVERABLE DRIFT (input not fixed).
      3. disagreeing overall OR per-layer counts -> P0 VERIFIER BUG.
      4. otherwise -> STABLE.
    """
    n = len(reports)
    shas = [str(r.get("submission_sha")) for r in reports]
    overalls = [str(r.get("overall")) for r in reports]
    layer_flips = _build_layer_flips(reports)
    messages: List[str] = []

    if n < 2:
        messages.append(
            f"USAGE: need >=2 graded reports to assess stability, got {n}. "
            "Re-run with --n >= 2."
        )
        return StabilityResult(
            n=n, submission_shas=shas, overalls=overalls,
            layer_flips=layer_flips, exit_code=EXIT_USAGE, messages=messages,
        )

    # (i) deliverable must be truly fixed — this is a precondition, not a
    # verifier result. A reference dir is a pure byte-copy, so a differing sha
    # means the EXPERIMENT is invalid (the input drifted), not that the
    # verifier flaked. Surface it as a distinct error so it's never logged as
    # a P0 verifier bug.
    distinct_shas = sorted(set(shas))
    if len(distinct_shas) > 1:
        messages.append(
            "DELIVERABLE NOT FIXED: submission_sha changed across runs — the "
            "graded input was not constant, so a verdict difference cannot be "
            "attributed to verifier noise. This is a setup/experiment bug."
        )
        messages.append(f"  distinct submission_sha: {distinct_shas}")
        # 'rejected' is the sentinel the runner writes on substrate/sandbox
        # reject (exit 3/4): a constant deliverable graded N times should never
        # alternate between 'rejected' and a real sha.
        if "rejected" in distinct_shas:
            messages.append(
                "  note: 'rejected' present — the substrate hash-pin / sandbox "
                "rejected SOME runs but not others (F1-class env flake). The "
                "reject-vs-grade outcome depends on uncommitted working-tree "
                "state, not the deliverable."
            )
        return StabilityResult(
            n=n, submission_shas=shas, overalls=overalls,
            layer_flips=layer_flips, exit_code=EXIT_DELIVERABLE_DRIFT,
            messages=messages,
        )

    # (ii) + (iii) — same fixed deliverable, so ANY disagreement is P0.
    overall_stable = len(set(overalls)) <= 1
    flipped_layers = {name: f for name, f in layer_flips.items() if f.flipped}

    if not overall_stable or flipped_layers:
        messages.append(
            "P0 VERIFIER BUG: a single FIXED deliverable (constant "
            f"submission_sha={distinct_shas[0][:12]}) produced a DIFFERENT "
            "verdict across runs. This is verifier noise, NEVER an agent "
            "result. Variance on a constant input must be 0."
        )
        if not overall_stable:
            counts = Counter(overalls)
            messages.append(f"  overall flipped: {dict(counts)} over {n} runs")
        for name, f in flipped_layers.items():
            attrib = []
            if f.exit_flip_rate > 0.0:
                attrib.append(
                    f"L1-style exit-code flip rate={f.exit_flip_rate:.2f} "
                    f"({f.exit_codes})"
                )
            if f.count_flip_rate > 0.0:
                attrib.append(
                    f"L2-style band/count flip rate={f.count_flip_rate:.2f} "
                    f"({[list(tc) for tc in f.test_counts]})"
                )
            if f.status_flip_rate > 0.0:
                attrib.append(
                    f"L2I-style error-vs-pass flip rate={f.status_flip_rate:.2f} "
                    f"({f.statuses})"
                )
            messages.append(f"  layer {name}: " + "; ".join(attrib))
        return StabilityResult(
            n=n, submission_shas=shas, overalls=overalls,
            layer_flips=layer_flips, exit_code=EXIT_VERIFIER_BUG,
            messages=messages,
        )

    messages.append(
        f"STABLE: {n} runs of a fixed deliverable "
        f"(submission_sha={distinct_shas[0][:12]}) all agreed "
        f"(overall={overalls[0]!r}). Verifier-noise == 0."
    )
    return StabilityResult(
        n=n, submission_shas=shas, overalls=overalls,
        layer_flips=layer_flips, exit_code=EXIT_STABLE, messages=messages,
    )


# --------------------------------------------------------------------------- #
# The N-run driver (uses the injectable grade_once seam)
# --------------------------------------------------------------------------- #
def run_stability_check(
    *,
    n: int,
    grade_once: GradeOnce,
    report_dir: Path,
) -> StabilityResult:
    """Grade the fixed deliverable N times via ``grade_once`` and evaluate.

    Each run gets a distinct report path ``report_dir/report_<i>.json``. A
    failure to produce/parse a report on any run is a usage error (we cannot
    assess stability from a partial set), reported with EXIT_USAGE.
    """
    report_dir.mkdir(parents=True, exist_ok=True)
    reports: List[Dict[str, Any]] = []
    for i in range(n):
        report_path = report_dir / f"report_{i}.json"
        try:
            rep = grade_once(i, report_path)
        except Exception as exc:  # noqa: BLE001 — surface any grading failure
            return StabilityResult(
                n=len(reports),
                submission_shas=[str(r.get("submission_sha")) for r in reports],
                overalls=[str(r.get("overall")) for r in reports],
                layer_flips=_build_layer_flips(reports),
                exit_code=EXIT_USAGE,
                messages=[
                    f"USAGE: grading run {i} failed before producing a report: "
                    f"{type(exc).__name__}: {exc}",
                ],
            )
        reports.append(rep)
    return evaluate(reports)


# --------------------------------------------------------------------------- #
# Live grade_once binding — invokes run_task.py as a subprocess
# --------------------------------------------------------------------------- #
def make_subprocess_grade_once(
    *,
    task: Path,
    submission: Path,
    ue_root: Path,
    python_exe: Optional[str] = None,
    run_task_py: Path = _RUN_TASK,
    extra_args: Optional[List[str]] = None,
) -> GradeOnce:
    """Build a grade_once that shells out to ``run_task.py``.

    Always passes ``--harness filesystem`` implicitly (run_task's default) so
    the deliverable is a pure byte-copy with no model call — the only way the
    submission_sha can be guaranteed constant across runs.
    """
    py = python_exe or sys.executable
    base = [
        py,
        str(run_task_py),
        "--task", str(task),
        "--submission", str(submission),
        "--ue-root", str(ue_root),
    ]
    if extra_args:
        base = base + list(extra_args)

    def _grade(run_index: int, report_json_path: Path) -> Dict[str, Any]:
        cmd = base + ["--report-json", str(report_json_path)]
        # run_task.py returns 0 (pass) / 1 (fail) / 3 (substrate reject) /
        # 4 (sandbox reject). We do NOT trust the exit code for the verdict —
        # we read report.json. We only fail the RUN (usage) if no report was
        # written and we can't parse it.
        proc = subprocess.run(
            cmd, capture_output=True, text=True, cwd=str(REPO_ROOT)
        )
        if not report_json_path.exists():
            raise RuntimeError(
                f"run_task.py wrote no report (exit={proc.returncode}). "
                f"stderr tail: {proc.stderr[-500:]!r}"
            )
        try:
            return json.loads(report_json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"could not parse report.json from run {run_index}: {exc}"
            ) from exc

    return _grade


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def render_text(result: StabilityResult) -> str:
    lines = [
        "CraftBench verifier-noise stability check",
        f"  runs (N)          : {result.n}",
        f"  deliverable fixed : {result.deliverable_fixed}",
        f"  overall stable    : {result.overall_stable}",
        f"  layers stable     : {result.layers_stable}",
        "  per-layer flip-rate:",
    ]
    if not result.layer_flips:
        lines.append("    (no layers observed)")
    for name, f in result.layer_flips.items():
        lines.append(
            f"    {name:10s} exit={f.exit_flip_rate:.2f} "
            f"count={f.count_flip_rate:.2f} status={f.status_flip_rate:.2f}"
            + ("  <-- FLIPPED" if f.flipped else "")
        )
    lines.append("")
    for m in result.messages:
        lines.append(m)
    lines.append("")
    verdict = {
        EXIT_STABLE: "PASS (verifier-noise == 0)",
        EXIT_VERIFIER_BUG: "FAIL — P0 VERIFIER BUG",
        EXIT_DELIVERABLE_DRIFT: "ERROR — DELIVERABLE NOT FIXED",
        EXIT_USAGE: "ERROR — could not complete N runs",
    }.get(result.exit_code, f"exit={result.exit_code}")
    lines.append(f"  verdict           : {verdict}  (exit {result.exit_code})")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="stability_check.py",
        description=(
            "Verifier-noise stability check: grade ONE fixed reference solution "
            "N times and assert the verdict never changes (variance == 0). Any "
            "disagreement on a constant submission_sha is a P0 verifier bug, "
            "never an agent result. Requires a UE install — budgeted CI, not "
            "per-PR."
        ),
    )
    p.add_argument("--task", required=True, type=Path, help="Task .md under tasks/.")
    p.add_argument(
        "--submission", required=True, type=Path,
        help="The ONE FIXED reference-solution directory to grade N times.",
    )
    p.add_argument(
        "--ue-root", required=True, type=Path,
        help="Path to a UE 5.7 install (the directory containing Engine/).",
    )
    p.add_argument(
        "--n", type=int, default=5,
        help="Number of times to grade the fixed deliverable (default 5).",
    )
    p.add_argument(
        "--report-dir", type=Path, default=None,
        help="Directory for the N per-run report_<i>.json files and the "
        "aggregate stability.json. Default: a tempdir.",
    )
    p.add_argument(
        "--json", dest="json_out", action="store_true",
        help="Also print the machine-readable stability summary as JSON.",
    )
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    if args.n < 2:
        print(
            f"USAGE: --n must be >= 2 to assess stability (got {args.n}).",
            file=sys.stderr,
        )
        return EXIT_USAGE

    if args.report_dir is not None:
        report_dir = args.report_dir
        report_dir.mkdir(parents=True, exist_ok=True)
        _tmp = None
    else:
        import tempfile

        _tmp = tempfile.mkdtemp(prefix="cb-stability-")
        report_dir = Path(_tmp)

    grade = make_subprocess_grade_once(
        task=args.task, submission=args.submission, ue_root=args.ue_root,
    )
    result = run_stability_check(n=args.n, grade_once=grade, report_dir=report_dir)

    # Persist the aggregate next to the per-run reports.
    (report_dir / "stability.json").write_text(
        json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(render_text(result))
    if args.json_out:
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    print(f"reports + stability.json in: {report_dir}")
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())

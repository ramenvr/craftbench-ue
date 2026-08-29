"""Frozen data model for the CraftBench dashboard — PURE STDLIB.

Every type here is an immutable ``@dataclass(frozen=True)`` so a Snapshot can be
shared across the watcher thread and request handlers without defensive copying.
This module imports only ``dataclasses``/``datetime``/``pathlib``/``typing`` — it
must stay importable in a bare ``python3`` with no third-party deps, so the data
layer is testable without textual/fastapi installed.

The ONE place that reaches outside stdlib is ``Snapshot.comparison()``, which
imports ``tools/compare/compare_products.py`` *lazily* (inside the method) to
delegate the per-capability pass-rate matrix, head-to-head, leaders and grounding
math. The dashboard does ZERO aggregation math of its own — it converts its
richer ``Run`` rows into ``compare.RunRecord`` rows and hands them to
``compare.aggregate``. Keeping that import lazy and local means ``model`` and
``collect`` stay dependency-free at import time.

Casing trap (encoded deliberately): ``result.json.overall`` is UPPERCASE
(``PASS``/``FAIL``/``FAIL_NO_EDITS``) while a verify-single ``report.overall`` is
lowercase (``pass``/``fail``). ``Run.passed`` is computed ONLY from
``overall.upper() == "PASS"`` — the two are never compared naively.
"""

from __future__ import annotations

import datetime as _dt
import pathlib
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Canonical layer keys, in their printed/declared order. ``render_text`` prints
# them as left-padded 3-char names; we strip the pad and normalize to these.
LAYER_KEYS = ("L1", "L2", "L2I", "L3", "ART", "R2")


@dataclass(frozen=True)
class LayerResult:
    """One per-layer outcome, text-parsed from a run's ``verifier_stdout.txt``.

    This is parsed from ``report.py::Report.render_text()`` output, NOT from a
    machine contract — see ``collect.parse_verifier_stdout`` and open-risk #1. The
    parse is best-effort; the coarse ``Run.overall`` is always authoritative.

    Fields:
        key:    one of LAYER_KEYS ("L1"/"L2"/"L2I"/"L3"/"ART"/"R2"), the layer
                name with ``render_text``'s left-pad stripped.
        status: normalized lowercase enum — "pass"|"fail"|"skip"|"error"|"n/a".
                stdout prints UPPERCASE (PASS/FAIL/SKIPPED); we lowercase and map
                "skipped" -> "skip".
        detail: the bracket extras (e.g. "exit=0, tests=1/1, warn=2") joined to
                the indented "- <note>" lines (newline-separated). The FAIL reason
                lives here. None when neither bracket nor notes are present.
    """

    key: str
    status: str
    detail: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {"key": self.key, "status": self.status, "detail": self.detail}


@dataclass(frozen=True)
class Task:
    """A scrubbed benchmark task, parsed from ``tasks/<task_id>.md``.

    ``task_id`` is the join key to runs (matched against ``Path(run.task).stem``).
    ``title``/``prompt_excerpt`` are cosmetic. ``set_name`` is named to avoid
    shadowing the ``set`` builtin (the spec field is literally ``- set:``).
    """

    task_id: str
    title: str
    capability_bucket: str
    tier: str
    set_name: Optional[str]
    layers: List[str]
    prompt_excerpt: str
    path: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "capability_bucket": self.capability_bucket,
            "tier": self.tier,
            "set_name": self.set_name,
            "layers": list(self.layers),
            "prompt_excerpt": self.prompt_excerpt,
            "path": self.path,
        }


@dataclass(frozen=True)
class Run:
    """One product × task attempt, parsed from ``runs/<run_id>/result.json``.

    ``product`` is the FULL slug (``<tool_layer>:<model>``) and is the compare
    join key; ``tool_layer``/``model`` are derived halves kept for grouping but
    the full slug is never dropped. ``blocker`` is SYNTHESIZED here (no such field
    exists in the schema) so the UI can show *why* a non-PASS happened without
    re-deriving it. ``layer_results`` prefers the embedded ``result.json.verifier``
    report dict (new runs) and falls back to a text-parse of the sibling
    ``verifier_stdout.txt``; it is ``[]`` whenever both are absent/empty —
    which is *every* FAIL_NO_EDITS run.
    """

    run_id: str
    task_id: str
    product: str          # full slug, the compare join key
    tool_layer: str       # product.partition(":")[0] — claude-p IS the Baseline product
    model: str            # product.partition(":")[2] suffix, "" if no colon
    overall: str          # raw PASS/FAIL/FAIL_NO_EDITS (UPPERCASE)
    passed: bool          # overall.upper() == "PASS"
    started_at: Optional[_dt.datetime]
    duration_s: Optional[float]
    cost_usd: Optional[float]
    summary: str
    blocker: Optional[str]            # DERIVED, None when passed
    layer_results: List[LayerResult]  # [] for FAIL_NO_EDITS / no captured text
    advisory_score: Optional[float]   # verifier.r2_advisory.advisory_score; None today
    # Swept capture screenshots: sorted PNG basenames under runs/<id>/artifacts/.
    # [] for every run recorded before phase-3 capture existed (the default).
    artifacts: List[str] = field(default_factory=list)
    # Whether this run belongs in a pass-rate denominator. False for the
    # verdicts meaning "the harness never reached a gradable state" —
    # HARNESS-ERROR, TIMEOUT, AGENT-CONFIG-ERROR, UNGRADED — because counting
    # those as non-passes charges an infrastructure failure to the model.
    #
    # SANDBOX-REJECT / NO_DELIVERABLE / FAIL_NO_EDITS are deliberately GRADED
    # (owner decision 2026-08-14): they describe what the MODEL did, and
    # excluding them would bias scores upward. The authoritative set is
    # ``collect._GRADED_VERDICTS``.
    #
    # Defaults True so pre-existing constructions keep their meaning.
    graded: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "task_id": self.task_id,
            "product": self.product,
            "tool_layer": self.tool_layer,
            "model": self.model,
            "overall": self.overall,
            "passed": self.passed,
            # Serialized: without it, every web/API consumer silently defaults
            # a voided run back to graded=True and re-counts what we excluded.
            "graded": self.graded,
            "started_at": _iso_z(self.started_at),
            "duration_s": self.duration_s,
            "cost_usd": self.cost_usd,
            "summary": self.summary,
            "blocker": self.blocker,
            "advisory_score": self.advisory_score,
            "layer_results": [lr.to_dict() for lr in self.layer_results],
            "artifacts": list(self.artifacts),
        }


def _iso_z(dt: Optional[_dt.datetime]) -> Optional[str]:
    """ISO-8601 UTC with a trailing 'Z' (not '+00:00'); None passes through."""
    if dt is None:
        return None
    return dt.astimezone(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class Snapshot:
    """The immutable read-only view of everything on disk at ``collect()`` time.

    Aggregation (matrix / head-to-head / leaders / grounding) is delegated to
    ``tools/compare`` via ``comparison()`` — the only method that imports a
    non-stdlib intra-repo module, and it does so lazily so this class stays
    importable without compare on ``sys.path`` until aggregation is requested.

    The ``latest_only`` flag (default False everywhere = all-attempts, matching
    ``compare.aggregate``'s n-counting) dedupes duplicate ``(product, task_id)``
    attempts down to the newest ``started_at`` BEFORE feeding compare, so a
    re-run sweep doesn't inflate n. The per-run table / head-to-head / coverage
    views disambiguate n>1 (open-risk #3).
    """

    generated_at: str          # ISO-8601 UTC of the collect() call
    tasks: List[Task]          # sorted by task_id
    runs: List[Run]            # ALL product runs, NO dedupe, sorted by started_at then run_id
    products: List[str]        # sorted unique Run.product slugs
    capabilities: List[str]    # sorted unique buckets across tasks + runs
    repo_root: pathlib.Path = field(default=pathlib.Path("."))

    # -- aggregation: the SOLE compare importer ---------------------------------

    def comparison(self, latest_only: bool = False):
        """Build the compare ``Comparison`` (the only place importing compare).

        Converts ``Run`` rows -> ``compare.RunRecord`` rows and calls
        ``compare.aggregate``. With ``latest_only=True`` we first dedupe to the
        newest attempt per ``(product, task_id)`` so n reflects tasks, not retries.
        The import is via ``sys.path`` append of ``<repo_root>/tools/compare`` +
        ``import compare_products`` by basename — matching ``test_compare.py`` and
        the one documented intra-repo coupling (open-risk #4).
        """
        compare = _import_compare(self.repo_root)
        # task_id -> capability, so compare's RunRecord.capability is consistent
        # with the task .md the dashboard already parsed (a run may reference a
        # task that has since changed bucket; the parsed Task is the source).
        cap_by_task = {t.task_id: t.capability_bucket for t in self.tasks}

        runs = self.runs
        if latest_only:
            runs = _dedupe_latest(runs)

        records = [
            compare.RunRecord(
                product=r.product,
                task_id=r.task_id,
                capability=cap_by_task.get(r.task_id, "uncategorized"),
                passed=r.passed,
                advisory_score=r.advisory_score,
                cost_usd=r.cost_usd,
                graded=r.graded,
            )
            for r in runs
        ]
        return compare.aggregate(records)

    # -- thin read-only views over the comparison -------------------------------

    def matrix(self, latest_only: bool = False) -> List[Dict[str, Any]]:
        """compare's per-(capability, product) cells with n>0 (the ``cells`` list)."""
        compare = _import_compare(self.repo_root)
        return compare.to_dict(self.comparison(latest_only))["cells"]

    def cell(self, capability: str, product: str, latest_only: bool = False) -> Dict[str, Any]:
        """One matrix cell as a plain dict; zeros when no run for (cap, product)."""
        c = self.comparison(latest_only).cell(capability, product)
        return {
            "capability": capability,
            "product": product,
            "n": c.n,
            "n_pass": c.n_pass,
            "pass_rate": round(c.pass_rate, 3),
            "mean_advisory": c.mean_advisory,
            "cost_usd": round(c.cost, 4) or None,
        }

    def head_to_head(self, latest_only: bool = False) -> List[Dict[str, Any]]:
        """Tasks run by >=2 products (compare's ``head_to_head``)."""
        compare = _import_compare(self.repo_root)
        return compare.to_dict(self.comparison(latest_only))["head_to_head"]

    def coverage_gaps(self) -> List[Dict[str, Any]]:
        """Declared task × observed product with NO run for that pair.

        Framed as "not yet attempted", NOT "should have run" (open-risk #5) — the
        cross product is intentionally permissive. Only products actually observed
        in ``runs`` are considered (we never invent a product). A task with no
        runs at all lists every observed product as missing.
        """
        observed = list(self.products)
        ran = {(r.task_id, r.product) for r in self.runs}
        gaps: List[Dict[str, Any]] = []
        for t in self.tasks:
            missing = [p for p in observed if (t.task_id, p) not in ran]
            if missing:
                gaps.append({
                    "task_id": t.task_id,
                    "capability": t.capability_bucket,
                    "products_missing": missing,
                })
        return gaps

    def totals(self) -> Dict[str, Any]:
        """Headline counters over ALL attempts (not deduped) + cost roll-up.

        ``total_cost_usd`` sums only present ``cost_usd`` (None-tolerant — May-27
        runs have no telemetry, open-risk #6). Grounded/ungrounded come from
        compare's grounding over the default all-attempts comparison.
        """
        cmp = self.comparison(latest_only=False)
        n_pass = sum(1 for r in self.runs if r.passed)
        n_fail_no_edits = sum(1 for r in self.runs if r.overall.upper() == "FAIL_NO_EDITS")
        # FAIL = any GRADED non-PASS that is not the explicit no-edits sentinel.
        # This used to be a denylist-by-default with exactly one exception, so
        # every harness verdict (HARNESS-ERROR, TIMEOUT, ...) was counted as a
        # model failure. It is now an allowlist: ungraded runs get their own
        # bucket instead of inflating n_fail.
        n_fail = sum(
            1 for r in self.runs
            if r.graded and not r.passed and r.overall.upper() != "FAIL_NO_EDITS"
        )
        n_excluded = sum(1 for r in self.runs if not r.graded)
        total_cost = sum(r.cost_usd for r in self.runs if r.cost_usd is not None)
        grounded = [c for c in cmp.capabilities if cmp.is_grounded(c)]
        ungrounded = [c for c in cmp.capabilities if not cmp.is_grounded(c)]
        return {
            "n_tasks": len(self.tasks),
            "n_runs": len(self.runs),
            "n_products": len(self.products),
            "n_pass": n_pass,
            "n_fail": n_fail,
            "n_fail_no_edits": n_fail_no_edits,
            # Runs that never reached a gradable state. Reported so a shrinking
            # denominator is visible rather than silent.
            "n_excluded": n_excluded,
            "total_cost_usd": round(total_cost, 4) if total_cost else None,
            "grounded_capabilities": grounded,
            "ungrounded_capabilities": ungrounded,
        }

    def task_progress(self) -> Dict[str, Any]:
        """Per-task implementation status + a roll-up funnel — "what's built yet".

        Honest, purely disk-derived (no manual status field to drift):
          * ``validated`` — >=1 PASS run exists (the verifier discriminated a
            correct solution) -> fully implemented AND proven.
          * ``wired`` — a reference solution exists OR the task has been run, but
            no PASS yet -> implemented, awaiting validation.
          * ``planned`` — only the ``.md`` exists (no reference solution, never
            run) -> authored, verifier not yet implemented.

        ``summary`` frames the funnel against the v1.0 ~40-task target so the
        not-yet-built gap (authored vs target) is explicit.
        """
        refsol_dir = self.repo_root / "tests" / "reference-solutions"
        have_ref = (
            {p.name for p in refsol_dir.iterdir() if p.is_dir()}
            if refsol_dir.is_dir() else set()
        )
        # Folder-per-task layout: a task's reference solution may live beside its
        # spec (tasks/<set>/<id>/reference/) instead of the legacy tree above.
        # Union both homes so either counts as "wired".
        for ref in (self.repo_root / "tasks").glob("*/*/reference"):
            if ref.is_dir():
                have_ref.add(ref.parent.name)
        n_runs: Dict[str, int] = {}
        n_pass: Dict[str, int] = {}
        for r in self.runs:
            n_runs[r.task_id] = n_runs.get(r.task_id, 0) + 1
            if r.passed:
                n_pass[r.task_id] = n_pass.get(r.task_id, 0) + 1

        items: List[Dict[str, Any]] = []
        counts = {"validated": 0, "wired": 0, "planned": 0}
        for t in self.tasks:
            runs_ct = n_runs.get(t.task_id, 0)
            pass_ct = n_pass.get(t.task_id, 0)
            ref = t.task_id in have_ref
            if pass_ct > 0:
                status = "validated"
            elif ref or runs_ct > 0:
                status = "wired"
            else:
                status = "planned"
            counts[status] += 1
            items.append({
                "task_id": t.task_id,
                "capability": t.capability_bucket,
                "tier": t.tier,
                "set_name": t.set_name,
                "layers": list(t.layers),
                "has_reference_solution": ref,
                "n_runs": runs_ct,
                "n_pass": pass_ct,
                "status": status,
            })
        return {
            "items": items,
            "summary": {
                "authored": len(self.tasks),
                "validated": counts["validated"],
                "wired": counts["wired"],
                "planned": counts["planned"],
                "v1_target": 40,  # spec: v1.0 task-set target is ~40
            },
        }

    # -- the web API payload ----------------------------------------------------

    def to_dict(self, latest_only: bool = False) -> Dict[str, Any]:
        """The schema-tagged, JSON-serializable web payload (GET /api/snapshot).

        ``matrix``/``leaders``/``head_to_head``/``ungrounded_capabilities`` come
        VERBATIM from ``compare.to_dict`` (the dashboard does no matrix math);
        ``coverage_gaps``/``totals`` are dashboard-only derived views. Default
        ``latest_only=False`` = all-attempts, matching ``compare.aggregate``.
        """
        compare = _import_compare(self.repo_root)
        cmp_dict = compare.to_dict(self.comparison(latest_only))
        return {
            "schema": "craftbench.dashboard/v1",
            "generated_at": self.generated_at,
            "products": list(self.products),
            "capabilities": list(self.capabilities),
            "tasks": [t.to_dict() for t in self.tasks],
            "runs": [r.to_dict() for r in self.runs],
            # straight from compare:
            "matrix": cmp_dict["cells"],
            "leaders": cmp_dict["leaders"],
            "head_to_head": cmp_dict["head_to_head"],
            "ungrounded_capabilities": cmp_dict["ungrounded_capabilities"],
            # dashboard-only derived:
            "coverage_gaps": self.coverage_gaps(),
            "task_progress": self.task_progress(),
            "totals": self.totals(),
        }


def _dedupe_latest(runs: List[Run]) -> List[Run]:
    """Keep the newest attempt per (product, task_id) by ``started_at``.

    Runs with an unparseable ``started_at`` (None) sort earliest, so a sibling
    with a real timestamp wins; if every attempt for a pair is None they tie and
    the last-seen (input order) is kept. Input is assumed sorted by started_at
    then run_id (as ``collect`` produces), so the last write per key is newest.
    """
    chosen: Dict[tuple, Run] = {}
    epoch = _dt.datetime(1970, 1, 1, tzinfo=_dt.timezone.utc)
    for r in runs:
        key = (r.product, r.task_id)
        prev = chosen.get(key)
        if prev is None or (r.started_at or epoch) >= (prev.started_at or epoch):
            chosen[key] = r
    return list(chosen.values())


_COMPARE_MODULE: Any = None


def _compare_dir_candidates(repo_root: pathlib.Path) -> List[pathlib.Path]:
    """Where ``tools/compare`` might live, most-reliable first.

    1. Beside THIS package on disk (``tools/dashboard`` and ``tools/compare`` are
       siblings) — correct regardless of where the *data* repo_root points, so a
       synthetic test repo_root (a tempdir with no ``tools/compare``) still finds
       the real, repo-resident compare module.
    2. Under the data ``repo_root`` (the documented intra-repo coupling, used when
       the dashboard code is co-located with the data it reads).
    """
    here = pathlib.Path(__file__).resolve().parent          # .../tools/dashboard
    return [here.parent / "compare", pathlib.Path(repo_root).resolve() / "tools" / "compare"]


def _import_compare(repo_root: pathlib.Path):
    """Import ``compare_products`` (lazy, cached) — the SOLE non-stdlib import.

    Mirrors ``tools/compare/tests/test_compare.py``: append the ``tools/compare``
    dir to ``sys.path`` and import by basename. The module is the same object for
    any repo_root (compare is global, pure stdlib), so we cache it once. This is
    the one documented intra-repo coupling (open-risk #4) and lives only behind
    aggregation calls, keeping ``model``/``collect`` import-time dep-free.
    """
    global _COMPARE_MODULE
    if _COMPARE_MODULE is not None:
        return _COMPARE_MODULE
    for compare_dir in _compare_dir_candidates(repo_root):
        if (compare_dir / "compare_products.py").is_file():
            if str(compare_dir) not in sys.path:
                sys.path.insert(0, str(compare_dir))
            break
    import compare_products  # noqa: E402  (lazy, intentional intra-repo coupling)
    _COMPARE_MODULE = compare_products
    return compare_products

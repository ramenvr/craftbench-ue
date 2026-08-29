"""Report types for the CraftBench verifier runner.

Serializes to the JSON shape documented in tools/verify-single/README.md and
renders a short human-readable summary for stdout.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class LayerReport:
    """Per-layer outcome. ``status`` is one of pass|fail|skipped|error.

    ``error`` is NOT a third grade — it means the layer's verdict channel
    produced nothing to read (a verifier-owned grader is missing/broken), and
    ``run_task.harness_error_reasons`` predicate (5) routes it to the non-graded
    HARNESS-ERROR state (exit 7) rather than letting it reach ``overall``. Only
    L2I emits it today; see ``layers/INTROSPECT_CONTRACT.md``.
    """

    status: str
    log: Optional[str] = None
    exit_code: Optional[int] = None
    duration_seconds: Optional[float] = None
    # L1-specific
    warnings_in_agent_files: Optional[int] = None
    # STRUCTURAL provenance, same doctrine as the four L2 signals below: True
    # only when l1_build's own fault paths fired. harness_error_reasons
    # predicate (3) requires it ALONGSIDE the exit code, because Build.cs is
    # inside the sandbox writable prefix and so a submission can make the build
    # tool exit anything it likes.
    build_tool_never_ran: Optional[bool] = None
    # L2-specific
    tests_run: Optional[int] = None
    tests_passed: Optional[int] = None
    # Free-form extras
    notes: list[str] = field(default_factory=list)
    # STRUCTURAL machine-fault signal, computed by the layer that reads the log
    # (l2_pie._rhi_unavailable). It exists so harness_error_reasons can tell "the
    # GPU refused the editor a resource" from "the agent's code crashed the
    # editor" WITHOUT reading note prose — those two are otherwise identical in
    # shape (L1 pass, tests_run 0, status skipped), which is exactly why
    # predicate (4) was left unimplemented until now.
    rhi_unavailable: Optional[bool] = None
    # Second structural machine-fault signal, same doctrine: the automation
    # controller QUEUED the requested test (so the filter matched) and the
    # editor exited before it started — our own `; Quit` in -ExecCmds racing
    # the controller. Distinguished from an agent crash by the fact that
    # nothing of the submission has run yet at that point; see
    # l2_pie._queued_never_started for the three-log measurement.
    queued_never_started: Optional[bool] = None
    # Third structural signal: a fixture finished through
    # EFunctionalTestResult::Error, which after the 2026-08-14 audit means one
    # thing corpus-wide — the HARNESS could not set the test up. MATCHED from the
    # engine's own FunctionalTest emission (FunctionalTest.cpp:471), not from our
    # note prose.
    #
    # Unlike the two above, this is NOT beyond a submission's reach: agent C++
    # shares the process and the log. The match is anchored on the engine's exact
    # format to reduce that, and the consuming predicate additionally requires
    # tests_run == 0 so a spoof must break its own run — see
    # l2_pie._harness_precondition for the full residual-risk argument, and
    # the ::Error tag audit for what a NEW ::Error must satisfy.
    harness_precondition: Optional[bool] = None
    # Fourth structural signal, and the only one of the four a submission cannot
    # reach: the editor produced a ZERO-BYTE log and exited on something other
    # than the governed timeout, i.e. it died before opening its own log and so
    # ran neither the test nor the submission. The other three match log TEXT,
    # which agent C++ can write; this one keys on the log's ABSENCE, and agent
    # code executes only after the log is open.
    #
    # Added 2026-08-17 from a measured run that had all three siblings False and
    # still graded FAIL against the model: both L2 legs 0 bytes, no UECC dump,
    # exit 0xC0000142 (STATUS_DLL_INIT_FAILED), L1 PASS. See
    # l2_pie._editor_never_started for why each conjunct is required.
    editor_never_started: Optional[bool] = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Drop None entries for a cleaner JSON shape.
        return {k: v for k, v in d.items() if v is not None and v != []}


@dataclass
class HostInfo:
    """Machine fingerprint captured at run time."""

    os: str
    arch: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Report:
    """Top-level verifier report."""

    task_id: str
    submission_sha: str
    layers: dict[str, LayerReport]
    # pass|fail|harness-error. "harness-error" (run_task.OVERALL_HARNESS_ERROR)
    # is the NON-GRADED state: the verifier could not produce a verdict at all,
    # so this run belongs in no pass-rate denominator. It is NOT a third grade —
    # consumers that ask "did it pass" keep doing `overall.upper() == "PASS"`,
    # and the ones that compute rates go through
    # adapters.base.is_graded_verdict, which allowlists PASS/FAIL only.
    overall: str
    duration_seconds: float
    ue_version: str
    host: HostInfo
    sandbox_violations: int = 0

    # Human-readable LOCAL wall-clock time the grade was produced
    # ("YYYY-MM-DD HH:MM:SS") — the report header leads with this so a run reads at a
    # glance instead of only by content hash. Optional so older reports / test literals
    # round-trip unchanged; OMITTED from the JSON when None.
    graded_at: Optional[str] = None

    # NON-GATING advisory block from the R2 LLM-judge (tools/verify-r2). It is
    # deliberately NOT a member of ``layers`` — ``overall`` is computed from
    # ``layers`` alone, so no advisory value can flip the certified outcome
    # (FR-020d). The judge that produced this never saw ``overall`` (anti-anchoring
    # firewall in tools/verify-r2/judge.py). Present only when --r2 was requested.
    r2_advisory: Optional[dict[str, Any]] = None

    # Run-dir-relative paths of collected visual artifacts (e.g.
    # "artifacts/shot.png" from --capture / L3 screenshot sweeps). NON-GATING and
    # OMITTED from the JSON when empty, so pre-existing reports stay
    # byte-identical when the feature is unused.
    artifacts: list[str] = field(default_factory=list)

    # How the graded substrate was materialized: "git-head" (committed files
    # only — the certified default) or "live" (--substrate-from-live / any
    # live-copy fallback — UNCERTIFIED, the verdict may depend on uncommitted
    # disk state). Optional so older reports / test literals round-trip
    # unchanged; OMITTED from the JSON when None.
    substrate_source: Optional[str] = None

    # How the graded workdir's CONTENT was staged (content_staging.py):
    # {"mode": "per-task"|"full", "excluded_count": N, "excluded": [...],
    #  "notes": [...]}. "per-task" means other tasks' maps / Content/Tasks/
    # baselines / OFPA mirrors were pruned from the staged tree; "full" means
    # everything was staged (the --full-substrate / CB_FULL_SUBSTRATE escape
    # hatch, or the filter's fail-open on a derivation error — the notes say
    # which). NON-GATING, purely descriptive: nothing here reaches ``overall``.
    # Optional/OMITTED-when-None so older reports round-trip unchanged.
    content_staging: Optional[dict[str, Any]] = None

    # FR-002 provenance anchor: the most recent commit SHA touching the graded
    # substrate dir (pinning.git_revision_for). Pins WHICH substrate the grade
    # ran against — "git-head" alone names a moving target (2026-07-22 audit:
    # the exact HEAD commit graded against was not recorded anywhere).
    # Optional/OMITTED-when-None so older reports round-trip unchanged.
    substrate_revision: Optional[str] = None

    # Wall-clock accounting of the RUNNER's own phases (phase_timer.PhaseTimer).
    # Sums to ``duration_seconds`` by construction: the block always carries an
    # ``unaccounted`` remainder, so an un-instrumented phase shows up as a
    # growing number rather than as absent cost. NON-GATING and purely
    # descriptive — nothing here reaches ``overall``. Optional/OMITTED-when-None
    # so pre-existing reports round-trip byte-identical.
    phases: Optional[dict[str, float]] = None

    # Run-level caveats that belong to the RUN rather than to any one layer —
    # today, what --lite did not do and why its numbers mean less than they look.
    # A reader who opens this report months later sees the caveat next to the
    # numbers instead of having to reconstruct which flags produced them.
    # OMITTED from the JSON when empty, so existing reports are unchanged.
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Executable non-gating guard, verifier-side: an advisory that claims to
        # gate is a contract breach and is refused at the door.
        if self.r2_advisory is not None and self.r2_advisory.get("gating") is True:
            raise ValueError("r2_advisory.gating must be False — the advisory is non-gating")

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "task_id": self.task_id,
            "submission_sha": self.submission_sha,
            "layers": {k: v.to_dict() for k, v in self.layers.items()},
            "overall": self.overall,
            "duration_seconds": self.duration_seconds,
            "ue_version": self.ue_version,
            "host": self.host.to_dict(),
            "sandbox_violations": self.sandbox_violations,
        }
        if self.graded_at is not None:
            d["graded_at"] = self.graded_at
        if self.r2_advisory is not None:
            d["r2_advisory"] = self.r2_advisory
        if self.artifacts:
            d["artifacts"] = list(self.artifacts)
        if self.substrate_source is not None:
            d["substrate_source"] = self.substrate_source
        if self.content_staging is not None:
            d["content_staging"] = dict(self.content_staging)
        if self.substrate_revision is not None:
            d["substrate_revision"] = self.substrate_revision
        if self.phases:
            d["phases"] = dict(self.phases)
        if self.notes:
            d["notes"] = list(self.notes)
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    def write_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json() + "\n", encoding="utf-8")

    def render_text(self) -> str:
        """Compact human-readable summary suitable for stdout."""
        lines = [
            f"CraftBench verifier report",
            f"  task_id   : {self.task_id}",
        ]
        # Lead with the actual date/time so the run is legible at a glance; the
        # content fingerprint (opaque sha) moves below and is clearly labelled.
        if self.graded_at:
            lines.append(f"  graded_at : {self.graded_at}")
        lines += [
            f"  ue_version: {self.ue_version}",
            f"  host      : {self.host.os}/{self.host.arch}",
            f"  duration  : {self.duration_seconds:.1f}s",
        ]
        if self.submission_sha and self.submission_sha != "rejected":
            lines.append(
                f"  content   : {self.submission_sha[:12]} (sha256 of graded files)")
        if self.substrate_source is not None:
            if self.substrate_source == "live":
                lines.append(
                    "  substrate : live (UNCERTIFIED — graded from the live "
                    "working tree, not git HEAD)")
            else:
                lines.append(f"  substrate : {self.substrate_source}")
        if self.substrate_revision is not None:
            lines.append(
                f"  substrate_rev: {self.substrate_revision[:12]} "
                f"(last commit touching the substrate)")
        if self.content_staging is not None:
            _cs_mode = self.content_staging.get("mode", "?")
            _cs_n = self.content_staging.get("excluded_count", 0)
            lines.append(
                f"  staging   : {_cs_mode} content"
                f" ({_cs_n} entr{'y' if _cs_n == 1 else 'ies'} excluded)")
        for name, layer in self.layers.items():
            extras = []
            # Duration leads the bracket: it is the field a reader scans for when
            # asking "where did the time go", and every layer carries one now
            # (registry.run_layers fills any the layer left unset).
            if layer.duration_seconds is not None:
                extras.append(f"{layer.duration_seconds:.1f}s")
            if layer.exit_code is not None:
                extras.append(f"exit={layer.exit_code}")
            if layer.tests_run is not None:
                extras.append(f"tests={layer.tests_passed}/{layer.tests_run}")
            if layer.warnings_in_agent_files is not None:
                extras.append(f"warn={layer.warnings_in_agent_files}")
            extras_str = (" [" + ", ".join(extras) + "]") if extras else ""
            log_str = f" log={layer.log}" if layer.log else ""
            lines.append(f"  {name:3s} : {layer.status.upper():7s}{extras_str}{log_str}")
            for note in layer.notes:
                lines.append(f"        - {note}")
        if self.artifacts:
            lines.append(f"  artifacts : {len(self.artifacts)} file(s)")
        if self.phases:
            # Descending by cost — the point of the block is "what should a
            # lighter mode trim", and that reads off the top line.
            lines.append("  phases    :")
            for pname, secs in sorted(
                self.phases.items(), key=lambda kv: kv[1], reverse=True
            ):
                share = (
                    f" ({100 * secs / self.duration_seconds:.1f}%)"
                    if self.duration_seconds else ""
                )
                lines.append(f"      {pname:<18s} {secs:7.2f}s{share}")
        for note in self.notes:
            lines.append(f"  note      : {note}")
        lines.append(f"  overall   : {self.overall.upper()}")
        # Say it in words, not just as a status token. "UNGRADED" alone is easy
        # to skim past as a variant of PASS; the reason it is not a verdict is
        # the thing a reader has to take away.
        if self.overall == "ungraded":
            lines.append(
                "              ^ NOT a verdict — this run did not build the "
                "code. Excluded from every pass-rate.")
        if self.sandbox_violations:
            lines.append(f"  sandbox   : {self.sandbox_violations} violation(s) — submission rejected")
        if self.r2_advisory is not None:
            adv = self.r2_advisory
            score = adv.get("advisory_score")
            conf = adv.get("confidence")
            score_s = f"{score:.2f}" if isinstance(score, (int, float)) else "n/a"
            conf_s = f"{conf:.2f}" if isinstance(conf, (int, float)) else "n/a"
            lines.append(
                f"  advisory  : {score_s} (conf {conf_s}) — NON-GATING, does not affect overall"
            )
        return "\n".join(lines)


def report_from_dict(data: dict[str, Any]) -> Report:
    """Inverse of `Report.to_dict` — used by tests for round-trip checks."""
    layers = {
        name: LayerReport(**body) for name, body in data.get("layers", {}).items()
    }
    return Report(
        task_id=data["task_id"],
        submission_sha=data["submission_sha"],
        layers=layers,
        overall=data["overall"],
        duration_seconds=float(data["duration_seconds"]),
        ue_version=data["ue_version"],
        host=HostInfo(**data["host"]),
        sandbox_violations=int(data.get("sandbox_violations", 0)),
        graded_at=data.get("graded_at"),
        r2_advisory=data.get("r2_advisory"),
        artifacts=list(data.get("artifacts", [])),
        substrate_source=data.get("substrate_source"),
        content_staging=data.get("content_staging"),
        # substrate_revision was silently DROPPED here (it round-tripped to
        # None), so a report re-serialized through this helper lost its FR-002
        # provenance anchor. Restored alongside `phases` rather than left as a
        # trap for the next round-trip test.
        substrate_revision=data.get("substrate_revision"),
        phases=data.get("phases"),
        notes=list(data.get("notes", [])),
    )

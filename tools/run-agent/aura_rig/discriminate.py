"""Batch DISCRIMINATION runner — the deterministic, token-free `cb discriminate`
(alias `cb wip`) mode.

For a task id (or a whole set, e.g. ``bp-g2``) this re-runs the FULL FR-017
discrimination matrix the ``/craftbench-build-verifier`` skill (SKILL.md Phase 7)
demands, WITHOUT any agent or tokens:

  * grade the reference solution  (folder-local ``reference/``, else the legacy
    ``tests/reference-solutions/<id>/``)                                 → must PASS
  * grade an EMPTY submission      (a throwaway empty dir)               → must FAIL
  * grade each gaming variant      (folder-local ``discrimination/<v>/``, else
    the legacy ``tests/discrimination/<id>/<v>/``)                       → must FAIL
    **via its MATRIX.md named-assertion substring**, NOT merely exit 1.

A task is *discriminated* iff every leg lands the expected way. A wrong-reason
FAIL — a compile error (L1), a SUBSTRATE-REJECT (exit 3), a SANDBOX-REJECT
(exit 4), a HARNESS-ERROR (exit 5/7: the verifier produced no verdict at all), a
SKIPPED (no tests discovered), or a FAIL whose L2 log does NOT contain the row's
named substring (i.e. the wrong checkpoint fired) — is NOT discrimination; it is
the pass-everything / fail-everything trap and is reported as such.

Design constraints honored (repo conventions + the task brief):
  * This module is **pure over the filesystem + an injected subprocess seam**
    (``runner=`` callable), mirroring ``tasks.py`` / ``doctor.py``. The only
    side effects are the (injected) ``run_task.py`` subprocesses + reading the
    JSON reports + L2 logs they write. That makes every aggregation / parsing /
    wrong-reason rule unit-testable with the editor mocked out.
  * It NEVER regenerates the verifier-hash manifest. Regenerating from a CRLF
    working tree corrupts from-HEAD grading (repo convention), so the runner only ever
    *chooses the substrate source*: a committed-and-clean task grades from git
    HEAD (the default), an UNCOMMITTED/WIP task grades ``--substrate-from-live``.
  * ``--wip`` forces from-live for every task (the maintainer is mid-edit).

``cb.py`` wires this in as a thin subcommand; this file reimplements nothing of
the verifier — it shells the existing ``tools/verify-single/run_task.py`` and
reads its existing JSON report + L2 log artifacts.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from aura_rig import tasks


# --------------------------------------------------------------------------- #
# Leg / outcome model                                                         #
# --------------------------------------------------------------------------- #

# run_task.py exit codes (tools/verify-single/run_task.py — see its exit-code
# taxonomy block; 3 is retired-and-reserved, 6 is forbidden).
EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_USAGE = 2
EXIT_SUBSTRATE_REJECT = 3
EXIT_SANDBOX_REJECT = 4
EXIT_NO_UPROJECT = 5
EXIT_HARNESS_ERROR = 7

# Human label per "wrong-reason" so the table can say WHY a FAIL wasn't credited.
# EVERY non-graded verifier exit belongs here: a leg that never reached the
# assertion cannot evidence discrimination in EITHER direction. Crediting exit 7
# would be the worst case — the harness announcing "I could not measure this"
# would be recorded as "the variant was correctly caught", which is precisely the
# fail-everything trap this module exists to detect.
_WRONG_REASON = {
    EXIT_USAGE: "usage-error",
    EXIT_SUBSTRATE_REJECT: "substrate-reject",
    EXIT_SANDBOX_REJECT: "sandbox-reject",
    EXIT_NO_UPROJECT: "harness-error",
    EXIT_HARNESS_ERROR: "harness-error",
}


@dataclass(frozen=True)
class RunResult:
    """What the injected runner returns for ONE ``run_task.py`` invocation.

    ``report`` is the parsed report.json dict (or ``None`` if the run produced
    no report — e.g. it crashed before writing one). ``l2_log`` is the text of
    the L2 layer's editor stdout log (the file ``report["layers"]["L2"]["log"]``
    points at), or ``""`` when there is no L2 layer / no log. The named MATRIX
    substring for a gaming variant lives in THAT log (the verifier counts
    pass/fail but does not lift the ``FinishTest(Failed, "At t=…")`` message
    into a structured report field — see tools/verify-single/layers/l2_pie.py),
    so wrong-reason detection searches it."""

    exit_code: int
    report: Optional[dict] = None
    l2_log: str = ""
    stderr_tail: str = ""


# What each leg is *supposed* to do.
KIND_REFERENCE = "reference"
KIND_EMPTY = "empty"
KIND_VARIANT = "variant"


@dataclass
class LegSpec:
    """One row of the matrix to run for a task."""

    kind: str  # reference | empty | variant
    label: str  # "reference", "empty", or the variant dir name
    submission: Optional[Path]  # None => empty (a throwaway dir is created)
    expect_pass: bool
    # For variants: the named MATRIX substring(s) that MUST appear in the L2 log
    # of the (expected) FAIL for it to count as discriminated. Empty for the
    # reference (PASS has no message to match) and for the empty stub when the
    # MATRIX did not record one (exit-1 FAIL is sufficient for empty).
    expected_substrings: Tuple[str, ...] = ()


@dataclass
class LegOutcome:
    """The verdict of running one LegSpec."""

    spec: LegSpec
    exit_code: int
    discriminated: bool  # did this leg behave as the matrix requires?
    detail: str  # short human reason (for the table cell)

    @property
    def cell(self) -> str:
        """Compact table cell: PASS / FAIL plus a parenthetical reason when the
        leg did NOT discriminate (so a wrong-reason FAIL is never mistaken for a
        clean one)."""
        verdict = "PASS" if self.exit_code == EXIT_PASS else "FAIL"
        if self.discriminated:
            return verdict
        return f"{verdict}({self.detail})"


@dataclass
class TaskOutcome:
    """All legs for one task + the overall discriminated verdict."""

    task_id: str
    legs: List[LegOutcome] = field(default_factory=list)
    error: Optional[str] = None  # set when the task could not be assembled at all

    @property
    def discriminated(self) -> bool:
        return self.error is None and bool(self.legs) and all(
            leg.discriminated for leg in self.legs
        )


# --------------------------------------------------------------------------- #
# MATRIX.md parsing                                                           #
# --------------------------------------------------------------------------- #

# A markdown table row: split on unescaped pipes, drop the leading/trailing
# empties. We only ever need the FIRST cell (submission) + the message cell.
def _split_md_row(line: str) -> List[str]:
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return cells


def _is_separator_row(cells: Sequence[str]) -> bool:
    return all(re.fullmatch(r":?-{2,}:?", c) is not None for c in cells if c)


_BACKTICK_RE = re.compile(r"`([^`]+)`")
_VARIANT_DIR_RE = re.compile(r"`?([A-Za-z0-9_-]+)/`?")


def _extract_substrings(message_cell: str) -> Tuple[str, ...]:
    """Pull the named-assertion substring(s) out of a MATRIX message cell.

    Two recorded shapes coexist in the repo today:
      * gp-spawn-sequence: ``expected 1, found 0 (children tagged `SpawnedClone`)``
        — a *summary* of the assertion, NOT verbatim. The real fixture message is
        ``At t=1.50s (checkpoint 1): expected 1 SpawnedChild actor(s); found 0.``
        — so ``expected 1, found 0`` is NOT a literal substring of the log. We
        therefore split this form into its two ANCHOR fragments — ``expected 1``
        and ``found 0`` — and require BOTH to appear (robust to the engine's
        interpolated ``<thing>; `` between them while still pinning the exact
        numbers, which is what discriminates the right checkpoint from the wrong).
      * gp-inventory-stacking: a backtick-wrapped literal,
        ``\\`AddItem(Stone,7) returned false; 7 units should fit.\\```. This IS the
        verbatim assertion text, matched as a single substring.

    Preference order: backtick-wrapped substantive literals (the author's exact
    assertion text) win as a single substring; else the ``expected N … found M``
    summary becomes the two-fragment anchor pair; else the whole de-noised cell.
    The returned TUPLE is matched with ALL-of semantics by ``grade_leg``."""
    cell = message_cell.strip()
    if not cell or cell in {"—", "-", "n/a", "N/A"}:
        return ()
    ticked = _BACKTICK_RE.findall(cell)
    if ticked:
        # Drop short bareword ticks like `SpawnedClone` that are parentheticals,
        # keep substantive assertion literals (contain a space or punctuation).
        substantive = [t for t in ticked if (" " in t or any(ch in t for ch in "(),.="))]
        if substantive:
            return tuple(substantive)
    # The "expected N, found M" summary → two number-anchored fragments, both
    # required. This pins the exact checkpoint numbers without assuming the
    # engine's verbatim phrasing between them.
    exp = re.search(r"expected\s+\d+", cell, re.IGNORECASE)
    found = re.search(r"found\s+\d+", cell, re.IGNORECASE)
    if exp and found:
        return (exp.group(0), found.group(0))
    if exp:
        return (exp.group(0),)
    # Last resort: strip parentheticals + markdown emphasis and use the lot.
    #
    # BACKTICKS ARE STRIPPED HERE, and that is a fix rather than tidying. This
    # path is reached whenever the cell's only backticked token is a BAREWORD --
    # which the `substantive` filter above drops as a suspected parenthetical --
    # and this repo's assertion NAMES are exactly that shape: the fixtures print
    # `AssertionName: message`, so `TheGateStaysShutUntilBothItsCratesAreHome`
    # has no space and no punctuation to qualify as "substantive". Without the
    # strip, the expected substring came back as
    # "`TheGateStaysShutUntilBothItsCratesAreHome`" WITH the markdown ticks while
    # the log holds it without, so the match could never succeed and grade_leg
    # recorded `wrong-reason`. Measured on
    # t3-gate-and-door-cpp: the empty leg failed for
    # EXACTLY the right reason and was reported as failing for the wrong one --
    # which reads as a task-design problem and sends the reader to the MATRIX and
    # the fixture instead of here.
    #
    # MONOTONE, which is the whole argument for doing it in the parser: a
    # substring that matches TODAY cannot contain a backtick (the log does not),
    # so stripping ticks can only turn an impossible match into a possible one.
    # It can never flip a credited leg to uncredited.
    bare = re.sub(r"\([^)]*\)", "", cell).strip()
    bare = bare.replace("**", "").replace("`", "").strip(" .")
    return (bare,) if bare else ()


@dataclass
class MatrixRow:
    label: str  # "reference" | "empty" | the variant dir name
    expect_pass: bool
    substrings: Tuple[str, ...]


def parse_matrix(matrix_text: str) -> Dict[str, MatrixRow]:
    """Parse a ``MATRIX.md`` into ``{label -> MatrixRow}``.

    Recognizes the markdown table whose header has a *Submission* (or first)
    column and an *Overall* column plus a message column (header containing
    "message" or "substring"). Each data row is classified:
      * reference row  — first cell mentions ``reference-solutions`` or the
        folder-local ``reference``/``reference/`` form → label "reference"
      * empty row      — first cell starts with "empty"             → label "empty"
      * variant row    — first cell names a ``<dir>/`` path          → label = dir name

    The expected outcome comes from the *Overall* cell (``PASS``/``FAIL``); the
    named substrings come from the message cell. Rows that don't classify
    (prose, anti-gaming summary tables) are skipped. Tolerant by construction:
    a malformed MATRIX yields an empty/partial dict, and the caller still has
    the on-disk variant dirs as the source of truth for WHICH legs to run."""
    rows: Dict[str, MatrixRow] = {}
    header: Optional[List[str]] = None
    msg_idx: Optional[int] = None
    overall_idx: Optional[int] = None

    for raw in matrix_text.splitlines():
        line = raw.strip()
        if not line.startswith("|"):
            header = None  # a non-table line ends the current table
            continue
        cells = _split_md_row(line)
        if header is None:
            header = cells
            lowered = [c.lower() for c in cells]
            msg_idx = next(
                (i for i, c in enumerate(lowered) if "message" in c or "substring" in c),
                None,
            )
            overall_idx = next(
                (i for i, c in enumerate(lowered) if "overall" in c),
                1 if len(cells) > 1 else None,
            )
            continue
        if _is_separator_row(cells):
            continue
        if not cells or not cells[0]:
            continue
        first = cells[0]
        first_plain = first.strip("`").strip()
        # Classify the row. The reference row tolerates every recorded shape:
        # the legacy tests/reference-solutions path AND the folder-local forms
        # ("reference", "reference/", "../reference", "../reference/").
        label: Optional[str] = None
        first_noslash = first_plain.rstrip("/")
        if ("reference-solution" in first_noslash
                or first_noslash.endswith("/reference")
                or first_noslash == "reference"):
            label = "reference"
        elif first_plain.lower().startswith("empty"):
            label = "empty"
        else:
            m = _VARIANT_DIR_RE.fullmatch(first_plain) or _VARIANT_DIR_RE.search(first_plain)
            # Only treat as a variant if it looks like a bare "<name>/" submission
            # path, not the reference-solutions path (already handled above).
            if m and "/" in first and "reference-solution" not in first_plain:
                label = m.group(1)
        if label is None:
            continue
        overall = (
            cells[overall_idx] if overall_idx is not None and overall_idx < len(cells) else ""
        )
        expect_pass = "pass" in overall.lower() and "fail" not in overall.lower()
        message = cells[msg_idx] if msg_idx is not None and msg_idx < len(cells) else ""
        # Only FAIL rows carry a named assertion to match; a PASS row's message
        # cell is descriptive prose ("all four checkpoints green") with no log
        # substring to find, so it must not seed a (spurious) expected substring.
        substrings = () if expect_pass else _extract_substrings(message)
        rows[label] = MatrixRow(
            label=label,
            expect_pass=expect_pass,
            substrings=substrings,
        )
    return rows


# --------------------------------------------------------------------------- #
# Leg assembly (filesystem; pure)                                             #
# --------------------------------------------------------------------------- #


def discover_variants(discrimination_dir: Path) -> List[str]:
    """Materialized variant dir names under ``tests/discrimination/<id>/``
    (each is a submission overlay). Sorted for a stable table; non-dirs and
    dotfiles skipped."""
    if not discrimination_dir.is_dir():
        return []
    return sorted(
        p.name
        for p in discrimination_dir.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    )


def build_legs(
    repo: Path,
    task_id: str,
    *,
    reference_root: Optional[Path] = None,
    discrimination_root: Optional[Path] = None,
) -> Tuple[List[LegSpec], Optional[str]]:
    """Assemble the legs to run for ``task_id`` from on-disk artifacts + MATRIX.

    Returns ``(legs, error)``. ``error`` is set (and ``legs`` empty) when the
    task cannot be assembled — no reference solution exists (the PASS oracle is
    mandatory: a task with no reference cannot be discriminated). A missing
    discrimination dir is NOT fatal (some tasks only have reference+empty); a
    missing MATRIX.md is NOT fatal (we still run the on-disk variant dirs, but
    every variant FAIL must then carry a recorded substring or it cannot be
    credited — see ``grade_leg``)."""
    # The reference/discrimination packages resolve through the dual-layout
    # helper: folder-local ``tasks/<set>/<id>/reference|discrimination/`` first,
    # legacy ``tests/reference-solutions|discrimination/<bare id>/`` fallback.
    # An injected *_root (tests) keeps the legacy <root>/<bare id> shape.
    bare = tasks.bare_id(task_id)
    if reference_root is not None:
        ref_dir = reference_root / bare
    else:
        ref_dir = tasks.reference_dir(repo, task_id) or (
            repo / "tests" / "reference-solutions" / bare)
    if not ref_dir.is_dir():
        return [], f"no reference solution at {ref_dir} (the PASS oracle is required)"

    if discrimination_root is not None:
        disc_dir = discrimination_root / bare
    else:
        disc_dir = tasks.discrimination_dir(repo, task_id) or (
            repo / "tests" / "discrimination" / bare)
    matrix_path = disc_dir / "MATRIX.md"
    matrix = (
        parse_matrix(matrix_path.read_text(encoding="utf-8", errors="replace"))
        if matrix_path.exists()
        else {}
    )

    empty_row = matrix.get("empty")
    legs: List[LegSpec] = [
        LegSpec(kind=KIND_REFERENCE, label="reference", submission=ref_dir, expect_pass=True),
        LegSpec(
            kind=KIND_EMPTY, label="empty", submission=None, expect_pass=False,
            # If the MATRIX recorded the empty stub's failure message, verify it
            # the same way as a variant; else a plain exit-1 FAIL is sufficient
            # (the README smoke contract: empty fails on zero captured signal).
            expected_substrings=empty_row.substrings if empty_row else (),
        ),
    ]
    for name in discover_variants(disc_dir):
        row = matrix.get(name)
        legs.append(
            LegSpec(
                kind=KIND_VARIANT,
                label=name,
                submission=disc_dir / name,
                expect_pass=False,
                expected_substrings=row.substrings if row else (),
            )
        )
    return legs, None


# --------------------------------------------------------------------------- #
# from-live decision (git provenance)                                         #
# --------------------------------------------------------------------------- #


def _git_status_dirty(repo: Path, paths: Sequence[Path], *, run: Callable) -> bool:
    """True if any of ``paths`` is untracked OR has uncommitted modifications.

    Uses ``git status --porcelain -- <paths>``: any output at all means at least
    one path under the pathspec is not committed-and-clean. ``run`` is injected
    (``subprocess.run``-compatible) so the decision is unit-testable. A git
    failure is treated as DIRTY (fail safe → grade from-live, never silently
    grade stale HEAD bytes)."""
    rel = [str(p) for p in paths]
    try:
        cp = run(
            ["git", "-C", str(repo), "status", "--porcelain", "--", *rel],
            capture_output=True,
            text=True,
        )
    except Exception:
        return True
    if cp.returncode != 0:
        return True
    return bool((cp.stdout or "").strip())


def _substrate_rel_for_task(repo: Path, task_id: str) -> str:
    """``UE-projects/<dir>`` for ``task_id``'s substrate, per its own spec.

    Falls back to the default substrate when the spec can't be resolved or
    parsed — a dirtiness probe must never be the thing that breaks a run.
    """
    default = "UE-projects/CraftBenchTemplate"
    try:
        from aura_rig import graded_scratch
        spec_path = tasks.resolve_task_path(repo, task_id)
        if spec_path is None:
            return default
        name = graded_scratch.substrate_for(spec_path)
        return f"UE-projects/{name}" if name else default
    except Exception:  # noqa: BLE001 — see docstring
        return default


def decide_from_live(
    repo: Path,
    task_id: str,
    *,
    force_wip: bool,
    substrate_rel: Optional[str] = None,
    run: Callable = subprocess.run,
) -> bool:
    """Should this task grade ``--substrate-from-live`` (True) or from git HEAD?

    ``--wip`` (``force_wip``) forces from-live for every task. Otherwise a task
    grades from HEAD ONLY when it is fully committed-and-clean — its spec, its
    reference solution, its discrimination package AND the substrate's
    verifier-only tree are all tracked with no working-tree drift. If anything is
    untracked/dirty (the common mid-authoring state), grade from-live so the WIP
    fixtures/maps the verifier needs are actually present.

    Why not "just always from HEAD"? The substrate fixtures (Source/CraftBenchTests/)
    and the reference/discrimination submissions are typically authored together
    and not yet committed; from-HEAD would materialize a substrate missing them
    and produce a wrong-reason failure for the whole task.

    Why not "just always from-live"? Repo convention: a committed task SHOULD grade
    from HEAD for determinism. We only fall to from-live when forced or when the
    task genuinely isn't committed yet.

    ``substrate_rel`` defaults to the TASK'S OWN substrate, resolved from its
    spec. It used to default to ``UE-projects/CraftBenchTemplate`` regardless,
    which probed the wrong tree for a ThirdPerson task: with only
    ``UE-projects/ThirdPerson/Source/CraftBenchTests/`` dirty and everything
    else committed-and-clean this returned False, graded from HEAD, and the
    author's uncommitted fixture edit silently had no effect — the "my
    tolerance fix does nothing" trap, on exactly the iteration loop the
    ThirdPerson (tp*) tasks live in."""
    if force_wip:
        return True
    if substrate_rel is None:
        substrate_rel = _substrate_rel_for_task(repo, task_id)
    # Probe the DUAL-LAYOUT resolutions: the spec (legacy flat or folder form)
    # plus the reference/discrimination packages (folder-local first, legacy
    # tests/... fallback). A None (missing) resolution is skipped — a path that
    # doesn't exist can't be dirty, matching the old literal-path probe.
    probe = [p for p in (
        tasks.resolve_task_path(repo, task_id),
        tasks.reference_dir(repo, task_id),
        tasks.discrimination_dir(repo, task_id),
        repo / substrate_rel / "Source" / "CraftBenchTests",
    ) if p is not None]
    return _git_status_dirty(repo, probe, run=run)


# --------------------------------------------------------------------------- #
# Grading one leg (pure given a RunResult)                                    #
# --------------------------------------------------------------------------- #


def _l2_status(report: Optional[dict]) -> Optional[str]:
    if not report:
        return None
    layers = report.get("layers", {})
    l2 = layers.get("L2") or layers.get("L2I") or layers.get("L3")
    if isinstance(l2, dict):
        return l2.get("status")
    return None


def grade_leg(spec: LegSpec, result: RunResult) -> LegOutcome:
    """Decide whether ONE leg discriminated, given the verifier's RunResult.

    Rules:
      * reference  → must exit 0 (PASS). Anything else is NOT discriminated.
      * empty      → must FAIL (exit 1) AND, if the MATRIX recorded a substring
                     for it, that substring must appear in the L2 log. A
                     SUBSTRATE/SANDBOX/usage reject (exit 2/3/4), a HARNESS-ERROR
                     (exit 5/7), or a SKIPPED L2 is a wrong-reason fail, NOT
                     discrimination.
      * variant    → must FAIL (exit 1) **via its named substring** in the L2
                     log. Exit 1 alone is insufficient (the wrong checkpoint may
                     have fired). A reject/skip/crash is a wrong reason. A variant
                     with NO recorded substring (MATRIX missing the row) cannot be
                     credited — surfaced as ``no-named-assertion`` so the author
                     records one."""
    ec = result.exit_code

    if spec.kind == KIND_REFERENCE:
        if ec == EXIT_PASS:
            return LegOutcome(spec, ec, True, "pass")
        if ec in _WRONG_REASON:
            return LegOutcome(spec, ec, False, _WRONG_REASON[ec])
        if _l2_status(result.report) == "skipped":
            return LegOutcome(spec, ec, False, "skipped")
        return LegOutcome(spec, ec, False, "did-not-pass")

    # Negative legs (empty + variant): the verdict must be FAIL for the RIGHT reason.
    if ec == EXIT_PASS:
        return LegOutcome(spec, ec, False, "unexpected-pass")
    if ec in _WRONG_REASON:
        # exit 2/3/4/5/7 — never a behavior failure; the leg never reached the
        # assertion, so this FAIL is not evidence the verifier discriminates.
        return LegOutcome(spec, ec, False, _WRONG_REASON[ec])
    if _l2_status(result.report) == "skipped":
        return LegOutcome(spec, ec, False, "skipped")

    # ec == 1 (or any other non-reject failure): require the named substring(s).
    if spec.expected_substrings:
        log = result.l2_log or ""
        missing = [s for s in spec.expected_substrings if s not in log]
        if not missing:
            return LegOutcome(spec, ec, True, "fail-named")
        return LegOutcome(spec, ec, False, "wrong-reason")

    # No recorded substring.
    if spec.kind == KIND_EMPTY:
        # Empty has no gaming "reason" to name; an honest FAIL is enough (the
        # README smoke contract: empty must just FAIL on zero captured signal).
        return LegOutcome(spec, ec, True, "fail")
    # A variant with no named assertion cannot be credited — the matrix is
    # incomplete. Flag it so it isn't mistaken for a clean discrimination.
    return LegOutcome(spec, ec, False, "no-named-assertion")


# --------------------------------------------------------------------------- #
# The default subprocess seam (shells run_task.py; reads report + L2 log)     #
# --------------------------------------------------------------------------- #


def make_run_task_runner(
    *,
    py_exe: str,
    py_pre: Sequence[str],
    run_task_py: Path,
    task_spec: Path,
    ue_root: Path,
    from_live: bool,
    warm_cache: bool = False,
    keep_root: Optional[Path] = None,
    extra_args: Sequence[str] = (),
    run: Callable = subprocess.run,
) -> Callable[[Optional[Path]], RunResult]:
    """Build the runner callable that ``run_matrix`` calls once per leg.

    The returned callable takes a submission dir (``None`` => an empty throwaway
    dir is created) and returns a :class:`RunResult` with the parsed report +
    the L2 log text. Each leg runs in its OWN ``--keep-workdir`` tempdir so the
    report.json + l2 log survive long enough to be read; the dir is cleaned up
    after parsing. ``run`` is injected for tests.

    ``keep_root`` (``cb discriminate --keep``) is the OPT-IN retention mode:
    each leg's dir lands under ``keep_root/<leg-label>/`` (label = the
    submission dir's name, ``empty`` for the empty stub; deduped ``-2``/``-3``
    on collision) and is KEPT after the run — report.json, layer logs, and the
    graded workdir survive for inspection. The empty-submission throwaway tmp
    is still cleaned in all modes."""

    def _leg_dir(submission: Optional[Path]) -> Path:
        if keep_root is None:
            # .resolve() is load-bearing, not cosmetic: on a host whose %TEMP%
            # is the Windows 8.3 short form (C:\Users\SHORT~1\...), this dir
            # feeds `--out-dir <leg>/out`, which becomes the editor's
            # -ReportExportPath. A short-form report path made every L2 leg
            # return exit 3 -> "skipped" -> FAIL (2026-07-25 testbed; the same
            # root cause that scored `cb batch-eval` 0/15). Here the failure
            # would masquerade as "no discrimination" rather than an
            # environment bug, which is strictly worse.
            return Path(tempfile.mkdtemp(prefix="cb-disc-")).resolve()
        label = "empty" if submission is None else (submission.name or "leg")
        base = Path(keep_root)
        cand = base / label
        n = 2
        while cand.exists():
            cand = base / f"{label}-{n}"
            n += 1
        cand.mkdir(parents=True)
        return cand

    def _runner(submission: Optional[Path]) -> RunResult:
        leg_tmp = _leg_dir(submission)
        empty_tmp: Optional[Path] = None
        try:
            if submission is None:
                empty_tmp = Path(tempfile.mkdtemp(prefix="cb-disc-empty-"))
                sub = empty_tmp
            else:
                sub = submission
            report_json = leg_tmp / "report.json"
            cmd = [
                py_exe, *py_pre, str(run_task_py),
                "--task", str(task_spec),
                "--submission", str(sub),
                "--ue-root", str(ue_root),
                "--report-json", str(report_json),
            ]
            if warm_cache:
                # WARM: build in the shared stable slot (a per-leg --workdir would
                # force cold). Put layer outputs in leg_tmp/out via --out-dir so the
                # L2 log survives for parsing whether this leg ran warm OR cold-fell-
                # back (the deleted cold tempdir doesn't take the log with it).
                cmd += ["--warm-cache", "--out-dir", str(leg_tmp / "out")]
            else:
                cmd += ["--workdir", str(leg_tmp / "wd")]
            if from_live:
                cmd.append("--substrate-from-live")
            cmd.extend(extra_args)
            # Narrow the L1 parallel cap when commit headroom is thin. The
            # preflight is a PRE-SPEND gate, so it cannot see a mid-build
            # collapse: measured 2026-08-24, a leg that started at 10.6 GB free
            # against a 10 GB floor died with `fatal error C1060` (compiler out
            # of heap) in ENGINE headers at cap 4, and the verdict recorded was
            # `reference FAIL(skipped)` -- the SUBMISSION failing. The same task
            # passed at cap 2 in LESS wall-clock. Read per leg, because headroom
            # moves during a sweep. Fail-open: a probe error leaves the env alone.
            _env = None
            try:
                from aura_rig import stack_guard as _sg
                _env = _sg.l1_cap_env()
            except Exception:  # noqa: BLE001
                _env = None
            cp = run(cmd, capture_output=True, text=True, env=_env)
            report = _read_json(report_json)
            l2_log = _read_l2_log(report)
            stderr_tail = "\n".join((cp.stderr or "").strip().splitlines()[-5:])
            return RunResult(
                exit_code=cp.returncode,
                report=report,
                l2_log=l2_log,
                stderr_tail=stderr_tail,
            )
        finally:
            if keep_root is None:
                _rmtree(leg_tmp)
            if empty_tmp is not None:
                _rmtree(empty_tmp)

    return _runner


def _read_json(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return None


def _read_l2_log(report: Optional[dict]) -> str:
    """Read the editor stdout log(s) named in the report — where the
    ``FinishTest(Failed, "At t=…")`` message / the L2I JSON verdict — i.e. the
    named MATRIX substring — actually lands. Logs of EVERY behavioral layer are
    concatenated: a task may run both L2 and L2I, and a variant can pass one
    while failing at the other (e.g. a C++-solve variant of a ``-bp`` task
    passes L2 but fails the L2I blueprint gate), so the named assertion must be
    findable whichever layer's log carries it."""
    if not report:
        return ""
    parts: List[str] = []
    for key in ("L2", "L3", "L2I"):
        layer = report.get("layers", {}).get(key)
        if isinstance(layer, dict) and layer.get("log"):
            try:
                parts.append(Path(layer["log"]).read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
    return "\n".join(parts)


def _rmtree(path: Path) -> None:
    import shutil

    shutil.rmtree(path, ignore_errors=True)


# --------------------------------------------------------------------------- #
# Orchestration (pure given the runner seam)                                  #
# --------------------------------------------------------------------------- #


def run_matrix(
    legs: Sequence[LegSpec],
    runner: Callable[[Optional[Path]], RunResult],
    task_id: str,
) -> TaskOutcome:
    """Run every leg through the (injected) runner and grade each. Pure aside
    from the runner's side effects, so unit tests mock ``runner`` and assert the
    aggregation + wrong-reason rules with no editor."""
    outcome = TaskOutcome(task_id=task_id)
    for spec in legs:
        result = runner(spec.submission)
        outcome.legs.append(grade_leg(spec, result))
    return outcome


# --------------------------------------------------------------------------- #
# Set / id expansion (reuse tasks.py)                                         #
# --------------------------------------------------------------------------- #


def expand_targets(repo: Path, target: str) -> Tuple[List[str], Optional[str]]:
    """Resolve a CLI target into a list of task ids.

    ``target`` may be:
      * a task id (root or unique subdir match)  → ``[id]``
      * a set-qualified id ``set/id``             → ``[set/id]``
      * a set name (a ``tasks/<set>/`` dir)       → every task in that set,
        as set-qualified ids ``set/<id>`` (so they resolve unambiguously).

    Returns ``(ids, error)``; ``error`` is set when nothing matches."""
    discovered = tasks.discover(repo)
    # A bare set name?
    if target in discovered and "/" not in target and target != "root":
        return [f"{target}/{t.id}" for t in discovered[target]], None
    if target == "root" and "root" in discovered:
        return [t.id for t in discovered["root"]], None
    # Else treat as a task id (set-qualified or unique).
    path = tasks.resolve_task_path(repo, target)
    if path is not None:
        return [target], None
    return [], (
        f"no task or set matched {target!r} under tasks/ — use a task id, a "
        f"set-qualified 'set/id', or a set name ({', '.join(sorted(discovered))})"
    )


# --------------------------------------------------------------------------- #
# Table rendering                                                             #
# --------------------------------------------------------------------------- #


def render_table(outcomes: Sequence[TaskOutcome]) -> str:
    """A compact per-task discrimination table.

    One block per task: a header line + one line per leg + the overall
    discriminated verdict. Wrong-reason cells carry a parenthetical so a
    pass-everything/fail-everything trap is impossible to miss."""
    lines: List[str] = []
    for oc in outcomes:
        lines.append("")
        if oc.error:
            lines.append(f"task {oc.task_id}: SKIPPED — {oc.error}")
            lines.append(f"  discriminated: NO")
            continue
        verdict = "YES" if oc.discriminated else "NO"
        lines.append(f"task {oc.task_id}    discriminated: {verdict}")
        width = max((len(leg.spec.label) for leg in oc.legs), default=9)
        for leg in oc.legs:
            mark = "ok " if leg.discriminated else "BAD"
            lines.append(f"  [{mark}] {leg.spec.label:<{width}}  {leg.cell}")
    # Summary footer.
    total = len(outcomes)
    yes = sum(1 for o in outcomes if o.discriminated)
    lines.append("")
    lines.append(f"discriminated {yes}/{total} task(s)")
    return "\n".join(lines).lstrip("\n")


def overall_exit_code(outcomes: Sequence[TaskOutcome]) -> int:
    """0 iff every task discriminated; 1 otherwise (CI gate)."""
    return 0 if outcomes and all(o.discriminated for o in outcomes) else 1

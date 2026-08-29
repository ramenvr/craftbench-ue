#!/usr/bin/env python3
"""CraftBench high-tier concept-coverage report.

Joins each task spec's PRIMARY concept against the concept catalogue
(``tools/coverage/concepts.csv``) and reports how much of the
**in_scope, high-tier** concept catalogue the current task set covers.

This is a pure-stdlib reporting tool (no third-party deps). It does NOT
build the UE project, run PIE, or call any verifier layer; it only reads
markdown + CSV. It is the SC-007 / v1.0 task-set-target instrument: the
spec relaxes SC-007 at v1.0 to "the subset of high-tier concepts covered
by ``concept-1``", and this tool tells you what that subset actually is.

------------------------------------------------------------------------
How a task declares its primary concept (discovered, not assumed)
------------------------------------------------------------------------
Task specs are markdown with normative H2 sections (the same join-key
convention as ``tools/verify-single/run_task.py``: a line is an H2 iff it
``startswith("## ")`` and not ``startswith("### ")``; the heading text is
``line[3:].strip()``). The primary concept lives in the ``## Primary
concept`` section. Its FIRST list item carries the concept_id(s) as
backtick-quoted kebab-case tokens, e.g.::

    ## Primary concept

    - `ps-actors` — Actors
      (https://dev.epicgames.com/.../actors-in-unreal-engine)

Most tasks list a single id. A handful (e.g. ``tasks/gp-flight-mode.md``)
list two co-primary ids joined by ``+`` on the same first bullet::

    - `gas-abilities` + `ps-character-movement` — GAS ability driving a ...

We treat EVERY backtick-quoted token on that first bullet as a referenced
concept (first listed is the nominal primary, but for coverage both count).
We deliberately read ONLY the first list item of the section, so inline
``backtick`` mentions in the rationale prose below it (e.g. ``AActor``) do
not pollute the parse.

Ambiguities / known caveats (see also ``tasks/*/README.md``):
  * Some tasks use an *advisory placeholder* concept_id that is not in the
    catalogue at all (e.g. ``level-gated-checks-no-framework``,
    ``hitresult-field-semantics``, ``project-onboarding-summary``,
    ``anim-state-machine-transition``). These never join to a high-tier
    catalogue row; they are reported under ``unmatched_referenced`` rather
    than silently dropped.
  * Some tasks intentionally anchor to a *medium*-tier in_scope concept
    (the materials tasks anchor to ``material-instance-dynamic`` because
    the high-tier catalogue has zero material entries). Medium concepts do
    not count toward high-tier coverage by construction.

------------------------------------------------------------------------
CSV schema (discovered)
------------------------------------------------------------------------
``concepts.csv`` columns: ``concept_id, concept_name, doc_url, doc_section,
doc_depth, forum_mentions_12mo, weight_tier, in_scope, capability_bucket,
notes``. ``weight_tier`` is one of ``high|medium|low|n/a``; ``in_scope`` is
``yes|no``. The high-tier in_scope universe is the coverage denominator.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Dict, List

# ---------------------------------------------------------------------------
# Repo-relative defaults (this file lives at tools/coverage/coverage.py).
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONCEPTS_CSV = _REPO_ROOT / "tools" / "coverage" / "concepts.csv"
DEFAULT_TASKS_DIR = _REPO_ROOT / "tasks"

# Reusable filter constants (kept explicit so a catalogue schema change is a
# one-line edit here, not a scavenger hunt).
HIGH_TIER = "high"
IN_SCOPE_YES = "yes"


# Concept ids inside the FIRST Primary-concept bullet are backtick-quoted
# kebab-case tokens. We capture every such token on that line so a `a` + `b`
# co-primary bullet yields both.
_BACKTICK_ID = "`"


# ---------------------------------------------------------------------------
# Markdown H2 split — byte-for-byte the convention in run_task.py so the two
# tools never disagree on what an H2 section is.
# ---------------------------------------------------------------------------
def split_h2_sections(markdown: str) -> Dict[str, str]:
    """Return {H2 heading text -> raw body up to the next H2}.

    Mirrors ``tools/verify-single/run_task.py::_split_h2_sections``: a line
    is an H2 iff it ``startswith("## ")`` and not ``startswith("### ")``.
    """
    out: Dict[str, str] = {}
    current_heading = None
    current_lines: List[str] = []
    for line in markdown.splitlines():
        if line.startswith("## ") and not line.startswith("### "):
            if current_heading is not None:
                out[current_heading] = "\n".join(current_lines).strip()
            current_heading = line[3:].strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_heading is not None:
        out[current_heading] = "\n".join(current_lines).strip()
    return out


def _backtick_tokens(line: str) -> List[str]:
    """Return the backtick-quoted tokens on a single line, in order.

    ``- `gas-abilities` + `ps-character-movement` — ...`` -> the two ids.
    Naive paired-backtick scan (no nesting in these specs); preserves order
    and de-dupes within the line while keeping first occurrence.
    """
    tokens: List[str] = []
    parts = line.split(_BACKTICK_ID)
    # Odd indices are the contents between matched backticks.
    for i in range(1, len(parts), 2):
        tok = parts[i].strip()
        if tok and tok not in tokens:
            tokens.append(tok)
    return tokens


def parse_primary_concept_ids(task_path: Path) -> List[str]:
    """Extract the referenced concept_id(s) from a task spec's first
    ``## Primary concept`` bullet.

    Returns an ordered, de-duplicated list (possibly empty if the section is
    absent or has no backtick token in its first list item). Never raises on
    a malformed/absent section.
    """
    try:
        raw = task_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    section = split_h2_sections(raw).get("Primary concept", "")
    if not section:
        return []
    # The first list item (a line whose first non-space char is '-' or '*').
    for line in section.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(("- ", "* ")):
            return _backtick_tokens(line)
    # Fall back: no bullet found, but the section may put the id on its first
    # non-empty line. Be conservative and read backticks there.
    for line in section.splitlines():
        if line.strip():
            return _backtick_tokens(line)
    return []


# ---------------------------------------------------------------------------
# concepts.csv loader
# ---------------------------------------------------------------------------
def load_high_tier_in_scope_concepts(csv_path: Path) -> Dict[str, str]:
    """Return {concept_id -> concept_name} for every in_scope, high-tier row.

    Tier/scope comparisons are case- and whitespace-insensitive.
    """
    out: Dict[str, str] = {}
    with csv_path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            tier = (row.get("weight_tier") or "").strip().lower()
            scope = (row.get("in_scope") or "").strip().lower()
            if tier == HIGH_TIER and scope == IN_SCOPE_YES:
                cid = (row.get("concept_id") or "").strip()
                if cid:
                    out[cid] = (row.get("concept_name") or "").strip()
    return out


def load_all_concept_ids(csv_path: Path) -> set:
    """Return the set of ALL concept_ids in the catalogue (any tier/scope).

    Used to distinguish a 'referenced a real concept but it isn't high-tier
    in_scope' id from a true advisory placeholder that is not in the
    catalogue at all.
    """
    out: set = set()
    with csv_path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            cid = (row.get("concept_id") or "").strip()
            if cid:
                out.add(cid)
    return out


# ---------------------------------------------------------------------------
# Per-concept doc_section loader
# ---------------------------------------------------------------------------
def load_concept_sections(csv_path: Path) -> Dict[str, str]:
    """Return ``{concept_id -> doc_section}`` for high-tier in_scope rows."""
    out: Dict[str, str] = {}
    with csv_path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            tier = (row.get("weight_tier") or "").strip().lower()
            scope = (row.get("in_scope") or "").strip().lower()
            if tier == HIGH_TIER and scope == IN_SCOPE_YES:
                cid = (row.get("concept_id") or "").strip()
                if cid:
                    out[cid] = (row.get("doc_section") or "?").strip()
    return out


# ---------------------------------------------------------------------------
# Coverage join
# ---------------------------------------------------------------------------
# Non-spec markdown that lives in the tasks/ tree. CATALOG.md is the per-task
# TLDR index (it has no ``## Primary concept`` and is not a task); counting it
# inflated task_count by one (69 instead of the honest 68 — fixed 2026-06-11).
# ``task.md`` guards against a folder-form spec misplaced DIRECTLY in a root/
# set dir (it belongs one level down, at ``tasks/<set>/<id>/task.md``).
# ``preamble.md`` is the harness's central prompt-preamble contract
# (tasks/PREAMBLE.md), not a spec.
_NON_SPEC_NAMES = frozenset({"readme.md", "catalog.md", "task.md",
                             "preamble.md"})

# The spec filename inside a folder-form task dir (the 2026-07 dual layout:
# ``tasks/<set>/<id>/task.md`` beside its reference/ + discrimination/ dirs).
_FOLDER_SPEC_NAME = "task.md"


def task_id_for(path: Path) -> str:
    """The bare task id a spec path denotes: the parent-dir name for the
    folder form (``.../<id>/task.md``), else the file stem (``.../<id>.md``).

    Mirrors ``tools/run-agent/aura_rig/tasks.py::task_id_for`` (this tool is
    pure-stdlib and deliberately does not import across tool trees)."""
    p = Path(path)
    return p.parent.name if p.name == _FOLDER_SPEC_NAME else p.stem


def _is_spec_md(path: Path) -> bool:
    """True only for a LEGACY FLAT spec (``tasks/<set>/<id>.md``).

    Two filters, and the second one is the load-bearing half.

    The name denylist alone is **fail-open**: it admits any markdown whose
    filename nobody thought to exclude, and `tasks/README.md` is explicit that
    "enumerators select ``*/task.md``, never ``rglob(*.md)``" — a coordination
    or scratch `.md` in a set folder is NOT a spec. Found 2026-08-08 when
    `tasks/bp-g2/QUEUE.md` (a per-set owner queue, since moved to
    the g2 task queue) was discovered as a task
    and inflated the generated CATALOG block to "36 task specs · 1 paper".
    A phantom spec is the expensive kind of wrong: it silently moves the
    benchmark's own advertised task count, and the count is what `cb lint`
    then enforces against four prose anchors.

    So a flat spec must also LOOK like one: v2 front matter carrying an ``id:``
    key, or the legacy H2 metadata the parser still falls back to. Content is
    the honest test — a denylist needs editing every time someone adds a new
    kind of note, and it fails toward counting things."""
    name = path.name.lower()
    if name in _NON_SPEC_NAMES or name.endswith(".note.md"):
        return False
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:2048]
    except OSError:
        return False
    if head.lstrip().startswith("---") and re.search(r"^id:\s*\S", head, re.M):
        return True  # v2 front matter
    return bool(re.search(r"^##\s+Prompt given to the agent\s*$", head, re.M))


def _iter_task_files(tasks_dir: Path):
    """Yield every task spec under ``tasks_dir``, both layouts: flat
    ``tasks/*.md`` + ``tasks/<set>/*.md`` (minus README.md / CATALOG.md /
    NOTE files / a stray ``task.md``) plus folder-form
    ``tasks/<set>/<id>/task.md``. Deliberately NOT a recursive rglob: a
    folder-form task dir co-locates non-spec markdown (discrimination/
    MATRIX.md, notes.md, reference/ READMEs) that must never count as specs."""
    specs = [p for p in tasks_dir.glob("*.md") if _is_spec_md(p)]
    specs += [p for p in tasks_dir.glob("*/*.md") if _is_spec_md(p)]
    specs += list(tasks_dir.glob(f"*/*/{_FOLDER_SPEC_NAME}"))
    yield from sorted(specs)


def compute_coverage(
    concepts_csv: Path,
    tasks_dir: Path,
    sections: Dict[str, str] | None = None,
) -> dict:
    """Join task primary-concepts against the high-tier in_scope catalogue.

    Returns a JSON-serializable dict::

        {
          "total_high_tier": int,        # denominator
          "covered_count": int,          # numerator
          "coverage_pct": float,         # covered/total * 100
          "covered": {cid: [task_id,...] sorted},   # only covered cids
          "uncovered": [cid, ...] sorted,
          "all_high_tier": {cid: name},  # full universe w/ display names
          "unmatched_referenced": {cid: [task_id,...]},  # ids no high-tier row
          "task_count": int,
        }
    """
    high = load_high_tier_in_scope_concepts(concepts_csv)
    all_ids = load_all_concept_ids(concepts_csv)

    # cid -> set of task_ids that reference it (any backtick id on bullet 1).
    refs: Dict[str, set] = {}
    unmatched: Dict[str, set] = {}
    task_count = 0
    for task_path in _iter_task_files(tasks_dir):
        task_count += 1
        task_id = task_id_for(task_path)
        for cid in parse_primary_concept_ids(task_path):
            if cid in high:
                refs.setdefault(cid, set()).add(task_id)
            else:
                # Referenced but not a high-tier in_scope concept. Surface it
                # so authors can see medium-anchors and advisory placeholders.
                unmatched.setdefault(cid, set()).add(task_id)

    covered = {cid: sorted(tasks) for cid, tasks in refs.items()}
    uncovered = sorted(cid for cid in high if cid not in refs)
    total = len(high)
    covered_count = len(covered)
    pct = round(100.0 * covered_count / total, 1) if total else 0.0

    sections = sections or {}

    # Per-doc-section rollup over the high-tier in_scope universe.
    by_section: Dict[str, dict] = {}
    for cid in high:
        sec = sections.get(cid, "?")
        bucket = by_section.setdefault(sec, {"total": 0, "referenced": 0})
        bucket["total"] += 1
        if cid in refs:
            bucket["referenced"] += 1

    return {
        "total_high_tier": total,
        "covered_count": covered_count,
        "coverage_pct": pct,
        "covered": dict(sorted(covered.items())),
        "uncovered": uncovered,
        "all_high_tier": dict(sorted(high.items())),
        "unmatched_referenced": {cid: sorted(t) for cid, t in sorted(unmatched.items())},
        "task_count": task_count,
        "by_doc_section": dict(sorted(by_section.items())),
    }


# ---------------------------------------------------------------------------
# Human-readable rendering
# ---------------------------------------------------------------------------
def render_table(result: dict) -> str:
    """Render the coverage result as a human-readable text report."""
    lines: List[str] = []
    total = result["total_high_tier"]
    covered = result["covered_count"]
    pct = result["coverage_pct"]

    lines.append("CraftBench high-tier concept coverage")
    lines.append("=" * 52)
    lines.append(
        f"Covered {covered} / {total} in_scope high-tier concepts "
        f"({pct:.1f}%) across {result['task_count']} task specs."
    )

    lines.append("")
    lines.append("Coverage by UE doc-section (referenced of total):")
    sec_rows = result.get("by_doc_section", {})
    width = max((len(s) for s in sec_rows), default=10)
    for sec, b in sec_rows.items():
        lines.append(f"  {sec:<{width}}  {b['referenced']:>2} of {b['total']:>2}")
    lines.append("")

    # (a) covered concepts + their referencing tasks
    lines.append(f"COVERED high-tier concepts ({covered}):")
    if result["covered"]:
        names = result["all_high_tier"]
        width = max(len(c) for c in result["covered"])
        for cid in sorted(result["covered"]):
            tasks = ", ".join(result["covered"][cid])
            label = names.get(cid, "")
            lines.append(f"  {cid:<{width}}  [{label}]")
            lines.append(f"      <- {tasks}")
    else:
        lines.append("  (none)")
    lines.append("")

    # (b) uncovered set
    uncov = result["uncovered"]
    lines.append(f"UNCOVERED high-tier concepts ({len(uncov)}):")
    if uncov:
        names = result["all_high_tier"]
        for cid in uncov:
            lines.append(f"  {cid}  [{names.get(cid, '')}]")
    else:
        lines.append("  (none — full high-tier coverage)")
    lines.append("")

    # transparency: referenced ids that are NOT high-tier in_scope concepts
    unmatched = result["unmatched_referenced"]
    if unmatched:
        lines.append(
            f"REFERENCED but not high-tier in_scope ({len(unmatched)}) "
            "— medium-tier anchors / advisory placeholders:"
        )
        for cid in sorted(unmatched):
            tasks = ", ".join(unmatched[cid])
            lines.append(f"  {cid}  <- {tasks}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv=None) -> int:
    # The report prints em-dashes. On a Windows console defaulting to cp1252
    # those render as mojibake, which on the one validated platform makes the
    # tool look broken. Best-effort: a stream that cannot be reconfigured
    # (a pipe, a captured stdout in a test) is left exactly as it was.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError, ValueError):
        pass

    parser = argparse.ArgumentParser(
        description=(
            "Report CraftBench high-tier concept coverage: join each task "
            "spec's primary concept against the concept catalogue."
        )
    )
    parser.add_argument(
        "--concepts",
        type=Path,
        default=DEFAULT_CONCEPTS_CSV,
        help="Path to concepts.csv (default: tools/coverage/concepts.csv).",
    )
    parser.add_argument(
        "--tasks",
        type=Path,
        default=DEFAULT_TASKS_DIR,
        help="Path to the tasks/ directory (default: repo tasks/).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit ONLY the machine-readable JSON summary to stdout.",
    )
    args = parser.parse_args(argv)

    if not args.concepts.is_file():
        print(f"error: concepts CSV not found: {args.concepts}", file=sys.stderr)
        return 2
    if not args.tasks.is_dir():
        print(f"error: tasks dir not found: {args.tasks}", file=sys.stderr)
        return 2

    sections = load_concept_sections(args.concepts)
    result = compute_coverage(
        concepts_csv=args.concepts,
        tasks_dir=args.tasks,
        sections=sections,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(render_table(result))
        print("--- JSON summary ---")
        print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Repo-level inventory checks: the hand-maintained docs vs what git actually tracks.

``docs/MAPS.md`` and ``tasks/CATALOG.md`` each restate facts that
are **mechanically derivable** — how many maps are committed, which maps exist,
how many task specs there are. Restating them by hand means they drift, and two
of the three are load-bearing: `the repo conventions` is auto-loaded into every agent's
context, and ``docs/MAPS.md`` is where an author looks to find out whether a map
already exists.

They had all drifted by 2026-07-25: the committed
``t2-homing-projectile/L_HomingProjectile.umap`` had no MAPS.md row and MAPS.md
still claimed "14 committed binaries" against a real 15, while the repo conventions
repeated the same 14. Nothing checked either: both were hand-maintained
prose that no gate read.

Two rule families, deliberately different in kind:

* **Membership** (the load-bearing half) — every committed map under a
  substrate's ``Content/Maps/`` must be *named* somewhere in MAPS.md, and every
  task spec must be named in CATALOG.md. Robust: map names and task ids are
  distinctive tokens, so this survives any amount of prose restructuring. The
  match is ANCHORED (``_mentions``), not a raw substring — see that function
  for why a prefix-shaped id otherwise reads "present" off a longer id's row,
  and why ``\b`` does not fix it for hyphenated ids.
* **Anchored counts** — a count claim is checked only where the checker can
  find its anchor phrase. A doc that rewords past the anchor loses the count
  check but keeps membership, so this never silently becomes the only guard.

Dependency-free and standalone-runnable, like the rest of this tree.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

MAPS_DOC = Path("docs") / "MAPS.md"
CATALOG_DOC = Path("tasks") / "CATALOG.md"
DOCS_INDEX_DOC = Path("docs") / "DOCS_INDEX.md"


@dataclass
class InventoryFinding:
    rule: str
    severity: str          # "error" | "warn"
    message: str


# --------------------------------------------------------------------------- #
# Ground truth (git is the authority — "committed binary is the only map source")
# --------------------------------------------------------------------------- #

def tracked_files(repo_root: Path, pattern: str) -> Optional[List[str]]:
    """``git ls-files <pattern>`` as repo-relative POSIX paths, or None if git
    cannot answer (no repo / no git on PATH) — callers degrade to a WARN."""
    try:
        cp = subprocess.run(
            ["git", "ls-files", pattern],
            cwd=str(repo_root), capture_output=True, text=True,
            errors="replace", timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if cp.returncode != 0:
        return None
    return [ln.strip() for ln in (cp.stdout or "").splitlines() if ln.strip()]


def committed_task_maps(repo_root: Path) -> Optional[Dict[str, List[str]]]:
    """``{substrate_dir: [map stem, …]}`` for committed ``.umap``s under each
    substrate's ``Content/Maps/``.

    Scoped to ``Content/Maps/`` on purpose: that is the task/probe map root. A
    substrate's own shipped levels (ThirdPerson's ``Lvl_ThirdPerson`` and its
    ``Variant_*`` maps) live elsewhere in ``Content/`` and are not inventory.
    """
    # List every tracked .umap and filter HERE rather than in the pathspec:
    # git's `**/` does not match zero directories, so
    # `UE-projects/*/Content/Maps/**/*.umap` silently returns only the
    # per-task-FOLDERED maps and misses every pre-migration flat one (8 of 16
    # when this was written) — a checker that under-counts is worse than none.
    tracked = tracked_files(repo_root, "*.umap")
    if tracked is None:
        return None
    out: Dict[str, List[str]] = {}
    for rel in tracked:
        parts = rel.split("/")
        # UE-projects/<substrate>/Content/Maps/[<task-id>/]<L_Name>.umap
        if len(parts) < 5 or parts[0] != "UE-projects":
            continue
        if parts[2] != "Content" or parts[3] != "Maps":
            continue
        out.setdefault(parts[1], []).append(Path(rel).stem)
    return {k: sorted(v) for k, v in sorted(out.items())}


def task_spec_ids(repo_root: Path) -> List[str]:
    """Task ids on disk, via tasklint's discovery (THE spec-detection rule)."""
    import tasklint
    specs = tasklint.discover_specs(repo_root / "tasks")
    ids = []
    for p in specs:
        ids.append(p.parent.name if p.name == "task.md" else p.stem)
    return sorted(ids)


# --------------------------------------------------------------------------- #
# Anchored count claims                                                        #
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class CountClaim:
    """One prose number the checker knows how to verify.

    ``pattern`` must capture the claimed number in group 1 (plus, optionally, a
    substrate dir name in a group named ``substrate``). ``truth`` receives the
    match and returns the real number, or None to skip.
    """
    rule: str
    doc: Path
    pattern: str
    truth: Callable
    what: str
    #: True = "verify it IF present". The docs whose whole job is to state the
    #: inventory (MAPS/CATALOG) must carry their count, so a missing
    #: anchor there is a WARN. A skill may legitimately not quote one, and
    #: warning about that trains readers to ignore the rule.
    optional: bool = False


def _maps_truth_for_substrate(repo_root: Path, m: "re.Match") -> Optional[int]:
    maps = committed_task_maps(repo_root)
    if maps is None:
        return None
    return len(maps.get(m.group("substrate"), []))


def _maps_truth_total(repo_root: Path, _m: "re.Match") -> Optional[int]:
    maps = committed_task_maps(repo_root)
    if maps is None:
        return None
    return sum(len(v) for v in maps.values())


def _tasks_truth(repo_root: Path, _m: "re.Match") -> Optional[int]:
    return len(task_spec_ids(repo_root))


COUNT_CLAIMS: Sequence[CountClaim] = (
    # docs/MAPS.md:30 — "14 committed binaries under `UE-projects/X/Content/Maps/`"
    CountClaim(
        "inventory-maps-count", MAPS_DOC,
        r"(\d+)\s+committed\s+binaries\s+under\s+`?UE-projects/(?P<substrate>[A-Za-z0-9_]+)/Content/Maps/?`?",
        _maps_truth_for_substrate, "committed maps under that substrate"),
    # tasks/CATALOG.md — "**117 task specs** in four directories".
    # A second claim here used to anchor on "the <N>-task tree" — a different
    # phrasing of the same number in the same file. CATALOG states it once now,
    # so that anchor could only ever report "reworded?" and never a real drift.
    CountClaim(
        "inventory-task-count", CATALOG_DOC,
        r"(\d+)\s+task specs\b",
        _tasks_truth, "task specs on disk"),
    # docs/DOCS_INDEX.md — "the task tree holds **63 tasks** in three baskets".
    # Added 2026-08-14 after code review found it still claiming 60 / python 9,
    # three tasks stale, with NO gate covering it: the doc that tells a reader
    # where everything is was the one surface nobody checked. optional=True so a
    # future rename of the index cannot turn a missing file into a hard error.
    CountClaim(
        "inventory-task-count", DOCS_INDEX_DOC,
        r"task tree holds\s+(?:\*\*)?(\d+)\s+tasks",
        _tasks_truth, "task specs on disk", optional=True),
)


# --------------------------------------------------------------------------- #
# The checks                                                                   #
# --------------------------------------------------------------------------- #

def _read(repo_root: Path, rel: Path) -> Optional[str]:
    try:
        return (repo_root / rel).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


#: Characters that may appear INSIDE a task id or a map stem. A match is only a
#: real mention when neither neighbour is one of these.
_ID_CHARS = "0-9A-Za-z_-"


def _mentions(doc: str, token: str) -> bool:
    """True iff ``doc`` names ``token`` as a whole identifier.

    **Why not ``in``, and why not ``\\b``.** The membership rules exist to
    catch a spec/map that no doc names; both failure directions are silent, so
    the boundary rule has to be exactly right for the format being searched.

    * A RAW SUBSTRING (``token in doc``) — what the CATALOG check did until
      2026-08-08 — reads a SHORTER id's row off a LONGER id's row: while
      ``gp-glide-stamina`` and ``gp-glide-stamina-bp`` coexisted (2026-08-03 →
      the 2026-08-06 ``-cpp`` rename), ``gp-glide-stamina`` scored "present"
      purely because ``gp-glide-stamina-bp`` was listed. The rename dissolved
      that INSTANCE; nothing stopped the next prefix-shaped id from re-opening
      it, which is why the durable fix is here and not in a naming convention.
    * A NAIVE ``\\b`` does not fix it. ``\\b`` sits between a word char and a
      non-word char, and ``-`` is a NON-word char — so ``\\bgp-glide-stamina\\b``
      still matches inside ``gp-glide-stamina-bp`` (the boundary lands between
      the ``a`` and the ``-``). Hyphenated ids need the hyphen treated as an
      id-INTERNAL character, which is what the lookarounds below do.

    Deliberately a token match against the whole document rather than a
    markdown-table-cell match: ids appear backticked in table cells, backticked
    in prose, and bare inside paths (``tasks/bp-g2/<id>/task.md``). All three
    are legitimate "this doc names it", and every real delimiter around them
    (backtick, pipe, comma, slash, space, period) is outside ``_ID_CHARS``.
    """
    return re.search(
        rf"(?<![{_ID_CHARS}]){re.escape(token)}(?![{_ID_CHARS}])", doc
    ) is not None


def check_map_membership(repo_root: Path) -> List[InventoryFinding]:
    """Every committed task map is named in MAPS.md, and vice versa."""
    out: List[InventoryFinding] = []
    maps = committed_task_maps(repo_root)
    if maps is None:
        return [InventoryFinding("inventory-maps", "warn",
                                 "git could not list committed maps — inventory unchecked")]
    doc = _read(repo_root, MAPS_DOC)
    if doc is None:
        return [InventoryFinding("inventory-maps", "warn", f"{MAPS_DOC} not readable")]
    for substrate, stems in maps.items():
        for stem in stems:
            # Map stems (`L_Foo`) carry no hyphens today, so `\b` happened to
            # be right for them — but the same anchored rule is used so a
            # hyphenated map name can never re-open the id bug one dir over.
            if not _mentions(doc, stem):
                out.append(InventoryFinding(
                    "inventory-maps", "error",
                    f"{MAPS_DOC}: committed map {stem} "
                    f"(UE-projects/{substrate}/Content/Maps/) has no row — "
                    f"an author reading MAPS.md cannot tell it exists"))
    # Stale rows: a `L_Name` in an inventory TABLE that git no longer tracks.
    # Scoped to table rows on purpose — prose legitimately names deleted maps
    # ("`L_GasLaunch` + `L_GasLaunchControl` were deleted 2026-07-21 with the
    # retired task"), and flagging a retirement note as drift would train
    # authors to ignore this rule.
    committed = {s for stems in maps.values() for s in stems}
    rows = [ln for ln in doc.splitlines() if ln.lstrip().startswith("|")]
    for stem in sorted({s for ln in rows
                        for s in re.findall(r"`(L_[A-Za-z0-9_]+)`", ln)}):
        if stem not in committed:
            out.append(InventoryFinding(
                "inventory-maps", "error",
                f"{MAPS_DOC}: has a table row for map {stem} but git tracks no "
                f"such Content/Maps/**/{stem}.umap (retired without a doc sweep?)"))
    return out


def check_task_membership(repo_root: Path) -> List[InventoryFinding]:
    """Every task spec on disk is named in CATALOG.md.

    The id must be named as a WHOLE identifier (``_mentions``) — a raw
    substring test let a prefix-shaped id read "present" off a longer id's row.
    """
    doc = _read(repo_root, CATALOG_DOC)
    if doc is None:
        return [InventoryFinding("inventory-tasks", "warn", f"{CATALOG_DOC} not readable")]
    out: List[InventoryFinding] = []
    for task_id in task_spec_ids(repo_root):
        if not _mentions(doc, task_id):
            out.append(InventoryFinding(
                "inventory-tasks", "error",
                f"{CATALOG_DOC}: task {task_id} exists on disk but is not listed"))
    return out


def check_count_claims(repo_root: Path) -> List[InventoryFinding]:
    """Verify each prose count the checker can anchor. An unanchored claim is
    reported as a WARN so a reworded doc is visible, not silently unchecked."""
    out: List[InventoryFinding] = []
    for claim in COUNT_CLAIMS:
        doc = _read(repo_root, claim.doc)
        if doc is None:
            continue
        matches = list(re.finditer(claim.pattern, doc))
        if not matches:
            if not claim.optional:
                out.append(InventoryFinding(
                    claim.rule, "warn",
                    f"{claim.doc}: no '{claim.what}' count claim found where one is "
                    f"expected — reworded? (count unchecked; membership still is)"))
            continue
        for m in matches:
            truth = claim.truth(repo_root, m)
            if truth is None:
                continue
            claimed = int(m.group(1))
            if claimed != truth:
                out.append(InventoryFinding(
                    claim.rule, "error",
                    f"{claim.doc}: claims {claimed} {claim.what}, real count is "
                    f"{truth} — fix the line"))
    return out


_STALE_STATUS_MARKERS = ("wired, not validated", "PENDING")


# check_matrix_status_staleness was removed for the open-source release. It
# cross-checked each MATRIX.md against ROADMAP.md's dated status table, and
# ROADMAP.md is not part of this release. Re-pointing it at tasks/CATALOG.md
# would be circular: CATALOG.md names discrimination/MATRIX.md as the status
# authority. A rule whose input is gone returns [] and guards nothing, which
# reads as a green that measured something -- so it is gone, not disarmed.

def check_repo_inventory(repo_root: Path) -> List[InventoryFinding]:
    """All repo-level inventory findings, in report order."""
    return [*check_map_membership(repo_root),
            *check_task_membership(repo_root),
            *check_count_claims(repo_root),]


def render(findings: Sequence[InventoryFinding]) -> str:
    lines = []
    for f in findings:
        tag = "ERROR" if f.severity == "error" else "WARN "
        lines.append(f"  {tag} [{f.rule}] {f.message}")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    found = check_repo_inventory(root)
    print(render(found) or "  inventory OK")
    raise SystemExit(1 if any(f.severity == "error" for f in found) else 0)

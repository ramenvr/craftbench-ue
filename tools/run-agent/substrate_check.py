"""Substrate-integrity pre-flight.

Before workspace build + agent dispatch, verify that the substrate's tracked
files match the current git HEAD — limited to the subtrees that actually
affect the eval. Catches auto-saves from a running UE editor (e.g. someone
accidentally mutating L_SanityTask.umap) and other working-tree drift that
would silently invalidate the run before the verifier ever sees the agent's
submission.

Filters applied to git porcelain output:

- Untracked ("??") entries are dropped — they're typically legitimate build
  artefacts that pre-date or run after the smoke.
- Anything under SKIP_SUBTREES is dropped — these subtrees are also skipped
  by workspace.py (they regenerate on UE project open). Build artefacts in
  Intermediate/, Saved/, Binaries/, DerivedDataCache/ would otherwise drown
  out the signal whenever a UE build has run.

So a dirty entry that survives the filter is, by construction, a change in
a path the verifier WILL see — a source file, a content asset, the project
descriptor, an engine config. Those are the changes that matter.

Gracefully degrades when the substrate isn't in a git repo (returns empty
list) — local sandboxes shouldn't break the harness.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List


# Subtrees that are either skipped entirely by workspace.py (build cache:
# Binaries/Intermediate/DerivedDataCache/Saved) OR are routinely-rewritten
# active-dev directories that aren't part of the eval signal (Plugins is the
# user's working area for Aura today; add a per-substrate override later if
# Plugins ever becomes task-relevant).
SKIP_SUBTREES = ("Binaries", "Intermediate", "DerivedDataCache", "Saved", "Plugins")

# File suffixes that are NOT part of the eval signal. The .uproject file is
# rewritten on every project open (timestamp / plugin-list ordering). Markdown
# docs (README.md and other markdown) are never built, graded, or agent-writable —
# editing substrate docs (e.g. a UE 5.7->5.8 version bump) must not block a run.
SKIP_FILE_SUFFIXES = (".uproject", ".md")


def porcelain_path(line: str) -> str:
    """The repo-root-relative path from one ``git status --porcelain`` line
    (2-char status + space + path; renames keep only the destination).
    The single parser for the gate's dirty lines — fairness's crash-recovery
    heal consumes the same lines, so the contract must live in one place."""
    path = line[3:] if len(line) > 3 else ""
    if " -> " in path:
        path = path.split(" -> ", 1)[1]
    return path.strip().strip('"')


def _is_filtered_noise(substrate_rel_path: str) -> bool:
    """True if substrate-relative path is in a skipped subtree or has a skipped suffix."""
    if not substrate_rel_path:
        return False
    first = substrate_rel_path.split("/", 1)[0]
    if first in SKIP_SUBTREES:
        return True
    if substrate_rel_path.endswith(SKIP_FILE_SUFFIXES):
        return True
    return False


def _has_content_diff(repo_root: Path, repo_rel_path: str) -> bool:
    """True iff the working-tree file differs from HEAD in CONTENT.

    Windows/autocrlf guard: `git status --porcelain` can flag a tracked file
    as modified on a line-ending or stat (mtime) flicker with NO real content
    change — e.g. CRLF working-tree bytes vs an LF blob, or the index stat
    cache getting churned by another git process mid-run. `git diff` normalizes
    CRLF<->LF, so a pure line-ending / mtime touch returns no diff. Comparing
    against HEAD also covers staged changes. Fails OPEN (treats as a real
    change) if git can't be invoked, so we never silently pass a dirty tree."""
    try:
        r = subprocess.run(
            ["git", "-C", str(repo_root), "diff", "--quiet", "HEAD", "--", repo_rel_path],
            capture_output=True, text=True, check=False, timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return True
    # `git diff --quiet` exit code: 0 = no diff, 1 = diff, >1 = error.
    return r.returncode != 0


def check_substrate_clean(substrate_root: Path) -> List[str]:
    """Return a list of dirty tracked entries relative to the substrate.

    Each entry is the verbatim porcelain line (e.g. ' M Content/Maps/X.umap').
    Empty list means clean (or substrate is not in a git repo, in which case
    the check is skipped — see module docstring).

    Paths under SKIP_SUBTREES are filtered out — see module docstring.
    """
    try:
        top = subprocess.run(
            ["git", "-C", str(substrate_root), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=False, timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []

    if top.returncode != 0:
        return []

    repo_root = Path(top.stdout.strip())
    porcelain = subprocess.run(
        ["git", "-C", str(substrate_root), "status", "--porcelain", "--",
         str(substrate_root)],
        capture_output=True, text=True, check=False, timeout=10,
    )
    if porcelain.returncode != 0:
        return []

    # We need repo-root-relative paths from porcelain to be matched against
    # the substrate prefix so we can strip it. The path part starts at line[3:].
    try:
        substrate_rel_root = substrate_root.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        substrate_rel_root = ""

    dirty: List[str] = []
    for line in porcelain.stdout.splitlines():
        if not line:
            continue
        status = line[:2]
        if status == "??":
            continue

        path = porcelain_path(line)

        # Compute substrate-relative path for the skip filter.
        if substrate_rel_root and path.startswith(substrate_rel_root + "/"):
            substrate_rel = path[len(substrate_rel_root) + 1:]
        else:
            substrate_rel = path

        if _is_filtered_noise(substrate_rel):
            continue

        # Suppress autocrlf / stat-only flicker: only count it dirty if the
        # working tree differs from HEAD in real content (see _has_content_diff).
        if not _has_content_diff(repo_root, path):
            continue

        dirty.append(line)
    return dirty

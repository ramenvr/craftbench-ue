"""Guarantee a ``--live-project`` run starts from the committed substrate.

WHY THIS EXISTS (P0, 2026-08-18). A live-project run writes its deliverable into
``UE-projects/<substrate>/Content/Tasks/<task>/``. That path is **untracked** in git,
so the usual between-run repair — ``git checkout -- UE-projects/`` — does not remove
it. ``fairness.stage_task_tree_isolation_hide`` then *deliberately* keeps the ACTIVE
task's own folder (asset tasks may need a committed baseline there). The two rules
are individually correct and jointly leave the next run of the same task starting on
top of the previous run's finished work.

Measured, byte-exact: a ``unreal-mcp`` run's own ``live_backup`` held
``GA_Glide.uasset`` at 100 857 B — the exact size of the ``aura-mcp`` submission
written 40 minutes earlier — and "improved" it to 129 185 B, then graded L1 pass /
L2I pass. Two of five cells that day were contaminated, and **they were the two
best-looking ones**, because inheriting a head start is precisely what makes a cell
look good. Nothing in ``result.json`` distinguishes such a run from an honest one.

DESIGN NOTES, each of which is a deliberate rejection of a simpler option:

* **Quarantine, never delete.** Leftovers are moved into the run directory rather
  than removed. A benchmark harness silently deleting files from a live project is
  not something to do on an inference, and the moved bytes are the evidence that the
  contamination existed. They are already preserved in the *producing* run's
  ``submission/``, so nothing unique is at stake either way.
* **Run BEFORE ``live_backup`` is taken.** The end-of-run restore replays
  ``live_backup``; cleaning after it would restore the contamination.
* **Untracked-ness is the test, not the file name.** A task whose baseline is
  genuinely committed under ``Content/Tasks/<task>/`` has TRACKED files there and is
  left completely alone. Only files git does not know about can be leftovers.
* **Fail CLOSED when the check cannot run.** If the tree is not a git work tree, or
  git errors, we cannot tell a baseline from a leftover, so the caller is told the
  check was unavailable and decides. Reporting "clean" from a check that did not run
  is the failure mode this module exists to prevent.
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Sequence

#: Where quarantined leftovers land inside the run directory.
QUARANTINE_SUBDIR = "preexisting_leftovers"

#: git exit is not enough — a repo with no commits, a submodule boundary or a
#: permissions error all surface as noise on stderr. Treated as UNAVAILABLE.
_GIT_TIMEOUT_S = 60.0


@dataclass
class HygieneReport:
    """What the pre-drive check found. Serialised into ``result.json``."""

    #: True only if git actually answered. False => we do NOT know the tree is clean.
    checked: bool = False
    #: Why the check could not run, when ``checked`` is False.
    unavailable_reason: str = ""
    #: Repo-relative paths moved out of the writable area before the drive.
    quarantined: List[str] = field(default_factory=list)
    #: Paths that should have been quarantined but could not be moved (locked file).
    #: A non-empty list means the run is NOT safe to grade.
    stuck: List[str] = field(default_factory=list)

    @property
    def safe_to_grade(self) -> bool:
        """A run may be graded only if we KNOW the writable area was pristine."""
        return self.checked and not self.stuck

    def as_dict(self) -> dict:
        return {
            "checked": self.checked,
            "unavailable_reason": self.unavailable_reason,
            "quarantined": list(self.quarantined),
            "stuck": list(self.stuck),
            "safe_to_grade": self.safe_to_grade,
        }


def _git(args: Sequence[str], cwd: Path):
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True,
        timeout=_GIT_TIMEOUT_S,
    )


def untracked_under(project_dir: Path, writable_prefixes: Sequence[str]):
    """Repo-relative-to-``project_dir`` paths git does not track in the writable area.

    Returns ``(paths, unavailable_reason)``. A non-empty reason means the answer is
    unknown, NOT that the area is clean — callers must not conflate the two.
    """
    project_dir = Path(project_dir)
    try:
        inside = _git(["rev-parse", "--is-inside-work-tree"], project_dir)
        if inside.returncode != 0 or inside.stdout.strip() != "true":
            return [], "not a git work tree (cannot distinguish baseline from leftover)"
        # --others = untracked; --exclude-standard honours .gitignore, so Binaries/,
        # Saved/, Intermediate/ and Plugins/ are never listed and never touched.
        res = _git(["ls-files", "--others", "--exclude-standard", "-z", "."],
                   project_dir)
        if res.returncode != 0:
            return [], f"git ls-files failed: {(res.stderr or '').strip()[:200]}"
    except FileNotFoundError:
        return [], "git executable not found"
    except subprocess.TimeoutExpired:
        return [], f"git did not answer within {_GIT_TIMEOUT_S:.0f}s"
    except OSError as exc:
        return [], f"git could not be run: {exc}"

    prefixes = tuple(p.replace("\\", "/") for p in writable_prefixes)
    out = []
    for rel in res.stdout.split("\0"):
        rel = rel.strip().replace("\\", "/")
        if rel and any(rel.startswith(pre) for pre in prefixes):
            out.append(rel)
    return sorted(out), ""


def quarantine_untracked_writable(
    project_dir: Path,
    writable_prefixes: Sequence[str],
    quarantine_root: Path,
    log: Optional[Callable[[str], None]] = None,
) -> HygieneReport:
    """Move untracked files out of the agent-writable area before a live drive.

    Call this BEFORE taking ``live_backup`` so the backup — and therefore the
    post-run restore — records the pristine tree.
    """
    say = log or (lambda _m: None)
    project_dir = Path(project_dir)
    report = HygieneReport()

    rels, reason = untracked_under(project_dir, writable_prefixes)
    if reason:
        report.unavailable_reason = reason
        # LOUD: this is the one branch where a run can proceed without the guarantee.
        say(f"  WARN  pre-drive hygiene check UNAVAILABLE — {reason}. This run "
            f"cannot prove it started from the committed substrate; treat its "
            f"verdict as provisional.")
        return report

    report.checked = True
    if not rels:
        say("  OK    writable area matches git HEAD (no untracked leftovers)")
        return report

    for rel in rels:
        src = project_dir / rel
        dst = Path(quarantine_root) / QUARANTINE_SUBDIR / rel
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            report.quarantined.append(rel)
        except OSError as exc:
            # A file we cannot move stays agent-visible, which is the whole bug.
            # Record it; the caller must refuse to grade.
            report.stuck.append(f"{rel} ({exc.__class__.__name__})")

    say(f"  ..    quarantined {len(report.quarantined)} untracked leftover(s) from "
        f"the writable area -> {Path(quarantine_root).name}/{QUARANTINE_SUBDIR}/ "
        f"(a previous live run's output; leaving them would hand this agent a "
        f"head start)")
    for rel in report.quarantined[:8]:
        say(f"          {rel}")
    if len(report.quarantined) > 8:
        say(f"          ... and {len(report.quarantined) - 8} more")
    if report.stuck:
        say(f"  FAIL  {len(report.stuck)} leftover(s) could NOT be moved — the agent "
            f"would start on top of them, so this run must not be graded:")
        for rel in report.stuck:
            say(f"          {rel}")
    return report

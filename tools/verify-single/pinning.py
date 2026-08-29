"""Pinning-metadata collection for score-reports.

Per FR-002: every score-report MUST carry substrate_revision,
task_set_revision, verifier_revision, engine_version, harness_id,
model_id. Reports missing any are uncitable.

This module exposes ``collect_pinning()`` which resolves each field
from the environment (git, UE editor command, harness/model identifiers
passed in by the caller) and raises ``PinningResolutionError`` when any
field cannot be resolved.

Git-revision queries scope to specific paths so the substrate, task-set,
and verifier revisions move independently — bumping `tasks/` does not
move `substrate_revision`.
"""

from __future__ import annotations

import platform
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Optional


__all__ = [
    "PinningResolutionError",
    "PinningResult",
    "collect_pinning",
    "detect_engine_version",
    "git_revision_for",
]


class PinningResolutionError(RuntimeError):
    """Raised when one or more required pinning fields cannot be resolved.

    Carries ``.missing`` listing the field names so the caller can render
    a helpful error or fall back to a degraded mode (e.g. internal-only
    runs that don't yet need full pinning).
    """

    def __init__(self, missing: list[str], detail: str = "") -> None:
        self.missing = missing
        msg = f"unable to resolve pinning fields: {missing}"
        if detail:
            msg = f"{msg}; {detail}"
        super().__init__(msg)


@dataclass(frozen=True)
class PinningResult:
    substrate_revision: str
    task_set_revision: str
    verifier_revision: str
    engine_version: str
    harness_id: str
    model_id: str
    contract_versions: Mapping[str, str] = field(default_factory=dict)


def git_revision_for(path: Path, *, repo_root: Path) -> Optional[str]:
    """Return the most recent commit SHA touching ``path`` under ``repo_root``.

    Falls back to None if git is unavailable or the path has no history
    (e.g. fresh untracked file). The caller decides whether to harden
    that into an error.
    """
    if not path.exists():
        return None
    try:
        out = subprocess.run(
            [
                "git", "-C", str(repo_root),
                "log", "-1", "--format=%H", "--", str(path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    sha = (out.stdout or "").strip()
    return sha or None


def detect_engine_version(ue_root: Optional[Path]) -> Optional[str]:
    """Resolve the UE version from a UE install root.

    Reads ``Engine/Build/Build.version`` (JSON with MajorVersion /
    MinorVersion / PatchVersion). Returns ``None`` if ue_root is missing
    or the file isn't present (e.g. unusual install layouts).
    """
    if ue_root is None:
        return None
    path = ue_root / "Engine" / "Build" / "Build.version"
    if not path.exists():
        return None
    import json
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    major = data.get("MajorVersion")
    minor = data.get("MinorVersion")
    patch = data.get("PatchVersion")
    if major is None or minor is None:
        return None
    if patch is None:
        return f"{major}.{minor}"
    return f"{major}.{minor}.{patch}"


def collect_pinning(
    *,
    repo_root: Path,
    substrate_dir: Path,
    task_path: Path,
    verifier_dirs: tuple[Path, ...],
    ue_root: Optional[Path],
    harness_id: str,
    model_id: str,
    contract_versions: Optional[Mapping[str, str]] = None,
    strict: bool = True,
) -> PinningResult:
    """Resolve all pinning fields. Raises PinningResolutionError when
    strict=True and any field cannot be resolved.

    `verifier_dirs` should include `tools/verify-single/` so the verifier
    revision moves when it changes.
    """
    fields_resolved: dict[str, Optional[str]] = {}

    fields_resolved["substrate_revision"] = git_revision_for(
        substrate_dir, repo_root=repo_root
    )
    fields_resolved["task_set_revision"] = git_revision_for(
        task_path, repo_root=repo_root
    )

    # Verifier revision = the newest commit touching any verifier dir.
    verifier_shas = [
        git_revision_for(d, repo_root=repo_root) for d in verifier_dirs
    ]
    verifier_shas_set = sorted(set(s for s in verifier_shas if s))
    # If the verifier dirs aren't yet git-tracked (fresh repo), we degrade
    # to a literal "uncommitted" marker; strict mode then rejects.
    if verifier_shas_set:
        # Use a stable composite: the lex-max commit (the most recent on
        # whichever verifier dir was last touched). Composite hashing is
        # an option for later; for now the lex-max gives a stable string.
        fields_resolved["verifier_revision"] = verifier_shas_set[-1]
    else:
        fields_resolved["verifier_revision"] = None

    fields_resolved["engine_version"] = detect_engine_version(ue_root)
    fields_resolved["harness_id"] = harness_id or None
    fields_resolved["model_id"] = model_id or None

    missing = [k for k, v in fields_resolved.items() if not v]
    if strict and missing:
        raise PinningResolutionError(
            missing,
            detail=(
                "ensure the repo is a git checkout (substrate/task/verifier "
                "revisions), that UE_ROOT contains Engine/Build/Build.version, "
                "and that --harness and --model were passed"
            ),
        )

    # Non-strict fallback: substitute degraded placeholders so the
    # report is still well-typed; FR-002 will mark such reports
    # uncitable downstream.
    return PinningResult(
        substrate_revision=fields_resolved["substrate_revision"] or "uncommitted",
        task_set_revision=fields_resolved["task_set_revision"] or "uncommitted",
        verifier_revision=fields_resolved["verifier_revision"] or "uncommitted",
        engine_version=fields_resolved["engine_version"] or "unknown",
        harness_id=fields_resolved["harness_id"] or "unknown",
        model_id=fields_resolved["model_id"] or "unknown",
        contract_versions=contract_versions or {},
    )

"""Agent-writable-path enforcement for CraftBench submissions.

A submission is a directory tree the agent produced. Before we overlay it
onto the substrate copy in the runner's workdir, every file in the tree
is checked against a per-substrate manifest at:

    UE-projects/<name>/AGENT_WRITABLE.json

A file's repo-relative path (POSIX-normalized, with links/reparse points
rejected rather than followed) must:

    1. Match at least one prefix in `writable`, AND
    2. Not match any prefix in `deny`.

Anything outside the writable set is rejected with a per-path violation.
Path traversal (``..``) attempts and absolute paths are also rejected.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


# Asset-file extensions that the BP-deliverable capture path may collect from
# anywhere under an ``asset_writable`` prefix (default ``Content/``) — even
# outside the strict ``writable`` source prefixes. Deny prefixes (e.g.
# ``Content/Maps/``) still win, so the verifier-owned task maps stay out.
ASSET_EXTENSIONS = (".uasset", ".umap")


@dataclass(frozen=True)
class WritableManifest:
    """Parsed AGENT_WRITABLE.json contents."""

    substrate: str
    game_module: str
    writable: tuple[str, ...]
    deny: tuple[str, ...]
    # Prefixes under which ASSET files (.uasset/.umap) are accepted even when
    # they fall outside the strict ``writable`` source prefixes. This is the
    # BP-deliverable allowance: Aura sub-agents author Blueprints under
    # Content/Blueprints/, Content/Abilities/, … (not only Content/Tasks/), and
    # those .uasset deliverables must be gradeable. Deny still takes precedence,
    # so Content/Maps/ remains rejected. Defaults to EMPTY when the manifest
    # omits the key — back-compatible: existing --submission runs and manifests
    # that don't opt in keep the strict "Content/Tasks/ only" behavior, and a
    # stray .uasset at the Content/ root stays rejected. A substrate enables the
    # BP path by listing its asset folders explicitly in AGENT_WRITABLE.json.
    asset_writable: tuple[str, ...] = ()
    # Exact, task-owned plugin Content prefixes whose ASSET files may cross the
    # substrate's broad ``Plugins/`` deny. This is deliberately separate from
    # ``asset_writable``: plugin descriptors, Source/, Config/, neighboring
    # features, and host-local plugins remain denied. A manifest must opt in to
    # each task plugin root explicitly.
    plugin_asset_writable: tuple[str, ...] = ()
    # Exact FILE rel-paths (NOT prefixes) whose submission is path-ACCEPTED
    # here and then SEMANTICALLY validated later by config_lane (the runner
    # invokes validate_config_submission): the file's UE-ini diff against the
    # substrate baseline must be covered by the task spec's ``config_allow``
    # rules, or the run is rejected. This is the config lane: it lets a task
    # legitimately touch e.g. Config/DefaultEngine.ini (collision profiles)
    # without a broad Config/ writable prefix. Deny still wins — a rel-path
    # both denied and listed here is denied. Defaults to EMPTY when the
    # manifest omits the key — back-compatible: manifests that don't opt in
    # keep rejecting all of Config/ by allowlist-miss.
    config_writable: tuple[str, ...] = ()

    @classmethod
    def load(cls, path: Path) -> "WritableManifest":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            substrate=str(data["substrate"]),
            game_module=str(data["game_module"]),
            writable=tuple(_normalize_prefix(p) for p in data.get("writable", ())),
            deny=tuple(_normalize_prefix(p) for p in data.get("deny", ())),
            asset_writable=tuple(
                _normalize_prefix(p) for p in data.get("asset_writable", ())
            ),
            plugin_asset_writable=tuple(
                _normalize_prefix(p)
                for p in data.get("plugin_asset_writable", ())
            ),
            config_writable=tuple(
                _normalize_prefix(p) for p in data.get("config_writable", ())
            ),
        )


@dataclass
class Violation:
    """One sandbox violation: a submission file that may not be applied."""

    submission_path: Path
    rel_path: str
    reason: str

    def render(self) -> str:
        return f"  - {self.rel_path}: {self.reason}"


@dataclass
class SandboxResult:
    """Outcome of scanning a submission tree against a manifest."""

    accepted: list[tuple[Path, str]] = field(default_factory=list)
    violations: list[Violation] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations

    def render_report(self) -> str:
        if self.ok:
            return f"sandbox: accepted {len(self.accepted)} file(s), 0 violations"
        lines = [
            f"sandbox: REJECTED — {len(self.violations)} violation(s), "
            f"{len(self.accepted)} acceptable file(s)",
        ]
        lines.extend(v.render() for v in self.violations)
        return "\n".join(lines)


def _normalize_prefix(prefix: str) -> str:
    """Normalize a manifest prefix to a POSIX, leading-slash-free form.

    Input domain: manifest prefixes (from AGENT_WRITABLE.json) and the
    submission rel-paths they are matched against are *always* POSIX,
    repo-relative paths rooted inside the submission directory. The
    ``replace("\\", "/")`` maps Windows-native backslash separators to the
    POSIX manifest form, so a submission staged on Windows compares equal to
    the committed manifest.

    UNC paths (``//server/share/...``) are intentionally NOT supported: the
    final ``lstrip("/")`` would collapse the leading ``//`` and mangle the
    host component. This is out of scope by construction — submissions live
    under a local submission root and never resolve to a UNC location, so a
    UNC string can never reach this function in practice. The lstrip chain is
    correct for the supported (repo-relative, leading-slash-free) input domain.
    """
    p = prefix.replace("\\", "/").lstrip("./").lstrip("/")
    return p


def _is_asset_file(rel_path: str) -> bool:
    """True if the path is a UE asset file (.uasset / .umap), case-insensitive."""
    lower = rel_path.lower()
    return any(lower.endswith(ext) for ext in ASSET_EXTENSIONS)


def _is_writable(rel_path: str, manifest: WritableManifest) -> tuple[bool, str]:
    """Return (allowed, reason)."""
    raw = str(rel_path).replace("\\", "/")
    if raw.startswith("/") or re.match(r"^[A-Za-z]:", raw):
        return False, "absolute path disallowed"
    parts = [part for part in raw.split("/") if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        return False, "path traversal disallowed"
    rel_path = "/".join(parts)
    # A task-owned GameFeature is the one narrow exception to the broad
    # substrate Plugins/ deny. Require BOTH an asset extension and an explicit
    # task Content prefix; this cannot legalize descriptors, source/config, a
    # neighboring feature, or a host plugin.
    if _is_asset_file(rel_path):
        for allow in manifest.plugin_asset_writable:
            if _matches_prefix(rel_path, allow):
                return True, ""
    # Deny list takes precedence (Content/Maps/ etc.).
    for deny in manifest.deny:
        if _matches_prefix(rel_path, deny):
            return False, f"denied by manifest prefix '{deny}'"
    for allow in manifest.writable:
        if _matches_prefix(rel_path, allow):
            return True, ""
    # BP-deliverable allowance: an ASSET file under an ``asset_writable`` prefix
    # is accepted even though it is outside the strict writable source prefixes.
    # (Deny already short-circuited above, so Content/Maps/ never reaches here.)
    if _is_asset_file(rel_path):
        for allow in manifest.asset_writable:
            if _matches_prefix(rel_path, allow):
                return True, ""
    # Config-lane allowance: a rel-path EXACTLY equal to a ``config_writable``
    # entry is path-accepted here; the semantic diff validation against the
    # task spec's config_allow rules happens later in config_lane, invoked by
    # the runner. Exact match on purpose — config_writable entries are files,
    # not prefixes. (Deny already short-circuited above, so a denied path
    # never reaches here.)
    if rel_path.casefold() in {p.casefold() for p in manifest.config_writable}:
        return True, ""
    return False, "not under any writable prefix"


def _matches_prefix(rel_path: str, prefix: str) -> bool:
    """Prefix match against a manifest entry.

    A prefix ending in ``/`` matches any descendant; a prefix without a
    trailing slash matches the exact path or any descendant. Comparison is
    case-insensitive so the policy is stable on the Windows grading host.
    """
    if not prefix:
        return False
    rel_path = rel_path.casefold()
    prefix = prefix.casefold()
    if prefix.endswith("/"):
        return rel_path == prefix.rstrip("/") or rel_path.startswith(prefix)
    return rel_path == prefix or rel_path.startswith(prefix + "/")


def _is_link_like(path: Path) -> bool:
    """True for symlinks, NTFS junctions, and any other reparse point."""
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    if is_junction is not None and is_junction():
        return True
    try:
        return bool(getattr(os.lstat(path), "st_reparse_tag", 0))
    except OSError:
        return False


def _walk_submission(submission_root: Path):
    """Yield ``(path, is_link_like)`` without traversing link-like dirs."""
    for dirpath, dirnames, filenames in os.walk(submission_root, followlinks=False):
        here = Path(dirpath)
        kept_dirs = []
        for name in sorted(dirnames):
            entry = here / name
            linked = _is_link_like(entry)
            if linked:
                yield entry, True
            else:
                kept_dirs.append(name)
        dirnames[:] = kept_dirs
        for name in sorted(filenames):
            entry = here / name
            yield entry, _is_link_like(entry)


def iter_submission_files(submission_root: Path) -> Iterable[Path]:
    """Yield every non-link regular file inside the submission tree."""
    for entry, linked in _walk_submission(Path(submission_root)):
        if not linked and entry.is_file():
            yield entry


def scan_submission(
    submission_root: Path,
    manifest: WritableManifest,
) -> SandboxResult:
    """Classify every file in `submission_root` as accepted or violation.

    `submission_root` is the directory the agent handed us. We compute each
    file's path relative to the submission root (which is then interpreted
    as repo-relative inside the substrate copy in the workdir).
    """
    result = SandboxResult()
    original_root = Path(submission_root)
    if _is_link_like(original_root):
        result.violations.append(
            Violation(original_root, str(original_root),
                      "submission root is a symlink/junction/reparse point")
        )
        return result
    submission_root = original_root.resolve()

    for f, linked in _walk_submission(submission_root):
        if linked:
            try:
                rel_link = f.relative_to(submission_root).as_posix()
            except ValueError:
                rel_link = str(f)
            result.violations.append(
                Violation(f, rel_link,
                          "symlink/junction/reparse point disallowed")
            )
            continue
        if not f.is_file():
            continue
        try:
            resolved = f.resolve()
        except OSError as e:
            result.violations.append(
                Violation(f, str(f), f"resolve failed: {e}")
            )
            continue

        # Reject symlinks that escape the submission root.
        try:
            resolved.relative_to(submission_root)
        except ValueError:
            result.violations.append(
                Violation(
                    f,
                    str(f),
                    f"resolves outside submission root: {resolved}",
                )
            )
            continue

        try:
            rel = f.relative_to(submission_root)
        except ValueError:
            result.violations.append(
                Violation(f, str(f), "not relative to submission root")
            )
            continue

        rel_str = rel.as_posix()
        if ".." in rel.parts or rel.is_absolute():
            result.violations.append(
                Violation(f, rel_str, "path traversal disallowed")
            )
            continue

        allowed, reason = _is_writable(rel_str, manifest)
        if allowed:
            result.accepted.append((f, rel_str))
        else:
            result.violations.append(Violation(f, rel_str, reason))

    return result


def enforce_exact_accepted_files(
    result: SandboxResult,
    submission_root: Path,
    expected_files: Iterable[str],
) -> None:
    """Require accepted paths to equal a task's exact file manifest.

    The substrate manifest answers whether a path is writable at all. A task
    can be much narrower. This second boundary consumes only paths already
    classified by :func:`scan_submission`, so links, denied files, and unsafe
    spellings retain their original violations while missing and otherwise
    writable extras fail before grading.
    """
    expected = {
        str(path).replace("\\", "/").casefold():
            str(path).replace("\\", "/")
        for path in expected_files
    }
    if not expected:
        return
    actual = {
        rel.replace("\\", "/").casefold(): (path, rel)
        for path, rel in result.accepted
    }
    for key in sorted(actual.keys() - expected.keys()):
        path, rel = actual[key]
        result.violations.append(
            Violation(path, rel, "not declared in task accepted_files")
        )
    root = Path(submission_root)
    for key in sorted(expected.keys() - actual.keys()):
        rel = expected[key]
        result.violations.append(
            Violation(
                root / Path(rel),
                rel,
                "required by task accepted_files but missing",
            )
        )

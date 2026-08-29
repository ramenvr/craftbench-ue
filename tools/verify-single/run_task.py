#!/usr/bin/env python3
"""CraftBench verifier runner — entry point.

Applies an agent's submission to a substrate copy and runs the requested
verifier layers (currently L1 build + L2 PIE functional test). See
tools/verify-single/README.md for the CLI surface and the worked T0 example.

Substrate materialization (stability): the graded substrate is cloned from
git HEAD by default (``copy_substrate``), so only COMMITTED files enter the
graded tree — untracked WIP fixtures, uncommitted maps, stale Intermediate/,
and gold-task solution residue can never decide the verdict (stability findings
F1/F3/F4). ``--substrate-from-live`` (or CRAFTBENCH_SUBSTRATE_FROM_LIVE=1)
forces the old live-copy path for debugging.

SUBSTRATE-MAINTAINER NOTE: grading-from-HEAD only PASSES once the legit
substrate is committed to HEAD — the gold ``.umap`` maps, the Build.cs GAS
deps, and the CraftBenchTests verifier fixtures. Verifier-tree provenance is
git itself (``pinning.py`` records ``substrate_revision``); the old
verifier-hash manifest gate was removed with it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Mapping, Optional, Sequence

# Ensure local module imports resolve when invoked as a script.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import config_overlay  # noqa: E402
import repo_env  # noqa: E402
import failure_evidence  # noqa: E402
from fs_cleanup import robust_rmtree  # noqa: E402
from layers.l1_build import L1Result, SPAWN_FAULT_EXIT, run_l1  # noqa: E402
from layers.l2_pie import L2Result, run_l2  # noqa: E402
from layers.l2_introspect import run_l2_introspect  # noqa: E402
from report import HostInfo, LayerReport, Report  # noqa: E402
from sandbox import (  # noqa: E402
    SandboxResult,
    Violation,
    WritableManifest,
    enforce_exact_accepted_files,
    scan_submission,
)
# THE submittability predicate, bound AT IMPORT (not looked up per call) so a
# rename in sandbox.py is a loud ImportError here rather than silent drift.
# extract_writable_subset_from_project used to re-implement this rule and had
# already drifted off it; see that function's docstring for the measured cost.
from sandbox import _is_writable as _sandbox_is_writable  # noqa: E402
from config_lane import (  # noqa: E402
    parse_config_allow,
    validate_config_submission,
)
from content_staging import (  # noqa: E402
    MODE_FULL,
    StagingResult,
    full_substrate_requested,
    stage_per_task_content,
)
from task_layout import stage_per_task_dirs_active_only  # noqa: E402
from phase_timer import PhaseTimer  # noqa: E402

# Task-spec parsing lives in spec.py — THE single parser (front matter
# preferred, legacy H2 fallback). run_task re-exports the legacy helper names
# below so long-standing external imports (tasklint, build_warm_baseline,
# tests) keep resolving; nobody re-implements parsing here.
from spec import (  # noqa: E402
    Fixture,
    TaskSpec,
    parse_task_file,
    _fixtures_inline_to_block,
    _parse_fixtures_block,
    _parse_framerate_legs,
    _parse_introspect_block,
    _parse_metadata_block,
    _parse_randomization_block,
    _parse_scalar_section,
    _parse_verifier_layers_block,
    _split_h2_sections,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
_SCOPED_GAMEFEATURE_TASKS_REL = Path("Plugins") / "GameFeatures" / "Tasks"
_HOST_LOCAL_PLUGIN_NAMES = ("Aura", "Ramen")
DEFAULT_SUBSTRATE_NAME = "CraftBenchTemplate"

# ---------------------------------------------------------------------------
# Process exit-code taxonomy — THE contract every harness path reads.
#
# Only 0 and 1 are GRADED (they are the agent's measured outcome and belong in a
# pass-rate denominator). Everything else says "no measurement happened" and the
# harness maps it to a non-graded verdict — see adapters/base.py's
# VERIFIER_EXIT_VERDICT + GRADED_VERDICTS and aura_rig/driver.py's VERDICT,
# which must agree with this list key-for-key.
#
#   3 is RETIRED-AND-RESERVED: it was the removed verifier-hash-manifest
#     REJECT. Never re-use it — historical reports mean SUBSTRATE-REJECT by it.
#   6 is FORBIDDEN: 6 is UBT's OWN build-failure code, and
#     docs/harness-tour/02-verify-single.md documents "Exit 6 does not exist
#     here". Never emit it from this process.
#   7 was chosen for the harness-error state because it is below 126 and so
#     cannot collide with the POSIX shell's 124/126/127/128+N conventions.
# ---------------------------------------------------------------------------
EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_USAGE = 2
EXIT_SANDBOX_REJECT = 4
EXIT_NO_UPROJECT = 5
EXIT_HARNESS_ERROR = 7
# 8 = UNGRADED — the run deliberately did not certify. Today's only producer is
# --lite, which skips L1 and therefore grades against a binary it did not build:
# the remaining layers still report their check counts, but no PASS/FAIL claim is
# defensible. It is a SEPARATE code from 7 because harness-error means "the
# verifier could not produce a verdict" (a fault) while this means "the operator
# asked for no verdict" (a choice) — collapsing them would make a deliberate
# iteration run indistinguishable from a broken one in every dashboard.
#
# The safety property is structural, not procedural: adapters.base.GRADED_VERDICTS
# is an ALLOWLIST of {PASS, FAIL}, so UNGRADED is excluded from every pass-rate
# denominator by omission — nobody has to remember to exclude it. This is exactly
# why --lite emits a new verdict rather than a flag on top of PASS/FAIL: a flag
# would leave a PASS in the report that some consumer eventually counts.
EXIT_UNGRADED = 8

# report.json ``overall`` for the harness-error state. Deliberately NOT "fail":
# consumers that read report.json / result.json directly (dashboard,
# run_batch._collect_result_verdicts) key off this string, and "fail" there would
# smuggle a non-measurement back into the graded population through the side
# door. Uppercased by adapters.base._overall_from_report_json it becomes exactly
# VERDICT_HARNESS_ERROR ("HARNESS-ERROR"), so both routes agree.
OVERALL_HARNESS_ERROR = "harness-error"

# report.json ``overall`` for a --lite run. Uppercased by the harness it becomes
# VERDICT_UNGRADED, which is not in GRADED_VERDICTS — so a lite report can never
# be read as a graded outcome by either route. It is set UNCONDITIONALLY, even
# when every layer that ran passed: "L2I 11/11 against a binary we did not build"
# is a useful iteration signal and NOT a certification, and letting it print PASS
# is precisely how a forgotten flag ends up in a certification run.
OVERALL_UNGRADED = "ungraded"

# L1 sub-process exit codes that layers/l1_build.py synthesizes itself (they are
# NOT UBT's own codes): 127 = the build tool could not be executed at all
# (FileNotFoundError on the UBT script / editor binary), 124 = the governed
# timeout reaped the build, 126 = SPAWN_FAULT_EXIT (imported so the literal
# lives in one place) = a no-trace spawn reproduced on retry.
L1_EXIT_EXEC_FAILED = 127
L1_EXIT_TIMEOUT = 124

# Which of those mean "the HARNESS could not build" rather than "the submission
# does not compile", with the reason text per member so predicate 3 stays one
# membership test. Neither routes on the code alone — both additionally require
# LayerReport.build_tool_never_ran. L1_EXIT_TIMEOUT is deliberately ABSENT: a
# pathological submission can hang a compile, so routing 124 out of the
# denominator would hand every agent an opt-out. Ambiguity resolves toward
# GRADED — see harness_error_reasons' docstring, predicate 3.
_L1_HARNESS_ERROR_REASONS = {
    L1_EXIT_EXEC_FAILED: (
        f"L1 exit {L1_EXIT_EXEC_FAILED}: the build tool could not be executed "
        "(missing UBT script / editor binary)"
    ),
    SPAWN_FAULT_EXIT: (
        f"L1 exit {SPAWN_FAULT_EXIT}: a UBT target exited non-zero having "
        "written no output and touched no build product, on two consecutive "
        "spawns — the process was never created"
    ),
}
L1_HARNESS_ERROR_EXITS = frozenset(_L1_HARNESS_ERROR_REASONS)

# The fourth LayerReport status, alongside pass|fail|skipped. A layer emits it
# when its VERDICT CHANNEL produced nothing to read — not when the thing it
# measured came out wrong. Today only L2I can (layers/l2_introspect.py's
# fail-safe: missing verifier script, editor binary absent, no verdict block,
# malformed JSON, no `checks` list); the predicate below is keyed on the status,
# not on the layer key, so any future layer that adopts the same fail-safe is
# routed the same way. See harness_error_reasons' docstring, predicate 5.
LAYER_STATUS_ERROR = "error"

# Sub-process exit codes that keep an ``error`` layer GRADED. 124 is the
# governed timeout, synthesized by l2_introspect exactly as l1_build synthesizes
# it, and it carries the SAME asymmetry: agent C++ is linked into the editor
# this layer launches, so a pathological submission can hang it, and routing 124
# to the non-graded state would hand every agent an opt-out of the denominator.
# Ambiguity resolves toward GRADED — the identical argument that keeps
# L1_EXIT_TIMEOUT out of L1_HARNESS_ERROR_EXITS above.
LAYER_ERROR_GRADED_EXITS = frozenset({L1_EXIT_TIMEOUT})

# Framerate-independence tasks: run the SAME fixture/map in N separate PIE
# processes at different fixed dts (via run_l2's `fps` param) and require ALL to
# pass. The Timer task's 20Hz leg makes a tick-count overfit fail where a
# wall-clock FTimerManager solution passes. Keyed by task_id.
#
# LEGACY FALLBACK (DD-9): framerate legs are now declared per-task in the spec
# (``## Verifier framerate legs``, or an ``fps:`` param on the unified
# ``## Verifier layers`` L2 line) and parsed into ``TaskSpec.framerate_legs``;
# registry.py prefers those and falls back to this dict. The dict is empty
# since the fresh-start cull removed its last two entries (the retired
# gp-timer-delayed-destroy / timer-delayed-spawn tasks, whose specs declared
# the same legs). Prefer the spec for any NEW task — do not add entries here.
_DT_LEGS_BY_TASK: dict[str, tuple[int, ...]] = {}


def _now_stamp() -> str:
    """Human-readable LOCAL wall-clock 'YYYY-MM-DD HH:MM:SS' for the report header
    (``report.graded_at``) — so a run reads at a glance instead of only by content
    hash. ``duration_seconds`` still carries the elapsed time."""
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


# ---------------------------------------------------------------------------
# Task-spec parsing — moved to spec.py (parse_task_file). The thin shim below
# keeps the long-standing `run_task.parse_task_spec` entry point working for
# external importers (tasklint.py, build_warm_baseline.py, tests).
# ---------------------------------------------------------------------------


def parse_task_spec(path: Path) -> TaskSpec:
    """Parse a task.md into a TaskSpec.

    Thin delegation shim: spec.parse_task_file is THE parser (front matter
    preferred; legacy H2 fallback with identical semantics, flagged
    ``legacy=True``). Kept so existing imports of run_task.parse_task_spec
    keep resolving.
    """
    return parse_task_file(path)


def resolve_randomization_tokens(
    tokens: Sequence[str], *, run_id: str, length: int = 8
) -> dict[str, str]:
    """Deterministic per-run resolution of token names → hex values.

    Same (run_id, token) → same value; different run_ids → different values.
    Hex length defaults to 8 (32 bits of entropy, plenty for in-substrate
    identifier uniqueness).
    """
    out: dict[str, str] = {}
    for tok in tokens:
        digest = hashlib.sha256(f"{run_id}|{tok}".encode("utf-8")).hexdigest()
        out[tok] = digest[:length]
    return out


def apply_randomization(
    root: Path,
    token_values: Mapping[str, str],
    *,
    file_globs: Sequence[str] = ("**/*.md", "**/*.h", "**/*.cpp", "**/*.cs", "**/*.py", "**/*.json", "**/*.ini"),
    skip_dirs: Sequence[str] = ("Binaries", "Intermediate", "Saved", "DerivedDataCache", "ThirdParty", "PortablePython", "Plugins", ".git"),
) -> dict[str, int]:
    """Walk ``root`` and substitute ``<<TOKEN_NAME>>`` patterns in matching files.

    The pattern is ``<<TOKEN_NAME>>`` where ``TOKEN_NAME`` is the uppercase
    snake-case rendering of the kebab-case token (e.g. ``log-tag`` → look for
    ``<<LOG_TAG>>``). Both kebab-original and snake-uppercase forms are
    accepted in source files so authors can pick the more readable one.

    Returns a dict ``{token: substitution_count}``. Files are rewritten in
    place; only files containing at least one matching pattern are touched.

    The default file_globs target the small set of text-y substrate files
    where token substitution is meaningful; the default skip_dirs avoid
    binary artifacts and the whole Plugins/ tree (the aura-plugin clone; Aura is
    disabled for grading anyway).
    """
    if not token_values:
        return {}

    # Build both kebab and SNAKE_UPPER patterns for each token.
    patterns: dict[str, str] = {}  # pattern → value
    for tok, val in token_values.items():
        kebab = f"<<{tok}>>"
        snake_upper = f"<<{tok.upper().replace('-', '_')}>>"
        patterns[kebab] = val
        patterns[snake_upper] = val

    counts: dict[str, int] = {tok: 0 for tok in token_values}
    # Reverse lookup: pattern → original token name (for the counts)
    pattern_to_token: dict[str, str] = {}
    for tok in token_values:
        pattern_to_token[f"<<{tok}>>"] = tok
        pattern_to_token[f"<<{tok.upper().replace('-', '_')}>>"] = tok

    seen_paths: set[Path] = set()
    for glob in file_globs:
        for path in root.glob(glob):
            if not path.is_file():
                continue
            if any(seg in skip_dirs for seg in path.relative_to(root).parts[:-1]):
                continue
            if path in seen_paths:
                continue
            seen_paths.add(path)
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            changed = False
            for pat, val in patterns.items():
                if pat in text:
                    n = text.count(pat)
                    text = text.replace(pat, val)
                    counts[pattern_to_token[pat]] += n
                    changed = True
            if changed:
                path.write_text(text, encoding="utf-8")

    return counts


# ---------------------------------------------------------------------------
# Substrate copy
# ---------------------------------------------------------------------------


def _env_truthy(name: str) -> bool:
    """True if env var ``name`` is set to a truthy value (1/true/yes/on)."""
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _substrate_dir_name(substrate_key: str) -> str:
    """Map the task-spec substrate alias to the on-disk directory name.

    The task spec writes ``substrate: template``; on disk this is
    ``UE-projects/CraftBenchTemplate/``. Names without an alias pass through
    unchanged (``mapping.get(key, key)``) — e.g. ``substrate:
    ThirdPersonTemplate`` resolves implicitly to
    ``UE-projects/ThirdPersonTemplate/``. Future Lyra support will add
    another mapping here.
    """
    mapping = {
        "template": DEFAULT_SUBSTRATE_NAME,
        "CraftBenchTemplate": DEFAULT_SUBSTRATE_NAME,
        "lyra": "LyraStarter",
    }
    return mapping.get(substrate_key, substrate_key)


def hash_submission(root: Path) -> str:
    """Single sha256 over the submission tree (path + content per file)."""
    h = hashlib.sha256()
    if not root.exists():
        return "0" * 64
    for f in sorted(root.rglob("*")):
        if not f.is_file():
            continue
        rel = f.relative_to(root).as_posix().encode("utf-8")
        h.update(len(rel).to_bytes(4, "big"))
        h.update(rel)
        h.update(b"\x00")
        with f.open("rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
    return h.hexdigest()


# NOTE (hash-manifest retirement): the verifier-hash integrity gate
# (verifier_hashes.json + verify_tests_module_integrity + the exit-3
# SUBSTRATE-REJECT path and the --regen-verifier-hashes /
# --regen-substrate-hashes maintainer flags) was REMOVED. Verifier-tree
# provenance is git itself: the graded substrate is materialized from git
# HEAD (copy_substrate) and pinning.py records substrate_revision.
# Exit code 3 is RETIRED and stays reserved so downstream tooling never
# confuses a historical hash-REJECT with a new failure mode; sandbox
# rejection (exit 4) is unchanged. Runs graded from the live working tree
# (--substrate-from-live) are annotated "substrate_source": "live" in the
# report and are NOT certified.


def _disable_plugin_in_uproject(uproject_path: Path, plugin_name: str) -> None:
    """Patch the uproject to mark a plugin as disabled (or add it as disabled).

    Used during verifier runs to prevent the Aura plugin from loading and
    crashing the editor before L2 automation discovery can run. The patch
    only affects the cloned workdir's uproject; the original substrate
    file is untouched. Idempotent.
    """
    if not uproject_path.exists():
        return
    raw = json.loads(uproject_path.read_text(encoding="utf-8"))
    plugins = list(raw.get("Plugins", []))
    found = False
    for entry in plugins:
        if entry.get("Name") == plugin_name:
            entry["Enabled"] = False
            found = True
    if not found:
        plugins.append({"Name": plugin_name, "Enabled": False})
    raw["Plugins"] = plugins
    # write_bytes (not write_text) so the cloned workdir .uproject stays LF
    # regardless of platform line-ending defaults / git core.autocrlf. UBT/UE
    # read it as machine JSON; keeping it LF avoids any CRLF surprise. Mac
    # already emits LF here, so this is byte-identical on macOS.
    uproject_path.write_bytes(
        (json.dumps(raw, indent="\t") + "\n").encode("utf-8")
    )


def _resolve_repo_root_for(path: Path) -> Optional[Path]:
    """Return the git work-tree root that contains ``path``, or None.

    Runs ``git -C <path> rev-parse --show-toplevel``. Returns None if ``path``
    is not inside a git work tree, or if git is unavailable / errors.
    """
    base = path if path.is_dir() else path.parent
    try:
        out = subprocess.run(
            ["git", "-C", str(base), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None
    top = out.stdout.strip()
    if not top:
        return None
    return Path(top)


def _path_is_tracked(repo_root: Path, relpath: str) -> bool:
    """True if any committed file at/under ``relpath`` exists in HEAD.

    Uses ``git ls-tree -r --name-only HEAD -- <relpath>`` and checks for any
    output. An untracked substrate dir (relpath matches nothing in HEAD)
    returns False, which routes the caller to the live-copy fallback.
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "ls-tree", "-r", "--name-only", "HEAD", "--", relpath],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return False
    return bool(out.stdout.strip())


def _is_windows_host(system: Optional[str] = None) -> bool:
    """True for native Windows CPython (``Windows``) AND Git-Bash/MSYS2/Cygwin
    Python (``MINGW64_NT-*`` / ``MSYS_NT-*`` / ``CYGWIN_NT-*``). Same family match
    as the L1/L2 layers — keeps the substrate-copy Windows handling in agreement
    with how the build/PIE layers detect a Windows host."""
    sys_l = (system or platform.system()).lower()
    return sys_l.startswith("win") or sys_l.startswith(("cygwin", "msys", "mingw"))


def new_temp_workdir(prefix: str = "craftbench-") -> Path:
    """``tempfile.mkdtemp`` + **canonicalization** — the only way this runner
    mints a disposable temp dir that a UE command line will ever see.

    WHY the ``.resolve()`` is load-bearing (FAILURE-LOG 2026-07-25): ``mkdtemp``
    roots in ``tempfile.gettempdir()``, which mirrors ``%TEMP%`` *verbatim*. On a
    Windows profile whose name exceeds 8 characters that string is the **8.3
    short form** — on the 2026-07-25 testbed host, ``%TEMP%`` reads
    ``C:\\Users\\SHORT~1\\AppData\\Local\\Temp`` while its long form is
    ``C:\\Users\\<user>\\AppData\\Local\\Temp``. The cold verify workdir
    (and therefore ``out/l2_report``, the dir handed to the editor as
    ``-ReportExportPath``) inherited that ``SHORT~1`` component, the L2 leg
    could not retrieve its automation result, and every task came back
    ``exit_code 3`` -> status ``skipped`` -> **FAIL**:
    ``cb batch-eval --references all`` scored **0/15** while the SAME references
    scored 2/2 under ``--keep`` (``C:\\cb\\wd\\...``) and 2/2 with ``%TEMP%``
    pointed at the long form. The 39-char long path PASSED and the 35-char short
    path FAILED, so this is emphatically NOT MAX_PATH — the 8.3 component is the
    only differing input.

    ``Path.resolve()`` expands an 8.3 component on Windows (verified on this
    host) and is a no-op everywhere else, so canonicalizing here makes the
    default temp branch behave exactly like the long-standing ``--workdir``
    branch, which has always called ``.resolve()``.
    """
    return Path(tempfile.mkdtemp(prefix=prefix)).resolve()


def copy_substrate_from_git(
    substrate_src: Path, dest: Path, *, repo_root: Path
) -> None:
    """Materialize the substrate into ``dest`` from git HEAD (committed files only).

    Pipes ``git archive HEAD -- <substrate-relpath>`` into ``tar -x`` rooted at
    a private staging dir, then moves the resulting subtree to ``dest``. ONLY
    committed files enter the graded tree — untracked WIP fixtures
    (AnimInterrupt/RenderProbe), uncommitted maps, stale Intermediate/Binaries,
    and gold-task solution residue in Source/CraftBenchTemplate/ are excluded by
    construction. This is the root-cause fix for stability findings F1/F3/F4 and
    the benchmark-contamination risk (uncommitted disk state deciding the verdict).

    ``dest`` must not already exist. ``repo_root`` is the git work-tree root;
    ``substrate_src`` must live under it. Raises on any git/tar/extraction error
    so the caller can fall back to a live copy.

    Saved/ exclusion: git archive omits gitignored paths (Saved/ is gitignored),
    so the existing exclusion semantics are preserved for free; a belt-and-braces
    guard removes any Saved/ subtree that slips through.

    SUBSTRATE-MAINTAINER NOTE: grading from HEAD only passes once the *legit*
    substrate is COMMITTED — the gold .umap maps, the Build.cs GAS deps, and the
    CraftBenchTests verifier fixtures. That is a separate substrate-maintainer
    commit, NOT performed here. Until then, the verifier-noise the F1/F3/F4
    fixes remove is replaced by a clean, deterministic "missing committed
    substrate" failure rather than a checkout-state-dependent flip.
    """
    relpath = substrate_src.resolve().relative_to(repo_root.resolve()).as_posix()

    # Both `git` and `tar` must be on PATH. On Windows they are not present by
    # default (Git Bash / MSYS2 / WSL provide them); on macOS/Linux they are
    # standard. shutil.which() lets us raise a clear, tool-named RuntimeError
    # BEFORE Popen so the caller's live-copy fallback gets an actionable reason
    # rather than a bare FileNotFoundError. (additive guard; no behavior change
    # when both tools are present, which is the macOS/Linux default.)
    for tool in ("git", "tar"):
        if shutil.which(tool) is None:
            raise RuntimeError(
                f"'{tool}' not found on PATH; cannot materialize the substrate "
                f"from git HEAD. Install git+tar (e.g. Git Bash / MSYS2 on "
                f"Windows) or rerun with --substrate-from-live to copy the live "
                f"working tree instead."
            )

    # Deliberately RAW mkdtemp (not new_temp_workdir): this staging dir is a
    # private git-archive|tar landing zone that is `shutil.move`d away and
    # rmtree'd in the `finally` below — it never reaches a UE command line or a
    # -ReportExportPath, so the 2026-07-25 8.3 canonicalization does not apply.
    # (Windows resolves the short form to the same directory for our own file
    # I/O; only UE's path round-trip was sensitive to it.)
    staging = Path(tempfile.mkdtemp(prefix="craftbench-gitarchive-"))
    try:
        # Tracked plugins are part of the certified substrate. Host-local Aura/Ramen
        # are ignored in the normal checkout and are stripped explicitly below as a
        # defense in depth; notably, this must not exclude the task-owned Game Feature
        # descriptors and baseline assets under Plugins/GameFeatures/Tasks/.
        # Force LF on export. A Windows host's global core.autocrlf=true makes
        # `git archive` rewrite LF->CRLF for text files whose .gitattributes leave
        # eol unspecified (the CraftBenchTests sources). Materialize the canonical
        # committed (LF) bytes regardless of host config so the graded tree is
        # byte-identical across hosts; a no-op on macOS/Linux where autocrlf is
        # already off.
        archive_args = ["git", "-C", str(repo_root), "-c", "core.autocrlf=false",
                        "-c", "core.eol=lf", "archive", "HEAD", "--", relpath]
        try:
            archive = subprocess.Popen(
                archive_args,
                stdout=subprocess.PIPE,
            )
            extract = subprocess.Popen(
                ["tar", "-x", "-C", str(staging)],
                stdin=archive.stdout,
            )
        except (FileNotFoundError, OSError) as exc:
            # A tool went missing between the which() check and launch, or the
            # OS refused to spawn it. Name the failure and steer to the fallback.
            raise RuntimeError(
                "failed to launch the git-archive | tar pipe to materialize the "
                f"substrate from git HEAD ({exc}). Ensure git+tar are installed "
                "and on PATH (Git Bash / MSYS2 on Windows), or rerun with "
                "--substrate-from-live to copy the live working tree instead."
            ) from exc
        # Allow archive to receive SIGPIPE if extract exits.
        if archive.stdout is not None:
            archive.stdout.close()
        extract_rc = extract.wait()
        archive_rc = archive.wait()
        if archive_rc != 0:
            raise RuntimeError(
                f"git archive HEAD -- {relpath} exited {archive_rc}"
            )
        if extract_rc != 0:
            raise RuntimeError(f"tar extract exited {extract_rc}")

        extracted = staging / relpath
        if not extracted.exists():
            raise RuntimeError(
                f"git archive produced no files under {relpath} "
                "(substrate path untracked in HEAD?)"
            )

        # Belt-and-braces: drop any Saved/ that slipped past gitignore.
        saved = extracted / "Saved"
        if saved.exists():
            shutil.rmtree(saved)
        for plugin_name in _HOST_LOCAL_PLUGIN_NAMES:
            _remove_exact_path(extracted / "Plugins" / plugin_name)

        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(extracted), str(dest))
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def copy_substrate_from_live(substrate_src: Path, dest: Path) -> None:
    """Copy the substrate tree from the LIVE working tree into ``dest``.

    DEBUG / fallback path: this includes uncommitted and untracked files
    (WIP fixtures, stale Intermediate/, uncommitted maps), so the verdict can
    depend on disk state. Use only via --substrate-from-live or when the
    project is not inside a git repo. Excludes Saved/ to preserve the existing
    per-run isolation semantics.
    """
    def _ignore(dirpath: str, names: List[str]) -> set:
        # Always drop Saved/ (per-run isolation) — preserves the prior
        # ignore_patterns("Saved") behavior on macOS/Linux exactly.
        ignored = {n for n in names if n == "Saved"}
        # Drop IDE-local dirs (never graded, and now gitignored). Visual Studio
        # keeps .vs/CraftBenchTemplate/FileContentIndex/*.vsidx locked open, so
        # copying them crashes copytree with WinError 32 whenever a maintainer has
        # the project open in VS — same "local-machine artifact" rationale as Saved.
        ignored |= {n for n in names if n in (".vs", ".idea", ".vscode")}
        # Never copy the substrate's Plugins/ — it is the host-local aura-plugin
        # clone (multi-GB: Binaries, PortablePython, node_modules) and Aura is
        # disabled for grading, so the workdir needs no plugins. Dropping the whole
        # tree also avoids following a legacy Plugins/Aura symlink into a dead target
        # (the old crash) and the Plugins/Ramen junction's MAX_PATH depths.
        if "Plugins" in names:
            ignored.add("Plugins")
        # NEVER traverse directory junctions/symlinks anywhere in the tree
        # (the workspace.py precedent). They are local-machine artifacts —
        # e.g. the Plugins/Ramen junction into the aura-plugin rig, whose
        # node_modules depths blow the Windows 260-char MAX_PATH mid-copy
        # (WinError 3) and whose contents are never graded.
        for n in names:
            if n in ignored:
                continue
            try:
                if _is_link_like(Path(dirpath) / n):
                    ignored.add(n)
            except OSError:
                ignored.add(n)   # unstatable == not copyable — skip it
        return ignored

    shutil.copytree(substrate_src, dest, ignore=_ignore)

    # The base walker intentionally excludes the whole host-local Plugins tree.
    # Add back only the task-owned Game Feature root, never a broad Plugins copy.
    scoped_src = substrate_src / _SCOPED_GAMEFEATURE_TASKS_REL
    scoped_dst = dest / _SCOPED_GAMEFEATURE_TASKS_REL
    scoped_ancestors = (
        substrate_src / "Plugins",
        substrate_src / "Plugins" / "GameFeatures",
        scoped_src,
    )
    try:
        if (not scoped_src.is_dir()
                or any(_is_link_like(p) for p in scoped_ancestors)):
            return
    except OSError:
        return

    generated_dirs = {
        name.casefold() for name in
        ("Binaries", "Intermediate", "Saved", "DerivedDataCache")
    }

    def _scoped_ignore(dirpath: str, names: List[str]) -> set:
        ignored = {n for n in names if n.casefold() in generated_dirs}
        for name in names:
            if name in ignored:
                continue
            try:
                if _is_link_like(Path(dirpath) / name):
                    ignored.add(name)
            except OSError:
                ignored.add(name)
        return ignored

    scoped_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(scoped_src, scoped_dst, ignore=_scoped_ignore)


def _remove_exact_path(path: Path) -> None:
    """Remove one exact extracted path without ever traversing a link/junction."""
    if not os.path.lexists(str(path)):
        return
    try:
        link_like = _is_link_like(path)
    except OSError:
        link_like = True
    if link_like:
        if path.is_symlink():
            path.unlink()
        elif path.is_dir():
            path.rmdir()
        else:
            path.unlink()
        return
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def _stage_scoped_task_plugins(
    project_root: Path,
    active_task_id: str,
    content_staging: StagingResult,
) -> StagingResult:
    """Prune foreign task plugin shells and fold the audit into staging data."""
    removed = stage_per_task_dirs_active_only(
        project_root,
        active_task_id,
        roots=(_SCOPED_GAMEFEATURE_TASKS_REL.as_posix(),),
    )
    note = f"scoped GameFeature staging excluded {len(removed)} task plugin dir(s)"
    return StagingResult(
        mode=content_staging.mode,
        excluded=tuple(sorted(set(content_staging.excluded).union(removed))),
        notes=tuple(content_staging.notes) + (note,),
    )


def _is_link_like(p: Path) -> bool:
    """True for symlinks AND NTFS junctions. ``Path.is_junction`` is Python
    3.12+ — on 3.11 fall back to the lstat reparse tag (a Windows-only stat
    attribute; absent on POSIX, where is_symlink() already covers links)."""
    if p.is_symlink():
        return True
    is_junc = getattr(p, "is_junction", None)
    if is_junc is not None:
        return bool(is_junc())
    return bool(getattr(os.lstat(p), "st_reparse_tag", 0))


def copy_substrate(
    substrate_src: Path,
    dest: Path,
    *,
    from_live: bool = False,
    repo_root: Optional[Path] = None,
) -> str:
    """Materialize the graded substrate into ``dest`` (which must not yet exist).

    DEFAULT: clone from git HEAD (committed files only) so the graded tree is a
    function of the deliverable, not of uncommitted working-tree state. Falls
    back to a live copy (with a logged warning) when the project is not in a git
    repo, the substrate path is untracked in HEAD, or git archive fails.

    Set ``from_live=True`` (CLI ``--substrate-from-live`` / env
    ``CRAFTBENCH_SUBSTRATE_FROM_LIVE=1``) to force the live-copy path for
    debugging.

    Returns the substrate source actually used: ``"git-head"`` for the
    committed-files clone, ``"live"`` for any live working-tree copy (forced OR
    fallback). The report records this as ``substrate_source`` — a ``"live"``
    grade is NOT certified, since the verdict may depend on uncommitted state.
    """
    if from_live:
        print(
            "info: --substrate-from-live set; copying the LIVE working tree "
            "(verdict may depend on uncommitted disk state — UNCERTIFIED)"
        )
        copy_substrate_from_live(substrate_src, dest)
        return "live"

    root = repo_root or _resolve_repo_root_for(substrate_src)
    if root is None:
        print(
            f"WARNING: {substrate_src} is not inside a git work tree; falling "
            "back to a live copy (verdict may depend on uncommitted disk state)",
            file=sys.stderr,
        )
        copy_substrate_from_live(substrate_src, dest)
        return "live"

    relpath = substrate_src.resolve().relative_to(root.resolve()).as_posix()
    if not _path_is_tracked(root, relpath):
        print(
            f"WARNING: substrate path '{relpath}' is untracked in HEAD; falling "
            "back to a live copy (verdict may depend on uncommitted disk state)",
            file=sys.stderr,
        )
        copy_substrate_from_live(substrate_src, dest)
        return "live"

    try:
        copy_substrate_from_git(substrate_src, dest, repo_root=root)
        print(f"info: substrate materialized from git HEAD ({relpath})")
        return "git-head"
    except Exception as exc:  # noqa: BLE001 — any git/tar failure → fallback
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
        print(
            f"WARNING: git-archive substrate clone failed ({exc}); falling back "
            "to a live copy (verdict may depend on uncommitted disk state)",
            file=sys.stderr,
        )
        copy_substrate_from_live(substrate_src, dest)
        return "live"


def apply_submission(
    submission_root: Path,
    workdir_substrate: Path,
    accepted: list[tuple[Path, str]],
) -> None:
    """Copy each accepted submission file into the workdir substrate copy.

    A file whose content ALREADY matches the destination is left alone. That is
    semantically a no-op — the graded tree is byte-identical either way — but it
    preserves the destination's MTIME, which UBT reads to decide what to rebuild.

    WHY THIS MATTERS, measured 2026-08-03. ``--submission-from-project`` does not
    extract the agent's *diff*; it sweeps the whole writable subtree. On a kp-
    row whose actual deliverable was ONE .uasset, the "submission" was 89 files,
    88 of them under Source/. Copying them unconditionally rewrote every source
    file with a fresh mtime, so UBT logged "Invalidating makefile for
    ThirdPersonEditor (ThirdPerson.Build.cs modified)" and rebuilt all 47 actions
    -- L1 127.5s where the same warm slot had just done 3.9s.

    The content fingerprint had correctly decided the compile inputs were
    IDENTICAL and skipped the mtime bump (warm_cache.compile_input_fingerprint).
    This function then bumped them anyway, as a side effect of copying. Stopping
    the harness from lying to UBT in one place is worthless while it still lies
    here.

    Only the reference-grading path was unaffected, because there the submission
    really is just the deliverable.
    """
    for src, rel in accepted:
        dst = workdir_substrate / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if _same_content(src, dst):
            continue
        shutil.copy2(src, dst)


def _same_content(src: Path, dst: Path) -> bool:
    """True when both files exist with identical bytes.

    Size is checked first as a cheap reject. Any OSError answers False, so an
    unreadable file falls through to the copy — the fail-safe direction is
    "write it", never "assume it matched".
    """
    try:
        if not dst.is_file():
            return False
        if src.stat().st_size != dst.stat().st_size:
            return False
        return src.read_bytes() == dst.read_bytes()
    except OSError:
        return False


def _stage_config_overlay(
    task_path: Path, workdir_substrate: Path, task_id: str
) -> list[str]:
    """Apply the per-task UE config overlay (B7) into the workdir substrate.

    A task folder may ship verifier-owned ``Config/*.ini`` fragments at
    ``tasks/<set>/<id>/ue-config/``; each is APPEND-applied (marker-headed)
    onto the workdir copy's ``Config/<IniName>.ini`` — see ``config_overlay``.
    The workdir is disposable, so no revert here: cold workdirs are deleted
    after the grade, and warm slots snapshot + reset ``Config/`` to pristine
    each verify (``warm_cache.VERIFIER_MUTABLE_PREFIXES``). Returns the applied
    ini names ([] for tasks without an ``ue-config/`` dir — which is all but ONE
    task as of 2026-08-19: ``tasks/bp/t2-consistent-enum-names`` ships a
    ``DefaultEngine.ini`` fragment. The docstring used to say "every task today";
    it was written before that fragment landed and had gone stale, which matters
    because the overlay IS the config-lane diff baseline for the task that has
    one).
    """
    fragments = config_overlay.discover(task_path)
    if not fragments:
        return []
    applied = config_overlay.apply(
        workdir_substrate / "Config", fragments, task_id
    )
    return [a.ini_name for a in applied]


# Path segments that are build/editor detritus rather than deliverables. NOT
# part of the sandbox rule — a live UE Editor session leaves Binaries/,
# Intermediate/, DerivedDataCache/ and Saved/ residue INSIDE the writable
# subtree, and sweeping it into the submission both bloats the copy and rewrites
# mtimes UBT reads (see apply_submission's measured note). Kept verbatim from
# the pre-delegation implementation so the delegation moves no other behaviour.
_EXTRACT_DETRITUS_SEGMENTS = frozenset(
    {"Binaries", "Intermediate", "DerivedDataCache", "Saved"}
)


def extract_writable_subset_from_project(
    project_root: Path,
    manifest: "WritableManifest",
    *,
    capture_assets: bool = False,
) -> Path:
    """Pull just the agent-SUBMITTABLE subtree out of an in-place UE project.

    Used by ``--submission-from-project``, the live-project grading lane: the
    agent edits files in a real UE project (the composed graded scratch, or the
    ``UE-projects/<Substrate>/`` checkout under ``CB_LIVE_SUBSTRATE=1``) and we
    score those edits without treating every substrate-owned file as a sandbox
    violation.

    ACCEPTANCE IS NOT DEFINED HERE. Every candidate path is decided by
    ``sandbox._is_writable`` — literally the predicate ``scan_submission`` runs
    over this function's output moments later — so "what we extract" and "what
    the sandbox accepts" are the same code, not two implementations that agree
    today. The name is bound at import (see the import block), so a rename over
    there is an ImportError here instead of a silent behaviour change.

    WHY, measured 2026-08-19. This function previously re-implemented the rule
    from ``manifest.writable`` + ``manifest.deny`` and NEVER consulted
    ``config_writable`` — while claiming in a comment to mirror
    ``sandbox._is_writable``. The identical defect in the OTHER submission
    collector (``tools/run-agent/snapshot.py``, since fixed the same way) made
    ``bp/t3-piercing-projectile`` unwinnable: run
    ``runs/unreal-mcp/20260819-034252-t3-piercing-projectile-unreal-mcp-claude-sonnet-5``
    graded FAIL with 8 of 9 L2I checks reporting the verifier saw nothing
    (``PIERCE_PRESET_MISSING name=Bullet defined=[]``) because the agent's
    correct collision vocabulary sat in the project's ``Config/DefaultEngine.ini``
    — a file the ThirdPerson manifest lists in ``config_writable`` — and the
    collector threw it away before grading. Read snapshot.py's module docstring
    for the full incident.

    ENUMERATION is still local, because a predicate cannot enumerate. What this
    function OFFERS the predicate, per manifest key:

      * ``writable``        — PREFIXES. Walk each one under ``project_root``.
      * ``config_writable`` — EXACT FILE REL-PATHS, never prefixes. Offer each
                              listed file that exists. PATH acceptance only: the
                              ini DIFF is gated afterwards against the task
                              spec's ``config_allow`` by ``config_lane``
                              (invoked in ``main``), which is the whole reason a
                              broad ``Config/`` prefix must never be added to a
                              manifest.
      * ``asset_writable``  — PREFIXES, ``.uasset``/``.umap`` only. Swept from
                              each approved existing root by ``asset_capture`` when
                              ``capture_assets`` is set: the BP-deliverable path,
                              where sub-agents author under
                              ``Content/Blueprints/``, ``Content/Abilities/``, …
                              and not only the writable ``Content/Tasks/``. The
                              caller is expected to have run
                              ``save_all_dirty_assets`` first so the in-memory
                              packages are on disk.
      * ``deny``            — PREFIXES, and DENY WINS over all three above.
                              Enforced INSIDE ``_is_writable``; deliberately not
                              re-checked here, so there is one deny rule, not two.

    A missing optional key reads as an empty tuple (``WritableManifest``'s own
    defaults), so a manifest predating ``asset_writable``/``config_writable``
    behaves exactly as it did before — pinned by
    ``tests/test_submission_from_project_rule.py::TestLegacyManifestUnchanged``.

    Anything the predicate rejects is simply not extracted. As before, this path
    can never PRODUCE a per-path sandbox violation — it can only decline to
    submit a file — which is the deliberate difference from ``--submission``.

    Returns the path to the tempdir. Caller is responsible for cleanup
    (or honoring ``--keep-workdir`` to leave it for inspection).
    """
    # Deliberately RAW mkdtemp (not new_temp_workdir): this becomes the
    # *submission* dir, which only ever gets read by sandbox.py and copied into
    # the graded workdir by this process. It is never passed to UE and never
    # becomes a -ReportExportPath, so it is outside the 2026-07-25 8.3 fix.
    out = Path(tempfile.mkdtemp(prefix="craftbench-extracted-"))

    def _offer(src: Path, rel: str) -> None:
        """Copy ``rel`` into the submission dir iff the SANDBOX accepts it.

        The only acceptance test in this function.
        """
        allowed, _reason = _sandbox_is_writable(rel, manifest)
        if not allowed:
            return
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    # (1) ``writable`` prefixes — the source/content subtree walk.
    for writable_prefix in manifest.writable:
        src = project_root / writable_prefix
        if src.is_file():
            # ``_matches_prefix`` accepts an entry that names an exact FILE, so
            # enumerate that shape too rather than silently dropping it. No
            # committed manifest uses it today (checked 2026-08-19); this exists
            # so the enumeration cannot fall behind the rule if one ever does.
            _offer(src, src.relative_to(project_root).as_posix())
            continue
        if not src.is_dir():
            continue
        for f in src.rglob("*"):
            if not f.is_file():
                continue
            rel = f.relative_to(project_root).as_posix()
            if any(seg in _EXTRACT_DETRITUS_SEGMENTS for seg in rel.split("/")):
                continue
            _offer(f, rel)

    # (2) ``config_writable`` — EXACT rel-paths. THE KEY THE OLD CODE MISSED.
    # Offered unconditionally when the file exists: this function has no
    # baseline to diff against (it sweeps the whole writable subtree, it does
    # not extract the agent's diff — see apply_submission), and an unmodified
    # ini diffs to zero changes in config_lane, so an untouched config costs a
    # copy and nothing else.
    for config_rel in manifest.config_writable:
        f = project_root / config_rel
        if f.is_file():
            _offer(f, config_rel)

    # (3) ``asset_writable`` — manifest-root .uasset/.umap sweep.
    if capture_assets:
        from asset_capture import capture_content_assets

        captured = capture_content_assets(
            project_root=project_root,
            out_dir=out,
            deny_prefixes=manifest.deny,
            allow_prefixes=tuple(manifest.asset_writable) + tuple(manifest.writable),
        )
        # asset_capture owns its own sweep AND its own copy of the asset
        # extension set, so re-run THE predicate over what it produced and drop
        # anything the sandbox would refuse. Fail-closed backstop, not a second
        # rule: a captured file the sandbox rejects would exit-4 the whole run,
        # so declining to submit it is strictly the safer direction.
        for rel in captured:
            allowed, _reason = _sandbox_is_writable(rel, manifest)
            if not allowed:
                (out / rel).unlink(missing_ok=True)
    return out


# ---------------------------------------------------------------------------
# L2 test-filter derivation
# ---------------------------------------------------------------------------


def derive_test_filter(
    task: TaskSpec,
    *,
    explicit: Optional[str] = None,
    prefix_for_map: Optional[Callable[[str], str]] = None,
) -> str:
    """Choose a UE automation-test filter for the given task.

    Strategy:
      - If ``explicit`` was passed (``--test-filter``), use it verbatim.
      - Else if the task declares a ``## Verifier fixtures`` list, build a
        ``+``-joined filter that names every fixture by
        ``Project.Functional Tests.Maps.<map>.<class>``. UE's
        ``Automation RunTests`` accepts this multi-test syntax and runs
        each in sequence (loading each map between tests).
      - Else, build one from the parsed map name and test-class hint:
        ``Project.Functional Tests.Maps.<MapName>.<TestClassNoAPrefix>``.
      - Else, fall back to the map-only filter:
        ``Project.Functional Tests.Maps.<MapName>``.

    ``prefix_for_map`` (optional) maps a map name to its automation-prefix
    segment (map_locator.MapLocation.automation_prefix): "" for root maps,
    "<folder>" for one-level-foldered maps. When it returns non-empty the
    map segment becomes ``Maps.<prefix>.<MapName>`` — mirroring UE's
    path-slashes-to-dots conversion for ``Content/Maps/<folder>/<map>.umap``.
    Default ``None`` keeps today's flat output byte-identical.

    Format verified against UE's own ``Automation List`` output:
    ``Project.Functional Tests.Maps.L_SanityTask.SanityFunctionalTest``.
    UE strips the ``/Game/`` prefix and converts path slashes to dots; it
    also strips the ``A`` prefix from AActor subclass names for the
    automation display.
    """
    if explicit:
        return explicit
    if task.fixtures:
        return "+".join(
            _filter_for_fixture(f, prefix_for_map=prefix_for_map)
            for f in task.fixtures
        )
    map_name = task.map_name or "L_Unknown"
    map_segment = _map_filter_segment(map_name, prefix_for_map)
    actor = _strip_class_prefix(task.test_class_hint or "")
    if actor:
        return f"Project.Functional Tests.Maps.{map_segment}.{actor}"
    return f"Project.Functional Tests.Maps.{map_segment}"


def _strip_class_prefix(name: str) -> str:
    """Strip the UE automation-display convention: ``ASanityFunctionalTest``
    appears as ``SanityFunctionalTest``. Spec authors may use either form."""
    if name and name[0] in ("A", "F"):
        return name[1:]
    return name


def _map_filter_segment(
    map_name: str, prefix_for_map: Optional[Callable[[str], str]]
) -> str:
    """The filter segment for a map: ``<Map>`` (root) or ``<prefix>.<Map>``."""
    if prefix_for_map is None:
        return map_name
    prefix = prefix_for_map(map_name)
    return f"{prefix}.{map_name}" if prefix else map_name


def _filter_for_fixture(
    fixture: Fixture,
    *,
    prefix_for_map: Optional[Callable[[str], str]] = None,
) -> str:
    return (
        "Project.Functional Tests.Maps."
        f"{_map_filter_segment(fixture.map_name, prefix_for_map)}."
        f"{_strip_class_prefix(fixture.test_class)}"
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="run_task.py",
        description="Apply an agent submission to the CraftBench substrate "
        "and run the verifier layers (L1 build, L2 PIE functional test).",
    )
    p.add_argument(
        "--task",
        required=True,
        type=Path,
        help="Path to the task spec .md — either the legacy flat "
        "tasks/<id>.md or the folder form tasks/<set>/<id>/task.md.",
    )
    p.add_argument(
        "--submission",
        type=Path,
        default=None,
        help="Directory containing the agent's submitted source tree. "
        "Mutually exclusive with --submission-from-project.",
    )
    p.add_argument(
        "--submission-from-project",
        type=Path,
        default=None,
        help="Extract the submission from an in-place UE project directory "
        "(e.g. UE-projects/CraftBenchTemplate/ where Aura just made edits). "
        "Scans the project for files under the substrate's writable_paths, "
        "copies them to a tempdir, and uses that as the submission. Files "
        "outside writable_paths are silently filtered out — they're assumed "
        "to be the substrate's baseline / verifier-only / config / content "
        "rather than agent intent. Mutually exclusive with --submission.",
    )
    p.add_argument(
        "--capture-assets",
        action="store_true",
        help="(--submission-from-project) Before extracting the submission, run "
        "headless editor-Python to SAVE ALL DIRTY packages (so agent-authored "
        ".uasset files hit disk), then sweep every manifest-approved asset root "
        "for .uasset/.umap deliverables — including task Game Feature plugin "
        "Content/. Content/Maps/ stays denied. "
        "Required for BP-heavy tasks where the agent's deliverable is a Blueprint "
        "authored outside Content/Tasks/. No-op for source-only tasks.",
    )
    p.add_argument(
        "--ue-root",
        required=True,
        type=Path,
        help="Path to a UE 5.8 install (the directory containing Engine/).",
    )
    p.add_argument(
        "--substrate-overlay",
        type=Path,
        default=None,
        help="Override path to the substrate dir (defaults to "
        "<repo>/UE-projects/<resolved-substrate-name>/).",
    )
    p.add_argument(
        "--full-substrate",
        action="store_true",
        default=False,
        help="Escape hatch: stage the ENTIRE substrate Content/ tree instead "
        "of the default per-task content staging (which prunes other tasks' "
        "maps, Content/Tasks/ baselines, and OFPA mirrors from the graded "
        "workdir). Env equivalent: CB_FULL_SUBSTRATE=1. Source/ is always "
        "staged whole either way; the report records the staging mode either "
        "way (report.content_staging).",
    )
    p.add_argument(
        "--report-json",
        type=Path,
        default=None,
        help="Where to write the JSON report. Defaults to "
        "<workdir>/out/report.json.",
    )
    p.add_argument(
        "--layers",
        type=str,
        default=None,
        help="Comma-separated subset of layers to run (e.g. L1,L2). "
        "Defaults to whatever the task spec lists.",
    )
    p.add_argument(
        "--keep-workdir",
        action="store_true",
        help="Do not delete the temporary workdir on success.",
    )
    p.add_argument(
        "--strict-warnings",
        action="store_true",
        help="Fail L1 if any warning is found in agent-writable files.",
    )
    p.add_argument(
        "--test-filter",
        default=None,
        help="Override the L2 automation-test filter string. See README "
        "for the default-derivation strategy.",
    )
    p.add_argument(
        "--use-nullrhi",
        dest="use_nullrhi",
        action="store_true",
        default=True,
        help="(default) Pass -nullrhi to the editor for L2.",
    )
    p.add_argument(
        "--no-nullrhi",
        dest="use_nullrhi",
        action="store_false",
        help="Disable -nullrhi (use a real RHI for tests that need a viewport).",
    )
    p.add_argument(
        "--visible",
        action="store_true",
        default=False,
        help="Opt-in: run the L2/L2I editor legs with a REAL RHI (window-"
        "capable) instead of the headless -nullrhi default. Determinism is "
        "unaffected: -deterministic and -FPS are NEVER dropped.",
    )
    p.add_argument(
        "--capture",
        action="store_true",
        default=False,
        help="Opt-in: capture screenshots during the PIE legs — implies a real "
        "RHI (the headless -nullrhi default is disabled), appends "
        "-CraftBenchCapture to the editor command so fixtures write PNGs to "
        "Saved/CraftBench/, and sweeps them into <out>/artifacts/. Determinism "
        "is unaffected: -deterministic and -FPS are NEVER dropped.",
    )
    p.add_argument(
        "--workdir",
        type=Path,
        default=None,
        help="Use this path as the workdir root (must not exist). "
        "Default: a fresh tempdir.",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Where the layer outputs (l1_build.log, l2_pie.log, l2_report, "
        "report.json) are written. Default: <workdir>/out. Set this to a path "
        "OUTSIDE the workdir to keep the logs/report after the workdir is "
        "cleaned — e.g. so a warm-cache verify (whose workdir is a shared slot, "
        "or a cold tempdir that gets deleted) still leaves a readable L2 log.",
    )
    p.add_argument(
        "--substrate-from-live",
        action="store_true",
        default=_env_truthy("CRAFTBENCH_SUBSTRATE_FROM_LIVE"),
        help="DEBUG: copy the substrate from the LIVE working tree instead of "
        "from git HEAD. The default (git HEAD) materializes only committed "
        "files so the verdict cannot depend on uncommitted/untracked disk state "
        "(stability fixes F1/F3/F4). Forcing live-copy reintroduces that "
        "dependency. Also settable via CRAFTBENCH_SUBSTRATE_FROM_LIVE=1.",
    )
    # (--regen-verifier-hashes / --regen-substrate-hashes were REMOVED together
    # with the verifier-hash manifest gate; git provenance via pinning.py
    # substrate_revision replaced it. Exit code 3 is retired/reserved.)
    # T025 — harness adapter selector + model identifier (FR-002 pinning).
    # Defaults preserve the existing reference-solution flow: --harness
    # filesystem requires --submission; --harness aura/bare_llm drive a
    # real harness instead. --model is consumed by the harness adapter
    # AND recorded in the score-report's pinning metadata.
    p.add_argument(
        "--harness",
        choices=("filesystem", "aura", "bare_llm"),
        default="filesystem",
        help="Harness adapter to drive the agent submission. "
        "'filesystem' (default) copies --submission verbatim (the "
        "discrimination-check / reference-solution flow). 'aura' drives "
        "the Aura plugin via the file-watcher contract. 'bare_llm' drives "
        "a minimal SWE-bench-Verified-style harness directly against a "
        "model provider.",
    )
    p.add_argument(
        "--model",
        default="anthropic/claude-sonnet-4-6",
        help="Model identifier in '<provider>/<model>[@<version>]' form. "
        "Recorded in the score-report's pinning metadata per FR-002 and "
        "forwarded to the harness adapter where relevant.",
    )
    p.add_argument(
        "--aura-plugin-root",
        type=Path,
        default=None,
        help="(--harness aura) override path to the Aura plugin root. "
        "Defaults to <substrate>/Plugins/Aura.",
    )
    p.add_argument(
        "--r2",
        action="store_true",
        help="Also run the NON-GATING R2 LLM-judge advisory (tools/verify-r2) if "
        "the task carries a '## R2 advisory rubric'. The judge is firewalled from "
        "this run's deterministic verdict and never affects PASS/FAIL. Requires "
        "ANTHROPIC_API_KEY. Off by default.",
    )
    p.add_argument(
        "--r2-eval-model",
        default="claude-opus-4-8",
        help="(--r2) judge model id; MUST differ from --r2-agent-model (anti-self-grading).",
    )
    p.add_argument(
        "--r2-agent-model",
        default=None,
        help="(--r2) agent-under-test model id the judge is graded against; "
        "defaults to --model. The firewall rejects equality with --r2-eval-model.",
    )
    p.add_argument(
        "--r2-ensemble",
        type=int,
        default=3,
        help="(--r2) number of independent judges in the advisory ensemble.",
    )
    p.add_argument(
        "--lite",
        action="store_true",
        help="ITERATION MODE, NOT A GRADE. Skip L1 and run the remaining layers "
             "against the already-built binaries in a warm slot, then exit 8 "
             "(UNGRADED) whatever they report. Measured on t0: the build is "
             "~87%% of a verify, so this is the only meaningful thing a lighter "
             "mode can trim. Requires --warm-cache with a primed, current slot "
             "(prime with `cb warm-prime`) — there is nothing to run against "
             "otherwise. NEVER produces PASS/FAIL and is excluded from every "
             "pass-rate by construction; use it for prompt/agent iteration and "
             "cost measurement, never for certification.",
    )
    p.add_argument(
        "--warm-cache",
        action="store_true",
        default=_env_flag("CB_WARM_CACHE"),
        help="Seed the L1 build from a prebuilt baseline (Intermediate/Binaries) "
             "so UBT only recompiles the agent's delta. No-op (cold build) if no "
             "current baseline exists for this substrate+UE version. Prime one "
             "with build_warm_baseline.py. Honors env CB_WARM_CACHE=1.",
    )
    p.add_argument(
        "--warm-cache-dir",
        type=Path,
        default=None,
        help="Baseline cache root (default: CB_WARM_CACHE_DIR or "
             "%%LOCALAPPDATA%%/CraftBench/warm-baseline).",
    )
    # --- Lightweight-hardening flags (all opt-in; default-off) ----------------
    # With none of these passed the runner behaves byte-for-byte as before, and
    # nothing changes on non-Windows hosts.
    p.add_argument(
        "--tighten-workdir-acl",
        action="store_true",
        default=False,
        help="Windows-only, best-effort: after creating the disposable cold "
             "workdir tempdir, tighten its ACL (break inheritance, grant only "
             "the current user) via icacls. No-op off Windows / when the "
             "workdir is user-supplied; never fatal.",
    )
    p.add_argument(
        "--govern-resources",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Windows-only, best-effort: run the L1 build and L2 PIE editor "
             "under a Win32 Job Object with KILL_ON_JOB_CLOSE + a conservative "
             "memory cap, so a runaway/leaked child process tree is reaped with "
             "the grade. DEFAULT-ON; pass --no-govern-resources to opt out. "
             "Resolves to CRAFTBENCH_GOVERN_RESOURCES=1/0 for the layer modules "
             "(an env var the operator set by hand wins over this flag, in both "
             "directions). No-op off Windows; never fatal; never gates a verdict "
             "(it only reaps on OOM/timeout, which are already failures).",
    )
    # --- Windows-Sandbox containment (opt-in; default-OFF) --------------------
    # SEPARATE concern from --govern-resources: the governor caps RAM and reaps a
    # runaway process tree IN-PROCESS on the host; --sandbox re-runs the WHOLE
    # grade inside a disposable, network-disabled, hardware-virtualized Windows
    # Sandbox VM so untrusted agent C++ cannot touch the host home dir, the
    # aura-plugin junction, or the network. The governor stays the IN-VM backstop.
    p.add_argument(
        "--sandbox",
        action="store_true",
        default=False,
        help="EXPERIMENTAL, Windows Pro/Edu/Enterprise only, DEFAULT-OFF: re-run "
             "this grade inside a disposable Windows Sandbox (.wsb VM) — UE mapped "
             "read-only, a COPY of the workdir mapped read-write, networking "
             "disabled, host home + aura-plugin junction never mapped. The "
             "untrusted-agent-C++ containment step. On a host WITHOUT Windows "
             "Sandbox (e.g. Windows Home), prints a clear warning and falls back to "
             "the normal in-process grade. UNVALIDATED end-to-end — see "
             "wsb_runner.py. No-op (with warning) off a WSB-capable host.",
    )
    return p


def _env_flag(name: str) -> bool:
    """True for env vars set to a truthy value (1/true/yes/on, case-insensitive)."""
    return str(os.environ.get(name, "")).strip().lower() in {"1", "true", "yes", "on"}


_R2_RUNNER = REPO_ROOT / "tools" / "verify-r2" / "run_r2.py"


def _maybe_run_r2(
    args,
    task: TaskSpec,
    substrate_src: Path,
    out_dir: Path,
) -> Optional[dict]:
    """Run the NON-GATING R2 advisory judge as a subprocess, if requested.

    Returns the advisory block (a non-gating dict) to attach to the report, or
    ``None`` when --r2 was not set / the task has no rubric. NEVER raises and
    NEVER affects the deterministic outcome: any failure yields an error-shaped
    advisory note so the absence of a judge is visible but harmless. The judge
    runs in its own firewalled workspace (tools/verify-r2/run_r2.py) and is never
    shown this run's verdict — anti-anchoring by construction.
    """
    if not getattr(args, "r2", False):
        return None
    if "## R2 advisory rubric" not in task.raw_text:
        return None
    if not _R2_RUNNER.exists():
        return {"status": "error", "gating": False, "note": f"R2 runner missing: {_R2_RUNNER}"}

    agent_model = args.r2_agent_model or args.model
    out_json = out_dir / "r2-advisory.json"
    cmd = [
        sys.executable, str(_R2_RUNNER),
        "--task", str(task.source_path),
        "--submission", str(args.submission),
        "--substrate", str(substrate_src),
        "--agent-model", str(agent_model),
        "--eval-model", str(args.r2_eval_model),
        "-n", str(args.r2_ensemble),
        "--out", str(out_json),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=1800)
    except Exception as e:  # noqa: BLE001 — advisory is best-effort, never fatal
        return {"status": "error", "gating": False, "note": f"R2 subprocess failed: {e}"}
    if proc.returncode != 0 or not out_json.exists():
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-3:]
        return {"status": "error", "gating": False,
                "note": "R2 judge did not complete: " + " | ".join(tail)}
    try:
        payload = json.loads(out_json.read_text(encoding="utf-8"))
        advisory = payload.get("advisory")
        if not isinstance(advisory, dict) or advisory.get("gating") is True:
            return {"status": "error", "gating": False, "note": "R2 produced no non-gating advisory"}
        return advisory
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "gating": False, "note": f"R2 advisory unreadable: {e}"}


def _maybe_dispatch_to_sandbox(args) -> Optional[int]:
    """If ``--sandbox`` is set, try to run the grade inside a Windows Sandbox.

    Returns:
      * an int exit code when the grade was DISPATCHED into a sandbox (the caller
        returns it directly), OR
      * ``None`` to mean "continue the normal in-process grade" — either because
        ``--sandbox`` was not set, or because this host can't run a sandbox and we
        chose the friendlier fallback-with-warning over aborting.

    Containment-prototype scope (see wsb_runner.py): this builds the ``.wsb`` and
    launches it. Propagating the in-VM verdict/report back to the host is NOT yet
    wired, so a successful launch returns 0 with a clear note rather than the
    contained grade's real PASS/FAIL. This keeps the prototype honest about what
    it does and does not yet do.
    """
    if not getattr(args, "sandbox", False):
        return None

    import wsb_runner  # local import keeps the module optional / lazy

    if not wsb_runner.windows_sandbox_available():
        print(
            "WARNING: --sandbox requested but Windows Sandbox is not available: "
            f"{wsb_runner.unavailable_reason()}",
            file=sys.stderr,
        )
        print(
            "info: falling back to the normal IN-PROCESS grade (no VM containment). "
            "The in-process job_governor still provides the RAM/kill backstop. To "
            "get real containment, run on a Windows Pro/Edu/Enterprise host (or CI) "
            "with the Windows Sandbox feature enabled.",
            file=sys.stderr,
        )
        return None  # fallback-with-warning: continue the host-side grade

    # WSB available: stage a workdir copy + the verifier tools, build the spec,
    # and launch. (The full host-side materialization — clone substrate, apply
    # submission, stage tools/verify-single/ — is intentionally left to the real
    # integration; this prototype demonstrates the dispatch + config contract.)
    print(
        "info: --sandbox: Windows Sandbox available; dispatching the grade into a "
        "disposable VM (UE read-only, workdir-copy read-write, networking disabled).",
        file=sys.stderr,
    )
    forbidden = wsb_runner.default_forbidden_paths(repo_root=REPO_ROOT)
    # The in-VM grade re-invokes run_task.py against the mapped workdir copy; pass
    # through the task path + the same submission flags, MINUS --sandbox.
    passthrough: list[str] = ["--task", str(args.task)]
    if args.submission:
        passthrough += ["--submission", str(args.submission)]
    spec = wsb_runner.WsbSpec(
        ue_root_host=args.ue_root.resolve(),
        # In real wiring this is the staged workdir COPY; for the prototype we
        # point at the substrate source so the spec is well-formed end-to-end.
        workdir_copy_host=(args.substrate_overlay or REPO_ROOT / "UE-projects" / "CraftBenchTemplate").resolve(),
        extra_run_task_args=tuple(passthrough),
        forbidden_paths=forbidden,
    )
    launch = wsb_runner.run_grade_in_sandbox(spec)
    if not launch.launched:
        print(f"ERROR: --sandbox dispatch failed: {launch.note}", file=sys.stderr)
        print("info: falling back to the normal IN-PROCESS grade.", file=sys.stderr)
        return None
    print(f"info: {launch.note}", file=sys.stderr)
    print(
        "info: in-VM verdict propagation is not yet wired (prototype). Inspect the "
        "report.json the in-VM grade writes to the read-write mapped workdir copy.",
        file=sys.stderr,
    )
    return 0


def _apply_visible_capture(args) -> None:
    """--visible / --capture imply a real RHI for the editor legs.

    Both flags need the scene to actually render (a window for --visible; PNG
    content for --capture), which -nullrhi prevents. Mutates
    ``args.use_nullrhi`` in place; a no-op when neither flag is set, so the
    headless -nullrhi default is untouched. Determinism switches
    (-deterministic / -FPS) are owned by run_l2 and are never dropped.
    """
    if getattr(args, "visible", False) or getattr(args, "capture", False):
        args.use_nullrhi = False


def _apply_task_rhi(args, task: TaskSpec) -> None:
    """Honor a task-owned real-RHI requirement.

    The command-line default remains ``-nullrhi`` for every existing task.
    A spec may tighten that environment with ``rhi: real``; callers such as
    refgate and discriminate do not need a private argument seam, and an
    explicit real-RHI CLI request remains compatible.  A task requirement is
    never weakened by an explicit/default ``--use-nullrhi``.
    """
    if task.rhi in {"real", "d3d11"}:
        args.use_nullrhi = False


def _gating_layer_requires(registry=None) -> dict[str, tuple[str, ...]]:
    """``{key: requires}`` for every GATING layer in the registry.

    Read off the registry rather than hand-copied, so adding a layer to
    layers/registry.py automatically extends the guards below. Advisory layers
    (R2, gating=False) are EXCLUDED on purpose: they never land in ``layers_out``
    by construction, so listing them would make "declared but absent" fire on
    every ``layers:`` list that mentions R2.
    """
    if registry is None:
        from layers.registry import REGISTRY as registry
    return {layer.key: tuple(layer.requires) for layer in registry if layer.gating}


def harness_error_reasons(
    layers_out: Mapping[str, LayerReport],
    requested_layers: Iterable[str],
    registry=None,
) -> list[str]:
    """Reasons the harness could NOT produce a verdict for this run (may be []).

    A non-empty result means the run is a HARNESS ERROR: exit
    ``EXIT_HARNESS_ERROR`` and a non-graded verdict, NOT a graded agent FAIL.
    Every predicate here is STRUCTURAL — layer keys, statuses, exit codes and the
    registry's declared dependencies. None of them reads note prose: the two
    producers of a "skipped" LayerReport differ only in their notes text, and
    gating a verdict on a note string is unacceptably brittle.

    The predicates:

    1. ``layers_out`` is EMPTY. ``overall`` is ``all(status == "pass" for ...)``
       and ``all({})`` is True, so an empty gating set grades a vacuous PASS at
       exit 0 with ``"layers": {}`` in report.json. A spec naming only L4/L5
       (RECOGNIZED_LAYERS but unimplemented) reaches exactly this shape.
    2. A requested token that IS an implemented gating layer produced no key.
       The declared gate silently did not run, so the grade is narrower than the
       spec claims (e.g. ``--layers L1,L2I`` on a task with no introspect
       scripts; a legacy ``- ART`` line with no ``artifact:`` param).
    3. L1 did not pass, carries ``build_tool_never_ran``, AND its exit code is one
       of l1_build's synthesized "no build process ever ran" codes
       (``L1_HARNESS_ERROR_EXITS``): 127, FileNotFoundError launching the UBT
       script / editor binary, or 126, a target that produced no trace on two
       consecutive spawns.

       Both conjuncts are required because the code alone is FORGEABLE:
       ``Build.cs`` sits inside the sandbox writable prefix, so a submission can
       exit the build tool with any status it likes and buy itself a non-graded
       verdict for no work. The flag is a structural field only l1_build's own
       fault paths set — the same shape the L2 predicates below use, and for the
       same reason.

       Note the deliberate asymmetry with 124 (the governed timeout), which stays
       a graded FAIL — a pathological submission (runaway template instantiation,
       a generated translation unit that never finishes) CAN hang a compile, so
       routing 124 here would hand every agent an opt-out of the denominator:
       hang the build and be excluded instead of scored. Ambiguity resolves
       toward GRADED.
    4. A gating layer whose status is "skipped" while every dependency it
       declares PASSED (or is absent, mirroring run_layers' own predicate). That
       is the layer having actually RUN and counted nothing — "no tests
       discovered" — which is a verifier/spec fault, not agent behavior.

       Predicate 4 is dependency-structural for a load-bearing reason:
       registry.run_layers emits status="skipped" for EVERY dependent of a failed
       layer, so "L2 is skipped" is the shape of an ordinary L1 compile failure
       too. Keying harness-error on the status alone would move every compile
       failure in the benchmark out of the denominator — strictly worse than the
       bug being fixed. When the dependency did NOT pass, the skip is downstream
       of a graded agent failure and MUST stay a graded FAIL.
    5. A gating layer whose status is ``LAYER_STATUS_ERROR`` and whose exit_code
       is not in ``LAYER_ERROR_GRADED_EXITS``. "error" is not a third grade: it
       is a layer saying its VERDICT CHANNEL produced nothing to read. L2I is
       the only producer today — layers/l2_introspect.py fail-safes to it when
       the verifier-owned script is MISSING, when the editor binary is absent,
       or when the run emitted no parseable verdict block (no block / malformed
       JSON / no ``checks`` list). Every one of those is a VERIFIER-owned
       artifact being wrong, so collapsing them to "fail" (registry.py did, up
       to this change) scored a typo in a grader as a model failure — exactly
       what the verdict contract forbids.

       Why this is on the harness side of the line that keeps predicate 3's L1
       exit 124 and predicate 4's zero-test L2 GRADED: those two are shapes that
       an ordinary AGENT failure also produces on the normal path — a
       pathological submission can hang a compile, and a submission that
       compiles and then crashes PIE lands on tests_run==0. Their ambiguity is
       between "harness broke" and "agent broke", and it resolves toward GRADED.
       An L2I "error" is not ambiguous in that way: it is raised BEFORE any
       agent-derived predicate is evaluated, by the channel that carries the
       verdict rather than by the verdict, and l2_introspect never reaches it
       from a check's content (a script that runs and reports failing checks
       returns "fail", never "error"). The one producer an agent CAN reach — the
       governed timeout, since agent C++ is linked into the editor this layer
       launches — is carved back out by LAYER_ERROR_GRADED_EXITS, so 124 stays
       graded here for the same reason it does at L1.

       KNOWN NARROWING (accepted, 2026-07-27): agent code crashing that editor
       before the verdict block is printed also yields "error" with a non-124
       exit code, and is therefore routed here. Distinguishing it needs the same
       signal predicate 4 is waiting on — l2_introspect already computes
       ``result_source`` ("json" | "none") but ``LayerReport`` cannot carry it.
       The exposure is bounded in a way predicate 4's is not: L2I runs a
       READ-ONLY editor-Python introspection pass, never PIE, so it never ticks
       gameplay — the modal crash surface (BeginPlay, timers, movement) is not
       executed at all. When result_source is exported, narrow this to
       ``result_source != "none" or the script was never launched``.
    """
    requires_by_key = _gating_layer_requires(registry)
    requested = tuple(requested_layers)
    reasons: list[str] = []

    # (1) empty gating set -> vacuous PASS
    if not layers_out:
        reasons.append(
            "no gating verifier layer produced a verdict — `overall` would be "
            "a vacuous PASS (all({}) is True). requested layers: "
            f"{list(requested)}; implemented gating layers: "
            f"{sorted(requires_by_key)}"
        )

    # (2) a requested, implemented, gating layer that produced no key
    missing = [k for k in requested if k in requires_by_key and k not in layers_out]
    if missing:
        reasons.append(
            "requested gating layer(s) produced no verdict and were silently "
            f"dropped from `overall`: {', '.join(missing)}"
        )

    # (3) L1 never got a build process to run. Provenance first: the exit code is
    #     only a label on a fault l1_build itself declared.
    l1 = layers_out.get("L1")
    if (
        l1 is not None
        and l1.status != "pass"
        and getattr(l1, "build_tool_never_ran", False)
        and l1.exit_code in L1_HARNESS_ERROR_EXITS
    ):
        reasons.append(_L1_HARNESS_ERROR_REASONS[l1.exit_code])

    # (4) DELIBERATELY NOT IMPLEMENTED — "a gating layer ran and counted nothing"
    #     is NOT currently routed here, and the reason is worth keeping so nobody
    #     re-adds it casually (2026-07-26 review).
    #
    #     The tempting predicate is: L2 status=="skipped" while every declared
    #     dependency PASSED. That is dependency-structural (good — it correctly
    #     leaves an L1-compile-failure's downstream skip as a graded FAIL), but it
    #     is still too broad by one case: an agent whose code COMPILES and then
    #     CRASHES the PIE editor also lands on tests_run==0 -> status="skipped"
    #     with L1 passing. Routing that here would move crash-failures out of the
    #     denominator, i.e. reward crashing over failing an assertion — the same
    #     defect family as the compile-failure bug, one layer down, and directly
    #     contrary to the "ambiguity resolves toward GRADED" rule that keeps L1
    #     exit 124 graded above.
    #
    #     Distinguishing the two needs the signal l2_pie ALREADY computes but does
    #     not export: `L2Result.result_source` ("json" | "stdout-fallback" |
    #     "none", l2_pie.py:78). "none" means the editor never produced an
    #     automation result at all (crash / never started); a real source with
    #     tests_run==0 means automation genuinely ran and matched no test, which is
    #     the verifier/spec fault this predicate was meant to catch. `LayerReport`
    #     (report.py:19-29) carries no such field, so wiring it means adding one —
    #     a report.json schema change, which this change set deliberately avoids
    #     (a clean run's report.json stays byte-identical today).
    #
    #     Note the editor exit code is NOT a usable substitute: on the normal
    #     success path `_run_editor_with_marker_kill` TERMINATES the editor once it
    #     sees a terminal marker, so `proc.returncode` is nonzero on healthy runs
    #     (l2_pie.py:229). Any `exit_code == 0` conjunct would be wrong.
    #
    #     Until `result_source` is exported, a zero-test L2 stays a graded FAIL.
    #     That is the conservative direction: it never excuses an agent.
    #
    #     STILL TRUE, and predicate (4b) below does NOT change it. `result_source`
    #     turned out to be insufficient anyway: an agent that crashes the editor
    #     mid-test and a GPU that dies mid-test BOTH yield "none". Measured
    #     2026-08-10 — the failing rep's test had already printed "Test Started"
    #     when the editor died, so "never started" does not separate them either.

    # (4b) The GPU refused the editor a resource. NARROW carve-out of the case
    #      above, and the ONLY one that does not risk excusing an agent.
    #
    #      Agent C++ runs in GAMEPLAY; it does not allocate render targets. A
    #      `CreateCommittedResource` refusal / OutOfVideoMemory / DEVICE_REMOVED is
    #      the machine's condition, so it cannot be manufactured by submission
    #      content the way a PIE crash can. `l2_pie` classifies it where the log is
    #      already in hand and exports `LayerReport.rhi_unavailable`, so this stays
    #      structural — no predicate here reads note prose.
    #
    #      Measured 2026-08-10 (runs/aura-product/bp-g2__gp-glide-stamina-cpp-
    #      20260810-164355): L1 PASSED both targets, the model shipped 4 files, the
    #      test was discovered AND started, then
    #      `LogD3D12RHI: Error: CreateCommittedResource(...) failed` killed the
    #      editor. tests 0/0, exit 3 -> graded FAIL against the model. Sweeping all
    #      146 recorded reports found 3 with (L1 pass AND L2 tests_run == 0); the
    #      one with exit 124 is a governed timeout and MUST stay graded, which is
    #      why the conjunct below excludes LAYER_ERROR_GRADED_EXITS.
    #
    #      Deliberately requires tests_run == 0: a GPU hiccup that still produced a
    #      complete result set is a real verdict and stays graded.
    for key in sorted(layers_out):
        if key not in requires_by_key:
            continue
        lr = layers_out[key]
        if not getattr(lr, "rhi_unavailable", False):
            continue
        if (lr.tests_run or 0) != 0:
            continue
        if lr.exit_code in LAYER_ERROR_GRADED_EXITS:
            continue
        reasons.append(
            f"{key}: the GPU refused the editor a resource (RHI allocation "
            "failure) and no test result was produced — a machine fault, not "
            "submission content. NB the certified L2 environment is `-nullrhi`; "
            "if this ran on the full-RHI fallback, read l2_pie_nullrhi.log for "
            "why the headless attempt produced nothing"
        )

    # (4c) The editor exited before it started the test it had already QUEUED.
    #      Second narrow carve-out, same doctrine as (4b) and the same
    #      requirement: it must be a condition the submission cannot manufacture.
    #
    #      The queue line proves our filter MATCHED. What follows it — the
    #      controller finding a worker and starting the test — is entirely
    #      harness-side; NOTHING of the submission has executed at that point.
    #      Contrast the agent-reachable case, which this file already records at
    #      the note above: an agent that crashes the editor mid-test "had already
    #      printed Test Started". Started-then-died is the agent's; queued-and-
    #      never-started is ours.
    #
    #      Measured 2026-08-11 (runs/aura-product/bp-g2__gp-glide-stamina-cpp-
    #      20260811-010729): L1 PASSED both targets, the model shipped 4 files
    #      over 43 tool calls, and L2 logged
    #        Automation: RunTests='...GlideStaminaFunctionalTest' Queued.
    #        Automation: Quit Command Queued.            <- 2ms later
    #        LogAutomationWorker: Received FindWorkersMessage   <- +770ms, exit
    #      tests 0/0 -> graded FAIL against the model. Across the same task's
    #      three logs, `Test Started` was present on both PASSing reps and
    #      absent here — the discriminator is structural, not prose.
    #
    #      Same conjuncts as (4b): zero tests only (a run that produced a
    #      complete result set is a real verdict), and never over a governed
    #      timeout, which must stay graded.
    for key in sorted(layers_out):
        if key not in requires_by_key:
            continue
        lr = layers_out[key]
        if not getattr(lr, "queued_never_started", False):
            continue
        if (lr.tests_run or 0) != 0:
            continue
        if lr.exit_code in LAYER_ERROR_GRADED_EXITS:
            continue
        reasons.append(
            f"{key}: the test was QUEUED (so the filter matched) but the editor "
            "ended before starting it. No submission code had run at that "
            "point, so this is a machine fault and not a model result. The "
            "CAUSE of the early exit is not yet established — see "
            "l2_pie._queued_never_started for what has been ruled out"
        )

    # (4d) A fixture finished through EFunctionalTestResult::Error — it declared
    #      that the HARNESS could not set the test up. Third carve-out, same
    #      doctrine as (4b)/(4c): the condition must be one the submission cannot
    #      manufacture.
    #
    #      What makes that true here is not the enum by itself but a corpus-wide
    #      INVARIANT, established by the 2026-08-14 audit
    #      (the ::Error tag audit) and approved under charter §3.4: every
    #      ::Error whose guard read agent-writable state was retagged ::Failed —
    #      19 sites across 12 tasks, the seed case being a fixture that counted
    #      actors by a tag stamped in an agent-writable constructor, where
    #      deleting one line was a denominator opt-out. After that pass the
    #      surviving ::Error sites are exactly three shapes: 29 `no UWorld
    #      available` guards, one unresolvable CDO, and two provably-unreachable
    #      fixture state-machine assertions.
    #
    #      So this predicate is only as sound as that invariant. Any NEW ::Error
    #      must name the owner of every input its guard reads; if any input sits
    #      under an agent-writable prefix the gate belongs at ::Failed, or this
    #      code starts excusing submissions. That rule is in the authoring
    #      checklist for exactly this reason.
    #
    #      Conjuncts are the same two as (4b)/(4c), and `tests_run == 0` is doing
    #      real work here rather than being copied for symmetry. _TEST_RESULT_RE
    #      counts only Passed|Failed|Skipped, so an Error-finished test does not
    #      increment the tally: tests_run == 0 is precisely "no graded outcome was
    #      recorded", i.e. the Error was the whole story.
    #
    #      It is ALSO the conservative choice under the one thing here that is
    #      unverified — whether UE's index.json records an Error-finished test as
    #      a countable result. If it does, tests_run > 0, this predicate declines,
    #      and the run stays GRADED. The uncertainty therefore fails toward
    #      grading, never toward excusing a submission, which is the direction the
    #      conservatism rule demands. (Do NOT reach for tests_failed: LayerReport
    #      carries only tests_run and tests_passed, so a tests_failed conjunct
    #      reads as 0 always and silently does nothing.)
    for key in sorted(layers_out):
        if key not in requires_by_key:
            continue
        lr = layers_out[key]
        if not getattr(lr, "harness_precondition", False):
            continue
        if (lr.tests_run or 0) != 0:
            continue
        if lr.exit_code in LAYER_ERROR_GRADED_EXITS:
            continue
        reasons.append(
            f"{key}: a fixture finished through EFunctionalTestResult::Error and "
            "no graded test result was recorded. That enum means the harness could "
            "not set the test up — the submission was never in a position to be "
            "graded. See the ::Error tag audit for the invariant this "
            "relies on"
        )

    # (4d) the editor produced NO OUTPUT AT ALL — a zero-byte log plus a
    #      non-timeout exit, i.e. it died before opening its own log, so neither
    #      the test nor the submission ever ran.
    #
    #      This is the ONLY one of the four structural signals a submission
    #      cannot reach: (4a)/(4b)/(4c) all match text in a log agent C++ shares,
    #      while this one keys on the log being EMPTY, and agent code executes
    #      only after the log is open. A submission cannot forge its own absence.
    #
    #      Same two guard conjuncts as (4c) and for the same reasons: tests_run
    #      == 0 so a run that banked a real outcome keeps it, and the
    #      LAYER_ERROR_GRADED_EXITS carve-out so the governed timeout (124) stays
    #      GRADED — a pathological submission can hang the editor, and voiding a
    #      hang would be an opt-out needing no submission content.
    #
    #      Found 2026-08-17 by reading a real run rather than by reasoning: both
    #      L2 legs 0 bytes, no UECC dump, exit 0xC0000142, L1 PASS, all three
    #      sibling flags False — and `overall: FAIL` charged to the model.
    for key in sorted(layers_out):
        if key not in requires_by_key:
            continue
        lr = layers_out[key]
        if not getattr(lr, "editor_never_started", False):
            continue
        if (lr.tests_run or 0) != 0:
            continue
        if lr.exit_code in LAYER_ERROR_GRADED_EXITS:
            continue
        reasons.append(
            f"{key}: the editor produced a zero-byte log and exited "
            f"{lr.exit_code} — it never reached the point of opening its own "
            "log, so the test never ran and the submission was never executed. "
            "This is a machine/environment fault, not submission content"
        )

    # (5) a gating layer whose VERDICT CHANNEL produced nothing (status
    #     "error"), minus the governed-timeout carve-out. Keyed on the status
    #     and the registry's gating set, never on the layer key, so a second
    #     adopter of the fail-safe needs no change here.
    for key in sorted(layers_out):
        if key not in requires_by_key:
            continue
        lr = layers_out[key]
        if lr.status != LAYER_STATUS_ERROR:
            continue
        if lr.exit_code in LAYER_ERROR_GRADED_EXITS:
            continue
        reasons.append(
            f"{key} status=error (exit {lr.exit_code}): the verifier-owned "
            "grader produced no readable verdict — missing script / no verdict "
            "block / malformed JSON. This is a verifier fault, not submission "
            "content"
        )

    return reasons


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    # Fill in the repo's .env CRAFTBENCH_* tuning BEFORE any layer reads it.
    # `cb` already exports these (aura_rig.stack.load_aura_env), but the
    # documented no-cb path (the no-cb path) had none of the
    # guardrails: without CRAFTBENCH_L1_MAX_PARALLEL the L1 editor-PCH compiles
    # run at full parallelism and exhaust a 32 GB box's commit charge -> C3859 /
    # exit 6. An explicitly-set var still wins; see repo_env for precedence.
    _applied_env = repo_env.load_repo_env(REPO_ROOT)
    if _applied_env:
        print(f"[env] {REPO_ROOT / '.env'}: applied "
              + ", ".join(f"{k}={v}" for k, v in sorted(_applied_env.items())))
    _apply_visible_capture(args)
    started = time.monotonic()
    # Wall-clock accounting for the runner's own phases. Descriptive only —
    # nothing it records reaches `overall`. The block it emits always closes
    # against `duration_seconds` via a derived `unaccounted` entry, so a phase
    # nobody instrumented is visible instead of merely absent (phase_timer.py).
    phases = PhaseTimer()

    # --sandbox (opt-in): if set AND the host can run a Windows Sandbox, re-run the
    # grade inside the disposable VM and return its dispatch result. Otherwise this
    # is a no-op (returns None) and the normal in-process grade proceeds below.
    _sandbox_rc = _maybe_dispatch_to_sandbox(args)
    if _sandbox_rc is not None:
        return _sandbox_rc

    # Wire --govern-resources to the env var the layer modules read. This keeps
    # the layers (l1_build / l2_pie / job_governor) decoupled from argparse: they
    # gate purely on CRAFTBENCH_GOVERN_RESOURCES + os.name == "nt". DEFAULT-ON —
    # the governor is active unless explicitly opted out (--no-govern-resources or
    # CRAFTBENCH_GOVERN_RESOURCES=0/false). An env var the operator set by hand is
    # AUTHORITATIVE and wins over the flag default in both directions; only when
    # the env is unset/blank does the resolved flag pick the 1/0 value. The
    # governor itself stays a Windows-only, fail-open, NON-GATING backstop — it can
    # only reap on OOM/timeout (already failures), so default-on never flips a
    # normal grade's verdict.
    _gov_env = os.environ.get("CRAFTBENCH_GOVERN_RESOURCES")
    if _gov_env is None or _gov_env.strip() == "":
        os.environ["CRAFTBENCH_GOVERN_RESOURCES"] = (
            "1" if getattr(args, "govern_resources", True) else "0"
        )

    # Validate submission-source flags.
    if args.submission and args.submission_from_project:
        print(
            "ERROR: --submission and --submission-from-project are mutually exclusive",
            file=sys.stderr,
        )
        return EXIT_USAGE
    if not args.submission and not args.submission_from_project:
        print(
            "ERROR: one of --submission or --submission-from-project is required",
            file=sys.stderr,
        )
        return EXIT_USAGE

    # A malformed spec is a config/usage error (exit 2), NEVER a graded FAIL
    # (exit 1) — the rig's VERDICT map reads 1 as an agent FAIL, so an uncaught
    # ValueError traceback here would mis-record spec-authoring bugs as agent
    # failures in run summaries/matrices.
    try:
        task = parse_task_spec(args.task)
    except ValueError as exc:
        print(f"ERROR: task spec malformed: {exc}", file=sys.stderr)
        return EXIT_USAGE

    _apply_task_rhi(args, task)
    if task.rhi in {"real", "d3d11"}:
        print(f"info: task execution contract requires {task.rhi} RHI")

    substrate_dir_name = _substrate_dir_name(task.substrate)
    substrate_src = args.substrate_overlay or (
        REPO_ROOT / "UE-projects" / substrate_dir_name
    )
    if not substrate_src.exists():
        print(f"ERROR: substrate not found at {substrate_src}", file=sys.stderr)
        return EXIT_USAGE

    manifest_path = substrate_src / "AGENT_WRITABLE.json"
    if not manifest_path.exists():
        print(
            f"ERROR: AGENT_WRITABLE.json missing at {manifest_path}",
            file=sys.stderr,
        )
        return EXIT_USAGE
    manifest = WritableManifest.load(manifest_path)

    # Resolve the submission source. If --submission-from-project was passed,
    # extract the writable subtree to a tempdir and use that.
    extracted_dir: Optional[Path] = None
    if args.submission_from_project:
        if not args.submission_from_project.exists():
            print(
                f"ERROR: --submission-from-project path does not exist: {args.submission_from_project}",
                file=sys.stderr,
            )
            return EXIT_USAGE
        # BP-deliverable capture: flush dirty in-memory packages to disk BEFORE
        # extraction, so agent-authored Blueprints (which sub-agents leave dirty)
        # become real .uasset files the sweep can see. Best-effort — a save
        # failure never blocks the run; we score whatever IS on disk.
        if args.capture_assets:
            from asset_capture import save_all_dirty_assets

            proj_uproject = (
                args.submission_from_project / f"{substrate_dir_name}.uproject"
            )
            # Timed: this LAUNCHES AN EDITOR to flush dirty packages, so it is
            # one of the most expensive non-layer steps in a grade — and it only
            # exists on the --submission-from-project path, which is why it was
            # invisible until an aura-product run exercised it.
            with phases.phase("capture_save_dirty"):
                save_res = save_all_dirty_assets(
                    ue_root=args.ue_root,
                    project_path=proj_uproject,
                    log_path=Path(tempfile.gettempdir()) / "craftbench-save-dirty.log",
                )
            print(
                f"info: save-all-dirty {save_res.status} "
                f"(exit {save_res.exit_code}, {save_res.duration_seconds:.0f}s)"
            )
            for n in save_res.notes:
                print(f"  {n}")
        # Timed separately from the save above: under --capture-assets this
        # sweeps ALL of Content/, so on an asset-heavy substrate it is a real
        # cost and needs its own number to be arguable from data.
        with phases.phase("extract_submission"):
            extracted_dir = extract_writable_subset_from_project(
                args.submission_from_project, manifest,
                capture_assets=args.capture_assets,
            )
        print(
            f"info: extracted {sum(1 for _ in extracted_dir.rglob('*') if _.is_file())} "
            f"file(s) from {args.submission_from_project} into {extracted_dir}"
        )
        args.submission = extracted_dir

    # Decide which layers to run.
    requested_layers = (
        tuple(s.strip().upper() for s in args.layers.split(",")) if args.layers else task.layers
    )
    if not requested_layers:
        print(
            "ERROR: task spec did not declare any verifier layers and --layers "
            "was not passed",
            file=sys.stderr,
        )
        return EXIT_USAGE

    # --lite: iteration mode. L1 is REMOVED from requested_layers rather than
    # merely skipped at run time, because harness_error_reasons' predicate (2)
    # fires on "a requested gating layer produced no key" — and here that is the
    # POINT of the mode, not a gate that silently failed. Dropping the token
    # keeps the harness-error taxonomy honest instead of carving an exception
    # into it.
    lite = bool(getattr(args, "lite", False))
    if lite:
        if not getattr(args, "warm_cache", False):
            print(
                "ERROR: --lite requires --warm-cache. Skipping L1 means the "
                "remaining layers need binaries somebody else built, and a cold "
                "workdir is materialized from git HEAD, which carries no "
                "Binaries/. Prime a slot (`cb warm-prime`) and re-run with "
                "--warm-cache.",
                file=sys.stderr,
            )
            return EXIT_USAGE
        requested_layers = tuple(l for l in requested_layers if l != "L1")
        if not requested_layers:
            print(
                "ERROR: --lite leaves this task with no layers to run (its spec "
                "declares L1 only), so there is nothing to iterate on.",
                file=sys.stderr,
            )
            return EXIT_USAGE

    # Build the workdir.
    # WARM mode (opt-in) uses a fixed, reusable slot built at a stable absolute
    # path — UBT bakes absolute paths into its build cache, so an incremental
    # build is only valid at the path the baseline was built at. The slot is
    # RESET to pristine each verify (not recreated), preserving isolation while
    # keeping Intermediate/Binaries. Warm never blocks and never changes a
    # verdict: a busy slot or stale/missing baseline falls back to cold, and
    # --workdir / --substrate-from-live force cold. See warm_cache.py.
    warm_slot = None
    warm_reset = None
    # The warm baseline is always built Aura-disabled (the grading config), so
    # warm mode is incompatible with --harness aura (which needs Aura enabled).
    _warm_eligible = (
        getattr(args, "warm_cache", False)
        and not args.workdir
        and not args.substrate_from_live
        and args.harness != "aura"
    )
    if _warm_eligible:
        import warm_cache as _wc

        # .resolve() the user-supplied --warm-cache-dir for the same reason
        # default_cache_root() canonicalizes its own branches: a slot under this
        # root becomes the UE project path AND the -ReportExportPath parent, and
        # an 8.3 short component there scores the whole batch 0/N
        # (FAILURE-LOG 2026-07-25). No-op when the value is already canonical.
        cache_root = (args.warm_cache_dir.resolve() if args.warm_cache_dir
                      else _wc.default_cache_root())
        warm_slot, warm_reason = _wc.try_acquire_any(
            _wc.slot_root(cache_root, substrate_dir_name),
            substrate_tree_sha=_wc.substrate_tree_sha(substrate_src, repo_root=REPO_ROOT),
            ue_version=_detect_ue_version(args.ue_root),
            writable_prefixes=tuple(manifest.writable) + tuple(manifest.asset_writable),
            ue_root=args.ue_root,
        )
        if warm_slot is None:
            print(f"info: warm-cache MISS ({warm_reason}) — cold build")
            if lite:
                # A cold fallback is harmless for a normal warm run (it just
                # builds) but FATAL for --lite: with no slot there are no
                # binaries, so every remaining layer would fail for want of an
                # editor and the run would look like the submission's fault.
                print(
                    f"ERROR: --lite has nothing to run against — {warm_reason}. "
                    f"Prime the pool with `cb warm-prime` (a stale slot is the "
                    f"usual cause: the baseline is keyed on the substrate git "
                    f"tree SHA, so any substrate commit invalidates it).",
                    file=sys.stderr,
                )
                return EXIT_USAGE
    elif getattr(args, "warm_cache", False):
        print("info: warm-cache ignored (forced cold by --workdir / "
              "--substrate-from-live / --harness aura)")

    # Catch-all, deliberately OUTSIDE the eligibility branches above: --workdir /
    # --substrate-from-live / --harness aura all force cold WITHOUT reaching the
    # miss path, and a lite run with no slot has no binaries at all. One check
    # here covers every route into that state instead of one per branch.
    if lite and warm_slot is None:
        print(
            "ERROR: --lite has no warm slot to run against (forced cold by "
            "--workdir / --substrate-from-live / --harness aura, or the pool is "
            "unprimed). Drop those flags and prime with `cb warm-prime`.",
            file=sys.stderr,
        )
        return EXIT_USAGE

    if warm_slot is not None:
        workdir = warm_slot.slot_dir
        workdir_substrate = warm_slot.substrate_path
        out_dir = warm_slot.out_dir
        workdir_owns_tempdir = False
    elif args.workdir:
        if args.workdir.exists():
            print(
                f"ERROR: --workdir {args.workdir} already exists; choose a fresh path",
                file=sys.stderr,
            )
            return EXIT_USAGE
        # Resolve to absolute: the derived -project= path is handed to UBT,
        # whose cwd is the Engine tree — a relative workdir fails there with
        # "Unable to find project file" (FAILURE-LOG 2026-07-22).
        workdir = args.workdir.resolve()
        workdir.mkdir(parents=True)
        workdir_substrate = workdir / substrate_dir_name
        out_dir = workdir / "out"
        out_dir.mkdir(parents=True, exist_ok=True)
        workdir_owns_tempdir = False
    else:
        # CANONICAL, never raw mkdtemp: an 8.3 short component here (%TEMP% =
        # C:\Users\SHORT~1\...) propagates into -ReportExportPath and takes the
        # whole batch to 0/N. See new_temp_workdir's docstring for the
        # 2026-07-25 four-run testbed that isolated it from MAX_PATH.
        workdir = new_temp_workdir()
        workdir_substrate = workdir / substrate_dir_name
        out_dir = workdir / "out"
        out_dir.mkdir(parents=True, exist_ok=True)
        workdir_owns_tempdir = True
        # Opt-in (--tighten-workdir-acl): lock the disposable cold workdir down to
        # the current user. Scoped to THIS mkdtemp dir only (asserted under the
        # system temp root we just created it in), Windows-only, best-effort, and
        # never fatal — a failed ACL tighten must not abort a grade. Skipped for
        # warm slots and user-supplied --workdir (those branches don't reach here).
        if getattr(args, "tighten_workdir_acl", False):
            _maybe_tighten_workdir_acl(workdir)

    # --out-dir overrides where layer logs/report land, decoupling them from the
    # workdir lifecycle (so warm-slot and deleted-cold-tempdir verifies still
    # leave a readable L2 log for callers like `cb discriminate`).
    if getattr(args, "out_dir", None) is not None:
        # .resolve() for the same reason new_temp_workdir() does it: out_dir
        # becomes `report_dir = out_dir / "l2_report"`, i.e. the editor's
        # -ReportExportPath. A caller that mints its own temp dir under an 8.3
        # %TEMP% and hands it here would reproduce the 2026-07-25 batch-eval
        # 0/15 exactly — `cb discriminate --warm-cache` did (it passes
        # `--out-dir <mkdtemp>/out`, bypassing the --workdir branch that has
        # always resolved). Canonicalizing at THIS consumption point heals
        # every caller at once, whatever they pass.
        out_dir = args.out_dir.resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

    report_json_path = args.report_json or (out_dir / "report.json")
    # Bound BEFORE the try so the `finally`'s evidence pass cannot NameError on
    # a run that raised before run_layers() returned. `{}` is a no-op there, and
    # nothing between here and the assignment at run_layers() reads it.
    layers_out: Mapping[str, LayerReport] = {}

    try:
        # 1) Materialize the substrate. COLD: clone from git HEAD into the fresh
        #    workdir (only committed files enter the graded tree). WARM: the slot
        #    already holds a built clone — reset its agent-writable dirs to
        #    pristine (drops the previous submission, keeps Intermediate/Binaries)
        #    so this verify starts from clean source.
        with phases.phase("stage_substrate"):
            if warm_slot is not None:
                warm_reset = warm_slot.reset_to_pristine()
                # Warm baselines are primed from git HEAD (build_warm_baseline uses
                # the default copy_substrate path) and warm is forced cold under
                # --substrate-from-live, so a warm slot is always git-provenance.
                substrate_source = "git-head"
            else:
                substrate_source = copy_substrate(
                    substrate_src,
                    workdir_substrate,
                    from_live=args.substrate_from_live,
                )

            # 1b) Per-task CONTENT staging (default ON): prune other tasks'
            #     maps, Content/Tasks/ baselines, and OFPA mirrors from the
            #     freshly staged Content/ so the graded project carries only
            #     what THIS task needs. CONTENT-ONLY — Source/ stays whole
            #     (the L1 build compiles every CraftBenchTests fixture, and
            #     fixtures #include their scaffolds). Applies on BOTH branches:
            #     the cold clone above and the warm slot (whose reset restores
            #     the full pristine Content/ each verify, so a prune here never
            #     leaks into the next task's grade). Fail-open by contract —
            #     any derivation error stages the full substrate with a note,
            #     because a wrongly-excluded map is a false L2 FAIL scored
            #     against the model. NON-GATING: recorded in the report
            #     (content_staging), never consulted by any verdict.
            if full_substrate_requested(getattr(args, "full_substrate", False)):
                content_staging = StagingResult(
                    mode=MODE_FULL,
                    excluded=(),
                    notes=(
                        "full substrate requested "
                        "(--full-substrate / CB_FULL_SUBSTRATE=1)",
                    ),
                )
            else:
                content_staging = stage_per_task_content(
                    workdir_substrate,
                    task,
                    REPO_ROOT / "tasks",
                    substrate_dir_name,
                    substrate_alias=_substrate_dir_name,
                )
                content_staging = _stage_scoped_task_plugins(
                    workdir_substrate, task.task_id, content_staging)
            print(
                f"info: content staging: {content_staging.mode} "
                f"({len(content_staging.excluded)} entries excluded)"
            )
            for _cs_note in content_staging.notes:
                print(f"  content-staging: {_cs_note}")

            # NOTE: verify-time scaffold isolation is intentionally NOT performed.
            # The L1 build compiles the verifier-owned CraftBenchTests module,
            # whose per-task fixtures #include the task scaffold headers —
            # removing the foreign scaffolds here breaks the verifier's own
            # compile. There is also no fairness benefit at verify time
            # (the submission is already authored). Decoy isolation belongs in the
            # agent DRIVE phase, which fairness.stage_task_isolation_hide handles.
            # staging.py remains a unit-tested building block for a future
            # drive-time integration. See memory: hardening-prototype.

        # 1a) Per-task UE config overlay (B7): append any verifier-owned
        #     tasks/<set>/<id>/ue-config/*.ini fragments onto the freshly
        #     materialized workdir's Config/ (both paths: cold clone above,
        #     warm slot just reset to pristine). No-op for tasks without an
        #     ue-config/ dir. Since the 2026-07-29 config lane, Config/ is no
        #     longer wholesale agent-denied: a task that BOTH stages a
        #     verifier ue-config overlay AND allows agent edits to the same
        #     file diffs the agent's submission against the OVERLAID baseline
        #     (the overlay is the task's starting config) — see step 3a.
        with phases.phase("config_overlay"):
            overlay_applied = _stage_config_overlay(
                args.task, workdir_substrate, task.task_id
            )
        if overlay_applied:
            print(
                "info: applied per-task UE config overlay: "
                + ", ".join(overlay_applied)
            )

        # 2) (RETIRED) The verifier-hash integrity gate lived here and exited 3
        #    on drift. It was removed with verifier_hashes.json: the graded tree
        #    is materialized from git HEAD (substrate_source above), so git is
        #    the provenance and pinning.py records substrate_revision. Exit code
        #    3 stays RESERVED (never reused); a "live" substrate_source marks
        #    the run uncertified in the report instead of aborting.

        # 3) Sandbox the submission.
        _t_sandbox = time.monotonic()
        sandbox_result = scan_submission(args.submission, manifest)
        # 3a) Semantic config lane (2026-07-29): a path-accepted Config/ file
        #     is only truly accepted if its ini DIFF against the workdir
        #     substrate stays inside the task spec's `config_allow` allowlist.
        #     The diff baseline deliberately includes any verifier ue-config
        #     overlay staged in step 1.5 — that overlay IS the task's starting
        #     config. Violations are SANDBOX-REJECT class (agent-chosen
        #     submission property -> the existing exit-4 path below); a
        #     malformed `config_allow` entry is a SPEC error -> exit 2, never
        #     graded.
        try:
            config_rules = parse_config_allow(task.config_allow)
        except ValueError as e:
            print(f"ERROR: malformed config_allow entry in task spec: {e}",
                  file=sys.stderr)
            return EXIT_USAGE
        for rel, reason in validate_config_submission(
            sandbox_result.accepted, workdir_substrate, config_rules
        ):
            sandbox_result.violations.append(
                Violation(
                    submission_path=Path(args.submission) / rel,
                    rel_path=rel,
                    reason=reason,
                )
            )
        enforce_exact_accepted_files(
            sandbox_result, args.submission, task.accepted_files
        )
        # Recorded by hand rather than with `phases.phase(...)` so the span
        # survives the early return above (a malformed `config_allow` is a
        # SPEC error, exit 2 — never billed as sandbox time). The config-lane
        # diff validation IS sandbox semantics, so it bills into this span.
        phases.record("sandbox", time.monotonic() - _t_sandbox)
        print(sandbox_result.render_report())
        if not sandbox_result.ok:
            # Write a minimal report so callers always see a JSON artifact.
            _rejected_after = time.monotonic() - started
            report = _violation_report(
                task=task,
                sandbox=sandbox_result,
                duration_seconds=_rejected_after,
                ue_version=_detect_ue_version(args.ue_root),
                substrate_source=substrate_source,
                content_staging=content_staging.to_dict(),
                phases=phases.to_dict(_rejected_after),
            )
            report.write_json(report_json_path)
            print(report.render_text())
            return EXIT_SANDBOX_REJECT

        # 4) Apply the submission into the workdir substrate copy.
        with phases.phase("apply_submission"):
            apply_submission(
                args.submission, workdir_substrate, sandbox_result.accepted
            )
        # Accepted rel-paths, doing double duty: the L2I asset-integrity
        # preamble validates each submitted asset (identity + no-redirector)
        # inside the grading editor session, and --lite uses them to refuse a
        # submission carrying compile inputs.
        submitted_rel_files = tuple(rel for _, rel in sandbox_result.accepted)

        # --lite's two ways of producing a WRONG answer rather than a weaker one.
        # Both are REFUSALS, not warnings: each one makes the layer results
        # describe a binary that has nothing to do with this submission, and a
        # warning printed above a green "L2 1/1" is not a defence — the 2026-07-31
        # measurement run proved that by passing t0 on the previous grade's build.
        lite_notes: list[str] = []
        if lite:
            # (a) The submission carries source. --lite runs no compiler, so that
            #     source cannot possibly be under test.
            _compile_inputs = tuple(
                r for r in submitted_rel_files
                if r.lower().endswith((".cpp", ".h", ".hpp", ".cc", ".cxx",
                                       ".inl", ".cs"))
            )
            if _compile_inputs:
                print(
                    f"ERROR: --lite cannot grade this submission — it contains "
                    f"{len(_compile_inputs)} compile input(s) and --lite runs no "
                    f"build, so every layer below would test OTHER code: "
                    + ", ".join(sorted(_compile_inputs)[:5])
                    + ("…" if len(_compile_inputs) > 5 else "")
                    + ". --lite is for asset/structural submissions (the kp- "
                      "rows carry 0 C++ files); use a normal grade for source.",
                    file=sys.stderr,
                )
                return EXIT_USAGE
            # (b) The slot's binaries must have been built from THIS source tree.
            #     After any warm grade the slot holds that grade's compiled code,
            #     so reusing it without building would inherit the previous
            #     submission's behaviour — observed live 2026-07-31, when a lite
            #     run passed t0 on the preceding grade's build.
            #
            #     The test is content identity, not "is the slot pristine": what
            #     makes the binaries correct is that they were compiled from the
            #     bytes now on disk, and that is true after a normal warm grade of
            #     an asset-only submission just as much as after a fresh prime.
            #     Keying on PRISTINE would reject that case for no reason — and,
            #     worse, would ACCEPT a pristine-labelled slot whose build had
            #     been reaped halfway.
            import warm_cache as _wc_mod
            _fp_lite = _wc_mod.compile_input_fingerprint(
                workdir_substrate, warm_slot.writable_prefixes
            )
            _fp_built = _wc_mod.read_compile_fingerprint(warm_slot.slot_dir)
            if _fp_built != _fp_lite:
                _built_from = _wc_mod.read_binaries_state(warm_slot.slot_dir)
                print(
                    f"ERROR: --lite refuses this warm slot — its binaries were "
                    f"built from a DIFFERENT source tree (slot fingerprint "
                    f"{(_fp_built or 'none/incomplete build')!r}, this tree "
                    f"{_fp_lite[:12]!r}, last built from {_built_from!r}), so "
                    f"the layers would test other code. Re-prime with "
                    f"`cb warm-prime --warm-force`. A lite run never builds, so "
                    f"it never invalidates a slot — one prime serves an entire "
                    f"iteration loop.",
                    file=sys.stderr,
                )
                return EXIT_USAGE
            lite_notes.append(
                f"--lite: NO BUILD RAN. The slot's binaries were compiled from "
                f"this exact source tree (fingerprint {_fp_lite[:12]}) and the "
                f"submission carries no compile inputs, so the layers below did "
                f"test the right code — but nothing verified that it COMPILES, "
                f"which is why this run is UNGRADED by construction."
            )

        # 4a) WARM mode: force UBT to recompile the agent's overlaid sources by
        #     bumping their mtimes strictly newer than every cached artifact (the
        #     correctness gate — without it, a broken submission could reuse a
        #     baseline .obj and falsely PASS). L1 then builds incrementally at the
        #     slot's stable path. Must run AFTER apply_submission.
        if warm_slot is not None and lite:
            # The bump exists solely to make UBT recompile. --lite runs no build,
            # so bumping would only churn mtimes across every writable file for
            # nothing. Skipping it is also SAFE across runs: the next verify to
            # take this slot resets to pristine and bumps before building, so it
            # can never inherit a stale .obj from a lite run's overlay.
            print("info: --lite — skipping the warm mtime bump (no build to force)")
        elif warm_slot is not None:
            import warm_cache as _wc_state
            reset_note = (
                f"reset {warm_reset.prefixes_restored} prefix(es)"
                if warm_reset is not None else "no reset"
            )
            # CONTENT-KEYED BUMP. The bump makes every writable source look newer
            # than every object file, which forces UBT to recompile the whole
            # writable module — the reason a warm verify measured SLOWER than a
            # cold one (173.7s vs 104.3s on t0, 2026-07-31). It is only NEEDED
            # when the compile inputs actually differ from what produced the
            # cached objects, and content identity answers that exactly: same
            # bytes in, same objects valid. Different (or unknown) -> bump, i.e.
            # the old behaviour, so this can only ever skip redundant work.
            #
            # This does NOT weaken the grade. L1 still runs, still builds both
            # targets, still fails when it should; UBT's dependency graph remains
            # the authority on what to rebuild. The harness simply stops lying to
            # it about mtimes when it has no reason to.
            with phases.phase("warm_fingerprint"):
                _files_now = _wc_state.compile_input_hashes(
                    workdir_substrate, warm_slot.writable_prefixes
                )
                _fp_now = _wc_state.compile_input_fingerprint(
                    workdir_substrate, warm_slot.writable_prefixes
                )
            _fp_cached = _wc_state.read_compile_fingerprint(warm_slot.slot_dir)
            _files_built = _wc_state.read_compile_files(warm_slot.slot_dir)
            _sources_unchanged = (
                _fp_cached is not None and _fp_cached == _fp_now
            )
            # Mark the slot dirty BEFORE building: a build reaped mid-flight has
            # already overwritten object files. compile_fingerprint=None here is
            # what makes a crashed build untrusted until one SUCCEEDS below.
            _wc_state.write_binaries_state(
                warm_slot.slot_dir, hash_submission(args.submission),
                compile_fingerprint=None,
            )
            if _sources_unchanged:
                print(
                    f"info: warm-cache HIT — {reset_note}; compile inputs "
                    f"IDENTICAL to the cached build (fp {_fp_now[:12]}) — "
                    f"skipping the mtime bump, L1 builds incrementally"
                )
            else:
                # PER-FILE, not the whole tree. Bumping everything was correct
                # but far too coarse: a t0 eval changed TWO files and UBT
                # recompiled 28 actions because the harness claimed all 53 were
                # new — 1.35x where an unchanged tree gets 26x. We now name only
                # the files whose bytes differ from the ones that produced the
                # cached objects and let UBT's dependency graph decide what that
                # implies. When the cache's provenance is unknown (a slot primed
                # before per-file hashes, or a build that never completed),
                # changed_compile_inputs returns EVERY file — the old behaviour,
                # and the safe direction.
                _to_bump = _wc_state.changed_compile_inputs(
                    _files_now, _files_built
                )
                with phases.phase("warm_mtime_bump"):
                    bump = warm_slot.bump_files(_to_bump)
                print(
                    f"info: warm-cache HIT — {reset_note}, compile inputs "
                    f"CHANGED — bumped {bump.overlaid_touched} of "
                    f"{len(_files_now)} compile input(s); L1 rebuilds only what "
                    f"UBT derives from them"
                )
                for n in bump.notes:
                    print(f"  warm-cache: {n}")

        # 4b) Disable the Aura plugin in the cloned workdir's .uproject when
        # the harness is NOT 'aura'. The Aura plugin's native Mac module
        # fails to load in the verifier's automation invocation (the failure
        # is specific to the non-headless code path; Aura's own headless
        # mode works correctly per tools/scripts/aura_smoke.py). Without
        # this patch, UE prints "模块'Aura'无法被加载" / "Module 'Aura'
        # failed to load" and calls EngineExit() before the L2 automation
        # framework can discover any tests, producing a spurious tests=0/0
        # SKIPPED result. For aura-harness runs we leave Aura enabled
        # because the harness depends on it.
        project_path = workdir_substrate / f"{substrate_dir_name}.uproject"
        # In WARM mode the slot's .uproject was Aura-disabled at prime time and
        # reset never touches it, so re-disabling would only rewrite the file
        # (bumping its mtime) and risk a spurious full rebuild — skip it.
        if args.harness != "aura" and warm_slot is None:
            _disable_plugin_in_uproject(project_path, "Aura")

        # 5) Run layers.
        if not project_path.exists():
            print(
                f"ERROR: .uproject not found at {project_path}", file=sys.stderr
            )
            return EXIT_NO_UPROJECT

        # 5) Run the verification layers via the pluggable registry. Each layer
        #    decides if it applies, declares gating + dependencies, and returns a
        #    LayerReport; advisory (non-gating) layers route to advisory_out.
        from layers.base import LayerContext
        from layers.registry import run_layers

        layer_ctx = LayerContext(
            task=task,
            args=args,
            project_path=project_path,
            workdir_substrate=workdir_substrate,
            out_dir=out_dir,
            manifest=manifest,
            substrate_src=substrate_src,
            requested_layers=set(requested_layers),
            submitted_files=submitted_rel_files,
        )
        with phases.phase("layers"):
            layers_out, advisory_out = run_layers(layer_ctx)

        # Now — and only now — the slot's object files correspond to a source
        # tree we can name. Recorded ONLY on a PASSING L1: a failed or reaped
        # build leaves the fingerprint None from the pre-build write above, so
        # the next verify distrusts the cache and bumps, exactly as it should.
        if warm_slot is not None and not lite:
            _l1_report = layers_out.get("L1")
            if _l1_report is not None and _l1_report.status == "pass":
                _wc_state.write_binaries_state(
                    warm_slot.slot_dir,
                    hash_submission(args.submission),
                    compile_fingerprint=_fp_now,
                    compile_files=_files_now,
                )

        # 5a) Lift swept screenshot artifacts into the report: the L2 --capture
        #     sweep writes "visual_artifacts" and the L3 render layer writes both
        #     that and its legacy "L3_visual" key. Deduped + sorted; paths are
        #     run-dir-relative ("artifacts/<name>"). Empty when neither ran, so
        #     the report JSON omits the key and stays byte-identical.
        artifacts = sorted({
            str(p)
            for key in ("visual_artifacts", "L3_visual")
            for p in (advisory_out.get(key) or [])
        })

        # 5b) HARNESS-ERROR gate — runs BEFORE `overall` is computed, because two
        #     of the shapes it catches would otherwise be scored as a real
        #     verdict: an empty gating set grades a vacuous PASS (all({}) is
        #     True), and a layer that ran but counted nothing grades a FAIL that
        #     no measurement supports. Every predicate is structural; see
        #     harness_error_reasons for the per-predicate argument (notably why
        #     L1-failed short-circuits stay a graded FAIL).
        harness_errors = harness_error_reasons(layers_out, requested_layers)

        # 6) Compose final report. `overall` is computed from the GATING layers
        #    ALONE (advisory layers are absent from layers_out), so no advisory
        #    value can flip it.
        if harness_errors:
            overall = OVERALL_HARNESS_ERROR
            for reason in harness_errors:
                print(f"ERROR: harness could not grade this run: {reason}",
                      file=sys.stderr)
        elif lite:
            # UNCONDITIONAL, and checked BEFORE the pass/fail computation so that
            # value is never even formed. A lite run that happens to pass every
            # layer it ran is still not a PASS: it never built the code. Ordering
            # this after a pass/fail branch would leave a "pass" string one
            # refactor away from reaching the report.
            overall = OVERALL_UNGRADED
        else:
            overall = "pass" if all(
                lr.status == "pass" for lr in layers_out.values()
            ) else "fail"
        # FR-002 provenance anchor: pin WHICH substrate commit was graded
        # ("git-head" alone names a moving target). Best-effort — a non-git
        # tree records None and the report stays well-formed.
        # Everything the report needs but does not yet have: the provenance
        # anchor (a git call), the submission content hash (walks + hashes every
        # graded file) and the UE version probe. Grouped into one timed phase so
        # `unaccounted` is left holding only the JSON write and the stdout
        # render, which is what makes the block's remainder interpretable.
        with phases.phase("compose_report"):
            substrate_revision = None
            try:
                from pinning import git_revision_for
                _rr = _resolve_repo_root_for(substrate_src)
                if _rr is not None:
                    substrate_revision = git_revision_for(substrate_src, repo_root=_rr)
            except Exception:
                substrate_revision = None
            submission_sha = hash_submission(args.submission)
            ue_version = _detect_ue_version(args.ue_root)
        _total_seconds = time.monotonic() - started
        report = Report(
            task_id=task.task_id,
            submission_sha=submission_sha,
            layers=layers_out,
            overall=overall,
            duration_seconds=round(_total_seconds, 2),
            ue_version=ue_version,
            host=HostInfo(os=platform.system().lower(), arch=platform.machine()),
            sandbox_violations=0,
            graded_at=_now_stamp(),
            r2_advisory=advisory_out.get("R2"),
            artifacts=artifacts,
            substrate_source=substrate_source,
            substrate_revision=substrate_revision,
            content_staging=content_staging.to_dict(),
            phases=phases.to_dict(_total_seconds),
            notes=lite_notes,
        )
        report.write_json(report_json_path)
        print(report.render_text())
        print(f"json report: {report_json_path}")

        if overall == OVERALL_HARNESS_ERROR:
            return EXIT_HARNESS_ERROR
        if overall == OVERALL_UNGRADED:
            return EXIT_UNGRADED
        return EXIT_PASS if overall == "pass" else EXIT_FAIL
    finally:
        if warm_slot is not None:
            warm_slot.release()
        # Diagnostic-only, and deliberately ABOVE the rmtree: that cleanup is
        # verdict-blind, so this is the last moment a failed layer's log exists.
        # Fail-open in both directions — the report is already written, and
        # nothing here can reach `overall`. See failure_evidence.py for the
        # measured incident that motivated it.
        try:
            failure_evidence.preserve(
                layers_out,
                report_json_path=report_json_path,
                workdir=workdir,
            )
        except Exception:  # noqa: BLE001
            pass
        if not args.keep_workdir and workdir_owns_tempdir:
            robust_rmtree(workdir, log=print)
        elif args.keep_workdir:
            print(f"workdir preserved at: {workdir}")
        # Clean up the extracted-from-project tempdir unless --keep-workdir.
        if extracted_dir is not None and not args.keep_workdir:
            robust_rmtree(extracted_dir, log=print)
        elif extracted_dir is not None and args.keep_workdir:
            print(f"extracted submission preserved at: {extracted_dir}")


def _violation_report(
    *,
    task: TaskSpec,
    sandbox: SandboxResult,
    duration_seconds: float,
    ue_version: str,
    substrate_source: Optional[str] = None,
    content_staging: Optional[dict] = None,
    phases: Optional[dict] = None,
) -> Report:
    return Report(
        task_id=task.task_id,
        submission_sha="rejected",
        layers={
            "sandbox": LayerReport(
                status="fail",
                notes=[v.render() for v in sandbox.violations],
            )
        },
        overall="fail",
        duration_seconds=round(duration_seconds, 2),
        ue_version=ue_version,
        host=HostInfo(os=platform.system().lower(), arch=platform.machine()),
        sandbox_violations=len(sandbox.violations),
        graded_at=_now_stamp(),
        substrate_source=substrate_source,
        content_staging=content_staging,
        phases=phases,
    )


def _maybe_tighten_workdir_acl(workdir: Path) -> None:
    """Windows-only, best-effort ACL tighten of the disposable cold workdir.

    Breaks ACL inheritance and grants Full control to ONLY the current user via
    ``icacls``. This is a defense-in-depth measure for the throwaway grading
    tempdir; it is opt-in (``--tighten-workdir-acl``) and MUST never abort a
    grade — any failure (icacls missing, non-zero exit, OS refusal) is logged and
    swallowed.

    Safety: only ever runs against the freshly-created ``mkdtemp`` workdir, which
    is asserted to live under the system temp root. It is NEVER applied to a
    user-supplied ``--workdir`` or a warm slot (those code paths don't call this).
    """
    if os.name != "nt":
        return
    # Path-prefix guard: refuse to touch anything that is not under the system
    # temp root we just created the workdir in. mkdtemp() roots in
    # tempfile.gettempdir(); resolve both and compare so a symlinked/relative
    # path can't escape the assertion.
    #
    # BOTH SIDES MUST STAY RESOLVED (FAILURE-LOG 2026-07-25). Since
    # new_temp_workdir() canonicalizes, `workdir` arrives here in LONG form
    # (C:\Users\<user>\...) while raw gettempdir() on this host is the 8.3
    # SHORT form (C:\Users\SHORT~1\...). Dropping the .resolve() on `temp_root`
    # would make the two incomparable, the guard would false-reject a perfectly
    # legitimate workdir, and --tighten-workdir-acl would silently stop
    # tightening. Do not "simplify" either .resolve() away.
    try:
        temp_root = Path(tempfile.gettempdir()).resolve()
        target = workdir.resolve()
        if not (target == temp_root or temp_root in target.parents):
            print(
                f"WARNING: --tighten-workdir-acl skipped; workdir {target} is not "
                f"under the system temp root {temp_root}",
                file=sys.stderr,
            )
            return
    except OSError as exc:  # pragma: no cover — path resolution should not fail
        print(f"WARNING: --tighten-workdir-acl path check failed ({exc}); skipped",
              file=sys.stderr)
        return

    username = os.environ.get("USERNAME") or os.environ.get("USER") or ""
    if not username:
        print("WARNING: --tighten-workdir-acl skipped; no USERNAME in environment",
              file=sys.stderr)
        return

    cmd = [
        "icacls", str(target),
        "/inheritance:r",
        "/grant:r", f"{username}:(OI)(CI)F",
    ]
    try:
        # icacls speaks the ANSI codepage on localized Windows - never strict-decode
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=60)
    except (FileNotFoundError, OSError, subprocess.SubprocessError) as exc:
        print(f"WARNING: --tighten-workdir-acl icacls failed to run ({exc}); "
              "continuing with default ACL", file=sys.stderr)
        return
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip()
        print(f"WARNING: --tighten-workdir-acl icacls exited {proc.returncode} "
              f"({tail}); continuing with default ACL", file=sys.stderr)
        return
    print(f"info: tightened workdir ACL on {target} (inheritance broken; "
          f"granted {username} full control)")


def _detect_ue_version(ue_root: Path) -> str:
    """Best-effort UE version detection from ``Engine/Build/Build.version``."""
    build_version = ue_root / "Engine" / "Build" / "Build.version"
    if not build_version.exists():
        return "unknown"
    try:
        data = json.loads(build_version.read_text(encoding="utf-8"))
        return ".".join(
            str(data.get(k, "")) for k in ("MajorVersion", "MinorVersion", "PatchVersion")
        ).rstrip(".")
    except (json.JSONDecodeError, OSError):
        return "unknown"


def cli(argv: Optional[list[str]] = None) -> int:
    """Process entry point: ``main()`` plus a last-resort harness-error trap.

    An uncaught exception used to leave the process exit code to Python — 1 —
    which every harness path reads as a GRADED agent FAIL. A verifier that
    crashed measured nothing, so the crash was silently scored against the agent
    and counted in the pass-rate denominator. Here it becomes exit
    ``EXIT_HARNESS_ERROR`` (non-graded) with the traceback still on stderr.

    The traceback is the whole diagnostic: a crash this deep writes NO
    report.json, which is exactly why adapters.base.verdict_from_verifier
    consults the exit code BEFORE looking for a report.

    ``main()`` keeps its own contract (it returns int and lets exceptions
    propagate) so tests can still assert on raised errors; only the process
    boundary swallows them. SystemExit/KeyboardInterrupt are BaseException and
    deliberately pass straight through.
    """
    try:
        return main(argv)
    except Exception:  # noqa: BLE001 — the crash trap is the point
        import traceback

        traceback.print_exc()
        print(
            "ERROR: the verifier crashed before producing a verdict; exiting "
            f"{EXIT_HARNESS_ERROR} (HARNESS-ERROR, NOT graded as an agent FAIL)",
            file=sys.stderr,
        )
        return EXIT_HARNESS_ERROR


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(cli())

"""doctor — the READ-ONLY, per-tier environment diagnostic behind ``cb doctor``.

Same shape as :mod:`aura_rig.envgate`: a PURE
CORE over an INJECTABLE-SEAMS dataclass plus a THIN WRAPPER (``cb.cmd_doctor``)
that resolves the live facts. :func:`diagnose` is a pure function over a single
:class:`Probe` literal of pre-resolved plain values + one ``which`` callable; it
touches NOTHING but its argument — no filesystem, no env, no network — so
``tests/test_cb_doctor.py`` runs fully offline (no UE, no stack, no real ``.env``).

The split is load-bearing: ``cb doctor`` (this module) NEVER mutates — it only
reports, stamping ``safe_autofix=True`` on the one check that is safe for the
setup layer (``tools/scripts/setup_craftbench.py``) to heal: the ``.env`` copy.
Setup is the only layer allowed to act; the diagnoser describes.

TWO CUMULATIVE tiers, in dependency order (the higher includes the lower):
  * **grade-only** — grade tasks deterministically: harness Python, git, tar,
                     UE 5.8, and the committed substrate.
  * **baseline**   — grade-only + the ``claude`` CLI + ``ANTHROPIC_API_KEY`` +
                     a ``.env`` at the craftbench root (the CLI/key pair is WARN
                     at check level — absent it blocks the baseline verdict,
                     never grading).

There used to be a THIRD ``full-rig`` tier here, and its removal is deliberate.
It probed the private rig behind the ``aura-mcp`` arm — a closed-source UE
plugin, two servers that are not published, an entitled vendor account and that
plugin's built editor module. None of it ships in this repository. The
``aura-mcp`` arm is still dispatchable and still documented, but it is DISCLOSED
BUT NOT REPRODUCIBLE from a public clone, and a readiness tier for a lane nobody
outside can bring up is worse than no line at all: it reports a wall of FAILs on
a machine that is perfectly healthy for everything this repo CAN run, and sends
the reader hunting for a checkout that does not exist.

Verdicts are cumulative — a tier reads READY only when it AND every tier below
it is clean; otherwise the blockers are attributed to their own tier, e.g.
``baseline: blocked by grade-only (ue)``.

Exit policy (advisory only — see :meth:`Diagnosis.exit_code`): 0 iff the HIGHEST
tier the machine is *provisioned for* is READY; non-zero is a soft signal.
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

# Canonical user-facing tier names, lowest first (the ONLY tier vocabulary —
# README / setup key on these two; the private-rig 'full-rig' tier was removed
# for the public release, see the module docstring).
_TIER_ORDER = ("grade-only", "baseline")

# --------------------------------------------------------------------------- #
# (1) Probe — the injected-facts dataclass (analog of preflight.Seams).        #
#     The wrapper resolves every live fact (filesystem, env, HTTP snapshot)    #
#     and packs it here; tests build a Probe literal with fakes.               #
# --------------------------------------------------------------------------- #

@dataclass
class Probe:
    # --- grade-only ---
    py_exe: Optional[str]                      # ctx.py_exe (None => no harness python)
    which: Callable[[str], Optional[str]]      # shutil.which seam (git / tar)
    ue: Optional[Path]                         # ctx.ue (None => UnrealEditor not found)
    uproject_exists: bool
    # --- baseline (claude-p agent) ---
    claude_cli: Optional[str]                  # which('claude'|'claude.cmd'|'claude.exe') pre-resolved
    env_keys: Dict[str, Optional[str]]         # {ANTHROPIC_API_KEY} (placeholders pre-nulled)
    env_present: bool
    # --- machine telemetry (rides OUTSIDE every tier gate — never a verdict) ---
    live_coding: int = 0                       # count_image('LiveCodingConsole') — informational only


# --------------------------------------------------------------------------- #
# (2) Check — one per-line result (no status logic baked in).                  #
# --------------------------------------------------------------------------- #

@dataclass
class Check:
    id: str
    label: str
    tier: str             # 'grade-only' | 'baseline' (see _TIER_ORDER)
    status: str           # 'PASS' | 'FAIL' | 'WARN'
    detail: str           # human one-liner; for secrets reports PRESENCE only, never the value
    fix_hint: str         # exact command / doc pointer (text only; doctor never acts on it)
    safe_autofix: bool = False  # advisory flag the SKILL machine-reads; doctor never acts on it


# --------------------------------------------------------------------------- #
# (3) Diagnosis — grouping + per-tier verdict + exit policy.                   #
# --------------------------------------------------------------------------- #

@dataclass
class Diagnosis:
    checks: List[Check] = field(default_factory=list)

    def by_tier(self, tier: str) -> List[Check]:
        return [c for c in self.checks if c.tier == tier]

    def get(self, check_id: str) -> Optional[Check]:
        for c in self.checks:
            if c.id == check_id:
                return c
        return None

    # The baseline WARNs that STILL gate the baseline verdict, by id. Naming
    # them beats "every WARN in the tier": `env-file` also lives in baseline and
    # is WARN, but it must NOT block — real_probe falls back to os.environ, so a
    # box that exports ANTHROPIC_API_KEY without ever writing a `.env` is fully
    # baseline-ready and saying otherwise is a false blocker.
    _BASELINE_GATING_WARNS = ("claude-cli", "anthropic-key")

    def tier_missing(self, tier: str) -> List[str]:
        """Check ids the tier ITSELF is missing. FAILs always count; the baseline
        pair (claude-cli / anthropic-key) is WARN severity yet still gates the
        baseline verdict — absent, it blocks baseline, never grading."""
        out = [c.id for c in self.by_tier(tier) if c.status == "FAIL"]
        if tier == "baseline":
            out += [c.id for c in self.by_tier(tier)
                    if c.status == "WARN" and c.id in self._BASELINE_GATING_WARNS]
        return out

    def tier_verdict(self, tier: str) -> str:
        """CUMULATIVE verdict: READY only when this tier AND every tier below it
        is clean; blockers are attributed to the tier they belong to.

        A tier name this build no longer defines degrades to a plain sentence
        instead of raising. That guard exists for exactly one reason: callers
        outside this module (tools/scripts/setup_craftbench.py) enumerate the
        tier names as a LITERAL list, and the public release dropped the
        private-rig 'full-rig' tier. A stale caller must print an honest line,
        not blow up a setup run with `tuple.index(x): x not in tuple`."""
        if tier not in _TIER_ORDER:
            return "not applicable (tier not defined by this build)"
        own = self.tier_missing(tier)
        below = [(t, self.tier_missing(t))
                 for t in _TIER_ORDER[:_TIER_ORDER.index(tier)]]
        below = [(t, ids) for t, ids in below if ids]
        if not own and not below:
            warns = [c for c in self.by_tier(tier) if c.status == "WARN"]
            return "READY" + (f" ({len(warns)} warning(s))" if warns else "")
        parts: List[str] = []
        if own:
            parts.append(f"{len(own)} blocker(s) ({', '.join(own)})")
        parts.extend(f"blocked by {t} ({', '.join(ids)})" for t, ids in below)
        if own and below:
            return parts[0] + "; also " + "; ".join(parts[1:])
        return "; ".join(parts)

    def tier_ready(self, tier: str) -> bool:
        """CUMULATIVE: ready iff this tier and every tier below it are clean.
        A tier this build no longer defines has nothing to block on (see
        :meth:`tier_verdict`), so it reads ready rather than raising."""
        if tier not in _TIER_ORDER:
            return True
        idx = _TIER_ORDER.index(tier)
        return not any(self.tier_missing(t) for t in _TIER_ORDER[:idx + 1])

    def provisioned_tier(self) -> str:
        """The HIGHEST tier the machine shows REAL provisioning signals for — this
        decides which tier's readiness the exit code reflects.

          * baseline   — a real ANTHROPIC_API_KEY (the claude CLI alone is not a
                         signal — Claude Code drops it on grade-only boxes too;
                         and NEVER mere .env presence: setup auto-creates .env on
                         every fresh clone, so it signals nothing).
          * grade-only — everything else.
        """
        anth = self.get("anthropic-key")
        if anth and anth.status == "PASS":
            return "baseline"
        return "grade-only"

    def exit_code(self) -> int:
        """0 iff the highest provisioned-for tier is CUMULATIVELY READY, else 1.
        The baseline WARN pair gates only the baseline verdict — a WARN never
        blocks grade-only. Advisory only — a non-zero code is a soft signal,
        not a hard error."""
        return 0 if self.tier_ready(self.provisioned_tier()) else 1


# --------------------------------------------------------------------------- #
# (4) diagnose(probe) -> Diagnosis  —  THE PURE CORE.                          #
#     Builds the Check records in tier order. Touches only its argument.        #
# --------------------------------------------------------------------------- #

def _present(value: Optional[str]) -> bool:
    return bool(value)


def diagnose(probe: Probe) -> Diagnosis:
    checks: List[Check] = []

    def add(id, label, tier, ok, detail_ok, detail_bad, fix_hint,
            *, miss="FAIL", safe_autofix=False):
        checks.append(Check(
            id=id, label=label, tier=tier,
            status="PASS" if ok else miss,
            detail=detail_ok if ok else detail_bad,
            fix_hint=fix_hint, safe_autofix=safe_autofix,
        ))

    # ========== GRADE-ONLY (prereqs + substrate — grade tasks) ============= #
    add("harness-py", "Harness Python 3.11+", "grade-only",
        _present(probe.py_exe),
        f"{probe.py_exe}", "no harness Python launcher resolved",
        "Install Python 3.11+ (3.12 recommended) so `py -3.12 --version` works, or "
        "override with `cb --py \"py -3.12\"` / set CB_PY. Doc: docs/WINDOWS.md §1.")

    git = probe.which("git")
    add("git", "git on PATH", "grade-only",
        _present(git), f"{git}", "not on PATH",
        "Install Git for Windows (also provides tar) and add it to PATH. "
        "Doc: docs/WINDOWS.md §1 (git row) + §9.")

    tar = probe.which("tar")
    add("tar", "tar on PATH", "grade-only",
        _present(tar), f"{tar}", "not on PATH",
        "Git for Windows ships tar; Win10 1803+/11 ship native tar.exe. If neither is "
        "present, grade with `--substrate-from-live`. Doc: docs/WINDOWS.md §1 (tar row) + §7.")

    add("ue", "UE 5.8 install", "grade-only",
        probe.ue is not None, f"{probe.ue}", "UnrealEditor not found",
        "Install UE 5.8 via the Epic Games Launcher (default C:\\Program Files\\Epic "
        "Games\\UE_5.8; ~100 GB disk, allow hours — one-time), or set "
        "`cb --ue-root \"<path>\"` / CB_UE_ROOT. Root must contain "
        "Engine\\Build\\BatchFiles\\Build.bat + Engine\\Binaries\\Win64\\UnrealEditor-Cmd.exe. "
        "Doc: docs/WINDOWS.md §1 + §9.")

    add("substrate", "Substrate project present", "grade-only",
        probe.uproject_exists,
        "CraftBenchTemplate.uproject present", "CraftBenchTemplate.uproject missing",
        "Substrate is committed; a missing .uproject means an incomplete clone or wrong "
        "repo root. `git checkout -- UE-projects/`, or set CB_CRAFTBENCH to the real repo "
        "root. Doc: docs/harness-tour/03-substrate.md (what the substrate is).")

    # ======= BASELINE (grade-only + claude CLI + ANTHROPIC_API_KEY) ======== #
    add("claude-cli", "claude CLI on PATH", "baseline",
        _present(probe.claude_cli),
        f"{probe.claude_cli}", "not on PATH (only the baseline claude-p agent needs it)",
        "Only the baseline `claude-p` agent needs it (pure grading does not). "
        "Install Claude Code (drops claude.cmd/claude.exe) and add its dir to PATH. "
        "Doc: docs/WINDOWS.md §1 (claude row) + §9.",
        miss="WARN")

    anth = probe.env_keys.get("ANTHROPIC_API_KEY")
    add("anthropic-key", "ANTHROPIC_API_KEY present", "baseline",
        _present(anth),
        "present", "not set (baseline tier only)",
        "Needed for the baseline tier — the claude-p agent's model calls (pure grading "
        "does not need it). Set ANTHROPIC_API_KEY in <craftbench>/.env (replace the sk-ant-xxxx… "
        "placeholder; see .env.example). Reported as present/absent only, never echoed.",
        miss="WARN")

    # ``.env`` is a BASELINE fact, not a rig fact: ANTHROPIC_API_KEY is normally
    # read out of it. ADVISORY on purpose (WARN, and deliberately NOT in
    # _BASELINE_GATING_WARNS) — real_probe falls back to os.environ, so a box
    # that exports the key without ever writing a `.env` is baseline-ready and
    # must not be told otherwise. It is the one check stamped safe_autofix: the
    # copy is idempotent and overwrites nothing (it only ever runs when the file
    # is absent), which is what makes it safe for setup to apply unattended.
    add("env-file", ".env at craftbench root", "baseline",
        probe.env_present,
        ".env present", "no .env at the craftbench root (fine if you export the keys)",
        "Setup-applied SAFE fix (ONLY when .env is absent): `cp .env.example .env` (git-bash) "
        "/ `copy .env.example .env` (cmd), then fill the secret keys. Doc: .env.example header.",
        miss="WARN", safe_autofix=True)

    # (The FULL-RIG tier used to sit here — nine checks over the private rig
    # behind the aura-mcp arm: its closed-source plugin checkout, that checkout's
    # server subdirectories, the vendor account credentials, the auth keys, the
    # built editor module and a live service/tool-catalogue probe. All of it went
    # with the rig itself; see the module docstring. Nothing about that arm is
    # checkable from a public clone, so the honest diagnostic is silence, not a
    # tier of FAILs.)

    return Diagnosis(checks=checks)


# --------------------------------------------------------------------------- #
# (5) render(diag) -> str — grouped-by-tier, colour-free, fix hints under each #
#     non-PASS line + a per-tier verdict + a SUMMARY block. Pure (no I/O).     #
# --------------------------------------------------------------------------- #

_TIER_HEADERS = [
    ("grade-only", "GRADE-ONLY (grade tasks deterministically: python + git + tar + UE 5.8 + substrate)"),
    ("baseline", "BASELINE (grade-only + claude CLI + ANTHROPIC_API_KEY + .env — the claude-p agent)"),
]

# Fix-hint wrapping: hang the text under the `->` marker at ~96 columns so the
# STATUS/id/detail grid survives a real console, and console soft-wrap can never
# swallow the space at a wrap boundary ("CB_UE_ROOTis set"-class capture bugs).
_HINT_PREFIX = "        -> "
_HINT_INDENT = " " * len(_HINT_PREFIX)
_HINT_WIDTH = 96
_HINT_CMD_MIN = 40   # backtick-quoted commands at least this long get their own line
_NBSP = "\u00a0"     # glues short inline `commands` so textwrap can't split them


def _split_command(cmd: str) -> List[str]:
    """One command per line; ``&&``-chained multi-command fixes split at the
    chain points (the joiner stays visible so the chain is still copyable)."""
    parts = cmd.split(" && ")
    if len(parts) == 1:
        return [cmd]
    return [(("" if i == 0 else "  ") + p + (" &&" if i < len(parts) - 1 else ""))
            for i, p in enumerate(parts)]


def _wrap_hint(hint: str) -> List[str]:
    """Wrap one fix hint at ~96 columns with a hanging indent under the ``->``
    marker. Long backtick-quoted commands go on their own indented line(s) so
    they stay copy-pastable and are never broken mid-token; short quoted spans
    stay inline. Pure text -> lines; no I/O."""
    segments = hint.split("`")
    # Re-merge into (is_cmd, text) chunks: odd indexes are backtick-quoted.
    chunks: List[Tuple[bool, str]] = []
    for i, seg in enumerate(segments):
        if i % 2 == 1 and len(seg) >= _HINT_CMD_MIN:
            chunks.append((True, seg))
        else:
            # Short quoted spans stay inline but must never be split mid-command:
            # glue their internal spaces (textwrap only breaks on ASCII spaces).
            text = f"`{seg.replace(' ', _NBSP)}`" if i % 2 == 1 else seg
            if chunks and not chunks[-1][0]:
                chunks[-1] = (False, chunks[-1][1] + text)
            else:
                chunks.append((False, text))

    lines: List[str] = []
    first = True
    last_was_cmd = False
    for is_cmd, seg in chunks:
        if is_cmd:
            if first:            # hint opens with a command: keep the marker row
                lines.append(_HINT_PREFIX.rstrip())
                first = False
            lines.extend(f"{_HINT_INDENT}  {cl}" for cl in _split_command(seg))
            last_was_cmd = True
            continue
        text = seg
        if last_was_cmd:
            # The line break after an own-line command already reads as the
            # sentence boundary — drop the orphaned leading punctuation.
            text = text.lstrip()
            while text and text[0] in ".,;":
                text = text[1:].lstrip()
        text = text.strip()
        if not text:
            continue
        lines.extend(w.replace(_NBSP, " ") for w in textwrap.wrap(
            text, width=_HINT_WIDTH,
            initial_indent=_HINT_PREFIX if first else _HINT_INDENT,
            subsequent_indent=_HINT_INDENT,
            break_long_words=False, break_on_hyphens=False))
        first = False
        last_was_cmd = False
    return lines or [_HINT_PREFIX.rstrip()]


def render(diag: Diagnosis, *, live_coding: int = 0) -> str:
    """Render the grouped diagnosis exactly as ``cb doctor`` prints it. ``diag`` is
    the pure result; ``live_coding`` is the informational console count the wrapper
    captured (rides outside the per-tier gate — never affects any verdict)."""
    lines: List[str] = [
        "",
        "cb doctor — read-only environment diagnostic  (advisory; does not mutate)",
    ]

    for tier, header in _TIER_HEADERS:
        lines.append("")
        lines.append(header)
        for c in diag.by_tier(tier):
            lines.append(f"  {c.status:<4}  {c.id:<16} {c.detail}")
            if c.status != "PASS":
                lines.extend(_wrap_hint(c.fix_hint))
        lines.append(f"  {tier}: {diag.tier_verdict(tier)}")

    lines.append("")
    lc_note = ("holds UE's build lock while up — `cb down` frees it"
               if live_coding else "engine build lock is free")
    lines.append(f"  note: LiveCoding {live_coding} console(s)  "
                 f"(UE hot-reload helper; {lc_note})")

    # SUMMARY — one CUMULATIVE verdict per canonical tier (blockers attributed
    # to their tier), then the provisioned-tier exit decision.
    prov = diag.provisioned_tier()
    prov_why = ("ANTHROPIC_API_KEY set" if prov == "baseline"
                else "no baseline credentials")
    lines += [
        "",
        "SUMMARY",
        f"  grade-only: {diag.tier_verdict('grade-only')}",
        f"  baseline:   {diag.tier_verdict('baseline')}",
        f"  Highest provisioned tier: {prov} ({prov_why})  ->  exit {diag.exit_code()}",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# (6) real_probe(ctx) -> Probe — the live-wiring factory (used by cmd_doctor). #
#     The ONLY place that touches the filesystem / env / live HTTP snapshot.   #
#     Read-only: it resolves facts, never mutates. diagnose() stays offline.   #
# --------------------------------------------------------------------------- #

# Unedited .env.example placeholders -> treated as "absent" so diagnose() stays
# policy-free (it just sees None for a key that is still the example sentinel).
# KEEP IN SYNC with tools/scripts/setup_craftbench.py::_PLACEHOLDERS - the two
# dicts must stay identical (setup is stdlib-only and cannot import this module).
# The AURA_USERNAME / AURA_PASSWORD rows went with the private rig's tier: no
# check here reads either key any more, and shipping the sentinels would keep a
# vendor-credential vocabulary alive in a repo that has no vendor lane. Setup's
# copy still lists them at the time of writing - drop them there too, in the
# same change that drops those rows from .env.example.
_PLACEHOLDERS = {
    "ANTHROPIC_API_KEY": ("sk-ant-xxxx", "sk-ant-xxx"),
    "OPENROUTER_API_KEY": ("sk-or-xxxx",),
}


def _strip_placeholder(key: str, value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    for ph in _PLACEHOLDERS.get(key, ()):
        if value == ph or value.startswith(ph):
            return None
    return value


def real_probe(ctx) -> Probe:  # pragma: no cover - live wiring
    """Resolve every live fact off the cb ``_Ctx`` and pack a :class:`Probe`.

    Read-only. We read the craftbench ``.env`` text directly (with an os.environ
    fallback) and strip the .env.example placeholders here, leaving
    :func:`diagnose` pure + policy-free."""
    import os
    import shutil

    from aura_rig import stack  # local import (cb.py already imports stack)

    paths = ctx.paths
    cb_root = paths.craftbench

    env_path = cb_root / ".env"
    env_present = env_path.exists()
    env_text = ""
    if env_present:
        try:
            env_text = env_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            env_text = ""

    def _key(k: str) -> Optional[str]:
        v = stack._env_val(env_text, k) if env_text else None
        if not v:
            v = os.environ.get(k)
        return _strip_placeholder(k, v)

    env_keys = {"ANTHROPIC_API_KEY": _key("ANTHROPIC_API_KEY")}

    # Informational only, and deliberately kept after the private-rig cut: a
    # LiveCodingConsole holds UE's build lock, which stalls a Build.bat on ANY
    # arm, so this is machine truth rather than lane truth. It rides outside
    # every tier gate (render() prints it under the tiers) and can never move
    # a verdict.
    try:
        live_coding = stack.count_image("LiveCodingConsole")
    except Exception:
        live_coding = 0

    claude_cli = (shutil.which("claude") or shutil.which("claude.cmd")
                  or shutil.which("claude.exe"))

    return Probe(
        py_exe=ctx.py_exe,
        which=shutil.which,
        ue=ctx.ue,
        uproject_exists=paths.uproject.exists(),
        claude_cli=claude_cli,
        env_keys=env_keys,
        env_present=env_present,
        live_coding=live_coding,
    )

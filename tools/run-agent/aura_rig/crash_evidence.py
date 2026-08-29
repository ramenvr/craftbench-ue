"""Crash evidence for a dead drive editor — DIAGNOSTIC ONLY, never a verdict.

WHY THIS EXISTS (2026-08-13)
----------------------------
When the drive editor dies mid-turn the rep records ``EDITOR-GONE`` and the
operator is told to "check runs/.kill-audit.log to see whether the rig itself
killed it". That log answers exactly one question — *did WE kill it* — and when
the answer is no, the trail ends. Every unexplained EDITOR-GONE since 2026-08-05
has cost hours for that reason.

The evidence was there the whole time and was simply thrown away. A fatal editor
death writes ``<project>/Saved/Crashes/UECC-*/`` containing:

  * ``CrashContext.runtime-xml`` — structured: ``IsEnsure``, ``CrashType``,
    ``ErrorMessage``, ``TimeOfCrash``, ``ProcessId``;
  * ``ThirdPerson.log`` — the editor's OWN log, ~270 KB, carrying the assert
    text, the UE **script stack** (which names the API and its caller), and the
    **command line**.

That last one is the load-bearing find. ``CrashContext.runtime-xml`` scrubs the
command line to the literal ``CommandLineRemoved``, but the BUNDLED LOG keeps
it — and it is what separates a real drive editor (``-AuraHeadless``) from a
maintainer's own probe script (``-ExecutePythonScript=…``). Applied to the
ThirdPerson project's history it re-attributed **4 of its 6** "unexplained" fatal
crashes to maintainer scripts of mine in one pass — one more than a hand-written
census found, because that census assumed the log was named ``ThirdPerson.log``
and the fourth dump's is ``ThirdPerson_2.log``. The ``glob("*.log")`` below is
why the tool beat the hand-audit.

WHAT THIS MODULE DELIBERATELY DOES NOT DO
-----------------------------------------
**It never changes a verdict.** EDITOR-GONE stays non-graded, exactly as before.

That restraint is the whole design. An agent CAN kill the editor with three
stock editor-Python calls (``AnimMontageFactory`` carries
``check(TargetSkeleton == NULL || TargetSkeleton == SourceSkeleton)`` — engine
code, unguarded, and we are engine-pinned so it cannot be fixed on our side), so
a dead editor is in principle a denominator escape. Grading on that signal is
tempting and wrong today, for two reasons that this module is built to
eventually answer rather than assume:

  1. **No confirmed agent escape has ever happened.** Of the 6 fatal crashes
     under ``UE-projects/ThirdPerson/Saved/Crashes`` when this shipped, **4 were
     maintainer scripts of mine and 2 were drive-editor deaths** — one of those
     on a ``/Game/Variants/…`` authoring path, i.e. a human driving Aura rather
     than a graded model. Box-wide there are 11 fatals; the other 5 are all the
     same ``AuraModelGenerator`` startup assert at ``SecondsSinceStart=0`` with
     no script stack, so none of them is an agent action either. Census dated
     and scoped on purpose: dump counts move (a 63-reference sweep pushed
     ThirdPerson past 200 in hours, since healthy runs mint ensures).
  2. **Attribution is not yet airtight.** The harness records no editor PID, so
     a dump binds to a rep only through a time window. Grading on a
     mis-attributed dump would convert a harness fault into a model FAIL — the
     one outcome the verdict contract forbids outright, and strictly
     worse than the escape it would be fixing.

So: capture, attribute, print. Decide later, on data.

PLACEMENT RULE (do not move this call)
--------------------------------------
It runs INSIDE ``run_graded._model_pin_gate``'s ``editor_gone`` branch. It must
never run above ``record_drive_pressure``, which returns first precisely so a
commit-exhausted editor is classified as COMMIT-EXHAUSTED and stays non-graded.
Reordering those would put this diagnostic in the path of deaths it has no
business describing.

Everything here is fail-open: a missing dump, unreadable XML, a copy error or a
hostile path yields ``None`` and a quiet note. A diagnostic that can break a run
is worse than no diagnostic.
"""
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

# .NET ticks (100 ns since 0001-01-01) -> POSIX seconds. UE writes TimeOfCrash
# in this form; the constant is the tick count at the epoch.
_TICKS_AT_EPOCH = 621355968000000000
_TICKS_PER_SECOND = 10_000_000

# How far back a dump may sit and still be attributed to THIS death. There is no
# PID binding (the harness records no editor pid), so the window is the only
# guard against inheriting a previous rep's crash. Deliberately tight: a wrong
# attribution is worse than "no dump matched", because it invites someone to act
# on another rep's stack trace.
DEFAULT_WINDOW_SECONDS = 15 * 60

# Bounded excerpt around the fatal line. The bundled log is ~270 KB and the
# minidump can be tens of MB; neither belongs in a run dir wholesale.
_EXCERPT_BEFORE = 40
_EXCERPT_AFTER = 60
_EXCERPT_CAP_BYTES = 64 * 1024

# Written into a dump dir once it has been reported, so a LATER rep cannot claim
# the same crash. Saved/Crashes is per-PROJECT and nothing prunes it between
# reps, so one fatal dump sitting inside two reps' windows would otherwise be
# attributed to both — and the second attribution is simply false. See capture().
_CLAIM_FILE = ".craftbench-reported"

_FATAL_MARKERS = (
    "Assertion failed:",
    "Fatal error:",
    "=== Critical error: ===",
    "EXCEPTION_ACCESS_VIOLATION",
)


def _tag(xml: str, name: str) -> Optional[str]:
    m = re.search(r"<%s>(.*?)</%s>" % (name, name), xml, re.DOTALL)
    return m.group(1).strip() if m else None


@dataclass
class CrashEvidence:
    """One attributed fatal crash. ``attribution`` is the honest part."""

    dir_name: str
    crash_type: Optional[str] = None
    error: Optional[str] = None
    when_epoch: Optional[float] = None
    process_id: Optional[str] = None
    command_line: Optional[str] = None
    attribution: str = "unknown"
    script_stack: List[str] = field(default_factory=list)

    def lines(self) -> List[str]:
        """Operator-facing summary — the three things worth reading."""
        out = [f"crash dump: {self.dir_name} ({self.crash_type or 'unknown type'})"]
        if self.error:
            out.append(f"  error: {self.error[:200]}")
        if self.script_stack:
            out.append("  script stack (names the API and its caller):")
            out.extend(f"    {f}" for f in self.script_stack[:6])
        out.append(f"  attribution: {self.attribution}")
        return out


def _attribute(command_line: str) -> str:
    """Who was driving this editor, from its own command line.

    The one genuinely load-bearing classification here, because it is what
    separates a real measured drive from a maintainer's probe — and the XML's
    own CommandLine field is scrubbed, so this is the only place it survives.
    """
    cl = command_line or ""
    if not cl:
        # ABSENT is not the same as UNRECOGNISED. Conflating them would misreport
        # a dump whose log could not be read as though its command line HAD been
        # read and found wanting.
        #
        # NB the original justification here cited "one of this box's six" dumps
        # as having shipped no log. That was WRONG (found 2026-08-14): its log is
        # named ThirdPerson_2.log, which the glob('*.log') below finds and a
        # hand-written census assuming the filename did not. No dump on this box
        # ships no log. The distinction is still worth keeping — a future dump
        # may genuinely be unreadable — it just is not evidenced by that one.
        return "unknown"
    if "-AuraHeadless" in cl:
        return "DRIVE EDITOR (a real measured session)"
    if "scratchpad" in cl or "-ExecutePythonScript=" in cl:
        return "maintainer script / probe (NOT a measured run)"
    return "unknown (command line present but unrecognised)"


def _script_stack(log_text: str) -> List[str]:
    """The UE script stack frames, if the log carries one.

    This is what makes a crash actionable rather than merely recorded: it names
    the reflected API and the caller, e.g.
        /Script/Engine.AnimationDataController.SetModel
        /Script/Aura.AuraPythonStatics.RunPythonScript
    """
    m = re.search(r"Script Stack \(\d+ frames?\) ?:\n(.*?)\n\s*\n",
                  log_text, re.DOTALL)
    if not m:
        return []
    frames = []
    for raw in m.group(1).splitlines():
        line = re.sub(r"^\[[^\]]*\]\[[^\]]*\][A-Za-z]*: ?", "", raw).strip()
        if line:
            frames.append(line)
    return frames


def _read_dump(dump_dir: Path) -> Optional[CrashEvidence]:
    """Parse one UECC dir, or None when it is not a FATAL crash.

    Non-fatal ensures are filtered here and that filter is the difference
    between a useful signal and a useless one: on this box 142 of 148 dumps are
    ensures, minted by perfectly healthy runs. ``IsEnsure`` is the discriminator.
    """
    xml_path = dump_dir / "CrashContext.runtime-xml"
    try:
        xml = xml_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if (_tag(xml, "IsEnsure") or "").lower() != "false":
        return None                       # an ensure: healthy, not a death

    ev = CrashEvidence(dir_name=dump_dir.name,
                       crash_type=_tag(xml, "CrashType"),
                       error=(_tag(xml, "ErrorMessage") or "").replace("\n", " ").strip() or None,
                       process_id=_tag(xml, "ProcessId"))
    ticks = _tag(xml, "TimeOfCrash")
    if ticks and ticks.isdigit():
        ev.when_epoch = (int(ticks) - _TICKS_AT_EPOCH) / _TICKS_PER_SECOND

    for log in sorted(dump_dir.glob("*.log")):
        try:
            text = log.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        m = re.search(r"Command Line: ?(.*)", text)
        if m:
            ev.command_line = m.group(1).strip()
        ev.script_stack = ev.script_stack or _script_stack(text)
        if not ev.error:
            for marker in _FATAL_MARKERS:
                i = text.find(marker)
                if i >= 0:
                    ev.error = text[i:i + 200].splitlines()[0].strip()
                    break
        break
    ev.attribution = _attribute(ev.command_line or "")
    return ev


def find_fatal_crash(project_dir, *, now: float,
                     window_seconds: float = DEFAULT_WINDOW_SECONDS
                     ) -> Optional[CrashEvidence]:
    """Newest FATAL crash under ``project_dir/Saved/Crashes`` inside the window.

    A crash SESSION emits several dirs sharing one UECC id with ``_NNNN``
    suffixes — typically ensures first and the fatal one last — so scanning
    every dir and keeping fatals is correct; grouping is unnecessary once
    ensures are filtered.

    Returns None (never raises) when there is nothing to say.
    """
    try:
        crashes = Path(project_dir) / "Saved" / "Crashes"
        if not crashes.is_dir():
            return None
        best: Optional[CrashEvidence] = None
        for d in crashes.iterdir():
            if not d.is_dir() or not d.name.startswith("UECC-"):
                continue
            if (d / _CLAIM_FILE).exists():
                continue          # already reported to an earlier rep
            ev = _read_dump(d)
            if ev is None or ev.when_epoch is None:
                continue
            # Outside the window: almost certainly a previous rep's crash.
            # Silence beats a confident wrong stack trace.
            if not (0 <= (now - ev.when_epoch) <= window_seconds):
                continue
            if best is None or (ev.when_epoch or 0) > (best.when_epoch or 0):
                best = ev
        return best
    except Exception:      # noqa: BLE001 - a diagnostic must never break a run
        return None


def capture(project_dir, run_dir, *, now: float,
            window_seconds: float = DEFAULT_WINDOW_SECONDS) -> Optional[CrashEvidence]:
    """Find + copy the evidence into ``run_dir/crash/``. Fail-open.

    CLAIMS THE DUMP so it is never reported twice (review finding, 2026-08-14).
    ``Saved/Crashes`` is per-PROJECT and nothing prunes it between reps, so
    without a claim marker one fatal dump inside two reps' windows would be
    attributed to both — and the second attribution is simply false. Cross-rep
    evidence bleed has already manufactured wrong conclusions in this repo, so
    the guard is cheap insurance rather than theory.

    The marker is written INSIDE the dump directory, which is disposable
    engine-owned scratch: if it cannot be written the dump is still reported
    (fail-open), it just loses its once-only guarantee.
    """
    ev = find_fatal_crash(project_dir, now=now, window_seconds=window_seconds)
    if ev is None:
        return None
    try:
        src = Path(project_dir) / "Saved" / "Crashes" / ev.dir_name
        dst = Path(run_dir) / "crash"
        dst.mkdir(parents=True, exist_ok=True)
        xml = src / "CrashContext.runtime-xml"
        if xml.is_file():
            shutil.copy2(xml, dst / xml.name)
        # An EXCERPT of the log only. The full log is ~270 KB and the .dmp can
        # be tens of MB; a run dir is not an archive.
        for log in sorted(src.glob("*.log")):
            text = log.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()
            hit = next((i for i, l in enumerate(lines)
                        if any(m in l for m in _FATAL_MARKERS)), None)
            if hit is None:
                chunk = lines[-(_EXCERPT_BEFORE + _EXCERPT_AFTER):]
            else:
                chunk = lines[max(0, hit - _EXCERPT_BEFORE): hit + _EXCERPT_AFTER]
            # TRUNCATE BY BYTES, not characters (code review). The cap is
            # named _EXCERPT_CAP_BYTES and slicing a str bounds CHARACTERS, so a
            # non-ASCII log blew the stated bound by up to 3x — measured on this
            # box's own Chinese UE output, which is exactly what a crash log
            # here contains ("由于…的USkeleton缺失" appeared in a real dump
            # today). errors="ignore" drops a split multi-byte char at the
            # boundary rather than writing invalid UTF-8.
            body = ("\n".join(chunk).encode("utf-8")[:_EXCERPT_CAP_BYTES]
                    .decode("utf-8", "ignore"))
            # newline="" so the ON-DISK size is the size we just capped. Default
            # text mode translates \n -> \r\n on Windows AFTER the cap, which put
            # the first version of this 7 bytes over its own bound — the cap has
            # to bound what is WRITTEN, not what was measured.
            with open(dst / (log.stem + ".excerpt.log"), "w",
                      encoding="utf-8", newline="") as fh:
                fh.write(body)
            break
        # Claim it LAST: if any copy above failed we would rather report the
        # dump again than lose it silently.
        try:
            (src / _CLAIM_FILE).write_text(
                "reported by craftbench\n", encoding="utf-8")
        except OSError:
            pass      # fail-open: the report stands, it stays re-claimable
    except Exception:      # noqa: BLE001 - the summary lines still get printed
        pass
    return ev

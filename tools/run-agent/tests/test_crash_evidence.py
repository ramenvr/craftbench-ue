"""The EDITOR-GONE crash diagnostic: it must be USEFUL, QUIET, and HARMLESS.

Harmless is the one that matters. This module runs on the verdict path of a
non-graded rep, so every test below that asserts "returns None" or "does not
raise" is protecting a run from its own diagnostic.

The signal it extracts is only worth having because of two facts measured on
this box 2026-08-13:

  * 142 of 148 crash dumps are NON-FATAL ENSURES minted by healthy runs. Any
    check that treats "a UECC dir exists" as evidence of death fires on
    perfectly good reps. ``IsEnsure`` is the discriminator, and
    ``test_ensure_dump_is_never_matched`` is the test that pins it.
  * ``CrashContext.runtime-xml`` scrubs the command line to the literal
    ``CommandLineRemoved``, but the BUNDLED LOG preserves it — and that is the
    only surviving key to WHO was driving. Applied to this box's history it
    re-attributed 3 of 6 "unexplained" fatal crashes to maintainer probe
    scripts in a single pass.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aura_rig import crash_evidence as ce  # noqa: E402

# 2026-08-13 17:58 UTC-ish, in .NET ticks — the real repro's stamp shape.
TICKS = 639222406991580000
EPOCH = (TICKS - ce._TICKS_AT_EPOCH) / ce._TICKS_PER_SECOND

XML = """<?xml version="1.0" encoding="UTF-8"?>
<FGenericCrashContext>
 <RuntimeProperties>
  <CrashType>{ctype}</CrashType>
  <IsEnsure>{ensure}</IsEnsure>
  <ProcessId>51384</ProcessId>
  <TimeOfCrash>{ticks}</TimeOfCrash>
  <CommandLine>CommandLineRemoved</CommandLine>
  <ErrorMessage>{err}</ErrorMessage>
 </RuntimeProperties>
</FGenericCrashContext>
"""

LOG = """[2026.08.13-17.58.00:000][  0]LogInit: Command Line: {cmdline}
[2026.08.13-17.58.10:000][  2]LogPython: doing things
[2026.08.13-17.58.17:129][  2]LogOutputDevice: Warning:

Script Stack (2 frames) :
/Script/Engine.AnimationDataController.SetModel
/Script/Aura.AuraPythonStatics.RunPythonScript

[2026.08.13-17.58.17:138][  2]LogWindows: Error: appError called: {err}
[2026.08.13-17.58.19:215][  2]LogWindows: Error: === Critical error: ===
"""


def _project(tmp, *, ensure="false", ctype="Assert", ticks=TICKS,
             cmdline="-AuraHeadless -unattended", name="UECC-Windows-AAA_0004",
             err="Assertion failed: TargetSkeleton == 0 || TargetSkeleton == SourceSkeleton",
             with_log=True):
    d = Path(tmp) / "Saved" / "Crashes" / name
    d.mkdir(parents=True)
    (d / "CrashContext.runtime-xml").write_text(
        XML.format(ensure=ensure, ctype=ctype, ticks=ticks, err=err), encoding="utf-8")
    if with_log:
        (d / "ThirdPerson.log").write_text(
            LOG.format(cmdline=cmdline, err=err), encoding="utf-8")
    (d / "UEMinidump.dmp").write_bytes(b"\x00" * 2048)
    return Path(tmp)


class TestFindsAndAttributes(unittest.TestCase):
    def test_fatal_dump_in_window_is_found_and_parsed(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = _project(tmp)
            ev = ce.find_fatal_crash(proj, now=EPOCH + 30)
            self.assertIsNotNone(ev)
            self.assertEqual("Assert", ev.crash_type)
            self.assertIn("TargetSkeleton", ev.error)
            self.assertEqual(
                ["/Script/Engine.AnimationDataController.SetModel",
                 "/Script/Aura.AuraPythonStatics.RunPythonScript"],
                ev.script_stack,
                "the script stack is what makes a crash actionable — it names "
                "the API and its caller",
            )

    def test_drive_editor_and_probe_are_told_apart(self):
        """THE ATTRIBUTION KEY. The XML scrubs the command line; the log keeps it."""
        with tempfile.TemporaryDirectory() as tmp:
            proj = _project(tmp, cmdline="-AuraHeadless -unattended -nosplash")
            self.assertIn("DRIVE EDITOR",
                          ce.find_fatal_crash(proj, now=EPOCH + 30).attribution)
        with tempfile.TemporaryDirectory() as tmp:
            proj = _project(
                tmp, cmdline="-ExecutePythonScript=C:/…/scratchpad/probe.py -nullrhi")
            self.assertIn(
                "maintainer", ce.find_fatal_crash(proj, now=EPOCH + 30).attribution,
                "a maintainer's own probe must never be reported as a measured "
                "session — 3 of this box's 6 fatal crashes are exactly that",
            )

    def test_xml_command_line_alone_would_attribute_nothing(self):
        """Pins WHY the log is read at all: the XML field is scrubbed."""
        with tempfile.TemporaryDirectory() as tmp:
            proj = _project(tmp, with_log=False)
            ev = ce.find_fatal_crash(proj, now=EPOCH + 30)
            self.assertIsNotNone(ev)
            self.assertIsNone(ev.command_line)
            self.assertEqual("unknown", ev.attribution)


class TestRefusesToGuess(unittest.TestCase):
    """Every case here must yield None. A confident wrong stack trace is worse
    than silence: it sends the next person to debug another rep's crash."""

    def test_ensure_dump_is_never_matched(self):
        """142 of 148 dumps on this box are ensures, from HEALTHY runs."""
        with tempfile.TemporaryDirectory() as tmp:
            proj = _project(tmp, ensure="true", ctype="Ensure")
            self.assertIsNone(
                ce.find_fatal_crash(proj, now=EPOCH + 30),
                "an ensure is not a death; matching one would fire the "
                "diagnostic on healthy reps",
            )

    def test_dump_outside_the_window_is_not_inherited(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = _project(tmp)
            self.assertIsNone(
                ce.find_fatal_crash(proj, now=EPOCH + 10_000),
                "no PID binding exists, so the time window is the ONLY guard "
                "against attributing a previous rep's crash to this one",
            )

    def test_future_dump_is_not_matched(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = _project(tmp)
            self.assertIsNone(ce.find_fatal_crash(proj, now=EPOCH - 600))

    def test_no_crashes_dir_at_all(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(ce.find_fatal_crash(Path(tmp), now=EPOCH))

    def test_unreadable_and_garbage_dirs_are_survived(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp)
            c = proj / "Saved" / "Crashes"
            (c / "UECC-Windows-EMPTY_0000").mkdir(parents=True)
            (c / "not-a-crash-dir").mkdir()
            (c / "UECC-Windows-JUNK_0000").mkdir()
            (c / "UECC-Windows-JUNK_0000" / "CrashContext.runtime-xml").write_text(
                "<<<not xml", encoding="utf-8")
            self.assertIsNone(ce.find_fatal_crash(proj, now=EPOCH))

    def test_a_hostile_project_path_never_raises(self):
        self.assertIsNone(ce.find_fatal_crash(
            "Z:/does/not/exist/\x00bad", now=EPOCH))


class TestOnceOnlyClaim(unittest.TestCase):
    """A dump must be reported to ONE rep, ever.

    Saved/Crashes is per-PROJECT and nothing prunes it between reps, so without a
    claim marker a single fatal dump sitting inside two reps' windows is
    attributed to BOTH — and the second attribution is simply false. Cross-rep
    evidence bleed has already manufactured wrong conclusions in this repo
    (recorded in FAILURE-LOG), which is why this is a test and not a comment.
    """

    def test_a_dump_is_reported_once_and_then_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = _project(tmp)
            run1, run2 = Path(tmp) / "r1", Path(tmp) / "r2"
            run1.mkdir(); run2.mkdir()

            first = ce.capture(proj, run1, now=EPOCH + 30)
            self.assertIsNotNone(first, "the first rep must get the evidence")

            second = ce.capture(proj, run2, now=EPOCH + 40)
            self.assertIsNone(
                second,
                "the SAME dump was attributed to a second rep — that rep's "
                "summary would carry another rep's stack trace")

    def test_the_claim_marker_lands_in_the_dump_not_the_run_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = _project(tmp)
            run = Path(tmp) / "r"; run.mkdir()
            ce.capture(proj, run, now=EPOCH + 30)
            dump = proj / "Saved" / "Crashes" / "UECC-Windows-AAA_0004"
            self.assertTrue((dump / ce._CLAIM_FILE).is_file(),
                            "the claim belongs in the disposable dump dir")
            self.assertFalse((run / "crash" / ce._CLAIM_FILE).exists())

    def test_an_unclaimable_dump_is_still_reported(self):
        """Fail-open: losing the once-only guarantee beats losing the report.

        NOTE ON THIS TEST'S OWN PREMISE. The first draft pre-created the marker
        as a DIRECTORY to make the write fail — but that made the scan skip the
        dump before it could ever be reported, so the test was asserting on a
        state the code never reaches. Patching the write itself is the only way
        to exercise the fail-open path, and the distinction is exactly the
        probe-premise trap this session keeps hitting: a test that cannot reach
        the branch it names proves nothing about it.
        """
        with tempfile.TemporaryDirectory() as tmp:
            proj = _project(tmp)
            run = Path(tmp) / "r"
            run.mkdir()
            real_write = Path.write_text

            def _refuse(self, *a, **kw):
                if self.name == ce._CLAIM_FILE:
                    raise OSError("read-only")
                return real_write(self, *a, **kw)

            Path.write_text = _refuse
            try:
                ev = ce.capture(proj, run, now=EPOCH + 30)
            finally:
                Path.write_text = real_write
            self.assertIsNotNone(ev, "the report must survive an unwritable claim")
            self.assertIn("TargetSkeleton", ev.error)


class TestCapture(unittest.TestCase):
    def test_capture_writes_xml_and_a_BOUNDED_log_excerpt(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = _project(tmp)
            run = Path(tmp) / "run"
            run.mkdir()
            ev = ce.capture(proj, run, now=EPOCH + 30)
            self.assertIsNotNone(ev)
            out = run / "crash"
            self.assertTrue((out / "CrashContext.runtime-xml").is_file())
            excerpts = list(out.glob("*.excerpt.log"))
            self.assertEqual(1, len(excerpts))
            self.assertIn("TargetSkeleton", excerpts[0].read_text(encoding="utf-8"))
            self.assertLessEqual(excerpts[0].stat().st_size, ce._EXCERPT_CAP_BYTES)
            self.assertEqual(
                [], list(out.glob("*.dmp")),
                "the minidump can be tens of MB and must never be copied into "
                "a run dir",
            )

    def test_the_excerpt_cap_is_BYTES_even_for_non_ascii_logs(self):
        """The cap is named _EXCERPT_CAP_BYTES, so it must bound BYTES.

        Slicing a `str` bounds CHARACTERS. Measured: 64 KiB of the Chinese text
        this box's UE actually emits encodes to ~192 KB — 3x the stated bound,
        and a crash log here really does contain it (a real dump today carried
        "由于…的USkeleton缺失"). Flagged in code review; the file is now
        capped after encoding, and decoded with errors="ignore" so a split
        multi-byte character at the boundary cannot write invalid UTF-8.
        """
        with tempfile.TemporaryDirectory() as tmp:
            proj = _project(tmp, err="Assertion failed: " + "缺失日志" * 30000)
            run = Path(tmp) / "r"
            run.mkdir()
            ev = ce.capture(proj, run, now=EPOCH + 30)
            self.assertIsNotNone(ev)
            out = next((run / "crash").glob("*.excerpt.log"))
            self.assertLessEqual(
                out.stat().st_size, ce._EXCERPT_CAP_BYTES,
                "the excerpt blew its own byte cap on non-ASCII content")
            # and it must still be readable UTF-8, not a split character
            out.read_text(encoding="utf-8")

    def test_capture_on_a_read_only_run_dir_still_returns_the_evidence(self):
        """The COPY is a nicety; the printed summary is the point."""
        with tempfile.TemporaryDirectory() as tmp:
            proj = _project(tmp)
            ev = ce.capture(proj, "Z:/nonexistent/run", now=EPOCH + 30)
            self.assertIsNotNone(ev)
            self.assertIn("TargetSkeleton", ev.error)

    def test_summary_lines_carry_error_stack_and_attribution(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = _project(tmp)
            text = "\n".join(ce.find_fatal_crash(proj, now=EPOCH + 30).lines())
            self.assertIn("TargetSkeleton", text)
            self.assertIn("AnimationDataController.SetModel", text)
            self.assertIn("DRIVE EDITOR", text)


if __name__ == "__main__":
    unittest.main()

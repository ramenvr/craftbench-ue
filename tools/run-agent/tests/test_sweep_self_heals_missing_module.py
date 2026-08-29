"""The sweep must REBUILD on a missing binary, not abort -- and still abort on poison.

WHY THIS IS A TEST AND NOT A COMMENT. The detector that finds the missing module
(`test_declared_module_missing.py`) landed first, and on its own it made things
WORSE for the sweep: it turns a silent 8-minute editor-launch timeout into an
immediate `exit 6`. Correct, and useless -- because the condition it detects
recurs after essentially EVERY cell whose agent recompiles, which on the cpp
surface is every cell. Measured 2026-08-25: of 16 cells in block 1, exactly two
produced a graded verdict, and both were the first cell after a hand rebuild.

So the guard has to heal, and the healing has to be scoped:

  * MISSING  -> rebuild the editor target. This is the action the detector's own
               message asks for. It changes nothing the grade reads: the graded
               substrate is materialised from git HEAD and `Binaries/` is
               gitignored.
  * POISONED -> still abort. That marker means the products could not be cleaned
               automatically; rebuilding on top of it bakes the stubbed fixtures
               deeper into the DLL, which is the ORIGINAL nine-dead-cells defect.

Both directions are load-bearing and they pull opposite ways, which is exactly
the shape that rots when someone later "simplifies" the condition.

Stdlib only. Parses the shell source; runs no build, no editor, no tokens.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_SWEEP = _ROOT / "sweep_mcp_lanes.sh"
_SRC = _SWEEP.read_text(encoding="utf-8")

_HEAL_OPEN = 'if [ -n "$_poison" ] && ['


def _heal_block() -> str:
    """The `if` that decides to rebuild, up to its closing `fi`."""
    start = _SRC.index(_HEAL_OPEN)
    end = _SRC.index("\n      fi\n", start)
    return _SRC[start:end]


def _heal_code() -> str:
    """The heal block with comment lines dropped.

    The comments deliberately NAME the trap the code must avoid -- "NOT $safe"
    is the clearest way to stop the next reader reintroducing it -- so a check
    for "does the code USE $safe" has to look at code only. Otherwise the
    explanation of the bug reads as the bug.
    """
    keep = [l for l in _heal_block().splitlines() if not l.lstrip().startswith("#")]
    return chr(10).join(keep)


class TestTheHealIsScopedToMissing(unittest.TestCase):
    def test_the_condition_requires_the_MISSING_marker(self):
        # A heal that fires on any non-empty reason would rebuild on top of a
        # poisoned tree, which is the defect the poison marker exists to stop.
        cond = _heal_block().split(chr(10), 1)[0]
        self.assertIn("is MISSING", cond)

    def test_a_poisoned_project_still_reaches_the_abort(self):
        # The unconditional abort must survive BELOW the heal, so a reason the
        # heal declines to handle still stops the sweep instead of driving.
        heal_at = _SRC.index(_HEAL_OPEN)
        abort_at = _SRC.index('echo "ABORT: $SUBSTRATE is not fit to drive."')
        self.assertGreater(abort_at, heal_at,
                           "the catch-all abort must come after the heal")

    def test_the_heal_rechecks_and_refuses_to_drive_if_it_did_not_work(self):
        # Rebuilding and then driving anyway would re-hide the failure behind
        # the same 8-minute editor timeout this whole change exists to remove.
        block = _heal_block()
        self.assertIn("print(verifier_build_suspect(sys.argv[1])", block,
                      "the heal must re-ask the detector after building")
        self.assertIn("still not fit", block)
        self.assertIn("exit 6", block)


class TestTheBuildInvocationIsWellFormed(unittest.TestCase):
    def test_it_builds_the_editor_target_of_this_substrate(self):
        block = _heal_code()
        self.assertIn('_tgt="$(basename "$SUBSTRATE")Editor"', block)
        self.assertIn("$UE_ROOT_BAT", block)
        self.assertIn("Win64 Development", block)

    def test_UE_ROOT_BAT_is_defined_before_the_heal_uses_it(self):
        define_at = _SRC.index("UE_ROOT_BAT=")
        use_at = _SRC.index('"$UE_ROOT_BAT" "$_tgt"')
        self.assertLess(define_at, use_at)

    def test_a_substrate_with_no_uproject_aborts_rather_than_building_nothing(self):
        self.assertIn("no .uproject", _heal_code())


class TestTheHealLogNameIsNotTheStaleCellName(unittest.TestCase):
    """`safe` is assigned BELOW this block. Using it here names the log after
    the PREVIOUS cell -- or nothing at all on the first one -- which sends the
    reader to the wrong file precisely when they are debugging a failed heal."""

    def test_no_reference_to_safe_survives_in_the_heal(self):
        self.assertNotIn("$safe", _heal_code())

    def test_safe_really_is_assigned_after_the_heal(self):
        # Guards the premise above: if `safe` ever moves ABOVE the heal this
        # test should fail loudly rather than quietly permitting "$safe" again.
        safe_at = _SRC.index('safe="$(printf')
        self.assertGreater(safe_at, _SRC.index(_HEAL_OPEN))

    def test_the_log_is_named_after_the_substrate_and_appended(self):
        block = _heal_code()
        self.assertIn('_hlog="$LOG_DIR/heal-$(basename "$SUBSTRATE").log"', block)
        # Appended, not truncated: a heal that fails after an earlier heal
        # succeeded must not erase the record of the one that worked.
        self.assertIn('>> "$_hlog" 2>&1', block)
        self.assertNotIn('> "$_hlog" 2>&1' + chr(10), block.replace(">> ", "@@ "))

    def test_the_abort_message_names_the_log_that_was_actually_written(self):
        self.assertIn('echo "       build log: $_hlog"', _SRC)


class TestTheScriptStillParses(unittest.TestCase):
    def test_no_unbalanced_quote_in_the_heal_block(self):
        # `sh -n` is the real check and CI runs it; this is the cheap stdlib
        # approximation so a broken quote fails here too, without a shell.
        for line in _heal_code().splitlines():
            self.assertEqual(line.count('"') % 2, 0,
                             f"odd number of quotes: {line!r}")


if __name__ == "__main__":
    unittest.main()


class TestTheProjectPathReachesUBTAbsolute(unittest.TestCase):
    """The heal's FIRST real firing failed here, and a source-grep test would
    not have caught it.

    2026-08-25: the heal fired correctly, named the right project, and UBT
    rejected it -- "Unable to find project file based on argument
    UE-projects/ThirdPerson/ThirdPerson.uproject". $SUBSTRATE is relative by
    design, `ls "$SUBSTRATE"/*.uproject` therefore yields a relative path, and
    UBT resolves -Project= itself against something other than the shell's cwd.

    What made it survive review is the more useful lesson: the rebuild HAD been
    verified by hand minutes earlier, with an absolute path typed into the
    terminal. That proved the build works and proved nothing about the argument
    the script assembles. So this test RUNS the script's own path logic on a
    relative input rather than asserting the source contains `cygpath`.
    """

    def _absolutise(self, rel_path: str, cwd: str) -> str:
        """Run the heal's path block verbatim, extracted from the script."""
        block = _heal_code()
        start = block.index("if command -v cygpath")
        end = block.index("_hlog=")
        snippet = block[start:end].rstrip()
        script = f'_proj="{rel_path}"\n{snippet}\nprintf "%s" "$_proj"\n'
        out = subprocess.run(["sh", "-c", script], cwd=cwd, capture_output=True,
                             text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        return out.stdout.strip()

    def test_a_relative_uproject_comes_back_absolute(self):
        with tempfile.TemporaryDirectory() as d:
            sub = Path(d) / "UE-projects" / "ThirdPerson"
            sub.mkdir(parents=True)
            (sub / "ThirdPerson.uproject").write_text("{}", encoding="utf-8")
            got = self._absolutise("UE-projects/ThirdPerson/ThirdPerson.uproject", d)
        self.assertTrue(got.startswith("/") or (len(got) > 1 and got[1] == ":"),
                        f"UBT needs an absolute path, got {got!r}")
        self.assertNotEqual(got, "UE-projects/ThirdPerson/ThirdPerson.uproject")
        self.assertTrue(got.endswith("ThirdPerson.uproject"))

    def test_an_already_absolute_path_is_not_mangled(self):
        # cygpath -m -a is idempotent on absolute input; the fallback branch
        # must be too, or a substrate given absolutely breaks instead.
        with tempfile.TemporaryDirectory() as d:
            sub = Path(d) / "P"
            sub.mkdir(parents=True)
            f = sub / "P.uproject"
            f.write_text("{}", encoding="utf-8")
            once = self._absolutise(str(f).replace(chr(92), "/"), d)
            twice = self._absolutise(once, d)
        self.assertEqual(once, twice)
        self.assertTrue(once.endswith("P.uproject"))

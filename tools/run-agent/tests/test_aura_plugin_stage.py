"""Staging the Aura plugin must never leave the graded substrate modified.

aura-mcp had produced ZERO graded runs because its bring-up waits on :30010, which
is served by RemoteControl, which reaches the project only as an Aura dependency —
and no .uproject listed Aura. Measured 2026-08-18: without it the port never binds
in 480s and the editor log mentions Aura 0 times; with it the port binds in ~5s and
the log mentions it 39 times.

The fix stages the entry for the bring-up and restores it. These tests pin the
restore, because the .uproject is graded substrate for every other lane: a leaked
edit would silently change what bare / claude-p / openrouter / unreal-mcp are
measured against.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from aura_rig.aura_plugin_stage import AURA_PLUGIN, aura_enabled  # noqa: E402

BASE = {
    "FileVersion": 3,
    "EngineAssociation": "5.8",
    "Plugins": [{"Name": "GameplayAbilities", "Enabled": True}],
}


def _write(tmp, spec=None):
    p = Path(tmp) / "T.uproject"
    p.write_text(json.dumps(spec if spec is not None else BASE, indent=4) + "\n",
                 encoding="utf-8")
    return p


class TestStaging(unittest.TestCase):

    def test_aura_is_present_inside_and_absent_after(self):
        with tempfile.TemporaryDirectory() as td:
            p = _write(td)
            with aura_enabled(p) as staged:
                self.assertTrue(staged)
                names = [x["Name"] for x in json.loads(p.read_text(encoding="utf-8"))["Plugins"]]
                self.assertIn(AURA_PLUGIN, names)
            names = [x["Name"] for x in json.loads(p.read_text(encoding="utf-8"))["Plugins"]]
            self.assertNotIn(AURA_PLUGIN, names)

    def test_the_file_is_restored_BYTE_for_byte(self):
        """Not re-serialised. A reformat would show as a dirty substrate on every
        run and, worse, would look like someone edited the project."""
        with tempfile.TemporaryDirectory() as td:
            p = _write(td)
            before = p.read_bytes()
            with aura_enabled(p):
                pass
            self.assertEqual(p.read_bytes(), before)

    def test_restore_happens_even_when_the_body_raises(self):
        """A crashed bring-up must not leak the edit into the substrate."""
        with tempfile.TemporaryDirectory() as td:
            p = _write(td)
            before = p.read_bytes()
            with self.assertRaises(RuntimeError):
                with aura_enabled(p):
                    raise RuntimeError("bring-up exploded")
            self.assertEqual(p.read_bytes(), before)

    def test_a_project_that_ALREADY_lists_aura_is_untouched(self):
        """No-op, and nothing restored — because nothing was changed."""
        spec = {"Plugins": [{"Name": "Aura", "Enabled": True}]}
        with tempfile.TemporaryDirectory() as td:
            p = _write(td, spec)
            before = p.read_bytes()
            with aura_enabled(p) as staged:
                self.assertFalse(staged)
                self.assertEqual(p.read_bytes(), before)
            self.assertEqual(p.read_bytes(), before)

    def test_it_does_NOT_add_remotecontrol_directly(self):
        """RemoteControl must arrive through Aura's dependency list. Adding it
        separately would mask the real requirement if those deps ever change."""
        with tempfile.TemporaryDirectory() as td:
            p = _write(td)
            with aura_enabled(p):
                names = [x["Name"] for x in json.loads(p.read_text(encoding="utf-8"))["Plugins"]]
                self.assertNotIn("RemoteControl", names)

    def test_an_unparseable_project_fails_OPEN(self):
        """Never rewrite a file we cannot read. The drive then fails at the
        readiness gate with its own clear message instead of here with a
        confusing one."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "T.uproject"
            p.write_text("{not json", encoding="utf-8")
            msgs = []
            with aura_enabled(p, log=msgs.append) as staged:
                self.assertFalse(staged)
            self.assertEqual(p.read_text(encoding="utf-8"), "{not json")
            self.assertTrue(any("could not read" in m for m in msgs))


if __name__ == "__main__":
    unittest.main()

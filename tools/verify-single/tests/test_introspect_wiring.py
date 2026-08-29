"""Unit tests for the L2-introspect wiring into run_task.

No UE install required — only the task-spec parsing surface is exercised
(the layer itself is covered by tests/test_l2_introspect.py).
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_VERIFY = _HERE.parent
if str(_VERIFY) not in sys.path:
    sys.path.insert(0, str(_VERIFY))

from run_task import _parse_introspect_block, parse_task_spec  # noqa: E402


class TestParseIntrospectBlock(unittest.TestCase):
    def test_plain_script_names(self):
        body = "- mat_emissive_pulse.py\n- widget_card.py\n"
        self.assertEqual(
            _parse_introspect_block(body),
            ("mat_emissive_pulse.py", "widget_card.py"),
        )

    def test_asset_prefix_form(self):
        body = "- /Game/Tasks/t/M_Target :: t_introspect.py\n"
        self.assertEqual(_parse_introspect_block(body), ("t_introspect.py",))

    def test_dedup_and_prose_skipped(self):
        body = "this section verifies the material\n- a.py\n- a.py\n- b.py\n"
        self.assertEqual(_parse_introspect_block(body), ("a.py", "b.py"))

    def test_empty(self):
        self.assertEqual(_parse_introspect_block(""), ())


class TestTaskSpecIntrospect(unittest.TestCase):
    def test_spec_picks_up_section(self):
        md = (
            "## Task ID and metadata\n\n- task_id: demo\n- substrate: template\n\n"
            "## Verifier layers used\n\nL1\n\n"
            "## Verifier introspection\n\n- demo_introspect.py\n"
        )
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write(md)
            p = Path(f.name)
        spec = parse_task_spec(p)
        self.assertEqual(spec.introspect_scripts, ("demo_introspect.py",))
        self.assertIn("L1", spec.layers)

    def test_spec_without_section_is_empty(self):
        md = (
            "## Task ID and metadata\n\n- task_id: demo2\n- substrate: template\n\n"
            "## Verifier layers used\n\nL1 L2\n"
        )
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write(md)
            p = Path(f.name)
        self.assertEqual(parse_task_spec(p).introspect_scripts, ())


if __name__ == "__main__":
    unittest.main()

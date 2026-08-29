"""Read-only grounding tools: workspace_list / workspace_read / groundtruth.

These let the judge cross-check the submission's claims against the REAL project
(substrate ∪ submission). They are anti-circular (CraftBench's own fs reads),
sandboxed, and bounded so a huge tree can't flood the judge's context.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_R2 = Path(__file__).resolve().parents[1]
if str(_R2) not in sys.path:
    sys.path.insert(0, str(_R2))

from judge import (  # noqa: E402
    FirewallViolation,
    build_groundtruth_tool,
    build_workspace_readonly_tools,
)
from config import EVIDENCE_SOURCES, REFEREE_SOURCES  # noqa: E402


class TestWorkspaceTools(unittest.TestCase):
    def _ws(self, d: Path):
        (d / "Source" / "CraftBenchTemplate").mkdir(parents=True)
        (d / "Source" / "CraftBenchTemplate" / "A.cpp").write_text("// a", encoding="utf-8")
        (d / "Source" / "CraftBenchTemplate" / "B.h").write_text("// b", encoding="utf-8")
        (d / "Content").mkdir()
        (d / "Content" / "x.txt").write_text("x", encoding="utf-8")
        return build_workspace_readonly_tools(d)

    def test_workspace_file_kind_is_a_referee_source(self):
        self.assertIn("workspace_file", EVIDENCE_SOURCES)
        self.assertIn("workspace_file", REFEREE_SOURCES)

    def test_list_scopes_to_subpath(self):
        with tempfile.TemporaryDirectory() as d:
            t = self._ws(Path(d))
            res = t["workspace_list"]({"path": "Source"})
            self.assertEqual(set(res["files"]),
                             {"Source/CraftBenchTemplate/A.cpp", "Source/CraftBenchTemplate/B.h"})
            self.assertFalse(res["truncated"])

    def test_list_caps_and_flags_truncation(self):
        with tempfile.TemporaryDirectory() as d:
            t = self._ws(Path(d))
            res = t["workspace_list"]({"max": 1})
            self.assertEqual(len(res["files"]), 1)
            self.assertTrue(res["truncated"])

    def test_read_returns_content(self):
        with tempfile.TemporaryDirectory() as d:
            t = self._ws(Path(d))
            res = t["workspace_read"]({"path": "Source/CraftBenchTemplate/A.cpp"})
            self.assertEqual(res["content"], "// a")
            self.assertFalse(res["truncated"])

    def test_read_rejects_escape(self):
        with tempfile.TemporaryDirectory() as d:
            t = self._ws(Path(d))
            with self.assertRaises(FirewallViolation):
                t["workspace_read"]({"path": "../../../etc/passwd"})

    def test_read_missing_file_is_soft_error(self):
        with tempfile.TemporaryDirectory() as d:
            t = self._ws(Path(d))
            self.assertIn("error", t["workspace_read"]({"path": "nope.txt"}))


class TestGroundtruthTool(unittest.TestCase):
    def test_returns_pinned_facts(self):
        tool = build_groundtruth_tool(["fact one", "fact two"])["read_task_groundtruth"]
        self.assertEqual(tool({})["groundtruth_facts"], ["fact one", "fact two"])


if __name__ == "__main__":
    unittest.main()

"""editor_introspect: marker parsing + injectable editor (no UE install needed)."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_R2 = Path(__file__).resolve().parents[1]
if str(_R2) not in sys.path:
    sys.path.insert(0, str(_R2))

from ue_tools import build_editor_introspect_tool, extract_marked_output, editor_binary  # noqa: E402


# A realistic UnrealEditor-Cmd stdout: timestamped LogPython-prefixed lines
# with the marked block in the middle.
FAKE_STDOUT = """\
[2026.06.02-00.00.00:000][  0]LogInit: starting
[2026.06.02-00.00.01:000][  0]LogPython: CRAFTBENCH-JUDGE-INTROSPECT-START
[2026.06.02-00.00.01:001][  0]LogPython: {"actor_count": 3, "has_tag_SanityRoot": true}
[2026.06.02-00.00.01:002][  0]LogPython: CRAFTBENCH-JUDGE-INTROSPECT-END
[2026.06.02-00.00.02:000][  0]LogExit: done
"""


def _uproject_dir(d: Path) -> Path:
    (d / "CraftBenchTemplate.uproject").write_text("{}", encoding="utf-8")
    return d


class TestEditorIntrospect(unittest.TestCase):
    def test_extract_strips_logpython_prefix(self):
        out = extract_marked_output(FAKE_STDOUT)
        self.assertIn('"actor_count": 3', out)
        self.assertNotIn("LogPython", out)
        self.assertNotIn("LogInit", out)  # only the marked block survives

    def test_tool_returns_marked_output_via_injected_editor(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            calls = {}

            def fake_run(cmd):
                calls["cmd"] = cmd
                return 0, FAKE_STDOUT

            tool = build_editor_introspect_tool(
                ue_root=d / "UE", project_path=_uproject_dir(d), run_editor=fake_run,
            )["editor_introspect"]
            res = tool({"script": "import unreal\nprint('hi')"})
            self.assertIn('"actor_count": 3', res["output"])
            self.assertEqual(res["returncode"], 0)
            # it shelled out headless + read-only (no Aura bridge)
            self.assertIn("-ExecutePythonScript=", " ".join(calls["cmd"]))
            self.assertIn("-nullrhi", calls["cmd"])

    def test_missing_script_is_soft_error(self):
        with tempfile.TemporaryDirectory() as d:
            tool = build_editor_introspect_tool(
                ue_root=Path(d) / "UE", project_path=_uproject_dir(Path(d)),
                run_editor=lambda cmd: (0, ""),
            )["editor_introspect"]
            self.assertIn("error", tool({}))

    def test_no_uproject_is_soft_error(self):
        with tempfile.TemporaryDirectory() as d:
            tool = build_editor_introspect_tool(
                ue_root=Path(d) / "UE", project_path=Path(d),  # empty dir, no .uproject
                run_editor=lambda cmd: (0, FAKE_STDOUT),
            )["editor_introspect"]
            self.assertIn("error", tool({"script": "x=1"}))

    def test_editor_binary_path_shape(self):
        b = editor_binary(Path("/opt/UE_5.7"))
        self.assertTrue(b.name.startswith("UnrealEditor-Cmd"))
        self.assertIn("Engine/Binaries", b.as_posix())


if __name__ == "__main__":
    unittest.main()

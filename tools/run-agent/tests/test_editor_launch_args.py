"""editor_launch_args (stack + unreal_mcp_stack): the --visible contract.

visible=True drops EXACTLY -RenderOffScreen; everything else — in particular
-AuraHeadless (Aura's tool-bridge bootstrap, NOT a rendering switch) and
-unattended/-nosplash/-nopause/-nosound — stays in ALL modes. Fully offline.
"""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aura_rig import stack  # noqa: E402
from aura_rig import unreal_mcp_stack as ums  # noqa: E402


class TestStackEditorLaunchArgs(unittest.TestCase):
    UE = Path("C:/UE/UnrealEditor.exe")
    UPROJ = Path("C:/proj/CraftBenchTemplate.uproject")

    def test_default_is_headless(self):
        args = stack.editor_launch_args(self.UE, self.UPROJ)
        self.assertIn("-RenderOffScreen", args)
        self.assertIn("-AuraHeadless", args)
        self.assertIn("-unattended", args)
        self.assertEqual(args[0], str(self.UE))
        self.assertEqual(args[1], str(self.UPROJ))

    def test_visible_drops_exactly_renderoffscreen(self):
        headless = stack.editor_launch_args(self.UE, self.UPROJ)
        visible = stack.editor_launch_args(self.UE, self.UPROJ, visible=True)
        self.assertNotIn("-RenderOffScreen", visible)
        # EXACTLY one arg differs — the render switch. Everything else stays.
        self.assertEqual(set(headless) - set(visible), {"-RenderOffScreen"})
        self.assertEqual(set(visible) - set(headless), set())
        # The Aura tool bridge + unattended determinism MUST survive visible mode.
        self.assertIn("-AuraHeadless", visible)
        self.assertIn("-unattended", visible)
        self.assertIn("-nosplash", visible)
        self.assertIn("-nopause", visible)
        self.assertIn("-nosound", visible)


class TestUnrealMcpEditorLaunchArgs(unittest.TestCase):
    UE = Path("C:/UE/UnrealEditor.exe")
    UPROJ = Path("C:/proj/CraftBenchTemplate.uproject")

    def test_default_is_headless_with_mcp(self):
        args = ums.editor_launch_args(self.UE, self.UPROJ)
        self.assertIn("-RenderOffScreen", args)
        self.assertIn("-ModelContextProtocolStartServer", args)
        self.assertIn("-unattended", args)

    def test_visible_drops_exactly_renderoffscreen(self):
        headless = ums.editor_launch_args(self.UE, self.UPROJ)
        visible = ums.editor_launch_args(self.UE, self.UPROJ, visible=True)
        self.assertNotIn("-RenderOffScreen", visible)
        self.assertEqual(set(headless) - set(visible), {"-RenderOffScreen"})
        self.assertEqual(set(visible) - set(headless), set())
        self.assertIn("-ModelContextProtocolStartServer", visible)
        self.assertIn("-unattended", visible)

    def test_non_default_port_inserted_before_log(self):
        args = ums.editor_launch_args(self.UE, self.UPROJ, port=8123)
        self.assertIn("-ModelContextProtocolPort=8123", args)
        self.assertEqual(args[-1], "-log")

    def test_default_port_not_inserted(self):
        default_port = ums._port_of(ums.DEFAULT_URL)
        args = ums.editor_launch_args(self.UE, self.UPROJ, port=default_port)
        self.assertFalse(any(a.startswith("-ModelContextProtocolPort=") for a in args))


class TestEnvFlag(unittest.TestCase):
    def setUp(self):
        self._old = os.environ.pop("CB_VISIBLE", None)

    def tearDown(self):
        if self._old is None:
            os.environ.pop("CB_VISIBLE", None)
        else:
            os.environ["CB_VISIBLE"] = self._old

    def test_truthy_values(self):
        for v in ("1", "true", "TRUE", "yes"):
            os.environ["CB_VISIBLE"] = v
            self.assertTrue(stack.env_flag("CB_VISIBLE"), v)

    def test_falsy_values(self):
        os.environ.pop("CB_VISIBLE", None)
        self.assertFalse(stack.env_flag("CB_VISIBLE"))
        for v in ("0", "false", "no", ""):
            os.environ["CB_VISIBLE"] = v
            self.assertFalse(stack.env_flag("CB_VISIBLE"), v)


if __name__ == "__main__":
    unittest.main()

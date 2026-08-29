"""wsb_runner — OFFLINE tests for the Windows-Sandbox containment prototype.

These assert the CONTAINMENT CONTRACT of the generated ``.wsb`` config and the
``--sandbox`` wiring WITHOUT launching a real sandbox:

  * networking is Disabled,
  * the UE MappedFolder is ReadOnly=true,
  * the workdir-copy MappedFolder is read-write (ReadOnly=false),
  * the aura-plugin junction target is NOT in any MappedFolder (fail-closed),
  * the LogonCommand invokes run_task.py with the in-VM mapped paths,
  * ``--sandbox`` parses (default-OFF), and the not-available path falls back.

GATING: nothing here needs Windows Sandbox, so the suite runs on every host
(including this Windows 11 **Home** box, which has no sandbox). The ONE test that
needs a live sandbox is ``@unittest.skipUnless(windows_sandbox_available())`` and
will SKIP here by design. Run with ``py -3.12 -m unittest``.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

_HERE = Path(__file__).resolve().parent
_VERIFY = _HERE.parent
if str(_VERIFY) not in sys.path:
    sys.path.insert(0, str(_VERIFY))

import wsb_runner  # noqa: E402
from wsb_runner import (  # noqa: E402
    MappedFolder,
    WsbSpec,
    build_wsb_config,
    default_forbidden_paths,
    windows_sandbox_available,
    write_wsb_config,
)


def _make_spec(*, forbidden=()) -> WsbSpec:
    """A representative spec with distinct UE / workdir host paths."""
    return WsbSpec(
        ue_root_host=Path(r"C:\UnrealEngine\UE_5.8"),
        workdir_copy_host=Path(r"C:\stage\craftbench-work\CraftBenchTemplate"),
        extra_run_task_args=("--task", r"C:\work\tasks\t0.md", "--submission", r"C:\work\sub"),
        forbidden_paths=tuple(forbidden),
    )


class TestWsbConfigContainment(unittest.TestCase):
    """The generated .wsb enforces the containment contract."""

    def setUp(self) -> None:
        self.xml = build_wsb_config(_make_spec())
        self.root = ET.fromstring(self.xml)

    def _mapped(self) -> list[dict]:
        out = []
        for mf in self.root.findall("./MappedFolders/MappedFolder"):
            out.append({
                "host": mf.findtext("HostFolder"),
                "sandbox": mf.findtext("SandboxFolder"),
                "read_only": mf.findtext("ReadOnly"),
            })
        return out

    def test_parses_as_xml(self) -> None:
        # build_wsb_config must emit well-formed XML rooted at <Configuration>.
        self.assertEqual(self.root.tag, "Configuration")

    def test_networking_disabled(self) -> None:
        self.assertEqual(self.root.findtext("Networking"), "Disable")

    def test_ue_mapped_read_only(self) -> None:
        ue = [m for m in self._mapped() if "UnrealEngine" in (m["host"] or "")]
        self.assertEqual(len(ue), 1, "exactly one UE mapped folder expected")
        self.assertEqual(ue[0]["read_only"], "true", "UE install MUST be ReadOnly=true")

    def test_workdir_copy_is_read_write(self) -> None:
        work = [m for m in self._mapped() if "craftbench-work" in (m["host"] or "")]
        self.assertEqual(len(work), 1, "exactly one workdir-copy mapped folder expected")
        self.assertEqual(work[0]["read_only"], "false",
                         "the workdir COPY must be read-write (ReadOnly=false)")

    def test_exactly_two_mapped_folders(self) -> None:
        # UE (ro) + workdir-copy (rw). Nothing else is mapped — no home, no repo.
        self.assertEqual(len(self._mapped()), 2)

    def test_logon_command_invokes_run_task_with_mapped_paths(self) -> None:
        cmd = self.root.findtext("./LogonCommand/Command")
        self.assertIsNotNone(cmd)
        self.assertIn("run_task.py", cmd)
        # Points at the in-VM read-only UE root and the in-VM read-write workdir.
        self.assertIn("--ue-root", cmd)
        self.assertIn(r"C:\ue", cmd)
        self.assertIn("--substrate-overlay", cmd)
        self.assertIn(r"C:\work", cmd)
        # The forwarded task/submission args ride along.
        self.assertIn("--task", cmd)
        self.assertIn("--submission", cmd)
        # No nested sandboxing.
        self.assertNotIn("--sandbox", cmd)

    def test_logon_command_targets_in_vm_run_task_path(self) -> None:
        cmd = self.root.findtext("./LogonCommand/Command")
        # run_task.py is invoked at its in-VM location under the mapped workdir,
        # NOT at any host path.
        self.assertIn(r"C:\work\tools\verify-single\run_task.py", cmd)


class TestForbiddenPathRejection(unittest.TestCase):
    """The aura-plugin junction / home dir must never be mappable."""

    def test_aura_plugin_target_not_in_any_mapped_folder(self) -> None:
        # A well-formed spec maps only UE + workdir; assert the aura-plugin path
        # is absent from the rendered MappedFolders even when declared forbidden.
        genius = Path(r"C:\Users\hello\OneDrive\Documents\GitHub\aura-plugin")
        xml = build_wsb_config(_make_spec(forbidden=(genius,)))
        root = ET.fromstring(xml)
        hosts = [mf.findtext("HostFolder") for mf in root.findall("./MappedFolders/MappedFolder")]
        for h in hosts:
            self.assertNotIn("aura-plugin", (h or "").lower(),
                             "aura-plugin must NOT be mapped into the sandbox VM")

    def test_mapping_a_forbidden_workdir_raises(self) -> None:
        # Fail-closed: if the workdir-copy itself overlapped the aura-plugin
        # junction target, build_wsb_config must REFUSE (ValueError), not silently
        # map the blast radius in.
        genius = Path(r"C:\Users\hello\OneDrive\Documents\GitHub\aura-plugin")
        bad = WsbSpec(
            ue_root_host=Path(r"C:\UnrealEngine\UE_5.8"),
            workdir_copy_host=genius / "Aura" / "work",  # descendant of forbidden
            forbidden_paths=(genius,),
        )
        with self.assertRaises(ValueError):
            build_wsb_config(bad)

    def test_mapping_the_home_dir_raises(self) -> None:
        # Mapping the home dir (an ancestor of the workdir) must be refused.
        home = Path(r"C:\Users\hello")
        bad = WsbSpec(
            ue_root_host=Path(r"C:\UnrealEngine\UE_5.8"),
            workdir_copy_host=home / "work",  # under the forbidden home dir
            forbidden_paths=(home,),
        )
        with self.assertRaises(ValueError):
            build_wsb_config(bad)

    def test_default_forbidden_includes_home(self) -> None:
        forbidden = default_forbidden_paths()
        home = Path("~").expanduser()
        self.assertIn(home, forbidden)


class TestWriteWsbConfig(unittest.TestCase):
    """write_wsb_config persists the XML to disk."""

    def test_writes_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "nested" / "grade.wsb"
            out = write_wsb_config(_make_spec(), dest)
            self.assertEqual(out, dest)
            self.assertTrue(dest.exists())
            text = dest.read_text(encoding="utf-8")
            self.assertIn("<Networking>Disable</Networking>", text)
            self.assertIn("<ReadOnly>true</ReadOnly>", text)


class TestMappedFolderInVm(unittest.TestCase):
    def test_explicit_sandbox_path_wins(self) -> None:
        mf = MappedFolder(Path(r"C:\foo\bar"), read_only=True, sandbox_path=r"C:\ue")
        self.assertEqual(mf.in_vm_path(), r"C:\ue")

    def test_default_sandbox_path_is_desktop_basename(self) -> None:
        mf = MappedFolder(Path(r"C:\foo\bar"), read_only=False)
        self.assertTrue(mf.in_vm_path().endswith(r"Desktop\bar"))


class TestSandboxArgAndFallback(unittest.TestCase):
    """--sandbox parses (default-OFF) and the not-available path falls back."""

    def setUp(self) -> None:
        from run_task import build_parser  # noqa: E402
        self.build_parser = build_parser

    def _base(self, *extra: str) -> list[str]:
        return ["--task", "x.md", "--ue-root", "y", "--submission", "z", *extra]

    def test_sandbox_defaults_off(self) -> None:
        args = self.build_parser().parse_args(self._base())
        self.assertFalse(args.sandbox, "--sandbox must default OFF (opt-in)")

    def test_sandbox_flag_sets_true(self) -> None:
        args = self.build_parser().parse_args(self._base("--sandbox"))
        self.assertTrue(args.sandbox)

    def test_sandbox_is_separate_from_govern_resources(self) -> None:
        # The two hardening knobs are independent: --sandbox does not flip the
        # default-ON governor, and --no-govern-resources does not flip --sandbox.
        args = self.build_parser().parse_args(self._base("--sandbox", "--no-govern-resources"))
        self.assertTrue(args.sandbox)
        self.assertFalse(args.govern_resources)

    def test_dispatch_noop_when_flag_absent(self) -> None:
        from run_task import _maybe_dispatch_to_sandbox
        args = self.build_parser().parse_args(self._base())  # no --sandbox
        self.assertIsNone(_maybe_dispatch_to_sandbox(args),
                          "without --sandbox the dispatcher is a no-op (None)")

    def test_dispatch_falls_back_when_unavailable(self) -> None:
        # On a host WITHOUT Windows Sandbox (this Win11 Home box, and every
        # non-Windows host), --sandbox must NOT abort: the dispatcher returns None
        # so main() continues the in-process grade.
        if windows_sandbox_available():
            self.skipTest("host HAS Windows Sandbox; the fallback path is not exercised here")
        from run_task import _maybe_dispatch_to_sandbox
        args = self.build_parser().parse_args(self._base("--sandbox"))
        self.assertIsNone(
            _maybe_dispatch_to_sandbox(args),
            "--sandbox on a non-WSB host must fall back to in-process (return None)",
        )


class TestAvailabilityProbe(unittest.TestCase):
    def test_unavailable_reason_is_nonempty(self) -> None:
        self.assertTrue(unavailable_reason_nonempty := wsb_runner.unavailable_reason())
        self.assertIsInstance(unavailable_reason_nonempty, str)

    def test_available_is_bool(self) -> None:
        self.assertIsInstance(windows_sandbox_available(), bool)


@unittest.skipUnless(windows_sandbox_available(),
                     "Windows Sandbox not present (needs Win Pro/Edu/Enterprise)")
class TestRealSandboxLaunch(unittest.TestCase):
    """End-to-end launch — SKIPS unless a real Windows Sandbox is available.

    This is the placeholder for the validation that MUST happen on a Pro/Edu/CI
    box. It does not run on Windows 11 Home (no sandbox binary) and is recorded
    here so the gap is visible in the test report as a SKIP, not a silent absence.
    """

    def test_launch_smoke(self) -> None:  # pragma: no cover - needs WSB host
        # Intentionally minimal: a real validation would launch, let the in-VM
        # grade run, and read the report.json back from the mapped workdir copy.
        self.skipTest("manual/CI validation required: launch + in-VM verdict readback")


if __name__ == "__main__":
    unittest.main()

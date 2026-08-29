"""A module the manifest DECLARES with no binary makes the editor exit, quietly.

THE INCIDENT, 2026-08-25. It cost most of a day and produced three wrong
diagnoses before the right one.

After the first cell whose agent recompiled, every later cell died. The lanes
reported different things and neither pointed at the cause:

    unreal-mcp : "editor MCP never became ready at http://127.0.0.1:8000/mcp"
    aura-mcp   : "editor launched but EXITED before binding :30010 - crash on
                  startup (e.g. missing/out-of-date plugin binary; run cb doctor)"

The second sent me to rebuild the Aura plugin, which was never broken — the
editor log carried `LogAura:` lines, a registered fatal-state marker, a bound
`:30010`, and a clean `LogExit: Exiting`. The truth was in
`Binaries/Win64/UnrealEditor.modules`: it DECLARED `CraftBenchTests` while the
DLL beside it did not exist. UE reads that manifest, cannot load the module, and
shuts down cleanly about twelve seconds in.

WHY IT HAPPENS, and why it recurs rather than being a one-off: this module's own
restore INVALIDATES the verifier build products when an agent recompiles them
while the fixtures are stubbed — correctly, because a recompile bakes the stubs
into the DLL. Invalidation is a DELETE, and the log says "the next build
regenerates them". That next build is L1, which builds a WORKDIR COPY. The LIVE
project is never rebuilt, so the live tree stays un-launchable until someone
rebuilds it by hand.

`verifier_build_suspect` already existed for exactly this class of "do not drive
this project" question and answered `clean`, because it asked whether the
products were POISONED and never whether they were THERE. The sweep's own ISSUE
11 note records the same trap from a previous occurrence: "nine consecutive cells
died that way at ~2 min each while the stack log blamed 'crash on startup', and
the 21-check preflight passed every one of them."

Stdlib only. No UE, no editor, no tokens.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fairness import verifier_build_suspect  # noqa: E402


def _project(tmp: Path, modules: dict, present: tuple = ()) -> Path:
    """A project whose manifest declares ``modules``; only ``present`` exist."""
    proj = tmp / "Proj"
    binaries = proj / "Binaries" / "Win64"
    binaries.mkdir(parents=True)
    (binaries / "UnrealEditor.modules").write_text(
        json.dumps({"BuildId": "x", "Modules": modules}), encoding="utf-8")
    for dll in present:
        (binaries / dll).write_bytes(b"MZ")
    return proj


class TestTheMissingBinaryIsCaught(unittest.TestCase):
    def test_a_declared_module_with_no_dll_refuses_the_drive(self):
        with tempfile.TemporaryDirectory() as d:
            proj = _project(Path(d),
                            {"CraftBenchTests": "UnrealEditor-CraftBenchTests.dll",
                             "ThirdPerson": "UnrealEditor-ThirdPerson.dll"},
                            present=("UnrealEditor-ThirdPerson.dll",))
            why = verifier_build_suspect(proj)
            self.assertIsNotNone(why, "the exact live state of 2026-08-25 read "
                                      "as fit to drive")
            self.assertIn("CraftBenchTests", why)
            self.assertIn("MISSING", why)

    def test_the_message_names_the_real_remedy_not_the_misleading_one(self):
        # The whole cost of this defect was the diagnosis, not the failure. The
        # message must say "rebuild the editor target for this project" and warn
        # that a workdir L1 build does not do it -- otherwise the reader follows
        # the lane's own message and rebuilds a healthy plugin.
        with tempfile.TemporaryDirectory() as d:
            proj = _project(Path(d),
                            {"CraftBenchTests": "UnrealEditor-CraftBenchTests.dll"})
            why = verifier_build_suspect(proj) or ""
        self.assertIn("Rebuild the editor target", why)
        self.assertIn("LIVE", why)

    def test_every_declared_module_is_checked_not_just_the_first(self):
        with tempfile.TemporaryDirectory() as d:
            proj = _project(Path(d),
                            {"AAA": "UnrealEditor-AAA.dll",
                             "CraftBenchTests": "UnrealEditor-CraftBenchTests.dll"},
                            present=("UnrealEditor-AAA.dll",))
            self.assertIn("CraftBenchTests", verifier_build_suspect(proj) or "")


class TestAHealthyProjectIsNotRefused(unittest.TestCase):
    """The loud direction. A false refusal aborts the sweep (exit 6) on a box
    that is fine, which is worse than the failure it prevents."""

    def test_all_binaries_present_is_fit(self):
        with tempfile.TemporaryDirectory() as d:
            proj = _project(Path(d),
                            {"CraftBenchTests": "UnrealEditor-CraftBenchTests.dll",
                             "ThirdPerson": "UnrealEditor-ThirdPerson.dll"},
                            present=("UnrealEditor-CraftBenchTests.dll",
                                     "UnrealEditor-ThirdPerson.dll"))
            self.assertIsNone(verifier_build_suspect(proj))

    def test_an_unreadable_manifest_fails_open(self):
        # A manifest that cannot be parsed does not PROVE the project unfit, and
        # refusing on a read error turns a diagnostic into an outage.
        with tempfile.TemporaryDirectory() as d:
            proj = _project(Path(d), {"X": "UnrealEditor-X.dll"},
                            present=("UnrealEditor-X.dll",))
            (proj / "Binaries" / "Win64" / "UnrealEditor.modules").write_text(
                "{ not json", encoding="utf-8")
            self.assertIsNone(verifier_build_suspect(proj))

    def test_a_project_with_no_binaries_tree_is_not_accused(self):
        with tempfile.TemporaryDirectory() as d:
            proj = Path(d) / "Bare"
            proj.mkdir()
            self.assertIsNone(verifier_build_suspect(proj))

    def test_an_empty_module_path_is_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            proj = _project(Path(d), {"Weird": ""})
            self.assertIsNone(verifier_build_suspect(proj))


class TestItIsTheGateTheSweepAlreadyAsks(unittest.TestCase):
    def test_the_sweep_calls_verifier_build_suspect_per_cell(self):
        # A detector nothing calls is the defect this repo keeps finding. The
        # sweep's ISSUE 11 block is the caller; this widens what that call SEES
        # rather than adding a second, unwired check.
        src = (_ROOT / "sweep_mcp_lanes.sh").read_text(encoding="utf-8")
        self.assertIn("verifier_build_suspect", src)
        self.assertIn("is not fit to drive", src)


if __name__ == "__main__":
    unittest.main()


class TestAnAbsentManifestIsAlsoFatal(unittest.TestCase):
    """The second half, measured 2026-08-26 while block 1 was running.

    The checks above ask whether every module the manifest DECLARES has a binary.
    They answer CLEAN when there is no manifest at all -- and that state is just
    as fatal, in the engine's own words. A modal dialog, which headless means an
    immediate exit:

        Message dialog closed, result: Ok, title: 消息,
        text: 游戏模块"ThirdPerson"无法被找到。请确认此模块存在且已被编译。
        LogCore: Engine exit requested (reason: EngineExit() was called)

    Every aura-mcp cell on gp-glide-stamina-cpp died that way at ~1 minute each,
    on a loop, while `verifier_build_suspect` returned None and the sweep's heal
    therefore never fired. Both module DLLs were present; `UnrealEditor.modules`
    and `ThirdPersonEditor.target` were not -- the shape an interrupted build
    leaves after it deletes them and before it rewrites them.
    """

    def test_binaries_present_but_no_manifest_refuses_the_drive(self):
        with tempfile.TemporaryDirectory() as d:
            proj = Path(d) / "Proj"
            binaries = proj / "Binaries" / "Win64"
            binaries.mkdir(parents=True)
            (binaries / "UnrealEditor-ThirdPerson.dll").write_bytes(b"MZ")
            (binaries / "UnrealEditor-CraftBenchTests.dll").write_bytes(b"MZ")
            why = verifier_build_suspect(proj)
        self.assertIsNotNone(why, "the exact live state of 2026-08-26 read as "
                                  "fit to drive, and the heal never fired")
        self.assertIn("ABSENT", why)
        self.assertIn("Rebuild the editor target", why)

    def test_a_source_only_checkout_is_not_accused(self):
        # No Binaries tree at all says nothing about fitness -- refusing there
        # would make a fresh clone unfit and the sweep unstartable.
        with tempfile.TemporaryDirectory() as d:
            proj = Path(d) / "Fresh"
            (proj / "Source").mkdir(parents=True)
            self.assertIsNone(verifier_build_suspect(proj))

    def test_an_empty_binaries_dir_is_not_accused(self):
        with tempfile.TemporaryDirectory() as d:
            proj = Path(d) / "Proj"
            (proj / "Binaries" / "Win64").mkdir(parents=True)
            self.assertIsNone(verifier_build_suspect(proj))

    def test_an_unreadable_manifest_still_fails_open(self):
        # Unreadable is NOT the same as absent: the manifest is there, the engine
        # will read it, and a parse failure here is our problem, not the tree's.
        # This is the direction that must not change with the new branch.
        with tempfile.TemporaryDirectory() as d:
            proj = _project(Path(d), {"X": "UnrealEditor-X.dll"},
                            present=("UnrealEditor-X.dll",))
            (proj / "Binaries" / "Win64" / "UnrealEditor.modules").write_text(
                "{ not json", encoding="utf-8")
            self.assertIsNone(verifier_build_suspect(proj))

    def test_the_message_says_how_many_dlls_are_stranded(self):
        # The count is what tells the reader this is a manifest problem and not
        # an empty tree -- two DLLs with no manifest is unmistakable.
        with tempfile.TemporaryDirectory() as d:
            proj = Path(d) / "Proj"
            binaries = proj / "Binaries" / "Win64"
            binaries.mkdir(parents=True)
            for n in ("A", "B", "C"):
                (binaries / f"UnrealEditor-{n}.dll").write_bytes(b"MZ")
            why = verifier_build_suspect(proj) or ""
        self.assertIn("3 module DLL(s)", why)

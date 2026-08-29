"""L1's adaptive-unity flag and its retry-then-empty-output spawn-fault route.

Two independent things land here because both are properties of the UBT
invocation this module owns.

`-DisableAdaptiveUnity`: UBT's working-set heuristic puts every .cpp of both
modules in its own translation unit on every graded build, because a workdir
staged by `git archive | tar -x` has no .git and an installed engine then routes
SourceFileWorkingSet.Create to the Perforce provider, whose "in the working set"
test is "not read-only". The flag is opt-in rather than default because the
corpus does not yet compile as unity — see the test's own docstring.

The spawn fault: a target that exits non-zero having written zero bytes and
touched no build product never ran, so it is not a model result. Routing it out
of the denominator takes the structural ``build_tool_never_ran`` flag AND the
exit code — `Build.cs` is agent-writable, so the code alone is forgeable.

No UE, no network: every UBT invocation is mocked.

    py -3 -m unittest tools.verify-single.tests.test_l1_spawn_fault
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

_VERIFY = Path(__file__).resolve().parent.parent
if str(_VERIFY) not in sys.path:
    sys.path.insert(0, str(_VERIFY))

import run_task  # noqa: E402
from layers import l1_build  # noqa: E402
from layers.l1_build import SPAWN_FAULT_EXIT, _SingleTargetResult  # noqa: E402
from report import LayerReport  # noqa: E402


def _result(target, exit_code, output=""):
    return _SingleTargetResult(
        target=target, exit_code=exit_code, output=output,
        duration_seconds=0.1, note=f"target {target}: exit {exit_code} in 0.1s",
    )


class TestDisableAdaptiveUnityFlag(unittest.TestCase):
    """Read the flag off the real argv `_run_one_target` hands CreateProcess."""

    def _argv(self, env=None):
        captured = {}

        def fake_run(cmd, **kw):
            captured["cmd"] = cmd
            return subprocess.CompletedProcess(cmd, 0, stdout="ok")

        with mock.patch.dict(os.environ, env or {}, clear=False):
            if not (env or {}).get("CRAFTBENCH_DISABLE_ADAPTIVE_UNITY"):
                os.environ.pop("CRAFTBENCH_DISABLE_ADAPTIVE_UNITY", None)
            with mock.patch.object(subprocess, "run", fake_run):
                l1_build._run_one_target(
                    script=Path("Build.bat"), target="P",
                    project_path=Path("P.uproject"), extra_env=None, job=None,
                )
        return captured["cmd"]

    def test_opt_in_only_until_the_corpus_compiles_under_unity(self):
        """OFF by default on purpose: file-scope names repeat across .cpp of the
        same module, and a unity blob merging their unnamed namespaces makes each
        pair a redefinition — on the REFERENCE solution, not just on agent
        output."""
        self.assertNotIn("-DisableAdaptiveUnity", self._argv())
        for v in ("1", "true", "True"):
            self.assertIn(
                "-DisableAdaptiveUnity",
                self._argv({"CRAFTBENCH_DISABLE_ADAPTIVE_UNITY": v}),
                msg=f"CRAFTBENCH_DISABLE_ADAPTIVE_UNITY={v!r} should opt in")


class TestSpawnFaultRetry(unittest.TestCase):
    def _run(self, tmp, side_effects, on_call=None):
        """Drive run_l1 with a scripted sequence of UBT outcomes.

        ``on_call(target, project_dir)`` runs inside the fake invocation, which is
        where a build's own writes would land — the only way to make a file's
        mtime fall at/after the spawn's ``started_at``.
        """
        calls = []
        self.forensics = []
        proj = Path(tmp) / "P"
        proj.mkdir(exist_ok=True)

        def fake_forensics(exit_code, target):
            self.forensics.append((len(calls), exit_code, target))

        def fake_run_one_target(**kw):
            calls.append(kw["target"])
            if on_call is not None:
                on_call(kw["target"], proj)
            if not side_effects:
                # An unscripted spawn: fail on the `calls` assertion rather than
                # on an IndexError, so a retry that should not have happened
                # reads as one.
                return _result(kw["target"], 99, "UNSCRIPTED SPAWN\n")
            return side_effects.pop(0)

        log = Path(tmp) / "l1.log"
        with mock.patch.object(l1_build, "_run_one_target", fake_run_one_target), \
             mock.patch.object(l1_build, "_spawn_forensics", fake_forensics), \
             mock.patch.object(l1_build, "_build_script", return_value=Path(__file__)):
            res = l1_build.run_l1(
                ue_root=Path(tmp), project_path=proj / "P.uproject",
                game_module="P", log_path=log,
            )
        return res, calls, log.read_text(encoding="utf-8")

    def test_reproduced_no_trace_failure_is_a_machine_fault(self):
        with tempfile.TemporaryDirectory() as tmp:
            res, calls, log_text = self._run(tmp, [
                _result("PEditor", 0),
                _result("P", 3221225794),   # 0xC0000142, zero output
                _result("P", 3221225794),
            ])
        self.assertEqual(res.status, "fail")
        self.assertEqual(res.exit_code, SPAWN_FAULT_EXIT)
        self.assertTrue(res.build_tool_never_ran)
        self.assertEqual(calls, ["PEditor", "P", "P"])
        # The OBSERVED code is the forensic fingerprint and must survive both
        # channels: report.json's notes and the retained log.
        self.assertTrue(any("3221225794" in n for n in res.notes), res.notes)
        self.assertIn("3221225794", log_text)

    def test_a_healed_spawn_yields_a_real_verdict(self):
        with tempfile.TemporaryDirectory() as tmp:
            res, calls, _ = self._run(tmp, [
                _result("PEditor", 0),
                _result("P", 3221225794),
                _result("P", 0, "Total build time: 300s\n"),
            ])
        self.assertEqual(res.status, "pass")
        self.assertEqual(res.exit_code, 0)
        self.assertFalse(res.build_tool_never_ran)
        self.assertEqual(calls, ["PEditor", "P", "P"])
        # The box state that explains a spawn death is gone seconds later, so it
        # is snapshotted BEFORE the re-spawn (i.e. after spawn 2 of 3). A heal
        # must not be what discards the only evidence there was.
        self.assertEqual([(n, code) for n, code, _ in self.forensics],
                         [(2, 3221225794)])

    def test_a_compile_error_is_never_retried(self):
        """The conjunct that keeps this unreachable from submission content: UBT
        prints before it schedules an action, so a real failure has output."""
        with tempfile.TemporaryDirectory() as tmp:
            res, calls, _ = self._run(tmp, [
                _result("PEditor", 6, "Foo.cpp(3,1): error C2065: undeclared\n"),
            ])
        self.assertEqual(res.status, "fail")
        self.assertEqual(res.exit_code, 6)
        self.assertFalse(res.build_tool_never_ran)
        self.assertEqual(calls, ["PEditor"])

    def test_a_build_that_wrote_a_product_is_never_retried(self):
        """Independent of the output conjunct: a spawn that touched Binaries/ did
        work, whatever it printed."""
        def touch_binary(target, proj):
            b = proj / "Binaries" / "Win64"
            b.mkdir(parents=True, exist_ok=True)
            (b / f"{target}.dll").write_bytes(b"x")

        with tempfile.TemporaryDirectory() as tmp:
            res, calls, _ = self._run(
                tmp, [_result("PEditor", 1)], on_call=touch_binary)
        self.assertEqual(res.exit_code, 1)
        self.assertEqual(calls, ["PEditor"])

    def test_a_product_stamped_BEFORE_the_spawn_still_counts_as_work(self):
        """The clock-independence pin, and the reason the cutoff is gone.

        The predicate used to ask ``st_mtime >= started_at``. That is unsound on
        Windows: ``time.time()`` resolves to sub-microsecond while a file's mtime
        is stamped at the system clock's own granularity, so a file written
        immediately AFTER the reading can carry an mtime BELOW it. Measured
        2026-08-24 on this box: 2830 of 4000 writes did exactly that, by up to
        1.6 ms. The consequence was not cosmetic — a spawn that wrote a build
        product inside that window read as one that never ran, and
        ``build_tool_never_ran`` is half of the route that takes a target OUT of
        the denominator. It showed up as
        ``test_a_build_that_wrote_a_product_is_never_retried`` failing on the
        3.13 CI leg while 3.11 and 3.12 passed on identical bytes.

        Here the product is stamped an hour in the PAST, which the old cutoff
        could never see and the set comparison always can.

        The directory is pre-created and itself backdated, which is what makes
        this leg discriminate at all: ``rglob`` yields DIRECTORIES too, so a
        spawn that had to mkdir ``Binaries/Win64`` handed the old cutoff a
        fresh directory mtime and passed for the wrong reason. Measured while
        writing this test — the first version of it passed against the old
        predicate for exactly that reason.
        """
        def write_backdated(target, proj):
            f = proj / "Binaries" / "Win64" / f"{target}.dll"
            f.write_bytes(b"x")
            old = time.time() - 3600
            os.utime(f, (old, old))

        with tempfile.TemporaryDirectory() as tmp:
            b = Path(tmp) / "P" / "Binaries" / "Win64"
            b.mkdir(parents=True)
            old = time.time() - 3600
            for d in (b, b.parent):
                os.utime(d, (old, old))
            res, calls, _ = self._run(
                tmp, [_result("PEditor", 1)], on_call=write_backdated)
        self.assertEqual(res.exit_code, 1)
        self.assertEqual(calls, ["PEditor"],
                         "a spawn that wrote a build product was retried")
        self.assertFalse(res.build_tool_never_ran)

    def test_a_product_the_spawn_only_GREW_counts_as_work(self):
        """Size and mtime both, so an append to an existing product is seen.

        A UBT invocation that relinks into a file the previous target created
        may leave its path unchanged; keying on the path SET alone would call
        that "no work".
        """
        def grow(target, proj):
            b = proj / "Binaries" / "Win64"
            b.mkdir(parents=True, exist_ok=True)
            f = b / "shared.dll"
            with f.open("ab") as fh:
                fh.write(b"more")
            old = time.time() - 3600
            os.utime(f, (old, old))

        with tempfile.TemporaryDirectory() as tmp:
            pre = Path(tmp) / "P" / "Binaries" / "Win64"
            pre.mkdir(parents=True)
            f = pre / "shared.dll"
            f.write_bytes(b"x")
            old = time.time() - 3600
            os.utime(f, (old, old))
            res, calls, _ = self._run(tmp, [_result("PEditor", 1)], on_call=grow)
        self.assertEqual(res.exit_code, 1)
        self.assertEqual(calls, ["PEditor"])

    def test_a_stale_product_does_not_mask_the_fault(self):
        """The Editor target's own binaries predate the Game target's spawn, so
        the cutoff has to be the spawn time and not the file's existence."""
        with tempfile.TemporaryDirectory() as tmp:
            stale = Path(tmp) / "P" / "Binaries" / "Win64"
            stale.mkdir(parents=True)
            (stale / "PEditor.dll").write_bytes(b"x")
            time.sleep(0.01)
            res, calls, _ = self._run(tmp, [
                _result("PEditor", 0),
                _result("P", 3221225794),
                _result("P", 3221225794),
            ])
        self.assertEqual(res.exit_code, SPAWN_FAULT_EXIT)
        self.assertEqual(calls, ["PEditor", "P", "P"])

    def test_a_missing_build_script_is_flagged_too(self):
        """127's provenance, set on the other path that means no build ran."""
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(l1_build, "_build_script",
                                   return_value=Path(tmp) / "nope" / "Build.bat"):
                res = l1_build.run_l1(
                    ue_root=Path(tmp), project_path=Path(tmp) / "P.uproject",
                    game_module="P", log_path=Path(tmp) / "l1.log",
                )
        self.assertEqual(res.exit_code, run_task.L1_EXIT_EXEC_FAILED)
        self.assertTrue(res.build_tool_never_ran)


def _l1(exit_code, **kw):
    return LayerReport(status="fail", exit_code=exit_code, **kw)


_SKIPPED_L2 = LayerReport(status="skipped",
                          notes=["short-circuited: L1 did not pass"])


class TestSpawnFaultRouting(unittest.TestCase):
    def _reasons(self, l1):
        return run_task.harness_error_reasons(
            {"L1": l1, "L2": _SKIPPED_L2}, ("L1", "L2"))

    def test_confirmed_spawn_fault_is_not_graded(self):
        reasons = self._reasons(
            _l1(SPAWN_FAULT_EXIT, build_tool_never_ran=True))
        self.assertEqual(len(reasons), 1)
        self.assertIn("two consecutive spawns", reasons[0])

    def test_an_exit_code_without_provenance_stays_graded(self):
        """`Source/CraftBenchTemplate/CraftBenchTemplate.Build.cs` is inside the
        sandbox writable prefix, so a submission can exit the build tool with any
        status. Without the flag l1_build sets, the code buys nothing."""
        for code in (SPAWN_FAULT_EXIT, run_task.L1_EXIT_EXEC_FAILED, 3221225794):
            with self.subTest(exit_code=code):
                self.assertEqual(self._reasons(_l1(code)), [])

    def test_the_flag_alone_does_not_route_an_arbitrary_code(self):
        self.assertEqual(self._reasons(_l1(1, build_tool_never_ran=True)), [])

    def test_the_layer_carries_the_flag_onto_the_report(self):
        """L1Result -> LayerReport is where this gate would silently go dead."""
        from layers.registry import L1Layer

        l1 = l1_build.L1Result(
            status="fail", exit_code=SPAWN_FAULT_EXIT, log_path=Path("l1.log"),
            duration_seconds=0.1, warning_count=0, warning_count_agent_files=0,
            notes=[], build_tool_never_ran=True,
        )
        ctx = SimpleNamespace(
            args=SimpleNamespace(ue_root=Path("."), strict_warnings=False),
            project_path=Path("P.uproject"), out_dir=Path("."),
            manifest=SimpleNamespace(game_module="P"), agent_prefixes=(),
        )
        with mock.patch.object(l1_build, "run_l1", return_value=l1):
            rep = L1Layer().run(ctx)
        self.assertTrue(rep.build_tool_never_ran)
        self.assertEqual(self._reasons(rep)[0][:11], "L1 exit 126")


if __name__ == "__main__":
    unittest.main()

"""Unit tests for aura_rig.refgate (gate certificates) and `cb refgate`.

UE-free and repo-free: the grade subprocess is an injected child (the
test_bench pattern) and every git lookup routes through the injectable
refgate._run_git seam — no real grades, no real git repo, no tokens.
"""
import json
import os
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from aura_rig import refgate as rg


# --------------------------------------------------------------------------- #
# Canned git runners.                                                          #
# --------------------------------------------------------------------------- #

def _fake_git(task_sha="tsha", sub_sha="ssha", ver_sha="vsha",
              head="headsha", dirty=""):
    """A run_git fake with controllable tree shas / dirt.

    THE THREE TREES ARE DISTINGUISHED, and that matters: an earlier version
    mapped anything that was not UE-projects to `task_sha`, so the VERIFIER tree
    silently returned the task's sha and a grader-only edit was invisible to
    every test. A fake that collapses two independent inputs into one cannot
    show that they are independent.
    """
    def _run(args, repo):
        if args[:2] == ["rev-parse", "HEAD"]:
            return 0, head
        if args and args[0] == "rev-parse":
            rel = args[1]
            if "UE-projects" in rel:
                return 0, sub_sha
            if "verify-single" in rel:
                return 0, ver_sha
            return 0, task_sha
        if args and args[0] == "status":
            return 0, dirty
        return 1, ""
    return _run


def _broken_git(args, repo):
    return 128, ""


# --------------------------------------------------------------------------- #
# The identity (content key).                                                  #
# --------------------------------------------------------------------------- #

def _fake_engine(root, *, patch=0, changelist=55116800):
    """Give a temp dir the Engine/Build/Build.version a real UE install has.

    Needed since 2026-08-14: the certificate key includes the ENGINE BUILD, not
    just the path to it, so a root with no version file yields key=None (re-gate)
    rather than a version-blind certificate. Tests that want a certifiable
    identity must therefore look like an engine.
    """
    d = Path(root) / "Engine" / "Build"
    d.mkdir(parents=True, exist_ok=True)
    (d / "Build.version").write_text(json.dumps({
        "MajorVersion": 5, "MinorVersion": 8,
        "PatchVersion": patch, "Changelist": changelist}), encoding="utf-8")
    return str(root)


class TestIdentity(unittest.TestCase):
    def setUp(self):
        self.repo = Path(tempfile.mkdtemp())
        d = self.repo / "tasks" / "setA" / "t-a"
        (d / "reference").mkdir(parents=True)
        (d / "task.md").write_text(
            "---\nid: t-a\nlayers: [L1]\n---\n\n# t-a\n", encoding="utf-8")
        self.spec = d / "task.md"
        self.ue = _fake_engine(Path(tempfile.mkdtemp()))
        self.ue_other = _fake_engine(Path(tempfile.mkdtemp()))

    def _ident(self, **kw):
        base = dict(hostname="boxA", run_git=_fake_git())
        base.update(kw)
        ue = base.pop("ue_root", self.ue)
        return rg.identity_for(self.repo, "t-a", self.spec, ue, **base)

    def test_clean_committed_tree_yields_a_key_and_the_qualified_id(self):
        ident = self._ident()
        self.assertTrue(ident.certifiable)
        self.assertEqual(ident.task_id, "setA/t-a",
                         "store key is set-qualified however the id was typed")
        self.assertEqual(ident.task_rel, "tasks/setA/t-a")
        self.assertEqual(ident.substrate_rel, "UE-projects/CraftBenchTemplate")

    def test_key_changes_with_each_identity_input(self):
        base = self._ident().key
        self.assertNotEqual(base, self._ident(
            run_git=_fake_git(task_sha="OTHER")).key, "task tree must key")
        self.assertNotEqual(base, self._ident(
            run_git=_fake_git(sub_sha="OTHER")).key, "substrate tree must key")
        self.assertNotEqual(base, rg.identity_for(
            self.repo, "t-a", self.spec, self.ue_other,
            hostname="boxA", run_git=_fake_git()).key, "UE root must key")
        self.assertNotEqual(base, self._ident(hostname="boxB").key,
                            "hostname must key")
        self.assertEqual(base, self._ident().key, "same inputs, same key")

    def test_dirty_tree_is_never_certifiable_but_keeps_its_key(self):
        ident = self._ident(run_git=_fake_git(dirty=" M tasks/setA/t-a/task.md"))
        self.assertTrue(ident.dirty)
        self.assertFalse(ident.certifiable)
        self.assertIn("uncommitted", ident.reason)

    def test_a_committed_GRADER_edit_invalidates_the_certificate(self):
        """A certificate asserts "this reference graded PASS". The thing that
        GRADES it is tools/verify-single/ — so editing a grader must re-gate.

        FOUND IN CODE REVIEW (2026-08-14). Before this, the key covered the
        task tree, the substrate tree, the UE path and the host: the INPUTS and
        not the JUDGE. Editing a per-task grader left every certificate valid, so
        `cb refgate` self-skipped exactly the tasks whose grading logic had just
        changed — the one moment it most needs to run.
        """
        base = self._ident().key
        self.assertNotEqual(
            base, self._ident(run_git=_fake_git(ver_sha="OTHER")).key,
            "a committed change under tools/verify-single/ left the certificate "
            "key unchanged — the gate would skip a task whose GRADER just moved")

    def test_uncommitted_verifier_changes_make_the_gate_uncertifiable(self):
        """Same rule as a dirty task/substrate tree: grade, but do not certify."""
        ident = self._ident(run_git=_fake_git(dirty=" M tools/verify-single/x.py"))
        self.assertIsNotNone(ident.key)
        self.assertTrue(ident.dirty)
        self.assertFalse(ident.certifiable)

    def test_an_IN_PLACE_engine_patch_invalidates_the_certificate(self):
        """THE BUG THIS PINS (found 2026-08-14, live).

        The key used to be sha1(task_sha + sub_sha + str(ue_root) + host), and
        `ue_root` is the PATH, not the engine. So upgrading the engine AT THE
        SAME PATH left every cached certificate valid, and `cb refgate`
        self-skipped tasks it had certified against a build no longer on disk.

        Not hypothetical: Q:/UE_5.8 went 5.8.0-55116800 -> 5.8.1-56057345
        mid-session that day, between one spike and the next. It was benign only
        because every run happened after the bump.

        A certificate means "this reference graded PASS on this engine". This
        test is that sentence.
        """
        before = self._ident().key
        _fake_engine(self.ue, patch=1, changelist=56057345)   # same path, new build
        after = self._ident().key
        self.assertNotEqual(
            before, after,
            "an in-place engine upgrade left the certificate key unchanged — "
            "the gate would skip a task certified against an engine that is no "
            "longer installed")

    def test_engine_build_is_recorded_for_the_operator(self):
        self.assertEqual("5.8.0+55116800", self._ident().engine_build)

    def test_an_UNREADABLE_engine_version_means_no_key_never_a_wrong_one(self):
        """Fail-safe direction: re-gate, never certify blind.

        Matches this module's existing contract for git failures — an unknowable
        input degrades to key=None (gate runs every time) rather than to a key
        that would skip on stale state.
        """
        (Path(self.ue) / "Engine" / "Build" / "Build.version").write_text(
            "{not json", encoding="utf-8")
        ident = self._ident()
        self.assertIsNone(ident.key)
        self.assertFalse(ident.certifiable)
        self.assertIn("engine build identity unavailable", ident.reason)

    def test_engine_build_id_reads_a_real_install_and_survives_a_bogus_path(self):
        self.assertEqual("5.8.0+55116800", rg.engine_build_id(self.ue))
        self.assertIsNone(rg.engine_build_id("Z:/definitely/not/an/engine"))

    def test_git_failure_means_no_key_never_a_wrong_one(self):
        ident = self._ident(run_git=_broken_git)
        self.assertIsNone(ident.key)
        self.assertFalse(ident.certifiable)
        self.assertTrue(ident.reason)

    def test_unresolved_spec_means_no_key(self):
        ident = rg.identity_for(self.repo, "t-a", None, self.ue,
                                hostname="boxA", run_git=_fake_git())
        self.assertIsNone(ident.key)


# --------------------------------------------------------------------------- #
# The store.                                                                   #
# --------------------------------------------------------------------------- #

class TestCertStore(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.path = self.dir / "runs" / ".refgate-certs.json"
        self.ident = rg.GateIdentity(
            task_id="setA/t-a", key="k1", dirty=False,
            ue_root="C:/UE_5.8", hostname="boxA")

    def test_certify_roundtrips_through_disk(self):
        store = rg.CertStore(self.path)
        rec = store.certify(self.ident, "headsha", now="2026-08-06 21:00 UTC")
        self.assertEqual(rec["substrate_rev"], "headsha")
        again = rg.CertStore(self.path)
        self.assertEqual(again.valid(self.ident)["ts"], "2026-08-06 21:00 UTC")

    def test_key_mismatch_reads_as_no_cert(self):
        store = rg.CertStore(self.path)
        store.certify(self.ident, "headsha")
        stale = rg.GateIdentity(task_id="setA/t-a", key="k2", dirty=False)
        self.assertIsNone(rg.CertStore(self.path).valid(stale))

    def test_dirty_or_keyless_identity_never_validates_or_certifies(self):
        store = rg.CertStore(self.path)
        store.certify(self.ident, "headsha")
        dirty = rg.GateIdentity(task_id="setA/t-a", key="k1", dirty=True)
        keyless = rg.GateIdentity(task_id="setA/t-a", key=None, dirty=False)
        self.assertIsNone(store.valid(dirty))
        self.assertIsNone(store.valid(keyless))
        self.assertIsNone(store.certify(dirty, "x"))
        self.assertIsNone(store.certify(keyless, "x"))

    def test_invalidate_drops_the_record_on_disk(self):
        store = rg.CertStore(self.path)
        store.certify(self.ident, "headsha")
        store.invalidate("setA/t-a")
        self.assertIsNone(rg.CertStore(self.path).valid(self.ident))

    def test_corrupt_or_wrong_schema_store_loads_empty(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("{not json", encoding="utf-8")
        self.assertIsNone(rg.CertStore(self.path).valid(self.ident))
        self.path.write_text(json.dumps({"schema": 999, "certs": {
            "setA/t-a": {"key": "k1"}}}), encoding="utf-8")
        self.assertIsNone(rg.CertStore(self.path).valid(self.ident))


# --------------------------------------------------------------------------- #
# The `cb refgate` command (injected child + injected git).                     #
# --------------------------------------------------------------------------- #

class _Child:
    """Stands in for run_task.py: records each cmd, answers canned."""

    def __init__(self, returncode=0, stdout="overall : PASS"):
        self.returncode, self.stdout = returncode, stdout
        self.cmds = []

    def __call__(self, cmd, **kw):
        self.cmds.append([str(c) for c in cmd])
        return types.SimpleNamespace(returncode=self.returncode,
                                     stdout=self.stdout, stderr="")

    def gated_tasks(self):
        out = []
        for cmd in self.cmds:
            spec = Path(cmd[cmd.index("--task") + 1])
            out.append(spec.parent.name)      # tasks/<set>/<id>/task.md
        return out


class TestCmdRefgate(unittest.TestCase):
    def setUp(self):
        import aura_rig.envgate as _envgate
        self.repo = Path(tempfile.mkdtemp())
        for tid in ("t-a", "t-b"):
            d = self.repo / "tasks" / "setA" / tid
            (d / "reference").mkdir(parents=True)
            (d / "task.md").write_text(
                f"---\nid: {tid}\nlayers: [L1]\n---\n\n# {tid}\n",
                encoding="utf-8")
            (d / "reference" / "stub.txt").write_text("x", encoding="utf-8")
        # A task with NO committed reference: --all must skip it silently,
        # an explicit request must FAIL the gate.
        d = self.repo / "tasks" / "setA" / "t-noref"
        d.mkdir(parents=True)
        (d / "task.md").write_text(
            "---\nid: t-noref\nlayers: [L1]\n---\n\n# t-noref\n",
            encoding="utf-8")
        gate = mock.patch.object(_envgate, "enforce", lambda *a, **k: True)
        gate.start()
        self.addCleanup(gate.stop)
        git = mock.patch.object(rg, "_run_git", _fake_git())
        git.start()
        self.addCleanup(git.stop)
        _fake_engine(self.repo)      # the cert key now includes the engine build
        env = mock.patch.dict(os.environ, {"CB_UE_ROOT": str(self.repo)})
        env.start()
        self.addCleanup(env.stop)

    def _ctx(self):
        return types.SimpleNamespace(
            ue=Path("UnrealEditor"), py_exe="py", py_pre=[],
            paths=types.SimpleNamespace(craftbench=self.repo,
                                        uproject=self.repo / "X.uproject"))

    @staticmethod
    def _args(**kw):
        base = dict(outputs="", refgate_all=False, force=False,
                    no_preflight=True)
        base.update(kw)
        return types.SimpleNamespace(**base)

    def _refgate(self, args, child=None):
        from aura_rig import cb as _cb
        child = child or _Child()
        said = []
        with mock.patch.object(_cb.subprocess, "run", child), \
             mock.patch.object(_cb, "_say", said.append):
            rc = _cb.cmd_refgate(self._ctx(), args)
        return rc, "\n".join(said), child

    def _certs_on_disk(self):
        try:
            data = json.loads((self.repo / "runs" / ".refgate-certs.json")
                              .read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data.get("certs", {})

    def test_no_tasks_is_a_usage_error(self):
        rc, text, child = self._refgate(self._args())
        self.assertEqual(rc, 2)
        self.assertIn("cb refgate <task>", text)
        self.assertEqual(child.cmds, [])

    def test_unknown_task_reports_the_resolution_error(self):
        rc, text, child = self._refgate(self._args(outputs="setA/nope"))
        self.assertEqual(rc, 2)
        self.assertIn("task not found", text)
        self.assertEqual(child.cmds, [])

    def test_all_with_a_task_list_is_a_usage_error(self):
        rc, text, child = self._refgate(
            self._args(outputs="setA/t-a", refgate_all=True))
        self.assertEqual(rc, 2)
        self.assertIn("not both", text)

    def test_gates_each_listed_task_and_certifies(self):
        rc, text, child = self._refgate(
            self._args(outputs="setA/t-a,setA/t-b,setA/t-a"))
        self.assertEqual(rc, 0)
        self.assertEqual(child.gated_tasks(), ["t-a", "t-b"],
                         "deduped, one grade per task")
        self.assertIn("refgate [1/2] setA/t-a", text)
        self.assertIn("refgate [2/2] setA/t-b", text)
        self.assertIn("2/2 gate(s) OK", text)
        self.assertIn("2 graded PASS", text)
        certs = self._certs_on_disk()
        self.assertIn("setA/t-a", certs)
        self.assertIn("setA/t-b", certs)
        self.assertEqual(certs["setA/t-a"]["substrate_rev"], "headsha")

    def test_second_run_self_skips_on_the_certificate(self):
        self._refgate(self._args(outputs="setA/t-a"))
        rc, text, child = self._refgate(self._args(outputs="setA/t-a"))
        self.assertEqual(rc, 0)
        self.assertEqual(child.cmds, [], "a certified task must not regrade")
        self.assertIn("already certified", text)
        self.assertIn("--force", text)
        self.assertIn("1 already certified (skipped)", text)

    def test_force_regrades_despite_a_valid_certificate(self):
        self._refgate(self._args(outputs="setA/t-a"))
        rc, text, child = self._refgate(
            self._args(outputs="setA/t-a", force=True))
        self.assertEqual(rc, 0)
        self.assertEqual(child.gated_tasks(), ["t-a"])
        self.assertNotIn("already certified", text)

    def test_task_tree_change_invalidates_the_certificate(self):
        self._refgate(self._args(outputs="setA/t-a"))
        with mock.patch.object(rg, "_run_git", _fake_git(task_sha="CHANGED")):
            rc, text, child = self._refgate(self._args(outputs="setA/t-a"))
        self.assertEqual(rc, 0)
        self.assertEqual(child.gated_tasks(), ["t-a"],
                         "a changed task tree must regrade")

    def test_substrate_change_invalidates_the_certificate(self):
        self._refgate(self._args(outputs="setA/t-a"))
        with mock.patch.object(rg, "_run_git", _fake_git(sub_sha="CHANGED")):
            rc, text, child = self._refgate(self._args(outputs="setA/t-a"))
        self.assertEqual(rc, 0)
        self.assertEqual(child.gated_tasks(), ["t-a"])

    def test_dirty_tree_grades_but_never_certifies_or_skips(self):
        dirty = _fake_git(dirty=" M tasks/setA/t-a/task.md")
        with mock.patch.object(rg, "_run_git", dirty):
            rc, text, child = self._refgate(self._args(outputs="setA/t-a"))
            self.assertEqual(rc, 0)
            self.assertEqual(child.gated_tasks(), ["t-a"])
            self.assertIn("NOT certified", text)
            self.assertNotIn("setA/t-a", self._certs_on_disk())
            rc2, text2, child2 = self._refgate(self._args(outputs="setA/t-a"))
            self.assertEqual(child2.gated_tasks(), ["t-a"],
                             "no skip while the tree stays dirty")

    def test_gate_fail_exits_9_with_evidence_and_never_certifies(self):
        from aura_rig.cb import EXIT_BENCH_REFGATE_FAIL
        child = _Child(returncode=1, stdout=(
            "L1 ok\nverdict-evidence: stamina never drained\noverall : FAIL"))
        rc, text, child = self._refgate(
            self._args(outputs="setA/t-a,setA/t-b"), child=child)
        self.assertEqual(rc, EXIT_BENCH_REFGATE_FAIL)
        self.assertIn("verdict-evidence: stamina never drained", text)
        self.assertIn("refgate: FAIL", text)
        self.assertEqual(child.gated_tasks(), ["t-a"],
                         "fail-and-STOP: t-b never graded")
        self.assertEqual(self._certs_on_disk(), {},
                         "a FAIL must never leave a certificate")

    def test_gate_fail_removes_a_prior_certificate(self):
        self._refgate(self._args(outputs="setA/t-a"))
        self.assertIn("setA/t-a", self._certs_on_disk())
        with mock.patch.object(rg, "_run_git", _fake_git(task_sha="CHANGED")):
            rc, _text, _child = self._refgate(
                self._args(outputs="setA/t-a"),
                child=_Child(returncode=1, stdout="overall : FAIL"))
        self.assertEqual(rc, 9)
        self.assertNotIn("setA/t-a", self._certs_on_disk())

    def test_all_sweeps_every_committed_reference(self):
        rc, text, child = self._refgate(self._args(refgate_all=True))
        self.assertEqual(rc, 0)
        self.assertEqual(child.gated_tasks(), ["t-a", "t-b"],
                         "--all gates exactly the tasks holding a reference")
        self.assertNotIn("t-noref", text)
        self.assertIn("2/2 gate(s) OK", text)

    def test_missing_reference_on_an_explicit_task_fails_the_gate(self):
        rc, text, child = self._refgate(self._args(outputs="setA/t-noref"))
        self.assertEqual(rc, 9)
        self.assertIn("no committed reference", text)
        self.assertEqual(child.cmds, [], "nothing to grade — the gate itself "
                                         "reports the missing reference")


class TestRefgateParserWiring(unittest.TestCase):
    def test_refgate_flags_parse(self):
        from aura_rig import cb as _cb
        ns = _cb.build_parser().parse_args(["refgate", "setA/t-a", "--force"])
        self.assertEqual(ns.outputs, "setA/t-a")
        self.assertFalse(ns.refgate_all)
        self.assertTrue(ns.force)
        ns = _cb.build_parser().parse_args(["refgate", "--all"])
        self.assertTrue(ns.refgate_all)

    def test_bench_refgates_and_deprecated_skip_parse(self):
        from aura_rig import cb as _cb
        ns = _cb.build_parser().parse_args(["bench", "--refgates"])
        self.assertTrue(ns.refgates)
        self.assertFalse(ns.skip_refgates)
        ns = _cb.build_parser().parse_args(["bench", "--skip-refgates"])
        self.assertTrue(ns.skip_refgates)

    def test_stray_second_positional_is_refused(self):
        from aura_rig import cb as _cb
        err = _cb.reject_stray_positionals(
            _cb.build_parser().parse_args(["refgate", "setA/t-a", "stray"]))
        self.assertIsNotNone(err)
        self.assertIn("stray", err)


if __name__ == "__main__":
    unittest.main()


# --------------------------------------------------------------------------- #
# PER-TASK PARTITIONS (2026-08-19).                                            #
#                                                                              #
# The substrate sha used to be the WHOLE tree, so authoring one task dropped   #
# every other task's certificate — 62 at a time — and ten untracked task       #
# folders made every task permanently "dirty", i.e. the gate cached nothing.   #
# These tests pin BOTH directions: another task's partition must not key, and  #
# everything shared still must. The second half is the one that matters: an    #
# over-eager exclusion would keep a certificate alive across a change that can #
# alter the grade, which is the only dangerous direction.                      #
# --------------------------------------------------------------------------- #

_SUB = "UE-projects/CraftBenchTemplate"


def _tree_git(files, *, status="", head="headsha", task_sha="tsha",
              ver_sha="vsha"):
    """A run_git fake that serves a real `ls-tree -r` listing and a real
    `status --porcelain`, so the partition filter is actually exercised
    rather than falling back to the whole-tree sha."""
    listing = "\n".join(f"100644 blob {i:040x}\t{p}" for i, p in enumerate(files))

    def _run(args, repo):
        if args[:2] == ["rev-parse", "HEAD"]:
            return 0, head
        if args and args[0] == "ls-tree":
            return 0, listing
        if args and args[0] == "rev-parse":
            rel = args[1]
            if "UE-projects" in rel:
                return 0, "whole-tree-sha"
            if "verify-single" in rel:
                return 0, ver_sha
            return 0, task_sha
        if args and args[0] == "status":
            # Real git filters by the `-- <paths>` it was given; a fake that
            # ignores them makes the task/verifier dirty check see SUBSTRATE
            # dirt and hides the very partitioning under test.
            wanted = args[args.index("--") + 1:] if "--" in args else []
            if not wanted:
                return 0, status
            keep = [ln for ln in status.splitlines()
                    if any(ln[3:].strip().startswith(w) for w in wanted)]
            return 0, "\n".join(keep)
        return 1, ""
    return _run


class PerTaskPartitions(unittest.TestCase):
    def setUp(self):
        self.repo = Path(tempfile.mkdtemp())
        d = self.repo / "tasks" / "setA" / "t-a"
        (d / "reference").mkdir(parents=True)
        (d / "task.md").write_text(
            "---\nid: t-a\nlayers: [L1]\n---\n\n# t-a\n", encoding="utf-8")
        self.spec = d / "task.md"
        self.ue = _fake_engine(Path(tempfile.mkdtemp()))
        self.base_files = [
            "Config/DefaultEngine.ini",
            "Source/CraftBenchTemplate/SharedCharacter.h",
            "Source/CraftBenchTemplate/Tasks/t-a/MyActor.h",
            "Source/CraftBenchTemplate/Tasks/t-b/TheirActor.h",
            "Content/Maps/t-a/L_Mine.umap",
            "Content/Maps/t-b/L_Theirs.umap",
            "Content/LevelPrototyping/Materials/M_Shared.uasset",
        ]

    def _key(self, files=None, status=""):
        return rg.identity_for(
            self.repo, "t-a", self.spec, self.ue, hostname="boxA",
            run_git=_tree_git(files or self.base_files, status=status)).key

    def _sub(self, old, new, files=None):
        return [new if f == old else f for f in (files or self.base_files)]

    # ---- the exclusions (the whole point) --------------------------------
    def test_another_tasks_map_does_not_invalidate(self):
        self.assertEqual(
            self._key(),
            self._key(self._sub("Content/Maps/t-b/L_Theirs.umap",
                                "Content/Maps/t-b/L_Renamed.umap")),
            "another task's map cannot change this task's grade")

    def test_another_tasks_scaffold_source_does_not_invalidate(self):
        self.assertEqual(
            self._key(),
            self._key(self._sub("Source/CraftBenchTemplate/Tasks/t-b/TheirActor.h",
                                "Source/CraftBenchTemplate/Tasks/t-b/Other.h")),
            "another task's own folder fails LOUD (build break), never silently")

    def test_a_whole_new_task_appearing_does_not_invalidate(self):
        self.assertEqual(
            self._key(),
            self._key(self.base_files + [
                "Source/CraftBenchTemplate/Tasks/t-z/New.h",
                "Content/Maps/t-z/L_New.umap"]),
            "authoring a task must not drop every other certificate")

    # ---- the inclusions (proof it is not over-excluding) ------------------
    def test_this_tasks_own_map_DOES_invalidate(self):
        self.assertNotEqual(
            self._key(),
            self._key(self._sub("Content/Maps/t-a/L_Mine.umap",
                                "Content/Maps/t-a/L_Mine2.umap")))

    def test_this_tasks_own_source_DOES_invalidate(self):
        self.assertNotEqual(
            self._key(),
            self._key(self._sub("Source/CraftBenchTemplate/Tasks/t-a/MyActor.h",
                                "Source/CraftBenchTemplate/Tasks/t-a/Other.h")))

    def test_SHARED_source_DOES_invalidate(self):
        self.assertNotEqual(
            self._key(),
            self._key(self._sub("Source/CraftBenchTemplate/SharedCharacter.h",
                                "Source/CraftBenchTemplate/SharedChar2.h")),
            "shared code is outside Tasks/ and must key for everyone")

    def test_SHARED_content_DOES_invalidate(self):
        self.assertNotEqual(
            self._key(),
            self._key(self._sub(
                "Content/LevelPrototyping/Materials/M_Shared.uasset",
                "Content/LevelPrototyping/Materials/M_Shared2.uasset")))

    def test_config_DOES_invalidate(self):
        self.assertNotEqual(
            self._key(),
            self._key(self._sub("Config/DefaultEngine.ini",
                                "Config/DefaultGame.ini")))

    # ---- dirt, the half that made the gate cache nothing ------------------
    def test_another_tasks_dirt_leaves_this_task_certifiable(self):
        ident = rg.identity_for(
            self.repo, "t-a", self.spec, self.ue, hostname="boxA",
            run_git=_tree_git(self.base_files,
                              status=f"?? {_SUB}/Content/Maps/t-b/\n"
                                     f"?? {_SUB}/Source/CraftBenchTemplate/Tasks/t-b/"))
        self.assertFalse(ident.dirty)
        self.assertTrue(ident.certifiable)

    def test_this_tasks_own_dirt_still_blocks_certification(self):
        ident = rg.identity_for(
            self.repo, "t-a", self.spec, self.ue, hostname="boxA",
            run_git=_tree_git(self.base_files,
                              status=f" M {_SUB}/Content/Maps/t-a/L_Mine.umap"))
        self.assertTrue(ident.dirty)
        self.assertFalse(ident.certifiable)

    def test_SHARED_dirt_still_blocks_certification(self):
        ident = rg.identity_for(
            self.repo, "t-a", self.spec, self.ue, hostname="boxA",
            run_git=_tree_git(self.base_files,
                              status=f" M {_SUB}/Source/CraftBenchTemplate/SharedCharacter.h"))
        self.assertTrue(ident.dirty)

    # ---- the fallback stays conservative ---------------------------------
    def test_ls_tree_failure_falls_back_to_the_whole_tree_sha(self):
        ident = rg.identity_for(
            self.repo, "t-a", self.spec, self.ue, hostname="boxA",
            run_git=_fake_git())
        self.assertIsNotNone(ident.key,
                             "no ls-tree must degrade to over-invalidating, "
                             "never to a missing or permissive key")

"""``--submission-from-project`` extracts exactly what the SANDBOX accepts.

WHY THIS MODULE EXISTS (2026-08-19). ``run_task.extract_writable_subset_from_project``
was the FIFTH copy of the "which files may an agent submit" rule, and it had
drifted: it read ``manifest.writable`` + ``manifest.deny`` and never consulted
``config_writable``, while a comment claimed it mirrored ``sandbox._is_writable``.
The identical defect in the other collector (``tools/run-agent/snapshot.py``) is
what made ``bp/t3-piercing-projectile`` unwinnable — 8 of 9 L2I checks reported
``defined=[]`` because the agent's correct collision vocabulary sat in
``Config/DefaultEngine.ini`` and the collector dropped it before grading.

The fix DELEGATES acceptance to ``sandbox._is_writable``. These tests pin the
BEHAVIOUR of that delegation rather than the delegation itself, because a
delegation can be undone by "helpfully" re-implementing the rule again. Each test
below is paired, in this module's own ``TestBrokenVariantsGoRed``, with a
concrete broken implementation it catches — an assertion that cannot tell a
correct implementation from a broken one is not a test.

No UE install required; pure filesystem + manifest logic.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_VERIFY = _HERE.parent
if str(_VERIFY) not in sys.path:
    sys.path.insert(0, str(_VERIFY))

import run_task  # noqa: E402
from sandbox import WritableManifest, scan_submission  # noqa: E402

#: The real ThirdPerson substrate manifest shape (UE-projects/ThirdPerson/
#: AGENT_WRITABLE.json, read 2026-08-19), trimmed to the entries these tests
#: exercise. ``config_writable`` is the key the pre-fix implementation ignored.
THIRDPERSON = WritableManifest(
    substrate="ThirdPerson",
    game_module="ThirdPerson",
    writable=("Source/ThirdPerson/", "Content/Tasks/"),
    asset_writable=("Content/Tasks/", "Content/Blueprints/"),
    config_writable=("Config/DefaultEngine.ini", "Config/DefaultInput.ini"),
    deny=("Source/CraftBenchTests/", "Content/Maps/", "Plugins/",
          "ThirdPerson.uproject", "AGENT_WRITABLE.json"),
)

#: A manifest predating ``asset_writable`` / ``config_writable`` (the
#: CraftBenchTemplate shape, which denies all of ``Config/``). Used to pin that
#: this change moved NOTHING for substrates that never opted in.
LEGACY_TEMPLATE = WritableManifest(
    substrate="CraftBenchTemplate",
    game_module="CraftBenchTemplate",
    writable=("Source/CraftBenchTemplate/", "Content/Tasks/"),
    deny=("Source/CraftBenchTests/", "Config/", "Content/Maps/", "Plugins/",
          "CraftBenchTemplate.uproject", "AGENT_WRITABLE.json"),
)


def _write(root: Path, rel: str, text: str = "x") -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _extracted_rels(out_dir: Path) -> set[str]:
    return {
        p.relative_to(out_dir).as_posix()
        for p in out_dir.rglob("*")
        if p.is_file()
    }


class _ProjectCase(unittest.TestCase):
    """Base: builds a throwaway UE-shaped project and cleans up every tempdir."""

    def setUp(self) -> None:
        self._tmps: list[Path] = []
        self.project = Path(tempfile.mkdtemp(prefix="cb-test-project-"))
        self._tmps.append(self.project)

    def tearDown(self) -> None:
        for t in self._tmps:
            shutil.rmtree(t, ignore_errors=True)

    def extract(self, manifest, *, capture_assets=False, impl=None) -> set[str]:
        """Run the extractor (or an injected broken ``impl``) and list its output.

        Looked up on the module at CALL time so ``TestBrokenVariantsGoRed`` can
        substitute an implementation and re-run these same assertions.
        """
        fn = impl or run_task.extract_writable_subset_from_project
        out = fn(self.project, manifest, capture_assets=capture_assets)
        self._tmps.append(out)
        self._last_out = out
        return _extracted_rels(out)


class TestConfigWritableIsCaptured(_ProjectCase):
    """The defect itself: a ``config_writable`` file must reach the grader."""

    def _build(self) -> None:
        _write(self.project, "Source/ThirdPerson/MyActor.cpp", "// code")
        _write(self.project, "Config/DefaultEngine.ini",
               "[/Script/Engine.CollisionProfile]\n+Profiles=(Name=\"Bullet\")\n")
        _write(self.project, "Config/DefaultInput.ini", "[Input]\nKey=A\n")

    def test_config_writable_file_is_captured(self):
        self._build()
        rels = self.extract(THIRDPERSON)
        self.assertIn("Config/DefaultEngine.ini", rels)
        self.assertIn("Config/DefaultInput.ini", rels)

    def test_captured_config_bytes_are_the_agents(self):
        """Captured, not merely present: the graded bytes are what the agent wrote.

        A collector that created an empty placeholder would satisfy the
        membership assertion above and still lose the answer.
        """
        self._build()
        self.extract(THIRDPERSON)
        got = (self._last_out / "Config/DefaultEngine.ini").read_text(encoding="utf-8")
        self.assertIn('+Profiles=(Name="Bullet")', got)

    def test_missing_config_file_is_simply_absent(self):
        """A listed config the project does not have is not invented."""
        _write(self.project, "Source/ThirdPerson/MyActor.cpp", "// code")
        rels = self.extract(THIRDPERSON)
        self.assertNotIn("Config/DefaultEngine.ini", rels)
        self.assertIn("Source/ThirdPerson/MyActor.cpp", rels)


class TestConfigWritableIsExactNotPrefix(_ProjectCase):
    """``config_writable`` entries are EXACT rel-paths, never prefixes.

    The manifest's own ``_comment`` forbids a broad ``Config/`` prefix: those
    files are path-accepted here and only THEN semantically diff-gated against
    the task spec's ``config_allow``. A prefix reading would path-accept
    arbitrary engine-config edits.
    """

    def setUp(self) -> None:
        super().setUp()
        _write(self.project, "Source/ThirdPerson/MyActor.cpp", "// code")
        _write(self.project, "Config/DefaultEngine.ini", "[A]\nK=1\n")
        _write(self.project, "Config/DefaultGame.ini", "[B]\nK=2\n")
        _write(self.project, "Config/Windows/WindowsEngine.ini", "[C]\nK=3\n")
        # Sharp discriminator against a startswith() reading: this path has
        # "Config/DefaultEngine.ini" as a string prefix but is NOT that file.
        _write(self.project, "Config/DefaultEngine.ini.bak", "[D]\nK=4\n")

    def test_unlisted_config_file_is_not_captured(self):
        rels = self.extract(THIRDPERSON)
        self.assertIn("Config/DefaultEngine.ini", rels)
        self.assertNotIn("Config/DefaultGame.ini", rels)
        self.assertNotIn("Config/Windows/WindowsEngine.ini", rels)

    def test_prefix_lookalike_is_not_captured(self):
        rels = self.extract(THIRDPERSON)
        self.assertNotIn("Config/DefaultEngine.ini.bak", rels)


class TestDenyWins(_ProjectCase):
    """DENY beats every allow key, including one it is nested inside."""

    def test_deny_prefix_nested_under_a_writable_prefix(self):
        nested = WritableManifest(
            substrate="T", game_module="T",
            writable=("Content/Tasks/",),
            asset_writable=("Content/Tasks/",),
            # A verifier-owned answer key parked inside the agent's own folder.
            deny=("Content/Tasks/_verifier/",),
        )
        _write(self.project, "Content/Tasks/mine/Notes.txt", "agent work")
        _write(self.project, "Content/Tasks/_verifier/GOLD.txt", "answer key")
        rels = self.extract(nested)
        self.assertIn("Content/Tasks/mine/Notes.txt", rels)
        self.assertNotIn("Content/Tasks/_verifier/GOLD.txt", rels)

    def test_deny_wins_over_config_writable(self):
        """A rel-path both denied and config_writable is DENIED.

        ``config_lane``'s module docstring states this ordering as the safety
        property of the whole lane; it must hold on the collector too.
        """
        contradictory = WritableManifest(
            substrate="T", game_module="T",
            writable=("Source/ThirdPerson/",),
            config_writable=("Config/DefaultEngine.ini",),
            deny=("Config/",),
        )
        _write(self.project, "Source/ThirdPerson/A.cpp", "// code")
        _write(self.project, "Config/DefaultEngine.ini", "[A]\nK=1\n")
        rels = self.extract(contradictory)
        self.assertIn("Source/ThirdPerson/A.cpp", rels)
        self.assertNotIn("Config/DefaultEngine.ini", rels)

    def test_deny_wins_in_the_asset_sweep(self):
        """The real shape: Content/Maps/ is the verifier's own task maps."""
        _write(self.project, "Content/Tasks/t/BP_Thing.uasset", "asset")
        _write(self.project, "Content/Blueprints/BP_Other.uasset", "asset")
        _write(self.project, "Content/Maps/t/L_Task.umap", "verifier map")
        rels = self.extract(THIRDPERSON, capture_assets=True)
        self.assertIn("Content/Tasks/t/BP_Thing.uasset", rels)
        self.assertIn("Content/Blueprints/BP_Other.uasset", rels)
        self.assertNotIn("Content/Maps/t/L_Task.umap", rels)

    def test_non_asset_outside_writable_stays_out_of_the_asset_sweep(self):
        """``asset_writable`` gates on the .uasset/.umap extension set.

        A non-asset file under an asset_writable-only prefix is NOT submittable
        (sandbox._is_writable checks _is_asset_file first), so it must not ride
        in on the capture path.
        """
        _write(self.project, "Content/Blueprints/BP_Ok.uasset", "asset")
        _write(self.project, "Content/Blueprints/notes.txt", "not an asset")
        rels = self.extract(THIRDPERSON, capture_assets=True)
        self.assertIn("Content/Blueprints/BP_Ok.uasset", rels)
        self.assertNotIn("Content/Blueprints/notes.txt", rels)


class TestAgreesWithTheVerifiersOwnScan(_ProjectCase):
    """Semantic (not naming) equivalence: the sandbox accepts ALL of our output.

    This is the check that survives a rename or an inlining of the predicate —
    it runs sandbox's PUBLIC ``scan_submission`` over the extracted tree, which
    is exactly what ``run_task.main`` does next.
    """

    def test_scan_submission_reports_zero_violations(self):
        _write(self.project, "Source/ThirdPerson/MyActor.cpp", "// code")
        _write(self.project, "Source/ThirdPerson/Intermediate/Build/x.obj", "obj")
        _write(self.project, "Content/Tasks/t/BP_Thing.uasset", "asset")
        _write(self.project, "Content/Blueprints/BP_Other.uasset", "asset")
        _write(self.project, "Content/Maps/t/L_Task.umap", "verifier map")
        _write(self.project, "Config/DefaultEngine.ini", "[A]\nK=1\n")
        _write(self.project, "Config/DefaultGame.ini", "[B]\nK=2\n")
        _write(self.project, "Source/CraftBenchTests/Fixture.cpp", "// verifier")
        self.extract(THIRDPERSON, capture_assets=True)
        result = scan_submission(self._last_out, THIRDPERSON)
        self.assertTrue(
            result.ok,
            f"extractor produced sandbox violations:\n{result.render_report()}",
        )
        self.assertIn(
            "Config/DefaultEngine.ini", {rel for _p, rel in result.accepted}
        )

    def test_build_detritus_is_not_submitted(self):
        """The detritus filter is NOT the sandbox rule — pin it separately.

        ``Source/ThirdPerson/Intermediate/**`` IS sandbox-acceptable (it is under
        a writable prefix); we drop it anyway because a live editor session
        leaves it there and copying it rewrites mtimes UBT reads. If someone
        removes the filter this test says so, instead of an L1 slowdown showing
        up as a mystery months later.
        """
        _write(self.project, "Source/ThirdPerson/MyActor.cpp", "// code")
        for rel in (
            "Source/ThirdPerson/Intermediate/Build/x.obj",
            "Source/ThirdPerson/Binaries/Win64/x.dll",
            "Source/ThirdPerson/Saved/Logs/x.log",
            "Source/ThirdPerson/DerivedDataCache/x.udd",
        ):
            _write(self.project, rel, "detritus")
        rels = self.extract(THIRDPERSON)
        self.assertEqual(rels, {"Source/ThirdPerson/MyActor.cpp"})


# ---------------------------------------------------------------------------
# Pre-fix implementation, kept VERBATIM, for the two jobs only it can do:
# (a) prove this change moved nothing for legacy manifests, and
# (b) prove the config assertions above actually go red on the real defect.
# ---------------------------------------------------------------------------


def _prefix_extract(project_root, manifest, *, capture_assets: bool = False):
    """``extract_writable_subset_from_project`` as it stood before 2026-08-19.

    Copied verbatim (including its since-corrected "Mirrors sandbox._is_writable"
    comment) — do NOT tidy it. Its value is being exactly what shipped.
    """
    out = Path(tempfile.mkdtemp(prefix="craftbench-extracted-"))
    for writable_prefix in manifest.writable:
        src_dir = project_root / writable_prefix
        if not src_dir.exists():
            continue
        for f in src_dir.rglob("*"):
            if not f.is_file():
                continue
            rel = f.relative_to(project_root).as_posix()
            if any(rel.startswith(d) for d in manifest.deny):
                continue
            if any(seg in {"Binaries", "Intermediate", "DerivedDataCache", "Saved"}
                   for seg in rel.split("/")):
                continue
            dst = out / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dst)

    if capture_assets:
        from asset_capture import capture_content_assets

        # Mirrors sandbox._is_writable  <- the claim that had drifted.
        allow_prefixes = tuple(manifest.asset_writable) + tuple(manifest.writable)
        capture_content_assets(
            project_root=project_root,
            out_dir=out,
            deny_prefixes=manifest.deny,
            allow_prefixes=allow_prefixes,
        )
    return out


def _broken_config_as_prefix(project_root, manifest, *, capture_assets=False):
    """The tempting WRONG fix: treat ``config_writable`` as a prefix set.

    This is what "just sweep Config/" looks like. It path-accepts arbitrary
    engine-config edits, which the manifest's ``_comment`` explicitly forbids.
    """
    out = _prefix_extract(project_root, manifest, capture_assets=capture_assets)
    for entry in manifest.config_writable:
        base = project_root / entry.rsplit("/", 1)[0]
        if not base.is_dir():
            continue
        for f in base.rglob("*"):
            if not f.is_file():
                continue
            rel = f.relative_to(project_root).as_posix()
            dst = out / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dst)
    return out


def _broken_allow_before_deny(project_root, manifest, *, capture_assets=False):
    """The other tempting WRONG fix: check allow first and forget deny wins."""
    out = Path(tempfile.mkdtemp(prefix="craftbench-extracted-"))

    def _matches(rel, prefix):
        p = prefix.rstrip("/")
        return rel == p or rel.startswith(p + "/")

    roots = list(manifest.writable) + list(manifest.asset_writable)
    for prefix in roots:
        src_dir = project_root / prefix
        if not src_dir.is_dir():
            continue
        for f in src_dir.rglob("*"):
            if not f.is_file():
                continue
            rel = f.relative_to(project_root).as_posix()
            if any(seg in {"Binaries", "Intermediate", "DerivedDataCache", "Saved"}
                   for seg in rel.split("/")):
                continue
            if not any(_matches(rel, a) for a in roots):
                continue
            dst = out / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dst)
    for entry in manifest.config_writable:
        f = project_root / entry
        if f.is_file():
            dst = out / entry
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dst)
    return out


class TestLegacyManifestUnchanged(_ProjectCase):
    """A manifest with no ``config_writable`` behaves EXACTLY as it did before.

    Byte-equality against the verbatim pre-fix implementation on the same tree,
    so the delegation is provably a fix and not a rewrite with side effects.
    """

    def _tree(self) -> None:
        _write(self.project, "Source/CraftBenchTemplate/Tasks/t0/A.cpp", "// a")
        _write(self.project, "Source/CraftBenchTemplate/Tasks/t0/A.h", "// h")
        _write(self.project, "Source/CraftBenchTemplate/Intermediate/x.obj", "o")
        _write(self.project, "Source/CraftBenchTests/Fixture.cpp", "// verifier")
        _write(self.project, "Content/Tasks/t0/BP_Thing.uasset", "asset")
        _write(self.project, "Content/Maps/L_Sanity.umap", "map")
        _write(self.project, "Config/DefaultEngine.ini", "[A]\nK=1\n")

    def _compare(self, capture_assets: bool) -> None:
        self._tree()
        new_rels = self.extract(LEGACY_TEMPLATE, capture_assets=capture_assets)
        new_out = self._last_out
        old_rels = self.extract(
            LEGACY_TEMPLATE, capture_assets=capture_assets, impl=_prefix_extract
        )
        old_out = self._last_out
        self.assertEqual(new_rels, old_rels)
        for rel in sorted(new_rels):
            self.assertEqual(
                (new_out / rel).read_bytes(), (old_out / rel).read_bytes(), rel
            )
        # And the tree is not empty, or the equality above proves nothing.
        self.assertIn("Source/CraftBenchTemplate/Tasks/t0/A.cpp", new_rels)
        self.assertNotIn("Config/DefaultEngine.ini", new_rels)

    def test_source_only_extraction_is_byte_identical(self):
        self._compare(capture_assets=False)

    def test_asset_capture_extraction_is_byte_identical(self):
        self._compare(capture_assets=True)


class TestBrokenVariantsGoRed(_ProjectCase):
    """Every assertion above must be able to FAIL. Proof, not assertion.

    Each broken implementation is run through the SAME assertions the real tests
    use; the test passes only when those assertions raise. A check that cannot
    tell "no" from "could not tell" is not a check.
    """

    def _assert_fails(self, fn, msg):
        with self.assertRaises(AssertionError, msg=msg):
            fn()

    def test_prefix_impl_drops_the_config_file(self):
        _write(self.project, "Source/ThirdPerson/A.cpp", "// code")
        _write(self.project, "Config/DefaultEngine.ini", "[A]\nK=1\n")
        rels = self.extract(THIRDPERSON, impl=_prefix_extract)
        self._assert_fails(
            lambda: self.assertIn("Config/DefaultEngine.ini", rels),
            "the pre-fix implementation must fail the config-capture assertion",
        )

    def test_prefix_impl_fails_the_sandbox_agreement_check(self):
        """The DEFECT stated in sandbox terms: the sandbox would accept a file
        the pre-fix collector never handed it. Asserted as the missing-accepted
        path, since a dropped file cannot show up as a violation."""
        _write(self.project, "Source/ThirdPerson/A.cpp", "// code")
        _write(self.project, "Config/DefaultEngine.ini", "[A]\nK=1\n")
        self.extract(THIRDPERSON, impl=_prefix_extract)
        result = scan_submission(self._last_out, THIRDPERSON)
        accepted = {rel for _p, rel in result.accepted}
        self._assert_fails(
            lambda: self.assertIn("Config/DefaultEngine.ini", accepted),
            "pre-fix output must not contain the config file",
        )

    def test_config_as_prefix_impl_captures_an_unlisted_config(self):
        _write(self.project, "Source/ThirdPerson/A.cpp", "// code")
        _write(self.project, "Config/DefaultEngine.ini", "[A]\nK=1\n")
        _write(self.project, "Config/DefaultGame.ini", "[B]\nK=2\n")
        _write(self.project, "Config/DefaultEngine.ini.bak", "[D]\nK=4\n")
        rels = self.extract(THIRDPERSON, impl=_broken_config_as_prefix)
        self._assert_fails(
            lambda: self.assertNotIn("Config/DefaultGame.ini", rels),
            "a prefix reading of config_writable must fail the exactness test",
        )
        self._assert_fails(
            lambda: self.assertNotIn("Config/DefaultEngine.ini.bak", rels),
            "a prefix reading must also fail the lookalike test",
        )

    def test_allow_before_deny_impl_captures_a_denied_path(self):
        nested = WritableManifest(
            substrate="T", game_module="T",
            writable=("Content/Tasks/",),
            asset_writable=("Content/Tasks/",),
            deny=("Content/Tasks/_verifier/",),
        )
        _write(self.project, "Content/Tasks/mine/Notes.txt", "agent work")
        _write(self.project, "Content/Tasks/_verifier/GOLD.txt", "answer key")
        rels = self.extract(nested, impl=_broken_allow_before_deny)
        self._assert_fails(
            lambda: self.assertNotIn("Content/Tasks/_verifier/GOLD.txt", rels),
            "an allow-before-deny implementation must fail the deny-wins test",
        )

    def test_allow_before_deny_impl_also_captures_a_denied_config(self):
        contradictory = WritableManifest(
            substrate="T", game_module="T",
            writable=("Source/ThirdPerson/",),
            config_writable=("Config/DefaultEngine.ini",),
            deny=("Config/",),
        )
        _write(self.project, "Source/ThirdPerson/A.cpp", "// code")
        _write(self.project, "Config/DefaultEngine.ini", "[A]\nK=1\n")
        rels = self.extract(contradictory, impl=_broken_allow_before_deny)
        self._assert_fails(
            lambda: self.assertNotIn("Config/DefaultEngine.ini", rels),
            "deny must beat config_writable; this variant lets it through",
        )


class TestBoundToTheVerifiersPredicate(unittest.TestCase):
    """The delegation itself, so a re-implementation is caught at import time."""

    def test_run_task_binds_sandbox_is_writable(self):
        import sandbox

        self.assertIs(run_task._sandbox_is_writable, sandbox._is_writable)


if __name__ == "__main__":
    unittest.main()

"""Offline oracle for the t2-consistent-enum-names L2I grader.

No editor, no UE install, no tokens. A minimal fake ``unreal`` module models
exactly the surface the introspect script uses (the asset-registry handle,
per-object-path ``AssetData`` with ``asset_class_path``/``package_name``/
``get_tag_value``, ``get_referencers``/``get_dependencies``,
``get_assets_by_path``). The binary half (baseline + reference + variants)
is authored by a later headless boot, so every leg here is BUILT in the fake
world with exactly the GRADED-WORKDIR state the runner's overlay produces
(the leg builders mirror ``authoring/author_all_assets.py`` leg by leg,
including the overlay's baseline-resurrection semantics), and each leg's
EXACT check vector is pinned in both directions - which checks fail AND
which still pass. Every leg of ``discrimination/MATRIX.md`` is simulated and
joined against the REAL ``discriminate.parse_matrix`` + the REAL
``layers/l2_introspect`` parser.

What this pins:
  * the reference (clean rename, orphan branch) is 11/11 and the empty leg
    (the committed baseline unchanged) is a genuine 0/11 with its named
    token;
  * every negative leg's MATRIX substring is a literal the script PRINTS,
    on the check the matrix blames, and each leg fails EXACTLY the
    predicted check set;
  * the TRI-STATE contract: the Lane B state (correct-target redirector +
    unresaved referencer) PASSES 11/11 through the one-hop substitution; a
    wrong-target redirector fails C5 AND blocks substitution in C9; a
    CHAINED redirector fails (one-hop tag equals the intermediate); a
    duplicate-not-rename submission fails all six closure checks while the
    names-only checks pass.
    **``TestTriStateContract`` is the ONLY coverage of the tri-state's
    redirector branch** as of 2026-07-30: the planned
    ``redirector-wrong-target/`` folder leg was retired UNAUTHORED because
    the redirector residue is not manufacturable headless (three dead
    routes - notes.md section 5 RESOLVED-NEGATIVE (c)). The grader keeps the
    branch (a real agent can still produce the state), so these tests are
    what stop it rotting;
  * fail-closed probes: a forged redirector with a missing/garbage
    DestinationObject tag, a missing registry, an unreadable
    referencer/dependency list, and a missing old-path AssetData all grade
    tokens from ``UNCREDITED_TOKENS`` - never a pass, never a skip, never a
    MATRIX-creditable token;
  * C11 collapses folder listings to a PACKAGE-NAME SET (the SKEL_<Name>_C
    same-package duplicate lesson) and fails junk with
    ENUM_FOLDER_UNEXPECTED_ASSET;
  * echoed registry-derived text cannot inject an automation-result marker;
  * ASCII purity of the grader, no automation-marker substrings, a constant
    denominator of 11 on every leg including no-``unreal``, and the spec
    front matter's task-scoped ``allow_redirectors`` declaration.

The fake is deliberately dumb: it cannot prove the UE 5.8 registry
marshaling survives a real editor session - that is the authoring boot's job
(notes.md section 5, incl. the two named calibration pins: referencer-fixup
semantics and the DestinationObject tag shape) - but it does prove the
grader's LOGIC, its tri-state contract, and its printed tokens.
"""
import ast
import contextlib
import io
import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
_VERIFY = _TESTS.parent
_REPO = _VERIFY.parent.parent

sys.path.insert(0, str(_VERIFY))
sys.path.insert(0, str(_REPO / "tools" / "run-agent"))

from layers.l2_introspect import parse_introspect_verdict  # noqa: E402
from aura_rig.discriminate import parse_matrix  # noqa: E402
import spec as spec_mod  # noqa: E402

TASK_ID = "t2-consistent-enum-names"
TASK_DIR = _REPO / "tasks" / "bp" / TASK_ID
MATRIX_PATH = TASK_DIR / "discrimination" / "MATRIX.md"
SCRIPT_PATH = _VERIFY / "introspect" / "consistent_enum_names.py"
AUTHORING_PATH = TASK_DIR / "authoring" / "author_all_assets.py"
#: The multi-boot driver. Which legs a default pass runs lives HERE now (one
#: phase per boot - see the tombstone law in notes.md section 5), so the
#: retired-redirector-leg guards read this file, not a python constant.
RUNNER_PATH = TASK_DIR / "authoring" / "run_author_all_assets.sh"

EXPECTED_TOTAL = 11

PKG = "/Game/Tasks/%s" % TASK_ID
ED = "%s/Enums" % PKG
OLD_W, OLD_A = "%s/WeaponType" % ED, "%s/E_ammo_kind" % ED
OLD_D, OLD_R = "%s/enum_DamageType" % ED, "%s/ItemRarity" % ED
NEW_W, NEW_A = "%s/E_WeaponType" % ED, "%s/E_AmmoKind" % ED
NEW_D, NEW_R = "%s/E_DamageType" % ED, "%s/E_ItemRarity" % ED
BPA, BPB = "%s/BP_RefA" % PKG, "%s/BP_RefB" % PKG
DECOY = "%s/DecoyEnum" % PKG

#: The committed discrimination folders. ``redirector-wrong-target`` was
#: RETIRED UNAUTHORED 2026-07-30: the redirector residue is not
#: manufacturable headless (three dead routes - notes.md section 5
#: RESOLVED-NEGATIVE (c)), so it can never become a folder leg. The branch it
#: was meant to cover is now pinned by TestTriStateContract ONLY.
VARIANTS = ("duplicate-not-rename", "one-left-behind")

ALL_CHECKS = (
    "new_asset_weapon_type", "new_asset_ammo_kind", "new_asset_damage_type",
    "new_asset_item_rarity", "old_path_retired_weapon_type",
    "old_path_retired_ammo_kind", "old_path_retired_damage_type",
    "old_path_retired_item_rarity", "refs_resolved_bp_ref_a",
    "refs_resolved_bp_ref_b", "folder_inventory",
)


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "_consistent_enum_names_introspect", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = _load_script()


# --------------------------------------------------------------------------- #
# the fake unreal surface                                                      #
# --------------------------------------------------------------------------- #

class _ClassPath:
    def __init__(self, name):
        self.asset_name = name


class FakeAssetData:
    def __init__(self, pkg, cls, tags=None):
        self.package_name = pkg
        self.asset_class_path = _ClassPath(cls)
        self._tags = dict(tags or {})

    def is_valid(self):
        return True

    def get_tag_value(self, name):
        """Live-proven marshaling (spike facts D): plain str, or None when
        the tag does not exist."""
        return self._tags.get(name)


class _World:
    def __init__(self):
        self.assets = {}        # object path -> FakeAssetData
        self.referencers = {}   # pkg -> list[str] | None (None = read break)
        self.dependencies = {}  # pkg -> list[str] | None
        self.registry_broken = False


WORLD = _World()


def _obj(pkg, name=None):
    return "%s.%s" % (pkg, name or pkg.rsplit("/", 1)[1])


class _FakeRegistry:
    def wait_for_completion(self):
        pass

    def get_asset_by_object_path(self, path):
        return WORLD.assets.get(str(path))

    def get_assets_by_path(self, path, recursive=False):
        path = str(path)
        return [ad for ad in WORLD.assets.values()
                if str(ad.package_name).rsplit("/", 1)[0] == path]

    def get_referencers(self, pkg, _options):
        return WORLD.referencers.get(str(pkg), [])

    def get_dependencies(self, pkg, _options):
        return WORLD.dependencies.get(str(pkg), [])


class _Helpers:
    @staticmethod
    def get_asset_registry():
        if WORLD.registry_broken:
            return None
        return _FakeRegistry()


class _DependencyOptions:
    pass


class FakeUnreal:
    AssetRegistryHelpers = _Helpers
    AssetRegistryDependencyOptions = _DependencyOptions

    @staticmethod
    def log(msg):
        pass


def _add(pkg, cls, tags=None, name=None):
    WORLD.assets[_obj(pkg, name)] = FakeAssetData(pkg, cls, tags)


def _enum(pkg):
    _add(pkg, "UserDefinedEnum")


def _redirector(pkg, target_pkg=None, tag=Ellipsis):
    """A redirector AssetData at pkg. Default tag: the 5.8 export-path form
    the design cites (Class'/Game/Path.Name'); pass tag= to override."""
    if tag is Ellipsis:
        tag = "/Script/Engine.UserDefinedEnum'%s'" % _obj(target_pkg)
    tags = {} if tag is None else {"DestinationObject": tag}
    _add(pkg, "ObjectRedirector", tags)


def _reference_world():
    """The graded-workdir state of the CLEAN rename (Lane A): four new
    enums, four overlay-resurrected orphans, both BPs resaved onto the new
    packages. Engine/script deps included to pin out-of-scope filtering."""
    for p in (NEW_W, NEW_A, NEW_D, NEW_R, OLD_W, OLD_A, OLD_D, OLD_R):
        _enum(p)
    for p in (OLD_W, OLD_A, OLD_D, OLD_R):
        WORLD.referencers[p] = []
    _add(BPA, "Blueprint")
    _add(BPB, "Blueprint")
    WORLD.dependencies[BPA] = [NEW_W, NEW_A, "/Script/Engine",
                               "/Script/CoreUObject"]
    WORLD.dependencies[BPB] = [NEW_D, NEW_R, "/Script/Engine"]


def _baseline_world():
    """The committed baseline == the EMPTY leg's graded state."""
    for p in (OLD_W, OLD_A, OLD_D, OLD_R):
        _enum(p)
    WORLD.referencers[OLD_W] = [BPA]
    WORLD.referencers[OLD_A] = [BPA]
    WORLD.referencers[OLD_D] = [BPB]
    WORLD.referencers[OLD_R] = [BPB]
    _add(BPA, "Blueprint")
    _add(BPB, "Blueprint")
    WORLD.dependencies[BPA] = [OLD_W, OLD_A, "/Script/Engine"]
    WORLD.dependencies[BPB] = [OLD_D, OLD_R, "/Script/Engine"]


def run_leg(builder):
    """Run the introspect script against a freshly built world."""
    global WORLD
    WORLD = _World()
    builder()
    MOD.unreal = FakeUnreal
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        MOD.main()
    out = buf.getvalue()
    return out, parse_introspect_verdict(out)


def _by_id(parsed):
    return {c.id: c for c in parsed.checks}


def _fails(parsed):
    return {c.id for c in parsed.checks if not c.passed}


# --------------------------------------------------------------------------- #
# leg builders (mirror authoring/author_all_assets.py, graded-overlay state)   #
# --------------------------------------------------------------------------- #

LEGS = {}


def _leg(name):
    def deco(fn):
        LEGS[name] = fn
        return fn
    return deco


@_leg("reference")
def _ref():
    _reference_world()


@_leg("empty")
def _empty():
    _baseline_world()


@_leg("duplicate-not-rename")
def _duplicate():
    """Baseline + four fresh correctly-named copies; BPs untouched."""
    _baseline_world()
    for p in (NEW_W, NEW_A, NEW_D, NEW_R):
        _enum(p)


@_leg("one-left-behind")
def _one_left():
    """Three renamed (orphans resurrected), ItemRarity untouched: BP_RefB
    still depends on - and still counts as a referencer of - the old pkg."""
    for p in (NEW_W, NEW_A, NEW_D, OLD_W, OLD_A, OLD_D, OLD_R):
        _enum(p)
    for p in (OLD_W, OLD_A, OLD_D):
        WORLD.referencers[p] = []
    WORLD.referencers[OLD_R] = [BPB]
    _add(BPA, "Blueprint")
    _add(BPB, "Blueprint")
    WORLD.dependencies[BPA] = [NEW_W, NEW_A, "/Script/Engine"]
    WORLD.dependencies[BPB] = [NEW_D, OLD_R, "/Script/Engine"]


def _wrong_target():
    """The RETIRED ``redirector-wrong-target`` shape, kept as an OFFLINE-ONLY
    world: a REAL redirector at the old WeaponType path forwarding to the
    decoy (task root - C11 must stay green); the other three renamed clean;
    BP_RefA still imports the old WeaponType package.

    Deliberately NOT registered in ``LEGS``: it can never be a folder leg
    (the residue is not manufacturable headless - notes.md section 5
    RESOLVED-NEGATIVE (c)), so the MATRIX carries no row for it. This world
    plus ``_lane_b`` are the ONLY coverage of the tri-state's redirector
    branch; see TestTriStateContract."""
    for p in (NEW_W, NEW_A, NEW_D, NEW_R, OLD_A, OLD_D, OLD_R):
        _enum(p)
    _enum(DECOY)
    _redirector(OLD_W, DECOY)
    for p in (OLD_A, OLD_D, OLD_R):
        WORLD.referencers[p] = []
    _add(BPA, "Blueprint")
    _add(BPB, "Blueprint")
    WORLD.dependencies[BPA] = [OLD_W, NEW_A, "/Script/Engine"]
    WORLD.dependencies[BPB] = [NEW_D, NEW_R, "/Script/Engine"]


def _lane_b():
    """The Lane B PASS shape (offline-only, same reason as ``_wrong_target``):
    a redirector at the old WeaponType path forwarding EXACTLY to the new
    package, with BP_RefA still importing the old package (unresaved
    referencer). Must grade 11/11 through the one-hop substitution."""
    _reference_world()
    del WORLD.assets[_obj(OLD_W)]
    _redirector(OLD_W, NEW_W)
    WORLD.dependencies[BPA] = [OLD_W, NEW_A, "/Script/Engine"]


#: label -> the EXACT failing-check set (both directions: everything else
#: must PASS). The empty leg fails all 11.
EXPECTED_FAILURES = {
    "reference": set(),
    "empty": set(ALL_CHECKS),
    "duplicate-not-rename": {
        "old_path_retired_weapon_type", "old_path_retired_ammo_kind",
        "old_path_retired_damage_type", "old_path_retired_item_rarity",
        "refs_resolved_bp_ref_a", "refs_resolved_bp_ref_b"},
    "one-left-behind": {
        "new_asset_item_rarity", "old_path_retired_item_rarity",
        "refs_resolved_bp_ref_b", "folder_inventory"},
}

#: The retired variant's exact vector, kept because the OFFLINE oracle is now
#: the only thing that pins it.
WRONG_TARGET_FAILURES = {"old_path_retired_weapon_type",
                         "refs_resolved_bp_ref_a"}


# --------------------------------------------------------------------------- #
# tests                                                                        #
# --------------------------------------------------------------------------- #

class TestMatrixIsCreditable(unittest.TestCase):
    """Every MATRIX row must be parseable AND its substring actually printed."""

    def setUp(self):
        self.rows = parse_matrix(MATRIX_PATH.read_text(encoding="utf-8"))

    def test_every_declared_leg_has_a_row(self):
        self.assertEqual(set(self.rows), set(LEGS))

    def test_variant_folders_are_a_prefix_of_the_declared_set(self):
        """The folder tree becomes the variant-count authority once the binary
        half lands (playbook trap). The authoring boot ships legs one at a
        time, so a partially-authored subset is legal WHILE the binary half is
        in flight - but a folder the MATRIX does not declare never is: that
        would run a leg nothing predicts. (The reference/ folder is not a
        variant and is checked separately.)"""
        disc = TASK_DIR / "discrimination"
        on_disk = {p.name for p in disc.iterdir() if p.is_dir()}
        self.assertLessEqual(on_disk, set(VARIANTS),
                             "undeclared discrimination folder(s)")

    def test_the_retired_redirector_variant_has_no_folder(self):
        """RETIRED UNAUTHORED 2026-07-30. The redirector residue is not
        manufacturable headless, so this folder can never legitimately
        appear; if it ever does, the MATRIX row must come back with it."""
        self.assertFalse((TASK_DIR / "discrimination"
                          / "redirector-wrong-target").exists())
        self.assertNotIn("redirector-wrong-target", self.rows)

    def test_no_negative_leg_has_a_blank_substring_tuple(self):
        blank = sorted(k for k, v in self.rows.items()
                       if not v.expect_pass and not v.substrings)
        self.assertEqual(blank, [], "these legs can never be credited")

    def test_no_substring_carries_backticks(self):
        for label, row in self.rows.items():
            for s in row.substrings:
                self.assertNotIn("`", s, "%s: backticks never match log text" % label)

    def test_reference_leg_passes_all_eleven(self):
        out, parsed = run_leg(LEGS["reference"])
        self.assertTrue(parsed.found)
        self.assertEqual(parsed.total, EXPECTED_TOTAL)
        failed = [(c.id, c.detail) for c in parsed.checks if not c.passed]
        self.assertEqual(failed, [], out)

    def test_every_negative_leg_fails_with_its_named_substring(self):
        for label, builder in LEGS.items():
            row = self.rows[label]
            if row.expect_pass:
                continue
            with self.subTest(leg=label):
                out, parsed = run_leg(builder)
                self.assertTrue(parsed.found)
                self.assertEqual(parsed.total, EXPECTED_TOTAL)
                self.assertLess(parsed.passed_count, EXPECTED_TOTAL,
                                "expected a FAIL")
                details = "\n".join(c.detail for c in parsed.checks
                                    if not c.passed)
                for sub in row.substrings:
                    self.assertIn(sub, details,
                                  "%s: MATRIX substring never printed" % label)

    def test_named_substring_lands_on_the_predicted_check(self):
        predicted = {
            "empty": "new_asset_weapon_type",
            "duplicate-not-rename": "refs_resolved_bp_ref_a",
            "one-left-behind": "new_asset_item_rarity",
        }
        self.assertEqual(set(predicted) | {"reference"}, set(self.rows))
        for label, check_id in predicted.items():
            with self.subTest(leg=label):
                _, parsed = run_leg(LEGS[label])
                got = _by_id(parsed)[check_id]
                self.assertFalse(got.passed)
                for sub in self.rows[label].substrings:
                    self.assertIn(sub, got.detail)

    def test_each_leg_fails_exactly_the_predicted_check_set(self):
        """Both directions: the named checks FAIL and every other check
        PASSES. A leg that fails extra checks cannot prove which gate
        caught it."""
        for label, expect in EXPECTED_FAILURES.items():
            with self.subTest(leg=label):
                _, parsed = run_leg(LEGS[label])
                self.assertEqual(_fails(parsed), expect)

    def test_empty_leg_scores_zero_of_eleven(self):
        """The committed baseline is DESIGNED to fail everything: 0/11."""
        _, parsed = run_leg(LEGS["empty"])
        self.assertEqual({c.id for c in parsed.checks if c.passed}, set())
        by_id = _by_id(parsed)
        self.assertIn("ENUM_NEW_MISSING_E_WeaponType path=%s" % NEW_W,
                      by_id["new_asset_weapon_type"].detail)
        self.assertIn("ENUM_OLD_STILL_REFERENCED_WeaponType",
                      by_id["old_path_retired_weapon_type"].detail)
        self.assertIn("BP_DEP_OLD_NAME_LIVE_BP_RefA old=",
                      by_id["refs_resolved_bp_ref_a"].detail)
        self.assertIn("ENUM_FOLDER_INCOMPLETE missing=",
                      by_id["folder_inventory"].detail)

    def test_duplicate_leg_passes_names_but_fails_the_closure(self):
        """The tri-state's reason to exist: copies satisfy every names-only
        check (C1-C4 + the exact inventory) and fail all six closure
        checks."""
        _, parsed = run_leg(LEGS["duplicate-not-rename"])
        by_id = _by_id(parsed)
        for cid in ALL_CHECKS[:4] + ("folder_inventory",):
            self.assertTrue(by_id[cid].passed, cid)
        # sorted() puts the E_ammo_kind old pkg first in the echo - the
        # MATRIX cell depends on that ordering.
        self.assertIn("BP_DEP_OLD_NAME_LIVE_BP_RefA old=%s" % OLD_A,
                      by_id["refs_resolved_bp_ref_a"].detail)

    def test_matrix_records_the_redirector_coverage_gap(self):
        """The retired leg must leave a PROSE record below the table (never a
        second table - the parser reads only the one), naming why the residue
        cannot be authored and where the branch is covered instead."""
        text = MATRIX_PATH.read_text(encoding="utf-8")
        self.assertIn("Coverage note", text)
        for claim in ("manufacturable headless",
                      "RENLANE-REDIRECTOR-NOT-CREATED",
                      "level_refs_enum=False",
                      "unreflected C++ member",
                      "4 legs"):
            self.assertIn(claim, text, "MATRIX lost: %r" % claim)
        # exactly one table carrying variant rows survives the edit
        self.assertEqual(text.count("| Submission | Overall |"), 1)


class TestTriStateContract(unittest.TestCase):
    """The closure's redirector arm, both directions.

    THIS CLASS IS THE ONLY COVERAGE OF BRANCH (a) of the C5-C8 tri-state.
    The ``redirector-wrong-target/`` folder leg was retired UNAUTHORED on
    2026-07-30 because the redirector residue is not manufacturable headless
    (notes.md section 5 RESOLVED-NEGATIVE (c): the stock rename lane always
    deletes the old package, the chmod read-only trick does not reach
    DetectReadOnlyPackages, an unloaded map referencing a placed Blueprint
    instance references the BLUEPRINT not the enum, and Python cannot build
    a UObjectRedirector - DestinationObject is unreflected). The grader keeps
    the branch because a real agent CAN still produce the state; these tests
    are what stop it rotting.
    """

    def test_lane_b_correct_redirector_passes(self):
        """Lane B: a redirector forwarding EXACTLY to the new package + an
        unresaved referencer grades 11/11 through the one-hop substitution
        (the allow_redirectors lane's happy path). Pins the CHECK's own
        passing token too, not just the aggregate."""
        out, parsed = run_leg(_lane_b)
        self.assertEqual(_fails(parsed), set(), out)
        self.assertEqual(parsed.passed_count, EXPECTED_TOTAL)
        got = _by_id(parsed)["old_path_retired_weapon_type"]
        self.assertTrue(got.passed)
        self.assertIn("ENUM_OLD_REDIRECTS_OK old=%s target=%s" % (OLD_W, NEW_W),
                      got.detail)

    def test_lane_b_substitutes_the_old_dep_through_the_verified_redirector(self):
        """The other half of Lane B: C9 must RESOLVE BP_RefA even though its
        dependency is still the OLD package, because C5 verified the hop."""
        _, parsed = run_leg(_lane_b)
        got = _by_id(parsed)["refs_resolved_bp_ref_a"]
        self.assertTrue(got.passed)
        self.assertNotIn("BP_DEP_OLD_NAME_LIVE", got.detail)

    def test_wrong_target_redirector_fails_by_name(self):
        """The retired variant's whole point, now offline-only: a redirector
        forwarding to the DECOY fails C5 with its named token (pinning the
        decoy package it forwards to) and fails NOTHING else beyond the
        blocked C9 substitution."""
        _, parsed = run_leg(_wrong_target)
        self.assertEqual(parsed.total, EXPECTED_TOTAL)
        self.assertEqual(_fails(parsed), WRONG_TARGET_FAILURES)
        got = _by_id(parsed)["old_path_retired_weapon_type"]
        self.assertFalse(got.passed)
        self.assertIn(
            "ENUM_OLD_REDIRECT_WRONG_TARGET_WeaponType got=%s expected=%s"
            % (DECOY, NEW_W), got.detail)

    def test_bare_object_path_tag_form_also_parses(self):
        """The 5.8 tag text shape is an authoring-boot open question: the
        tolerant parse must accept a bare object path too."""
        def build():
            _reference_world()
            del WORLD.assets[_obj(OLD_W)]
            _redirector(OLD_W, None, tag=_obj(NEW_W))
        _, parsed = run_leg(build)
        self.assertEqual(_fails(parsed), set())

    def test_chained_redirector_fails_the_exact_target_rule(self):
        """old -> intermediate -> new: the ONE-HOP tag equals the
        intermediate, not the expected package - wrong-target by name."""
        def build():
            _reference_world()
            del WORLD.assets[_obj(OLD_W)]
            hop = "%s/IntermediateHop" % PKG
            _redirector(OLD_W, hop)
        _, parsed = run_leg(build)
        self.assertEqual(_fails(parsed), {"old_path_retired_weapon_type"})
        got = _by_id(parsed)["old_path_retired_weapon_type"]
        self.assertIn("ENUM_OLD_REDIRECT_WRONG_TARGET_WeaponType", got.detail)

    def test_unverified_redirector_is_never_substituted_in_c9(self):
        """A wrong-target redirector must not resolve a BP dependency: the
        old name counts as LIVE (the closure's one-hop rule)."""
        _, parsed = run_leg(_wrong_target)
        got = _by_id(parsed)["refs_resolved_bp_ref_a"]
        self.assertIn("BP_DEP_OLD_NAME_LIVE_BP_RefA old=%s" % OLD_W,
                      got.detail)

    def test_repointed_bp_fails_unresolved(self):
        """Anti-gaming #4: BPs re-typed onto assets outside the task folder
        leave no old dep to catch - the expected-new coverage check fails."""
        def build():
            _reference_world()
            WORLD.dependencies[BPA] = ["/Game/SomewhereElse/E_Foreign",
                                       "/Script/Engine"]
        _, parsed = run_leg(build)
        self.assertEqual(_fails(parsed), {"refs_resolved_bp_ref_a"})
        got = _by_id(parsed)["refs_resolved_bp_ref_a"]
        self.assertIn("BP_DEP_UNRESOLVED_BP_RefA missing=", got.detail)

    def test_missing_bp_fails_by_name(self):
        def build():
            _reference_world()
            del WORLD.assets[_obj(BPB)]
        _, parsed = run_leg(build)
        self.assertEqual(_fails(parsed), {"refs_resolved_bp_ref_b"})
        self.assertIn("BP_REF_MISSING_BP_RefB path=%s" % BPB,
                      _by_id(parsed)["refs_resolved_bp_ref_b"].detail)

    def test_wrong_class_impostor_at_new_path_fails(self):
        """Anti-gaming: a Blueprint named E_WeaponType is not an enum."""
        def build():
            _reference_world()
            WORLD.assets[_obj(NEW_W)] = FakeAssetData(NEW_W, "Blueprint")
        _, parsed = run_leg(build)
        self.assertEqual(_fails(parsed), {"new_asset_weapon_type"})
        got = _by_id(parsed)["new_asset_weapon_type"]
        self.assertIn("ENUM_NEW_WRONG_CLASS_E_WeaponType", got.detail)
        self.assertIn("Blueprint", got.detail)

    def test_folder_junk_fails_the_exact_inventory(self):
        """Anti-gaming #3: E_WeaponType_1 in the audited folder."""
        def build():
            _reference_world()
            _enum("%s/E_WeaponType_1" % ED)
        _, parsed = run_leg(build)
        self.assertEqual(_fails(parsed), {"folder_inventory"})
        got = _by_id(parsed)["folder_inventory"]
        self.assertIn("ENUM_FOLDER_UNEXPECTED_ASSET extra=[", got.detail)

    def test_folder_inventory_collapses_same_package_duplicates(self):
        """The SKEL_<Name>_C lesson: two AssetData entries in ONE package
        must count once - the reference stays 11/11."""
        def build():
            _reference_world()
            WORLD.assets[_obj(NEW_W, "SKEL_E_WeaponType_C")] = \
                FakeAssetData(NEW_W, "BlueprintGeneratedClass")
        _, parsed = run_leg(build)
        self.assertNotIn("folder_inventory", _fails(parsed))

    def test_unexpected_class_at_old_path_fails_by_name(self):
        def build():
            _reference_world()
            WORLD.assets[_obj(OLD_W)] = FakeAssetData(OLD_W, "Texture2D")
        _, parsed = run_leg(build)
        self.assertEqual(_fails(parsed), {"old_path_retired_weapon_type"})
        self.assertIn("ENUM_OLD_UNEXPECTED_CLASS_WeaponType",
                      _by_id(parsed)["old_path_retired_weapon_type"].detail)


class TestFailsClosed(unittest.TestCase):
    """Probe breakage grades UNCREDITED_TOKENS entries - never a pass, never
    a skip, never a MATRIX-creditable token."""

    def test_forged_redirector_with_missing_tag_is_uncredited(self):
        def build():
            _reference_world()
            del WORLD.assets[_obj(OLD_W)]
            _redirector(OLD_W, None, tag=None)
        out, parsed = run_leg(build)
        got = _by_id(parsed)["old_path_retired_weapon_type"]
        self.assertFalse(got.passed)
        self.assertIn("ENUM_OLD_TAG_UNREADABLE", got.detail)
        self.assertNotIn("ENUM_OLD_REDIRECT_WRONG_TARGET", out,
                         "a broken tag must never wear the graded token")

    def test_forged_redirector_with_garbage_tag_is_uncredited(self):
        def build():
            _reference_world()
            del WORLD.assets[_obj(OLD_W)]
            _redirector(OLD_W, None, tag="not an export path at all")
        _, parsed = run_leg(build)
        got = _by_id(parsed)["old_path_retired_weapon_type"]
        self.assertFalse(got.passed)
        self.assertIn("ENUM_OLD_TAG_UNPARSEABLE", got.detail)

    def test_missing_old_assetdata_is_uncredited(self):
        """No agent action can empty an old path under the copy-only
        overlay - conservative token, never the graded ones."""
        def build():
            _reference_world()
            del WORLD.assets[_obj(OLD_W)]
        out, parsed = run_leg(build)
        got = _by_id(parsed)["old_path_retired_weapon_type"]
        self.assertFalse(got.passed)
        self.assertIn("ENUM_OLD_ASSETDATA_UNAVAILABLE old=%s" % OLD_W,
                      got.detail)
        self.assertNotIn("ENUM_OLD_STILL_REFERENCED", out)

    def test_unreadable_referencers_is_a_read_error_not_an_orphan(self):
        def build():
            _reference_world()
            WORLD.referencers[OLD_W] = None
        out, parsed = run_leg(build)
        got = _by_id(parsed)["old_path_retired_weapon_type"]
        self.assertFalse(got.passed)
        self.assertIn("ENUM_OLD_REFERENCERS_READ_ERROR", got.detail)
        self.assertNotIn("ENUM_OLD_ORPHAN_OK old=%s" % OLD_W, out)

    def test_unreadable_dependencies_is_a_read_error(self):
        def build():
            _reference_world()
            WORLD.dependencies[BPA] = None
        _, parsed = run_leg(build)
        got = _by_id(parsed)["refs_resolved_bp_ref_a"]
        self.assertFalse(got.passed)
        self.assertIn("BP_DEP_READ_ERROR bp=BP_RefA", got.detail)

    def test_broken_registry_fails_all_eleven_uncredited(self):
        def build():
            _reference_world()
            WORLD.registry_broken = True
        _, parsed = run_leg(build)
        self.assertEqual(parsed.total, EXPECTED_TOTAL)
        self.assertEqual(parsed.passed_count, 0)
        for c in parsed.checks:
            self.assertIn("RENAME_REGISTRY_UNAVAILABLE", c.detail)

    def test_adversarial_tag_text_cannot_inject_a_marker(self):
        def build():
            _reference_world()
            del WORLD.assets[_obj(OLD_W)]
            _redirector(OLD_W, None,
                        tag="X'/Game/%s.%s'" % ("TestResult" + "=Passed",
                                                "Automation Test" + " Succeeded"))
        out, _parsed = run_leg(build)
        self.assertNotIn("TestResult" + "=Passed", out)
        self.assertNotIn("Automation Test" + " Succeeded", out)

    def test_adversarial_extra_package_name_is_sanitized(self):
        def build():
            _reference_world()
            bad = "%s/Evil TestResult" % ED
            WORLD.assets[bad + ".Evil"] = FakeAssetData(bad, "UserDefinedEnum")
        out, parsed = run_leg(build)
        self.assertIn("ENUM_FOLDER_UNEXPECTED_ASSET",
                      _by_id(parsed)["folder_inventory"].detail)
        self.assertNotIn("Evil TestResult", out, "space must be neutralized")

    def test_offline_run_without_unreal_fails_every_check(self):
        """No editor => 0/11, all error-shaped tokens. Never a vacuous PASS."""
        MOD.unreal = None
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            MOD.main()
        parsed = parse_introspect_verdict(buf.getvalue())
        self.assertEqual(parsed.total, EXPECTED_TOTAL)
        self.assertEqual(parsed.passed_count, 0)
        payload = json.loads(buf.getvalue().splitlines()[1])
        self.assertEqual([c["id"] for c in payload["checks"]],
                         list(MOD.CHECK_IDS))
        for c in payload["checks"]:
            self.assertIn("RENAME_INTROSPECTION_ABORTED", c["detail"])


class TestErrorTokensAreDisjointFromMatrix(unittest.TestCase):
    """A probe break must never be creditable as a variant's named failure."""

    def test_no_uncredited_token_appears_in_any_matrix_substring(self):
        rows = parse_matrix(MATRIX_PATH.read_text(encoding="utf-8"))
        subs = [s for r in rows.values() for s in r.substrings]
        self.assertTrue(MOD.UNCREDITED_TOKENS,
                        "expected the script to declare its error tokens")
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        for token in MOD.UNCREDITED_TOKENS:
            self.assertIn(token, source, "declared token never printed")
            for sub in subs:
                self.assertNotIn(token, sub)
        # graded-but-uncredited-by-this-matrix tokens stay out of cells too
        # ENUM_OLD_REDIRECT* joined this list 2026-07-30: the grader still
        # prints both, but no folder leg can reach them any more, so no MATRIX
        # cell may claim them (TestTriStateContract is their only coverage).
        for token in ("ENUM_OLD_UNEXPECTED_CLASS", "ENUM_NEW_WRONG_CLASS",
                      "BP_REF_WRONG_CLASS", "ENUM_FOLDER_INCOMPLETE",
                      "BP_DEP_UNRESOLVED", "ENUM_OLD_REDIRECT_WRONG_TARGET",
                      "ENUM_OLD_REDIRECTS_OK"):
            for sub in subs:
                self.assertNotIn(token, sub)

    def test_script_is_pure_ascii(self):
        raw = SCRIPT_PATH.read_bytes()
        self.assertEqual(raw.decode("utf-8"), raw.decode("ascii"))

    def test_script_carries_no_automation_result_marker(self):
        """parse_automation_log's whole-file finditer counts these as TESTS."""
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertNotIn("TestResult" + "=Passed", source)
        self.assertNotIn("Automation Test" + " Succeeded", source)

    def test_grader_never_loads_an_asset(self):
        """The binding allow_redirectors contract rule, enforced at the
        strongest possible level: no load_asset/load_object call exists in
        the grader at all - every fact is a registry read. (The docstring
        NAMES the forbidden calls, so this greps for CALL syntax.)"""
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertNotIn("load_asset(", source)
        self.assertNotIn("load_object(", source)
        self.assertNotIn("EditorAssetLibrary", source)

    def test_check_ids_are_the_declared_eleven(self):
        self.assertEqual(tuple(MOD.CHECK_IDS), ALL_CHECKS)

    def test_grader_carries_no_forced_rescan(self):
        """notes.md decision #16, pinned so nobody adds one without reading it.

        Dependency/referencer edges are SCAN-time, not save-time (live-proven
        2026-07-30) - but that only bites IN-PROCESS authoring-time grading.
        A real grade overlays the submission BEFORE the editor boots, so the
        startup scan has already built every edge this grader reads: a
        ``scan_paths_synchronous(force_rescan=True)`` here would buy nothing
        while putting a state-changing call and a new probe-failure surface
        on the one code path that must never manufacture a false negative.
        The rescan is the CALLER's job - see
        TestAuthoringScriptRoutes below, which pins the other direction.
        """
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertNotIn("scan_paths_synchronous", source)
        self.assertNotIn("force_rescan", source)

    def test_grader_uses_default_dependency_options(self):
        """Also confirmed 2026-07-30: the default AssetRegistryDependency-
        Options() already carries bIncludeSoft/HardPackageReferences=True, so
        the default construction is CORRECT - the options object was never
        why a freshly authored Blueprint read zero edges. No flag fiddling."""
        tree = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"))
        calls = [n for n in ast.walk(tree)
                 if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Attribute)
                 and n.func.attr == "AssetRegistryDependencyOptions"]
        self.assertTrue(calls, "expected the grader to build the options")
        for call in calls:
            self.assertEqual(call.args, [])
            self.assertEqual(call.keywords, [])


def _authoring_tree():
    return ast.parse(AUTHORING_PATH.read_text(encoding="utf-8"))


def _func(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError("authoring script has no function %r" % name)


def _module_const(tree, name):
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError("authoring script has no constant %r" % name)


def _assigned(tree, name):
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == name:
                    return node.value
    raise AssertionError("authoring script has no assignment %r" % name)


def _leg_spec_names(tree):
    """The leg LABELS of the ``LEG_SPECS`` dict - literal_eval can't read the
    dict because every value carries a function reference."""
    value = _assigned(tree, "LEG_SPECS")
    assert isinstance(value, ast.Dict), "LEG_SPECS"
    return [ast.literal_eval(k) for k in value.keys]


def _leg_spec(tree, source, leg):
    """The source text of one LEG_SPECS entry."""
    value = _assigned(tree, "LEG_SPECS")
    for key, val in zip(value.keys, value.values):
        if ast.literal_eval(key) == leg:
            return ast.get_source_segment(source, val) or ""
    raise AssertionError("no LEG_SPECS entry for %r" % leg)


class TestAuthoringScriptRoutes(unittest.TestCase):
    """The authoring script must stay on the two routes live-proven on UE 5.8
    on 2026-07-30 (notes.md section 5), and must keep grading every leg with
    the REAL grader against exact expected vectors.

    This is a static oracle: the script imports ``unreal`` at module scope so
    it can only be read, never imported, offline.
    """

    @classmethod
    def setUpClass(cls):
        cls.tree = _authoring_tree()
        cls.source = AUTHORING_PATH.read_text(encoding="utf-8")

    # -- fact 2: edges are scan-time -------------------------------------- #

    def test_grade_rescans_before_every_authoring_phase_grade(self):
        """``grade()``'s FIRST statement is the rescan, and it DEFAULTS on, so
        no authoring-phase caller can forget it (un-forgettable by
        construction, not by discipline).

        The one opt-out is the VERIFY phase, which must read the registry
        exactly as the graded lane's editor does - first scan only. That is
        asserted separately (``test_verify_phase_grades_without_a_rescan``);
        here we only pin that the default is ON.
        """
        fn = _func(self.tree, "grade")
        self.assertEqual([a.arg for a in fn.args.args], ["rescan_first"])
        self.assertEqual([getattr(d, "value", None) for d in fn.args.defaults],
                         [True], "the rescan must DEFAULT on")
        body = [n for n in fn.body
                if not (isinstance(n, ast.Expr)
                        and isinstance(n.value, ast.Constant)
                        and isinstance(n.value.value, str))]
        first = body[0]
        self.assertIsInstance(first, ast.If)
        self.assertEqual(getattr(first.test, "id", None), "rescan_first")
        self.assertEqual(
            [getattr(n.value.func, "id", None) for n in first.body], ["rescan"])

    def test_rescan_forces_a_synchronous_task_folder_rescan(self):
        fn = _func(self.tree, "rescan")
        seg = ast.get_source_segment(self.source, fn) or ""
        self.assertIn("scan_paths_synchronous", seg)
        forced = [kw for call in ast.walk(fn)
                  if isinstance(call, ast.Call)
                  for kw in call.keywords
                  if kw.arg == "force_rescan"
                  and getattr(kw.value, "value", None) is True]
        self.assertTrue(forced, "the rescan must pass force_rescan=True")

    def test_an_unavailable_rescan_is_a_named_abort(self):
        """No rescan => every in-process grade reads a phantom 0-edge world.
        That must die named, never ship doubtful bytes."""
        seg = ast.get_source_segment(self.source, _func(self.tree, "rescan"))
        self.assertIn("RENLANE-RESCAN-UNAVAILABLE", seg)
        self.assertIn("RENLANE-RESCAN-FAILED", seg)

    # -- fact 1: the pin is built by TEXT IMPORT --------------------------- #

    def test_pin_type_is_built_by_text_import(self):
        seg = ast.get_source_segment(self.source, _func(self.tree, "_pin_type"))
        self.assertIn("import_text", seg)
        self.assertIn("export_text", seg,
                      "the imported pin must be read back for proof")

    def test_pin_text_uses_the_doubled_leaf_object_path(self):
        """UE wants <package path>.<asset name> - the doubled leaf, quoted."""
        seg = ast.get_source_segment(self.source, _func(self.tree, "_pin_text"))
        self.assertIn('PinCategory="%s"', seg)
        self.assertIn('PinSubCategoryObject="%s.%s"', seg)

    def test_no_set_editor_property_on_a_pin_field(self):
        """The route that aborted the first boot: EdGraphPinType's properties
        are PROTECTED, so set_editor_property("pin_category", ...) raises."""
        for node in ast.walk(self.tree):
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "set_editor_property"):
                continue
            first = node.args[0] if node.args else None
            name = getattr(first, "value", None)
            if isinstance(name, str):
                self.assertNotIn("in_category", name.lower(),
                                 "pin fields are protected - use import_text")

    def test_the_mcp_fallback_claim_is_gone(self):
        """Resolved 2026-07-30: the BP-variable route is stock Python. No
        note may still send this row to the Aura MCP bp_agent lane."""
        self.assertNotIn("bp_agent", self.source)
        self.assertNotIn("edit_blueprint", self.source)

    # -- the safety properties that must survive the patch ----------------- #

    def test_refuse_if_exists_guard_survives(self):
        """The baseline phase is the only one that MINTS assets, so it is the
        one that must refuse a non-empty substrate."""
        seg = ast.get_source_segment(self.source,
                                     _func(self.tree, "phase_baseline"))
        self.assertIn("refusing to overwrite", seg)

    def test_every_route_failure_still_aborts_named(self):
        for token in ("RENLANE-TYPE-UNAVAILABLE",
                      "RENLANE-BPVAR-ROUTE-UNAVAILABLE",
                      "RENLANE-BPVAR-UNDO-FAILED",
                      "RENLANE-BPVAR-TYPE-NOT-HARVESTABLE",
                      "RENLANE-ENUMFACTORY-UNAVAILABLE",
                      "RENLANE-RENAME-FAILED",
                      "RENLANE-REDIRECTOR-NOT-CREATED",
                      "RENLANE-RESCAN-UNAVAILABLE"):
            self.assertIn(token, self.source)

    def test_every_leg_is_graded_against_an_exact_vector(self):
        """House law: every leg declares an EXACT failing set, and the
        deliverable is graded by the REAL grader against it."""
        seg = ast.get_source_segment(self.source, _func(self.tree, "expect"))
        self.assertIn("fail_exactly", seg)
        self.assertIn("!=", seg, "the exact-set compare must stay")
        for leg in ("empty", "duplicate-not-rename", "one-left-behind",
                    "reference", "redirector-wrong-target"):
            spec = _leg_spec(self.tree, self.source, leg)
            self.assertIn("fail_exactly", spec, "%s declares no vector" % leg)
            self.assertIn("substrings", spec, "%s declares no substrings" % leg)
        verify = ast.get_source_segment(self.source,
                                        _func(self.tree, "phase_verify"))
        self.assertIn("expect(", verify)
        self.assertIn('fail_exactly=spec["fail_exactly"]', verify)
        self.assertIn('substrings=spec["substrings"]', verify)

    # -- the tombstone law: no leg is graded in the boot that mutated it --- #

    def test_no_author_phase_takes_a_vector(self):
        """THE 2026-07-30 law (notes.md section 5, fact (d)): after an
        in-session delete the registry false-PASSES the orphan branch off
        stale AssetData. So an author function may not grade, and the author
        phase may not assert a leg vector - only the baseline preflight,
        which runs before anything has been deleted."""
        for leg in ("author_duplicate_not_rename", "author_one_left_behind",
                    "author_reference", "author_redirector_wrong_target"):
            seg = ast.get_source_segment(self.source, _func(self.tree, leg))
            self.assertNotIn("expect(", seg, "%s grades its own mutation" % leg)
            self.assertNotIn("grade(", seg, "%s grades its own mutation" % leg)
        author = ast.get_source_segment(self.source,
                                        _func(self.tree, "phase_author"))
        self.assertNotIn("expect(", author)
        # the ONLY grade in the author phase is the pre-mutation baseline pin
        self.assertIn("grade_baseline(\"preflight-", author)
        self.assertNotIn("simulate_overlay", self.source,
                         "in-session overlay simulation is REFUTED - it "
                         "cannot reproduce the graded state (tombstone law)")

    def test_verify_phase_grades_without_a_rescan(self):
        """The verify boot's state is materialized on disk BEFORE it starts,
        so it must read the registry exactly as the graded lane's editor
        does: first scan only, no rescan, no mutation."""
        seg = ast.get_source_segment(self.source,
                                     _func(self.tree, "phase_verify"))
        self.assertIn("grade(rescan_first=False)", seg)

    def test_nothing_ships_before_its_cold_vector_is_asserted(self):
        """Staging is the refuse-to-ship boundary: an author boot HARVESTS to
        .staged/, and only the verify phase - after ``expect`` - promotes into
        reference/ or discrimination/."""
        author = ast.get_source_segment(self.source,
                                        _func(self.tree, "phase_author"))
        self.assertIn("stage(", author)
        self.assertNotIn("promote(", author, "the author boot ships directly")
        verify = ast.get_source_segment(self.source,
                                        _func(self.tree, "phase_verify"))
        expect_at = verify.index("expect(")
        self.assertLess(expect_at, verify.index("promote("),
                        "promotion must follow the exact-vector assertion")
        stage_fn = ast.get_source_segment(self.source, _func(self.tree, "stage"))
        self.assertIn("STAGE", stage_fn)
        promote_fn = ast.get_source_segment(self.source,
                                            _func(self.tree, "promote"))
        self.assertIn("staged inventory", promote_fn)
        self.assertIn("die(", promote_fn,
                      "a staged/declared inventory mismatch must abort")

    def test_every_boot_ends_at_the_committed_baseline(self):
        """Each phase is a whole boot now, so the exit invariant has to hold
        per boot - proven by BYTES, because after a delete the registry
        cannot be asked (tombstone law)."""
        for phase in ("phase_baseline", "phase_author", "phase_verify"):
            seg = ast.get_source_segment(self.source, _func(self.tree, phase))
            self.assertIn("baseline()", seg, "%s has no exit invariant" % phase)
        restore = ast.get_source_segment(self.source,
                                         _func(self.tree, "restore_baseline"))
        self.assertIn("assert_substrate_is_baseline()", restore)
        self.assertIn("RENLANE-RESTORE-LOCKED", self.source)

    # -- the retired redirector legs (2026-07-30) -------------------------- #

    def test_redirector_legs_are_off_the_default_boot(self):
        """The residue is not manufacturable headless, so the redirector leg
        would abort a boot. It must not be in the runner's default leg list -
        otherwise no pass can ever run to completion."""
        runner = RUNNER_PATH.read_text(encoding="utf-8")
        default = re.search(r"^LEGS=\((.*)\)$", runner, re.M)
        self.assertIsNotNone(default, "the runner's default LEGS array moved")
        names = re.findall(r'"([^"]+)"', default.group(1))
        self.assertEqual(names, ["duplicate-not-rename", "one-left-behind",
                                 "reference"])
        self.assertNotIn("redirector-wrong-target", names)

    def test_redirector_legs_are_retained_behind_an_opt_in_flag(self):
        """RETAINED, not deleted: a future engine/SCC configuration must be
        able to re-attempt the manufacture without re-deriving any of it. The
        leg keeps its author route and its full expected vector."""
        runner = RUNNER_PATH.read_text(encoding="utf-8")
        gate = re.search(
            r'if \[ "\$\{RENLANE_TRY_REDIRECTOR:-\}" = "1" \]; then\s*\n'
            r'\s*LEGS\+=\("redirector-wrong-target"\)', runner)
        self.assertIsNotNone(gate, "the opt-in gate for the retired leg moved")
        self.assertIn("redirector-wrong-target", _leg_spec_names(self.tree))
        spec = _leg_spec(self.tree, self.source, "redirector-wrong-target")
        self.assertIn("ENUM_OLD_REDIRECT_WRONG_TARGET_WeaponType", spec)

    def test_the_redirector_manufacture_capability_survives(self):
        """The _rename(expect_redirector=True) route and its named abort stay
        wired, and the finding is recorded where the next reader will look."""
        self.assertIn("expect_redirector=True", self.source)
        self.assertIn("RENLANE-REDIRECTOR-NOT-CREATED", self.source)
        self.assertIn("RENLANE_TRY_REDIRECTOR", self.source)

    def test_authoring_mapping_mirrors_the_grader(self):
        """The script's hard-coded old->new mapping and BP variable plan must
        be the one the grader (and this oracle) is written against."""
        enum_specs = _module_const(self.tree, "ENUM_SPECS")
        self.assertEqual(tuple(enum_specs), MOD.ENUM_SPECS)
        bp_specs = dict((name, tuple(k for _v, k in pairs))
                        for name, pairs in _module_const(self.tree, "BP_SPECS"))
        self.assertEqual(
            bp_specs,
            {bp_name: tuple(keys) for _cid, bp_name, keys in MOD.BP_SPECS})

    def test_the_grader_under_test_is_the_committed_one(self):
        """The in-process grade must load the REAL verifier-owned grader, not
        a copy the authoring script could drift from."""
        self.assertIn('"tools", "verify-single", "introspect"', self.source)
        self.assertIn('"consistent_enum_names.py"', self.source)


class TestSpecFrontMatter(unittest.TestCase):
    def test_front_matter_declares_the_lane_and_the_grader(self):
        parsed = spec_mod.parse_task_file(TASK_DIR / "task.md")
        self.assertEqual(parsed.task_id, TASK_ID)
        self.assertEqual(parsed.substrate, "ThirdPerson")
        self.assertEqual(tuple(parsed.layers), ("L1", "L2I"))
        self.assertEqual(list(parsed.introspect_scripts),
                         ["consistent_enum_names.py"])

    def test_allow_redirectors_names_exactly_the_four_old_packages(self):
        """The task-scoped exception form the flag enforces: the four OLD
        packages, nothing else - a redirector anywhere else (including the
        new paths) still dies REDIRECTOR_SUBMITTED in the preamble."""
        parsed = spec_mod.parse_task_file(TASK_DIR / "task.md")
        self.assertEqual(sorted(parsed.allow_redirectors),
                         sorted((OLD_W, OLD_A, OLD_D, OLD_R)))
        for entry in parsed.allow_redirectors:
            self.assertTrue(entry.startswith("/Game/Tasks/%s/" % TASK_ID))

    def test_grader_mapping_matches_the_spec_constants(self):
        """The hard-coded old->new mapping in the grader is the one this
        oracle (and the MATRIX) is written against."""
        self.assertEqual(MOD.OLD_PKGS,
                         {"weapon_type": OLD_W, "ammo_kind": OLD_A,
                          "damage_type": OLD_D, "item_rarity": OLD_R})
        self.assertEqual(MOD.NEW_PKGS,
                         {"weapon_type": NEW_W, "ammo_kind": NEW_A,
                          "damage_type": NEW_D, "item_rarity": NEW_R})


if __name__ == "__main__":
    unittest.main()

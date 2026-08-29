"""Offline oracle for the t1-hero-blueprint-copy-with-flashlight L2I grader.

No editor, no UE install, no tokens. A minimal fake ``unreal`` module models
the reflection surface the introspect script actually uses, so every leg of
``discrimination/MATRIX.md`` can be simulated and joined against the REAL
``discriminate.parse_matrix`` + the REAL ``layers/l2_introspect`` parser.

What this pins (each of these was a live defect, 2026-07-27):
  * every negative leg's MATRIX substring is a literal the script PRINTS;
  * the cone-light check fails CLOSED (it used to return True merely because a
    probe did not raise);
  * the attach-parent check is not name-only (a component the submission
    merely NAMED ``CharacterMesh0`` used to satisfy anti-gaming note #2);
  * an empty subobject walk cannot hand the NEGATIVE ``source_*`` checks a
    free PASS.

The fake is deliberately dumb: it models names, classes, subobject parentage
and the inherited/native flags, and nothing else. It cannot prove the UE API
names are right - only a live editor does that - but it does prove the
grader's LOGIC and its printed tokens.
"""
import importlib.util
import io
import json
import contextlib
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

TASK_DIR = _REPO / "tasks" / "bp" / "t1-hero-blueprint-copy-with-flashlight"
MATRIX_PATH = TASK_DIR / "discrimination" / "MATRIX.md"
SCRIPT_PATH = _VERIFY / "introspect" / "hero_blueprint_copy_with_flashlight.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("_hero_introspect", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------- #
# the fake unreal module                                                       #
# --------------------------------------------------------------------------- #

class _Class:
    def __init__(self, name):
        self._name = name

    def get_name(self):
        return self._name


class _UObject:
    def __init__(self, name, path=None, **props):
        self._name = name
        self._path = path or name
        self._props = dict(props)

    def get_name(self):
        return self._name

    def get_path_name(self):
        return self._path

    def get_class(self):
        return _Class(type(self).__name__)

    def get_editor_property(self, name):
        if name not in self._props:
            raise Exception("unknown property %r on %s" % (name, self._name))
        return self._props[name]


class Actor(_UObject):
    pass


class Pawn(Actor):
    pass


class Character(Pawn):
    pass


class SceneComponent(_UObject):
    def get_attach_parent(self):
        return self._props.get("_attach_parent")


class StaticMeshComponent(SceneComponent):
    pass


class SkeletalMeshComponent(SceneComponent):
    pass


class CapsuleComponent(SceneComponent):
    """ACharacter's collision root. Models the UFUNCTION getter, which is the
    route hero_locomotion_intact prefers over the reflected property."""

    def get_collision_enabled(self):
        return self._props["collision_enabled"]


class CharacterMovementComponent(_UObject):
    """Carries the two locomotion scalars hero_locomotion_intact reads.

    Modelled because _UObject.get_editor_property RAISES on an unknown name: with
    no movement component on the CDO the check would fail-closed on every leg for
    a mock reason, and would silently stop testing the properties at all.
    """


class LightComponent(SceneComponent):
    pass


class PointLightComponent(LightComponent):
    pass


class SpotLightComponent(PointLightComponent):
    pass


class SubobjectDataHandle:
    def __init__(self, data):
        self.data = data


class SubobjectData:
    def __init__(self, var_name, obj, parent=None, inherited=False, native=False):
        self.var_name = var_name
        self.obj = obj
        self.parent = parent
        self.inherited = inherited
        self.native = native

    @property
    def handle(self):
        return SubobjectDataHandle(self)


class SubobjectDataSubsystem:
    pass


class Blueprint(_UObject):
    def __init__(self, name, path, subobjects, status="BlueprintStatus.BS_UP_TO_DATE"):
        _UObject.__init__(self, name, path, status=status)
        self.subobjects = subobjects


class _AssetData:
    def __init__(self, tags):
        self._tags = tags

    def get_tag_value(self, name):
        return self._tags.get(name, "")


class _World:
    """One simulated project state: which assets exist and what they contain."""

    def __init__(self):
        self.assets = {}        # path -> Blueprint
        self.cdos = {}          # path -> CDO instance (or None = will not load)
        self.tags = {}          # path -> {tag: value}
        self.gather_empty = False


WORLD = _World()


class _EditorAssetLibrary:
    @staticmethod
    def does_asset_exist(path):
        return path in WORLD.assets

    @staticmethod
    def load_asset(path):
        return WORLD.assets[path]

    @staticmethod
    def load_blueprint_class(path):
        return _Class(path + "_C") if path in WORLD.cdos else None

    @staticmethod
    def find_asset_data(path):
        return _AssetData(WORLD.tags.get(path, {}))


class _SubobjectLib:
    @staticmethod
    def get_data(handle):
        return handle.data

    @staticmethod
    def is_handle_valid(handle):
        return handle is not None

    @staticmethod
    def get_variable_name(data):
        return data.var_name

    @staticmethod
    def get_parent_handle(data):
        return data.parent.handle if data.parent is not None else None

    @staticmethod
    def get_object(data):
        return data.obj

    @staticmethod
    def is_inherited_component(data):
        return data.inherited

    @staticmethod
    def is_native_component(data):
        return data.native


class _Subsystem:
    @staticmethod
    def gather_subobject_data_for_blueprint(blueprint):
        if WORLD.gather_empty:
            return []
        return [s.handle for s in blueprint.subobjects]


class FakeUnreal:
    EditorAssetLibrary = _EditorAssetLibrary
    SubobjectDataBlueprintFunctionLibrary = _SubobjectLib
    SubobjectDataHandle = SubobjectDataHandle
    SubobjectDataSubsystem = SubobjectDataSubsystem
    Character = Character
    SkeletalMeshComponent = SkeletalMeshComponent
    SpotLightComponent = SpotLightComponent
    PointLightComponent = PointLightComponent
    StaticMeshComponent = StaticMeshComponent

    @staticmethod
    def get_engine_subsystem(cls):
        return _Subsystem

    @staticmethod
    def get_default_object(cls):
        path = cls.get_name()[:-2]
        return WORLD.cdos.get(path)

    @staticmethod
    def log(msg):
        pass


# --------------------------------------------------------------------------- #
# leg builders                                                                 #
# --------------------------------------------------------------------------- #

# 11 until 2026-08-19, when two SPECIFIED-but-ungated requirements-table rows
# were closed (hero_locomotion_intact, source_retains_body_and_health). Every
# score recorded before that date is out of 11.
TOTAL_CHECKS = 13

MOD = _load_script()
HERO = MOD.ASSET_HERO
SOURCE = MOD.ASSET_SOURCE


def _source_assets(*, is_character=False, has_flashlight=False,
                   body=True, health=100.0):
    """Build BP_Source.

    ``body`` / ``health`` exist for source_retains_body_and_health (2026-08-19):
    "unchanged" used to be sampled at two properties only, so a submission could
    overlay a BP_Source with Health rewritten or Body deleted and still pass both
    source_* checks. The CDO now carries Health for the same reason the hero's
    does - without it the check fails closed for a mock reason.
    """
    root = SubobjectData("DefaultSceneRoot", SceneComponent("DefaultSceneRoot"),
                         native=True, inherited=True)
    subs = [root]
    if body:
        subs.append(SubobjectData("Body", StaticMeshComponent("Body"), parent=root))
    if has_flashlight:
        subs.append(SubobjectData(
            "Flashlight", SpotLightComponent("Flashlight", outer_cone_angle=44.0,
                                             intensity=12000.0),
            parent=root))
    WORLD.assets[SOURCE] = Blueprint("BP_Source", SOURCE, subs)
    WORLD.cdos[SOURCE] = (Character("BP_Source_C", **{"Health": health})
                          if is_character
                          else Actor("BP_Source_C", **{"Health": health}))
    WORLD.tags[SOURCE] = {
        "ParentClass": "Character" if is_character else "Actor",
        "NativeParentClass": "Character" if is_character else "Actor",
    }


def _hero_assets(*, character=True, body=True, health=100.0,
                 flashlight="spot", attach="mesh", intensity=12000.0,
                 status="BlueprintStatus.BS_UP_TO_DATE",
                 walk_speed=500.0, jump_velocity=700.0,
                 collision="ECollisionEnabled.QUERY_AND_PHYSICS"):
    """Build BP_Hero. ``attach`` selects the Flashlight's parent subobject:
    "mesh" (the real inherited CharacterMesh0), "root", "impostor-static"
    (an SCS StaticMeshComponent the agent named CharacterMesh0) or
    "impostor-skeletal" (an SCS SkeletalMeshComponent the agent named Mesh)."""
    mesh_obj = SkeletalMeshComponent("CharacterMesh0",
                                     path=HERO + "_C:CharacterMesh0")
    root = SubobjectData("CapsuleComponent", SceneComponent("CapsuleComponent"),
                         native=True, inherited=True)
    inherited_mesh = SubobjectData("CharacterMesh0", mesh_obj, parent=root,
                                   native=True, inherited=True)
    subs = [root, inherited_mesh] if character else [root]
    if body:
        subs.append(SubobjectData("Body", StaticMeshComponent("Body"), parent=root))

    parents = {"mesh": inherited_mesh, "root": root}
    if attach == "impostor-static":
        parents["impostor-static"] = SubobjectData(
            "CharacterMesh0",
            StaticMeshComponent("CharacterMesh0",
                                path=HERO + "_C:StaticMeshComponent_0"),
            parent=root)
        subs.append(parents["impostor-static"])
    elif attach == "impostor-skeletal":
        parents["impostor-skeletal"] = SubobjectData(
            "Mesh",
            SkeletalMeshComponent("Mesh", path=HERO + "_C:SkeletalMeshComponent_0"),
            parent=root)
        subs.append(parents["impostor-skeletal"])

    if flashlight is not None:
        if flashlight == "spot":
            light = SpotLightComponent("Flashlight", outer_cone_angle=44.0,
                                       intensity=intensity)
        elif flashlight == "point":
            light = PointLightComponent("Flashlight", intensity=intensity)
        else:  # a non-light that merely exposes the cone property (fail-open probe)
            light = StaticMeshComponent("Flashlight", outer_cone_angle=0.0,
                                        intensity=intensity)
        subs.append(SubobjectData("Flashlight", light, parent=parents[attach]))

    WORLD.assets[HERO] = Blueprint("BP_Hero", HERO, subs, status=status)
    cdo_cls = Character if character else Actor
    cdo = cdo_cls("BP_Hero_C", **{"Health": health})
    if character:
        cdo._props["mesh"] = mesh_obj
        # Locomotion defaults are the ENGINE's (500 / 700), which is what a real
        # Character subclass inherits; the gates are floors well below them.
        # A non-Character CDO deliberately gets NEITHER, so
        # hero_locomotion_intact fails there too - a Character-less hero has no
        # locomotion, and that cascade is asserted rather than assumed.
        cdo._props["character_movement"] = CharacterMovementComponent(
            "CharMoveComp", max_walk_speed=float(walk_speed),
            jump_z_velocity=float(jump_velocity))
        cdo._props["capsule_component"] = CapsuleComponent(
            "CapsuleComponent", collision_enabled=collision)
    WORLD.cdos[HERO] = cdo
    WORLD.tags[HERO] = {
        "ParentClass": "Character" if character else "Actor",
        "NativeParentClass": "Character" if character else "Actor",
    }


LEGS = {}


def _leg(name):
    def deco(fn):
        LEGS[name] = fn
        return fn
    return deco


@_leg("reference")
def _reference():
    _source_assets()
    _hero_assets()


@_leg("empty")
def _empty():
    _source_assets()  # the substrate ships BP_Source; BP_Hero is absent


@_leg("copy-without-character-base")
def _copy_without_character_base():
    _source_assets()
    _hero_assets(character=False, attach="root")


@_leg("flashlight-on-root")
def _flashlight_on_root():
    _source_assets()
    _hero_assets(attach="root")


@_leg("edited-source-in-place")
def _edited_source_in_place():
    _source_assets(is_character=True, has_flashlight=True)
    _hero_assets()


@_leg("hero-missing-body-and-health")
def _hero_missing_body_and_health():
    _source_assets()
    _hero_assets(body=False, health=0.0)


@_leg("default-brightness-point-light")
def _default_brightness_point_light():
    _source_assets()
    _hero_assets(flashlight="point", intensity=5000.0)


def run_leg(builder):
    """Run the introspect script against a freshly built world; return checks."""
    global WORLD
    WORLD = _World()
    MOD.unreal = FakeUnreal
    for target in (sys.modules.get("_hero_introspect"),):
        if target is not None:
            target.unreal = FakeUnreal
    builder()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        MOD.main()
    out = buf.getvalue()
    parsed = parse_introspect_verdict(out)
    return out, parsed


# --------------------------------------------------------------------------- #
# tests                                                                        #
# --------------------------------------------------------------------------- #

class TestMatrixIsCreditable(unittest.TestCase):
    """Every MATRIX row must be parseable AND its substring actually printed."""

    def setUp(self):
        self.rows = parse_matrix(MATRIX_PATH.read_text(encoding="utf-8"))

    def test_every_declared_leg_has_a_row(self):
        self.assertEqual(set(self.rows), set(LEGS))

    def test_no_negative_leg_has_a_blank_substring_tuple(self):
        blank = sorted(k for k, v in self.rows.items()
                       if not v.expect_pass and not v.substrings)
        self.assertEqual(blank, [], "these legs can never be credited")

    def test_no_substring_carries_backticks(self):
        for label, row in self.rows.items():
            for s in row.substrings:
                self.assertNotIn("`", s, "%s: backticks never match log text" % label)

    def test_reference_leg_passes_every_check(self):
        out, parsed = run_leg(LEGS["reference"])
        self.assertTrue(parsed.found)
        self.assertEqual(parsed.total, TOTAL_CHECKS)
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
                self.assertEqual(parsed.total, TOTAL_CHECKS)
                self.assertLess(parsed.passed_count, TOTAL_CHECKS, "expected a FAIL")
                details = "\n".join(c.detail for c in parsed.checks if not c.passed)
                for sub in row.substrings:
                    self.assertIn(sub, details,
                                  "%s: MATRIX substring never printed" % label)

    def test_named_substring_lands_on_the_predicted_check(self):
        """The substring must appear on the check the MATRIX blames, not just
        somewhere in the verdict."""
        expected = {
            "empty": "hero_asset_exists",
            "copy-without-character-base": "hero_parent_is_character",
            "flashlight-on-root": "hero_flashlight_attach_parent_is_mesh",
            "edited-source-in-place": "source_unchanged_not_character",
            "hero-missing-body-and-health": "hero_retains_body_component",
            "default-brightness-point-light": "hero_flashlight_is_cone_light",
        }
        for label, check_id in expected.items():
            with self.subTest(leg=label):
                _, parsed = run_leg(LEGS[label])
                got = {c.id: c for c in parsed.checks}[check_id]
                self.assertFalse(got.passed)
                for sub in self.rows[label].substrings:
                    self.assertIn(sub, got.detail)


class TestFailsClosed(unittest.TestCase):
    """Defect 3: no check may pass because a probe merely did not raise."""

    def test_cone_check_rejects_a_non_light_exposing_the_cone_property(self):
        # Pre-fix this returned True: get_editor_property('outer_cone_angle')
        # did not raise, so the component was declared a cone beam.
        _, parsed = run_leg(lambda: (_source_assets(),
                                     _hero_assets(flashlight="probe-only")))
        got = {c.id: c for c in parsed.checks}["hero_flashlight_is_cone_light"]
        self.assertFalse(got.passed)
        self.assertIn("HERO_FLASHLIGHT_NOT_CONE class=", got.detail)

    def test_attach_parent_rejects_a_component_merely_named_charactermesh0(self):
        # Pre-fix this PASSED - the check compared the parent's NAME only, so
        # anti-gaming note #2 was defeated by renaming a static mesh.
        _, parsed = run_leg(lambda: (_source_assets(),
                                     _hero_assets(attach="impostor-static")))
        got = {c.id: c
               for c in parsed.checks}["hero_flashlight_attach_parent_is_mesh"]
        self.assertFalse(got.passed)
        self.assertIn("HERO_FLASHLIGHT_ATTACH_PARENT_WRONG parent=", got.detail)
        self.assertIn("name_ok=True", got.detail)      # the name DID match ...
        self.assertIn("skeletal=False", got.detail)    # ... and it still fails

    def test_attach_parent_rejects_a_submission_authored_skeletal_mesh(self):
        # A SkeletalMeshComponent the agent added to BP_Hero's own SCS and
        # named "Mesh": right name, right type, still not the INHERITED one.
        _, parsed = run_leg(lambda: (_source_assets(),
                                     _hero_assets(attach="impostor-skeletal")))
        got = {c.id: c
               for c in parsed.checks}["hero_flashlight_attach_parent_is_mesh"]
        self.assertFalse(got.passed)
        self.assertIn("name_ok=True", got.detail)
        self.assertIn("skeletal=True", got.detail)
        self.assertIn("inherited=False", got.detail)

    def test_empty_subobject_walk_cannot_pass_the_negative_source_check(self):
        # Pre-fix a silently empty gather meant "no Flashlight on BP_Source",
        # i.e. a free PASS on an API break.
        def build():
            _source_assets()
            _hero_assets()
            WORLD.gather_empty = True
        _, parsed = run_leg(build)
        got = {c.id: c for c in parsed.checks}["source_has_no_flashlight"]
        self.assertFalse(got.passed)
        self.assertIn("SOURCE_WALK_ERROR", got.detail)

    def test_unloadable_source_class_is_not_scored_as_unchanged(self):
        def build():
            _source_assets()
            _hero_assets()
            WORLD.cdos[SOURCE] = None
        _, parsed = run_leg(build)
        got = {c.id: c for c in parsed.checks}["source_unchanged_not_character"]
        self.assertFalse(got.passed)
        self.assertIn("SOURCE_PARENT_CDO_UNAVAILABLE", got.detail)


class TestErrorTokensAreDisjointFromMatrix(unittest.TestCase):
    """An API break must never be creditable as a variant's named failure."""

    def test_no_error_token_appears_in_any_matrix_substring(self):
        rows = parse_matrix(MATRIX_PATH.read_text(encoding="utf-8"))
        subs = [s for r in rows.values() for s in r.substrings]
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        tokens = sorted({t for t in
                         __import__("re").findall(r"\b[A-Z][A-Z0-9_]{6,}\b", source)
                         if t.endswith(("_ERROR", "_ABORTED", "_UNAVAILABLE",
                                        "_EMPTY", "_NOT_EVALUATED"))})
        self.assertTrue(tokens, "expected the script to define error tokens")
        for token in tokens:
            for sub in subs:
                self.assertNotIn(token, sub)

    def test_offline_run_without_unreal_fails_every_check(self):
        """No editor => 0/TOTAL_CHECKS, all error tokens. Never a vacuous PASS."""
        global WORLD
        WORLD = _World()
        MOD.unreal = None
        try:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                MOD.main()
            parsed = parse_introspect_verdict(buf.getvalue())
            self.assertEqual(parsed.total, TOTAL_CHECKS)
            self.assertEqual(parsed.passed_count, 0)
            payload = json.loads(buf.getvalue().splitlines()[1])
            self.assertEqual(len(payload["checks"]), TOTAL_CHECKS)
        finally:
            MOD.unreal = FakeUnreal


if __name__ == "__main__":
    unittest.main()

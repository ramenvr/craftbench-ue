"""Offline oracle for the t1-dawn-fog-lighting-rig L2I grader.

No editor, no UE install, no tokens. A minimal fake ``unreal`` module models
the reflection surface the introspect script actually uses, so every leg of
``discrimination/MATRIX.md`` can be simulated and joined against the REAL
``discriminate.parse_matrix`` + the REAL ``layers/l2_introspect`` parser.

Modelled on ``test_introspect_hero_blueprint.py`` (the pilot, the only L2I task
that has ever graded on a real editor), and it pins the same five properties:

  * the reference leg passes every one of the 14 checks;
  * every negative leg fails at the check its MATRIX row blames, and the row's
    substring is a literal the script PRINTS on that check's ``detail``;
  * the offline / no-``unreal`` path emits an ERROR token that appears in NO
    matrix row, so an API break can never be credited as a variant's named
    failure;
  * the denominator is a CONSTANT 14 on every leg, including the broken ones -
    a shrinking denominator is how a vacuous pass gets in;
  * nothing passes merely because a probe did not raise (``TestFailsClosed``).

The fake is deliberately dumb: it models asset paths, subobject names, the
component classes and the handful of scalar properties the script reads, and
nothing else. It cannot prove the UE property spellings are right - only a live
editor does that - but it does prove the grader's LOGIC and its printed tokens.
"""
import contextlib
import importlib.util
import io
import json
import math
import re
import sys
import types
import unittest
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
_VERIFY = _TESTS.parent
_REPO = _VERIFY.parent.parent

sys.path.insert(0, str(_VERIFY))
sys.path.insert(0, str(_REPO / "tools" / "run-agent"))

from layers.l2_introspect import parse_introspect_verdict  # noqa: E402
from aura_rig.discriminate import parse_matrix  # noqa: E402

TASK_DIR = _REPO / "tasks" / "bp" / "t1-dawn-fog-lighting-rig"
MATRIX_PATH = TASK_DIR / "discrimination" / "MATRIX.md"
SCRIPT_PATH = _VERIFY / "introspect" / "dawn_fog_lighting_rig.py"

# 14 until 2026-08-19, when three SPECIFIED-but-ungated requirements-table rows
# were closed (rig_is_placeable_actor, rig_carries_only_the_four_parts,
# sun_casts_shadows). Every score recorded before that date is out of 14.
TOTAL_CHECKS = 17


def _load_script():
    spec = importlib.util.spec_from_file_location("_dawn_fog_introspect",
                                                  SCRIPT_PATH)
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


class Rotator:
    def __init__(self, pitch=0.0, yaw=0.0, roll=0.0):
        self.pitch, self.yaw, self.roll = float(pitch), float(yaw), float(roll)


class Color:
    def __init__(self, r, g, b):
        self.r, self.g, self.b = int(r), int(g), int(b)


class _UObject:
    """Only the pythonized (first-choice) property spelling resolves.

    That is deliberate: the script tries several spellings and the fake must
    not let a wrong first guess pass silently.
    """

    def __init__(self, name, **props):
        self._name = name
        self._props = dict(props)
        self.unreadable = set()

    def get_name(self):
        return self._name

    def get_class(self):
        return _Class(type(self).__name__)

    def get_editor_property(self, name):
        if name in self.unreadable:
            raise RuntimeError("property %r is protected and cannot be read" % name)
        if name not in self._props:
            raise RuntimeError("unknown property %r on %s" % (name, self._name))
        return self._props[name]


class Actor(_UObject):
    """The Blueprint's root ACTOR subobject - deliberately NOT a scene
    component, so it terminates ``_scene_ancestors``' walk."""


class SceneComponent(_UObject):
    def __init__(self, name, **props):
        props.setdefault("relative_rotation", Rotator())
        _UObject.__init__(self, name, **props)

    def get_relative_rotation(self):
        return self.get_editor_property("relative_rotation")


class SkyAtmosphereComponent(SceneComponent):
    pass


class LightComponentBase(SceneComponent):
    pass


class LightComponent(LightComponentBase):
    pass


class SkyLightComponent(LightComponentBase):
    pass


class DirectionalLightComponent(LightComponent):
    pass


class PointLightComponent(LightComponent):
    pass


class ExponentialHeightFogComponent(SceneComponent):
    pass


class SubobjectDataHandle:
    def __init__(self, data):
        self.data = data


class SubobjectData:
    def __init__(self, var_name, obj, parent=None):
        self.var_name = var_name
        self.obj = obj
        #: The SCS attach parent. ``None`` means "attached to nothing", which is
        #: what the root-most scene component reports.
        self.parent = parent

    @property
    def handle(self):
        return SubobjectDataHandle(self)


class SubobjectDataSubsystem:
    pass


class Blueprint(_UObject):
    def __init__(self, name, subobjects, status="BlueprintStatus.BS_UP_TO_DATE",
                 generate_abstract_class=False):
        # generate_abstract_class is the placeability flag rig_is_placeable_actor
        # reads (Class Settings -> Generate Abstract Class). Modelled because
        # _UObject.get_editor_property RAISES on an unknown name, so omitting it
        # would make that check fail-closed on EVERY leg for a mock reason and
        # quietly stop testing the property at all.
        _UObject.__init__(self, name, status=status,
                          generate_abstract_class=bool(generate_abstract_class))
        self.subobjects = subobjects


class _World:
    """One simulated project state."""

    def __init__(self):
        self.assets = {}          # content path -> Blueprint
        self.gather_empty = False
        self.exists_raises = False
        self.parent_handle_raises = False


WORLD = _World()


class _EditorAssetLibrary:
    @staticmethod
    def does_asset_exist(path):
        if WORLD.exists_raises:
            raise RuntimeError("asset registry unavailable")
        return path in WORLD.assets

    @staticmethod
    def load_asset(path):
        return WORLD.assets[path]


class _SubobjectLib:
    @staticmethod
    def get_data(handle):
        return handle.data

    @staticmethod
    def get_variable_name(data):
        return data.var_name

    @staticmethod
    def get_object(data):
        return data.obj

    @staticmethod
    def get_parent_handle(data):
        """The SCS attach parent's handle, invalid-shaped when there is none.

        Modelled on ``FSubobjectData::GetParentHandle``, a
        ``UFUNCTION(BlueprintCallable, BlueprintPure)`` that returns a handle by
        value: an unparented subobject yields an INVALID handle, not ``None``.
        The fake reproduces that so ``is_handle_valid`` is genuinely exercised.
        """
        if WORLD.parent_handle_raises:
            raise RuntimeError("parent handle accessor unavailable")
        return SubobjectDataHandle(data.parent)

    @staticmethod
    def is_handle_valid(handle):
        return handle is not None and handle.data is not None


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
    SkyAtmosphereComponent = SkyAtmosphereComponent
    SkyLightComponent = SkyLightComponent
    DirectionalLightComponent = DirectionalLightComponent
    PointLightComponent = PointLightComponent
    ExponentialHeightFogComponent = ExponentialHeightFogComponent
    SceneComponent = SceneComponent

    @staticmethod
    def get_engine_subsystem(cls):
        return _Subsystem

    @staticmethod
    def log(msg):
        pass


def _unreal_without(*names):
    """A stand-in ``unreal`` module with some attributes genuinely ABSENT.

    Subclassing would not do: ``getattr`` still finds the base's attribute
    through the MRO, so the "this build does not expose the type" case would
    never be simulated.
    """
    attrs = {k: getattr(FakeUnreal, k) for k in vars(FakeUnreal)
             if not k.startswith("__") and k not in names}
    return types.SimpleNamespace(**attrs)


# --------------------------------------------------------------------------- #
# leg builders - notes.md section 2 is the property-level source of truth      #
# --------------------------------------------------------------------------- #

MOD = _load_script()
RIG = MOD.ASSET_RIG


def _sun(pitch=-8.0, color=(255, 128, 70), intensity=2.5,
         use_temperature=False, temperature=6500.0, cls=DirectionalLightComponent,
         cast_shadows=True):
    # cast_shadows defaults TRUE because that is the engine default the reference
    # inherits; sun_casts_shadows reads it (2026-08-19). As with
    # generate_abstract_class above, leaving it off the mock would fail the check
    # closed everywhere for a reason that has nothing to do with the submission.
    return cls("Sun",
               relative_rotation=Rotator(pitch, 0.0, 0.0),
               light_color=Color(*color),
               intensity=float(intensity),
               use_temperature=bool(use_temperature),
               temperature=float(temperature),
               cast_shadows=bool(cast_shadows))


def _ambient(intensity=0.25, real_time_capture=True):
    return SkyLightComponent("Ambient",
                             intensity=float(intensity),
                             real_time_capture=bool(real_time_capture))


def _fog(density=0.6, volumetric=True, extinction=4.0):
    return ExponentialHeightFogComponent(
        "Fog",
        fog_density=float(density),
        enable_volumetric_fog=bool(volumetric),
        volumetric_fog_extinction_scale=float(extinction))


def _rig(sky=True, sun=None, ambient=None, fog=None,
         status="BlueprintStatus.BS_UP_TO_DATE", root_rotation=None,
         generate_abstract_class=False, extra=()):
    """Author BP_DawnLighting: actor root -> DefaultSceneRoot -> the four parts.

    The ACTOR root subobject is modelled because it is what really terminates
    the attach chain: ``SubobjectDataSubsystem`` gathers off
    ``GeneratedClass->GetDefaultObject()``, so handle 0 is the actor, not a
    scene component, and ``_scene_ancestors`` has to stop there rather than try
    to read a ``RelativeRotation`` off an ``AActor``. Its variable name is
    ``"None"`` so the script's display-name FALLBACK to the object name is
    exercised too.

    ``root_rotation`` rotates ``DefaultSceneRoot``. That is the whole point of
    the world-space fix: an author may put the sun's angle EITHER on the light
    or on the root, and both are the same sun.
    """
    actor = SubobjectData("None", _UObject("Default__BP_DawnLighting_C"))
    root = SubobjectData(
        "DefaultSceneRoot",
        SceneComponent("DefaultSceneRoot",
                       relative_rotation=root_rotation or Rotator()),
        parent=actor)
    subs = [actor, root]
    if sky:
        subs.append(SubobjectData("Sky", SkyAtmosphereComponent("Sky"),
                                  parent=root))
    for comp in (ambient if ambient is not None else _ambient(),
                 sun if sun is not None else _sun(),
                 fog if fog is not None else _fog()):
        if comp is not None:
            subs.append(SubobjectData(comp.get_name(), comp, parent=root))
    # `extra` = components beyond the required four, for the census check.
    for comp in extra:
        subs.append(SubobjectData(comp.get_name(), comp, parent=root))
    WORLD.assets[RIG] = Blueprint(
        "BP_DawnLighting", subs, status=status,
        generate_abstract_class=generate_abstract_class)
    return WORLD.assets[RIG]


LEGS = {}


def _leg(name):
    def deco(fn):
        LEGS[name] = fn
        return fn
    return deco


@_leg("reference")
def _reference():
    _rig()


@_leg("empty")
def _empty():
    # This task ships NO baseline asset, so an empty deliverable means the
    # content folder is genuinely empty.
    pass


@_leg("three-lights-no-atmosphere")
def _three_lights_no_atmosphere():
    _rig(sky=False)


@_leg("named-not-typed")
def _named_not_typed():
    # A point light wearing the name "Sun".
    _rig(sun=_sun(cls=PointLightComponent))


@_leg("overhead-noon-sun")
def _overhead_noon_sun():
    _rig(sun=_sun(pitch=-60.0))


@_leg("default-white-sun")
def _default_white_sun():
    _rig(sun=_sun(color=(255, 255, 255)))


@_leg("engine-default-fog")
def _engine_default_fog():
    # Every ExponentialHeightFogComponent ctor default (fog present, untouched).
    _rig(fog=_fog(density=0.02, volumetric=False, extinction=1.0))


def run_leg(builder, unreal_module=FakeUnreal):
    """Run the introspect script against a freshly built world."""
    global WORLD
    WORLD = _World()
    MOD.unreal = unreal_module
    builder()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        MOD.main()
    out = buf.getvalue()
    return out, parse_introspect_verdict(out)


def _by_id(parsed):
    return {c.id: c for c in parsed.checks}


# --------------------------------------------------------------------------- #
# tests                                                                        #
# --------------------------------------------------------------------------- #

class TestMatrixIsCreditable(unittest.TestCase):
    """Every MATRIX row must be parseable AND its substring actually printed."""

    def setUp(self):
        self.rows = parse_matrix(MATRIX_PATH.read_text(encoding="utf-8"))

    def test_every_declared_leg_has_a_row(self):
        self.assertEqual(set(self.rows), set(LEGS))

    def test_the_on_disk_variant_dirs_match_the_matrix(self):
        disc = TASK_DIR / "discrimination"
        on_disk = sorted(p.name for p in disc.iterdir() if p.is_dir())
        declared = sorted(k for k in self.rows if k not in ("reference", "empty"))
        self.assertEqual(on_disk, declared)

    def test_no_negative_leg_has_a_blank_substring_tuple(self):
        blank = sorted(k for k, v in self.rows.items()
                       if not v.expect_pass and not v.substrings)
        self.assertEqual(blank, [], "these legs can never be credited")

    def test_no_substring_carries_backticks(self):
        for label, row in self.rows.items():
            for sub in row.substrings:
                self.assertNotIn("`", sub,
                                 "%s: backticks never match log text" % label)

    def test_reference_leg_passes_all_fourteen(self):
        out, parsed = run_leg(LEGS["reference"])
        self.assertTrue(parsed.found)
        self.assertEqual(parsed.total, TOTAL_CHECKS)
        failed = [(c.id, c.detail) for c in parsed.checks if not c.passed]
        self.assertEqual(failed, [], out)

    def test_every_leg_reports_the_same_fourteen_checks(self):
        """Constant denominator - a shrunken one is how a vacuous pass gets in."""
        for label, builder in LEGS.items():
            with self.subTest(leg=label):
                _, parsed = run_leg(builder)
                self.assertTrue(parsed.found)
                self.assertEqual(parsed.total, TOTAL_CHECKS)
                self.assertEqual([c.id for c in parsed.checks],
                                 list(MOD.CHECK_IDS))

    def test_every_negative_leg_fails_with_its_named_substring(self):
        for label, builder in LEGS.items():
            row = self.rows[label]
            if row.expect_pass:
                continue
            with self.subTest(leg=label):
                out, parsed = run_leg(builder)
                self.assertTrue(parsed.found)
                self.assertEqual(parsed.total, TOTAL_CHECKS)
                self.assertLess(parsed.passed_count, TOTAL_CHECKS,
                                "expected a FAIL")
                details = "\n".join(c.detail for c in parsed.checks
                                    if not c.passed)
                for sub in row.substrings:
                    self.assertIn(sub, details,
                                  "%s: MATRIX substring never printed" % label)

    def test_named_substring_lands_on_the_predicted_check(self):
        """The substring must appear on the check the MATRIX blames, not just
        somewhere in the verdict."""
        expected = {
            "empty": "rig_asset_exists",
            "three-lights-no-atmosphere": "rig_sky_atmosphere_present",
            "named-not-typed": "rig_sun_light_present",
            "overhead-noon-sun": "sun_angle_is_low_dawn",
            "default-white-sun": "sun_color_is_warm",
            "engine-default-fog": "fog_density_is_dense",
        }
        self.assertEqual(sorted(expected),
                         sorted(k for k, v in self.rows.items()
                                if not v.expect_pass))
        for label, check_id in expected.items():
            with self.subTest(leg=label):
                _, parsed = run_leg(LEGS[label])
                got = _by_id(parsed)[check_id]
                self.assertFalse(got.passed)
                for sub in self.rows[label].substrings:
                    self.assertIn(sub, got.detail)

    def test_each_variant_scores_exactly_what_the_matrix_records(self):
        """The 'Also fails' column, executed rather than asserted in prose."""
        # Re-measured 2026-08-19 when the denominator went 14 -> 17. Every number
        # is what the grader actually returns for that leg, not the old value plus
        # three: named-not-typed gains only ONE (sun_casts_shadows cascades off the
        # same wrong-type sun lookup), while the rest gain all three.
        expected = {
            "reference": TOTAL_CHECKS,
            "empty": 0,
            "three-lights-no-atmosphere": 16,
            "named-not-typed": 12,
            "overhead-noon-sun": 16,
            "default-white-sun": 16,
            "engine-default-fog": 14,
        }
        for label, score in expected.items():
            with self.subTest(leg=label):
                _, parsed = run_leg(LEGS[label])
                self.assertEqual(parsed.passed_count, score,
                                 [(c.id, c.detail) for c in parsed.checks
                                  if not c.passed])

    def test_the_sun_resolution_failure_fans_out_to_the_three_value_checks(self):
        """One cause, one token, FIVE checks - the MATRIX prose, executed.

        sun_casts_shadows joined the fan-out 2026-08-19: it resolves the sun
        through the same type-checked lookup, so a `Sun` that is a PointLight
        cascades into it as well. Asserted rather than left implicit, because this
        cascade is invisible to `cb discriminate` (which only checks the leg fails
        at its NAMED substring) and it is the reason this leg scores 12/17 and not
        13/17.
        """
        _, parsed = run_leg(LEGS["named-not-typed"])
        by_id = _by_id(parsed)
        for cid in ("rig_sun_light_present", "sun_angle_is_low_dawn",
                    "sun_color_is_warm", "sun_intensity_is_dim",
                    "sun_casts_shadows"):
            self.assertFalse(by_id[cid].passed, cid)
            self.assertIn("RIG_SUN_LIGHT_WRONG_TYPE class=", by_id[cid].detail)

    def test_engine_default_fog_trips_all_three_fog_gates(self):
        _, parsed = run_leg(LEGS["engine-default-fog"])
        by_id = _by_id(parsed)
        self.assertIn("FOG_DENSITY_TOO_THIN density=",
                      by_id["fog_density_is_dense"].detail)
        self.assertIn("FOG_VOLUMETRIC_DISABLED enabled=",
                      by_id["fog_volumetric_enabled"].detail)
        self.assertIn("FOG_EXTINCTION_TOO_LOW scale=",
                      by_id["fog_extinction_raised"].detail)


class TestDeadGateAudit(unittest.TestCase):
    """Every graded band must EXCLUDE the UE 5.8 constructor default.

    A band an untouched component already sits inside grades nothing. The
    defaults are the ones the script's own docstring cites, and this test is
    what keeps a band re-cut (there has already been one, 2026-07-27) from
    quietly re-admitting one.
    """

    def test_no_band_admits_the_engine_default(self):
        self.assertFalse(MOD.SUN_PITCH_MIN <= 0.0 <= MOD.SUN_PITCH_MAX,
                         "identity rotation would pass sun_angle_is_low_dawn")
        self.assertFalse(MOD.SUN_INTENSITY_MIN <= 10.0 <= MOD.SUN_INTENSITY_MAX)
        self.assertFalse(
            MOD.SKYLIGHT_INTENSITY_MIN <= 1.0 <= MOD.SKYLIGHT_INTENSITY_MAX)
        self.assertFalse(MOD.FOG_DENSITY_MIN <= 0.02 <= MOD.FOG_DENSITY_MAX)
        self.assertGreater(MOD.FOG_EXTINCTION_MIN, 1.0)
        self.assertFalse(
            MOD.SUN_TEMPERATURE_MIN <= 6500.0 <= MOD.SUN_TEMPERATURE_MAX)

    def test_pure_white_is_not_a_warm_colour(self):
        # R == G == B fails the strict ordering, whatever the thresholds are.
        _, parsed = run_leg(lambda: _rig(sun=_sun(color=(255, 255, 255))))
        self.assertFalse(_by_id(parsed)["sun_color_is_warm"].passed)

    def test_the_documented_reference_values_sit_inside_the_graded_bands(self):
        # notes.md section 2 is the .uasset authoring spec. If a band is re-cut
        # so these fall outside it, that spec is now wrong on disk.
        self.assertTrue(MOD.SUN_PITCH_MIN <= -8.0 <= MOD.SUN_PITCH_MAX)
        self.assertTrue(MOD.SUN_INTENSITY_MIN <= 2.5 <= MOD.SUN_INTENSITY_MAX)
        self.assertTrue(
            MOD.SKYLIGHT_INTENSITY_MIN <= 0.25 <= MOD.SKYLIGHT_INTENSITY_MAX)
        self.assertTrue(MOD.FOG_DENSITY_MIN <= 0.6 <= MOD.FOG_DENSITY_MAX)
        self.assertGreaterEqual(4.0, MOD.FOG_EXTINCTION_MIN)
        self.assertTrue(MOD.SUN_TEMPERATURE_MIN <= 2400.0
                        <= MOD.SUN_TEMPERATURE_MAX)

    def test_the_documented_variant_values_stay_outside_the_graded_bands(self):
        # The five variant READMEs name these exact numbers.
        self.assertFalse(MOD.SUN_PITCH_MIN <= -60.0 <= MOD.SUN_PITCH_MAX)
        self.assertFalse(MOD.FOG_DENSITY_MIN <= 0.02 <= MOD.FOG_DENSITY_MAX)
        self.assertLess(1.0, MOD.FOG_EXTINCTION_MIN)

    def test_the_four_component_names_are_the_documented_ones(self):
        self.assertEqual(
            (MOD.SKY_NAME, MOD.AMBIENT_NAME, MOD.SUN_NAME, MOD.FOG_NAME),
            ("Sky", "Ambient", "Sun", "Fog"))


class TestFailsClosed(unittest.TestCase):
    """No check may pass because a probe merely did not raise."""

    def test_a_scene_component_named_sun_is_not_a_sun(self):
        # Anti-gaming #2: the name is not the thing. A bare SceneComponent that
        # happens to expose intensity/colour must not be graded numerically.
        impostor = SceneComponent("Sun",
                                  relative_rotation=Rotator(-8.0, 0.0, 0.0),
                                  light_color=Color(255, 128, 70),
                                  intensity=2.5)
        _, parsed = run_leg(lambda: _rig(sun=impostor))
        got = _by_id(parsed)["rig_sun_light_present"]
        self.assertFalse(got.passed)
        self.assertIn("RIG_SUN_LIGHT_WRONG_TYPE class=SceneComponent", got.detail)

    def test_a_type_the_build_does_not_expose_fails_rather_than_passes(self):
        # _isinstance_tristate returns None when unreal.<Type> is absent; the
        # part must NOT be credited, and the token must be distinct from the
        # "you never added it" token the matrix credits.
        no_type = _unreal_without("SkyAtmosphereComponent")
        _, parsed = run_leg(lambda: _rig(), unreal_module=no_type)
        got = _by_id(parsed)["rig_sky_atmosphere_present"]
        self.assertFalse(got.passed)
        self.assertIn("RIG_SKY_ATMOSPHERE_TYPE_PROBE_ERROR class=", got.detail)
        self.assertNotIn("RIG_SKY_ATMOSPHERE_MISSING", got.detail)

    def test_an_empty_subobject_walk_is_an_error_not_four_absent_parts(self):
        # A silently empty gather used to read as "this rig has no components",
        # which is the three-lights-no-atmosphere variant's named failure.
        def build():
            _rig()
            WORLD.gather_empty = True
        _, parsed = run_leg(build)
        by_id = _by_id(parsed)
        self.assertTrue(by_id["rig_asset_exists"].passed)
        for cid in MOD.CHECK_IDS:
            if cid in ("rig_asset_exists", "rig_compiles_up_to_date"):
                continue
            self.assertFalse(by_id[cid].passed, cid)
            self.assertIn("RIG_SUBOBJECT_WALK_ERROR raised", by_id[cid].detail)
        self.assertNotIn("RIG_SKY_ATMOSPHERE_MISSING",
                         by_id["rig_sky_atmosphere_present"].detail)

    def test_an_unreadable_rotation_is_an_error_not_a_noon_sun(self):
        def build():
            rig = _rig()
            sun = [d.obj for d in rig.subobjects if d.var_name == "Sun"][0]
            sun.unreadable.add("relative_rotation")
        _, parsed = run_leg(build)
        got = _by_id(parsed)["sun_angle_is_low_dawn"]
        self.assertFalse(got.passed)
        self.assertIn("SUN_PITCH_READ_ERROR raised", got.detail)
        self.assertNotIn("SUN_PITCH_NOT_LOW", got.detail)

    def test_an_unreadable_volumetric_flag_is_an_error_not_off(self):
        def build():
            rig = _rig()
            fog = [d.obj for d in rig.subobjects if d.var_name == "Fog"][0]
            fog.unreadable.add("enable_volumetric_fog")
        _, parsed = run_leg(build)
        got = _by_id(parsed)["fog_volumetric_enabled"]
        self.assertFalse(got.passed)
        self.assertIn("FOG_VOLUMETRIC_READ_ERROR raised", got.detail)
        self.assertNotIn("FOG_VOLUMETRIC_DISABLED", got.detail)

    def test_an_asset_probe_that_raises_is_not_the_empty_leg(self):
        # RIG_ASSET_MISSING is the empty leg's credited token; a broken registry
        # must carry a DIFFERENT one or an API break scores as a real variant.
        def build():
            WORLD.exists_raises = True
        _, parsed = run_leg(build)
        got = _by_id(parsed)["rig_asset_exists"]
        self.assertFalse(got.passed)
        self.assertEqual(parsed.passed_count, 0)
        self.assertIn("RIG_ASSET_PROBE_ERROR", got.detail)
        self.assertNotIn(MOD.RIG_MISSING_TOKEN, got.detail)

    def test_a_low_temperature_that_is_switched_off_is_not_warm(self):
        # Dead-gate: 6500 K with bUseTemperature false IS the engine default, so
        # the temperature route must require BOTH halves.
        _, parsed = run_leg(lambda: _rig(sun=_sun(color=(255, 255, 255),
                                                  use_temperature=False,
                                                  temperature=2400.0)))
        got = _by_id(parsed)["sun_color_is_warm"]
        self.assertFalse(got.passed)
        self.assertIn("SUN_COLOR_NOT_WARM color=", got.detail)

    def test_the_temperature_route_is_a_genuine_second_way_to_pass(self):
        # notes.md section 2 promises it; if it did not work the task would
        # reject a correct answer.
        _, parsed = run_leg(lambda: _rig(sun=_sun(color=(255, 255, 255),
                                                  use_temperature=True,
                                                  temperature=2400.0)))
        self.assertEqual(parsed.passed_count, TOTAL_CHECKS,
                         [(c.id, c.detail) for c in parsed.checks
                          if not c.passed])

    def test_an_uncompiled_rig_fails_the_compile_check_only(self):
        _, parsed = run_leg(lambda: _rig(status="BlueprintStatus.BS_DIRTY"))
        got = _by_id(parsed)["rig_compiles_up_to_date"]
        self.assertFalse(got.passed)
        self.assertIn("RIG_NOT_UP_TO_DATE status=", got.detail)
        self.assertEqual(parsed.passed_count, TOTAL_CHECKS - 1)


class TestWorldSpaceSunAngle(unittest.TestCase):
    """``sun_angle_is_low_dawn`` grades the WORLD direction, not a local one.

    The defect this pins (found 2026-07-27, cross-row review): the check read
    the Sun COMPONENT's own ``RelativeRotation``, so a rig that produces the
    identical sun by rotating the RIG'S ROOT and leaving the light at identity
    was FAILED - a false negative against a correct answer. The composition
    must widen the gate for that case and for nothing else, so every test below
    comes in accept/reject pairs.
    """

    def _angle_check(self, **kwargs):
        _, parsed = run_leg(lambda: _rig(**kwargs))
        return _by_id(parsed)["sun_angle_is_low_dawn"]

    # --- the false negative, and its mirror ---------------------------------

    def test_a_rig_rotated_at_the_root_is_accepted(self):
        """THE REGRESSION. Root pitched -8, light at identity: same sun."""
        got = self._angle_check(sun=_sun(pitch=0.0),
                                root_rotation=Rotator(-8.0, 0.0, 0.0))
        self.assertTrue(got.passed, got.detail)
        self.assertIn("SUN_PITCH_OK world_pitch=-8.0000", got.detail)

    def test_a_rig_rotated_at_the_light_is_still_accepted(self):
        """The reference shape must not regress while fixing the other one."""
        got = self._angle_check(sun=_sun(pitch=-8.0))
        self.assertTrue(got.passed, got.detail)
        self.assertIn("SUN_PITCH_OK world_pitch=-8.0000", got.detail)

    def test_the_rotation_may_be_split_across_the_chain(self):
        got = self._angle_check(sun=_sun(pitch=-4.0),
                                root_rotation=Rotator(-4.0, 0.0, 0.0))
        self.assertTrue(got.passed, got.detail)
        self.assertIn("world_pitch=-8.0000", got.detail)

    def test_a_root_that_cancels_the_light_is_rejected(self):
        """The gate must still be a gate: composed back to the horizon FAILS."""
        got = self._angle_check(sun=_sun(pitch=-8.0),
                                root_rotation=Rotator(8.0, 0.0, 0.0))
        self.assertFalse(got.passed, got.detail)
        self.assertIn("SUN_PITCH_NOT_LOW world_pitch=0.0000", got.detail)

    def test_a_root_that_drives_the_sun_underground_is_rejected(self):
        got = self._angle_check(sun=_sun(pitch=0.0),
                                root_rotation=Rotator(45.0, 0.0, 0.0))
        self.assertFalse(got.passed, got.detail)
        self.assertIn("SUN_PITCH_NOT_LOW world_pitch=45.0000", got.detail)

    def test_the_noon_variant_still_fails_the_same_way(self):
        """The MATRIX row must survive the change (its substring moved)."""
        got = self._angle_check(sun=_sun(pitch=-60.0))
        self.assertFalse(got.passed)
        rows = parse_matrix(MATRIX_PATH.read_text(encoding="utf-8"))
        for sub in rows["overhead-noon-sun"].substrings:
            self.assertIn(sub, got.detail)

    # --- the composition itself ---------------------------------------------

    def test_yaw_anywhere_in_the_chain_does_not_move_the_elevation(self):
        """Compass heading is not elevation; a yawed rig is not a noon sun."""
        got = self._angle_check(sun=_sun(pitch=-8.0),
                                root_rotation=Rotator(0.0, 137.0, 0.0))
        self.assertTrue(got.passed, got.detail)
        self.assertIn("world_pitch=-8.0000", got.detail)

    def test_the_matrix_row_is_the_ue_rotation_matrix(self):
        """Row 0 must equal ``FRotator::Vector`` = ``(cp*cy, cp*sy, sp)``.

        Transcription bugs here are silent - they would move every graded
        elevation by a few degrees without failing anything obviously.
        """
        for pitch, yaw, roll in ((-8.0, 0.0, 0.0), (0.0, 137.0, 0.0),
                                 (-25.0, -40.0, 15.0), (12.5, 200.0, -70.0)):
            with self.subTest(rotator=(pitch, yaw, roll)):
                row0 = MOD._rotator_matrix(pitch, yaw, roll)[0]
                cp, sp = (math.cos(math.radians(pitch)),
                          math.sin(math.radians(pitch)))
                cy, sy = (math.cos(math.radians(yaw)),
                          math.sin(math.radians(yaw)))
                for got, want in zip(row0, (cp * cy, cp * sy, sp)):
                    self.assertAlmostEqual(got, want, places=12)

    def test_the_matrix_is_orthonormal(self):
        m = MOD._rotator_matrix(-25.0, -40.0, 15.0)
        for i in range(3):
            for j in range(3):
                dot = sum(m[i][k] * m[j][k] for k in range(3))
                self.assertAlmostEqual(dot, 1.0 if i == j else 0.0, places=12)

    def test_an_unrotated_chain_reads_exactly_the_local_pitch(self):
        """Backwards compatibility: with a flat rig the number is unchanged."""
        for pitch in (-1.0, -8.0, -25.0, 0.0, -60.0):
            with self.subTest(pitch=pitch):
                got = self._angle_check(sun=_sun(pitch=pitch))
                self.assertIn("world_pitch=%.4f" % pitch, got.detail)

    # --- fail-closed ---------------------------------------------------------

    def test_an_unreadable_parent_chain_is_an_error_not_a_verdict(self):
        """A broken chain read must not be credited as the noon-sun failure."""
        def build():
            _rig(sun=_sun(pitch=0.0), root_rotation=Rotator(-8.0, 0.0, 0.0))
            WORLD.parent_handle_raises = True
        _, parsed = run_leg(build)
        got = _by_id(parsed)["sun_angle_is_low_dawn"]
        self.assertFalse(got.passed)
        self.assertIn("SUN_PITCH_READ_ERROR raised", got.detail)
        self.assertNotIn("SUN_PITCH_NOT_LOW", got.detail)

    def test_a_build_with_no_parent_handle_accessor_fails_closed(self):
        """The rest of the walk still works; only the chain read is missing.

        This is the shape a future UE would actually break in - the gather and
        the data accessors survive, ``GetParentHandle`` does not. It must be an
        ERROR, and it must NOT be the noon-sun token.
        """
        lib = types.SimpleNamespace(
            get_data=_SubobjectLib.get_data,
            get_variable_name=_SubobjectLib.get_variable_name,
            get_object=_SubobjectLib.get_object)
        crippled = _unreal_without("SubobjectDataBlueprintFunctionLibrary")
        crippled.SubobjectDataBlueprintFunctionLibrary = lib
        _, parsed = run_leg(lambda: _rig(), unreal_module=crippled)
        got = _by_id(parsed)["sun_angle_is_low_dawn"]
        self.assertFalse(got.passed)
        self.assertIn("SUN_PITCH_READ_ERROR raised", got.detail)
        self.assertIn("SUBOBJECT_PARENT_HANDLE_UNAVAILABLE", got.detail)
        self.assertNotIn("SUN_PITCH_NOT_LOW", got.detail)

    def test_an_attach_cycle_raises_instead_of_hanging(self):
        def build():
            rig = _rig()
            root = [d for d in rig.subobjects
                    if d.var_name == "DefaultSceneRoot"][0]
            sun = [d for d in rig.subobjects if d.var_name == "Sun"][0]
            root.parent = sun          # Sun -> root -> Sun -> ...
        _, parsed = run_leg(build)
        got = _by_id(parsed)["sun_angle_is_low_dawn"]
        self.assertFalse(got.passed)
        self.assertIn("SUN_PITCH_READ_ERROR raised", got.detail)
        self.assertIn("SUBOBJECT_ATTACH_CHAIN_TOO_DEEP", got.detail)

    def test_an_ancestor_with_an_unreadable_rotation_is_an_error(self):
        def build():
            rig = _rig()
            root = [d for d in rig.subobjects
                    if d.var_name == "DefaultSceneRoot"][0]
            root.obj.unreadable.add("relative_rotation")
        _, parsed = run_leg(build)
        got = _by_id(parsed)["sun_angle_is_low_dawn"]
        self.assertFalse(got.passed)
        self.assertIn("SUN_PITCH_READ_ERROR raised", got.detail)
        self.assertNotIn("SUN_PITCH_NOT_LOW", got.detail)

    def test_the_chain_stops_at_the_actor_and_does_not_read_it(self):
        """The actor root has no RelativeRotation; reading it would error."""
        got = self._angle_check(sun=_sun(pitch=-8.0))
        self.assertTrue(got.passed, got.detail)
        self.assertIn("DefaultSceneRoot:", got.detail)
        self.assertNotIn("Default__BP_DawnLighting_C", got.detail)


class TestErrorTokensAreDisjointFromMatrix(unittest.TestCase):
    """An API break must never be creditable as a variant's named failure."""

    def _error_tokens(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        return sorted({t for t in re.findall(r"\b[A-Z][A-Z0-9_]{6,}\b", source)
                       if t.endswith(("_ERROR", "_ABORTED", "_UNAVAILABLE",
                                      "_EMPTY", "_NOT_EVALUATED",
                                      "_UNREADABLE", "_TOO_DEEP"))})

    def test_no_error_token_appears_in_any_matrix_substring(self):
        rows = parse_matrix(MATRIX_PATH.read_text(encoding="utf-8"))
        subs = [s for r in rows.values() for s in r.substrings]
        tokens = self._error_tokens()
        self.assertTrue(tokens, "expected the script to define error tokens")
        self.assertTrue(subs, "expected the matrix to name some substrings")
        for token in tokens:
            for sub in subs:
                self.assertNotIn(token, sub)

    def test_script_carries_no_automation_result_marker(self):
        # parse_automation_log's whole-file finditer counts these as TESTS.
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertNotIn("TestResult" + "=Passed", source)
        self.assertNotIn("Automation Test" + " Succeeded", source)

    def test_script_is_pure_ascii(self):
        raw = SCRIPT_PATH.read_bytes()
        self.assertEqual(raw.decode("utf-8"), raw.decode("ascii"))

    def test_matrix_substrings_are_ascii_and_contain_a_space(self):
        rows = parse_matrix(MATRIX_PATH.read_text(encoding="utf-8"))
        for label, row in rows.items():
            for sub in row.substrings:
                sub.encode("ascii")
                self.assertIn(" ", sub,
                              "%s: a space-less tick is dropped by "
                              "_extract_substrings" % label)

    def test_offline_run_without_unreal_fails_every_check(self):
        """No editor => 0/14, an error token no matrix row claims."""
        global WORLD
        WORLD = _World()
        MOD.unreal = None
        try:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                MOD.main()
            out = buf.getvalue()
            parsed = parse_introspect_verdict(out)
            self.assertEqual(parsed.total, TOTAL_CHECKS)
            self.assertEqual(parsed.passed_count, 0)
            payload = json.loads(out.splitlines()[1])
            self.assertEqual(len(payload["checks"]), TOTAL_CHECKS)
            rows = parse_matrix(MATRIX_PATH.read_text(encoding="utf-8"))
            subs = [s for r in rows.values() for s in r.substrings]
            for chk in parsed.checks:
                self.assertIn("RIG_ASSET_PROBE_ERROR", chk.detail)
                for sub in subs:
                    self.assertNotIn(sub, chk.detail)
        finally:
            MOD.unreal = FakeUnreal


if __name__ == "__main__":
    unittest.main()

"""Offline oracle for the t1-third-person-chase-camera L2I grader.

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
  * nothing passes merely because a probe did not raise (``TestFailsClosed``),
    which matters most for ``camera_off_control_rotation`` - the one
    NEGATIVE-shaped check, whose passing state is "the flag reads False".

The fake models the SubobjectData graph (names, classes, attach parents and the
inherited/native/root flags), the asset-registry parent tags and the handful of
scalars the boom carries. It cannot prove the UE property spellings are right -
only a live editor does that - but it does prove the grader's LOGIC and its
printed tokens.
"""
import contextlib
import importlib.util
import io
import json
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

TASK_DIR = _REPO / "tasks" / "bp" / "t1-third-person-chase-camera"
MATRIX_PATH = TASK_DIR / "discrimination" / "MATRIX.md"
SCRIPT_PATH = _VERIFY / "introspect" / "third_person_chase_camera.py"

TOTAL_CHECKS = 14


def _load_script():
    spec = importlib.util.spec_from_file_location("_chase_camera_introspect",
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


class Vector:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = float(x), float(y), float(z)


class _UObject:
    """Only the pythonized (first-choice) property spelling resolves.

    That is deliberate: the script tries several spellings and the fake must
    not let a wrong first guess pass silently.
    """

    def __init__(self, name, path=None, **props):
        self._name = name
        self._path = path or name
        self._props = dict(props)
        self.unreadable = set()

    def get_name(self):
        return self._name

    def get_path_name(self):
        return self._path

    def get_class(self):
        return _Class(type(self).__name__)

    def get_editor_property(self, name):
        if name in self.unreadable:
            raise RuntimeError("property %r is protected and cannot be read" % name)
        if name not in self._props:
            raise RuntimeError("unknown property %r on %s" % (name, self._name))
        return self._props[name]


class SceneComponent(_UObject):
    def get_attach_parent(self):
        # On an SCS component TEMPLATE this pointer is null at rest; the
        # hierarchy lives in the SCS node graph. The script treats it as a
        # corroboration only, and this models the normal case.
        return self._props.get("_attach_parent")


class ShapeComponent(SceneComponent):
    pass


class CapsuleComponent(ShapeComponent):
    pass


class MeshComponent(SceneComponent):
    pass


class SkeletalMeshComponent(MeshComponent):
    pass


class SpringArmComponent(SceneComponent):
    pass


class CameraComponent(SceneComponent):
    pass


class SubobjectDataHandle:
    def __init__(self, data):
        self.data = data


class SubobjectData:
    def __init__(self, var_name, obj, parent=None,
                 inherited=False, native=False, root=False):
        self.var_name = var_name
        self.obj = obj
        self.parent = parent
        self.inherited = inherited
        self.native = native
        self.root = root

    @property
    def handle(self):
        return SubobjectDataHandle(self)


class SubobjectDataSubsystem:
    pass


class Blueprint(_UObject):
    def __init__(self, name, path, subobjects,
                 status="BlueprintStatus.BS_UP_TO_DATE"):
        _UObject.__init__(self, name, path, status=status)
        self.subobjects = subobjects


class _AssetData:
    def __init__(self, tags):
        self._tags = tags

    def get_tag_value(self, name):
        return self._tags.get(name, "")


class _World:
    """One simulated project state."""

    def __init__(self):
        self.assets = {}          # content path -> Blueprint
        self.tags = {}            # content path -> {tag: value}
        self.gather_empty = False
        self.exists_raises = False


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

    @staticmethod
    def is_root_component(data):
        return data.root


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
    SceneComponent = SceneComponent
    CapsuleComponent = CapsuleComponent
    SkeletalMeshComponent = SkeletalMeshComponent
    SpringArmComponent = SpringArmComponent
    CameraComponent = CameraComponent
    Vector = Vector

    @staticmethod
    def get_engine_subsystem(cls):
        return _Subsystem

    @staticmethod
    def log(msg):
        pass


def _unreal_without(*names):
    """A stand-in ``unreal`` module with some attributes genuinely ABSENT.

    Subclassing would not do: ``getattr`` still finds the base's attribute
    through the MRO, so the "this build does not expose the type/accessor"
    case would never be simulated.
    """
    attrs = {k: getattr(FakeUnreal, k) for k in vars(FakeUnreal)
             if not k.startswith("__") and k not in names}
    return types.SimpleNamespace(**attrs)


def _lib_without(*names):
    """``SubobjectDataBlueprintFunctionLibrary`` minus some accessors."""
    attrs = {k: getattr(_SubobjectLib, k) for k in vars(_SubobjectLib)
             if not k.startswith("__") and k not in names}
    lib = types.SimpleNamespace(**attrs)
    return types.SimpleNamespace(
        **dict({k: getattr(FakeUnreal, k) for k in vars(FakeUnreal)
                if not k.startswith("__")},
               SubobjectDataBlueprintFunctionLibrary=lib))


# --------------------------------------------------------------------------- #
# leg builders - notes.md sections 1-3 are the property-level source of truth  #
# --------------------------------------------------------------------------- #

MOD = _load_script()
SCOUT = MOD.ASSET_CHARACTER


def _boom_component(cls=SpringArmComponent, name="CameraBoom", path=None,
                    arm=400.0, socket=(0.0, 0.0, 75.0), control_rotation=True,
                    lag=True, lag_speed=4.0):
    """A SpringArmComponent template. ``cls=SceneComponent`` yields the
    "bare positioning node wearing the name" impostor, which carries NONE of
    the five scalars - exactly like the real thing."""
    if cls is not SpringArmComponent:
        return cls(name, path=path or (SCOUT + "_C:" + name))
    return cls(name, path=path or (SCOUT + "_C:" + name),
               target_arm_length=float(arm),
               socket_offset=Vector(*socket),
               target_offset=Vector(0.0, 0.0, 0.0),
               use_pawn_control_rotation=bool(control_rotation),
               enable_camera_lag=bool(lag),
               camera_lag_speed=float(lag_speed))


def _camera_component(control_rotation=False, cls=CameraComponent,
                      name="FollowCamera"):
    return cls(name, path=SCOUT + "_C:" + name,
               use_pawn_control_rotation=bool(control_rotation))


def _scout(boom=None, boom_parent="capsule", boom_inherited=False,
           camera=None, camera_parent="boom", extra=(),
           parent_class="Character", status="BlueprintStatus.BS_UP_TO_DATE",
           capsule_cls=CapsuleComponent, capsule_authored=False,
           capsule_root=None):
    """Author BP_Scout.

    ``boom_parent`` selects the boom's attach parent: "capsule" (the inherited
    collision body, correct), "mesh" (the animated mesh), or None (no parent
    handle at all). ``camera_parent`` selects the camera's: "boom", "capsule",
    or the SubobjectData of a decoy.
    """
    capsule_obj = capsule_cls("CapsuleComponent",
                              path=SCOUT + "_C:CollisionCylinder")
    capsule = SubobjectData("CapsuleComponent", capsule_obj,
                            inherited=not capsule_authored,
                            native=not capsule_authored,
                            root=(not capsule_authored if capsule_root is None
                                  else capsule_root))
    mesh = SubobjectData("CharacterMesh0",
                         SkeletalMeshComponent("CharacterMesh0",
                                               path=SCOUT + "_C:CharacterMesh0"),
                         parent=capsule, inherited=True, native=True)
    subs = [capsule, mesh]
    anchors = {"capsule": capsule, "mesh": mesh, None: None}

    boom_data = None
    if boom is not None:
        boom_data = SubobjectData("CameraBoom", boom,
                                  parent=anchors[boom_parent]
                                  if not isinstance(boom_parent, SubobjectData)
                                  else boom_parent,
                                  inherited=boom_inherited,
                                  native=boom_inherited)
        subs.append(boom_data)
    anchors["boom"] = boom_data

    for data in extra:
        subs.append(data)

    if camera is not None:
        target = (camera_parent if isinstance(camera_parent, SubobjectData)
                  else anchors[camera_parent])
        subs.append(SubobjectData("FollowCamera", camera, parent=target,
                                  inherited=boom_inherited,
                                  native=boom_inherited))

    WORLD.assets[SCOUT] = Blueprint("BP_Scout", SCOUT, subs, status=status)
    WORLD.tags[SCOUT] = {"ParentClass": parent_class,
                         "NativeParentClass": parent_class}
    return WORLD.assets[SCOUT]


LEGS = {}


def _leg(name):
    def deco(fn):
        LEGS[name] = fn
        return fn
    return deco


@_leg("reference")
def _reference():
    _scout(boom=_boom_component(), camera=_camera_component())


@_leg("empty")
def _empty():
    # The committed BASELINE: a boom-free Character whose FollowCamera hangs
    # off the capsule at head height and is still steering itself.
    _scout(boom=None, camera=_camera_component(control_rotation=True),
           camera_parent="capsule")


@_leg("rig-inherited-from-template-character")
def _rig_inherited_from_template_character():
    # Reparented to the substrate's third-person C++ character: the boom is
    # NATIVE, and the C++ base sets neither SocketOffset nor camera lag.
    _scout(boom=_boom_component(socket=(0.0, 0.0, 0.0), lag=False,
                                lag_speed=10.0),
           boom_inherited=True, camera=_camera_component(),
           parent_class="ThirdPersonCharacter")


@_leg("boom-hung-on-the-mesh")
def _boom_hung_on_the_mesh():
    _scout(boom=_boom_component(), boom_parent="mesh",
           camera=_camera_component())


@_leg("boom-is-a-plain-scene-component")
def _boom_is_a_plain_scene_component():
    _scout(boom=_boom_component(cls=SceneComponent), camera=_camera_component())


@_leg("boom-left-at-engine-defaults")
def _boom_left_at_engine_defaults():
    # Every SpringArmComponent ctor default (SpringArmComponent.cpp:18-46).
    _scout(boom=_boom_component(arm=300.0, socket=(0.0, 0.0, 0.0),
                                control_rotation=False, lag=False,
                                lag_speed=10.0),
           camera=_camera_component())


@_leg("camera-still-steering-itself")
def _camera_still_steering_itself():
    _scout(boom=_boom_component(),
           camera=_camera_component(control_rotation=True))


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
            "empty": "boom_component_exists",
            "rig-inherited-from-template-character": "boom_authored_on_this_asset",
            "boom-hung-on-the-mesh": "boom_attached_to_character_root",
            "boom-is-a-plain-scene-component": "boom_is_spring_arm",
            "boom-left-at-engine-defaults": "boom_arm_length_400",
            "camera-still-steering-itself": "camera_off_control_rotation",
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
        expected = {
            "reference": TOTAL_CHECKS,
            "empty": 3,
            "rig-inherited-from-template-character": 10,
            "boom-hung-on-the-mesh": 13,
            "boom-is-a-plain-scene-component": 7,
            "boom-left-at-engine-defaults": 9,
            "camera-still-steering-itself": 13,
        }
        for label, score in expected.items():
            with self.subTest(leg=label):
                _, parsed = run_leg(LEGS[label])
                self.assertEqual(parsed.passed_count, score,
                                 [(c.id, c.detail) for c in parsed.checks
                                  if not c.passed])

    def test_the_empty_leg_floor_is_the_three_checks_the_matrix_names(self):
        _, parsed = run_leg(LEGS["empty"])
        passed = sorted(c.id for c in parsed.checks if c.passed)
        self.assertEqual(passed, ["camera_component_exists",
                                  "character_asset_exists",
                                  "character_compiles_up_to_date"])
        by_id = _by_id(parsed)
        # The fan-out must carry the SAME credited substring the matrix names,
        # read from the matrix rather than hard-coded, so a token rename shows
        # up as a MATRIX-vs-script mismatch and not as a stale test literal.
        for sub in self.rows["empty"].substrings:
            for cid in MOD._BOOM_DEPENDENT:
                self.assertIn(sub, by_id[cid].detail, cid)

    def test_the_inherited_rig_would_score_eleven_without_the_authorship_check(self):
        """The whole reason boom_authored_on_this_asset exists (notes.md 0)."""
        _, parsed = run_leg(LEGS["rig-inherited-from-template-character"])
        by_id = _by_id(parsed)
        self.assertFalse(by_id["boom_authored_on_this_asset"].passed)
        self.assertIn("BOOM_NOT_AUTHORED_ON_ASSET inherited=",
                      by_id["boom_authored_on_this_asset"].detail)
        without = sum(1 for c in parsed.checks
                      if c.passed or c.id == "boom_authored_on_this_asset")
        self.assertEqual(without, 11)

    def test_the_plain_scene_component_boom_fails_five_scalars_as_errors(self):
        """Those five are ERROR tokens by design, and none is a matrix row."""
        _, parsed = run_leg(LEGS["boom-is-a-plain-scene-component"])
        by_id = _by_id(parsed)
        for cid, token in (("boom_arm_length_400", "BOOM_ARM_LENGTH_READ_ERROR"),
                           ("boom_socket_offset_up_75",
                            "BOOM_SOCKET_OFFSET_READ_ERROR"),
                           ("boom_uses_control_rotation",
                            "BOOM_CONTROL_ROTATION_READ_ERROR"),
                           ("boom_camera_lag_enabled",
                            "BOOM_CAMERA_LAG_READ_ERROR"),
                           ("boom_camera_lag_speed_4",
                            "BOOM_LAG_SPEED_READ_ERROR")):
            self.assertFalse(by_id[cid].passed, cid)
            self.assertIn(token, by_id[cid].detail)
        self.assertIn("CAMERA_ATTACH_PARENT_WRONG",
                      by_id["camera_attached_to_boom"].detail)

    def test_engine_default_boom_trips_all_five_settings(self):
        _, parsed = run_leg(LEGS["boom-left-at-engine-defaults"])
        by_id = _by_id(parsed)
        for cid, token in (("boom_arm_length_400", "BOOM_ARM_LENGTH_WRONG value="),
                           ("boom_socket_offset_up_75",
                            "BOOM_SOCKET_OFFSET_WRONG value="),
                           ("boom_uses_control_rotation",
                            "BOOM_NOT_ON_CONTROL_ROTATION value="),
                           ("boom_camera_lag_enabled",
                            "BOOM_CAMERA_LAG_DISABLED value="),
                           ("boom_camera_lag_speed_4",
                            "BOOM_LAG_SPEED_WRONG value=")):
            self.assertFalse(by_id[cid].passed, cid)
            self.assertIn(token, by_id[cid].detail)


class TestEmptyLegTokenIsUnambiguous(unittest.TestCase):
    """The 2026-07-27 silent-degradation fix, from the credited side.

    ``TestFailsClosed`` proves the *error* side - that a degraded walk RAISES.
    This class proves the other half: the empty leg's credited substring is a
    POSITIVE claim (``searched=<N>``, N subobjects walked AND every one named),
    so it cannot be produced by anything except a complete walk that found no
    boom. Before the fix the matrix joined on ``BOOM_COMPONENT_MISSING names=``,
    which a build with two broken name accessors printed verbatim as
    ``names=[]``.
    """

    def _empty_substrings(self):
        rows = parse_matrix(MATRIX_PATH.read_text(encoding="utf-8"))
        return rows["empty"].substrings

    def test_the_matrix_joins_on_the_positive_searched_token(self):
        self.assertEqual(self._empty_substrings(),
                         ("BOOM_COMPONENT_MISSING searched=",))

    def test_the_genuine_empty_leg_carries_a_nonzero_searched_count(self):
        _, parsed = run_leg(LEGS["empty"])
        got = _by_id(parsed)["boom_component_exists"]
        self.assertFalse(got.passed)
        for sub in self._empty_substrings():
            self.assertIn(sub, got.detail)
        self.assertRegex(got.detail, r"searched=[1-9][0-9]*")
        self.assertIn("wanted=%s" % MOD.BOOM_NAME, got.detail)
        # names= survives as a diagnostic and must still list what WAS found.
        self.assertIn(MOD.CAMERA_NAME, got.detail)

    def test_the_absent_camera_token_is_positive_the_same_way(self):
        """Same rule on the camera side, so the shape cannot rot back."""
        def build():
            _scout(boom=_boom_component(), camera=None)
        _, parsed = run_leg(build)
        got = _by_id(parsed)["camera_component_exists"]
        self.assertFalse(got.passed)
        self.assertIn("%s searched=" % MOD.CAMERA_MISSING_TOKEN, got.detail)
        self.assertRegex(got.detail, r"searched=[1-9][0-9]*")

    def test_the_boom_fanout_carries_the_same_positive_token(self):
        """All 8 dependents inherit it, so none of them is credit-ambiguous."""
        _, parsed = run_leg(LEGS["empty"])
        by_id = _by_id(parsed)
        for cid in MOD._BOOM_DEPENDENT:
            self.assertFalse(by_id[cid].passed, cid)
            self.assertIn("BOOM_COMPONENT_MISSING searched=", by_id[cid].detail)

    def test_an_unresolvable_subobject_data_is_an_error_not_an_absent_boom(self):
        """The OTHER degradation ``_components`` used to swallow with `continue`.

        ``GetData`` handing back nothing is a different break from
        ``GetVariableName`` handing back nothing, and it used to reach the same
        place: a short walk that reads as "the component is not there".
        """
        blind = _unreal_without("SubobjectDataBlueprintFunctionLibrary")
        blind.SubobjectDataBlueprintFunctionLibrary = types.SimpleNamespace(
            get_data=lambda handle: None,
            is_handle_valid=_SubobjectLib.is_handle_valid,
            get_parent_handle=_SubobjectLib.get_parent_handle,
            is_inherited_component=_SubobjectLib.is_inherited_component,
            is_native_component=_SubobjectLib.is_native_component,
            get_variable_name=_SubobjectLib.get_variable_name,
            get_object=_SubobjectLib.get_object)
        _, parsed = run_leg(lambda: _scout(boom=_boom_component(),
                                           camera=_camera_component()),
                            unreal_module=blind)
        got = _by_id(parsed)["boom_component_exists"]
        self.assertFalse(got.passed)
        self.assertIn("SUBOBJECT_NAMES_UNREADABLE", got.detail)
        self.assertIn("unresolved=", got.detail)
        for sub in self._empty_substrings():
            self.assertNotIn(sub, got.detail)

    def test_a_partially_readable_walk_is_refused_whole(self):
        """ONE unnameable subobject is enough - a short walk is not a walk.

        The boom is present and perfectly configured; only an unrelated
        subobject's name will not read. A grader that soldiered on would report
        a rig that is actually correct, off an incomplete picture.
        """
        real_get_object = _SubobjectLib.get_object

        def one_blind_object(data):
            obj = real_get_object(data)
            return None if getattr(obj, "_name", "") == "CharacterMesh0" else obj

        blind = _unreal_without("SubobjectDataBlueprintFunctionLibrary")
        blind.SubobjectDataBlueprintFunctionLibrary = types.SimpleNamespace(
            get_data=_SubobjectLib.get_data,
            is_handle_valid=_SubobjectLib.is_handle_valid,
            get_parent_handle=_SubobjectLib.get_parent_handle,
            is_inherited_component=_SubobjectLib.is_inherited_component,
            is_native_component=_SubobjectLib.is_native_component,
            is_root_component=_SubobjectLib.is_root_component,
            get_variable_name=lambda data: "None",
            get_object=one_blind_object)
        _, parsed = run_leg(lambda: _scout(boom=_boom_component(),
                                           camera=_camera_component()),
                            unreal_module=blind)
        got = _by_id(parsed)["boom_component_exists"]
        self.assertFalse(got.passed)
        self.assertIn("SUBOBJECT_NAMES_UNREADABLE", got.detail)
        self.assertIn("unnamed=1", got.detail)

    def test_the_lenient_walk_this_replaced_would_still_be_creditable(self):
        """The regression as a live, permanent demonstration.

        Restores the PRE-FIX ``_components`` body - skip an unresolvable
        subobject, keep a blank display name, let ``_names_of`` filter it out -
        and shows that with it, a submission that DOES have a correct boom, run
        against a build whose name accessors are broken, prints
        ``BOOM_COMPONENT_MISSING names=[]``: the same token, on the same check,
        as a genuinely boom-free asset. Then shows the shipping walk keeps the
        two apart. Reproducing the defect rather than citing a git revision
        keeps this true after the fix is many commits old.
        """
        def lenient_components(blueprint):
            subsystem = MOD._subobject_subsystem()
            out = []
            for handle in MOD._gather_handles(subsystem, blueprint):
                data = MOD._data_for(handle)
                if data is None:
                    continue
                out.append((MOD._sub_display_name(data), data))
            if not out:
                raise RuntimeError("SUBOBJECT_WALK_EMPTY")
            return out

        blind = _unreal_without("SubobjectDataBlueprintFunctionLibrary")
        blind.SubobjectDataBlueprintFunctionLibrary = types.SimpleNamespace(
            get_data=_SubobjectLib.get_data,
            is_handle_valid=_SubobjectLib.is_handle_valid,
            get_parent_handle=_SubobjectLib.get_parent_handle,
            is_inherited_component=_SubobjectLib.is_inherited_component,
            is_native_component=_SubobjectLib.is_native_component,
            is_root_component=_SubobjectLib.is_root_component,
            get_variable_name=lambda data: "",
            get_object=lambda data: None)
        build = lambda: _scout(boom=_boom_component(), camera=_camera_component())

        shipping = MOD._components
        MOD._components = lenient_components
        try:
            _, parsed = run_leg(build, unreal_module=blind)
        finally:
            MOD._components = shipping
        was = _by_id(parsed)["boom_component_exists"].detail
        # `BOOM_COMPONENT_MISSING names=` is what the matrix row used to be, and
        # here it is - `names=[]` - printed for an asset whose boom is present
        # and correct. (The shipping `_absent` renderer is still in play, so the
        # count sits between the two halves; the OLD row's substring is the
        # `BOOM_COMPONENT_MISSING ... names=` pair, and both parts are here.)
        self.assertIn("BOOM_COMPONENT_MISSING", was)
        self.assertIn("names=[]", was)
        # And it shows why moving the row to `searched=` was NOT on its own
        # enough: the lenient walk reports a healthy-looking count next to an
        # empty list. The walk itself had to start refusing.
        self.assertIn("searched=", was)

        _, parsed = run_leg(build, unreal_module=blind)
        now = _by_id(parsed)["boom_component_exists"].detail
        self.assertIn("SUBOBJECT_NAMES_UNREADABLE", now)
        genuine = _by_id(run_leg(LEGS["empty"])[1])["boom_component_exists"].detail
        for sub in self._empty_substrings():
            self.assertIn(sub, genuine)
            self.assertNotIn(sub, now)


class TestDeadGateAudit(unittest.TestCase):
    """Every asserted scalar must differ from the UE 5.8 constructor default.

    A check an untouched, freshly-added boom already satisfies grades nothing.
    The defaults are ``SpringArmComponent.cpp:18-46`` and
    ``CameraComponent.cpp:94``; the source row's own ``CameraLagSpeed == 10``
    IS the default, which is why this task asks for something else.
    """

    def test_no_graded_scalar_is_the_engine_default(self):
        self.assertNotEqual(MOD.EXPECTED_ARM_LENGTH, 300.0)
        self.assertNotEqual(tuple(MOD.EXPECTED_SOCKET_OFFSET), (0.0, 0.0, 0.0))
        self.assertNotEqual(MOD.EXPECTED_LAG_SPEED, 10.0)

    def test_no_tolerance_swallows_the_gap_to_the_default(self):
        self.assertLess(MOD.ARM_LENGTH_TOL, abs(MOD.EXPECTED_ARM_LENGTH - 300.0))
        self.assertLess(MOD.LAG_SPEED_TOL, abs(MOD.EXPECTED_LAG_SPEED - 10.0))
        self.assertLess(MOD.SOCKET_OFFSET_TOL,
                        max(abs(v) for v in MOD.EXPECTED_SOCKET_OFFSET))

    def test_the_fake_reference_matches_the_documented_reference(self):
        # notes.md section 2 is the .uasset authoring spec. If a constant is
        # re-cut and this test goes red, that spec is now wrong on disk.
        self.assertEqual(MOD.EXPECTED_ARM_LENGTH, 400.0)
        self.assertEqual(tuple(MOD.EXPECTED_SOCKET_OFFSET), (0.0, 0.0, 75.0))
        self.assertEqual(MOD.EXPECTED_LAG_SPEED, 4.0)
        self.assertEqual(MOD.BOOM_NAME, "CameraBoom")
        self.assertEqual(MOD.CAMERA_NAME, "FollowCamera")
        self.assertIn("CapsuleComponent", MOD.ROOT_BODY_NAMES)


class TestFailsClosed(unittest.TestCase):
    """No check may pass because a probe merely did not raise."""

    def test_attach_parent_rejects_a_component_merely_named_capsulecomponent(self):
        # Anti-gaming: a bare SceneComponent renamed "CapsuleComponent" must
        # not satisfy "hangs off the character's own body".
        _, parsed = run_leg(lambda: _scout(boom=_boom_component(),
                                           camera=_camera_component(),
                                           capsule_cls=SceneComponent))
        got = _by_id(parsed)["boom_attached_to_character_root"]
        self.assertFalse(got.passed)
        self.assertIn("BOOM_ATTACH_PARENT_WRONG parent=", got.detail)
        self.assertIn("name_ok=True", got.detail)     # the name DID match ...
        self.assertIn("capsule=False", got.detail)    # ... and it still fails

    def test_attach_parent_rejects_a_submission_authored_capsule(self):
        # Right name, right type, AND the actor's root - but authored on this
        # asset rather than inherited from the walking-character base. The
        # root flag is forced True on purpose so the inherited/native gate is
        # the ONLY thing that can reject this; with root=False the corroborating
        # is_root gate would mask a broken authorship gate.
        _, parsed = run_leg(lambda: _scout(boom=_boom_component(),
                                           camera=_camera_component(),
                                           capsule_authored=True,
                                           capsule_root=True))
        got = _by_id(parsed)["boom_attached_to_character_root"]
        self.assertFalse(got.passed)
        self.assertIn("name_ok=True", got.detail)
        self.assertIn("capsule=True", got.detail)
        self.assertIn("is_root=True", got.detail)
        self.assertIn("inherited=False", got.detail)
        self.assertIn("native=False", got.detail)

    def test_attach_parent_rejects_a_parent_that_is_not_the_actor_root(self):
        # The is_root corroboration gates whenever it reads back.
        _, parsed = run_leg(lambda: _scout(boom=_boom_component(),
                                           camera=_camera_component(),
                                           capsule_root=False))
        got = _by_id(parsed)["boom_attached_to_character_root"]
        self.assertFalse(got.passed)
        self.assertIn("is_root=False", got.detail)

    def test_a_boom_with_no_resolvable_parent_fails(self):
        _, parsed = run_leg(lambda: _scout(boom=_boom_component(),
                                           boom_parent=None,
                                           camera=_camera_component()))
        got = _by_id(parsed)["boom_attached_to_character_root"]
        self.assertFalse(got.passed)
        self.assertIn("no_resolvable_parent_handle", got.detail)

    def test_an_unreadable_authorship_probe_is_an_error_not_an_inherited_rig(self):
        # BOOM_NOT_AUTHORED_ON_ASSET is a credited matrix substring; an absent
        # accessor must carry a DIFFERENT token.
        no_probe = _lib_without("is_inherited_component")
        _, parsed = run_leg(lambda: _scout(boom=_boom_component(),
                                           camera=_camera_component()),
                            unreal_module=no_probe)
        got = _by_id(parsed)["boom_authored_on_this_asset"]
        self.assertFalse(got.passed)
        self.assertIn("BOOM_AUTHORSHIP_READ_ERROR", got.detail)
        self.assertNotIn("BOOM_NOT_AUTHORED_ON_ASSET", got.detail)

    def test_a_decoy_second_boom_cannot_satisfy_the_camera_attachment(self):
        # Two components named CameraBoom; the camera rides the WRONG one. The
        # object-identity comparison is what catches this.
        def build():
            decoy = SubobjectData(
                "CameraBoom",
                _boom_component(path=SCOUT + "_C:SpringArm_DECOY"),
                parent=None)
            _scout(boom=_boom_component(), camera=_camera_component(),
                   extra=(decoy,), camera_parent=decoy)
        _, parsed = run_leg(build)
        got = _by_id(parsed)["camera_attached_to_boom"]
        self.assertFalse(got.passed)
        self.assertIn("CAMERA_ATTACH_PARENT_WRONG parent=", got.detail)
        self.assertIn("name_ok=True", got.detail)      # named CameraBoom ...
        self.assertIn("boom_type=True", got.detail)    # ... and a real boom ...
        self.assertIn("boom_identity=different", got.detail)  # ... but not THE one

    def test_an_empty_subobject_walk_cannot_pass_the_negative_camera_check(self):
        # camera_off_control_rotation is the one check whose PASSING state is a
        # bool reading False, so an empty walk used to hand it a free pass.
        def build():
            _scout(boom=_boom_component(), camera=_camera_component())
            WORLD.gather_empty = True
        _, parsed = run_leg(build)
        by_id = _by_id(parsed)
        self.assertFalse(by_id["camera_off_control_rotation"].passed)
        self.assertIn("CAMERA_WALK_ERROR raised",
                      by_id["camera_off_control_rotation"].detail)
        self.assertIn("BOOM_WALK_ERROR raised",
                      by_id["boom_component_exists"].detail)
        self.assertNotIn("BOOM_COMPONENT_MISSING",
                         by_id["boom_component_exists"].detail)
        # only the asset + compile checks survive an unreadable walk
        self.assertEqual(sorted(c.id for c in parsed.checks if c.passed),
                         ["character_asset_exists",
                          "character_compiles_up_to_date"])

    def test_a_nameless_subobject_walk_is_an_error_not_an_absent_boom(self):
        """Everything downstream of the walk is a NAME lookup.

        If ``GetVariableName`` and the object-name fallback both break, the
        walk yields no names and every pre-declared component reads as absent -
        printing the empty leg's CREDITED token off an API break. The walk must
        refuse instead, with a token no matrix row claims.
        """
        blind = _unreal_without("SubobjectDataBlueprintFunctionLibrary")
        blind.SubobjectDataBlueprintFunctionLibrary = types.SimpleNamespace(
            get_data=_SubobjectLib.get_data,
            is_handle_valid=_SubobjectLib.is_handle_valid,
            get_parent_handle=_SubobjectLib.get_parent_handle,
            is_inherited_component=_SubobjectLib.is_inherited_component,
            is_native_component=_SubobjectLib.is_native_component,
            is_root_component=_SubobjectLib.is_root_component,
            get_variable_name=lambda data: "",
            get_object=lambda data: None)
        _, parsed = run_leg(lambda: _scout(boom=_boom_component(),
                                           camera=_camera_component()),
                            unreal_module=blind)
        got = _by_id(parsed)["boom_component_exists"]
        self.assertFalse(got.passed)
        self.assertIn("SUBOBJECT_NAMES_UNREADABLE", got.detail)
        rows = parse_matrix(MATRIX_PATH.read_text(encoding="utf-8"))
        for sub in rows["empty"].substrings:
            self.assertNotIn(sub, got.detail)

    def test_an_unreadable_camera_flag_is_an_error_not_off(self):
        def build():
            camera = _camera_component()
            camera.unreadable.add("use_pawn_control_rotation")
            _scout(boom=_boom_component(), camera=camera)
        _, parsed = run_leg(build)
        got = _by_id(parsed)["camera_off_control_rotation"]
        self.assertFalse(got.passed)
        self.assertIn("CAMERA_CONTROL_ROTATION_READ_ERROR", got.detail)
        self.assertNotIn("CAMERA_CONTROL_ROTATION_OK", got.detail)

    def test_a_non_camera_named_followcamera_is_not_a_viewpoint(self):
        _, parsed = run_leg(lambda: _scout(
            boom=_boom_component(),
            camera=_camera_component(cls=SceneComponent)))
        by_id = _by_id(parsed)
        self.assertFalse(by_id["camera_component_exists"].passed)
        self.assertIn("CAMERA_NOT_A_VIEWPOINT class=SceneComponent",
                      by_id["camera_component_exists"].detail)
        for cid in ("camera_attached_to_boom", "camera_off_control_rotation"):
            self.assertFalse(by_id[cid].passed, cid)

    def test_an_asset_probe_that_raises_is_not_the_absent_asset(self):
        # CHARACTER_ASSET_MISSING is a root-cause token; a broken registry must
        # carry a different one so an API break is never a graded failure.
        def build():
            WORLD.exists_raises = True
        _, parsed = run_leg(build)
        got = _by_id(parsed)["character_asset_exists"]
        self.assertFalse(got.passed)
        self.assertEqual(parsed.passed_count, 0)
        self.assertIn("CHARACTER_ASSET_PROBE_ERROR", got.detail)
        self.assertNotIn(MOD.ASSET_MISSING_TOKEN, got.detail)

    def test_an_unexposed_spring_arm_type_is_a_probe_error_not_the_impostor(self):
        """An unexposed type FAILS CLOSED under a DISTINCT token.

        ``BOOM_NOT_SPRING_ARM class=`` is the ``boom-is-a-plain-scene-
        component`` row's credited substring, so an API break printing it
        would be scored as that variant's named failure. The tristate routes
        "the build does not expose this type" to ``*_TYPE_PROBE_ERROR``
        instead — same red verdict, different (uncreditable) root cause.
        """
        no_type = _unreal_without("SpringArmComponent")
        _, parsed = run_leg(lambda: _scout(boom=_boom_component(),
                                           camera=_camera_component()),
                            unreal_module=no_type)
        by_id = _by_id(parsed)
        self.assertFalse(by_id["boom_is_spring_arm"].passed)
        self.assertIn("BOOM_TYPE_PROBE_ERROR",
                      by_id["boom_is_spring_arm"].detail)
        self.assertNotIn("BOOM_NOT_SPRING_ARM",
                         by_id["boom_is_spring_arm"].detail)
        # the camera-attach check consults the same type and must carry the
        # probe-error token too, not CAMERA_ATTACH_PARENT_WRONG
        self.assertFalse(by_id["camera_attached_to_boom"].passed)
        self.assertIn("CAMERA_ATTACH_TYPE_PROBE_ERROR",
                      by_id["camera_attached_to_boom"].detail)
        self.assertNotIn("CAMERA_ATTACH_PARENT_WRONG",
                         by_id["camera_attached_to_boom"].detail)
        # and the reference itself goes red, which is the audible signal
        self.assertLess(parsed.passed_count, TOTAL_CHECKS)

    def test_an_uncompiled_asset_fails_the_compile_check_only(self):
        _, parsed = run_leg(lambda: _scout(boom=_boom_component(),
                                           camera=_camera_component(),
                                           status="BlueprintStatus.BS_DIRTY"))
        got = _by_id(parsed)["character_compiles_up_to_date"]
        self.assertFalse(got.passed)
        self.assertIn("CHARACTER_NOT_UP_TO_DATE status=", got.detail)
        self.assertEqual(parsed.passed_count, TOTAL_CHECKS - 1)

    def test_socket_offset_is_not_satisfied_by_target_offset(self):
        # notes.md step 5: the row's "offset up by 75" is at the far END of the
        # arm. A submission that set TargetOffset instead must fail, and the
        # detail must say what it did set so the failure is diagnosable.
        def build():
            boom = _boom_component(socket=(0.0, 0.0, 0.0))
            boom._props["target_offset"] = Vector(0.0, 0.0, 75.0)
            _scout(boom=boom, camera=_camera_component())
        _, parsed = run_leg(build)
        got = _by_id(parsed)["boom_socket_offset_up_75"]
        self.assertFalse(got.passed)
        self.assertIn("BOOM_SOCKET_OFFSET_WRONG value=", got.detail)
        self.assertIn("target_offset=(0.0, 0.0, 75.0)", got.detail)


class TestErrorTokensAreDisjointFromMatrix(unittest.TestCase):
    """An API break must never be creditable as a variant's named failure."""

    def _error_tokens(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        return sorted({t for t in re.findall(r"\b[A-Z][A-Z0-9_]{6,}\b", source)
                       if t.endswith(("_ERROR", "_ABORTED", "_UNAVAILABLE",
                                      "_EMPTY", "_NOT_EVALUATED",
                                      "_UNREADABLE"))})

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
                self.assertIn("CHARACTER_ASSET_PROBE_ERROR", chk.detail)
                for sub in subs:
                    self.assertNotIn(sub, chk.detail)
        finally:
            MOD.unreal = FakeUnreal


if __name__ == "__main__":
    unittest.main()

"""Offline oracle for the t2-weapon-held-in-right-hand L2I grader.

No editor, no UE install, no tokens. A minimal fake ``unreal`` module models
the reflection surface the introspect script actually uses - including the
ONE surface that needs a live world (``EditorActorSubsystem`` +
``GetAttachSocketName`` on a constructed instance) - so every leg of
``discrimination/MATRIX.md`` can be simulated and joined against the REAL
``discriminate.parse_matrix`` + the REAL ``layers/l2_introspect`` parser.

What this pins:
  * every negative leg's MATRIX substring is a literal the script PRINTS, on
    the check the matrix blames;
  * the attach-parent check is not name-only (a component the submission
    merely NAMED ``Mesh`` must not satisfy anti-gaming note #3);
  * a dead transient spawn FAILS the socket check with its own distinct token
    rather than skipping it or passing it - the failure mode `notes.md` section
    5 is written against;
  * an empty subobject walk cannot hand any check a free pass;
  * the denominator is a constant 10 on every leg, including no-``unreal``.

The fake is deliberately dumb: it models names, classes, subobject parentage,
the inherited/native flags, socket records and what a constructed instance
would report. It cannot prove the UE API names are right - only a live editor
does that - but it does prove the grader's LOGIC and its printed tokens.
"""
import contextlib
import importlib.util
import io
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

TASK_DIR = _REPO / "tasks" / "bp" / "t2-weapon-held-in-right-hand"
MATRIX_PATH = TASK_DIR / "discrimination" / "MATRIX.md"
SCRIPT_PATH = _VERIFY / "introspect" / "weapon_held_in_right_hand.py"

EXPECTED_TOTAL = 10


def _load_script():
    spec = importlib.util.spec_from_file_location("_weapon_introspect", SCRIPT_PATH)
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


class Vector:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = float(x), float(y), float(z)


class Rotator:
    def __init__(self, roll=0.0, pitch=0.0, yaw=0.0):
        self.roll, self.pitch, self.yaw = float(roll), float(pitch), float(yaw)


class SkeletalMeshSocket(_UObject):
    pass


class StaticMesh(_UObject):
    pass


class SkeletalMesh(_UObject):
    """Models USkeletalMesh::FindSocket (mesh sockets, then the skeleton's)."""

    def __init__(self, name, path, sockets=None, find_raises=False):
        _UObject.__init__(self, name, path)
        self.sockets = dict(sockets or {})
        self.find_raises = find_raises

    def find_socket(self, socket_name):
        if self.find_raises:
            raise Exception("FindSocket unavailable")
        return self.sockets.get(str(socket_name))


class Actor(_UObject):
    def __init__(self, name, path=None, components=(), **props):
        _UObject.__init__(self, name, path, **props)
        self._components = list(components)

    def get_components_by_class(self, cls):
        return [c for c in self._components if isinstance(c, cls)]


class SceneComponent(_UObject):
    def get_attach_parent(self):
        return self._props.get("_attach_parent")

    def get_attach_socket_name(self):
        # UE hands back an FName; str(NAME_None) is "None".
        return self._props.get("_attach_socket", "None")


class StaticMeshComponent(SceneComponent):
    pass


class SkeletalMeshComponent(SceneComponent):
    def get_skeletal_mesh_asset(self):
        return self._props.get("_skeletal_mesh_asset")


class SubobjectDataHandle:
    def __init__(self, data):
        self.data = data


class SubobjectData:
    def __init__(self, var_name, obj, parent=None, inherited=False, native=False,
                 socket=None):
        self.var_name = var_name
        self.obj = obj
        self.parent = parent
        self.inherited = inherited
        self.native = native
        self.socket = socket  # the SCS node's AttachToName

    @property
    def handle(self):
        return SubobjectDataHandle(self)


class SubobjectDataSubsystem:
    pass


class EditorActorSubsystem:
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
    """One simulated project state."""

    def __init__(self):
        self.assets = {}          # path -> Blueprint | SkeletalMesh
        self.classes = {}         # path -> True when load_blueprint_class resolves
        self.tags = {}
        self.gather_empty = False
        self.spawn_mode = "ok"    # "ok" | "subsystem-missing" | "spawn-none" | "raise"
        self.spawned = []
        self.destroyed = []


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
        return _Class(path + "_C") if WORLD.classes.get(path) else None

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


class _EditorActorSubsystem:
    """Models the ONE live-world surface: construct the class, then destroy it.

    Construction mirrors ``USCS_Node::ExecuteNodeOnActor`` closely enough for
    the graded fact: each component subobject becomes an instance component
    whose ``AttachSocketName`` is the SCS node's ``AttachToName``.
    """

    @staticmethod
    def spawn_actor_from_class(cls, location, rotation, transient=False):
        if WORLD.spawn_mode == "raise":
            raise Exception("spawn refused under this RHI")
        if WORLD.spawn_mode == "spawn-none":
            return None
        path = cls.get_name()[:-2]
        bp = WORLD.assets.get(path)
        comps = []
        for data in getattr(bp, "subobjects", []):
            if data.obj is None:
                continue
            comps.append(type(data.obj)(
                data.var_name,
                path="%s_inst:%s" % (path, data.var_name),
                _attach_socket=("None" if data.socket is None else data.socket),
                _attach_parent=None,
            ))
        actor = Actor("%s_inst" % path, path=path + "_inst", components=comps)
        WORLD.spawned.append(actor)
        return actor

    @staticmethod
    def destroy_actor(actor):
        WORLD.destroyed.append(actor)
        return True


class FakeUnreal:
    EditorAssetLibrary = _EditorAssetLibrary
    SubobjectDataBlueprintFunctionLibrary = _SubobjectLib
    SubobjectDataHandle = SubobjectDataHandle
    SubobjectDataSubsystem = SubobjectDataSubsystem
    EditorActorSubsystem = EditorActorSubsystem
    SceneComponent = SceneComponent
    SkeletalMeshComponent = SkeletalMeshComponent
    StaticMeshComponent = StaticMeshComponent
    Vector = Vector
    Rotator = Rotator

    @staticmethod
    def get_engine_subsystem(cls):
        return _Subsystem

    @staticmethod
    def get_editor_subsystem(cls):
        if WORLD.spawn_mode == "subsystem-missing":
            return None
        return _EditorActorSubsystem

    @staticmethod
    def log(msg):
        pass


# --------------------------------------------------------------------------- #
# leg builders                                                                 #
# --------------------------------------------------------------------------- #

MOD = _load_script()
MESH = MOD.ASSET_MESH
CHAR = MOD.ASSET_CHAR
CUBE = MOD.CUBE_PATH


def _mesh_asset(*, socket_bone="hand_r", has_socket=True,
                loc=(0.0, 0.0, 0.0), rot=(0.0, 0.0, 0.0), bone_unreadable=False,
                loc_unreadable=False, find_raises=False):
    sockets = {}
    if has_socket:
        props = {}
        if not bone_unreadable:
            props["bone_name"] = socket_bone
        props["socket_name"] = MOD.SOCKET_NAME
        if not loc_unreadable:
            props["relative_location"] = Vector(*loc)
            props["relative_rotation"] = Rotator(*rot)
        sockets[MOD.SOCKET_NAME] = SkeletalMeshSocket(
            MOD.SOCKET_NAME, path="%s:%s" % (MESH, MOD.SOCKET_NAME), **props)
    WORLD.assets[MESH] = SkeletalMesh("SKM_EvalChar", MESH, sockets=sockets,
                                      find_raises=find_raises)
    return WORLD.assets[MESH]


def _char_bp(*, weapon="cube", attach="mesh", socket=MOD.SOCKET_NAME,
             mesh_asset_path=MESH, status="BlueprintStatus.BS_UP_TO_DATE"):
    """Build BP_EvalChar.

    ``attach`` selects the Weapon's parent subobject: "mesh" (the real
    inherited CharacterMesh0), "root", "impostor-static" (an SCS
    StaticMeshComponent the agent named Mesh) or "impostor-skeletal" (an SCS
    SkeletalMeshComponent the agent named Mesh).
    ``weapon``: "cube" | "nomesh" | "scene" (a non-static-mesh part) | None.
    """
    rendered = SkeletalMesh("rendered", mesh_asset_path)
    mesh_obj = SkeletalMeshComponent("CharacterMesh0",
                                     path=CHAR + "_C:CharacterMesh0",
                                     _skeletal_mesh_asset=rendered)
    root = SubobjectData("CapsuleComponent", SceneComponent("CapsuleComponent"),
                         native=True, inherited=True)
    inherited_mesh = SubobjectData("CharacterMesh0", mesh_obj, parent=root,
                                   native=True, inherited=True)
    subs = [root, inherited_mesh]

    parents = {"mesh": inherited_mesh, "root": root}
    if attach == "impostor-static":
        parents[attach] = SubobjectData(
            "Mesh",
            StaticMeshComponent("Mesh", path=CHAR + "_C:StaticMeshComponent_0"),
            parent=root)
        subs.append(parents[attach])
    elif attach == "impostor-skeletal":
        parents[attach] = SubobjectData(
            "Mesh",
            SkeletalMeshComponent("Mesh", path=CHAR + "_C:SkeletalMeshComponent_0"),
            parent=root)
        subs.append(parents[attach])

    if weapon is not None:
        if weapon == "cube":
            obj = StaticMeshComponent("Weapon", path=CHAR + "_C:Weapon",
                                      static_mesh=StaticMesh("Cube", CUBE + ".Cube"))
        elif weapon == "nomesh":
            obj = StaticMeshComponent("Weapon", path=CHAR + "_C:Weapon",
                                      static_mesh=None)
        else:  # a scene component that is not a static-mesh part
            obj = SceneComponent("Weapon", path=CHAR + "_C:Weapon",
                                 static_mesh=None)
        subs.append(SubobjectData("Weapon", obj, parent=parents[attach],
                                  socket=socket))

    WORLD.assets[CHAR] = Blueprint("BP_EvalChar", CHAR, subs, status=status)
    WORLD.classes[CHAR] = True
    WORLD.tags[CHAR] = {"ParentClass": "Character", "NativeParentClass": "Character"}


LEGS = {}


def _leg(name):
    def deco(fn):
        LEGS[name] = fn
        return fn
    return deco


@_leg("reference")
def _reference():
    _mesh_asset()
    _char_bp()


@_leg("empty")
def _empty():
    # The substrate ships all three baselines; nothing is done to them.
    _mesh_asset(has_socket=False)
    _char_bp(weapon=None)


@_leg("socket-on-wrong-bone")
def _socket_on_wrong_bone():
    _mesh_asset(socket_bone="hand_l")
    _char_bp()


@_leg("weapon-on-capsule-root")
def _weapon_on_capsule_root():
    _mesh_asset()
    _char_bp(attach="root", socket=None)


@_leg("weapon-on-mesh-no-socket")
def _weapon_on_mesh_no_socket():
    _mesh_asset()
    _char_bp(socket=None)


@_leg("bone-name-instead-of-socket")
def _bone_name_instead_of_socket():
    _mesh_asset(has_socket=False)
    _char_bp(socket="hand_r")


@_leg("weapon-without-cube-mesh")
def _weapon_without_cube_mesh():
    _mesh_asset()
    _char_bp(weapon="nomesh")


def run_leg(builder):
    """Run the introspect script against a freshly built world; return checks."""
    global WORLD
    WORLD = _World()
    MOD.unreal = FakeUnreal
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

    def test_no_negative_leg_has_a_blank_substring_tuple(self):
        blank = sorted(k for k, v in self.rows.items()
                       if not v.expect_pass and not v.substrings)
        self.assertEqual(blank, [], "these legs can never be credited")

    def test_no_substring_carries_backticks(self):
        for label, row in self.rows.items():
            for s in row.substrings:
                self.assertNotIn("`", s, "%s: backticks never match log text" % label)

    def test_reference_leg_passes_all_ten(self):
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
                self.assertLess(parsed.passed_count, EXPECTED_TOTAL, "expected a FAIL")
                details = "\n".join(c.detail for c in parsed.checks if not c.passed)
                for sub in row.substrings:
                    self.assertIn(sub, details,
                                  "%s: MATRIX substring never printed" % label)

    def test_named_substring_lands_on_the_predicted_check(self):
        """The substring must appear on the check the MATRIX blames, not just
        somewhere in the verdict."""
        expected = {
            "empty": "weapon_socket_exists",
            "socket-on-wrong-bone": "weapon_socket_on_hand_r",
            "weapon-on-capsule-root": "weapon_attach_parent_is_character_mesh",
            "weapon-on-mesh-no-socket": "weapon_attach_socket_is_weapon_socket",
            "bone-name-instead-of-socket": "weapon_attach_socket_is_weapon_socket",
            "weapon-without-cube-mesh": "weapon_shows_engine_cube",
        }
        self.assertEqual(set(expected) | {"reference"}, set(self.rows))
        for label, check_id in expected.items():
            with self.subTest(leg=label):
                _, parsed = run_leg(LEGS[label])
                got = _by_id(parsed)[check_id]
                self.assertFalse(got.passed)
                for sub in self.rows[label].substrings:
                    self.assertIn(sub, got.detail)

    def test_each_variant_fails_only_the_checks_the_matrix_predicts(self):
        """A variant that differs in two ways cannot prove which gate caught it."""
        expected_failures = {
            "socket-on-wrong-bone": {"weapon_socket_on_hand_r"},
            "weapon-on-capsule-root": {"weapon_attach_parent_is_character_mesh",
                                       "weapon_attach_socket_is_weapon_socket"},
            "weapon-on-mesh-no-socket": {"weapon_attach_socket_is_weapon_socket"},
            "bone-name-instead-of-socket": {"weapon_socket_exists",
                                            "weapon_socket_on_hand_r",
                                            "weapon_socket_offset_is_identity",
                                            "weapon_attach_socket_is_weapon_socket"},
            "weapon-without-cube-mesh": {"weapon_shows_engine_cube"},
        }
        for label, expect in expected_failures.items():
            with self.subTest(leg=label):
                _, parsed = run_leg(LEGS[label])
                got = {c.id for c in parsed.checks if not c.passed}
                self.assertEqual(got, expect)

    def test_empty_leg_scores_two_of_ten(self):
        """Documented in the spec + MATRIX: the baseline itself is intact."""
        _, parsed = run_leg(LEGS["empty"])
        passing = {c.id for c in parsed.checks if c.passed}
        self.assertEqual(passing, {"char_mesh_uses_task_skeletal_mesh",
                                   "char_bp_compiles_up_to_date"})


class TestFailsClosed(unittest.TestCase):
    """No check may pass because a probe merely did not raise or came back empty."""

    def test_attach_parent_rejects_a_component_merely_named_mesh(self):
        _, parsed = run_leg(lambda: (_mesh_asset(),
                                     _char_bp(attach="impostor-static")))
        got = _by_id(parsed)["weapon_attach_parent_is_character_mesh"]
        self.assertFalse(got.passed)
        self.assertIn("WEAPON_ATTACH_PARENT_WRONG parent=", got.detail)
        self.assertIn("name_ok=True", got.detail)      # the name DID match ...
        self.assertIn("skeletal=False", got.detail)    # ... and it still fails

    def test_attach_parent_rejects_a_submission_authored_skeletal_mesh(self):
        _, parsed = run_leg(lambda: (_mesh_asset(),
                                     _char_bp(attach="impostor-skeletal")))
        got = _by_id(parsed)["weapon_attach_parent_is_character_mesh"]
        self.assertFalse(got.passed)
        self.assertIn("name_ok=True", got.detail)
        self.assertIn("skeletal=True", got.detail)
        self.assertIn("inherited=False", got.detail)

    def test_weapon_that_is_not_a_static_mesh_part_is_rejected(self):
        _, parsed = run_leg(lambda: (_mesh_asset(), _char_bp(weapon="scene")))
        got = _by_id(parsed)["weapon_is_static_mesh_component"]
        self.assertFalse(got.passed)
        self.assertIn("WEAPON_NOT_STATIC_MESH class=", got.detail)

    def test_empty_subobject_walk_fails_every_walk_backed_check(self):
        def build():
            _mesh_asset()
            _char_bp()
            WORLD.gather_empty = True
        _, parsed = run_leg(build)
        by_id = _by_id(parsed)
        for cid in ("char_mesh_uses_task_skeletal_mesh",
                    "char_has_weapon_component",
                    "weapon_is_static_mesh_component",
                    "weapon_shows_engine_cube",
                    "weapon_attach_parent_is_character_mesh",
                    "weapon_attach_socket_is_weapon_socket"):
            self.assertFalse(by_id[cid].passed, cid)
        self.assertIn("WALK_ERROR", by_id["char_has_weapon_component"].detail)

    def test_unreadable_socket_transform_is_not_scored_as_identity(self):
        _, parsed = run_leg(lambda: (_mesh_asset(loc_unreadable=True), _char_bp()))
        got = _by_id(parsed)["weapon_socket_offset_is_identity"]
        self.assertFalse(got.passed)
        self.assertIn("WEAPONSOCKET_OFFSET_READ_ERROR", got.detail)

    def test_nonzero_socket_offset_fails(self):
        """The low-discrimination check still has to work when it fires."""
        _, parsed = run_leg(lambda: (_mesh_asset(loc=(0.0, 0.0, 5.0)), _char_bp()))
        got = _by_id(parsed)["weapon_socket_offset_is_identity"]
        self.assertFalse(got.passed)
        self.assertIn("WEAPONSOCKET_OFFSET_NOT_IDENTITY loc=", got.detail)

    def test_find_socket_raising_is_not_scored_as_a_named_failure(self):
        _, parsed = run_leg(lambda: (_mesh_asset(find_raises=True), _char_bp()))
        got = _by_id(parsed)["weapon_socket_exists"]
        self.assertFalse(got.passed)
        self.assertIn("WEAPONSOCKET_FIND_ERROR", got.detail)
        self.assertNotIn("WEAPONSOCKET_NOT_FOUND", got.detail)

    def test_mesh_swapped_out_from_under_the_socket_is_caught(self):
        _, parsed = run_leg(lambda: (
            _mesh_asset(),
            _char_bp(mesh_asset_path="/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple")))
        got = _by_id(parsed)["char_mesh_uses_task_skeletal_mesh"]
        self.assertFalse(got.passed)
        self.assertIn("CHAR_MESH_ASSET_WRONG asset=", got.detail)

    def test_missing_char_asset_fans_out_without_reusing_a_matrix_token(self):
        def build():
            _mesh_asset()
            # BP_EvalChar deleted by the submission.
        _, parsed = run_leg(build)
        self.assertEqual(parsed.total, EXPECTED_TOTAL)
        by_id = _by_id(parsed)
        for cid in MOD.CHAR_CHECK_IDS:
            self.assertFalse(by_id[cid].passed, cid)
            self.assertIn("CHAR_ASSET_MISSING", by_id[cid].detail)


class TestTheOneCheckThatNeedsAWorld(unittest.TestCase):
    """`notes.md` section 5's calibration item, pinned as behaviour.

    The transient spawn is the one route engine source cannot settle. These
    tests fix what the grader must do when it does NOT work: fail with a
    distinct, uncreditable token - never skip, never pass.
    """

    def test_missing_subsystem_fails_the_check_with_its_own_token(self):
        def build():
            _mesh_asset()
            _char_bp()
            WORLD.spawn_mode = "subsystem-missing"
        _, parsed = run_leg(build)
        got = _by_id(parsed)["weapon_attach_socket_is_weapon_socket"]
        self.assertFalse(got.passed)
        self.assertIn("WEAPON_SPAWN_UNAVAILABLE", got.detail)
        self.assertNotIn("WEAPON_ATTACH_SOCKET_WRONG", got.detail)

    def test_spawn_returning_none_fails_the_check(self):
        def build():
            _mesh_asset()
            _char_bp()
            WORLD.spawn_mode = "spawn-none"
        _, parsed = run_leg(build)
        got = _by_id(parsed)["weapon_attach_socket_is_weapon_socket"]
        self.assertFalse(got.passed)
        self.assertIn("WEAPON_SPAWN_FAILED", got.detail)

    def test_spawn_raising_fails_the_check(self):
        def build():
            _mesh_asset()
            _char_bp()
            WORLD.spawn_mode = "raise"
        _, parsed = run_leg(build)
        got = _by_id(parsed)["weapon_attach_socket_is_weapon_socket"]
        self.assertFalse(got.passed)
        self.assertIn("WEAPON_ATTACH_SOCKET_READ_ERROR", got.detail)

    def test_the_probe_actor_is_always_destroyed(self):
        for label in ("reference", "weapon-on-mesh-no-socket"):
            with self.subTest(leg=label):
                run_leg(LEGS[label])
                self.assertEqual(len(WORLD.spawned), 1)
                self.assertEqual(WORLD.destroyed, WORLD.spawned)


class TestErrorTokensAreDisjointFromMatrix(unittest.TestCase):
    """An API break must never be creditable as a variant's named failure."""

    def test_no_error_token_appears_in_any_matrix_substring(self):
        rows = parse_matrix(MATRIX_PATH.read_text(encoding="utf-8"))
        subs = [s for r in rows.values() for s in r.substrings]
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        tokens = sorted({t for t in re.findall(r"\b[A-Z][A-Z0-9_]{6,}\b", source)
                         if t.endswith(("_ERROR", "_ABORTED", "_UNAVAILABLE",
                                        "_EMPTY", "_FAILED", "_NOT_EVALUATED"))})
        self.assertTrue(tokens, "expected the script to define error tokens")
        for token in tokens:
            for sub in subs:
                self.assertNotIn(token, sub)

    def test_script_is_pure_ascii(self):
        raw = SCRIPT_PATH.read_bytes()
        self.assertEqual(raw.decode("utf-8"), raw.decode("ascii"))

    def test_script_carries_no_automation_result_marker(self):
        """parse_automation_log's whole-file finditer counts these as TESTS."""
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertNotIn("TestResult=Passed", source)
        self.assertNotIn("Automation Test Succeeded", source)

    def test_offline_run_without_unreal_fails_every_check(self):
        """No editor => 0/10, all error tokens. Never a vacuous PASS."""
        global WORLD
        WORLD = _World()
        MOD.unreal = None
        try:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                MOD.main()
            parsed = parse_introspect_verdict(buf.getvalue())
            self.assertEqual(parsed.total, EXPECTED_TOTAL)
            self.assertEqual(parsed.passed_count, 0)
            payload = json.loads(buf.getvalue().splitlines()[1])
            self.assertEqual(len(payload["checks"]), EXPECTED_TOTAL)
            self.assertEqual([c["id"] for c in payload["checks"]],
                             list(MOD.CHECK_IDS))
        finally:
            MOD.unreal = FakeUnreal


if __name__ == "__main__":
    unittest.main()

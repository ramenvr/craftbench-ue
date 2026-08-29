"""Shared deterministic map authoring for the two-walker avoidance task."""

from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
import unreal


TASK_ID = "t3-both-walkers-yield-and-still-arrive"
FINAL_MAP = "/Game/Maps/%s/L_BothWalkersYield" % TASK_ID
ADMISSION_MAP = "/Game/Maps/%s/L_BothWalkersYieldAdmission" % TASK_ID
FINAL_BP = "/Game/Tasks/%s/BP_YieldingWalker" % TASK_ID
ADMISSION_BP = ("/Game/__CraftBenchAdmission/%s/"
                "BP_YieldingWalker_Admission" % TASK_ID)
TEMPLATE = "/Engine/Maps/Templates/Template_Default"


@dataclass(frozen=True)
class Scenario:
    suffix: str
    origin: tuple[float, float]
    yaw_a: float
    yaw_b: float
    length_a: float
    length_b: float
    speed_a: float
    speed_b: float
    radius_a: float
    radius_b: float
    solo_offset: float


FINAL_SCENARIOS = (
    Scenario("LayoutA", (-2200.0, 0.0), 0.0, 90.0,
             1400.0, 1220.0, 270.0, 235.0, 40.0, 50.0, 1180.0),
    Scenario("LayoutB", (2200.0, 0.0), 25.0, 115.0,
             1560.0, 1320.0, 305.0, 255.0, 36.0, 54.0, 1280.0),
)
ADMISSION_SCENARIOS = (
    Scenario("Admission", (0.0, 0.0), -18.0, 72.0,
             1460.0, 1260.0, 285.0, 230.0, 42.0, 51.0, 1220.0),
)


def fail(message):
    unreal.log_error("WALKER-YIELD-MAP-FAILED: " + message)
    raise RuntimeError(message)


def spawn(actors, cls, location, label, rotation=None):
    value = actors.spawn_actor_from_class(
        cls, location, rotation or unreal.Rotator())
    if value is None:
        fail("spawn failed: " + label)
    value.set_actor_label(label)
    return value


def direction(yaw):
    radians = math.radians(yaw)
    return (math.cos(radians), math.sin(radians))


def add(origin, vector, scale=1.0):
    ox = origin.x if hasattr(origin, "x") else origin[0]
    oy = origin.y if hasattr(origin, "y") else origin[1]
    return unreal.Vector(ox + vector[0] * scale,
                         oy + vector[1] * scale, 96.0)


def perp(vector):
    return (-vector[1], vector[0])


def tags(actor, common, specific):
    actor.set_editor_property(
        "tags", [unreal.Name(common), unreal.Name(specific)])


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def add_goal(actors, mesh, material, location, tag):
    goal = spawn(actors, unreal.StaticMeshActor, location, tag)
    goal.static_mesh_component.set_static_mesh(mesh)
    if material is not None:
        goal.static_mesh_component.set_material(0, material)
    goal.set_actor_scale3d(unreal.Vector(0.25, 0.25, 1.4))
    marker_result = str(
        unreal.WalkerYieldAuthoringLibrary.configure_goal_marker(goal))
    unreal.log("WALKER-YIELD-GOAL-MARKER " + marker_result)
    if (not marker_result.startswith("PASS ") or
            " static_meshes=1 profile=NoCollision collision=0 "
            "nav_affect=0" not in marker_result):
        fail("goal marker configuration failed: " + marker_result)
    tags(goal, "WalkerYieldGoal", tag)
    return goal


def author(mode):
    if mode not in ("admission", "final"):
        fail("unsupported mode: " + mode)
    map_path = ADMISSION_MAP if mode == "admission" else FINAL_MAP
    bp_path = ADMISSION_BP if mode == "admission" else FINAL_BP
    scenarios = ADMISSION_SCENARIOS if mode == "admission" else FINAL_SCENARIOS
    map_file = (Path(unreal.Paths.project_content_dir()) /
                (map_path.removeprefix("/Game/") + ".umap")).resolve()
    if unreal.EditorAssetLibrary.does_asset_exist(map_path) or map_file.exists():
        fail("refusing to overwrite retained map: " + map_path)
    blueprint = unreal.EditorAssetLibrary.load_asset(bp_path)
    if blueprint is None or blueprint.generated_class() is None:
        fail("walker Blueprint missing or uncompiled: " + bp_path)
    walker_class = blueprint.generated_class()
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if not levels.new_level_from_template(map_path, TEMPLATE):
        fail("new_level_from_template failed")
    for actor in list(actors.get_all_level_actors()):
        actors.destroy_actor(actor)
    cube = unreal.EditorAssetLibrary.load_asset("/Engine/BasicShapes/Cube.Cube")
    cone = unreal.EditorAssetLibrary.load_asset("/Engine/BasicShapes/Cone.Cone")
    material = unreal.EditorAssetLibrary.load_asset(
        "/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial")
    if cube is None or cone is None:
        fail("engine shape asset missing")
    floor = spawn(actors, unreal.StaticMeshActor,
                  unreal.Vector(0.0, 0.0, -50.0), "WalkerYieldFloor")
    floor.static_mesh_component.set_static_mesh(cube)
    floor.set_actor_scale3d(unreal.Vector(82.0, 42.0, 1.0))
    floor.static_mesh_component.set_collision_enabled(
        unreal.CollisionEnabled.QUERY_AND_PHYSICS)
    nav = spawn(actors, unreal.NavMeshBoundsVolume,
                unreal.Vector(0.0, 0.0, 300.0), "WalkerYieldNavBounds")
    nav.set_actor_scale3d(unreal.Vector(82.0, 42.0, 8.0))

    fixture_classes = {
        "Admission": unreal.BothWalkersYieldAdmissionFunctionalTest,
        "LayoutA": unreal.BothWalkersYieldLayoutAFunctionalTest,
        "LayoutB": unreal.BothWalkersYieldLayoutBFunctionalTest,
    }
    for index, spec in enumerate(scenarios):
        da = direction(spec.yaw_a)
        db = direction(spec.yaw_b)
        starts = {
            "PairA": add(spec.origin, da, -spec.length_a / 2.0),
            "PairB": add(spec.origin, db, -spec.length_b / 2.0),
            "SoloA": add(add(spec.origin, perp(da), spec.solo_offset),
                         da, -spec.length_a / 2.0),
            "SoloB": add(add(spec.origin, perp(db), -spec.solo_offset),
                         db, -spec.length_b / 2.0),
        }
        goals = {
            "PairA": add(spec.origin, da, spec.length_a / 2.0),
            "PairB": add(spec.origin, db, spec.length_b / 2.0),
            "SoloA": add(add(spec.origin, perp(da), spec.solo_offset),
                         da, spec.length_a / 2.0),
            "SoloB": add(add(spec.origin, perp(db), -spec.solo_offset),
                         db, spec.length_b / 2.0),
        }
        subject_tags = {}
        goal_tags = {}
        for role in ("PairA", "PairB", "SoloA", "SoloB"):
            subject_tag = "WalkerYieldSubject.%s.%s" % (spec.suffix, role)
            goal_tag = "WalkerYieldGoal.%s.%s" % (spec.suffix, role)
            subject = spawn(actors, walker_class, starts[role], subject_tag,
                            unreal.Rotator(0.0,
                                           spec.yaw_a if role.endswith("A")
                                           else spec.yaw_b, 0.0))
            tags(subject, "WalkerYieldSubject", subject_tag)
            add_goal(actors, cone, material, goals[role], goal_tag)
            subject_tags[role] = unreal.Name(subject_tag)
            goal_tags[role] = unreal.Name(goal_tag)
        scenario_tag = "WalkerYieldScenario.%s" % spec.suffix
        scenario = spawn(
            actors, unreal.WalkerYieldScenarioActor,
            unreal.Vector(spec.origin[0], spec.origin[1], 30.0), scenario_tag)
        tags(scenario, "WalkerYieldScenario", scenario_tag)
        scenario.set_editor_property("scenario_id", unreal.Name(spec.suffix))
        scenario.set_editor_property("expected_walker_class", walker_class)
        for role, prop in (("PairA", "pair_a_tag"),
                           ("PairB", "pair_b_tag"),
                           ("SoloA", "solo_a_tag"),
                           ("SoloB", "solo_b_tag")):
            scenario.set_editor_property(prop, subject_tags[role])
        for role, prop in (("PairA", "pair_a_goal_tag"),
                           ("PairB", "pair_b_goal_tag"),
                           ("SoloA", "solo_a_goal_tag"),
                           ("SoloB", "solo_b_goal_tag")):
            scenario.set_editor_property(prop, goal_tags[role])
        scenario.set_editor_property("pair_a_speed", spec.speed_a)
        scenario.set_editor_property("pair_b_speed", spec.speed_b)
        scenario.set_editor_property("pair_a_radius", spec.radius_a)
        scenario.set_editor_property("pair_b_radius", spec.radius_b)
        scenario.set_editor_property("acceptance_radius", 70.0)
        spawn(actors, fixture_classes[spec.suffix],
              unreal.Vector(spec.origin[0] - 300.0,
                            spec.origin[1] - 300.0, 120.0),
              "BothWalkersYield%sFunctionalTest" % spec.suffix)

    spawn(actors, unreal.PlayerStart, unreal.Vector(0.0, -3500.0, 120.0),
          "WalkerYieldPlayerStart")
    spawn(actors, unreal.DirectionalLight, unreal.Vector(0.0, 0.0, 1000.0),
          "WalkerYieldKeyLight", unreal.Rotator(-55.0, -25.0, 0.0))
    spawn(actors, unreal.SkyLight, unreal.Vector(0.0, 0.0, 800.0),
          "WalkerYieldSkyLight")
    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem).get_editor_world()
    nav_result = str(
        unreal.WalkerYieldAuthoringLibrary.build_navigation(world))
    if not nav_result.startswith("PASS "):
        fail("navigation build failed: " + nav_result)
    expected = (len(scenarios), len(scenarios), 4 * len(scenarios),
                4 * len(scenarios))
    contract = str(unreal.WalkerYieldAuthoringLibrary.inspect_world(
        world, *expected))
    if not contract.startswith("PASS "):
        fail("pre-save world contract failed: " + contract)
    if not levels.save_current_level() or not map_file.is_file():
        fail("map save failed: " + map_path)
    unreal.log(
        "WALKER-YIELD-MAP-SAVED mode=%s map=%s sha256=%s scenarios=%d "
        "fixtures=%d walkers=%d goals=%d nav=%s contract=%s" %
        (mode, map_path, sha256(map_file), expected[0], expected[1],
         expected[2], expected[3], nav_result, contract))

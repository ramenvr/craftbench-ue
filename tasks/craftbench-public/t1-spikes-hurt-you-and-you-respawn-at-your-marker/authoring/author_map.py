"""Authors L_SpikeLane for t1-spikes-hurt-you-and-you-respawn-at-your-marker.

    UnrealEditor-Cmd.exe <ThirdPerson.uproject> -run=pythonscript \
        -script="<abs path to this file>" -nullrhi -unattended -nopause \
        -log -stdout -FullStdOutLogOutput

The constants below are the map contract the fixture asserts against.

First map in this set authored under the 2026-08-18 materials rule: floors, stripes
and markers wear the substrate's own MI_PrototypeGrid_* / MI_GlowNT / M_Lava rather
than bare engine grey. Nothing about that can move a verdict -- it is what stops the
level photographing as a grey box.

Every Rotator is built with KEYWORDS -- unreal.Rotator's positional order is
(roll, pitch, yaw).
"""
import unreal

TASK = "t1-spikes-hurt-you-and-you-respawn-at-your-marker"
MAP_PKG = f"/Game/Maps/{TASK}/L_SpikeLane"

# A LONG lane. The first version packed the start mark, the slab, both pads and
# the bystander into 3,200 x 1,400 cm, and the owner's note after playing it was
# that the spike lane is too short -- there is no run-up, no room to be somewhere
# the slab is not, and the two pads are close enough to be one.
FLOOR_MIN = (0.0, -1400.0)
FLOOR_MAX = (7200.0, 1400.0)
STRIPE_EVERY = 200.0
START_MARK = unreal.Vector(300.0, 0.0, 0.0)
PAD1 = unreal.Vector(1100.0, -300.0, 0.0)
PAD2 = unreal.Vector(1900.0, -300.0, 0.0)
SLAB_AT = unreal.Vector(2400.0, 0.0, 100.0)
# THE RAIL, and therefore the spike lane, is 2,000 cm long instead of 600. That is
# what "the lane of spike is too short" was about: the slab used to shuttle across a
# six-metre stretch, which is barely a hazard. The floor is longer too, so there is a
# run-up before it and somewhere to be after it.
#
# The slab still STARTS at 2,400 and the fixture still waits for it at 2,700: those
# two numbers are coupled, and moving the slab without moving the fixture's hold point
# is how a correct reference ended up walking to an empty patch of floor and never
# being hit at all.
POSTS = [(2000.0, 0.0), (4000.0, 0.0)]
# THE BYSTANDER WALKS, and it walks the whole length of the hazard on a lane
# beside it. Parked 200 cm from the slab and never moving, it proved only that a
# submission had not damaged a stationary object -- the owner's note was that it
# 'does not really do anything'. Now it is exercised: anything that hurts by
# radius, by timer, or globally catches it, and the fixture requires it to have
# actually covered ground.
TWIN_AT = unreal.Vector(800.0, 800.0, 96.0)
TWIN_PATROL_TO = unreal.Vector(6400.0, 800.0, 96.0)
LANDMARKS = [(200.0, 1300.0), (7000.0, 1300.0)]

CUBE = "/Engine/BasicShapes/Cube.Cube"
CYL = "/Engine/BasicShapes/Cylinder.Cylinder"
# Substrate materials. All committed content -- no new dependency.
M_FLOOR = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray"
M_STRIPE = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02"
M_MARK = "/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT"
M_POST = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"


def log(msg):
    unreal.log(f"SPIKELANE- {msg}")


def fail(msg):
    unreal.log_error(f"SPIKELANE-ERROR {msg}")
    raise SystemExit(1)


def probe():
    got = {}
    for name, cls in (("les", unreal.LevelEditorSubsystem),
                      ("eas", unreal.EditorActorSubsystem)):
        sub = unreal.get_editor_subsystem(cls)
        if sub is None:
            fail(f"subsystem {cls.__name__} is unavailable in this boot")
        got[name] = sub
    for path in (CUBE, CYL, M_FLOOR, M_STRIPE, M_MARK, M_POST):
        if not unreal.EditorAssetLibrary.does_asset_exist(path):
            fail(f"asset missing: {path}")
    for cls_name in ("SpikeLaneCharacter", "SpikeSlabActor", "LanePadActor",
                     "SpikeLaneCourse", "SpikeLaneGameMode",
                     "SpikeContactRespawnFunctionalTest"):
        if not hasattr(unreal, cls_name):
            fail(f"class {cls_name} is not exposed to python - is the module built?")
        got[cls_name] = getattr(unreal, cls_name)
    log(f"probe OK: {sorted(got)}")
    return got


def block(env, mesh, loc, scale, label, material=None, yaw=0.0):
    actor = env["eas"].spawn_actor_from_class(
        unreal.StaticMeshActor, loc, unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
    if actor is None:
        fail(f"could not spawn {label}")
    actor.set_actor_label(label)
    comp = actor.static_mesh_component
    comp.set_static_mesh(unreal.EditorAssetLibrary.load_asset(mesh))
    comp.set_editor_property("mobility", unreal.ComponentMobility.STATIC)
    if material:
        comp.set_material(0, unreal.EditorAssetLibrary.load_asset(material))
    actor.set_actor_scale3d(scale)
    return actor


def place(env, cls, loc, label, yaw=0.0):
    actor = env["eas"].spawn_actor_from_class(
        cls, loc, unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
    if actor is None:
        fail(f"could not place {label}")
    actor.set_actor_label(label)
    return actor


def main():
    env = probe()
    les, eas = env["les"], env["eas"]

    if unreal.EditorAssetLibrary.does_asset_exist(MAP_PKG):
        fail(f"{MAP_PKG} already exists. Delete the file from the SHELL and re-run.")
    if not les.new_level(MAP_PKG):
        fail(f"new_level({MAP_PKG}) returned False")
    log(f"created {MAP_PKG}")

    span_x = FLOOR_MAX[0] - FLOOR_MIN[0]
    span_y = FLOOR_MAX[1] - FLOOR_MIN[1]
    mid_x = (FLOOR_MAX[0] + FLOOR_MIN[0]) / 2.0
    mid_y = (FLOOR_MAX[1] + FLOOR_MIN[1]) / 2.0
    # ONE solid platform under the whole course: nothing in the run can fall out of
    # the world, including the freedom probes after a respawn.
    block(env, CUBE, unreal.Vector(mid_x, mid_y, -50.0),
          unreal.Vector(span_x / 100.0, span_y / 100.0, 1.0), "Floor", M_FLOOR)

    n = 0
    x = FLOOR_MIN[0] + STRIPE_EVERY
    while x < FLOOR_MAX[0]:
        block(env, CUBE, unreal.Vector(x, mid_y, 1.5),
              unreal.Vector(0.06, span_y / 100.0, 0.03), f"Stripe_{n:02d}", M_STRIPE)
        n += 1
        x += STRIPE_EVERY
    log(f"floor {span_x:.0f}x{span_y:.0f} + {n} stripes")

    mark = block(env, CUBE, unreal.Vector(START_MARK.x, START_MARK.y, 3.0),
                 unreal.Vector(2.0, 2.0, 0.06), "StartMark", M_MARK)
    mark.tags = ["StartMark"]

    p1 = place(env, env["LanePadActor"], PAD1, "LanePad_1")
    p1.set_editor_property("pad_order", 1)
    p2 = place(env, env["LanePadActor"], PAD2, "LanePad_2")
    p2.set_editor_property("pad_order", 2)
    log("start mark + two pads placed (PadOrder 1 and 2)")

    place(env, env["SpikeSlabActor"], SLAB_AT, "SpikeSlab")
    for idx, (px, py) in enumerate(POSTS):
        post = block(env, CYL, unreal.Vector(px, py, 150.0),
                     unreal.Vector(0.6, 0.6, 3.0), f"RailPost_{idx}", M_POST)
        post.tags = ["RailPost"]
    log(f"slab + two rail posts {POSTS[0]} .. {POSTS[1]}")

    place(env, env["SpikeLaneCourse"], unreal.Vector(0.0, 0.0, 0.0), "SpikeLaneCourse")

    twin = place(env, env["SpikeLaneCharacter"], TWIN_AT, "BystanderTwin")
    twin.tags = ["LaneCharacter", "ControlTwin"]
    log("bystander placed with the ControlTwin instance tag")

    start = eas.spawn_actor_from_class(
        unreal.PlayerStart, unreal.Vector(START_MARK.x, START_MARK.y, 100.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if start is None:
        fail("could not place PlayerStart")
    start.set_actor_label("PlayerStart")

    for idx, (lx, ly) in enumerate(LANDMARKS):
        block(env, CYL, unreal.Vector(lx, ly, 300.0),
              unreal.Vector(1.3, 1.3, 6.0), f"Landmark_{idx}", M_POST)

    sun = eas.spawn_actor_from_class(
        unreal.DirectionalLight, unreal.Vector(mid_x, mid_y, 900.0),
        unreal.Rotator(roll=0.0, pitch=-45.0, yaw=-130.0))
    sky = eas.spawn_actor_from_class(
        unreal.SkyLight, unreal.Vector(mid_x, mid_y, 900.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    atmo = eas.spawn_actor_from_class(
        unreal.SkyAtmosphere, unreal.Vector(mid_x, mid_y, 0.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if sun is None or sky is None or atmo is None:
        fail("could not place the lighting rig")
    sun.set_actor_label("DirectionalLight")
    sky.set_actor_label("SkyLight")
    atmo.set_actor_label("SkyAtmosphere")
    log("lighting: DirectionalLight + SkyLight + SkyAtmosphere")

    place(env, env["SpikeContactRespawnFunctionalTest"],
          unreal.Vector(-200.0, -900.0, 100.0), "SpikeContactRespawnFunctionalTest")

    world = unreal.EditorLevelLibrary.get_editor_world()
    settings = world.get_world_settings()
    settings.set_editor_property("default_game_mode", env["SpikeLaneGameMode"])
    log("world settings: default game mode = SpikeLaneGameMode")

    # Refuse to save a level nobody can SEE.
    lit = [a for a in eas.get_all_level_actors()
           if a.get_class().get_name() in ("DirectionalLight", "SkyLight")]
    if len(lit) < 2:
        fail(f"level has {len(lit)} light actor(s); a capture still would be black")

    # Refuse to save a level nobody can DRIVE. Naming a game mode above replaced
    # GlobalDefaultGameMode, and both halves of Enhanced Input live on the Blueprints
    # it would have supplied.
    gm_cdo = unreal.get_default_object(env["SpikeLaneGameMode"])
    pc_class = gm_cdo.get_editor_property("player_controller_class")
    pawn_class = gm_cdo.get_editor_property("default_pawn_class")
    if pc_class is None:
        fail("the game mode names no PlayerControllerClass; the level could not be "
             "driven by hand")
    unbound = []
    pawn_cdo = unreal.get_default_object(pawn_class) if pawn_class else None
    for prop in ("move_action", "look_action", "mouse_look_action", "jump_action"):
        try:
            if pawn_cdo is None or not pawn_cdo.get_editor_property(prop):
                unbound.append(prop)
        except Exception:
            unbound.append(prop)
    if unbound:
        fail(f"the pawn has nothing bound to {', '.join(unbound)}")
    log(f"play lane OK: controller={pc_class.get_name()} pawn={pawn_class.get_name()}")

    # Refuse to save a course the fixture cannot resolve.
    for tag, want in (("LanePad", 2), ("RailPost", 2), ("LaneCharacter", 1),
                      ("SpikeLane", 1), ("SlidingSpikes", 1), ("StartMark", 1)):
        got = [a for a in eas.get_all_level_actors() if a.actor_has_tag(tag)]
        if len(got) != want:
            fail(f"{len(got)} actor(s) tagged {tag}, expected {want}")
    log("every tag the fixture resolves is present in the authored count")

    if not les.save_current_level():
        fail("save_current_level() returned False")
    log(f"SAVED {MAP_PKG}")


main()

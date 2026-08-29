"""Authors L_CollectArena for t2-collect-then-exit.

Run headless against the ThirdPerson project:

    UnrealEditor-Cmd.exe <ThirdPerson.uproject> -run=pythonscript \
        -script="<abs path to this file>" -nullrhi -unattended -nopause \
        -log -stdout -FullStdOutLogOutput

The constants below are the map contract the fixture asserts against. Change one
here and you must change it there.

This level deliberately names NO game mode: it inherits the project default
(BP_ThirdPersonGameMode), whose pawn is BP_ThirdPersonCharacter and whose controller
carries IMC_Default. That is what the spec asks for and it also sidesteps the trap
recorded in the 2026-08-17 unplayable-play-lane finding -- naming a game
mode drops both halves of Enhanced Input and the level grades identically while being
impossible to walk around.

Every Rotator is built with KEYWORDS: unreal.Rotator's positional order is
(roll, pitch, yaw), so Rotator(0, 30, 0) is a 30 degree PITCH. That put a whole
level on its side once already.
"""
import unreal

TASK = "t2-collect-then-exit"
MAP_PKG = f"/Game/Maps/{TASK}/L_CollectArena"

# Floor spans X 0..2400, Y -1200..+1200, top at Z=0.
FLOOR_MIN = (0.0, -1200.0)
FLOOR_MAX = (2400.0, 1200.0)
STRIPE_EVERY = 200.0
START_AT = unreal.Vector(300.0, 0.0, 100.0)
RELICS = [(900.0, -500.0), (1500.0, 500.0), (1900.0, -500.0), (1900.0, -1000.0)]
RELIC_Z = 60.0
EXIT_AT = unreal.Vector(2100.0, 0.0, 0.0)
BOARD_AT = unreal.Vector(2050.0, 650.0, 0.0)
# Behind the player start and behind the exit, both on the FAR side in Y, so
# neither can stand in front of the signboard from a camera in the arena
# (the first pair put a pylon straight through the readouts).
LANDMARKS = [(-150.0, -1100.0), (2550.0, 1150.0)]

CUBE = "/Engine/BasicShapes/Cube.Cube"
CYL = "/Engine/BasicShapes/Cylinder.Cylinder"
CONE = "/Engine/BasicShapes/Cone.Cone"


def log(msg):
    unreal.log(f"COLLECT- {msg}")


def fail(msg):
    unreal.log_error(f"COLLECT-ERROR {msg}")
    raise SystemExit(1)


def probe():
    """Resolve everything before authoring. Refuses rather than half-builds."""
    got = {}
    for name, cls in (("les", unreal.LevelEditorSubsystem),
                      ("eas", unreal.EditorActorSubsystem)):
        sub = unreal.get_editor_subsystem(cls)
        if sub is None:
            fail(f"subsystem {cls.__name__} is unavailable in this boot")
        got[name] = sub
    for path in (CUBE, CYL, CONE):
        if not unreal.EditorAssetLibrary.does_asset_exist(path):
            fail(f"engine asset missing: {path}")
    for cls_name in ("RelicPickup", "ExitGate", "ArenaSignboard",
                     "CollectThenExitFunctionalTest"):
        if not hasattr(unreal, cls_name):
            fail(f"class {cls_name} is not exposed to python - is the module built?")
        got[cls_name] = getattr(unreal, cls_name)
    log(f"probe OK: {sorted(got)}")
    return got


def block(env, mesh, loc, scale, label, yaw=0.0):
    actor = env["eas"].spawn_actor_from_class(
        unreal.StaticMeshActor, loc, unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
    if actor is None:
        fail(f"could not spawn {label}")
    actor.set_actor_label(label)
    comp = actor.static_mesh_component
    comp.set_static_mesh(unreal.EditorAssetLibrary.load_asset(mesh))
    comp.set_editor_property("mobility", unreal.ComponentMobility.STATIC)
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
        fail(f"{MAP_PKG} already exists. Delete the file from the SHELL and re-run; "
             f"overwriting from here is not supported.")
    if not les.new_level(MAP_PKG):
        fail(f"new_level({MAP_PKG}) returned False")
    log(f"created {MAP_PKG}")

    # FLOOR, solid under the whole route including behind the player start.
    span_x = FLOOR_MAX[0] - FLOOR_MIN[0]
    span_y = FLOOR_MAX[1] - FLOOR_MIN[1]
    mid_x = (FLOOR_MAX[0] + FLOOR_MIN[0]) / 2.0
    mid_y = (FLOOR_MAX[1] + FLOOR_MIN[1]) / 2.0
    block(env, CUBE, unreal.Vector(mid_x, mid_y, -50.0),
          unreal.Vector(span_x / 100.0, span_y / 100.0, 1.0), "Floor")

    # STRIPES across X every 200 cm, 3 cm proud so they read on a still (a flush
    # stripe photographs as nothing at all).
    n = 0
    x = FLOOR_MIN[0] + STRIPE_EVERY
    while x < FLOOR_MAX[0]:
        block(env, CUBE, unreal.Vector(x, mid_y, 1.5),
              unreal.Vector(0.06, span_y / 100.0, 0.03), f"Stripe_{n:02d}")
        n += 1
        x += STRIPE_EVERY
    log(f"floor {span_x:.0f}x{span_y:.0f} + {n} stripes")

    # FOUR RELICS, all the same class, no per-instance mark saying which three
    # matter. The last two are 500 cm apart so the one that vanishes and the one
    # that stays sit in one camera frame.
    for idx, (rx, ry) in enumerate(RELICS):
        place(env, env["RelicPickup"], unreal.Vector(rx, ry, RELIC_Z),
              f"Relic_{idx}")
    log(f"{len(RELICS)} relics placed at {RELICS}")

    place(env, env["ExitGate"], EXIT_AT, "ExitGate", yaw=90.0)
    place(env, env["ArenaSignboard"], BOARD_AT, "ArenaSignboard", yaw=180.0)

    start = eas.spawn_actor_from_class(
        unreal.PlayerStart, START_AT, unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if start is None:
        fail("could not place PlayerStart")
    start.set_actor_label("PlayerStart")
    log("exit + signboard + PlayerStart placed")

    for idx, (lx, ly) in enumerate(LANDMARKS):
        block(env, CYL, unreal.Vector(lx, ly, 300.0),
              unreal.Vector(1.4, 1.4, 6.0), f"Landmark_{idx}")

    # LIGHTING. new_level() gives a COMPLETELY EMPTY level, and an unlit level
    # photographs as pure black while grading perfectly.
    sun = eas.spawn_actor_from_class(
        unreal.DirectionalLight, unreal.Vector(mid_x, mid_y, 900.0),
        unreal.Rotator(roll=0.0, pitch=-46.0, yaw=-140.0))
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

    place(env, env["CollectThenExitFunctionalTest"],
          unreal.Vector(-200.0, -1400.0, 100.0), "CollectThenExitFunctionalTest")

    # NO default_game_mode is set on purpose -- see the module docstring.
    world = unreal.EditorLevelLibrary.get_editor_world()
    settings = world.get_world_settings()
    if settings.get_editor_property("default_game_mode") is not None:
        fail("world settings already name a game mode; this level must inherit the "
             "project default so the play lane comes for free")
    log("world settings: no game mode named (inherits BP_ThirdPersonGameMode)")

    # Refuse to save a level nobody can SEE.
    lit = [a for a in eas.get_all_level_actors()
           if a.get_class().get_name() in ("DirectionalLight", "SkyLight")]
    if len(lit) < 2:
        fail(f"level has {len(lit)} light actor(s); a capture still would be black "
             f"and the task would grade clean while being invisible")

    # Refuse to save a level whose relics are not where the fixture expects, or
    # whose readouts are missing -- both are HARNESS-PRECONDITION failures at run
    # time, which is a slower and more confusing way to learn the same thing.
    placed = [a for a in eas.get_all_level_actors()
              if a.actor_has_tag("ArenaRelic")]
    if len(placed) != 4:
        fail(f"{len(placed)} relics tagged ArenaRelic, expected 4")
    for rx, ry in RELICS:
        near = [a for a in placed
                if abs(a.get_actor_location().x - rx) < 1.0
                and abs(a.get_actor_location().y - ry) < 1.0]
        if len(near) != 1:
            fail(f"no single relic at the authored spot ({rx}, {ry})")
    log("all four relics at their authored spots")

    if not les.save_current_level():
        fail("save_current_level() returned False")
    log(f"SAVED {MAP_PKG}")


main()

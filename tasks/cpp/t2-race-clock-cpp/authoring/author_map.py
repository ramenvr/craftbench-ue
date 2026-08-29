"""Authors L_RaceArena for t2-race-clock.

    UnrealEditor-Cmd.exe <ThirdPerson.uproject> -run=pythonscript \
        -script="<abs path to this file>" -nullrhi -unattended -nopause \
        -log -stdout -FullStdOutLogOutput

DEVIATION FROM THE SPEC, recorded here and in notes.md: the spec's scene calls for
Blueprint subclasses BP_RaceCoin and BP_RaceRound. The placed actors here are the C++
bases directly. The fixture resolves everything by TAG and reads PointValue / Score /
TimeRemaining / RoundState by PROPERTY NAME, so a Blueprint subclass and the base
grade identically -- and the agent is free to subclass either way. Placing the bases
avoids authoring two Blueprint assets that carry no behaviour of their own.

Every Rotator is built with KEYWORDS -- unreal.Rotator's positional order is
(roll, pitch, yaw).
"""
import unreal

TASK = "t2-race-clock"
MAP_PKG = f"/Game/Maps/{TASK}/L_RaceArena"

FLOOR_HALF = 2000.0
STRIPE_EVERY = 200.0
START_AT = unreal.Vector(-1400.0, 0.0, 100.0)
# The route runs the Y = 0 line; the control sits 300 cm off it, beside Coin_B.
COINS = [
    ("Coin_A", -1000.0, 0.0, 15),
    ("Coin_B", -600.0, 0.0, 40),
    ("Coin_C", -200.0, 0.0, 25),
    ("Coin_D", 300.0, 0.0, 60),
    ("Coin_E", 900.0, 0.0, 35),
    ("Coin_F", 1300.0, 0.0, 90),
    ("Coin_Ctrl", -600.0, 300.0, 100),
]
ROUND_AT = unreal.Vector(0.0, -900.0, 0.0)
# THE REPLAY PAD, out in front of the board on the arena floor, where somebody who has
# just watched their round time out is standing. Far enough from the board to be a
# thing you walk to rather than part of the scenery.
REPLAY_PAD_AT = unreal.Vector(0.0, -400.0, 5.0)
LANDMARKS = [(-1600.0, 900.0), (1600.0, 900.0)]

CUBE = "/Engine/BasicShapes/Cube.Cube"
CYL = "/Engine/BasicShapes/Cylinder.Cylinder"
M_FLOOR = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray"
M_STRIPE = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02"
M_POST = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"


def log(msg):
    unreal.log(f"RACE- {msg}")


def fail(msg):
    unreal.log_error(f"RACE-ERROR {msg}")
    raise SystemExit(1)


def probe():
    got = {}
    for name, cls in (("les", unreal.LevelEditorSubsystem),
                      ("eas", unreal.EditorActorSubsystem)):
        sub = unreal.get_editor_subsystem(cls)
        if sub is None:
            fail(f"subsystem {cls.__name__} is unavailable in this boot")
        got[name] = sub
    for path in (CUBE, CYL, M_FLOOR, M_STRIPE, M_POST):
        if not unreal.EditorAssetLibrary.does_asset_exist(path):
            fail(f"asset missing: {path}")
    for cls_name in ("RaceCoinBase", "RaceRoundBase", "RaceReplayPadActor",
                     "RaceCollector",
                     "RaceGameMode", "RaceTheClockFunctionalTest"):
        if not hasattr(unreal, cls_name):
            fail(f"class {cls_name} is not exposed to python - is the module built?")
        got[cls_name] = getattr(unreal, cls_name)
    log(f"probe OK: {sorted(got)}")
    return got


def block(env, mesh, loc, scale, label, material=None):
    actor = env["eas"].spawn_actor_from_class(
        unreal.StaticMeshActor, loc, unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
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

    block(env, CUBE, unreal.Vector(0.0, 0.0, -50.0),
          unreal.Vector(FLOOR_HALF * 2 / 100.0, FLOOR_HALF * 2 / 100.0, 1.0),
          "Floor", M_FLOOR)

    n = 0
    x = -FLOOR_HALF + STRIPE_EVERY
    while x < FLOOR_HALF:
        block(env, CUBE, unreal.Vector(x, 0.0, 1.5),
              unreal.Vector(0.06, FLOOR_HALF * 2 / 100.0, 0.03), f"Stripe_{n:02d}",
              M_STRIPE)
        n += 1
        x += STRIPE_EVERY
    log(f"floor {FLOOR_HALF*2:.0f} square + {n} stripes")

    for label, cx, cy, value in COINS:
        coin = place(env, env["RaceCoinBase"], unreal.Vector(cx, cy, 40.0), label)
        coin.set_editor_property("point_value", value)
    log(f"{len(COINS)} coins placed, values {[c[3] for c in COINS]}")

    place(env, env["RaceRoundBase"], ROUND_AT, "RaceRound")
    pad = place(env, env["RaceReplayPadActor"], REPLAY_PAD_AT, "RaceReplayPad")
    pad.tags = ["RaceReplayPad"]
    log(f"replay pad placed at {REPLAY_PAD_AT}; the round times out and standing "
        f"here has to start another one")

    start = eas.spawn_actor_from_class(
        unreal.PlayerStart, START_AT, unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if start is None:
        fail("could not place PlayerStart")
    start.set_actor_label("PlayerStart")

    for idx, (lx, ly) in enumerate(LANDMARKS):
        block(env, CYL, unreal.Vector(lx, ly, 350.0),
              unreal.Vector(1.3 + idx * 0.6, 1.3 + idx * 0.6, 7.0),
              f"Landmark_{idx}", M_POST)

    sun = eas.spawn_actor_from_class(
        unreal.DirectionalLight, unreal.Vector(0.0, 0.0, 900.0),
        unreal.Rotator(roll=0.0, pitch=-48.0, yaw=-125.0))
    sky = eas.spawn_actor_from_class(
        unreal.SkyLight, unreal.Vector(0.0, 0.0, 900.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    atmo = eas.spawn_actor_from_class(
        unreal.SkyAtmosphere, unreal.Vector(0.0, 0.0, 0.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if sun is None or sky is None or atmo is None:
        fail("could not place the lighting rig")
    sun.set_actor_label("DirectionalLight")
    sky.set_actor_label("SkyLight")
    atmo.set_actor_label("SkyAtmosphere")
    log("lighting: DirectionalLight + SkyLight + SkyAtmosphere")

    place(env, env["RaceTheClockFunctionalTest"],
          unreal.Vector(-1800.0, -1500.0, 100.0), "RaceTheClockFunctionalTest")

    world = unreal.EditorLevelLibrary.get_editor_world()
    settings = world.get_world_settings()
    settings.set_editor_property("default_game_mode", env["RaceGameMode"])
    log("world settings: default game mode = RaceGameMode")

    lit = [a for a in eas.get_all_level_actors()
           if a.get_class().get_name() in ("DirectionalLight", "SkyLight")]
    if len(lit) < 2:
        fail(f"level has {len(lit)} light actor(s); a capture still would be black")

    gm_cdo = unreal.get_default_object(env["RaceGameMode"])
    pc_class = gm_cdo.get_editor_property("player_controller_class")
    pawn_class = gm_cdo.get_editor_property("default_pawn_class")
    if pc_class is None:
        fail("the game mode names no PlayerControllerClass; the level could not be "
             "driven by hand")
    pawn_cdo = unreal.get_default_object(pawn_class) if pawn_class else None
    unbound = []
    for prop in ("move_action", "look_action", "mouse_look_action", "jump_action"):
        try:
            if pawn_cdo is None or not pawn_cdo.get_editor_property(prop):
                unbound.append(prop)
        except Exception:
            unbound.append(prop)
    if unbound:
        fail(f"the pawn has nothing bound to {', '.join(unbound)}")
    log(f"play lane OK: controller={pc_class.get_name()} pawn={pawn_class.get_name()}")

    coins = [a for a in eas.get_all_level_actors() if a.actor_has_tag("RaceCoin")]
    if len(coins) != len(COINS):
        fail(f"{len(coins)} coins tagged RaceCoin, expected {len(COINS)}")
    values = sorted(c.get_editor_property("point_value") for c in coins)
    if len(set(values)) != len(values) or min(values) < 5 or max(values) > 100:
        fail(f"coin values {values} are not seven distinct numbers between 5 and 100")
    # The route walks Y = 0; the control has to be far enough off it that the drive
    # cannot reach it. 300 cm against a ~94 cm reach is better than 3x clearance.
    offline = [c for c in coins if abs(c.get_actor_location().y) > 100.0]
    if len(offline) != 1:
        fail(f"{len(offline)} coins sit off the route line, expected exactly 1 control")
    log(f"seven distinct coin values {values}, one control off the route")

    if not les.save_current_level():
        fail("save_current_level() returned False")
    log(f"SAVED {MAP_PKG}")


main()

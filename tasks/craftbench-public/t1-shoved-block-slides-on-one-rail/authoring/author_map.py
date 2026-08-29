"""Authors L_RailBench for t1-shoved-block-slides-on-one-rail.

Run headless against the ThirdPerson project:

    UnrealEditor-Cmd.exe <ThirdPerson.uproject> -run=pythonscript \
        -script="<abs path to this file>" -nullrhi -unattended -nopause \
        -log -stdout -FullStdOutLogOutput

Everything is expressed in the RAIL FRAME, and the constants below are the map
contract the fixture asserts against: rail bearing 30 deg off world X, the rail
marker at the world origin, the railed block 1,000 cm back along the rail from it
and the twin 300 cm across. Change one here and you must change it there.

A capability probe runs first because a wrong API name in UE python does not raise
where you can see it - it returns None and the script sails on to save a broken
level.

Every Rotator here is built with KEYWORDS. unreal.Rotator's positional order is
(roll, pitch, yaw), so Rotator(0.0, 30.0, 0.0) is a 30 degree PITCH, not a yaw --
the first run of this script laid the rail, both blocks, the plunger, the stripes
and the sun on their sides that way, and the forward-axis assertion below is the
only thing that caught it. Other task scripts in this repo never hit it because
they only ever pass Rotator(0, 0, 0).
"""
import math

import unreal

TASK = "t1-shoved-block-slides-on-one-rail"
MAP_PKG = f"/Game/Maps/{TASK}/L_RailBench"

RAIL_YAW = 30.0
U = (math.cos(math.radians(RAIL_YAW)), math.sin(math.radians(RAIL_YAW)))
R = (-math.sin(math.radians(RAIL_YAW)), math.cos(math.radians(RAIL_YAW)))

# The rail marker sits at the world origin with its top flush with the floor, so
# both blocks rest on the floor at the same height and neither straddles a lip.
RAIL_AT = unreal.Vector(0.0, 0.0, -3.0)
BLOCK_Z = 34.0          # half of the 60 cm cube, plus a 4 cm air gap.
# The gap is load-bearing, not cosmetic. A block resting EXACTLY on the floor
# with its height locked by the rail fights the floor contact: the solver
# resolves the slight interpenetration with a large normal force, friction goes
# with it, and a 600 cm/s shove along the rail died at 31.7 cm/s (measured
# 2026-08-17). Held clear of the floor the same shove is unimpeded. The twin,
# which is on bare floor, simply settles the 4 cm at play start -- which is what
# the prompt's "settling at play start is fine" covers, and cp0 allows 10 cm.
STRIPE_EVERY = 200.0    # one stripe per 200 cm of rail travel
STRIPE_LEN = 1400.0
CORRIDOR_HALF = 60.0    # half-width of the stripe-free lane the blocks slide down
FLOOR = (4800.0, 3000.0)
FLOOR_AT = unreal.Vector(-300.0, -175.0, 0.0)

CUBE = "/Engine/BasicShapes/Cube.Cube"
CYL = "/Engine/BasicShapes/Cylinder.Cylinder"


def along(k):
    """A point k cm along the rail from the rail marker, at floor level."""
    return (RAIL_AT.x + U[0] * k, RAIL_AT.y + U[1] * k)


def across(p, k):
    return (p[0] + R[0] * k, p[1] + R[1] * k)


def log(msg):
    unreal.log(f"RAILBENCH- {msg}")


def fail(msg):
    unreal.log_error(f"RAILBENCH-ERROR {msg}")
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
    for path in (CUBE, CYL):
        if not unreal.EditorAssetLibrary.does_asset_exist(path):
            fail(f"engine asset missing: {path}")
    for cls_name in ("RailActor", "RailBlockActor", "TwinBlockActor",
                     "PlungerActor", "BenchCharacter", "BenchGameMode",
                     "ShovedBlockRailFunctionalTest"):
        if not hasattr(unreal, cls_name):
            fail(f"class {cls_name} is not exposed to python - is the module built?")
        got[cls_name] = getattr(unreal, cls_name)
    log(f"probe OK: {sorted(k for k in got)}")
    return got


def block(env, mesh, loc, scale, label, yaw=0.0):
    """A static-mesh box/cylinder placed as a plain StaticMeshActor."""
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


def place(env, cls, loc, label, yaw=RAIL_YAW):
    actor = env["eas"].spawn_actor_from_class(cls, loc, unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
    if actor is None:
        fail(f"could not place {label}")
    actor.set_actor_label(label)
    return actor


def main():
    env = probe()
    les, eas = env["les"], env["eas"]

    # One-way on purpose: new_level() refuses to overwrite, and a half-written
    # level is worse than none. Delete the .umap from the shell to re-author.
    if unreal.EditorAssetLibrary.does_asset_exist(MAP_PKG):
        fail(f"{MAP_PKG} already exists. Delete the file from the SHELL and "
             f"re-run; overwriting from here is not supported.")
    if not les.new_level(MAP_PKG):
        fail(f"new_level({MAP_PKG}) returned False")
    log(f"created {MAP_PKG}")

    # FLOOR. Solid under the WHOLE route including behind the player start, so a
    # reversing character never runs out of ground.
    block(env, CUBE, unreal.Vector(FLOOR_AT.x, FLOOR_AT.y, -50.0),
          unreal.Vector(FLOOR[0] / 100.0, FLOOR[1] / 100.0, 1.0), "Floor")

    # STRIPES, perpendicular to the rail: 200 cm of rail travel is one stripe by
    # eye. 3 cm proud, never flush - a flush stripe reads as nothing on a still.
    # Each stripe is TWO segments with a clear corridor down the rail. A stripe
    # that crosses the rail is an obstacle 3 cm tall in the block's path: with a
    # continuous stripe the railed block scraped every one of them and a 550 cm/s
    # shove arrived at cp1 having travelled 35 cm (measured 2026-08-17, and a
    # BIGGER shove travelled LESS, which is the tell). The corridor keeps the
    # stripes proud enough to read on a still and out of the slide.
    n = 0
    k = -1600.0
    while k <= 2000.0:
        p = along(k)
        for side in (-1.0, 1.0):
            q = across(p, side * (CORRIDOR_HALF + STRIPE_LEN / 4.0))
            block(env, CUBE, unreal.Vector(q[0], q[1], 1.5),
                  unreal.Vector(0.06, STRIPE_LEN / 200.0, 0.03),
                  f"Stripe_{n:02d}{'L' if side < 0 else 'R'}", yaw=RAIL_YAW)
        n += 1
        k += STRIPE_EVERY
    log(f"floor + {n} stripe pairs, {CORRIDOR_HALF * 2:.0f} cm corridor clear "
        f"down the rail")

    # THE RAIL, then the two blocks square with it.
    rail = place(env, env["RailActor"], RAIL_AT, "RailLine")
    fwd = rail.get_actor_forward_vector()
    if abs(fwd.x - U[0]) > 0.001 or abs(fwd.y - U[1]) > 0.001:
        fail(f"the placed rail's forward axis ({fwd.x:.4f},{fwd.y:.4f}) is not the "
             f"authored bearing ({U[0]:.4f},{U[1]:.4f}); the fixture asserts this "
             f"within 0.5 deg and would report the map, not the answer")

    b = along(-1100.0)
    place(env, env["RailBlockActor"], unreal.Vector(b[0], b[1], BLOCK_Z), "RailBlock")
    t = across(b, 300.0)
    place(env, env["TwinBlockActor"], unreal.Vector(t[0], t[1], BLOCK_Z), "TwinBlock")

    p = along(-1500.0)
    place(env, env["PlungerActor"], unreal.Vector(p[0], p[1], 0.0), "Plunger")

    s = along(-2400.0)
    start = eas.spawn_actor_from_class(
        unreal.PlayerStart, unreal.Vector(s[0], s[1], 96.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=RAIL_YAW))
    if start is None:
        fail("could not place PlayerStart")
    start.set_actor_label("PlayerStart")
    log("rail + both blocks + plunger + PlayerStart placed on the rail bearing")

    # LANDMARKS at each end of the backdrop, so a moving camera reads as moving.
    for idx, k in enumerate((-2500.0, 2200.0)):
        q = across(along(k), 700.0)
        block(env, CYL, unreal.Vector(q[0], q[1], 300.0),
              unreal.Vector(1.2, 1.2, 6.0), f"Landmark_{idx}")

    # LIGHTING. new_level() gives a COMPLETELY EMPTY level, and an unlit level
    # photographs as pure black while grading perfectly - the assertion below is
    # what stops that shipping again.
    sun = eas.spawn_actor_from_class(
        unreal.DirectionalLight, unreal.Vector(0.0, 0.0, 900.0),
        unreal.Rotator(roll=0.0, pitch=-48.0, yaw=150.0))
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

    ft = place(env, env["ShovedBlockRailFunctionalTest"],
               unreal.Vector(-2600.0, -1600.0, 100.0),
               "ShovedBlockRailFunctionalTest", yaw=0.0)
    if ft is None:
        fail("could not place ShovedBlockRailFunctionalTest")

    world = unreal.EditorLevelLibrary.get_editor_world()
    settings = world.get_world_settings()
    settings.set_editor_property("default_game_mode", env["BenchGameMode"])
    log("world settings: default game mode = BenchGameMode")

    # Refuse to save a level nobody can SEE.
    lit = [a for a in eas.get_all_level_actors()
           if a.get_class().get_name() in ("DirectionalLight", "SkyLight")]
    if len(lit) < 2:
        fail(f"level has {len(lit)} light actor(s); a capture still would be black "
             f"and the task would grade clean while being invisible")

    # Refuse to save a level nobody can DRIVE. Naming a game mode above replaced
    # GlobalDefaultGameMode (BP_ThirdPersonGameMode), and both halves of Enhanced
    # Input live on the Blueprints it would have supplied. No fixture catches this
    # - they all drive the pawn through AddMovementInput - which is how a map can
    # ship authored, lit, graded and completely uncontrollable. See
    # the 2026-08-17 unplayable-play-lane finding.
    gm_cdo = unreal.get_default_object(env["BenchGameMode"])
    pc_class = gm_cdo.get_editor_property("player_controller_class")
    pawn_class = gm_cdo.get_editor_property("default_pawn_class")
    if pc_class is None:
        fail("the game mode names no PlayerControllerClass, so the player would get "
             "a bare APlayerController with no input mapping context and the level "
             "could not be driven by hand")
    unbound = []
    pawn_cdo = unreal.get_default_object(pawn_class) if pawn_class else None
    for prop in ("move_action", "look_action", "mouse_look_action", "jump_action"):
        try:
            if pawn_cdo is None or not pawn_cdo.get_editor_property(prop):
                unbound.append(prop)
        except Exception:
            unbound.append(prop)
    if unbound:
        fail(f"the pawn has nothing bound to {', '.join(unbound)}; the level would "
             f"grade identically and be impossible to walk around")
    log(f"play lane OK: controller={pc_class.get_name()} "
        f"pawn={pawn_class.get_name()} all four input actions bound")

    if not les.save_current_level():
        fail("save_current_level() returned False")
    log(f"SAVED {MAP_PKG}")


main()

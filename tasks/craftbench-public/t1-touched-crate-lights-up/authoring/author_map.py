"""Authors L_CrateBay for t1-touched-crate-lights-up.

    UnrealEditor-Cmd.exe <ThirdPerson.uproject> -run=pythonscript \
        -script="<abs path to this file>" -nullrhi -unattended -nopause \
        -log -stdout -FullStdOutLogOutput

TWO CRATES THAT LOOK THE SAME AND NOTICE FROM DIFFERENT DISTANCES. That is the
whole task: one hard-coded reach is wrong about one of them wherever the
character stands between the two. The difference is PAINTED ON THE FLOOR as a
ring round each crate, so a reviewer can see at a glance that the two circles
are not the same size -- and so the level is honest about what it is asking.

The fixture SWAPS the crates between its two legs, so they are authored MOVABLE
and the level says so.

This level names NO game mode: it inherits the project default, so the play lane
comes for free (see the 2026-08-17 unplayable-play-lane finding).

Every Rotator is built with KEYWORDS -- unreal.Rotator's positional order is
(roll, pitch, yaw).
"""
import math

import unreal

TASK = "t1-touched-crate-lights-up"
MAP_PKG = f"/Game/Maps/{TASK}/L_CrateBay"

FLOOR_MIN = (-3600.0, -2000.0)
FLOOR_MAX = (9200.0, 2000.0)
STRIPE_EVERY = 400.0

# (x, y, notice radius). FIVE crates, no two reaches alike, and they are NOT in
# order of size -- so neither a single number nor "bigger as you go along" is an
# answer. The owner's note on the two-crate version: "CrateBay is easy, I think its
# mostly just collider part. Can we make it harder? Like put a bunch of boxes with
# different ranges."
#
# The reaches are deliberately interleaved with the spacing: crate 3's 200 is
# smaller than its neighbours', so there is a spot between crates 2 and 4 where
# BOTH of them notice you and the one you are standing next to does not.
CRATES = (
    (0.0, 0.0, 300.0),
    (1600.0, 0.0, 620.0),
    (3200.0, 0.0, 180.0),
    (4800.0, 0.0, 760.0),
    (6400.0, 0.0, 440.0),
)
CRATE_STAND_Z = 80.0          # half the crate's 160 cm height
START_AT = (-2900.0, 0.0)

# Mirrors the fixture's route factors, so "the far stops fit on the floor" is
# measured rather than eyeballed.
FAR_FACTOR = 3.0
RING_SEGMENTS = 32

CUBE = "/Engine/BasicShapes/Cube.Cube"
CYL = "/Engine/BasicShapes/Cylinder.Cylinder"
M_FLOOR = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray"
M_STRIPE = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02"
M_DARK = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"
M_GLOW = "/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT"
M_HAZARD = "/Game/Variant_Combat/Materials/M_Lava"


def log(msg):
    unreal.log(f"CRATEBAY- {msg}")


def fail(msg):
    unreal.log_error(f"CRATEBAY-ERROR {msg}")
    raise SystemExit(1)


def probe():
    got = {}
    for name, cls in (("les", unreal.LevelEditorSubsystem),
                      ("eas", unreal.EditorActorSubsystem)):
        sub = unreal.get_editor_subsystem(cls)
        if sub is None:
            fail(f"subsystem {cls.__name__} is unavailable in this boot")
        got[name] = sub
    for path in (CUBE, CYL, M_FLOOR, M_STRIPE, M_DARK, M_GLOW, M_HAZARD):
        if not unreal.EditorAssetLibrary.does_asset_exist(path):
            fail(f"asset missing: {path}")
    for cls_name in ("HighlightCrateActor", "CrateHighlightFunctionalTest"):
        if not hasattr(unreal, cls_name):
            fail(f"class {cls_name} is not exposed to python - is the module built?")
        got[cls_name] = getattr(unreal, cls_name)
    log(f"probe OK: {sorted(got)}")
    return got


def block(env, mesh, loc, scale, label, material=None, yaw=0.0, collide=True):
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
    if not collide:
        # The PROFILE, not just the enum: set_collision_enabled alone did not survive
        # into a saved level on the marked-ground task, and paint that quietly blocks
        # is indistinguishable from a bug in the submission.
        comp.set_collision_profile_name("NoCollision")
        comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    actor.set_actor_scale3d(scale)
    return actor


def check_geometry():
    """What has to be true before the level is worth saving."""
    reaches = [c[2] for c in CRATES]
    for i in range(len(CRATES)):
        for j in range(i + 1, len(CRATES)):
            if abs(reaches[i] - reaches[j]) < 100.0:
                fail(f"crates {i + 1} and {j + 1} notice from {reaches[i]:.0f} uu and "
                     f"{reaches[j]:.0f} uu, only {abs(reaches[i] - reaches[j]):.0f} "
                     f"apart; two crates a submission can treat as one is a crate "
                     f"that stopped testing anything")
    # NO TWO RINGS MAY TOUCH. If they did there would be nowhere to stand that is
    # inside one and outside its neighbour, and the whole point is standing exactly
    # there.
    for i in range(len(CRATES) - 1):
        ax, ay, ar = CRATES[i]
        bx, by, br = CRATES[i + 1]
        apart = math.hypot(bx - ax, by - ay)
        if apart <= ar + br + 100.0:
            fail(f"crates {i + 1} and {i + 2} are {apart:.0f} uu apart but their "
                 f"reaches total {ar + br:.0f}; their rings touch and there is "
                 f"nowhere between them that only one of them notices")
    # THE REACHES MUST NOT BE IN ORDER. Sorted radii let a submission key on
    # position -- "the further along, the further it sees" -- without ever reading
    # a crate's own number.
    if reaches == sorted(reaches) or reaches == sorted(reaches, reverse=True):
        fail(f"the reaches {[int(r) for r in reaches]} run in order along the bay; "
             f"a submission could key on position instead of reading each crate")
    # The fixture walks to maxReach * FAR_FACTOR beyond the end crates.
    far = max(reaches) * FAR_FACTOR
    if CRATES[0][0] - far < FLOOR_MIN[0] + 100.0:
        fail(f"the far stop before the first crate lands at "
             f"x={CRATES[0][0] - far:.0f}, off the floor (min {FLOOR_MIN[0]:.0f})")
    if CRATES[-1][0] + far > FLOOR_MAX[0] - 100.0:
        fail(f"the far stop past the last crate lands at "
             f"x={CRATES[-1][0] + far:.0f}, off the floor (max {FLOOR_MAX[0]:.0f})")
    log(f"geometry checked: {len(CRATES)} crates, reaches "
        f"{[int(r) for r in reaches]} (deliberately out of order), no two rings "
        f"touching, far stops inside a floor of {FLOOR_MIN[0]:.0f}.."
        f"{FLOOR_MAX[0]:.0f}")


def paint_ring(env, centre, radius, label, material):
    """The crate's reach, drawn on the floor so the difference is visible."""
    for k in range(RING_SEGMENTS):
        ang = 2.0 * math.pi * k / RING_SEGMENTS
        seg = 2.0 * math.pi * radius / RING_SEGMENTS * 0.7
        block(env, CUBE,
              unreal.Vector(centre[0] + math.cos(ang) * radius,
                            centre[1] + math.sin(ang) * radius, 2.0),
              unreal.Vector(0.10, seg / 100.0, 0.04),
              f"{label}_{k:02d}", material,
              yaw=math.degrees(ang) + 90.0, collide=False)


def main():
    env = probe()
    les, eas = env["les"], env["eas"]
    check_geometry()

    if unreal.EditorAssetLibrary.does_asset_exist(MAP_PKG):
        fail(f"{MAP_PKG} already exists. Delete the file from the SHELL and re-run.")
    if not les.new_level(MAP_PKG):
        fail(f"new_level({MAP_PKG}) returned False")
    log(f"created {MAP_PKG}")

    span_x = FLOOR_MAX[0] - FLOOR_MIN[0]
    span_y = FLOOR_MAX[1] - FLOOR_MIN[1]
    mid_x = (FLOOR_MAX[0] + FLOOR_MIN[0]) / 2.0
    mid_y = (FLOOR_MAX[1] + FLOOR_MIN[1]) / 2.0
    block(env, CUBE, unreal.Vector(mid_x, mid_y, -50.0),
          unreal.Vector(span_x / 100.0, span_y / 100.0, 1.0), "Floor", M_FLOOR)

    n = 0
    x = FLOOR_MIN[0] + STRIPE_EVERY
    while x < FLOOR_MAX[0]:
        block(env, CUBE, unreal.Vector(x, mid_y, 1.5),
              unreal.Vector(0.06, span_y / 100.0, 0.03), f"Stripe_{n:02d}", M_STRIPE,
              collide=False)
        n += 1
        x += STRIPE_EVERY
    log(f"bay {span_x:.0f}x{span_y:.0f} + {n} stripes")

    ring_looks = (M_GLOW, M_HAZARD, M_GLOW, M_HAZARD, M_GLOW)
    for idx, (cx, cy, cr) in enumerate(CRATES):
        label = f"HighlightCrate_{idx + 1}"
        ring_look = ring_looks[idx % len(ring_looks)]
        crate = eas.spawn_actor_from_class(
            env["HighlightCrateActor"], unreal.Vector(cx, cy, CRATE_STAND_Z),
            unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
        if crate is None:
            fail(f"could not place {label}")
        crate.set_actor_label(label)
        crate.set_editor_property("notice_radius_uu", cr)
        # MOVABLE: the fixture shifts every crate between its legs, and PIE scores
        # moving a STATIC actor as a failed test. The crate is not a StaticMeshActor,
        # so its mesh comes off its own Body property, not `static_mesh_component`.
        crate.get_editor_property("body").set_editor_property(
            "mobility", unreal.ComponentMobility.MOVABLE)
        paint_ring(env, (cx, cy), cr, f"Reach_{idx + 1}", ring_look)
    log(f"{len(CRATES)} crates placed, reaches "
        f"{[int(c[2]) for c in CRATES]}, each ring painted on the floor")

    start = eas.spawn_actor_from_class(
        unreal.PlayerStart, unreal.Vector(START_AT[0], START_AT[1], 100.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if start is None:
        fail("could not place PlayerStart")
    start.set_actor_label("PlayerStart")

    block(env, CUBE, unreal.Vector(mid_x, FLOOR_MAX[1] - 30.0, 90.0),
          unreal.Vector(span_x / 100.0, 0.4, 1.8), "Backdrop", M_DARK)
    for idx, lx in enumerate((FLOOR_MIN[0] + 250.0, FLOOR_MAX[0] - 250.0)):
        block(env, CYL, unreal.Vector(lx, FLOOR_MAX[1] - 400.0, 300.0),
              unreal.Vector(1.1 + idx * 0.9, 1.1 + idx * 0.9, 6.0), f"Landmark_{idx}",
              M_GLOW if idx else M_HAZARD)

    sun = eas.spawn_actor_from_class(
        unreal.DirectionalLight, unreal.Vector(mid_x, mid_y, 1000.0),
        unreal.Rotator(roll=0.0, pitch=-52.0, yaw=-120.0))
    sky = eas.spawn_actor_from_class(
        unreal.SkyLight, unreal.Vector(mid_x, mid_y, 1000.0),
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

    eas.spawn_actor_from_class(
        env["CrateHighlightFunctionalTest"],
        unreal.Vector(FLOOR_MIN[0] + 250.0, FLOOR_MIN[1] + 250.0, 120.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0)).set_actor_label(
            "CrateHighlightFunctionalTest")

    world = unreal.EditorLevelLibrary.get_editor_world()
    if world.get_world_settings().get_editor_property("default_game_mode") is not None:
        fail("world settings already name a game mode; this level must inherit the "
             "project default so the play lane comes for free")
    log("world settings: no game mode named (inherits BP_ThirdPersonGameMode)")

    lit = [a for a in eas.get_all_level_actors()
           if a.get_class().get_name() in ("DirectionalLight", "SkyLight")]
    if len(lit) < 2:
        fail(f"level has {len(lit)} light actor(s); a capture still would be black")

    crates = [a for a in eas.get_all_level_actors()
              if a.actor_has_tag("HighlightCrate")]
    if len(crates) != len(CRATES):
        fail(f"{len(crates)} actor(s) tagged HighlightCrate, expected {len(CRATES)}")

    reaches = []
    for crate in crates:
        reaches.append(float(crate.get_editor_property("notice_radius_uu")))
        if crate.get_editor_property("body").get_editor_property("mobility") != \
                unreal.ComponentMobility.MOVABLE:
            fail(f"{crate.get_actor_label()} is not MOVABLE; the fixture swaps the "
                 f"crates between its legs and PIE would log a mobility error, which "
                 f"the functional test scores as a FAIL")
        # A crate whose collision dips below the floor is penetrating from frame one.
        origin, extent = crate.get_actor_bounds(only_colliding_components=True)
        if origin.z - extent.z < -1.0:
            fail(f"{crate.get_actor_label()} reaches down to "
                 f"z={origin.z - extent.z:.1f}, below the floor")
    reaches.sort()
    for i in range(len(reaches) - 1):
        if reaches[i + 1] - reaches[i] < 100.0:
            fail(f"two placed crates notice from {reaches[i]:.0f} and "
                 f"{reaches[i + 1]:.0f} uu; the differences are what the task "
                 f"measures and they did not survive placement")
    log(f"placed crates read back their own reaches: {[int(r) for r in reaches]}, "
        f"all MOVABLE, all standing on the floor")

    if not les.save_current_level():
        fail("save_current_level() returned False")
    log(f"SAVED {MAP_PKG}")


main()

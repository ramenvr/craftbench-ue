"""Authors L_SightYard for t1-guard-only-spots-what-it-can-see.

    UnrealEditor-Cmd.exe <ThirdPerson.uproject> -run=pythonscript \
        -script="<abs path to this file>" -nullrhi -unattended -nopause \
        -log -stdout -FullStdOutLogOutput

THE GUARDS ARE INTERCHANGEABLE ON PURPOSE. Same class, same facing, no per-instance
tag, name or index that says which is which. Which one the wall blocks is decided by
GEOMETRY, and the fixture re-decides it after jittering both -- so a submission cannot
key on identity or position, only on what a guard can see.

This level names NO game mode: it inherits the project default, so the play lane comes
for free (see the 2026-08-17 unplayable-play-lane finding).

Every Rotator is built with KEYWORDS -- unreal.Rotator's positional order is
(roll, pitch, yaw).
"""
import math

import unreal

TASK = "t1-guard-only-spots-what-it-can-see"
MAP_PKG = f"/Game/Maps/{TASK}/L_SightYard"

FLOOR_MIN = (-900.0, -1100.0)
FLOOR_MAX = (2100.0, 1100.0)
STRIPE_EVERY = 200.0
# Both guards stand on X = 0 facing +X. The wall sits in front of ONE of them; the
# crate sits in front of the other, far enough out that the character can stand
# either side of it.
#
# THE SEPARATION IS MEASURED, NOT CHOSEN FOR LOOKS. At +/-150 the wall that blocks
# one guard reached across and blocked the OTHER one too, from every position on
# the route -- both guards read truth=0 all run and nothing was gradeable. The
# pre-save assertion at the bottom now measures the clearance instead of trusting
# the numbers here.
GUARD_A = (0.0, -300.0)
GUARD_B = (0.0, 300.0)
# Offset OUTWARD from the guard it blocks, so its near edge stays far from the
# other guard's sightlines.
# Span and offset are BOTH measured, twice over. The first draft's low edge missed one
# of the walled guard's sightlines by 4cm; the second passed here and then FAILED in
# PIE, because the fixture jitters the guards by up to 70cm before play and the
# assertion was measuring the placed positions only. The check below now samples the
# jittered corners, and the fixture re-checks the real thing after its own jitter.
# Only the wall's DISTANCE from the guards is chosen. Its width and offset are SOLVED
# from the geometry by plan_wall() below, because hand-tuning them cost three rounds:
# a span that cleared the placed guards stopped clearing the jittered ones, and the
# span that fixed that reached across the path the character walks.
WALL_X = 150.0
CRATE_AT = (500.0, -300.0)
START_AT = unreal.Vector(900.0, 0.0, 100.0)
SIGHT_RANGE = 1200.0
SIGHT_HALF_ANGLE = 45.0
# Mirrors the fixture's staging jitter. The checks below have to hold at every corner
# of that box, not just at the placed transforms -- a wall that cleared the placed
# positions and failed the jittered ones cost a correct reference solution a FAIL.
JITTER_CM = 70.0
JITTER_DEG = 8.0
JITTER_SLACK = 60.0
LANDMARKS = [(-800.0, 800.0), (2000.0, 800.0)]
# The stop the route keeps returning to, and the one the grade turns on.
IN_FRONT = ((GUARD_A[0] + GUARD_B[0]) / 2.0 + 600.0,
            (GUARD_A[1] + GUARD_B[1]) / 2.0)

CUBE = "/Engine/BasicShapes/Cube.Cube"
CYL = "/Engine/BasicShapes/Cylinder.Cylinder"
M_FLOOR = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray"
M_STRIPE = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02"
M_DARK = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"
M_GLOW = "/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT"


def route_samples():
    """Every point the character passes through, as the fixture walks it."""
    mid = ((GUARD_A[0] + GUARD_B[0]) / 2.0, (GUARD_A[1] + GUARD_B[1]) / 2.0)
    # The crate is nudged backwards before play and the behind-the-crate stop sits the
    # same distance beyond it, so that stop lands back on the crate's placed X.
    stops = [(START_AT.x, START_AT.y), IN_FRONT, (CRATE_AT[0], CRATE_AT[1]), IN_FRONT,
             (mid[0] - 500.0, mid[1] - 600.0), IN_FRONT,
             (mid[0] + 1700.0, mid[1]), IN_FRONT]
    out = []
    for (ax, ay), (bx, by) in zip(stops, stops[1:]):
        steps = max(2, int(math.hypot(bx - ax, by - ay) / 50.0))
        out += [(ax + k / steps * (bx - ax), ay + k / steps * (by - ay))
                for k in range(steps + 1)]
    return out


def eyes_of(guard):
    """Every eye position and facing the fixture's staging jitter can produce."""
    return [((guard[0] + jx + 40.0, guard[1] + jy), fd)
            for jx in (-JITTER_CM, 0.0, JITTER_CM)
            for jy in (-JITTER_CM, 0.0, JITTER_CM)
            for fd in (-JITTER_DEG, 0.0, JITTER_DEG)]


def could_see(eye, facing_deg, target):
    """Range and cone only -- the two conditions the wall cannot influence."""
    dx, dy = target[0] - eye[0], target[1] - eye[1]
    if math.hypot(dx, dy) > SIGHT_RANGE:
        return False
    rel = (math.degrees(math.atan2(dy, dx)) - facing_deg + 180.0) % 360.0 - 180.0
    return abs(rel) <= SIGHT_HALF_ANGLE + JITTER_DEG


def crosses_wall(eye, target):
    """Where this sightline crosses the wall's plane, or None if it never does."""
    if target[0] <= WALL_X + 1.0 or eye[0] >= WALL_X:
        return None
    return eye[1] + (WALL_X - eye[0]) / (target[0] - eye[0]) * (target[1] - eye[1])


def plan_wall(walked):
    """Solve the wall's span: it must cover every sightline the walled guard could
    otherwise use, at every corner of the jitter box, with margin to spare."""
    crossings = [crosses_wall(eye, t)
                 for eye, fd in eyes_of(GUARD_B)
                 for t in walked if could_see(eye, fd, t)]
    if not crossings or any(c is None for c in crossings):
        fail("the walled guard has a sightline that never reaches the wall's plane; "
             "move the wall or the guards")
    return min(crossings) - JITTER_SLACK, max(crossings) + JITTER_SLACK


def check_staging(walked, wall_lo, wall_hi):
    """The two things the solved wall must not have broken."""
    # (a) The character must never walk INTO the wall.
    for wx, wy in walked:
        if abs(wx - WALL_X) < 100.0 and wall_lo - 60.0 <= wy <= wall_hi + 60.0:
            fail(f"the route passes through the wall at ({wx:.0f}, {wy:.0f}); the "
                 f"character would walk into it")

    # (b) THE SIGNAL. The clear guard must genuinely see the character at the stop the
    # route keeps returning to -- in range, in cone, and past both the wall and the
    # crate -- or nothing ever lights and the task grades nothing.
    for eye, fd in eyes_of(GUARD_A):
        if not could_see(eye, fd, IN_FRONT):
            fail(f"the clear guard cannot see the in-front stop {IN_FRONT} on range "
                 f"and angle alone at jitter corner {eye}, {fd:+.0f}deg")
        cross = crosses_wall(eye, IN_FRONT)
        if cross is not None and wall_lo - JITTER_SLACK <= cross <= wall_hi + JITTER_SLACK:
            fail(f"the wall reaches across the CLEAR guard's view of the in-front "
                 f"stop (crosses at y={cross:.0f}, wall {wall_lo:.0f}..{wall_hi:.0f})")
        frac = (CRATE_AT[0] - eye[0]) / (IN_FRONT[0] - eye[0])
        at_crate = eye[1] + frac * (IN_FRONT[1] - eye[1])
        if abs(at_crate - CRATE_AT[1]) < 100.0 + JITTER_SLACK:
            fail(f"the crate sits in the CLEAR guard's view of the in-front stop "
                 f"(crosses at y={at_crate:.0f}, crate at y={CRATE_AT[1]:.0f})")
    log(f"staging checked over {len(walked)} route samples x the jitter box")


def log(msg):
    unreal.log(f"SIGHTYARD- {msg}")


def fail(msg):
    unreal.log_error(f"SIGHTYARD-ERROR {msg}")
    raise SystemExit(1)


def probe():
    got = {}
    for name, cls in (("les", unreal.LevelEditorSubsystem),
                      ("eas", unreal.EditorActorSubsystem)):
        sub = unreal.get_editor_subsystem(cls)
        if sub is None:
            fail(f"subsystem {cls.__name__} is unavailable in this boot")
        got[name] = sub
    for path in (CUBE, CYL, M_FLOOR, M_STRIPE, M_DARK, M_GLOW):
        if not unreal.EditorAssetLibrary.does_asset_exist(path):
            fail(f"asset missing: {path}")
    for cls_name in ("SightGuardActor", "GuardSightFunctionalTest"):
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
        comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    actor.set_actor_scale3d(scale)
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

    # THE TWO GUARDS. Identical, same facing, nothing distinguishing them.
    for idx, (gx, gy) in enumerate((GUARD_A, GUARD_B)):
        g = eas.spawn_actor_from_class(
            env["SightGuardActor"], unreal.Vector(gx, gy, 0.0),
            unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
        if g is None:
            fail(f"could not place guard {idx}")
        # Labels differ only so a human can tell them apart in the outliner; nothing
        # reads them, and both carry the same single tag from the constructor.
        g.set_actor_label(f"WatchGuard_{idx}")
    log(f"two interchangeable guards at {GUARD_A} and {GUARD_B}, both facing +X")

    walked = route_samples()
    wall_lo, wall_hi = plan_wall(walked)
    # The permanent occluder, spanning exactly what the solved geometry asks for.
    block(env, CUBE, unreal.Vector(WALL_X, (wall_lo + wall_hi) / 2.0, 130.0),
          unreal.Vector(0.4, (wall_hi - wall_lo) / 100.0, 2.6), "BlockerWall", M_DARK)
    log(f"blocker wall solved: x={WALL_X:.0f}, y {wall_lo:.0f}..{wall_hi:.0f} "
        f"({wall_hi - wall_lo:.0f}cm wide)")

    # The movable occluder.
    crate = block(env, CUBE, unreal.Vector(CRATE_AT[0], CRATE_AT[1], 110.0),
                  unreal.Vector(2.0, 2.0, 2.2), "SightCrate", M_DARK)
    crate.tags = ["SightCrate"]
    # MOVABLE, not static: the fixture relocates it before play so its placed
    # coordinates cannot be hard-coded. A static component silently refuses the move.
    crate.static_mesh_component.set_editor_property(
        "mobility", unreal.ComponentMobility.MOVABLE)
    log(f"crate at {CRATE_AT}, MOVABLE so the fixture can relocate it")

    # The two graded numbers, made photographable: cone-edge stripes at +/-45 deg out
    # to 1200, drawn from each guard. No collision -- they are paint, not geometry.
    for gi, (gx, gy) in enumerate((GUARD_A, GUARD_B)):
        for sign in (-1.0, 1.0):
            ang = math.radians(sign * SIGHT_HALF_ANGLE)
            mx = gx + math.cos(ang) * SIGHT_RANGE * 0.5
            my = gy + math.sin(ang) * SIGHT_RANGE * 0.5
            block(env, CUBE, unreal.Vector(mx, my, 1.0),
                  unreal.Vector(SIGHT_RANGE / 100.0, 0.08, 0.02),
                  f"ConeEdge_{gi}_{'L' if sign < 0 else 'R'}", M_GLOW,
                  yaw=sign * SIGHT_HALF_ANGLE, collide=False)
    log(f"cone-edge stripes painted at +/-{SIGHT_HALF_ANGLE:.0f} deg out to "
        f"{SIGHT_RANGE:.0f}")

    start = eas.spawn_actor_from_class(
        unreal.PlayerStart, START_AT, unreal.Rotator(roll=0.0, pitch=0.0, yaw=180.0))
    if start is None:
        fail("could not place PlayerStart")
    start.set_actor_label("PlayerStart")

    # A low back wall and two distinctly sized marker posts.
    block(env, CUBE, unreal.Vector(mid_x, FLOOR_MAX[1] - 20.0, 90.0),
          unreal.Vector(span_x / 100.0, 0.3, 1.8), "Backdrop", M_DARK)
    for idx, (lx, ly) in enumerate(LANDMARKS):
        block(env, CYL, unreal.Vector(lx, ly, 300.0),
              unreal.Vector(1.1 + idx * 0.8, 1.1 + idx * 0.8, 6.0),
              f"Landmark_{idx}", M_GLOW if idx else M_DARK)

    sun = eas.spawn_actor_from_class(
        unreal.DirectionalLight, unreal.Vector(mid_x, mid_y, 900.0),
        unreal.Rotator(roll=0.0, pitch=-50.0, yaw=-120.0))
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

    eas.spawn_actor_from_class(
        env["GuardSightFunctionalTest"], unreal.Vector(-800.0, -800.0, 100.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0)).set_actor_label(
            "GuardSightFunctionalTest")

    # NO game mode is named on purpose -- the level inherits the project default, whose
    # pawn is the stock mannequin and whose controller carries IMC_Default.
    world = unreal.EditorLevelLibrary.get_editor_world()
    if world.get_world_settings().get_editor_property("default_game_mode") is not None:
        fail("world settings already name a game mode; this level must inherit the "
             "project default so the play lane comes for free")
    log("world settings: no game mode named (inherits BP_ThirdPersonGameMode)")

    lit = [a for a in eas.get_all_level_actors()
           if a.get_class().get_name() in ("DirectionalLight", "SkyLight")]
    if len(lit) < 2:
        fail(f"level has {len(lit)} light actor(s); a capture still would be black")

    guards = [a for a in eas.get_all_level_actors() if a.actor_has_tag("SightGuard")]
    if len(guards) != 2:
        fail(f"{len(guards)} guards tagged SightGuard, expected 2")
    # The guards must be INTERCHANGEABLE: identical tag sets and identical facing. If
    # they were not, a submission could tell them apart without looking at anything.
    tagsets = {tuple(sorted(str(t) for t in g.tags)) for g in guards}
    if len(tagsets) != 1:
        fail(f"the two guards carry different tag sets {tagsets}; they must be "
             f"indistinguishable")
    yaws = {round(g.get_actor_rotation().yaw, 3) for g in guards}
    if len(yaws) != 1:
        fail(f"the two guards face different ways {yaws}; they must be identical")
    log("the two guards are indistinguishable: same tags, same facing")

    crates = [a for a in eas.get_all_level_actors() if a.actor_has_tag("SightCrate")]
    if len(crates) != 1:
        fail(f"{len(crates)} actors tagged SightCrate, expected 1")
    if crates[0].static_mesh_component.get_editor_property("mobility") !=             unreal.ComponentMobility.MOVABLE:
        fail("the crate is not MOVABLE; the fixture relocates it before play and a "
             "static component would silently ignore the move")


    check_staging(walked, wall_lo, wall_hi)

    if not les.save_current_level():
        fail("save_current_level() returned False")
    log(f"SAVED {MAP_PKG}")


main()

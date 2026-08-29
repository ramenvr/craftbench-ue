"""Authors L_NightYard for t2-guard-goes-to-where-it-last-saw-you.

    UnrealEditor-Cmd.exe <ThirdPerson.uproject> -run=pythonscript \
        -script="<abs path to this file>" -nullrhi -unattended -nopause \
        -log -stdout -FullStdOutLogOutput

THE YARD IN ONE PARAGRAPH. Two watchmen stand on two posts, one north of the middle
lane and one south of it, both seeing 2000 uu. Each lane runs 1800 uu from ITS OWN
watchman's post and 3000 uu from the other's, so exactly one of them can reach a lane
with its own sight -- the second is kept blind by DISTANCE, never by a wall, because a
wall that hid the lane from it would also block its straight walk to the spot it gets
radioed. At the far end of each lane stands a three-sided alcove whose mouth faces AWAY
from the lane. The character outruns a watchman (500 uu/s against 300), so sight breaks
by range with the watchman about 2400 uu behind, and then the character runs on past the
alcove, round the back and in -- from where nothing on the lane side can see it. That is
what lets a watchman search the last-seen spot honestly for six seconds without the
search collapsing back into a chase, and it is what makes a watchman that walks at the
character's LIVE position end up a few hundred uu from somebody it cannot see.

WHY THE ALCOVE MOUTH FACES AWAY. An earlier cut had the mouth facing the lane. A
watchman standing anywhere past the alcove could then see straight in, so the character
was never really hidden and the fixture's own staging check refused the level. The mouth
now faces the far side: the south wall blocks every line from the lane, and the two side
walls block the ends.

WHY THE WALLS ARE MOVABLE. The fixture shifts each alcove along X by a per-run jitter
before its leg, and PIE scores moving a STATIC actor as a failed test.

This level names NO game mode: it inherits the project default, so the play lane comes
for free (the 2026-08-17 unplayable-play-lane finding).

Every Rotator is built with KEYWORDS -- unreal.Rotator's positional order is
(roll, pitch, yaw).
"""
import math

import unreal

TASK = "t2-guard-goes-to-where-it-last-saw-you"
MAP_PKG = f"/Game/Maps/{TASK}/L_NightYard"

FLOOR_MIN = (-9200.0, -4000.0)
FLOOR_MAX = (9200.0, 4000.0)
STRIPE_EVERY = 800.0

# The two watchmen. Numbers written ON the placed instance, not just on the class, so a
# submission that edits the class default cannot change what the yard is set to.
POSTS = ((0.0, 2400.0), (0.0, -2400.0))
WALK_PACE = 300.0            # uu/s. Slower than the character's 500 on purpose: a
                             # watchman can never catch a moving character, so sight
                             # breaks by range with a real gap behind it.
SIGHT_RANGE = 2400.0         # uu. Must sit BETWEEN the near lane offset (1800) and the
                             # far one (3000) -- that inequality is the whole reason
                             # exactly one watchman can see each lane.
LANE_Y = 600.0
CHAR_STAND_Z = 96.0          # capsule half-height, so the feet are on the floor

# Alcove A (north-east), and its 180-degree rotation in the south-west. Three walls,
# 300 thick and 600 tall, open on the side facing AWAY from the lane.
ALCOVE_CX = 6800.0
ALCOVE_NEAR_Y = 1200.0       # the side facing the lane -- closed
ALCOVE_FAR_Y = 2400.0        # the side facing away -- open
ALCOVE_HALF_W = 900.0
WALL_T = 300.0
WALL_H = 600.0

START_AT = (-2600.0, LANE_Y)

CUBE = "/Engine/BasicShapes/Cube.Cube"
CYL = "/Engine/BasicShapes/Cylinder.Cylinder"
M_FLOOR = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray"
M_STRIPE = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02"
M_DARK = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"
M_GLOW = "/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT"
M_HAZARD = "/Game/Variant_Combat/Materials/M_Lava"

RING_SEGMENTS = 48


def log(msg):
    unreal.log(f"NIGHTYARD- {msg}")


def fail(msg):
    unreal.log_error(f"NIGHTYARD-ERROR {msg}")
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
    for cls_name in ("YardWatchmanCharacter", "GuardLastSeenFunctionalTest"):
        if not hasattr(unreal, cls_name):
            fail(f"class {cls_name} is not exposed to python - is the module built?")
        got[cls_name] = getattr(unreal, cls_name)
    log(f"probe OK: {sorted(got)}")
    return got


def block(env, mesh, loc, scale, label, material=None, yaw=0.0, collide=True,
          movable=False, tags=None):
    actor = env["eas"].spawn_actor_from_class(
        unreal.StaticMeshActor, loc, unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
    if actor is None:
        fail(f"could not spawn {label}")
    actor.set_actor_label(label)
    comp = actor.static_mesh_component
    comp.set_static_mesh(unreal.EditorAssetLibrary.load_asset(mesh))
    comp.set_editor_property(
        "mobility",
        unreal.ComponentMobility.MOVABLE if movable else unreal.ComponentMobility.STATIC)
    if material:
        comp.set_material(0, unreal.EditorAssetLibrary.load_asset(material))
    if not collide:
        # The PROFILE, not just the enum: set_collision_enabled alone did not survive
        # into a saved level on the marked-ground task, and paint that quietly blocks is
        # indistinguishable from a bug in the submission.
        comp.set_collision_profile_name("NoCollision")
        comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    actor.set_actor_scale3d(scale)
    if tags:
        actor.tags = [unreal.Name(t) for t in tags]
    return actor


# ---------------------------------------------------------------------------
# Geometry, solved from the layout rather than hand-tuned
# ---------------------------------------------------------------------------

def alcove_boxes(sign):
    """The three wall footprints for one alcove, as (xmin, xmax, ymin, ymax).

    sign = +1 for the north-east alcove, -1 for its 180-degree rotation.
    """
    cx = ALCOVE_CX * sign
    near = ALCOVE_NEAR_Y * sign
    far = ALCOVE_FAR_Y * sign
    ylo, yhi = min(near, far), max(near, far)
    closed = (min(near, near + WALL_T * sign), max(near, near + WALL_T * sign))
    return {
        "closed": (cx - ALCOVE_HALF_W, cx + ALCOVE_HALF_W, closed[0], closed[1]),
        "left": (cx - ALCOVE_HALF_W, cx - ALCOVE_HALF_W + WALL_T, ylo, yhi),
        "right": (cx + ALCOVE_HALF_W - WALL_T, cx + ALCOVE_HALF_W, ylo, yhi),
    }


def box_union(boxes):
    return (min(b[0] for b in boxes), max(b[1] for b in boxes),
            min(b[2] for b in boxes), max(b[3] for b in boxes))


def seg_hits_box(p, q, b):
    """2D segment vs axis-aligned box (slab test) -- the same question the fixture asks
    the physics scene, answered here on paper so the level can refuse to save."""
    xmin, xmax, ymin, ymax = b
    t0, t1 = 0.0, 1.0
    for lo, hi, pv, dv in ((xmin, xmax, p[0], q[0] - p[0]),
                           (ymin, ymax, p[1], q[1] - p[1])):
        if abs(dv) < 1e-9:
            if pv < lo or pv > hi:
                return False
        else:
            a, c = (lo - pv) / dv, (hi - pv) / dv
            if a > c:
                a, c = c, a
            t0, t1 = max(t0, a), min(t1, c)
            if t0 > t1:
                return False
    return True


def clearance(p, boxes):
    best = 1.0e9
    for xmin, xmax, ymin, ymax in boxes:
        dx = max(xmin - p[0], 0.0, p[0] - xmax)
        dy = max(ymin - p[1], 0.0, p[1] - ymax)
        best = min(best, math.hypot(dx, dy))
    return best


def route_for(sign, boxes):
    """The waypoints the fixture will derive from these walls, re-derived here."""
    u = box_union([boxes["closed"], boxes["left"], boxes["right"]])
    mid_x = 0.5 * (u[0] + u[1])
    turn_x = u[1] + 500.0 if sign > 0 else u[0] - 500.0
    top_y = u[3] + 500.0 if sign > 0 else u[2] - 500.0
    hide_y = u[3] - 550.0 if sign > 0 else u[2] + 550.0
    lane = LANE_Y * sign
    return [(-2600.0 * sign, lane), (turn_x, lane), (turn_x, top_y),
            (mid_x, top_y), (mid_x, hide_y)]


def check_geometry():
    """What has to be true before this level is worth saving. Everything here is the
    same question the fixture asks at run time; a level that fails it would abort the
    run as a staging fault instead of grading anybody."""
    all_boxes = []
    for sign in (1, -1):
        b = alcove_boxes(sign)
        all_boxes += [b["closed"], b["left"], b["right"]]

    # (1) EXACTLY ONE WATCHMAN PER LANE, by distance, with margin. This inequality is
    #     the task: if it fails, either nobody ever sees the character or the radio
    #     never has anything to carry.
    for sign in (1, -1):
        lane = LANE_Y * sign
        near = min(abs(lane - py) for _, py in POSTS)
        far = max(abs(lane - py) for _, py in POSTS)
        if not (near + 200.0 < SIGHT_RANGE < far - 200.0):
            fail(f"lane y={lane:.0f} sits {near:.0f} uu from the near post and "
                 f"{far:.0f} uu from the far one, and the watchmen see {SIGHT_RANGE:.0f} "
                 f"uu. The sight range has to fall between those two with room to "
                 f"spare, or the second watchman is not blind")
        # and the in-view run must be long enough that "first spotted" and "last seen"
        # are nowhere near each other
        run = 2.0 * math.sqrt(max(SIGHT_RANGE ** 2 - near ** 2, 0.0))
        if run < 1500.0:
            fail(f"a watchman sees only {run:.0f} uu of its own lane; the character has "
                 f"to be in view for at least 1500 uu or where it was FIRST spotted and "
                 f"where it was LAST seen are the same answer")

    # (2) THE CHARACTER OUTRUNS A WATCHMAN. Without this sight never breaks by range,
    #     the watchman arrives on top of the character, and the whole task collapses.
    if WALK_PACE * 1.4 + 60.0 >= 500.0:
        fail(f"a watchman walks at {WALK_PACE:.0f} uu/s and the character does 500; the "
             f"gate that says a watchman only ever walked would then permit it to "
             f"outrun the character and sight would never break")

    # (3) THE DRIVE NEVER SCRAPES A WALL.
    for sign in (1, -1):
        boxes = alcove_boxes(sign)
        wp = route_for(sign, boxes)
        for a, b in zip(wp, wp[1:]):
            for k in range(41):
                p = (a[0] + (b[0] - a[0]) * k / 40.0, a[1] + (b[1] - a[1]) * k / 40.0)
                c = clearance(p, all_boxes)
                if c < 250.0:
                    fail(f"the drive passes {c:.0f} uu from a wall at "
                         f"({p[0]:.0f}, {p[1]:.0f}); the character would scrape it")

    # (4) THE HIDING PLACE IS HIDDEN -- from both posts and from the whole band a
    #     watchman could be searching. This is what makes a six-second search possible
    #     at all: a watchman standing on the last-seen spot must not be able to see
    #     where the character actually went.
    for sign in (1, -1):
        boxes = alcove_boxes(sign)
        hide = route_for(sign, boxes)[-1]
        lane = LANE_Y * sign
        watchers = [(px, py) for px, py in POSTS]
        for k in range(-34, 35):
            for j in (-1, 0, 1):
                watchers.append((k * 250.0 * sign, lane + j * 700.0))
        for w in watchers:
            if math.hypot(w[0] - hide[0], w[1] - hide[1]) > SIGHT_RANGE:
                continue          # out of range from there, so hidden anyway
            if not any(seg_hits_box(w, hide, b) for b in all_boxes):
                fail(f"the hiding place ({hide[0]:.0f}, {hide[1]:.0f}) can be seen from "
                     f"({w[0]:.0f}, {w[1]:.0f}), which is somewhere a watchman searching "
                     f"the last-seen spot could legitimately be standing")

    # (5) NOT CHECKED HERE, and deliberately so. The distance from the hiding place to
    #     the LAST-SEEN SPOT depends on how far the watchman chased before losing the
    #     character, which is the submission's business, so no number in this file can
    #     pin it down. What makes that safe is the shape of the blind rule rather than
    #     the shape of the yard: a watchman within twelve metres of the spot it was told
    #     about is exempt from it, and an honest searcher stays within seven, so it can
    #     never be caught by the rule for standing where the prompt sent it. Measured on
    #     the reference: the nearest a correct watchman comes to the hidden character
    #     while blind and away from the spot is about 2400 uu, against a floor of 1200.

    # (6) EVERYTHING FITS ON THE FLOOR.
    for sign in (1, -1):
        for p in route_for(sign, alcove_boxes(sign)):
            if not (FLOOR_MIN[0] + 200 < p[0] < FLOOR_MAX[0] - 200
                    and FLOOR_MIN[1] + 200 < p[1] < FLOOR_MAX[1] - 200):
                fail(f"a drive waypoint ({p[0]:.0f}, {p[1]:.0f}) falls off the floor")
    log("geometry checked: one watchman per lane by distance, the character outruns "
        "them both, the drive clears every wall by 250 uu, and each hiding place is "
        "out of sight from both posts and from the whole search band")


def paint_ring(env, centre, radius, label, material):
    """A watchman's sight range, drawn on the floor, so a human can see why one of them
    can reach the lane and the other cannot."""
    for k in range(RING_SEGMENTS):
        ang = 2.0 * math.pi * k / RING_SEGMENTS
        seg = 2.0 * math.pi * radius / RING_SEGMENTS * 0.7
        block(env, CUBE,
              unreal.Vector(centre[0] + math.cos(ang) * radius,
                            centre[1] + math.sin(ang) * radius, 2.0),
              unreal.Vector(0.12, seg / 100.0, 0.04),
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
    mid_x = 0.5 * (FLOOR_MAX[0] + FLOOR_MIN[0])
    mid_y = 0.5 * (FLOOR_MAX[1] + FLOOR_MIN[1])
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
    # The two lanes, painted, so a reviewer can see the route the character walks.
    for sign, name in ((1, "North"), (-1, "South")):
        block(env, CUBE, unreal.Vector(mid_x, LANE_Y * sign, 2.0),
              unreal.Vector(span_x / 100.0, 0.30, 0.04), f"Lane_{name}", M_DARK,
              collide=False)
    log(f"floor {span_x:.0f}x{span_y:.0f} + {n} stripes + 2 painted lanes")

    # The alcoves. MOVABLE, because the fixture slides each one along X before its leg.
    for sign, name in ((1, "North"), (-1, "South")):
        boxes = alcove_boxes(sign)
        for part, b in boxes.items():
            cx = 0.5 * (b[0] + b[1])
            cy = 0.5 * (b[2] + b[3])
            block(env, CUBE, unreal.Vector(cx, cy, WALL_H * 0.5),
                  unreal.Vector((b[1] - b[0]) / 100.0, (b[3] - b[2]) / 100.0,
                                WALL_H / 100.0),
                  f"YardWall_{name}_{part}", M_DARK, movable=True, tags=["YardWall"])
    log("two alcoves placed, six walls, all MOVABLE and tagged YardWall")

    # The watchmen. Both numbers are set on the PLACED INSTANCE, so they are baked into
    # this map and a submission editing the class default cannot change what the yard
    # asks of them.
    for idx, (px, py) in enumerate(POSTS):
        w = eas.spawn_actor_from_class(
            env["YardWatchmanCharacter"], unreal.Vector(px, py, CHAR_STAND_Z),
            unreal.Rotator(roll=0.0, pitch=0.0, yaw=-90.0 if py > 0 else 90.0))
        if w is None:
            fail(f"could not place watchman {idx + 1}")
        w.set_actor_label(f"YardWatchman_{idx + 1}")
        w.set_editor_property("walk_pace_uu_per_second", WALK_PACE)
        w.set_editor_property("sight_range_uu", SIGHT_RANGE)
        paint_ring(env, (px, py), SIGHT_RANGE, f"SightRing_{idx + 1}",
                   M_GLOW if idx == 0 else M_HAZARD)
        # A lit post to stand on, so "back on its post" reads at a glance.
        block(env, CYL, unreal.Vector(px, py, 6.0), unreal.Vector(3.2, 3.2, 0.12),
              f"Post_{idx + 1}", M_GLOW if idx == 0 else M_HAZARD, collide=False)
    log(f"two watchmen placed at {POSTS}, pace {WALK_PACE:.0f}, range {SIGHT_RANGE:.0f}")

    start = eas.spawn_actor_from_class(
        unreal.PlayerStart, unreal.Vector(START_AT[0], START_AT[1], 120.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if start is None:
        fail("could not place PlayerStart")
    start.set_actor_label("PlayerStart")

    block(env, CUBE, unreal.Vector(mid_x, FLOOR_MAX[1] - 40.0, 300.0),
          unreal.Vector(span_x / 100.0, 0.6, 6.0), "Backdrop", M_DARK)
    for idx, lx in enumerate((FLOOR_MIN[0] + 400.0, 0.0, FLOOR_MAX[0] - 400.0)):
        block(env, CYL, unreal.Vector(lx, FLOOR_MAX[1] - 700.0, 400.0),
              unreal.Vector(1.2 + idx * 0.7, 1.2 + idx * 0.7, 8.0), f"Landmark_{idx}",
              M_GLOW if idx % 2 else M_HAZARD)

    sun = eas.spawn_actor_from_class(
        unreal.DirectionalLight, unreal.Vector(mid_x, mid_y, 1400.0),
        unreal.Rotator(roll=0.0, pitch=-46.0, yaw=-125.0))
    sky = eas.spawn_actor_from_class(
        unreal.SkyLight, unreal.Vector(mid_x, mid_y, 1400.0),
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

    fixture = eas.spawn_actor_from_class(
        env["GuardLastSeenFunctionalTest"],
        unreal.Vector(FLOOR_MIN[0] + 400.0, FLOOR_MIN[1] + 400.0, 160.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if fixture is None:
        fail("could not place the functional test")
    fixture.set_actor_label("GuardLastSeenFunctionalTest")

    world = unreal.EditorLevelLibrary.get_editor_world()
    if world.get_world_settings().get_editor_property("default_game_mode") is not None:
        fail("world settings already name a game mode; this level must inherit the "
             "project default so the play lane comes for free")
    log("world settings: no game mode named (inherits BP_ThirdPersonGameMode)")

    # ---- read the level back rather than trusting what was asked for ----------
    placed = eas.get_all_level_actors()
    watchmen = [a for a in placed if a.actor_has_tag("YardWatchman")]
    walls = [a for a in placed if a.actor_has_tag("YardWall")]
    if len(watchmen) != 2:
        fail(f"{len(watchmen)} actor(s) tagged YardWatchman, expected 2")
    if len(walls) != 6:
        fail(f"{len(walls)} actor(s) tagged YardWall, expected 6")
    for w in watchmen:
        pace = float(w.get_editor_property("walk_pace_uu_per_second"))
        rng = float(w.get_editor_property("sight_range_uu"))
        if abs(pace - WALK_PACE) > 0.5 or abs(rng - SIGHT_RANGE) > 0.5:
            fail(f"{w.get_actor_label()} reads back pace {pace:.0f} range {rng:.0f}; "
                 f"the numbers did not survive placement, and every allowance the "
                 f"fixture grants is measured from them")
        origin, extent = w.get_actor_bounds(only_colliding_components=True)
        if origin.z - extent.z < -2.0:
            fail(f"{w.get_actor_label()} reaches down to z={origin.z - extent.z:.1f}, "
                 f"below the floor, so it is penetrating from frame one")
    for a in walls:
        comp = a.static_mesh_component
        if comp.get_editor_property("mobility") != unreal.ComponentMobility.MOVABLE:
            fail(f"{a.get_actor_label()} is not MOVABLE; the fixture slides the alcoves "
                 f"between its legs and PIE scores moving a static actor as a FAIL")
    north = [a for a in walls if a.get_actor_location().y >= 0.0]
    south = [a for a in walls if a.get_actor_location().y < 0.0]
    if len(north) != 3 or len(south) != 3:
        fail(f"the walls split {len(north)}/{len(south)} north/south and the fixture "
             f"tells the two alcoves apart by which side of the yard they stand on")
    lit = [a for a in placed
           if a.get_class().get_name() in ("DirectionalLight", "SkyLight")]
    if len(lit) < 2:
        fail(f"level has {len(lit)} light actor(s); a capture still would be black")
    log(f"read back: 2 watchmen (pace {WALK_PACE:.0f}, range {SIGHT_RANGE:.0f}), "
        f"6 movable walls split 3/3 north and south, lighting present")

    if not les.save_current_level():
        fail("save_current_level() returned False")
    log(f"SAVED {MAP_PKG}")


main()

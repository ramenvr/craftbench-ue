"""Authors L_TrestleYard for t2-bridge-only-holds-what-it-can-bear.

    UnrealEditor-Cmd.exe <ThirdPerson.uproject> -run=pythonscript \
        -script="<abs path to this file>" -nullrhi -unattended -nopause \
        -log -stdout -FullStdOutLogOutput

TWO FOOTBRIDGES RATED DIFFERENTLY, EACH ON PIERS WITH A RAMP UP AT EITHER END. The
yard puts crates on them, takes crates off them, and walks a character over them. Each
span holds what it is rated for, sags in proportion to how much of that rating is in
use, gives way when the total goes over, stays down while anything is still on the
fallen deck and heaves back up once it is clear.

EVERY NUMBER IN HERE IS RE-STAMPED BY THE FIXTURE AT RUN TIME. What is baked into the
map is a sane set for a human who opens the level and plays it by hand; the graded run
draws its own and writes them in before the first BeginPlay. So this script's job is
GEOMETRY, not values -- and the geometry is solved from the layout rather than typed in,
so a re-stage cannot quietly break a clearance the fixture depends on.

WHAT THIS SCRIPT REFUSES TO SAVE (each one has cost somebody a day somewhere):
  * a ramp steeper than the character can walk up, or a ramp/deck joint that becomes a
    WALL rather than a step once the deck is fully sagged;
  * a fallen deck whose lip is taller than the character can step back over, which would
    strand the drive on a collapsed span until the time limit;
  * a crate slot near a deck edge -- the prompt promises nothing is ever set down
    half-on, and the fixture's occupancy band assumes it;
  * anything solid inside the sideways exit lanes, or underneath a deck (a fallen deck
    has to reach the ground);
  * anything solid within 150 cm of a leg of the fixture's walk;
  * a level that names a game mode, which silently kills Enhanced Input and makes the
    level unplayable by hand while grading byte-identically.

The trestle posts under each deck are DELIBERATELY NON-COLLIDING. They are there so a
human sees a bridge; a colliding post would either block a sideways exit or stop a
fallen deck reaching the ground, and both fail a correct submission.

Every Rotator is built with KEYWORDS -- unreal.Rotator's positional order is
(roll, pitch, yaw).
"""
import math

import unreal

TASK = "t2-bridge-only-holds-what-it-can-bear"
MAP_PKG = f"/Game/Maps/{TASK}/L_TrestleYard"

# ---------------------------------------------------------------------------------
# The layout. Everything else is solved from these.
# ---------------------------------------------------------------------------------
FLOOR_MIN = (-3800.0, -2800.0)
FLOOR_MAX = (3800.0, 2800.0)
STRIPE_EVERY = 400.0

DECK_X = 900.0                 # along the span
DECK_Y = 700.0                 # across it
DECK_THICK = 40.0
DECK_TOP_Z = 240.0             # top of the deck at rest
FULL_SAG_CM = 30.0             # how far it sits down at exactly its rating
GIVE_WAY_DROP_CM = 200.0       # how far it drops when it gives way

RAMP_RUN = 720.0               # horizontal run of each approach ramp
# Between a ramp's top edge and the deck's end. Not cosmetic: a 40 cm thick slab
# tilted 18.4 degrees overhangs its own top edge by DECK_THICK*sin(theta) = 12.6 cm at
# the underside, and a ramp whose corner reaches in under the deck is something solid
# inside the volume a fallen deck has to occupy. check_geometry() solves the minimum.
RAMP_GAP = 20.0

CRATE_SIDE = 120.0
CRATE_LANE_OFFSET = -200.0     # crates go this side of a deck's centre line
WALK_LANE_OFFSET = 200.0       # and the character walks the other side
CRATE_SLOT_X = (-250.0, 150.0) # the two on-deck slots, relative to the deck centre

# (label, x, y, rated load). The fixture re-stamps both ratings; these are what a human
# playing the level by hand gets, and they must already satisfy every claim below.
SPANS = (
    ("WestSpan", 0.0, -900.0, 600.0),
    ("EastSpan", 0.0, 900.0, 340.0),
)
# (label, x, y, weight). Sorted by Y, the fixture calls these the sack, the keg and the
# anvil, in that order.
BANK = (
    ("YardLoad_Sack", -2600.0, -700.0, 140.0),
    ("YardLoad_Keg", -2600.0, 0.0, 230.0),
    ("YardLoad_Anvil", -2600.0, 700.0, 480.0),
)
START_AT = (-2000.0, 0.0)

# Engine facts this geometry is checked against, read from
# <UE_ROOT>/Engine/Source/Runtime/Engine/Private/Components/CharacterMovementComponent.cpp
# (MaxStepHeight = 45.0f at :689, SetWalkableFloorZ(0.71f) at :682).
MAX_STEP_HEIGHT = 45.0
WALKABLE_FLOOR_Z = 0.71
CAPSULE_RADIUS = 42.0          # ThirdPersonCharacter.cpp InitCapsuleSize(42, 96)

ROUTE_CLEARANCE = 150.0        # nothing solid this close to a leg of the walk
SLOT_EDGE_MARGIN = 90.0        # a crate slot is at least this far inside the deck

CUBE = "/Engine/BasicShapes/Cube.Cube"
CYL = "/Engine/BasicShapes/Cylinder.Cylinder"
M_FLOOR = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray"
M_STRIPE = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02"
M_DARK = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"
M_GLOW = "/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT"
M_HAZARD = "/Game/Variant_Combat/Materials/M_Lava"

# Every SOLID thing this script places, as (label, xmin, xmax, ymin, ymax, zmin, zmax).
# The clearance checks read this rather than a remembered list.
SOLIDS = []
# Things the character is MEANT to walk on or over.
WALKABLE_LABELS = set()


def log(msg):
    unreal.log(f"TRESTLE- {msg}")


def fail(msg):
    unreal.log_error(f"TRESTLE-ERROR {msg}")
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
    for cls_name in ("BridgeSpanActor", "YardLoadActor", "TrestleLoadFunctionalTest"):
        if not hasattr(unreal, cls_name):
            fail(f"class {cls_name} is not exposed to python - is the module built?")
        got[cls_name] = getattr(unreal, cls_name)
    log(f"probe OK: {sorted(got)}")
    return got


def block(env, mesh, loc, scale, label, material=None, pitch=0.0, yaw=0.0,
          collide=True, walkable=False, half=None):
    """Places a static block and, when it is solid, records its footprint."""
    actor = env["eas"].spawn_actor_from_class(
        unreal.StaticMeshActor, unreal.Vector(loc[0], loc[1], loc[2]),
        unreal.Rotator(roll=0.0, pitch=pitch, yaw=yaw))
    if actor is None:
        fail(f"could not spawn {label}")
    actor.set_actor_label(label)
    comp = actor.static_mesh_component
    comp.set_static_mesh(unreal.EditorAssetLibrary.load_asset(mesh))
    comp.set_editor_property("mobility", unreal.ComponentMobility.STATIC)
    if material:
        comp.set_material(0, unreal.EditorAssetLibrary.load_asset(material))
    if not collide:
        # The PROFILE, not just the enum: set_collision_enabled alone has been seen not
        # to survive into a saved level, and paint that quietly blocks is
        # indistinguishable from a bug in the submission.
        comp.set_collision_profile_name("NoCollision")
        comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    actor.set_actor_scale3d(unreal.Vector(scale[0], scale[1], scale[2]))
    if collide:
        hx, hy, hz = half if half else (scale[0] * 50.0, scale[1] * 50.0,
                                        scale[2] * 50.0)
        SOLIDS.append((label, loc[0] - hx, loc[0] + hx, loc[1] - hy, loc[1] + hy,
                       loc[2] - hz, loc[2] + hz))
        if walkable:
            WALKABLE_LABELS.add(label)
    return actor


def ramp_pose(low_x, high_x, y, top_z):
    """A ramp slab whose TOP SURFACE runs from (low_x, 0) to (high_x, top_z).

    Solved, not typed: the slab is 40 thick, so its centre has to be pushed back along
    its own local down-axis or the ramp's foot becomes a lip and its head becomes a
    step down onto the deck. Returns the true axis-aligned half-extents too, because
    the clearance checks are only as good as the footprint they are given.
    """
    run = abs(high_x - low_x)
    length = math.hypot(run, top_z)
    rising_toward_plus_x = high_x > low_x
    theta = math.atan2(top_z, run)
    pitch = math.degrees(theta) if rising_toward_plus_x else -math.degrees(theta)
    # Local up for pitch p (yaw 0) is (-sin p, 0, cos p).
    up = (-math.sin(math.radians(pitch)), 0.0, math.cos(math.radians(pitch)))
    mid = ((low_x + high_x) / 2.0, y, top_z / 2.0)
    half_thick = DECK_THICK / 2.0
    centre = (mid[0] - up[0] * half_thick, y, mid[2] - up[2] * half_thick)
    half = (length / 2.0 * math.cos(theta) + half_thick * math.sin(theta),
            DECK_Y / 2.0,
            length / 2.0 * math.sin(theta) + half_thick * math.cos(theta))
    return centre, pitch, length, half


def route_waypoints():
    """The fixture's walk, re-derived here so the clearance check tests the real thing.
    Mirrors ATrestleLoadFunctionalTest::BuildRoute."""
    half_x = DECK_X / 2.0
    half_y = DECK_Y / 2.0
    mid_x = SPANS[0][1]
    mid_y = (SPANS[0][2] + SPANS[1][2]) / 2.0
    ramp_foot = mid_x + half_x + 800.0
    left_foot = mid_x - half_x - 800.0
    corridor = mid_x + half_x + 1350.0
    yard = mid_x - half_x - 1550.0
    walk = [SPANS[i][2] + WALK_LANE_OFFSET for i in (0, 1)]
    exit_y = [SPANS[i][2] + half_y + 550.0 for i in (0, 1)]
    return [
        (yard, mid_y), (left_foot, walk[0]), (mid_x, walk[0]), (ramp_foot, walk[0]),
        (ramp_foot, walk[0]), (mid_x, walk[0]), (mid_x, exit_y[0]),
        (mid_x, exit_y[0]), (corridor, mid_y), (ramp_foot, walk[0]),
        (mid_x, walk[0]), (ramp_foot, walk[0]), (ramp_foot, walk[0]),
        (corridor, mid_y), (ramp_foot, walk[1]), (mid_x, walk[1]),
        (ramp_foot, walk[1]), (ramp_foot, walk[1]), (mid_x, walk[1]),
        (mid_x, exit_y[1]), (corridor, exit_y[1]), (corridor, mid_y),
        (ramp_foot, walk[0]), (mid_x, walk[0]), (mid_x, exit_y[0]),
        (mid_x, exit_y[0]), (yard, mid_y),
    ]


def check_geometry():
    """Everything that has to be true of the LAYOUT before a single actor is spawned."""
    half_x = DECK_X / 2.0
    half_y = DECK_Y / 2.0

    # 1. The ramps are walkable at all.
    slope = math.degrees(math.atan2(DECK_TOP_Z, RAMP_RUN))
    walkable_limit = math.degrees(math.acos(WALKABLE_FLOOR_Z))
    if slope >= walkable_limit - 2.0:
        fail(f"the approach ramps rise {slope:.1f} degrees and the character can only "
             f"walk a floor up to {walkable_limit:.1f} degrees; the drive would slide "
             f"back down and never reach a deck")

    # 2. A fully sagged deck must still be a STEP down off the ramp, not a wall, in
    #    both directions.
    if FULL_SAG_CM >= MAX_STEP_HEIGHT - 5.0:
        fail(f"a fully laden deck sits {FULL_SAG_CM:.0f} cm below its ramps and the "
             f"character can only step {MAX_STEP_HEIGHT:.0f} cm; the ramp/deck joint "
             f"would become a wall exactly when a span is carrying the most")

    # 3. A fallen deck rests on the floor, and its lip has to be steppable in BOTH
    #    directions or the sideways exit strands the drive on the collapsed span.
    fallen_top = DECK_TOP_Z - GIVE_WAY_DROP_CM
    if abs(fallen_top - DECK_THICK) > 1.0:
        fail(f"a deck that gives way drops to a top of z={fallen_top:.0f} but the deck "
             f"is {DECK_THICK:.0f} thick, so it does not come to rest on the floor")
    if fallen_top > MAX_STEP_HEIGHT:
        fail(f"the lip off a fallen deck is {fallen_top:.0f} cm and the character can "
             f"step {MAX_STEP_HEIGHT:.0f} cm; the walk could not get back on")

    # 3b. A tilted slab overhangs its own top edge underneath. The gap between a
    #     ramp's top edge and the deck's end has to cover that overhang, or the ramp's
    #     underside corner reaches in under the deck -- into the volume a fallen deck
    #     and whoever rode it down have to occupy.
    theta = math.atan2(DECK_TOP_Z, RAMP_RUN)
    overhang = DECK_THICK * math.sin(theta)
    if RAMP_GAP - overhang < 5.0:
        fail(f"the ramps stop {RAMP_GAP:.0f} cm short of the decks, and a "
             f"{DECK_THICK:.0f} cm slab at {math.degrees(theta):.1f} degrees overhangs "
             f"its own top edge by {overhang:.1f} cm; the ramp would reach in under "
             f"the deck")
    if RAMP_GAP > MAX_STEP_HEIGHT:
        fail(f"the {RAMP_GAP:.0f} cm gap between a ramp and its deck is wider than the "
             f"character can stride")

    # 4. Crate slots are squarely on the deck -- the prompt promises it and the
    #    fixture's occupancy band assumes it.
    for slot in CRATE_SLOT_X:
        edge = half_x - (abs(slot) + CRATE_SIDE / 2.0)
        if edge < SLOT_EDGE_MARGIN:
            fail(f"a crate slot at x={slot:.0f} leaves only {edge:.0f} cm to the deck "
                 f"edge; nothing may be set down anywhere near an edge")
    edge_y = half_y - (abs(CRATE_LANE_OFFSET) + CRATE_SIDE / 2.0)
    if edge_y < SLOT_EDGE_MARGIN:
        fail(f"the crate lane leaves only {edge_y:.0f} cm to the deck edge")
    edge_walk = half_y - (abs(WALK_LANE_OFFSET) + CAPSULE_RADIUS)
    if edge_walk < SLOT_EDGE_MARGIN:
        fail(f"the character's lane leaves only {edge_walk:.0f} cm to the deck edge")

    # 5. The two crates on one deck, and the character beside them, never touch.
    apart = abs(CRATE_SLOT_X[1] - CRATE_SLOT_X[0]) - CRATE_SIDE
    if apart < 100.0:
        fail(f"the two on-deck crate slots leave {apart:.0f} cm between the crates")
    lane_gap = abs(WALK_LANE_OFFSET - CRATE_LANE_OFFSET) - CRATE_SIDE / 2.0 \
        - CAPSULE_RADIUS
    if lane_gap < 200.0:
        fail(f"the character passes {lane_gap:.0f} cm from a crate on the deck; the "
             f"walk must never shove the cargo")

    # 6. The two staged ratings have to be far enough apart that one number cannot be
    #    right about both. (The fixture re-stamps and re-checks this at run time; the
    #    baked pair is what a human playing by hand gets.)
    rw, re_ = SPANS[0][3], SPANS[1][3]
    if abs(rw - re_) < 0.25 * max(rw, re_):
        fail(f"the spans are rated {rw:.0f} and {re_:.0f}, less than a quarter apart; "
             f"one hard-coded rating would be right about both")

    # 7. The demonstration has to be POSSIBLE with the baked numbers too, or a human
    #    playing by hand sees a different bridge from the graded one.
    weights = sorted(w for _, _, _, w in BANK)
    if not any(w <= 0.85 * rw and w + 0.40 * rw >= 1.15 * rw for w in weights):
        fail(f"no crate in the bank ({[int(w) for w in weights]}) is under the west "
             f"rating on its own AND over it together with the character; the seed "
             f"idea -- too much only TOGETHER -- would not be demonstrable by hand")

    # 8. The walk fits on the floor.
    for x, y in route_waypoints():
        if not (FLOOR_MIN[0] + 200.0 <= x <= FLOOR_MAX[0] - 200.0
                and FLOOR_MIN[1] + 200.0 <= y <= FLOOR_MAX[1] - 200.0):
            fail(f"the walk reaches ({x:.0f},{y:.0f}), off a floor of "
                 f"{FLOOR_MIN} .. {FLOOR_MAX}")

    log(f"layout checked: ramps {slope:.1f} deg (walkable to {walkable_limit:.1f}), "
        f"full sag {FULL_SAG_CM:.0f} cm and fallen lip {fallen_top:.0f} cm both under "
        f"a {MAX_STEP_HEIGHT:.0f} cm step, crate slots >= {SLOT_EDGE_MARGIN:.0f} cm "
        f"inside the deck, ratings {rw:.0f}/{re_:.0f}")


def seg_rect_distance(p, q, rect):
    """Shortest distance from segment p->q to an axis-aligned rectangle, sampled.
    Sampling is enough here: every rectangle is far larger than the step."""
    xmin, xmax, ymin, ymax = rect
    best = 1e9
    steps = 200
    for k in range(steps + 1):
        t = k / steps
        x = p[0] + (q[0] - p[0]) * t
        y = p[1] + (q[1] - p[1]) * t
        dx = max(xmin - x, 0.0, x - xmax)
        dy = max(ymin - y, 0.0, y - ymax)
        best = min(best, math.hypot(dx, dy))
    return best


def check_placement():
    """Everything that has to be true of what was actually SPAWNED."""
    half_x = DECK_X / 2.0
    half_y = DECK_Y / 2.0

    # A deck that gives way has to reach the ground: nothing solid may stand under a
    # deck's footprint below its resting height.
    for label, sx, sy, _ in SPANS:
        for name, xmin, xmax, ymin, ymax, zmin, zmax in SOLIDS:
            if name in ("Floor", label):
                continue
            if xmax < sx - half_x or xmin > sx + half_x:
                continue
            if ymax < sy - half_y or ymin > sy + half_y:
                continue
            if zmax > 0.5 and zmin < DECK_TOP_Z:
                fail(f"{name} stands under the {label} deck (z {zmin:.0f}..{zmax:.0f}); "
                     f"a span that gives way has to reach the ground, and anything "
                     f"solid under it would hold the deck up or block the character "
                     f"who rode it down")

    # The sideways exits off a fallen deck have to be clear. They are the ONLY way off
    # a collapsed span: the ramp tops are two metres above it.
    for i, (label, sx, sy, _) in enumerate(SPANS):
        exit_to = sy + half_y + 550.0
        lane = (sx - CAPSULE_RADIUS - 60.0, sx + CAPSULE_RADIUS + 60.0,
                min(sy + half_y, exit_to) - 10.0, max(sy + half_y, exit_to) + 10.0)
        for name, xmin, xmax, ymin, ymax, zmin, zmax in SOLIDS:
            if name in ("Floor", label):
                continue
            if xmax < lane[0] or xmin > lane[1] or ymax < lane[2] or ymin > lane[3]:
                continue
            if zmax > 5.0:
                fail(f"{name} stands in the sideways exit lane off {label}; a "
                     f"collapsed span cannot be left by its ramps and the drive would "
                     f"stall on the fallen deck until the time limit")

    # Nothing solid near a leg of the walk, except the things the walk is meant to
    # cross.
    route = route_waypoints()
    for s in range(len(route) - 1):
        if route[s] == route[s + 1]:
            continue
        for name, xmin, xmax, ymin, ymax, zmin, zmax in SOLIDS:
            if name in WALKABLE_LABELS:
                continue
            d = seg_rect_distance(route[s], route[s + 1], (xmin, xmax, ymin, ymax))
            if d < ROUTE_CLEARANCE:
                fail(f"the walk from {route[s]} to {route[s + 1]} passes {d:.0f} cm "
                     f"from {name}; the character would jam against it and the run "
                     f"would read as the submission's fault")
    log(f"placement checked: {len(SOLIDS)} solid actors, nothing under a deck, both "
        f"sideways exits clear, no leg of the walk within {ROUTE_CLEARANCE:.0f} cm of "
        f"anything solid it is not meant to cross")


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
    block(env, CUBE, (mid_x, mid_y, -50.0),
          (span_x / 100.0, span_y / 100.0, 1.0), "Floor", M_FLOOR, walkable=True)

    n = 0
    x = FLOOR_MIN[0] + STRIPE_EVERY
    while x < FLOOR_MAX[0]:
        block(env, CUBE, (x, mid_y, 1.5), (0.06, span_y / 100.0, 0.03),
              f"Stripe_{n:02d}", M_STRIPE, collide=False)
        n += 1
        x += STRIPE_EVERY
    log(f"yard {span_x:.0f}x{span_y:.0f} + {n} stripes")

    half_x = DECK_X / 2.0
    half_y = DECK_Y / 2.0
    span_looks = (M_GLOW, M_HAZARD)

    for idx, (label, sx, sy, rating) in enumerate(SPANS):
        # A coloured patch of floor under each span, so the two are told apart at a
        # glance in a capture. Paint: never collides.
        block(env, CUBE, (sx, sy, 2.0),
              ((DECK_X + 2 * RAMP_RUN + 400.0) / 100.0, (DECK_Y + 300.0) / 100.0, 0.04),
              f"{label}_Patch", span_looks[idx % 2], collide=False)

        # Four approach ramps, two per span, solved so their top surfaces run exactly
        # from the floor to the deck's resting top.
        for side, (low, high) in (
                ("W", (sx - half_x - RAMP_GAP - RAMP_RUN, sx - half_x - RAMP_GAP)),
                ("E", (sx + half_x + RAMP_GAP + RAMP_RUN, sx + half_x + RAMP_GAP))):
            centre, pitch, length, half = ramp_pose(low, high, sy, DECK_TOP_Z)
            block(env, CUBE, centre, (length / 100.0, DECK_Y / 100.0,
                                      DECK_THICK / 100.0),
                  f"{label}_Ramp{side}", M_DARK, pitch=pitch, walkable=True,
                  half=half)

        # Decorative trestle posts. NON-COLLIDING on purpose -- see the module note.
        for px in (-300.0, 300.0):
            for py in (-250.0, 250.0):
                block(env, CYL, (sx + px, sy + py, (DECK_TOP_Z - DECK_THICK) / 2.0),
                      (0.6, 0.6, (DECK_TOP_Z - DECK_THICK) / 100.0),
                      f"{label}_Post_{int(px)}_{int(py)}", M_DARK, collide=False)

        span = eas.spawn_actor_from_class(
            env["BridgeSpanActor"],
            unreal.Vector(sx, sy, DECK_TOP_Z - DECK_THICK / 2.0),
            unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
        if span is None:
            fail(f"could not place {label}")
        span.set_actor_label(label)
        span.set_editor_property("rated_load_kg", rating)
        span.set_editor_property("full_sag_cm", FULL_SAG_CM)
        span.set_editor_property("give_way_drop_cm", GIVE_WAY_DROP_CM)
        # MOVABLE, both of them. The deck is what the character rides; PIE logs a
        # mobility error for a STATIC component that moves, and the functional test
        # scores that as a FAIL.
        for comp_name in ("anchor", "deck"):
            span.get_editor_property(comp_name).set_editor_property(
                "mobility", unreal.ComponentMobility.MOVABLE)
        SOLIDS.append((label, sx - half_x, sx + half_x, sy - half_y, sy + half_y,
                       DECK_TOP_Z - DECK_THICK, DECK_TOP_Z))
        WALKABLE_LABELS.add(label)
    log(f"{len(SPANS)} spans placed with their ramps, rated "
        f"{[int(s[3]) for s in SPANS]}")

    for label, cx, cy, weight in BANK:
        crate = eas.spawn_actor_from_class(
            env["YardLoadActor"], unreal.Vector(cx, cy, CRATE_SIDE / 2.0),
            unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
        if crate is None:
            fail(f"could not place {label}")
        crate.set_actor_label(label)
        crate.set_editor_property("weight_kg", weight)
        crate.get_editor_property("body").set_editor_property(
            "mobility", unreal.ComponentMobility.MOVABLE)
        SOLIDS.append((label, cx - CRATE_SIDE / 2.0, cx + CRATE_SIDE / 2.0,
                       cy - CRATE_SIDE / 2.0, cy + CRATE_SIDE / 2.0, 0.0, CRATE_SIDE))
    # The bank, painted so a reviewer can see where the yard parks its cargo.
    block(env, CUBE, (BANK[0][1], 0.0, 2.0), (4.0, 20.0, 0.04), "BankPad", M_STRIPE,
          collide=False)
    log(f"{len(BANK)} crates parked on the bank weighing "
        f"{[int(b[3]) for b in BANK]}")

    start = eas.spawn_actor_from_class(
        unreal.PlayerStart, unreal.Vector(START_AT[0], START_AT[1], 120.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if start is None:
        fail("could not place PlayerStart")
    start.set_actor_label("PlayerStart")

    # Backdrop + two differently sized landmarks, so a moving camera is
    # distinguishable from a still one. Both well clear of the walk.
    block(env, CUBE, (mid_x, FLOOR_MAX[1] - 60.0, 140.0),
          (span_x / 100.0, 0.6, 2.8), "Backdrop", M_DARK)
    for idx, lx in enumerate((FLOOR_MIN[0] + 300.0, FLOOR_MAX[0] - 300.0)):
        block(env, CYL, (lx, FLOOR_MAX[1] - 700.0, 300.0),
              (1.2 + idx * 0.9, 1.2 + idx * 0.9, 6.0), f"Landmark_{idx}",
              M_GLOW if idx else M_HAZARD)

    sun = eas.spawn_actor_from_class(
        unreal.DirectionalLight, unreal.Vector(mid_x, mid_y, 1400.0),
        unreal.Rotator(roll=0.0, pitch=-48.0, yaw=-120.0))
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
        env["TrestleLoadFunctionalTest"],
        unreal.Vector(FLOOR_MIN[0] + 300.0, FLOOR_MIN[1] + 300.0, 150.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if fixture is None:
        fail("could not place TrestleLoadFunctionalTest")
    fixture.set_actor_label("TrestleLoadFunctionalTest")

    check_placement()

    # ---- read back what is actually in the level -------------------------------
    world = unreal.EditorLevelLibrary.get_editor_world()
    if world.get_world_settings().get_editor_property("default_game_mode") is not None:
        fail("world settings already name a game mode; this level must inherit the "
             "project default or Enhanced Input is dropped and the level cannot be "
             "played by hand, while still grading byte-identically")
    log("world settings: no game mode named (inherits BP_ThirdPersonGameMode)")

    lit = [a for a in eas.get_all_level_actors()
           if a.get_class().get_name() in ("DirectionalLight", "SkyLight")]
    if len(lit) < 2:
        fail(f"level has {len(lit)} light actor(s); a capture still would be black")

    placed_spans = [a for a in eas.get_all_level_actors() if a.actor_has_tag("LoadSpan")]
    placed_loads = [a for a in eas.get_all_level_actors() if a.actor_has_tag("YardLoad")]
    if len(placed_spans) != len(SPANS) or len(placed_loads) != len(BANK):
        fail(f"{len(placed_spans)} LoadSpan and {len(placed_loads)} YardLoad actors "
             f"in the level; the fixture expects {len(SPANS)} and {len(BANK)}")

    for span in placed_spans:
        origin, extent = span.get_actor_bounds(only_colliding_components=True)
        top = origin.z + extent.z
        if abs(top - DECK_TOP_Z) > 1.0:
            fail(f"{span.get_actor_label()}'s deck reads a top of z={top:.1f} and the "
                 f"ramps meet it at z={DECK_TOP_Z:.0f}; the joint would be a step the "
                 f"level never intended")
        if abs(extent.x * 2.0 - DECK_X) > 1.0 or abs(extent.y * 2.0 - DECK_Y) > 1.0:
            fail(f"{span.get_actor_label()}'s deck measures "
                 f"{extent.x * 2.0:.0f}x{extent.y * 2.0:.0f} and the layout is solved "
                 f"for {DECK_X:.0f}x{DECK_Y:.0f}")
        for comp_name in ("anchor", "deck"):
            if span.get_editor_property(comp_name).get_editor_property("mobility") \
                    != unreal.ComponentMobility.MOVABLE:
                fail(f"{span.get_actor_label()}'s {comp_name} is not MOVABLE; the deck "
                     f"has to move and a character standing on a non-movable deck is "
                     f"left hanging in the air when it does")

    for crate in placed_loads:
        origin, extent = crate.get_actor_bounds(only_colliding_components=True)
        if origin.z - extent.z < -1.0:
            fail(f"{crate.get_actor_label()} reaches down to "
                 f"z={origin.z - extent.z:.1f}, below the floor")
        if crate.get_editor_property("body").get_editor_property("mobility") \
                != unreal.ComponentMobility.MOVABLE:
            fail(f"{crate.get_actor_label()} is not MOVABLE; the yard picks it up and "
                 f"puts it down, and PIE scores moving a STATIC actor as a FAIL")
    log("read-back OK: both decks measure and sit where the ramps expect, everything "
        "the yard moves is MOVABLE, and every crate stands on the floor")

    if not les.save_current_level():
        fail("save_current_level() returned False")
    log(f"SAVED {MAP_PKG}")


main()

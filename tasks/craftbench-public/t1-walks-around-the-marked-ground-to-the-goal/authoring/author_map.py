"""Authors L_DetourYard for t1-walks-around-the-marked-ground-to-the-goal.

    UnrealEditor-Cmd.exe <ThirdPerson.uproject> -run=pythonscript \
        -script="<abs path to this file>" -nullrhi -unattended -nopause \
        -log -stdout -FullStdOutLogOutput

THIS SCRIPT SOLVES THE LEVEL BEFORE IT SAVES IT. Four things have to be true of
the geometry at once, and all four are measured here rather than asserted in
prose:

  (a) a route avoiding ONLY patch A fits the distance budget,
  (b) a route avoiding ONLY patch B fits it too,
  (c) a route avoiding BOTH does NOT -- otherwise "keep off all marked ground"
      is a winning answer and nothing forces a submission to read which patch is
      out of bounds this trip,
  (d) a GREEDY LOCAL AVOIDER -- head for the goal, sidestep when the next step
      lands on out-of-bounds paint -- fails to arrive, with EITHER patch marked.
      This is the difficulty axis. If wall-following solves the level, the task
      measures nothing, and the level must not ship.

Each patch is a U of paint opening back toward the start, positioned so its
mouth straddles the straight line. The U's interior is clean, so a walker drives
happily into the pocket and first meets paint at the back wall -- by which point
sliding either way along it runs into an arm. Getting out means going backwards.

This level names NO game mode: it inherits the project default, so the play lane
comes for free (see the 2026-08-17 unplayable-play-lane finding).

Every Rotator is built with KEYWORDS -- unreal.Rotator's positional order is
(roll, pitch, yaw).
"""
import heapq
import math

import unreal

TASK = "t1-walks-around-the-marked-ground-to-the-goal"
MAP_PKG = f"/Game/Maps/{TASK}/L_DetourYard"

FLOOR_MIN = (-2800.0, -2600.0)
FLOOR_MAX = (5200.0, 2600.0)
STRIPE_EVERY = 400.0

START_AT = (-2200.0, 0.0)
GOAL_AT = (4600.0, 0.0)
# (mouth_x, centre_y) for each patch. Same shape, different place.
PATCH_A = (400.0, -700.0)
PATCH_B = (2000.0, 700.0)

# Must match AMarkedGroundActor's constructor. Asserted against the real placed
# bounds below, so the two cannot drift apart silently.
U_HALF_Y = 1700.0
U_DEPTH = 1500.0
U_STROKE = 150.0
PAINT_Z = 4.0

# Must match the fixture's kBudgetFactor.
BUDGET_FACTOR = 1.30
# The walker's capsule is centred on its actor location, so it stands at half its
# own height plus a little daylight.
WALKER_STAND_Z = 95.0
WALKER_RADIUS = 35.0

CELL = 50.0
CLEARANCE = 60.0
GREEDY_STEP = 40.0
GREEDY_MAX_STEPS = 1200

CUBE = "/Engine/BasicShapes/Cube.Cube"
CYL = "/Engine/BasicShapes/Cylinder.Cylinder"
M_FLOOR = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray"
M_STRIPE = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02"
M_DARK = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"
M_GLOW = "/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT"
M_HAZARD = "/Game/Variant_Combat/Materials/M_Lava"


def log(msg):
    unreal.log(f"DETOURYARD- {msg}")


def fail(msg):
    unreal.log_error(f"DETOURYARD-ERROR {msg}")
    raise SystemExit(1)


# ------------------------------------------------------------------ the solver
def u_boxes(patch):
    """The three painted strokes of one U, opening toward -X."""
    mx, cy = patch
    back0, back1 = mx + U_DEPTH - U_STROKE, mx + U_DEPTH
    return [
        (back0, cy - U_HALF_Y, back1, cy + U_HALF_Y),
        (mx, cy + U_HALF_Y - U_STROKE, back0, cy + U_HALF_Y),
        (mx, cy - U_HALF_Y, back0, cy - U_HALF_Y + U_STROKE),
    ]


def in_boxes(p, boxes, pad=0.0):
    for (x0, y0, x1, y1) in boxes:
        if x0 - pad <= p[0] <= x1 + pad and y0 - pad <= p[1] <= y1 + pad:
            return True
    return False


def shortest(blocked):
    """Grid Dijkstra from the start to the goal avoiding every blocked box."""
    nx = int((FLOOR_MAX[0] - FLOOR_MIN[0]) / CELL) + 1
    ny = int((FLOOR_MAX[1] - FLOOR_MIN[1]) / CELL) + 1

    def pos_of(c):
        return (FLOOR_MIN[0] + c[0] * CELL, FLOOR_MIN[1] + c[1] * CELL)

    def cell_of(p):
        return (int(round((p[0] - FLOOR_MIN[0]) / CELL)),
                int(round((p[1] - FLOOR_MIN[1]) / CELL)))

    def free(c):
        return (0 <= c[0] < nx and 0 <= c[1] < ny
                and not in_boxes(pos_of(c), blocked, pad=CLEARANCE))

    s, g = cell_of(START_AT), cell_of(GOAL_AT)
    if not free(s) or not free(g):
        return None
    dist = {s: 0.0}
    pq = [(0.0, s)]
    steps = [(dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (dx, dy) != (0, 0)]
    while pq:
        d, c = heapq.heappop(pq)
        if c == g:
            return d
        if d > dist.get(c, 1e18):
            continue
        for dx, dy in steps:
            n = (c[0] + dx, c[1] + dy)
            if not free(n):
                continue
            nd = d + CELL * math.hypot(dx, dy)
            if nd < dist.get(n, 1e18):
                dist[n] = nd
                heapq.heappush(pq, (nd, n))
    return None


def greedy_arrives(forbidden):
    """Head for the goal; sidestep when the next step lands on forbidden paint.

    The shape a submission writes when it steers instead of planning. It must NOT
    arrive, or the level is solved by wall-following and measures nothing.
    """
    p = list(START_AT)
    travelled = 0.0
    for _ in range(GREEDY_MAX_STEPS):
        if math.dist(p, GOAL_AT) <= 120.0:
            return True, travelled
        vx, vy = GOAL_AT[0] - p[0], GOAL_AT[1] - p[1]
        n = math.hypot(vx, vy)
        vx, vy = vx / n, vy / n
        moved = False
        for turn in (0, 25, -25, 50, -50, 75, -75, 90, -90):
            a = math.radians(turn)
            cand = (p[0] + (vx * math.cos(a) - vy * math.sin(a)) * GREEDY_STEP,
                    p[1] + (vx * math.sin(a) + vy * math.cos(a)) * GREEDY_STEP)
            if in_boxes(cand, forbidden, pad=CLEARANCE):
                continue
            if not (FLOOR_MIN[0] <= cand[0] <= FLOOR_MAX[0]
                    and FLOOR_MIN[1] <= cand[1] <= FLOOR_MAX[1]):
                continue
            travelled += GREEDY_STEP
            p = list(cand)
            moved = True
            break
        if not moved:
            return False, travelled
    return False, travelled


def solve_or_refuse():
    a, b = u_boxes(PATCH_A), u_boxes(PATCH_B)
    straight = math.dist(START_AT, GOAL_AT)
    budget = straight * BUDGET_FACTOR
    only_a, only_b, both = shortest(a), shortest(b), shortest(a + b)

    def fmt(d):
        return "no route" if d is None else f"{d:.0f} uu ({d / straight:.2f}x)"

    log(f"straight line {straight:.0f} uu, budget {budget:.0f} uu "
        f"({BUDGET_FACTOR}x)")
    log(f"  avoid A only: {fmt(only_a)}   avoid B only: {fmt(only_b)}   "
        f"avoid BOTH: {fmt(both)}")

    if only_a is None or only_a > budget:
        fail(f"(a) avoiding only patch A costs {fmt(only_a)}, over the "
             f"{budget:.0f} uu budget - trip 1 would be unwinnable")
    if only_b is None or only_b > budget:
        fail(f"(b) avoiding only patch B costs {fmt(only_b)}, over the "
             f"{budget:.0f} uu budget - trip 2 would be unwinnable")
    if both is not None and both <= budget:
        fail(f"(c) a route avoiding BOTH patches fits the budget ({fmt(both)}), so "
             f"keeping off all marked ground wins and nothing forces a submission "
             f"to read which patch is out of bounds")

    for name, boxes in (("A", a), ("B", b)):
        crosses = any(
            in_boxes((START_AT[0] + t / 800.0 * (GOAL_AT[0] - START_AT[0]),
                      START_AT[1] + t / 800.0 * (GOAL_AT[1] - START_AT[1])), boxes)
            for t in range(801))
        if not crosses:
            fail(f"the straight line from start to goal misses patch {name}; a "
                 f"walker that ignored it entirely would pass")

    for name, boxes in (("A", a), ("B", b)):
        arrived, dist = greedy_arrives(boxes)
        log(f"  greedy local avoider with {name} out of bounds: "
            f"{'ARRIVED' if arrived else 'stuck'} after {dist:.0f} uu")
        if arrived:
            fail(f"(d) a greedy local avoider reaches the goal with patch {name} out "
                 f"of bounds, so wall-following solves this level and it measures "
                 f"nothing")
    log("solver: the level is winnable both trips, unwinnable by avoiding both, "
        "and unsolved by local steering")


# ----------------------------------------------------------------- the authoring
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
    for cls_name in ("MarkedGroundActor", "DetourWalkerActor",
                     "MarkedGroundDetourFunctionalTest"):
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
        # The PROFILE, not just the enum. set_collision_enabled alone did not survive
        # into the saved level: the start marker was authored with it and still blocked
        # the walker, which then could not move at all. ('collision_enabled' is not an
        # editor property on a StaticMeshComponent, so that spelling is not available.)
        comp.set_collision_profile_name("NoCollision")
        comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    actor.set_actor_scale3d(scale)
    return actor


def main():
    env = probe()
    les, eas = env["les"], env["eas"]
    solve_or_refuse()

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
        # PAINT, NOT GEOMETRY: a 3 cm lip is a wall to anything moved by a swept
        # SetActorLocation, which is what the supplied StepToward does.
        block(env, CUBE, unreal.Vector(x, mid_y, 1.5),
              unreal.Vector(0.06, span_y / 100.0, 0.03), f"Stripe_{n:02d}", M_STRIPE,
              collide=False)
        n += 1
        x += STRIPE_EVERY
    log(f"floor {span_x:.0f}x{span_y:.0f} + {n} stripes")

    for label, (mx, cy) in (("MarkedGround_A", PATCH_A), ("MarkedGround_B", PATCH_B)):
        patch = eas.spawn_actor_from_class(
            env["MarkedGroundActor"], unreal.Vector(mx, cy, PAINT_Z),
            unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
        if patch is None:
            fail(f"could not place {label}")
        patch.set_actor_label(label)
        # THE LEVEL SHIPS WITH ONE PATCH ALREADY OUT OF BOUNDS. Without this the only
        # thing that ever marks a patch is the fixture, so a human pressing Play sees
        # two identical green patches, nothing to avoid, and a walker that strolls
        # straight through both -- which is exactly what the owner found when they
        # played it. A level that is only meaningful while the harness drives it is
        # not a playable level.
        patch.set_editor_property("out_of_bounds", label.endswith("_A"))
    log(f"two identical marked patches, mouths at {PATCH_A} and {PATCH_B}; "
        f"MarkedGround_A ships OUT OF BOUNDS so the level reads correctly on Play")

    walker = eas.spawn_actor_from_class(
        env["DetourWalkerActor"],
        unreal.Vector(START_AT[0], START_AT[1], WALKER_STAND_Z),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if walker is None:
        fail("could not place the walker")
    walker.set_actor_label("DetourWalker")

    # FLAT MARKERS SIT UNDER THE WALKER. Its capsule centre is at 95 with a half
    # height of 90, so its feet are at z=5: a disc standing 6 uu proud spans 3..9 and
    # OVERLAPS it. Measured -- the walker was penetrating the start marker from frame
    # one and every swept move it made was refused at zero distance, while its Tick
    # ran and its route planned perfectly.
    start = block(env, CYL, unreal.Vector(START_AT[0], START_AT[1], 1.5),
                  unreal.Vector(2.2, 2.2, 0.03), "DetourStart", M_GLOW, collide=False)
    start.tags = ["DetourStart"]
    goal = block(env, CYL, unreal.Vector(GOAL_AT[0], GOAL_AT[1], 1.5),
                 unreal.Vector(2.6, 2.6, 0.03), "DetourGoal", M_GLOW, collide=False)
    goal.tags = ["DetourGoal"]
    block(env, CYL, unreal.Vector(GOAL_AT[0], GOAL_AT[1], 260.0),
          unreal.Vector(0.7, 0.7, 5.2), "GoalPost", M_GLOW)
    log(f"start marked at {START_AT}, goal at {GOAL_AT}")

    player = eas.spawn_actor_from_class(
        unreal.PlayerStart,
        unreal.Vector(START_AT[0] - 400.0, START_AT[1] - 500.0, 100.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if player is None:
        fail("could not place PlayerStart")
    player.set_actor_label("PlayerStart")

    block(env, CUBE, unreal.Vector(mid_x, FLOOR_MAX[1] - 20.0, 90.0),
          unreal.Vector(span_x / 100.0, 0.3, 1.8), "Backdrop", M_DARK)
    for idx, (lx, ly) in enumerate(((FLOOR_MIN[0] + 250.0, FLOOR_MAX[1] - 350.0),
                                    (FLOOR_MAX[0] - 250.0, FLOOR_MAX[1] - 350.0))):
        block(env, CYL, unreal.Vector(lx, ly, 320.0),
              unreal.Vector(1.2 + idx * 0.9, 1.2 + idx * 0.9, 6.4), f"Landmark_{idx}",
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
        env["MarkedGroundDetourFunctionalTest"],
        unreal.Vector(FLOOR_MIN[0] + 250.0, FLOOR_MIN[1] + 250.0, 120.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0)).set_actor_label(
            "MarkedGroundDetourFunctionalTest")

    world = unreal.EditorLevelLibrary.get_editor_world()
    if world.get_world_settings().get_editor_property("default_game_mode") is not None:
        fail("world settings already name a game mode; this level must inherit the "
             "project default so the play lane comes for free")
    log("world settings: no game mode named (inherits BP_ThirdPersonGameMode)")

    # ------------------------------------------------ what the placed level says
    lit = [a for a in eas.get_all_level_actors()
           if a.get_class().get_name() in ("DirectionalLight", "SkyLight")]
    if len(lit) < 2:
        fail(f"level has {len(lit)} light actor(s); a capture still would be black")

    for tag, want in (("MarkedGround", 2), ("DetourWalker", 1), ("DetourStart", 1),
                      ("DetourGoal", 1)):
        got = [a for a in eas.get_all_level_actors() if a.actor_has_tag(tag)]
        if len(got) != want:
            fail(f"{len(got)} actor(s) tagged {tag}, expected {want}; the fixture "
                 f"resolves the yard by these tags and would refuse to start")

    # EXACTLY ONE PATCH MUST SHIP MARKED. Two marked and there is no route; none
    # marked and the level is inert until the harness touches it.
    marked = [p for p in eas.get_all_level_actors()
              if p.actor_has_tag("MarkedGround")
              and bool(p.get_editor_property("out_of_bounds"))]
    if len(marked) != 1:
        fail(f"{len(marked)} of the 2 patches ship marked out of bounds, expected "
             f"exactly 1; with none the level is inert until the fixture runs and a "
             f"human sees nothing to avoid, with both there is no route at all")
    log(f"{marked[0].get_actor_label()} ships out of bounds")

    # THE PLACED PATCHES MUST BE THE SHAPE THE SOLVER SOLVED. Reading it back from
    # the real bounds is the only way to know the constructor and this file agree.
    for patch in [a for a in eas.get_all_level_actors()
                  if a.actor_has_tag("MarkedGround")]:
        origin, extent = patch.get_actor_bounds(only_colliding_components=False)
        want_x = U_DEPTH
        want_y = U_HALF_Y * 2.0
        if abs(extent.x * 2.0 - want_x) > 20.0 or abs(extent.y * 2.0 - want_y) > 20.0:
            fail(f"{patch.get_actor_label()} measures {extent.x * 2:.0f} x "
                 f"{extent.y * 2:.0f} uu, but the solver solved a {want_x:.0f} x "
                 f"{want_y:.0f} U; the level and the actor have drifted apart")

    # The patches must be PAINT. If one of them blocked, the whole task would be a
    # different one, and the fixture's not-made-solid gate would measure nothing.
    for patch in [a for a in eas.get_all_level_actors()
                  if a.actor_has_tag("MarkedGround")]:
        _, solid = patch.get_actor_bounds(only_colliding_components=True)
        if solid.x > 1.0 or solid.y > 1.0:
            fail(f"{patch.get_actor_label()} has colliding geometry; the marked "
                 f"ground is paint and must block nothing")

    # THE WALKER MUST STAND ON THE FLOOR, NOT IN IT. A walker whose collision dips
    # below the floor is penetrating from frame one and every swept move it makes is
    # refused at zero distance -- measured on the patrol task, 90 cm of penetration
    # and a Tick that ran 3600 times without the walker moving once.
    w_origin, w_extent = walker.get_actor_bounds(only_colliding_components=True)
    if w_origin.z - w_extent.z < 1.0:
        fail(f"the walker's collision reaches down to z={w_origin.z - w_extent.z:.1f}, "
             f"at or below the floor; it would be unable to move at all")
    log(f"walker stands with its collision bottom at "
        f"z={w_origin.z - w_extent.z:.1f}, clear of the floor")

    # NOTHING SOLID MAY OVERLAP WHERE THE WALKER STANDS. A walker that starts inside
    # anything is penetrating from frame one, and a swept move out of a penetration is
    # refused at zero distance -- which presents as a walker that never moves while its
    # Tick runs and its route plans correctly. Measured twice in one night, on two
    # different actors.
    w_lo = unreal.Vector(w_origin.x - w_extent.x, w_origin.y - w_extent.y,
                         w_origin.z - w_extent.z)
    w_hi = unreal.Vector(w_origin.x + w_extent.x, w_origin.y + w_extent.y,
                         w_origin.z + w_extent.z)
    for other in eas.get_all_level_actors():
        if other == walker or other.get_class().get_name() != "StaticMeshActor":
            continue
        o_origin, o_extent = other.get_actor_bounds(only_colliding_components=True)
        if o_extent.x <= 1.0 and o_extent.y <= 1.0 and o_extent.z <= 1.0:
            continue          # nothing solid on this actor
        o_lo = (o_origin.x - o_extent.x, o_origin.y - o_extent.y,
                o_origin.z - o_extent.z)
        o_hi = (o_origin.x + o_extent.x, o_origin.y + o_extent.y,
                o_origin.z + o_extent.z)
        if (w_lo.x < o_hi[0] and w_hi.x > o_lo[0]
                and w_lo.y < o_hi[1] and w_hi.y > o_lo[1]
                and w_lo.z < o_hi[2] and w_hi.z > o_lo[2]):
            fail(f"{other.get_actor_label()} has solid geometry overlapping where the "
                 f"walker stands (walker z {w_lo.z:.1f}..{w_hi.z:.1f}, {other.get_actor_label()} "
                 f"z {o_lo[2]:.1f}..{o_hi[2]:.1f}); the walker would be penetrating it "
                 f"from frame one and unable to move at all")
    log("nothing solid overlaps the walker's starting capsule")

    if not les.save_current_level():
        fail("save_current_level() returned False")
    log(f"SAVED {MAP_PKG}")


main()

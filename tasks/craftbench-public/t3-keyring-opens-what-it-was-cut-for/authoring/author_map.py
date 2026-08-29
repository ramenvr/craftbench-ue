"""Authors L_KeyYard for t3-keyring-opens-what-it-was-cut-for.

Run headless against the ThirdPerson project:

    UnrealEditor-Cmd.exe <ThirdPerson.uproject> -run=pythonscript \
        -script="<abs path to this file>" -nullrhi -unattended -nopause \
        -log -stdout -FullStdOutLogOutput

WHAT THIS FILE IS FOR, beyond placing meshes: it re-derives the fixture's whole route
from the layout and REFUSES TO SAVE unless every clearance the fixture will assert at
run time already holds -- plus the two the fixture cannot see, because it does not know
where the walls are. A staging fault found here costs a re-run of this script; the same
fault found at run time costs a ten-minute build-and-drive cycle and reads, at first
glance, like a broken submission.

The geometry is SOLVED from the props, not typed in twice. Mat radii and the panel's
slide are read off the spawned actors, the lane the drive walks is derived from the bay
mats exactly as the fixture derives it (KeyringFunctionalTest.cpp: LaneY = RowY - 2.4 x
the widest bay mat), and every stop is a fraction of the mat it belongs to. Change a
radius on the prop class and this script moves the yard to match.

The level deliberately names NO game mode: it inherits the project default
(BP_ThirdPersonGameMode), whose pawn is BP_ThirdPersonCharacter and whose controller
carries IMC_Default. Naming a game mode here would drop both halves of Enhanced Input --
the level would grade byte-identically and be impossible to walk around by hand -- and it
would also leave the shift change with no DefaultPawnClass to spawn.

Every Rotator is built with KEYWORDS: unreal.Rotator's positional order is
(roll, pitch, yaw), so Rotator(0, 30, 0) is a 30 degree PITCH.
"""
import math

import unreal

TASK = "t3-keyring-opens-what-it-was-cut-for"
MAP_PKG = f"/Game/Maps/{TASK}/L_KeyYard"

# ---------------------------------------------------------------------------
# The layout. Only the numbers that are genuinely free choices live here; every
# number the FIXTURE also uses is derived below from the props themselves.
# ---------------------------------------------------------------------------

ROW_Y = 0.0                 # the bay row runs along this line
BAY_SPACING = 1800.0        # west-to-east, six bays in the row
BAY_ROW_X0 = 0.0
SOUTH_STAND_Y = -3000.0
SOUTH_STAND_X = [1800.0, 5400.0]
FAR_STAND = [(900.0, 1600.0), (3300.0, 1600.0), (5700.0, 1600.0)]

# The walled corner behind the last bay in the row.
ALCOVE_X0, ALCOVE_X1 = 7900.0, 11900.0
ALCOVE_Y1 = 3400.0
ALCOVE_WALL_T = 60.0
ALCOVE_WALL_H = 500.0
ALCOVE_BAY = (10600.0, 2200.0)
ALCOVE_STAND = (8800.0, 2200.0)

GATE_X = -1400.0            # where the shift musters, and where a fresh body takes over
BOARD_X = -2100.0

FLOOR = (-3000.0, 12600.0, -4200.0, 4600.0)   # xmin, xmax, ymin, ymax; top at Z=0
PERIM_T = 100.0
PERIM_H = 600.0
STRIPE_EVERY = 400.0

# Placeholder categories so the yard is coherent if a person opens it and plays it by
# hand. The fixture RE-CUTS all six from a logged seed before any BeginPlay, so nothing
# downstream may depend on these particular words.
STAND_CATEGORY = ["Copper", "Amber", "Slate", "Cobalt", "Ivory", "Verdant"]

# Clearances this script enforces. The first three mirror the fixture
# (KeyringFunctionalTest.cpp); the last two are the ones only this script can check,
# because the fixture does not know the walls exist.
STAND_STOP_FACTOR = 0.50
BAY_STOP_FACTOR = 0.65
LANE_FACTOR = 2.4
ENTRY_FACTOR = 0.7
ROUTE_CLEAR_FACTOR = 2.0
WAYPOINT_UU = 45.0
SOLID_STANDOFF = 400.0
DOORWAY_LANE = 120.0
FRAME_HALF = 520.0
FRAME_BAND = 150.0
POST_STANDOFF = 120.0
WALL_CLEARANCE = 110.0      # capsule radius 42 plus half a wall plus slack

CUBE = "/Engine/BasicShapes/Cube.Cube"
CYL = "/Engine/BasicShapes/Cylinder.Cylinder"
MAT_FLOOR = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray.MI_PrototypeGrid_Gray"
MAT_STRIPE = ("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_Round"
              ".MI_PrototypeGrid_Gray_Round")
MAT_STAND_MAT = ("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02"
                 ".MI_PrototypeGrid_Gray_02")
MAT_BAY_MAT = ("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"
               ".MI_PrototypeGrid_TopDark")
MAT_WALL = ("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"
            ".MI_PrototypeGrid_TopDark")


def log(msg):
    unreal.log(f"KEYYARD- {msg}")


def fail(msg):
    unreal.log_error(f"KEYYARD-ERROR {msg}")
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
    for path in (CUBE, CYL, MAT_FLOOR, MAT_STRIPE, MAT_STAND_MAT, MAT_BAY_MAT, MAT_WALL):
        if not unreal.EditorAssetLibrary.does_asset_exist(path):
            fail(f"asset missing: {path}")
    for cls_name in ("KeyStandActor", "DoorBayActor", "RingBoardActor",
                     "KeyringFunctionalTest"):
        if not hasattr(unreal, cls_name):
            fail(f"class {cls_name} is not exposed to python - is the module built?")
        got[cls_name] = getattr(unreal, cls_name)
    log(f"probe OK: {sorted(got)}")
    return got


def block(env, mesh, loc, scale, label, material=None, collide=True, yaw=0.0):
    actor = env["eas"].spawn_actor_from_class(
        unreal.StaticMeshActor, loc, unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
    if actor is None:
        fail(f"could not spawn {label}")
    actor.set_actor_label(label)
    comp = actor.static_mesh_component
    comp.set_static_mesh(unreal.EditorAssetLibrary.load_asset(mesh))
    comp.set_editor_property("mobility", unreal.ComponentMobility.STATIC)
    if material is not None:
        comp.set_material(0, unreal.EditorAssetLibrary.load_asset(material))
    if not collide:
        comp.set_collision_profile_name("NoCollision")
    actor.set_actor_scale3d(scale)
    return actor


def place(env, cls, loc, label, yaw=0.0):
    actor = env["eas"].spawn_actor_from_class(
        cls, loc, unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
    if actor is None:
        fail(f"could not place {label}")
    actor.set_actor_label(label)
    return actor


def wall(env, x0, x1, y0, y1, height, label):
    """An axis-aligned solid slab standing on the floor. Returns its footprint box."""
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    block(env, CUBE, unreal.Vector(cx, cy, height / 2.0),
          unreal.Vector((x1 - x0) / 100.0, (y1 - y0) / 100.0, height / 100.0),
          label, material=MAT_WALL)
    return (x0, x1, y0, y1)


def dist2d(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def box_distance(p, box):
    """Distance from a point to an axis-aligned box footprint; 0 when inside."""
    x0, x1, y0, y1 = box
    dx = max(x0 - p[0], 0.0, p[0] - x1)
    dy = max(y0 - p[1], 0.0, p[1] - y1)
    return math.hypot(dx, dy)


def samples(a, b, n=48):
    for t in range(n + 1):
        f = t / float(n)
        yield (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)


# ---------------------------------------------------------------------------
# The route, re-derived exactly the way KeyringFunctionalTest builds it.
# ---------------------------------------------------------------------------

def build_route(row_bays, alcove_bay, south_stands, alcove_stand,
                stand_r, bay_r, lane_y, entry):
    """Returns [(x, y, stop_label)] with stop_label 0 for a corner."""
    nodes = []

    def corner(p):
        if nodes and dist2d(nodes[-1][:2], p) < 1.0:
            return
        nodes.append((p[0], p[1], 0))

    def stop(p, label):
        if nodes and nodes[-1][2] == 0 and dist2d(nodes[-1][:2], p) < 1.0:
            nodes.pop()
        nodes.append((p[0], p[1], label))

    def plaza(p, label):
        cur = nodes[-1][:2] if nodes else (GATE_X, lane_y)
        corner((cur[0], lane_y))
        corner((p[0], lane_y))
        stop(p, label)

    def alcove(p, label):
        cur = nodes[-1][:2] if nodes else entry
        corner((cur[0], entry[1]))
        corner((p[0], entry[1]))
        stop(p, label)

    def bay_stop(b):
        return (b[0], b[1] - BAY_STOP_FACTOR * bay_r)

    def stand_stop(s, from_north):
        return (s[0], s[1] + (1.0 if from_north else -1.0) * STAND_STOP_FACTOR * stand_r)

    muster = (GATE_X, lane_y)
    nodes.append((muster[0], muster[1], 1))
    plaza(bay_stop(row_bays[0]), 2)
    plaza(stand_stop(south_stands[0], True), 3)
    plaza(bay_stop(row_bays[0]), 4)
    plaza(bay_stop(row_bays[1]), 5)
    plaza(bay_stop(row_bays[2]), 6)
    plaza(stand_stop(south_stands[1], True), 7)
    plaza(bay_stop(row_bays[3]), 8)
    nodes.append((row_bays[3][0], lane_y, 9))
    nodes.append((muster[0], muster[1], 10))
    plaza(bay_stop(row_bays[4]), 11)
    plaza(bay_stop(row_bays[5]), 12)
    corner(entry)
    alcove(bay_stop(alcove_bay), 13)
    alcove(stand_stop(alcove_stand, False), 14)
    alcove(bay_stop(alcove_bay), 15)
    corner((nodes[-1][0], entry[1]))
    corner(entry)
    corner((entry[0], bay_stop(row_bays[5])[1]))
    plaza(bay_stop(row_bays[4]), 16)
    plaza(bay_stop(row_bays[2]), 17)
    plaza(bay_stop(row_bays[0]), 18)
    plaza(muster, 19)
    return nodes


def verify_route(nodes, bays, stands, wall_bay_index, stand_r, bay_r, walls):
    """Every clearance the fixture will assert, plus the walls it cannot see."""
    first_bay = [None] * len(bays)
    first_stand = [None] * len(stands)
    for i, n in enumerate(nodes):
        if n[2] == 0:
            continue
        for b, bp in enumerate(bays):
            if first_bay[b] is None and dist2d(n[:2], bp) <= bay_r:
                first_bay[b] = i
        for s, sp in enumerate(stands):
            if first_stand[s] is None and dist2d(n[:2], sp) <= stand_r:
                first_stand[s] = i
    for b, node in enumerate(first_bay):
        if node is None:
            fail(f"the drive never stands on bay {b + 1}'s mat")
    for s in range(3):
        if first_stand[s] is None:
            fail(f"the drive never stands on stand {s + 1}'s mat")
    for s in range(3, len(stands)):
        if first_stand[s] is not None:
            fail(f"the drive stands on stand {s + 1}'s mat, and that key must stay put")

    # Every stop plainly inside the mat it is about, under a flat read AND under a read
    # that carries the character capsule's 96 uu of height, at the worst point the drive
    # is allowed to settle.
    for n in nodes:
        if n[2] == 0:
            continue
        for label, ps, r in (("bay", bays, bay_r), ("stand", stands, stand_r)):
            for i, p in enumerate(ps):
                d = dist2d(n[:2], p)
                if d > r:
                    continue
                worst = math.hypot(d + WAYPOINT_UU, 96.0)
                if worst > 0.75 * r or WAYPOINT_UU > 0.15 * r:
                    fail(f"stop {n[2]} on {label} {i + 1}'s mat could settle {worst:.0f} "
                         f"uu out on a {r:.0f} uu mat")
    if BAY_STOP_FACTOR * bay_r - WAYPOINT_UU <= stand_r:
        fail(f"a bay stop stands {BAY_STOP_FACTOR * bay_r - WAYPOINT_UU:.0f} uu out and "
             f"a stand mat is {stand_r:.0f} uu; the wrong prop's number would still open "
             f"the bay")

    for k in range(len(nodes) - 1):
        for p in samples(nodes[k][:2], nodes[k + 1][:2]):
            for b, bp in enumerate(bays):
                d = dist2d(p, bp)
                dx, dy = abs(p[0] - bp[0]), abs(p[1] - bp[1])
                through = (b == wall_bay_index) and dx <= DOORWAY_LANE
                in_frame = dy < FRAME_BAND and dx < FRAME_HALF
                if not through and (in_frame or d < SOLID_STANDOFF):
                    fail(f"leg {k} passes {d:.0f} uu from bay {b + 1}'s frame")
                if first_bay[b] is not None and k + 1 < first_bay[b] \
                        and d < ROUTE_CLEAR_FACTOR * bay_r:
                    fail(f"leg {k} comes {d:.0f} uu from bay {b + 1} before the drive "
                         f"ever stands on its mat")
            for s, sp in enumerate(stands):
                d = dist2d(p, sp)
                if d < POST_STANDOFF:
                    fail(f"leg {k} passes {d:.0f} uu from stand {s + 1}'s post")
                if (first_stand[s] is None or k + 1 < first_stand[s]) \
                        and d < ROUTE_CLEAR_FACTOR * stand_r:
                    fail(f"leg {k} comes {d:.0f} uu from stand {s + 1} before the drive "
                         f"ever stands on its mat")
            # THE WALLS. The fixture cannot see these at all -- it knows where props
            # stand, not where the yard is fenced -- so this is the only place the drive
            # is checked against them.
            for name, box in walls:
                if box_distance(p, box) < WALL_CLEARANCE:
                    fail(f"leg {k} passes {box_distance(p, box):.0f} uu from {name}; the "
                         f"character would jam against it")
    log(f"route verified: {len(nodes)} nodes, "
        f"{sum(1 for n in nodes if n[2] > 0)} graded stops")


def main():
    env = probe()
    les, eas = env["les"], env["eas"]

    if unreal.EditorAssetLibrary.does_asset_exist(MAP_PKG):
        fail(f"{MAP_PKG} already exists. Delete the file from the SHELL and re-run; "
             f"overwriting from here is not supported.")
    if not les.new_level(MAP_PKG):
        fail(f"new_level({MAP_PKG}) returned False")
    log(f"created {MAP_PKG}")

    # FLOOR, solid under the whole yard including the walled corner.
    fx0, fx1, fy0, fy1 = FLOOR
    block(env, CUBE, unreal.Vector((fx0 + fx1) / 2.0, (fy0 + fy1) / 2.0, -50.0),
          unreal.Vector((fx1 - fx0) / 100.0, (fy1 - fy0) / 100.0, 1.0),
          "Floor", material=MAT_FLOOR)

    n = 0
    x = fx0 + STRIPE_EVERY
    while x < fx1:
        block(env, CUBE, unreal.Vector(x, (fy0 + fy1) / 2.0, 1.5),
              unreal.Vector(0.06, (fy1 - fy0) / 100.0, 0.03),
              f"Stripe_{n:02d}", material=MAT_STRIPE, collide=False)
        n += 1
        x += STRIPE_EVERY
    log(f"floor {fx1 - fx0:.0f}x{fy1 - fy0:.0f} + {n} stripes")

    # THE BAYS. Six in a row down the middle, one inside the walled corner. Placed
    # first, because their own MatRadiusUu and SlideUu decide where everything else
    # goes and how wide the doorway has to be.
    row_bays = []
    for i in range(6):
        p = (BAY_ROW_X0 + i * BAY_SPACING, ROW_Y)
        place(env, env["DoorBayActor"], unreal.Vector(p[0], p[1], 0.0), f"Bay_row_{i}")
        row_bays.append(p)
    place(env, env["DoorBayActor"],
          unreal.Vector(ALCOVE_BAY[0], ALCOVE_BAY[1], 0.0), "Bay_corner")

    # THE STANDS. Two on the south side, one inside the walled corner, three away on
    # the far side that the shift is never asked to visit.
    south = [(SOUTH_STAND_X[0], SOUTH_STAND_Y), (SOUTH_STAND_X[1], SOUTH_STAND_Y)]
    for i, p in enumerate(south):
        place(env, env["KeyStandActor"], unreal.Vector(p[0], p[1], 0.0), f"Stand_south_{i}")
    place(env, env["KeyStandActor"],
          unreal.Vector(ALCOVE_STAND[0], ALCOVE_STAND[1], 0.0), "Stand_corner")
    for i, p in enumerate(FAR_STAND):
        place(env, env["KeyStandActor"], unreal.Vector(p[0], p[1], 0.0), f"Stand_far_{i}")

    # READ THE NUMBERS OFF THE PROPS, do not restate them. Everything below is solved
    # from these three, so a change to the prop class moves the yard rather than
    # silently disagreeing with it.
    all_actors = eas.get_all_level_actors()
    stand_actors = [a for a in all_actors if a.actor_has_tag("Keyring_Stand")]
    bay_actors = [a for a in all_actors if a.actor_has_tag("Keyring_Bay")]
    if len(stand_actors) != 6 or len(bay_actors) != 7:
        fail(f"{len(stand_actors)} stands and {len(bay_actors)} bays placed; need 6 and 7")
    stand_r = float(stand_actors[0].get_editor_property("mat_radius_uu"))
    bay_r = float(bay_actors[0].get_editor_property("mat_radius_uu"))
    slide = float(bay_actors[0].get_editor_property("slide_uu"))
    for a in stand_actors:
        if abs(float(a.get_editor_property("mat_radius_uu")) - stand_r) > 0.5:
            fail("the key stands do not agree about how wide their mats are")
    for a in bay_actors:
        if abs(float(a.get_editor_property("mat_radius_uu")) - bay_r) > 0.5 \
                or abs(float(a.get_editor_property("slide_uu")) - slide) > 0.5:
            fail("the door bays do not agree about their mats or their slide")
    if bay_r - stand_r < 200.0:
        fail(f"stand mats reach {stand_r:.0f} and bay mats {bay_r:.0f}; the prompt says "
             f"they are not the same size and the difference has to be legible")
    log(f"props say: stand mat {stand_r:.0f}, bay mat {bay_r:.0f}, slide {slide:.0f}")

    # The lane and the way into the corner, derived exactly as the fixture derives them.
    lane_y = ROW_Y - LANE_FACTOR * bay_r
    entry = (row_bays[5][0], ROW_Y + ENTRY_FACTOR * bay_r)
    log(f"derived: laneY={lane_y:.0f} entry=({entry[0]:.0f},{entry[1]:.0f})")

    # THE DOORWAY in the corner's south wall lines up with the bay's own frame posts:
    # the posts are 390 uu either side of the bay, 60 uu across, so the gap is exactly
    # the outside of one post to the outside of the other.
    post_out = 420.0
    gap0, gap1 = row_bays[5][0] - post_out, row_bays[5][0] + post_out
    if not (ALCOVE_X0 < gap0 and gap1 < ALCOVE_X1):
        fail("the doorway does not fall inside the walled corner's south wall")
    # The panel slides into the wall beside the doorway like a pocket door, so the wall
    # has to be long enough on that side to hide it.
    if gap1 + slide + 350.0 > ALCOVE_X1 + 600.0:
        fail(f"a {slide:.0f} uu slide would carry the panel past the corner's east wall")

    walls = [
        ("the west fence", wall(env, fx0, fx0 + PERIM_T, fy0, fy1, PERIM_H, "Fence_W")),
        ("the east fence", wall(env, fx1 - PERIM_T, fx1, fy0, fy1, PERIM_H, "Fence_E")),
        ("the south fence", wall(env, fx0, fx1, fy0, fy0 + PERIM_T, PERIM_H, "Fence_S")),
        ("the north fence", wall(env, fx0, fx1, fy1 - PERIM_T, fy1, PERIM_H, "Fence_N")),
        ("the corner's west wall",
         wall(env, ALCOVE_X0, ALCOVE_X0 + ALCOVE_WALL_T, ROW_Y, ALCOVE_Y1,
              ALCOVE_WALL_H, "Corner_W")),
        ("the corner's east wall",
         wall(env, ALCOVE_X1 - ALCOVE_WALL_T, ALCOVE_X1, ROW_Y, ALCOVE_Y1,
              ALCOVE_WALL_H, "Corner_E")),
        ("the corner's back wall",
         wall(env, ALCOVE_X0, ALCOVE_X1, ALCOVE_Y1 - ALCOVE_WALL_T, ALCOVE_Y1,
              ALCOVE_WALL_H, "Corner_N")),
        ("the corner's south wall, west of the doorway",
         wall(env, ALCOVE_X0, gap0, ROW_Y - ALCOVE_WALL_T / 2.0,
              ROW_Y + ALCOVE_WALL_T / 2.0, ALCOVE_WALL_H, "Corner_S_W")),
        ("the corner's south wall, east of the doorway",
         wall(env, gap1, ALCOVE_X1, ROW_Y - ALCOVE_WALL_T / 2.0,
              ROW_Y + ALCOVE_WALL_T / 2.0, ALCOVE_WALL_H, "Corner_S_E")),
    ]

    # THE MATS, painted at each prop's OWN radius so the ring on the floor and the
    # number on the prop are the same fact. Non-colliding: they are paint.
    for i, p in enumerate(row_bays + [ALCOVE_BAY]):
        block(env, CYL, unreal.Vector(p[0], p[1], 1.0),
              unreal.Vector(bay_r * 2.0 / 100.0, bay_r * 2.0 / 100.0, 0.02),
              f"BayMat_{i}", material=MAT_BAY_MAT, collide=False)
    for i, p in enumerate(south + [ALCOVE_STAND] + list(FAR_STAND)):
        block(env, CYL, unreal.Vector(p[0], p[1], 1.5),
              unreal.Vector(stand_r * 2.0 / 100.0, stand_r * 2.0 / 100.0, 0.02),
              f"StandMat_{i}", material=MAT_STAND_MAT, collide=False)

    # THE BOARD, at the gate, facing into the yard.
    place(env, env["RingBoardActor"], unreal.Vector(BOARD_X, lane_y, 0.0), "RingBoard")

    # THE MUSTER MARK. Exactly one PlayerStart, exactly on the lane: the fixture asserts
    # both, because ChoosePlayerStart picks at random among unoccupied starts and a
    # second one would move the fresh body on some runs.
    start = eas.spawn_actor_from_class(
        unreal.PlayerStart, unreal.Vector(GATE_X, lane_y, 100.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if start is None:
        fail("could not place PlayerStart")
    start.set_actor_label("PlayerStart")

    # PLACEHOLDER CATEGORIES, so a person who opens this level and presses Play sees a
    # coherent yard. The fixture re-cuts all six before any BeginPlay, so nothing may
    # depend on these words -- they exist for the human, not for the grade.
    canonical_stands = south + [ALCOVE_STAND] + list(FAR_STAND)
    stand_by_pos = {}
    for a in stand_actors:
        loc = a.get_actor_location()
        for i, p in enumerate(canonical_stands):
            if dist2d((loc.x, loc.y), p) < 1.0:
                stand_by_pos[i] = a
    if len(stand_by_pos) != 6:
        fail("could not match every placed stand back to its authored spot")
    for i, a in stand_by_pos.items():
        a.set_editor_property("key_category", STAND_CATEGORY[i])

    bay_by_pos = {}
    for a in bay_actors:
        loc = a.get_actor_location()
        for i, p in enumerate(row_bays + [ALCOVE_BAY]):
            if dist2d((loc.x, loc.y), p) < 1.0:
                bay_by_pos[i] = a
    if len(bay_by_pos) != 7:
        fail("could not match every placed bay back to its authored spot")
    # The same role table the fixture uses: two bays for the first key, one for a key
    # nobody fetches, two for the second, one painted with two, one in the corner.
    demand = {
        0: (STAND_CATEGORY[0], ""),
        1: (STAND_CATEGORY[0], ""),
        2: (STAND_CATEGORY[3], ""),
        3: (STAND_CATEGORY[1], ""),
        4: (STAND_CATEGORY[0], STAND_CATEGORY[2]),
        5: (STAND_CATEGORY[1], ""),
        6: (STAND_CATEGORY[2], ""),
    }
    for i, a in bay_by_pos.items():
        wants, also = demand[i]
        a.set_editor_property("wants_category", wants)
        if also:
            a.set_editor_property("also_wants_category", also)
    log("placeholder categories cut; the fixture re-cuts them per run")

    # LIGHTING. new_level() gives a COMPLETELY EMPTY level, and an unlit level
    # photographs as pure black while grading perfectly.
    mid = unreal.Vector((fx0 + fx1) / 2.0, (fy0 + fy1) / 2.0, 1200.0)
    sun = eas.spawn_actor_from_class(
        unreal.DirectionalLight, mid, unreal.Rotator(roll=0.0, pitch=-48.0, yaw=-135.0))
    sky = eas.spawn_actor_from_class(
        unreal.SkyLight, mid, unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    atmo = eas.spawn_actor_from_class(
        unreal.SkyAtmosphere, unreal.Vector(mid.x, mid.y, 0.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if sun is None or sky is None or atmo is None:
        fail("could not place the lighting rig")
    sun.set_actor_label("DirectionalLight")
    sky.set_actor_label("SkyLight")
    atmo.set_actor_label("SkyAtmosphere")

    place(env, env["KeyringFunctionalTest"],
          unreal.Vector(-2400.0, -3600.0, 100.0), "KeyringFunctionalTest")

    # ---- refuse to save anything the fixture would refuse to run ----------
    route = build_route(row_bays, ALCOVE_BAY, south, ALCOVE_STAND,
                        stand_r, bay_r, lane_y, entry)
    verify_route(route, row_bays + [ALCOVE_BAY],
                 canonical_stands, 5, stand_r, bay_r, walls)

    length = sum(dist2d(route[i][:2], route[i + 1][:2]) for i in range(len(route) - 1))
    dwells = 3.0 * (sum(1 for r in route if r[2] > 0) - 2) + 8.0
    estimate = length / 500.0 + dwells + 0.35 * len(route)
    if estimate * 1.35 + 20.0 > 420.0:
        fail(f"the drive is {length:.0f} uu and would need about {estimate:.0f} s, which "
             f"does not fit the 420 s ceiling the fixture caps its sentinel at")
    log(f"drive: {length:.0f} uu, about {estimate:.0f} s, sentinel headroom OK")

    # The classification the fixture does at run time has to be unambiguous here too,
    # or the run ends as a staging fault nobody can read.
    bay_ys = sorted(p[1] for p in row_bays + [ALCOVE_BAY])
    if bay_ys[5] - bay_ys[0] > 200.0 or bay_ys[6] - bay_ys[5] < 1200.0:
        fail("the bays are not six in a row plus one standing well off it")
    stand_ys = sorted(p[1] for p in canonical_stands)
    if stand_ys[1] > ROW_Y - 1200.0 or stand_ys[2] < ROW_Y + 500.0:
        fail("there are not exactly two key stands south of the bay row")
    corner_like = [p for p in canonical_stands
                   if p[1] > ROW_Y + 500.0 and abs(p[0] - ALCOVE_BAY[0]) <= 3000.0]
    far_like = [p for p in canonical_stands
                if p[1] > ROW_Y + 500.0 and abs(p[0] - ALCOVE_BAY[0]) >= 4000.0]
    if len(corner_like) != 1 or len(far_like) != 3:
        fail(f"{len(corner_like)} stand(s) read as inside the walled corner and "
             f"{len(far_like)} as away from it; the fixture needs 1 and 3")

    lit = [a for a in eas.get_all_level_actors()
           if a.get_class().get_name() in ("DirectionalLight", "SkyLight")]
    if len(lit) < 2:
        fail(f"level has {len(lit)} light actor(s); a capture still would be black")
    starts = [a for a in eas.get_all_level_actors()
              if a.get_class().get_name() == "PlayerStart"]
    if len(starts) != 1:
        fail(f"{len(starts)} PlayerStart(s); the shift change needs exactly one")
    if abs(starts[0].get_actor_location().y - lane_y) > 1.0:
        fail("the PlayerStart is not on the lane the drive walks")

    world = unreal.EditorLevelLibrary.get_editor_world()
    settings = world.get_world_settings()
    if settings.get_editor_property("default_game_mode") is not None:
        fail("world settings already name a game mode; this level must inherit the "
             "project default, or the play lane and the shift change both break")
    log("world settings: no game mode named (inherits BP_ThirdPersonGameMode)")

    if not les.save_current_level():
        fail("save_current_level() returned False")
    log(f"SAVED {MAP_PKG}")


main()

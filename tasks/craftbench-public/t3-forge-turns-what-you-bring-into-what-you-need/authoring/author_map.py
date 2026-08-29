"""Authors L_ForgeHall for t3-forge-turns-what-you-bring-into-what-you-need.

    UnrealEditor-Cmd.exe <ThirdPerson.uproject> -run=pythonscript \
        -script="<abs path to this file>" -nullrhi -unattended -nopause \
        -log -stdout -FullStdOutLogOutput

A HALL WITH ONE AISLE, played as a two-step crafting chain against a carry cap.
The forge stands at the origin; heaps of raw stuff stand on pads either side of the
aisle; two carved plaques hang further out on the same side lines, one per step of
the chain; the forge's shelf-stones are behind it, off the far end of the aisle; and
a sign beside the PlayerStart posts how much the character may carry at once.

THE SEPARATIONS ARE THE LOAD-BEARING PART, and they are SOLVED here rather than
eyeballed: every walk the fixture can build has to be either plainly at the thing
it went to or plainly clear of everything else. If a spur passed within a heap's
reach of a heap it never went to, that heap would be taken from in passing and every
delivery after it would be graded against arithmetic the hall never staged. The
same is true of a plaque: reading one by walking past it would quietly hand the
submission a recipe it never went to fetch. And the lane that gets behind the forge
has to clear the forge's OWN take reach, or three units hauled down it would be
handed over halfway. check_geometry() therefore refuses to save the level when any
of that is within a factor of the reach, and it computes the offending distance so
the failure says which pair and by how much.

Three grids, deliberately offset from each other:
    pads     X in {1200, 2000, 2800, 3600}   Y = +-800    reach 180
    plaques  X in { 800, 1600, 2400, 3200}   Y = +-1200   read reach 260
    stones   X in {-600 .. -3400 by -700}    Y = +-1250   (owned by the forge)
The 400 uu offset between the pad and plaque X grids is what keeps a plaque spur
clear of a pad, and vice versa.

This level names NO game mode: it inherits the project default, so the play lane
comes for free (see the 2026-08-17 unplayable-play-lane finding).

Every Rotator is built with KEYWORDS -- unreal.Rotator's positional order is
(roll, pitch, yaw).
"""
import math

import unreal

TASK = "t3-forge-turns-what-you-bring-into-what-you-need"
MAP_PKG = f"/Game/Maps/{TASK}/L_ForgeHall"

FLOOR_MIN = (-4000.0, -2200.0)
FLOOR_MAX = (4800.0, 2200.0)
STRIPE_EVERY = 400.0

FORGE_AT = (0.0, 0.0)
FORGE_REACH = 450.0
FORGE_STOP_X = 300.0            # where the fixture stands to deliver
ANVIL_CLEAR = 180.0             # the solid anvil is 200 uu across; ~141 to a corner

PAD_X = (1200.0, 2000.0, 2800.0, 3600.0)
PAD_Y = (-800.0, 800.0)
# The reaches are SOLVED against the 400 uu offset between the pad and plaque X
# grids, not chosen for roundness: a plaque spur runs out to |Y|=1096 past a pad
# 400 uu away in X, so a pad reach of 180 clears it by 112 uu even at the 1.6x
# margin the fixture sweeps with. 220 would clear it by only 48.
PAD_REACH = 180.0
PAD_STAND_Z = 50.0              # the cone's pivot is at its centre
PRODUCT_REACH = 220.0           # the heap class's own default; the forge's outputs
                                # are spawned with it, so the stone row and the lane
                                # are spaced against THIS and not against PAD_REACH

PLAQUE_X = (800.0, 1600.0, 2400.0, 3200.0)
PLAQUE_ABS_Y = 1200.0
PLAQUE_READ_REACH = 260.0
PLAQUE_Z = 100.0                # the slab is 200 tall and pivots at its centre

# The factors the fixture's own route sweep uses. Duplicated here ON PURPOSE: a
# level that cannot pass the sweep must fail at AUTHORING time, not 40 minutes into
# a graded run as a HARNESS-PRECONDITION nobody sees.
AT_FACTOR = 0.5
CLEAR_FACTOR = 1.6
FORGE_LANE_CLEAR_FACTOR = 1.3

# How far short of a plaque the walk stops. DERIVED the same way the fixture derives
# it, never written down twice: a hard-coded stand-off desynced from the map's once
# already and the drive then failed the fixture's own arrival precondition.
PLAQUE_STAND_IN = min(max(PLAQUE_READ_REACH * AT_FACTOR * 0.8, 80.0), 150.0)

# THE GAME. Three of the base unit make one of the middle unit; three of the middle
# unit make the one thing at the top. Nine base units therefore have to reach the
# forge, and at a cap of three they cannot arrive in fewer than four loads -- and the
# three middle units the forge sets down on its own shelf-stones have to be walked
# out and carried back in before the top can be made at all.
CARRY_CAP = 3
RECIPE_SIZE = 3
BASE_ID = "EMBER"
PLAQUES = (
    # (carving, X slot, side)
    ("TIER 1 : EMBER EMBER EMBER -> SLAG", 0, -1.0),
    ("TIER 2 : SLAG SLAG SLAG -> BLADE", 2, 1.0),
)
# Pads in the order the fixture sorts them: by X, then by Y. 21 units of base
# material against the 9 the chain needs, so a walk that spends a trip filling up is
# not starved -- and two pads out at the far end that no walk ever approaches, which
# have to still be standing untouched at the end.
STOCK = (
    (BASE_ID, 2), (BASE_ID, 2),
    (BASE_ID, 1), (BASE_ID, 4),
    (BASE_ID, 3), (BASE_ID, 3),
    (BASE_ID, 3), (BASE_ID, 3),
)

START_AT = (700.0, 0.0)
SIGN_AT = (700.0, -350.0)
SIGN_Z = 110.0                  # the board is 220 tall and pivots at its centre
RING_SEGMENTS = 12

CUBE = "/Engine/BasicShapes/Cube.Cube"
CYL = "/Engine/BasicShapes/Cylinder.Cylinder"
M_FLOOR = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray"
M_STRIPE = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02"
M_DARK = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"
M_GLOW = "/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT"
M_HAZARD = "/Game/Variant_Combat/Materials/M_Lava"


def log(msg):
    unreal.log(f"FORGEHALL- {msg}")


def fail(msg):
    unreal.log_error(f"FORGEHALL-ERROR {msg}")
    raise SystemExit(1)


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def pads():
    """Every pad, in the order the fixture sorts them: by X, then by Y."""
    return [(x, y) for x in PAD_X for y in sorted(PAD_Y)]


def plaque_slots():
    """Every hanging point on the wall -- both sides of all four X positions. Only two
    of them carry a plaque, but the clearances are solved against ALL of them so the
    wall stays re-authorable without re-deriving the pad grid."""
    return [(x, s * PLAQUE_ABS_Y) for x in PLAQUE_X for s in (-1.0, 1.0)]


def hung():
    """Where the two plaques this level actually hangs stand."""
    return [(PLAQUE_X[slot], side * PLAQUE_ABS_Y) for _, slot, side in PLAQUES]


def plaque_stand(at):
    """Where the walk stops to read a plaque hanging at `at`: short of it, on the
    aisle side."""
    return (at[0], at[1] - math.copysign(PLAQUE_STAND_IN, at[1]))


def stones_expected():
    """Where the forge's own shelf-stones stand, derived the same way the actor's
    constructor derives them. Read back off the PLACED forge and compared, so a
    drift between this file and the C++ is caught here rather than at run time."""
    out = []
    for row in (-1.0, 1.0):
        for slot in range(5):
            out.append((FORGE_AT[0] - 600.0 - 700.0 * slot, row * 1250.0))
    return out


def lane_abs_y():
    """How far off the forge's line the lane behind it runs. SOLVED, not chosen, and
    solved by the same arithmetic the fixture uses: far enough out that a walker
    hauling a full load down it is plainly outside the forge's take reach, and near
    enough in that it is plainly clear of every shelf-stone's reach."""
    low = FORGE_REACH * FORGE_LANE_CLEAR_FACTOR
    high = min(abs(y) for _, y in stones_expected()) - PRODUCT_REACH * CLEAR_FACTOR
    if high - low < 100.0:
        fail(f"there is no lane behind the forge: it would have to run further than "
             f"{low:.0f} uu off the line (clear of the forge's {FORGE_REACH:.0f} uu "
             f"reach) and nearer than {high:.0f} uu (clear of a shelf-stone's "
             f"{PRODUCT_REACH:.0f} uu reach)")
    return (low + high) / 2.0


def parse_carving(text):
    """The step, the units and the single thing they make -- parsed here the same way
    the plaque and the fixture parse it, so a carving this file writes and a carving
    either of them reads can never mean two different things."""
    body, tier = text, 0
    if ":" in text:
        head, tail = text.split(":", 1)
        tokens = head.upper().split()
        if len(tokens) == 2 and tokens[0] == "TIER" and tokens[1].isdigit():
            tier, body = int(tokens[1]), tail
    if "->" not in body:
        return 0, [], ""
    left, right = body.split("->", 1)
    inputs = left.upper().split()
    outputs = right.upper().split()
    if not inputs or len(outputs) != 1:
        return 0, [], ""
    return tier, inputs, outputs[0]


def segments(pt_a, pt_b, n=40):
    for k in range(n + 1):
        t = k / n
        yield (pt_a[0] + (pt_b[0] - pt_a[0]) * t, pt_a[1] + (pt_b[1] - pt_a[1]) * t)


def check_geometry():
    """What has to be true before this level is worth saving.

    Everything here is the sweep the fixture will run at PrepareTest, done ahead of
    time on the same numbers -- so a layout mistake fails a 3-second authoring run
    instead of a 6-minute graded one.
    """
    P = pads()
    S = plaque_slots()
    forge = FORGE_AT
    stop = (FORGE_STOP_X, 0.0)
    lane = lane_abs_y()

    # 1. The delivery stop has to be plainly inside the forge's reach and plainly
    #    clear of the solid anvil, or a correct submission either misses the
    #    delivery or jams against the anvil and the run dies as a stall.
    if not (ANVIL_CLEAR + 50.0 < dist(stop, forge) < FORGE_REACH - 60.0):
        fail(f"the delivery stop is {dist(stop, forge):.0f} uu from the forge; it has "
             f"to be more than {ANVIL_CLEAR + 50.0:.0f} (clear of the anvil) and less "
             f"than {FORGE_REACH - 60.0:.0f} (plainly inside its reach)")

    # 2. No two pads within reach of each other, or one walk empties two heaps.
    for i in range(len(P)):
        for j in range(i + 1, len(P)):
            if dist(P[i], P[j]) < PAD_REACH * 2.0 * CLEAR_FACTOR:
                fail(f"pads {i + 1} and {j + 1} are {dist(P[i], P[j]):.0f} uu apart and "
                     f"each is taken from {PAD_REACH:.0f} uu; standing at one would be "
                     f"within reach of the other")

    # 3. The aisle itself must be clear of every pad and every plaque, because every
    #    walk in the hall runs down it.
    for i, p in enumerate(P):
        if abs(p[1]) < PAD_REACH * CLEAR_FACTOR:
            fail(f"pad {i + 1} sits {abs(p[1]):.0f} uu off the aisle and is taken from "
                 f"{PAD_REACH:.0f} uu; walking down the aisle would take from it")
    for i, s in enumerate(S):
        if abs(s[1]) < PLAQUE_READ_REACH * CLEAR_FACTOR:
            fail(f"plaque slot {i + 1} sits {abs(s[1]):.0f} uu off the aisle and is read "
                 f"from {PLAQUE_READ_REACH:.0f} uu; walking down the aisle would read it")

    # 4. Every spur -- aisle out to a pad, aisle out to a plaque -- must be clear of
    #    everything it did not go to. This is the check the two X grids exist for.
    def spur_is_clear(target, skip_pad=None, skip_slot=None, label=""):
        start = (target[0], 0.0)
        for pt in segments(start, target):
            for i, p in enumerate(P):
                if i == skip_pad:
                    continue
                if dist(pt, p) < PAD_REACH * CLEAR_FACTOR:
                    fail(f"the spur to {label} passes {dist(pt, p):.0f} uu from pad "
                         f"{i + 1}, which is taken from {PAD_REACH:.0f} uu")
            for i, s in enumerate(S):
                if i == skip_slot:
                    continue
                if dist(pt, s) < PLAQUE_READ_REACH * CLEAR_FACTOR:
                    fail(f"the spur to {label} passes {dist(pt, s):.0f} uu from plaque "
                         f"slot {i + 1}, which is read from {PLAQUE_READ_REACH:.0f} uu")

    for i, p in enumerate(P):
        spur_is_clear(p, skip_pad=i, label=f"pad {i + 1}")
    for i, s in enumerate(S):
        stand = plaque_stand(s)
        if dist(stand, s) > PLAQUE_READ_REACH * AT_FACTOR:
            fail(f"the stop for plaque slot {i + 1} is {dist(stand, s):.0f} uu from it "
                 f"and it is only read from {PLAQUE_READ_REACH:.0f} uu")
        spur_is_clear(stand, skip_slot=i, label=f"plaque slot {i + 1}")

    # 5. The errand behind the forge -- aisle, lane, stone -- must be clear of the
    #    anvil, of every stone but the one it went to, and of the forge's own take
    #    reach along the whole lane run. The last of those is what stops a walker
    #    hauling a full load from handing it over halfway down the lane.
    stones = stones_expected()
    for i, st in enumerate(stones):
        side = math.copysign(lane, st[1])
        path = [stop, (FORGE_STOP_X, side), (st[0], side), st]
        for a, b in zip(path, path[1:]):
            for pt in segments(a, b):
                if dist(pt, forge) < ANVIL_CLEAR:
                    fail(f"the errand to stone {i + 1} passes {dist(pt, forge):.0f} uu "
                         f"from the forge; the anvil is solid and the walk would jam")
                for j, other in enumerate(stones):
                    if j == i:
                        continue
                    if dist(pt, other) < PRODUCT_REACH * CLEAR_FACTOR:
                        fail(f"the errand to stone {i + 1} passes {dist(pt, other):.0f} "
                             f"uu from stone {j + 1}; whatever is standing there would "
                             f"be picked up in passing")
                for j, p in enumerate(P):
                    if dist(pt, p) < PAD_REACH * CLEAR_FACTOR:
                        fail(f"the errand to stone {i + 1} passes within reach of pad "
                             f"{j + 1}")
                for j, s in enumerate(S):
                    if dist(pt, s) < PLAQUE_READ_REACH * CLEAR_FACTOR:
                        fail(f"the errand to stone {i + 1} passes within reading "
                             f"distance of plaque slot {j + 1}")
        for pt in segments((FORGE_STOP_X, side), (st[0], side)):
            if dist(pt, forge) <= FORGE_REACH:
                fail(f"the lane to stone {i + 1} runs {lane:.0f} uu off the forge's "
                     f"line and passes {dist(pt, forge):.0f} uu from it, inside its "
                     f"{FORGE_REACH:.0f} uu reach; what the character is carrying "
                     f"would be handed over halfway")
    for i in range(len(stones)):
        for j in range(i + 1, len(stones)):
            if dist(stones[i], stones[j]) < PRODUCT_REACH * 2.0:
                fail(f"stones {i + 1} and {j + 1} are {dist(stones[i], stones[j]):.0f} "
                     f"uu apart; a product on one would be within reach of the other")

    # 6. NO STOP THE WALK MAKES, OTHER THAN THE DELIVERY STOP, MAY LIE INSIDE THE
    #    FORGE'S REACH. A stop that merely looks like transit but sits inside the
    #    reach hands over whatever the character is carrying at a moment nobody is
    #    modelling a delivery, and every count after it is wrong. The previous design
    #    of this task shipped exactly that mistake and it cost a graded run.
    transits = [(x, 0.0) for x in PAD_X] + [(x, 0.0) for x in PLAQUE_X]
    lane_ends = [(FORGE_STOP_X, lane), (FORGE_STOP_X, -lane)]
    for pt in transits + lane_ends + P + [plaque_stand(h) for h in hung()] + [START_AT]:
        if dist(pt, forge) <= FORGE_REACH:
            fail(f"the stop at ({pt[0]:.0f},{pt[1]:.0f}) is not the delivery stop and "
                 f"it stands {dist(pt, forge):.0f} uu from the forge, inside its "
                 f"{FORGE_REACH:.0f} uu reach")

    # 7. Everything on the floor, including every stop the walk makes.
    stops = [stop, START_AT, SIGN_AT] + P + stones + transits + lane_ends
    stops += [plaque_stand(s) for s in S]
    for pt in stops:
        if not (FLOOR_MIN[0] + 100.0 < pt[0] < FLOOR_MAX[0] - 100.0
                and FLOOR_MIN[1] + 100.0 < pt[1] < FLOOR_MAX[1] - 100.0):
            fail(f"a stop at ({pt[0]:.0f},{pt[1]:.0f}) is off the floor "
                 f"({FLOOR_MIN} .. {FLOOR_MAX})")

    # 8. THE WALL HAS TO CARVE A CHAIN, and the hall has to stock enough to walk it.
    #    Two steps at two different numbers, the top step eating exactly what the
    #    first step makes, three units each, and enough base material on the pads to
    #    complete the chain with room to spare.
    parsed = [parse_carving(text) for text, _, _ in PLAQUES]
    if len(parsed) != 2:
        fail(f"the wall carves {len(parsed)} recipe(s); this hall is a two-step chain")
    for (text, _, _), (tier, inputs, output) in zip(PLAQUES, parsed):
        if tier <= 0 or not inputs or not output:
            fail(f"'{text}' does not read as 'TIER n : UNIT UNIT UNIT -> THING'")
        if len(inputs) != RECIPE_SIZE:
            fail(f"'{text}' lists {len(inputs)} unit(s) and every step of this chain "
                 f"takes {RECIPE_SIZE}")
        if len(set(inputs)) != 1:
            fail(f"'{text}' merges {len(set(inputs))} different units; every step of "
                 f"this chain is three of a kind")
    low, high = sorted(parsed, key=lambda p: p[0])
    if low[0] == high[0]:
        fail(f"both plaques carve step {low[0]}; the forge makes the highest step it "
             f"can and two recipes at the same step would have no answer")
    if set(high[1]) != {low[2]}:
        fail(f"the top step needs {sorted(set(high[1]))} and the first step makes "
             f"{low[2]}; nothing the forge sets down would ever be an ingredient")
    if low[2] == high[2]:
        fail(f"both steps make {low[2]}; the output name is how a failure is "
             f"attributed to a recipe and it has to be unique")
    base = low[1][0]
    stocked = sum(units for name, units in STOCK if name == base)
    needed = RECIPE_SIZE * RECIPE_SIZE
    if stocked < needed:
        fail(f"the pads hold {stocked} unit(s) of {base} and the chain needs {needed} "
             f"to reach {high[2]}")
    if max(units for _, units in STOCK) <= CARRY_CAP:
        fail(f"no pad holds more than the carry cap of {CARRY_CAP}; nothing in the "
             f"hall would ever show a heap keeping what a full load left behind")

    log(f"geometry checked: {len(P)} pads, {len(S)} plaque slots, {len(stones)} stones, "
        f"lane at {lane:.0f} uu, chain {low[2]} -> {high[2]}, {stocked} base units "
        f"stocked against {needed} needed, cap {CARRY_CAP}, plaque stand-in "
        f"{PLAQUE_STAND_IN:.0f} uu")


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
    for cls_name in ("ForgeStationActor", "IngredientHeapActor", "RecipePlaqueActor",
                     "CarrySignActor", "ForgeCraftFunctionalTest"):
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


def paint_ring(env, centre, radius, label, material):
    """A reach, drawn on the floor. The numbers the grade uses are all written on the
    things themselves; this is what makes them legible to a human at a glance."""
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
    log(f"hall {span_x:.0f}x{span_y:.0f} + {n} stripes")

    forge = eas.spawn_actor_from_class(
        env["ForgeStationActor"], unreal.Vector(FORGE_AT[0], FORGE_AT[1], 0.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if forge is None:
        fail("could not place the forge")
    forge.set_actor_label("ForgeStation")
    forge.set_editor_property("take_reach_uu", FORGE_REACH)
    paint_ring(env, FORGE_AT, FORGE_REACH, "ForgeReach", M_GLOW)

    for i, (px, py) in enumerate(pads()):
        heap = eas.spawn_actor_from_class(
            env["IngredientHeapActor"], unreal.Vector(px, py, PAD_STAND_Z),
            unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
        if heap is None:
            fail(f"could not place heap {i + 1}")
        heap.set_actor_label(f"IngredientHeap_{i + 1}")
        heap.set_editor_property("ingredient_id", unreal.Name(STOCK[i][0]))
        heap.set_editor_property("units_in_heap", STOCK[i][1])
        heap.set_editor_property("reach_uu", PAD_REACH)
        # A flat pad under the heap, so the reach ring reads as belonging to something.
        block(env, CYL, unreal.Vector(px, py, 4.0), unreal.Vector(2.2, 2.2, 0.08),
              f"Pad_{i + 1}", M_DARK, collide=False)
        paint_ring(env, (px, py), PAD_REACH, f"PadReach_{i + 1}", M_HAZARD)

    for i, (text, slot, side) in enumerate(PLAQUES):
        sx, sy = PLAQUE_X[slot], side * PLAQUE_ABS_Y
        plaque = eas.spawn_actor_from_class(
            env["RecipePlaqueActor"], unreal.Vector(sx, sy, PLAQUE_Z),
            # Turned to face the aisle.
            unreal.Rotator(roll=0.0, pitch=0.0, yaw=180.0 if side < 0 else 0.0))
        if plaque is None:
            fail(f"could not place plaque {i + 1}")
        plaque.set_actor_label(f"RecipePlaque_{i + 1}")
        plaque.set_editor_property("carved_text", text)
        plaque.set_editor_property("read_reach_uu", PLAQUE_READ_REACH)
        # THE READING CIRCLE, at the hanging point that actually carries a plaque. The
        # wall does not move in this hall, so a circle painted at an empty hanging
        # point would be a promise about a recipe that is not there.
        paint_ring(env, (sx, sy), PLAQUE_READ_REACH, f"ReadReach_{i + 1}", M_GLOW)
        block(env, CYL, unreal.Vector(sx, sy, 4.0), unreal.Vector(1.4, 1.4, 0.08),
              f"HangingPoint_{i + 1}", M_DARK, collide=False)

    sign = eas.spawn_actor_from_class(
        env["CarrySignActor"], unreal.Vector(SIGN_AT[0], SIGN_AT[1], SIGN_Z),
        # Facing the aisle, so it is the first thing read on the way in.
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=180.0))
    if sign is None:
        fail("could not place the carry sign")
    sign.set_actor_label("CarrySign")
    sign.set_editor_property("carry_cap_units", CARRY_CAP)

    start = eas.spawn_actor_from_class(
        unreal.PlayerStart, unreal.Vector(START_AT[0], START_AT[1], 100.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=180.0))
    if start is None:
        fail("could not place PlayerStart")
    start.set_actor_label("PlayerStart")

    block(env, CUBE, unreal.Vector(mid_x, FLOOR_MAX[1] - 30.0, 120.0),
          unreal.Vector(span_x / 100.0, 0.4, 2.4), "Backdrop", M_DARK)
    for idx, lx in enumerate((FLOOR_MIN[0] + 300.0, FLOOR_MAX[0] - 300.0)):
        block(env, CYL, unreal.Vector(lx, FLOOR_MAX[1] - 500.0, 300.0),
              unreal.Vector(1.1 + idx * 0.9, 1.1 + idx * 0.9, 6.0), f"Landmark_{idx}",
              M_GLOW if idx else M_HAZARD)

    sun = eas.spawn_actor_from_class(
        unreal.DirectionalLight, unreal.Vector(mid_x, mid_y, 1200.0),
        unreal.Rotator(roll=0.0, pitch=-52.0, yaw=-120.0))
    sky = eas.spawn_actor_from_class(
        unreal.SkyLight, unreal.Vector(mid_x, mid_y, 1200.0),
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
        env["ForgeCraftFunctionalTest"],
        unreal.Vector(FLOOR_MIN[0] + 300.0, FLOOR_MIN[1] + 300.0, 120.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if fixture is None:
        fail("could not place the functional test")
    fixture.set_actor_label("ForgeCraftFunctionalTest")

    world = unreal.EditorLevelLibrary.get_editor_world()
    if world.get_world_settings().get_editor_property("default_game_mode") is not None:
        fail("world settings already name a game mode; this level must inherit the "
             "project default so the play lane comes for free")
    log("world settings: no game mode named (inherits BP_ThirdPersonGameMode)")

    # ---- read the level back ------------------------------------------------
    placed = eas.get_all_level_actors()
    forges = [a for a in placed if a.actor_has_tag("ForgeStation")]
    heaps = [a for a in placed if a.actor_has_tag("IngredientHeap")]
    slabs = [a for a in placed if a.actor_has_tag("RecipePlaque")]
    signs = [a for a in placed if a.actor_has_tag("CarrySign")]
    if len(forges) != 1:
        fail(f"{len(forges)} actor(s) tagged ForgeStation, expected 1")
    if len(heaps) != len(pads()):
        fail(f"{len(heaps)} actor(s) tagged IngredientHeap, expected {len(pads())}")
    if len(slabs) != len(PLAQUES):
        fail(f"{len(slabs)} actor(s) tagged RecipePlaque, expected {len(PLAQUES)}")
    if len(signs) != 1:
        fail(f"{len(signs)} actor(s) tagged CarrySign, expected 1")

    # THE SHELF-STONES ARE THE FORGE'S OWN COMPONENTS, so where they stand comes from
    # the C++ constructor and not from this file. Read them back and compare, or a
    # drift between the two would only surface as an unwalkable errand mid-run --
    # and the lane this script solved would be solved against the wrong row.
    got_stones = sorted(
        (round(c.get_world_location().x), round(c.get_world_location().y))
        for c in forges[0].get_components_by_class(unreal.StaticMeshComponent)
        if c.get_name().startswith("Shelf"))
    want_stones = sorted((round(x), round(y)) for x, y in stones_expected())
    if got_stones != want_stones:
        fail(f"the forge's shelf-stones stand at {got_stones} and this script solved "
             f"its clearances against {want_stones}; the level and the C++ have drifted")

    for a in heaps:
        if a.get_editor_property("units_in_heap") <= 0:
            fail(f"{a.get_actor_label()} was placed empty")
        if a.get_editor_property("ingredient_id") == unreal.Name("None"):
            fail(f"{a.get_actor_label()} has no ingredient name")
    for a in slabs:
        carved = a.get_editor_property("carved_text")
        tier, inputs, output = parse_carving(carved)
        if tier <= 0 or not inputs or not output:
            fail(f"{a.get_actor_label()} is carved '{carved}', which does not read as "
                 f"'TIER n : UNIT UNIT UNIT -> THING'")
        # MOVABLE: PIE scores moving a STATIC component as a failed test, and the
        # fixture rewrites the visible carving when it re-carves the wall.
        if a.get_editor_property("slab").get_editor_property("mobility") != \
                unreal.ComponentMobility.MOVABLE:
            fail(f"{a.get_actor_label()}'s slab is not MOVABLE")
    if signs[0].get_editor_property("carry_cap_units") != CARRY_CAP:
        fail(f"the sign posts a cap of "
             f"{signs[0].get_editor_property('carry_cap_units')}, expected {CARRY_CAP}")
    if signs[0].get_editor_property("post").get_editor_property("mobility") != \
            unreal.ComponentMobility.MOVABLE:
        fail("the carry sign's post is not MOVABLE; the fixture rewrites its notice "
             "when it re-posts the cap")

    lit = [a for a in placed
           if a.get_class().get_name() in ("DirectionalLight", "SkyLight")]
    if len(lit) < 2:
        fail(f"level has {len(lit)} light actor(s); a capture still would be black")

    log(f"read back: 1 forge, {len(heaps)} heaps, {len(slabs)} plaques, 1 carry sign "
        f"posting {CARRY_CAP}, {len(got_stones)} shelf-stones")

    if not les.save_current_level():
        fail("save_current_level() returned False")
    log(f"SAVED {MAP_PKG}")


main()

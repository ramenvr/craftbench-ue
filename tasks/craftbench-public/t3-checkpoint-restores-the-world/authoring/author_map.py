"""Authors L_CheckpointYard for t3-checkpoint-restores-the-world.

    UnrealEditor-Cmd.exe <ThirdPerson.uproject> -run=pythonscript \
        -script="<abs path to this file>" -nullrhi -unattended -nopause \
        -log -stdout -FullStdOutLogOutput

THE YARD IS FOUR LANES. Everything that can be stood on sits in one of them, and the
drive walks the empty band between two of them:

    y = +3600   the door leaves, in a low wall down one side
    y = +2900   their floor plates, out on the open floor
    y = +1500   the coins on their stands, and the counter with its painted line
    y =  +400   THE WALKING LANE -- nothing is placed here, ever
    y =  -700   the checkpoint pads
    y = -2700   the two strips of hot floor

That is not decoration. The fixture DERIVES its walking lane as the middle of the widest
empty band between the yard's occupied lanes, so the lanes below are chosen to make the
pad/coin band the widest one -- and this script refuses to save a level where that is not
true, or where any of the fixture's other staging invariants fails. Solve the geometry,
do not tune it: every number below is checked against the rule it exists to satisfy, and
a violation raises before the level is written.

The pads are numbered by how far into the yard they are, and the SCRIPT the fixture
walks marks them in the opposite order. That is the whole discrimination for the mark
gate, so `check_geometry` refuses a layout where the numbering does not track depth.

This level names NO game mode: it inherits the project default, so both halves of
Enhanced Input survive and the yard can be played by hand
(the 2026-08-17 unplayable-play-lane finding).

Every Rotator is built with KEYWORDS -- unreal.Rotator's positional order is
(roll, pitch, yaw).
"""
import math

import unreal

TASK = "t3-checkpoint-restores-the-world"
MAP_PKG = f"/Game/Maps/{TASK}/L_CheckpointYard"

FLOOR_MIN = (-3400.0, -3600.0)
FLOOR_MAX = (7200.0, 4800.0)
STRIPE_EVERY = 800.0

ENTRANCE = (-2400.0, 400.0)

DOOR_Y = 3600.0
PLATE_DY = -700.0          # the plate sits this far from the door, on the open floor
COIN_Y = 1500.0
PAD_Y = -700.0
HAZARD_Y = -2700.0
OPEN_SLIDE = 450.0         # the leaf slides AWAY from the plate, along local +Y

# (DoorId, x). Sorted DoorId order is the order the drive uses them in.
DOORS = (("DoorA", -1400.0), ("DoorB", 1600.0), ("DoorC", 5300.0))
# (CoinId, x). Sorted CoinId order is the order the drive takes them in.
COINS = (("Coin0", -400.0), ("Coin1", 700.0), ("Coin2", 2400.0),
         ("Coin3", 4400.0), ("Coin4", 6100.0))
# (StandOrder, x). Numbered by depth; the drive marks them 2, then 1, then 0.
PADS = ((0, 1200.0), (1, 3800.0), (2, 5900.0))
HAZARDS = (200.0, 4900.0)

# The counter's line volume sits 150 uu on the arriving side of the actor.
COUNTER_X = 3550.0
COUNTER_LINE_X = COUNTER_X - 150.0
STARTING_BANKED = 4

# Component Z, mirroring CheckpointYardProps.cpp. The pad's and the coin's volumes are
# their ROOTS, so the actor's own Z is the volume's centre.
PAD_Z = 110.0
COIN_Z = 120.0
HAZARD_Z = 60.0
DOOR_Z = 0.0
COUNTER_Z = 0.0

# Half-extents of every trigger volume, mirroring CheckpointYardProps.cpp. Kept here so
# the checks below measure the same boxes the fixture measures.
EXT_PAD = (170.0, 170.0)
EXT_PLATE = (130.0, 130.0)
EXT_COIN = (130.0, 130.0)
EXT_COUNTER = (140.0, 320.0)
EXT_HAZARD = (700.0, 300.0)

# Mirrors the fixture's own thresholds. If either side moves, both must.
MIN_LANE_GAP = 1200.0
MIN_CORRIDOR_CLEAR = 600.0
MIN_CROSS_CLEAR = 220.0
MIN_RESPAWN_TO_HAZARD = 1500.0
MIN_RESPAWN_TO_COUNTER = 1500.0
MIN_RESPAWN_TO_COIN = 400.0
MIN_PAD_DEPTH_STEP = 500.0

CUBE = "/Engine/BasicShapes/Cube.Cube"
CYL = "/Engine/BasicShapes/Cylinder.Cylinder"
M_FLOOR = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray"
M_STRIPE = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02"
M_DARK = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"
M_GLOW = "/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT"
M_LAVA = "/Game/Variant_Combat/Materials/M_Lava"

CLASSES = ("CheckpointStandActor", "LatchDoorActor", "CoinPickupActor",
           "BankCounterActor", "HazardStripActor", "CheckpointDirectorActor",
           "CheckpointRestoreFunctionalTest")


def log(msg):
    unreal.log(f"CHECKPOINTYARD- {msg}")


def fail(msg):
    unreal.log_error(f"CHECKPOINTYARD-ERROR {msg}")
    raise SystemExit(1)


# ---------------------------------------------------------------------------
# The geometry, solved and then checked
# ---------------------------------------------------------------------------

def volumes():
    """Every trigger volume the fixture will measure: (label, cx, cy, ex, ey)."""
    out = []
    for order, x in PADS:
        out.append((f"pad{order}", x, PAD_Y, EXT_PAD[0], EXT_PAD[1]))
    for door_id, x in DOORS:
        out.append((f"plate:{door_id}", x, DOOR_Y + PLATE_DY, EXT_PLATE[0], EXT_PLATE[1]))
    for coin_id, x in COINS:
        out.append((f"coin:{coin_id}", x, COIN_Y, EXT_COIN[0], EXT_COIN[1]))
    out.append(("counter", COUNTER_LINE_X, COIN_Y, EXT_COUNTER[0], EXT_COUNTER[1]))
    for i, x in enumerate(HAZARDS):
        out.append((f"hazard{i}", x, HAZARD_Y, EXT_HAZARD[0], EXT_HAZARD[1]))
    return out


def dist_to_volume(vol, px, py):
    _, cx, cy, ex, ey = vol
    dx = max(0.0, abs(px - cx) - ex)
    dy = max(0.0, abs(py - cy) - ey)
    return math.hypot(dx, dy)


def derive_corridor():
    """The same derivation the fixture performs: the middle of the widest gap between
    the occupied lanes. Computing it here rather than writing it down is what keeps the
    two in step."""
    ys = sorted({round(v[2], 3) for v in volumes()})
    best_gap, corridor = -1.0, None
    for a, b in zip(ys, ys[1:]):
        if b - a > best_gap:
            best_gap, corridor = b - a, 0.5 * (a + b)
    return corridor, best_gap, ys


def check_geometry():
    vols = volumes()
    corridor, gap, ys = derive_corridor()
    if corridor is None:
        fail("the yard has no lanes to walk between")
    if gap < MIN_LANE_GAP:
        fail(f"the widest empty band between lanes is {gap:.0f} uu and the drive needs "
             f"{MIN_LANE_GAP:.0f}; lanes at {[int(y) for y in ys]}")
    # The band the fixture will pick has to be the pad/coin one. If it picked another,
    # every leg would cross a lane the layout never planned for.
    if not (PAD_Y < corridor < COIN_Y):
        fail(f"the widest band is at y={corridor:.0f}, which is not between the pads "
             f"({PAD_Y:.0f}) and the coins ({COIN_Y:.0f}); the fixture would derive a "
             f"walking lane this layout was not built around")

    # 1. The lane itself must be clear along the whole yard.
    xs = [v[1] for v in vols]
    x0, x1 = min(xs) - 400.0, max(xs) + 400.0
    clear = min(dist_to_volume(v, x0 + (x1 - x0) * k / 200.0, corridor)
                for v in vols for k in range(201))
    if clear < MIN_CORRIDOR_CLEAR:
        fail(f"the walking lane passes {clear:.0f} uu from a prop and the drive needs "
             f"{MIN_CORRIDOR_CLEAR:.0f}")

    # 2. Every straight walk in and out of a prop must clear every OTHER prop. That is
    #    the whole of the route geometry: out to the lane, along it, in to the stop.
    for own in vols:
        for k in range(41):
            py = own[2] + (corridor - own[2]) * k / 40.0
            for other in vols:
                if other is own:
                    continue
                d = dist_to_volume(other, own[1], py)
                if d < MIN_CROSS_CLEAR:
                    fail(f"the walk in and out of {own[0]} passes {d:.0f} uu from "
                         f"{other[0]}, and {MIN_CROSS_CLEAR:.0f} is the least that keeps "
                         f"the character from brushing a prop the script never aimed at")

    # 3. A pad somebody is sent back to has to be far from the things that would grade
    #    them wrongly: hot floor they would walk back into while the gate watches, the
    #    line they could bank at by accident, a stand whose coin would be retaken.
    for order, x in PADS:
        for v in vols:
            d = dist_to_volume(v, x, PAD_Y)
            if v[0].startswith("hazard") and d < MIN_RESPAWN_TO_HAZARD:
                fail(f"pad {order} sends somebody back {d:.0f} uu from {v[0]}; the gate "
                     f"then watches them stay clear of hot floor for 3 s, which is "
                     f"1500 uu of walking")
            if v[0] == "counter" and d < MIN_RESPAWN_TO_COUNTER:
                fail(f"pad {order} sends somebody back {d:.0f} uu from the line; a "
                     f"respawn that close could bank a handful by accident")
            if v[0].startswith("coin:") and d < MIN_RESPAWN_TO_COIN:
                fail(f"pad {order} sends somebody back {d:.0f} uu from {v[0]}; a coin "
                     f"put back under their feet would be taken again in the same breath")

    # 4. The numbering has to TRACK DEPTH, or "the pad furthest in wins" is not a reading
    #    anybody could hold and the mark gate would measure nothing.
    ordered = sorted(PADS)
    prev = None
    for order, x in ordered:
        d = math.hypot(x - ENTRANCE[0], PAD_Y - ENTRANCE[1])
        if prev is not None and d <= prev + MIN_PAD_DEPTH_STEP:
            fail(f"pad {order} is {d:.0f} uu into the yard and the pad before it is "
                 f"{prev:.0f}; the numbering does not track depth, so recency and depth "
                 f"would not be two different answers")
        prev = d

    # 5. Everything has to fit on the floor, INCLUDING an open leaf.
    for door_id, x in DOORS:
        for label, y in ((f"{door_id} leaf shut", DOOR_Y),
                         (f"{door_id} leaf open", DOOR_Y + OPEN_SLIDE),
                         (f"{door_id} plate", DOOR_Y + PLATE_DY)):
            if not (FLOOR_MIN[1] + 100.0 < y < FLOOR_MAX[1] - 100.0):
                fail(f"{label} lands at y={y:.0f}, off a floor of "
                     f"{FLOOR_MIN[1]:.0f}..{FLOOR_MAX[1]:.0f}")
        if not (FLOOR_MIN[0] + 300.0 < x < FLOOR_MAX[0] - 300.0):
            fail(f"{door_id} sits at x={x:.0f}, off the floor")
    for _, x in COINS + PADS:
        if not (FLOOR_MIN[0] + 300.0 < x < FLOOR_MAX[0] - 300.0):
            fail(f"a prop sits at x={x:.0f}, off the floor")
    for x in HAZARDS:
        if not (FLOOR_MIN[0] + 800.0 < x < FLOOR_MAX[0] - 800.0):
            fail(f"a strip of hot floor sits at x={x:.0f}, off the floor")

    # 6. The board has to have something on it before anybody arrives, or a submission
    #    that zeroes the counter is indistinguishable from one that leaves it alone.
    if STARTING_BANKED <= 0:
        fail("STARTING_BANKED must be greater than zero")

    # 7. Distinct ids, or nothing can be named in a failure message.
    if len({d for d, _ in DOORS}) != len(DOORS):
        fail("two doors share a DoorId")
    if len({c for c, _ in COINS}) != len(COINS):
        fail("two coins share a CoinId")
    if len({o for o, _ in PADS}) != len(PADS):
        fail("two pads share a StandOrder")

    log(f"geometry checked: lanes {[int(y) for y in ys]}, walking lane derived at "
        f"y={corridor:.0f} with {clear:.0f} uu of clearance, {len(PADS)} pads "
        f"{len(DOORS)} doors {len(COINS)} coins {len(HAZARDS)} hazards, BANKED opens "
        f"at {STARTING_BANKED}")
    return corridor


# ---------------------------------------------------------------------------
# Placement
# ---------------------------------------------------------------------------

def probe():
    got = {}
    for name, cls in (("les", unreal.LevelEditorSubsystem),
                      ("eas", unreal.EditorActorSubsystem)):
        sub = unreal.get_editor_subsystem(cls)
        if sub is None:
            fail(f"subsystem {cls.__name__} is unavailable in this boot")
        got[name] = sub
    for path in (CUBE, CYL, M_FLOOR, M_STRIPE, M_DARK, M_GLOW, M_LAVA):
        if not unreal.EditorAssetLibrary.does_asset_exist(path):
            fail(f"asset missing: {path}")
    for cls_name in CLASSES:
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
        # into a saved level on the marked-ground task, and paint that quietly blocks is
        # indistinguishable from a bug in the submission.
        comp.set_collision_profile_name("NoCollision")
        comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    actor.set_actor_scale3d(scale)
    return actor


def place(env, cls_name, loc, label, yaw=0.0):
    actor = env["eas"].spawn_actor_from_class(
        env[cls_name], loc, unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
    if actor is None:
        fail(f"could not place {label}")
    actor.set_actor_label(label)
    return actor


def main():
    env = probe()
    les, eas = env["les"], env["eas"]
    corridor = check_geometry()

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

    # The walking lane is painted, so a person watching can see that the drive keeps to
    # the empty band and never brushes anything.
    block(env, CUBE, unreal.Vector(mid_x, corridor, 2.0),
          unreal.Vector(span_x / 100.0, 0.5, 0.03), "WalkingLane", M_STRIPE,
          collide=False)
    n = 0
    x = FLOOR_MIN[0] + STRIPE_EVERY
    while x < FLOOR_MAX[0]:
        block(env, CUBE, unreal.Vector(x, mid_y, 1.5),
              unreal.Vector(0.06, span_y / 100.0, 0.02), f"Stripe_{n:02d}", M_STRIPE,
              collide=False)
        n += 1
        x += STRIPE_EVERY
    log(f"floor {span_x:.0f}x{span_y:.0f} + {n} stripes + a painted walking lane")

    for order, x in PADS:
        pad = place(env, "CheckpointStandActor",
                    unreal.Vector(x, PAD_Y, PAD_Z), f"CheckpointStand_{order}")
        pad.set_editor_property("stand_order", order)

    # The doors stand in a low wall down one side. The wall is scenery -- the route never
    # goes through a doorway, deliberately: a submission that wrongly shuts a door would
    # otherwise jam the drive and report as a stall instead of naming the door.
    for door_id, x in DOORS:
        door = place(env, "LatchDoorActor", unreal.Vector(x, DOOR_Y, DOOR_Z), door_id)
        door.set_editor_property("door_id", unreal.Name(door_id))
        door.set_editor_property("open_slide_uu", OPEN_SLIDE)
        door.set_editor_property("plate_offset_uu",
                                 unreal.Vector(0.0, PLATE_DY, 0.0))
    # Wall stubs BETWEEN the doors, on the doors' own line, so the three leaves read as
    # gates in a wall rather than three slabs standing in a field. Each stub is solved
    # from the gap it fills and then checked: a stub that reached a leaf would stop that
    # leaf sliding and turn a working door into a jammed one.
    door_xs = sorted(x for _, x in DOORS)
    leaf_half = 200.0                     # the leaf is 400 uu across (scale 4.0)
    edges = [FLOOR_MIN[0] + 300.0] + door_xs + [FLOOR_MAX[0] - 300.0]
    stub = 0
    for lo, hi in zip(edges, edges[1:]):
        a = lo + (leaf_half + 150.0 if lo in door_xs else 0.0)
        b = hi - (leaf_half + 150.0 if hi in door_xs else 0.0)
        if b - a < 400.0:
            continue
        for dx in door_xs:
            if a < dx + leaf_half + 100.0 and b > dx - leaf_half - 100.0:
                fail(f"a wall stub spanning x={a:.0f}..{b:.0f} reaches door x={dx:.0f}; "
                     f"it would stop that leaf sliding")
        block(env, CUBE, unreal.Vector(0.5 * (a + b), DOOR_Y, 170.0),
              unreal.Vector((b - a) / 100.0, 0.4, 3.4), f"WallStub_{stub}", M_DARK)
        stub += 1
    log(f"{stub} wall stub(s) between {len(DOORS)} doors")

    for coin_id, x in COINS:
        coin = place(env, "CoinPickupActor", unreal.Vector(x, COIN_Y, COIN_Z), coin_id)
        coin.set_editor_property("coin_id", unreal.Name(coin_id))

    counter = place(env, "BankCounterActor",
                    unreal.Vector(COUNTER_X, COIN_Y, COUNTER_Z), "BankCounter")
    counter.set_editor_property("starting_banked", STARTING_BANKED)
    # THE LINE, painted where the counter's volume is, so crossing it is a thing a
    # person can see happen.
    block(env, CUBE, unreal.Vector(COUNTER_LINE_X, COIN_Y, 2.0),
          unreal.Vector(0.3, 2.0 * EXT_COUNTER[1] / 100.0, 0.04), "PaintedLine", M_GLOW,
          collide=False)

    for i, x in enumerate(HAZARDS):
        place(env, "HazardStripActor", unreal.Vector(x, HAZARD_Y, HAZARD_Z),
              f"HazardStrip_{i}")

    place(env, "CheckpointDirectorActor",
          unreal.Vector(ENTRANCE[0], ENTRANCE[1] - 900.0, 120.0), "CheckpointDirector")

    start = eas.spawn_actor_from_class(
        unreal.PlayerStart, unreal.Vector(ENTRANCE[0], ENTRANCE[1], 100.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if start is None:
        fail("could not place PlayerStart")
    start.set_actor_label("PlayerStart")

    # Backdrop + landmarks, so a moving camera reads as moving.
    block(env, CUBE, unreal.Vector(mid_x, FLOOR_MIN[1] + 40.0, 140.0),
          unreal.Vector(span_x / 100.0, 0.5, 2.8), "Backdrop", M_DARK)
    for idx, lx in enumerate((FLOOR_MIN[0] + 400.0, mid_x, FLOOR_MAX[0] - 400.0)):
        block(env, CYL, unreal.Vector(lx, FLOOR_MIN[1] + 500.0, 300.0),
              unreal.Vector(1.0 + idx * 0.8, 1.0 + idx * 0.8, 6.0), f"Landmark_{idx}",
              M_GLOW if idx % 2 else M_LAVA)

    sun = eas.spawn_actor_from_class(
        unreal.DirectionalLight, unreal.Vector(mid_x, mid_y, 1400.0),
        unreal.Rotator(roll=0.0, pitch=-50.0, yaw=-125.0))
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

    place(env, "CheckpointRestoreFunctionalTest",
          unreal.Vector(FLOOR_MIN[0] + 300.0, FLOOR_MIN[1] + 300.0, 200.0),
          "CheckpointRestoreFunctionalTest")

    # ---- read back what was actually placed -------------------------------
    world = unreal.EditorLevelLibrary.get_editor_world()
    if world.get_world_settings().get_editor_property("default_game_mode") is not None:
        fail("world settings already name a game mode; this level must inherit the "
             "project default so the play lane comes for free")
    log("world settings: no game mode named (inherits BP_ThirdPersonGameMode)")

    actors = eas.get_all_level_actors()

    def tagged(tag):
        return [a for a in actors if a.actor_has_tag(tag)]

    for tag, want in (("CheckpointStand", len(PADS)), ("LatchDoor", len(DOORS)),
                      ("CoinPickup", len(COINS)), ("BankCounter", 1),
                      ("HazardStrip", len(HAZARDS)), ("CheckpointDirector", 1)):
        got = len(tagged(tag))
        if got != want:
            fail(f"{got} actor(s) tagged {tag}, expected {want}")

    orders = sorted(int(a.get_editor_property("stand_order"))
                    for a in tagged("CheckpointStand"))
    if orders != sorted(o for o, _ in PADS):
        fail(f"the placed pads read back StandOrder {orders}, expected "
             f"{sorted(o for o, _ in PADS)}; the numbering did not survive placement")

    for a in tagged("LatchDoor"):
        slide = float(a.get_editor_property("open_slide_uu"))
        if abs(slide - OPEN_SLIDE) > 1.0:
            fail(f"{a.get_actor_label()} reads back a slide of {slide:.0f} uu, expected "
                 f"{OPEN_SLIDE:.0f}; the two places the leaf lives are what the door "
                 f"gate measures against")
        off = a.get_editor_property("plate_offset_uu")
        if abs(off.y - PLATE_DY) > 1.0:
            fail(f"{a.get_actor_label()} reads back a plate offset of {off.y:.0f}, "
                 f"expected {PLATE_DY:.0f}")

    banked = int(tagged("BankCounter")[0].get_editor_property("starting_banked"))
    if banked != STARTING_BANKED:
        fail(f"the counter reads back StartingBanked {banked}, expected "
             f"{STARTING_BANKED}")

    for a in tagged("CoinPickup"):
        mob = a.get_editor_property("trigger").get_editor_property("mobility")
        if mob != unreal.ComponentMobility.MOVABLE:
            fail(f"{a.get_actor_label()} is not MOVABLE; the fixture moves the coins "
                 f"part way through the run and PIE logs a mobility error for a static "
                 f"actor, which the functional test scores as a FAIL")

    lit = [a for a in actors
           if a.get_class().get_name() in ("DirectionalLight", "SkyLight")]
    if len(lit) < 2:
        fail(f"level has {len(lit)} light actor(s); a capture still would be black")

    log(f"read back: {len(tagged('CheckpointStand'))} pads with orders {orders}, "
        f"{len(tagged('LatchDoor'))} doors, {len(tagged('CoinPickup'))} coins all "
        f"movable, BANKED opens at {banked}, {len(tagged('HazardStrip'))} hazards, "
        f"one director, one fixture")

    if not les.save_current_level():
        fail("save_current_level() returned False")
    log(f"SAVED {MAP_PKG}")


main()

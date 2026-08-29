"""Authors L_MarketYard for t2-shop-takes-your-coins-and-remembers.

    UnrealEditor-Cmd.exe <ThirdPerson.uproject> -run=pythonscript \
        -script="<abs path to this file>" -nullrhi -unattended -nopause \
        -log -stdout -FullStdOutLogOutput

THREE STALLS IN A ROW, each with its own price, its own stock, its own capacity and
its own mat, plus a board by the gate. The stalls are placed MOVABLE because the
fixture destroys all three and the board part way through the day and spawns fresh
ones one place further along the row -- PIE scores moving a STATIC actor as a failed
test (the lesson the crate task's spec records).

THE NUMBERS IN THIS LEVEL ARE DECOYS AND THE SCRIPT ENFORCES THAT. The fixture stages
its own prices, stocks, capacities, deliveries and purse before anybody's BeginPlay,
and they are deliberately unlike the ones written here: an agent that reads the level
binary and hard-codes what it finds gets every number wrong. `check_geometry` refuses
to save a level whose authored numbers have drifted into agreeing with the fixture's.

Every clearance the fixture's route depends on is SOLVED from the layout here rather
than hand-tuned: the lane points, the gate and the walk between them are derived with
the same constants the fixture uses, and the script raises rather than saving a yard
the walk could not be run in.

This level names NO game mode: it inherits the project default, so the play lane comes
for free (see the 2026-08-17 unplayable-play-lane finding).

Every Rotator is built with KEYWORDS -- unreal.Rotator's positional order is
(roll, pitch, yaw).
"""
import math

import unreal

TASK = "t2-shop-takes-your-coins-and-remembers"
MAP_PKG = f"/Game/Maps/{TASK}/L_MarketYard"

FLOOR_MIN = (-2600.0, -1600.0)
FLOOR_MAX = (2600.0, 1200.0)
STRIPE_EVERY = 400.0

# (x, y) of each stall, left to right along the row. The counter is 200 x 100 x 200
# and stands at half its own height.
STALL_XY = (-900.0, 0.0, 900.0)
STALL_ROW_Y = 600.0
STALL_STAND_Z = 100.0
LEDGER_XY = (-1700.0, 100.0)
LEDGER_STAND_Z = 150.0
PLAYER_START = (0.0, -1100.0)

# The scaffold's own geometry, in the stall's local frame. Mirrored here so the
# clearances below are SOLVED rather than eyeballed.
MAT_LOCAL_Y = -300.0
MAT_HALF = 120.0
COUNTER_HALF_X = 100.0
COUNTER_HALF_Y = 50.0

# Mirrors the fixture's route constants exactly.
LANE_OUT_UU = 700.0
GATE_EXTRA_UU = 400.0
MIN_MAT_CLEARANCE_UU = 250.0
MIN_COUNTER_CLEARANCE_UU = 150.0

# THE DECOYS. What is written into this level, and what the fixture stages, must not
# agree -- that mismatch is the whole reason reading the .umap is a wrong turn.
# (goods, price, stock, capacity)
GOODS = (
    ("Rope", 12, 5, 7),
    ("Lantern", 18, 4, 6),
    ("Apple", 9, 6, 8),
)
DECOY_COINS = 500
DECOY_CARRY = 9

# The fixture's set 0, so the script can prove the decoys really are decoys.
FIXTURE_SET0_COINS = 240
FIXTURE_SET0_CARRY = 3
FIXTURE_SET0 = ((30, 2, 4), (40, 2, 3), (55, 4, 6))

CUBE = "/Engine/BasicShapes/Cube.Cube"
CYL = "/Engine/BasicShapes/Cylinder.Cylinder"
M_FLOOR = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray"
M_STRIPE = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02"
M_DARK = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"
M_GLOW = "/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT"
M_HAZARD = "/Game/Variant_Combat/Materials/M_Lava"


def log(msg):
    unreal.log(f"MARKETYARD- {msg}")


def fail(msg):
    unreal.log_error(f"MARKETYARD-ERROR {msg}")
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
    for cls_name in ("MarketStallActor", "MarketLedgerActor",
                     "MarketDayFunctionalTest"):
        if not hasattr(unreal, cls_name):
            fail(f"class {cls_name} is not exposed to python - is the module built?")
        got[cls_name] = getattr(unreal, cls_name)
    log(f"probe OK: {sorted(got)}")
    return got


def mat_centre(index):
    """Where the mat of stall `index` ends up in the world. Stalls face -Y, so the
    scaffold's local -300 in Y lands 300 in front of the counter."""
    return (STALL_XY[index], STALL_ROW_Y + MAT_LOCAL_Y)


def lane_point(index):
    """The fixture's lane point: LANE_OUT_UU further out along the counter->mat line."""
    mx, my = mat_centre(index)
    return (mx, my - LANE_OUT_UU)


def gate_point():
    lanes = [lane_point(i) for i in range(len(STALL_XY))]
    mx = sum(p[0] for p in lanes) / len(lanes)
    my = sum(p[1] for p in lanes) / len(lanes)
    return (mx, my - GATE_EXTRA_UU)


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def on_floor(p, margin=100.0):
    return (FLOOR_MIN[0] + margin <= p[0] <= FLOOR_MAX[0] - margin
            and FLOOR_MIN[1] + margin <= p[1] <= FLOOR_MAX[1] - margin)


def check_geometry():
    """What has to be true before the level is worth saving. Every clearance below is
    the one the FIXTURE will re-check at runtime, computed the same way, so a yard
    that would abort the walk never reaches the disk."""
    names = [g[0] for g in GOODS]
    if len(set(names)) != len(names):
        fail(f"two stalls sell the same thing ({names}); a stall is known by what it "
             f"sells and by nothing else")
    if len(GOODS) != len(STALL_XY):
        fail(f"{len(GOODS)} kinds of goods for {len(STALL_XY)} stalls")

    # THE DECOYS MUST STAY DECOYS. If the level's numbers ever drift into agreeing
    # with the fixture's, an agent that reads the level binary is suddenly right and
    # the task quietly stops measuring what it claims to.
    if DECOY_COINS == FIXTURE_SET0_COINS or DECOY_CARRY == FIXTURE_SET0_CARRY:
        fail(f"the level's purse/carry ({DECOY_COINS}/{DECOY_CARRY}) match the "
             f"fixture's staged ({FIXTURE_SET0_COINS}/{FIXTURE_SET0_CARRY}); reading "
             f"the level would become a correct answer")
    for idx, (goods, price, stock, cap) in enumerate(GOODS):
        fp, fs, fc = FIXTURE_SET0[idx]
        if price == fp or stock == fs or cap == fc:
            fail(f"stall {idx + 1} ({goods}) is authored {price}/{stock}/{cap} and "
                 f"the fixture stages {fp}/{fs}/{fc}; at least one number agrees, so "
                 f"reading the level binary would be partly right")
        if stock > cap:
            fail(f"stall {idx + 1} ({goods}) holds {stock} but can only hold {cap}")

    # NO TWO MATS MAY TOUCH, and no mat may reach its neighbour's counter, or there is
    # nowhere to stand that is on exactly one stall's mat.
    for i in range(len(STALL_XY)):
        for j in range(len(STALL_XY)):
            if i == j:
                continue
            d = dist(mat_centre(i), mat_centre(j))
            if d < 2.0 * MAT_HALF + MIN_MAT_CLEARANCE_UU:
                fail(f"the mats of stalls {i + 1} and {j + 1} are {d:.0f} uu apart; "
                     f"they need {2.0 * MAT_HALF + MIN_MAT_CLEARANCE_UU:.0f} so that "
                     f"standing on one is never standing on the other")

    # Every stop the fixture will drive to has to be on the floor, clear of every
    # counter, and clear of every mat it is not about.
    stops = [(f"lane {i + 1}", lane_point(i)) for i in range(len(STALL_XY))]
    stops.append(("gate", gate_point()))
    for label, p in stops:
        if not on_floor(p):
            fail(f"the {label} stop lands at ({p[0]:.0f},{p[1]:.0f}), off a floor of "
                 f"{FLOOR_MIN}..{FLOOR_MAX}")
        for i in range(len(STALL_XY)):
            counter = (STALL_XY[i], STALL_ROW_Y)
            if dist(p, counter) < MIN_COUNTER_CLEARANCE_UU + COUNTER_HALF_Y:
                fail(f"the {label} stop is {dist(p, counter):.0f} uu from stall "
                     f"{i + 1}'s counter; the character would be pushing it")
            if label != f"lane {i + 1}" and dist(p, mat_centre(i)) \
                    < MIN_MAT_CLEARANCE_UU:
                fail(f"the {label} stop is {dist(p, mat_centre(i)):.0f} uu from stall "
                     f"{i + 1}'s mat, close enough to be standing on it")

    # And no leg of the walk may pass through a counter. The fixture samples 40 points
    # per leg; so does this.
    legs = []
    for i in range(len(STALL_XY)):
        legs.append((lane_point(i), mat_centre(i)))
        for j in range(len(STALL_XY)):
            if i != j:
                legs.append((lane_point(i), lane_point(j)))
        legs.append((lane_point(i), gate_point()))
    for a, b in legs:
        for k in range(41):
            t = k / 40.0
            p = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
            for i in range(len(STALL_XY)):
                counter = (STALL_XY[i], STALL_ROW_Y)
                if dist(p, counter) < MIN_COUNTER_CLEARANCE_UU + COUNTER_HALF_Y:
                    fail(f"a leg of the walk passes {dist(p, counter):.0f} uu from "
                         f"stall {i + 1}'s counter; the character would jam on it")

    # The board must be readable from the lane and out of the way of the walk.
    for i in range(len(STALL_XY)):
        if dist(LEDGER_XY, mat_centre(i)) < MIN_MAT_CLEARANCE_UU:
            fail(f"the board by the gate stands on stall {i + 1}'s mat")
    if not on_floor(LEDGER_XY):
        fail(f"the board by the gate is off the floor at {LEDGER_XY}")
    if not on_floor(PLAYER_START):
        fail(f"the PlayerStart is off the floor at {PLAYER_START}")

    log(f"geometry checked: {len(STALL_XY)} stalls, mats "
        f"{[tuple(int(v) for v in mat_centre(i)) for i in range(len(STALL_XY))]}, "
        f"lane {[tuple(int(v) for v in lane_point(i)) for i in range(len(STALL_XY))]}, "
        f"gate {tuple(int(v) for v in gate_point())}, every clearance solved from the "
        f"layout")


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
        # into a saved level on an earlier task, and paint that quietly blocks is
        # indistinguishable from a bug in the submission.
        comp.set_collision_profile_name("NoCollision")
        comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    actor.set_actor_scale3d(scale)
    return actor


def make_movable(component, label):
    component.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
    if component.get_editor_property("mobility") != unreal.ComponentMobility.MOVABLE:
        fail(f"{label} would not go MOVABLE; the fixture tears the yard down and "
             f"spawns fresh actors, and PIE logs a mobility error for a STATIC one, "
             f"which the functional test scores as a FAIL")


def main():
    env = probe()
    les, eas = env["les"], env["eas"]
    # BEFORE new_level: it saves an empty package immediately, so a script that raises
    # later leaves a plausible-looking map on disk that the automation run then reports
    # as "No automation tests".
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

    # A stripe down the lane the walk uses, so a person can see where the yard is
    # walked from and that the mats are all reached from the same side.
    lane_y = lane_point(0)[1]
    block(env, CUBE, unreal.Vector(mid_x, lane_y, 1.5),
          unreal.Vector(span_x / 100.0, 0.3, 0.03), "LaneStripe", M_STRIPE,
          collide=False)
    n = 0
    x = FLOOR_MIN[0] + STRIPE_EVERY
    while x < FLOOR_MAX[0]:
        block(env, CUBE, unreal.Vector(x, mid_y, 1.0),
              unreal.Vector(0.06, span_y / 100.0, 0.02), f"Stripe_{n:02d}", M_STRIPE,
              collide=False)
        n += 1
        x += STRIPE_EVERY
    log(f"yard {span_x:.0f}x{span_y:.0f} + {n} stripes + a lane stripe at "
        f"y={lane_y:.0f}")

    for idx, (goods, price, stock, cap) in enumerate(GOODS):
        label = f"MarketStall_{idx + 1}"
        stall = eas.spawn_actor_from_class(
            env["MarketStallActor"],
            unreal.Vector(STALL_XY[idx], STALL_ROW_Y, STALL_STAND_Z),
            unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
        if stall is None:
            fail(f"could not place {label}")
        stall.set_actor_label(label)
        stall.set_editor_property("goods_name", goods)
        stall.set_editor_property("price_coins", price)
        stall.set_editor_property("stock_count", stock)
        stall.set_editor_property("stock_capacity", cap)
        stall.set_editor_property("delivered_since_close", 0)
        make_movable(stall.get_editor_property("counter"), f"{label}.Counter")
        make_movable(stall.get_editor_property("mat"), f"{label}.Mat")
        make_movable(stall.get_editor_property("sign"), f"{label}.Sign")
        make_movable(stall.get_editor_property("mat_plate"), f"{label}.MatPlate")
    log(f"{len(GOODS)} stalls placed with DECOY numbers "
        f"{[(g[0], g[1], g[2], g[3]) for g in GOODS]}")

    ledger = eas.spawn_actor_from_class(
        env["MarketLedgerActor"],
        unreal.Vector(LEDGER_XY[0], LEDGER_XY[1], LEDGER_STAND_Z),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if ledger is None:
        fail("could not place the board by the gate")
    ledger.set_actor_label("MarketLedger")
    ledger.set_editor_property("starting_coins", DECOY_COINS)
    ledger.set_editor_property("carry_limit", DECOY_CARRY)
    make_movable(ledger.get_editor_property("post"), "MarketLedger.Post")
    make_movable(ledger.get_editor_property("coins_board"), "MarketLedger.CoinsBoard")

    start = eas.spawn_actor_from_class(
        unreal.PlayerStart,
        unreal.Vector(PLAYER_START[0], PLAYER_START[1], 100.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=90.0))
    if start is None:
        fail("could not place PlayerStart")
    start.set_actor_label("PlayerStart")

    block(env, CUBE, unreal.Vector(mid_x, FLOOR_MAX[1] - 30.0, 120.0),
          unreal.Vector(span_x / 100.0, 0.4, 2.4), "Backdrop", M_DARK)
    for idx, lx in enumerate((FLOOR_MIN[0] + 250.0, FLOOR_MAX[0] - 250.0)):
        block(env, CYL, unreal.Vector(lx, FLOOR_MAX[1] - 400.0, 300.0),
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
        env["MarketDayFunctionalTest"],
        unreal.Vector(FLOOR_MIN[0] + 300.0, FLOOR_MIN[1] + 300.0, 150.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if fixture is None:
        fail("could not place the functional test")
    fixture.set_actor_label("MarketDayFunctionalTest")

    world = unreal.EditorLevelLibrary.get_editor_world()
    if world.get_world_settings().get_editor_property("default_game_mode") is not None:
        fail("world settings already name a game mode; this level must inherit the "
             "project default so the play lane comes for free")
    log("world settings: no game mode named (inherits BP_ThirdPersonGameMode)")

    # ---- read back what was actually placed -------------------------------------
    placed_stalls = [a for a in eas.get_all_level_actors()
                     if a.actor_has_tag("MarketStall")]
    if len(placed_stalls) != len(GOODS):
        fail(f"{len(placed_stalls)} actor(s) tagged MarketStall, expected {len(GOODS)}")
    placed_ledgers = [a for a in eas.get_all_level_actors()
                      if a.actor_has_tag("MarketLedger")]
    if len(placed_ledgers) != 1:
        fail(f"{len(placed_ledgers)} actor(s) tagged MarketLedger, expected 1")

    seen = []
    for stall in placed_stalls:
        goods = str(stall.get_editor_property("goods_name"))
        seen.append(goods)
        for prop in ("price_coins", "stock_count", "stock_capacity",
                     "delivered_since_close"):
            if stall.get_editor_property(prop) is None:
                fail(f"{stall.get_actor_label()} does not expose {prop}")
        counter = stall.get_editor_property("counter")
        if counter.get_editor_property("mobility") != unreal.ComponentMobility.MOVABLE:
            fail(f"{stall.get_actor_label()} is not MOVABLE and the yard is rebuilt "
                 f"mid-run")
        mat = stall.get_editor_property("mat")
        extent = mat.get_scaled_box_extent()
        if abs(extent.x - MAT_HALF) > 1.0 or abs(extent.y - MAT_HALF) > 1.0:
            fail(f"{stall.get_actor_label()}'s mat measures {extent.x:.0f} x "
                 f"{extent.y:.0f} in half-extent, expected {MAT_HALF:.0f}; the "
                 f"fixture's lane clearances are solved from that number")
        # The capsule's centre sits 96 above the floor. A mat that does not reach it
        # would never overlap a walking character, and the whole task would be
        # unwinnable while looking perfectly fine in the editor.
        mat_world = mat.get_world_location()
        if mat_world.z - extent.z > 90.0 or mat_world.z + extent.z < 100.0:
            fail(f"{stall.get_actor_label()}'s mat spans z "
                 f"{mat_world.z - extent.z:.0f}..{mat_world.z + extent.z:.0f}; a "
                 f"walking capsule's centre is 96 above the floor and would miss it")
        try:
            if mat.get_collision_enabled() != unreal.CollisionEnabled.QUERY_ONLY:
                fail(f"{stall.get_actor_label()}'s mat is not query-only; it would "
                     f"shove the character instead of noticing them")
        except Exception:  # noqa: BLE001 - the getter is not on every build
            log("note: mat collision-enabled could not be read back on this build")
        origin, bounds = stall.get_actor_bounds(only_colliding_components=True)
        if origin.z - bounds.z < -1.0:
            fail(f"{stall.get_actor_label()} reaches down to "
                 f"z={origin.z - bounds.z:.1f}, below the floor")
    if len(set(seen)) != len(seen):
        fail(f"the placed stalls sell {seen}; two of them are indistinguishable")

    lit = [a for a in eas.get_all_level_actors()
           if a.get_class().get_name() in ("DirectionalLight", "SkyLight")]
    if len(lit) < 2:
        fail(f"level has {len(lit)} light actor(s); a capture still would be black")

    log(f"placed stalls read back {seen}, all MOVABLE, mats {2 * MAT_HALF:.0f} square "
        f"and tall enough to notice a walking capsule, all standing on the floor")

    if not les.save_current_level():
        fail("save_current_level() returned False")
    log(f"SAVED {MAP_PKG}")


main()

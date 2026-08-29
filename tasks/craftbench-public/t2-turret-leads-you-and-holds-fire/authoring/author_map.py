"""Authors L_TurretYard for t2-turret-leads-you-and-holds-fire.

    UnrealEditor-Cmd.exe <ThirdPerson.uproject> -run=pythonscript \
        -script="<abs path to this file>" -nullrhi -unattended -nopause \
        -log -stdout -FullStdOutLogOutput

TWO BOLTED-DOWN GUNS THAT THROW SLOW, HEAVY SHOTS AT A WALKING TARGET. The whole
task is that a shot is settled at the instant it leaves the barrel, so the gun has
to aim at where the character is GOING; and that four numbers on each turret -- shot
speed, reach, traverse rate, reload -- differ between the two and are RE-TUNED TWICE
by the fixture while the level is running.

The map therefore leaks no answer: its authored numbers are the fixture's phase-1
set on purpose (so that reading them once in BeginPlay is correct until the first
re-tune and wrong forever after), and every other number the grade depends on is
staged at runtime.

NOTHING HERE IS HAND-TUNED. The floor, the ruler rings and the landmarks are all
sized from the ROUTE, and the route is recomputed here with the same formulas the
fixture uses -- from the turret positions and the parameter sets. If the two do not
agree, or if any fairness invariant fails, this script raises BEFORE saving.

`new_level()` saves an empty package immediately, so a script that raises later
leaves a plausible-looking map on disk. Check the log for the SAVED line, never the
filesystem for the file.

This level names NO game mode: it inherits the project default, so the play lane
comes for free (see the 2026-08-17 unplayable-play-lane finding).

Every Rotator is built with KEYWORDS -- unreal.Rotator's positional order is
(roll, pitch, yaw).
"""
import math

import unreal

TASK = "t2-turret-leads-you-and-holds-fire"
MAP_PKG = f"/Game/Maps/{TASK}/L_TurretYard"

# Where the guns are bolted. Everything else in the yard is derived from these two
# points and from the parameter sets below.
TURRETS = ((0.0, 0.0), (4200.0, 0.0))

# The three sets of four numbers the fixture stages: shot speed, reach, traverse
# deg/s, reload s. PHASE 1 is (SET_L on turret 1, SET_S on turret 2) and is what the
# .umap is authored with; phase 2 swaps them; phase 3 is (SET_M, SET_S).
SET_L = (460.0, 4200.0, 40.0, 1.5)
SET_S = (1350.0, 1500.0, 130.0, 0.9)
SET_M = (750.0, 2600.0, 70.0, 1.2)
PHASES = ((SET_L, SET_S), (SET_S, SET_L), (SET_M, SET_S))

# Route factors -- MUST match TurretLeadFunctionalTest.cpp.
LANE_A_ALONG, LANE_A_SIDE = 0.62, 0.52     # x SET_L reach
LANE_B_ALONG, LANE_B_SIDE = 2.00, 0.55     # x SET_S reach
RADIAL_IN, RADIAL_OUT = 0.18, 0.90         # x SET_L reach
CHARGE_OFFSET, CHARGE_STOP = 0.030, 0.20   # x SET_L reach
LANE_E_ALONG, LANE_E_SIDE = 0.68, 0.55     # x SET_M reach
LEG_PHASE = (0, 0, 0, 0, 1, 1, 1, 2, 2)    # phase in force walking TO each stop

MIN_STANDOFF = 400.0       # a leg or a stop this close to a base would jam
BOUNDARY_FRAC = 0.08       # a stop this near a reach boundary could round either way
FLOOR_MARGIN = 900.0       # ground beyond the outermost stop
MUZZLE_Z = 320.0
STRIPE_EVERY = 400.0
RULER_RINGS = (1000.0, 2000.0, 3000.0, 4000.0)
RULER_DASHES = 20

CUBE = "/Engine/BasicShapes/Cube.Cube"
CYL = "/Engine/BasicShapes/Cylinder.Cylinder"
M_FLOOR = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray"
M_STRIPE = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02"
M_DARK = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"
M_GLOW = "/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT"
M_HAZARD = "/Game/Variant_Combat/Materials/M_Lava"


def log(msg):
    unreal.log(f"TURRETYARD- {msg}")


def fail(msg):
    unreal.log_error(f"TURRETYARD-ERROR {msg}")
    raise SystemExit(1)


# ---------------------------------------------------------------------------------
# The route, recomputed here exactly as the fixture computes it.
# ---------------------------------------------------------------------------------

def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1])


def _mul(a, k):
    return (a[0] * k, a[1] * k)


def _norm(a):
    m = math.hypot(a[0], a[1])
    if m < 1e-6:
        fail("degenerate direction while building the route")
    return (a[0] / m, a[1] / m)


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _rot(v, rad):
    c, s = math.cos(rad), math.sin(rad)
    return (v[0] * c - v[1] * s, v[0] * s + v[1] * c)


def build_route():
    a, b = TURRETS
    along = _norm(_sub(b, a))
    side = (-along[1], along[0])
    rl, rs, rm = SET_L[1], SET_S[1], SET_M[1]

    w0 = _sub(_sub(a, _mul(along, LANE_A_ALONG * rl)), _mul(side, LANE_A_SIDE * rl))
    w1 = _sub(_add(a, _mul(along, LANE_A_ALONG * rl)), _mul(side, LANE_A_SIDE * rl))
    w2 = _sub(_sub(b, _mul(along, LANE_B_ALONG * rs)), _mul(side, LANE_B_SIDE * rs))
    w3 = _sub(_add(b, _mul(along, LANE_B_ALONG * rs)), _mul(side, LANE_B_SIDE * rs))

    u = _norm(_sub(w3, b))
    w4 = _add(b, _mul(u, RADIAL_IN * rl))
    w5 = _add(b, _mul(u, RADIAL_OUT * rl))
    p_off = CHARGE_OFFSET * rl
    r_stop = CHARGE_STOP * rl
    r_start = RADIAL_OUT * rl
    delta = math.acos(p_off / r_start) - math.acos(p_off / r_stop)
    cands = (_add(b, _mul(_rot(u, delta), r_stop)),
             _add(b, _mul(_rot(u, -delta), r_stop)))
    # The charge stays on the same side of the turret axis as the rest of the route.
    w6 = min(cands, key=lambda c: _sub(c, b)[0] * side[0] + _sub(c, b)[1] * side[1])

    w7 = _sub(_add(a, _mul(along, LANE_E_ALONG * rm)), _mul(side, LANE_E_SIDE * rm))
    w8 = _sub(_sub(a, _mul(along, LANE_E_ALONG * rm)), _mul(side, LANE_E_SIDE * rm))
    return [w0, w1, w2, w3, w4, w5, w6, w7, w8]


def check_geometry(route):
    """What has to be true before this level is worth saving."""
    # No constant fits both turrets, in any phase.
    for pi, (s1, s2) in enumerate(PHASES):
        if abs(s1[0] - s2[0]) < 500.0:
            fail(f"phase {pi + 1}: the two shot speeds are only "
                 f"{abs(s1[0] - s2[0]):.0f} uu/s apart; one constant would fit both")
        if abs(s1[1] - s2[1]) < 1000.0:
            fail(f"phase {pi + 1}: the two reaches are only "
                 f"{abs(s1[1] - s2[1]):.0f} uu apart; one constant would fit both")

    # Every stop clear of both solid bases, and clear of every reach boundary in the
    # phase it is walked in on AND the phase it is walked out on (a re-tune happens
    # standing at a stop, so the stop is judged under both).
    for i, w in enumerate(route):
        for t, tp in enumerate(TURRETS):
            d = _dist(w, tp)
            if d < MIN_STANDOFF:
                fail(f"stop {i} is {d:.0f} uu from turret {t + 1}, which is solid")
            for ph in {LEG_PHASE[i], LEG_PHASE[min(i + 1, len(route) - 1)]}:
                frac = d / PHASES[ph][t][1]
                if abs(frac - 1.0) < BOUNDARY_FRAC:
                    fail(f"stop {i} sits {abs(frac - 1) * 100:.1f}% from turret "
                         f"{t + 1}'s reach in phase {ph + 1}; a correct answer could "
                         f"round either way there")

    # No leg walks through a base.
    for i in range(1, len(route)):
        for k in range(201):
            f = k / 200.0
            p = (route[i - 1][0] + (route[i][0] - route[i - 1][0]) * f,
                 route[i - 1][1] + (route[i][1] - route[i - 1][1]) * f)
            for t, tp in enumerate(TURRETS):
                if _dist(p, tp) < MIN_STANDOFF:
                    fail(f"the walk to stop {i} passes {_dist(p, tp):.0f} uu from "
                         f"turret {t + 1}'s base; the character would jam on it")

    # The charge leg has to actually be the charge leg: it must stop SHORT of its own
    # closest-approach point, or the across-sight component runs past the shot speed
    # and the interception the fixture demands would not exist.
    off = CHARGE_OFFSET * SET_L[1]
    if _dist(route[6], TURRETS[1]) <= off * 1.5:
        fail(f"the charge leg ends {_dist(route[6], TURRETS[1]):.0f} uu from turret 2 "
             f"with an offset of {off:.0f}; it has run past its closest approach and "
             f"no shot could catch the character there")
    log(f"geometry checked: {len(route)} stops, all clear of both bases by "
        f">= {MIN_STANDOFF:.0f} uu and of every reach boundary by "
        f">= {BOUNDARY_FRAC * 100:.0f}%")


def floor_bounds(route):
    xs = [w[0] for w in route] + [t[0] for t in TURRETS]
    ys = [w[1] for w in route] + [t[1] for t in TURRETS]
    return ((min(xs) - FLOOR_MARGIN, min(ys) - FLOOR_MARGIN),
            (max(xs) + FLOOR_MARGIN, max(ys) + FLOOR_MARGIN))


# ---------------------------------------------------------------------------------
# Placement
# ---------------------------------------------------------------------------------

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
    for cls_name in ("LeadTurretActor", "TurretShotActor",
                     "TurretLeadFunctionalTest"):
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
    """A RULER, not a reach. The reaches are re-tuned twice while the level runs, so
    a ring drawn at one of them would be a lie for two thirds of the run; these are
    fixed 10 m marks so a viewer can read any distance off the floor."""
    for k in range(RULER_DASHES):
        ang = 2.0 * math.pi * k / RULER_DASHES
        seg = 2.0 * math.pi * radius / RULER_DASHES * 0.35
        block(env, CUBE,
              unreal.Vector(centre[0] + math.cos(ang) * radius,
                            centre[1] + math.sin(ang) * radius, 2.0),
              unreal.Vector(0.10, seg / 100.0, 0.04),
              f"{label}_{k:02d}", material,
              yaw=math.degrees(ang) + 90.0, collide=False)


def main():
    env = probe()
    les, eas = env["les"], env["eas"]
    route = build_route()
    check_geometry(route)
    (fx0, fy0), (fx1, fy1) = floor_bounds(route)

    if unreal.EditorAssetLibrary.does_asset_exist(MAP_PKG):
        fail(f"{MAP_PKG} already exists. Delete the file from the SHELL and re-run.")
    if not les.new_level(MAP_PKG):
        fail(f"new_level({MAP_PKG}) returned False")
    log(f"created {MAP_PKG}")

    span_x, span_y = fx1 - fx0, fy1 - fy0
    mid_x, mid_y = (fx1 + fx0) / 2.0, (fy1 + fy0) / 2.0
    block(env, CUBE, unreal.Vector(mid_x, mid_y, -50.0),
          unreal.Vector(span_x / 100.0, span_y / 100.0, 1.0), "Floor", M_FLOOR)

    n = 0
    x = fx0 + STRIPE_EVERY
    while x < fx1:
        block(env, CUBE, unreal.Vector(x, mid_y, 1.5),
              unreal.Vector(0.06, span_y / 100.0, 0.03), f"Stripe_{n:02d}", M_STRIPE,
              collide=False)
        n += 1
        x += STRIPE_EVERY
    log(f"yard {span_x:.0f}x{span_y:.0f} + {n} stripes every {STRIPE_EVERY:.0f} cm")

    for idx, (tx, ty) in enumerate(TURRETS):
        turret = eas.spawn_actor_from_class(
            env["LeadTurretActor"], unreal.Vector(tx, ty, 0.0),
            unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
        if turret is None:
            fail(f"could not place turret {idx + 1}")
        turret.set_actor_label(f"LeadTurret_{idx + 1}")
        speed, reach, traverse, reload_s = PHASES[0][idx]
        turret.set_editor_property("shot_speed_uu", speed)
        turret.set_editor_property("engage_range_uu", reach)
        turret.set_editor_property("traverse_deg_per_sec", traverse)
        turret.set_editor_property("reload_seconds", reload_s)
        for ring in RULER_RINGS:
            paint_ring(env, (tx, ty), ring, f"Ruler{idx + 1}_{int(ring)}",
                       M_GLOW if idx else M_HAZARD)
    log(f"2 turrets bolted at {TURRETS}, authored with the PHASE 1 numbers "
        f"{PHASES[0]} (the fixture re-tunes them twice)")

    start = eas.spawn_actor_from_class(
        unreal.PlayerStart, unreal.Vector(route[0][0], route[0][1], 120.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if start is None:
        fail("could not place PlayerStart")
    start.set_actor_label("PlayerStart")

    block(env, CUBE, unreal.Vector(mid_x, fy1 - 30.0, 140.0),
          unreal.Vector(span_x / 100.0, 0.4, 2.8), "Backdrop", M_DARK)
    for idx, lx in enumerate((fx0 + 300.0, fx1 - 300.0)):
        block(env, CYL, unreal.Vector(lx, fy1 - 500.0, 400.0),
              unreal.Vector(1.2 + idx * 1.0, 1.2 + idx * 1.0, 8.0), f"Landmark_{idx}",
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
        env["TurretLeadFunctionalTest"],
        unreal.Vector(fx0 + 300.0, fy0 + 300.0, 150.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if fixture is None:
        fail("could not place the functional test")
    fixture.set_actor_label("TurretLeadFunctionalTest")

    # ---- read the placed level back, and refuse to save a level that lies --------
    world = unreal.EditorLevelLibrary.get_editor_world()
    if world.get_world_settings().get_editor_property("default_game_mode") is not None:
        fail("world settings already name a game mode; this level must inherit the "
             "project default so the play lane comes for free")
    log("world settings: no game mode named (inherits BP_ThirdPersonGameMode)")

    placed = [a for a in eas.get_all_level_actors() if a.actor_has_tag("LeadTurret")]
    if len(placed) != 2:
        fail(f"{len(placed)} actor(s) tagged LeadTurret, expected 2")
    placed.sort(key=lambda a: a.get_actor_location().x)
    for idx, turret in enumerate(placed):
        want = PHASES[0][idx]
        got = (float(turret.get_editor_property("shot_speed_uu")),
               float(turret.get_editor_property("engage_range_uu")),
               float(turret.get_editor_property("traverse_deg_per_sec")),
               float(turret.get_editor_property("reload_seconds")))
        if any(abs(g - w) > 0.01 for g, w in zip(got, want)):
            fail(f"turret {idx + 1} reads back {got} and the phase-1 set is {want}; "
                 f"the numbers did not survive placement")
        loc = turret.get_actor_location()
        if abs(loc.x - TURRETS[idx][0]) > 1.0 or abs(loc.y - TURRETS[idx][1]) > 1.0:
            fail(f"turret {idx + 1} landed at ({loc.x:.0f},{loc.y:.0f}) and the yard "
                 f"asked for {TURRETS[idx]}")
        for tag in ("TurretBase", "TurretBarrel", "TurretMuzzle"):
            if not turret.get_components_by_tag(unreal.SceneComponent, tag):
                fail(f"turret {idx + 1} has no component tagged {tag}; the fixture "
                     f"identifies the parts of the gun by tag and would refuse to run")
        muzzle = turret.get_components_by_tag(unreal.SceneComponent, "TurretMuzzle")[0]
        mz = muzzle.get_world_location().z
        if abs(mz - MUZZLE_Z) > 25.0:
            fail(f"turret {idx + 1}'s muzzle sits at z={mz:.0f} and the yard is built "
                 f"around {MUZZLE_Z:.0f}; a level shot would not pass over the "
                 f"character's head by the margin the task depends on")

    lit = [a for a in eas.get_all_level_actors()
           if a.get_class().get_name() in ("DirectionalLight", "SkyLight")]
    if len(lit) < 2:
        fail(f"level has {len(lit)} light actor(s); a capture still would be black")

    for i, w in enumerate(route):
        if not (fx0 + 200.0 < w[0] < fx1 - 200.0
                and fy0 + 200.0 < w[1] < fy1 - 200.0):
            fail(f"stop {i} at ({w[0]:.0f},{w[1]:.0f}) is off the floor "
                 f"({fx0:.0f}..{fx1:.0f} by {fy0:.0f}..{fy1:.0f})")
    log(f"all {len(route)} stops on the floor; route x "
        f"{min(w[0] for w in route):.0f}..{max(w[0] for w in route):.0f}, y "
        f"{min(w[1] for w in route):.0f}..{max(w[1] for w in route):.0f}")

    if not les.save_current_level():
        fail("save_current_level() returned False")
    log(f"SAVED {MAP_PKG}")


main()

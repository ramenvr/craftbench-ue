"""Authors L_LiftTower for t3-lift-serves-its-calls-in-order.

Run headless, from the repo root, with ABSOLUTE paths (a relative one reaches UE
verbatim and the boot dies with "Failed to open descriptor file"):

    REPO=$(pwd)
    MSYS_NO_PATHCONV=1 "$CB_UE_ROOT/Engine/Binaries/Win64/UnrealEditor-Cmd.exe" \\
      "$(cygpath -m "$REPO/UE-projects/ThirdPerson/ThirdPerson.uproject")" \\
      -ExecutePythonScript="$(cygpath -m "$REPO/tasks/craftbench-public/\\
t3-lift-serves-its-calls-in-order/authoring/author_map.py")" \\
      -nullrhi -unattended -nosplash -stdout -FullStdOutLogOutput

`-FullStdOutLogOutput` is not optional: without it the script runs and prints
NOTHING, which reads exactly like a crash. Every line is prefixed LIFTTOWER- and
the last on success is LIFTTOWER-DONE. A boot that ends without that marker
FAILED, whatever its exit code says.

WHAT THIS LEVEL IS. A three-landing tower beside a clear vertical shaft, with one
lift car parked level with landing 1. The whole point of the task is that WHERE
THE FLOORS ARE is not knowable from the level: the verifier re-stages landing 2
before anybody's BeginPlay and moves it again half way through the run. So the
floor-2 height committed here is a DECOY, and this script REFUSES TO SAVE unless
that decoy is far enough from the height the verifier stages that a lift which
read the level instead of asking the landing is measurably wrong.

NOTHING IS HAND-TUNED. The landing X, the sill gap, the deck sizes and the
parapet positions are all solved from the scaffold's own component scales, read
back off the spawned actors -- so a change to the car or the landing geometry
moves this level with it instead of silently opening a hole the character can
fall through.

THE TOWER IS CLOSED. As shipped on 2026-08-19 it was not: the tower face and the
shaft wall were NoCollision decoration and there was no roof at all, so somebody
standing on the top landing could jump its 120 uu parapet and fall 18 m out
through the back. There is now a blocking TowerFace and a blocking TowerRoof, both
solved from the walls they join, and the refuse-to-save block AUDITS every block's
real collision -- because the failure the owner suspected (a roof that exists and
silently does not block) is one nothing here would have caught. What is still open
is recorded in notes.md; do not read the audit as a claim that the play space is
sealed on every axis.

This level names NO game mode: it inherits the project default, so both halves of
Enhanced Input survive and the tower can be walked around by hand
(the 2026-08-17 unplayable-play-lane finding).

Every Rotator is built with KEYWORDS -- unreal.Rotator's positional order is
(roll, pitch, yaw).
"""
import unreal

TASK = "t3-lift-serves-its-calls-in-order"
MAP_PKG = f"/Game/Maps/{TASK}/L_LiftTower"

# --- the only numbers this script chooses --------------------------------------
# The gap between the car floor and the landing deck. Wide enough to read as a
# lift, far narrower than the character's 42 uu capsule radius, so he bridges it
# walking in and out and can never fall down it.
SILL_GAP = 15.0

# The three committed sills. Landing 2's is the DECOY -- the verifier stages it to
# ~69% of the shaft before BeginPlay and to 25% between the legs.
SILL_1 = 0.0
SILL_2_DECOY = 600.0
SILL_3 = 1800.0

# What the verifier will stage landing 2 to, as fractions of the shaft. Mirrored
# here ONLY so this script can refuse to ship a decoy that is not a decoy.
STAGED_FRACTION_A = 0.6944
STAGED_FRACTION_B = 0.25
MIN_DECOY_ERROR = 400.0

# The car's three numbers, painted on it and readable at run time.
TRAVEL_SPEED = 200.0
DOOR_TRAVEL = 2.0
DOOR_HOLD = 3.0

GROUND_TOP = -20.0
RULER_EVERY = 300.0

# --- the tower's lid ---------------------------------------------------------------
# THE TOWER USED TO BE OPEN AT THE TOP. Nothing above landing 3 blocked anything, and
# the tower face and the shaft wall were both NoCollision decoration -- so a character
# standing on the top landing could jump its 120 uu parapet (a 127.6 uu apex clears it)
# and fall the whole 18 m out the back. Owner play-test, 2026-08-19: "LiftTower's top
# does not have collider so add that."
#
# ROOF_HEADROOM is the clear height the lid leaves above the TOP SILL and it is the one
# number here that is chosen rather than solved. What it has to clear, smallest first:
#   a standing character's head (capsule 42 x 96)   SILL_3 + 192
#   the car's own roof parked at landing 3          SILL_3 + 260
#   a JUMPING character's head -- JumpZVelocity 500
#   against the default -980 gravity is a 127.6 uu
#   apex (ThirdPersonCharacter.cpp:18 and :31)      SILL_3 + 320  ( = JUMP_HEAD_UU )
# and, the binding one, the camera plan: `landing-three-sign` looks from
# (-1150, -600, 2150) and its sight line crosses the tower's Y edge at z = 2122, so a
# lid at the walls' old height of SILL_3 + 300 would have cut that shot in half.
# 400 clears the jumping head by 80 uu and blocks none of the six poses.
ROOF_HEADROOM = 400.0
ROOF_THICKNESS = 20.0

# The character's reach above whatever he is standing on, mirrored here ONLY so the
# refuse-to-save block can prove the lid is above it. An OVER-estimate can only make the
# tower roomier and can never trap anybody, so this is the one duplicated number in this
# script whose two copies cannot desync into a defect.
JUMP_HEAD_UU = 320.0

CUBE = "/Engine/BasicShapes/Cube.Cube"
CYL = "/Engine/BasicShapes/Cylinder.Cylinder"
M_FLOOR = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray"
M_STRIPE = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02"
M_DARK = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"
M_GLOW = "/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT"


def log(msg):
    unreal.log(f"LIFTTOWER- {msg}")


def fail(msg):
    unreal.log_error(f"LIFTTOWER-ERROR {msg}")
    raise SystemExit(1)


def probe():
    """Resolve everything before authoring. Refuses rather than half-builds: a
    wrong API name in UE python does not raise where you can see it, it returns
    None and the script sails on to save a broken level."""
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
    for cls_name in ("LiftCarActor", "LiftLandingActor", "LiftTowerFunctionalTest"):
        if not hasattr(unreal, cls_name):
            fail(f"class {cls_name} is not exposed to python - is the module built?")
        got[cls_name] = getattr(unreal, cls_name)
    log(f"probe OK: {sorted(got)}")
    return got


def block(env, mesh, loc, scale, label, material=None, collide=True, cast_shadow=True):
    """A static-mesh box/cylinder placed as a plain StaticMeshActor.

    Every block records itself on env, so the refuse-to-save audit at the bottom can
    prove that each one really does block -- or really does not block -- what it was
    built to."""
    actor = env["eas"].spawn_actor_from_class(
        unreal.StaticMeshActor, loc, unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if actor is None:
        fail(f"could not spawn {label}")
    actor.set_actor_label(label)
    comp = actor.static_mesh_component
    comp.set_static_mesh(unreal.EditorAssetLibrary.load_asset(mesh))
    comp.set_editor_property("mobility", unreal.ComponentMobility.STATIC)
    actor.set_actor_scale3d(scale)
    if material is not None:
        comp.set_material(0, unreal.EditorAssetLibrary.load_asset(material))
    if collide:
        # SAY IT, do not inherit it. AStaticMeshActor's constructor sets the BlockAll
        # profile and then turns bUseDefaultCollision back ON (StaticMeshActor.cpp:33-36),
        # so what a placed block actually blocks comes from the MESH ASSET rather than
        # from anything this script did -- which is exactly the "it looks solid and is
        # not" failure the owner suspected of the roof. Setting the profile explicitly
        # clears that flag (UStaticMeshComponent::SetCollisionProfileName,
        # StaticMeshComponent.cpp:2618-2622) and turns the audit below into a real check
        # rather than a tautology.
        comp.set_collision_profile_name("BlockAll")
    else:
        comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    if not cast_shadow:
        comp.set_cast_shadow(False)
    env.setdefault("blocks", []).append((label, actor, comp, collide))
    return actor


def box_half(component):
    """Half-extents of a scaffold cube component, in uu. The scaffold builds every
    solid out of the 100 uu engine cube, so the scale IS the size and this is a
    measurement rather than a guess."""
    s = component.get_editor_property("relative_scale3d")
    return (s.x * 50.0, s.y * 50.0, s.z * 50.0)


def main():
    env = probe()
    les, eas = env["les"], env["eas"]

    # new_level() refuses to overwrite, and deleting the package in-session does
    # NOT help because of this repo's TOMBSTONE LAW (once a package is deleted in
    # an editor session the registry never tells the truth about that path again
    # in that boot; the delete reports success and the following new_level still
    # returns False).
    if unreal.EditorAssetLibrary.does_asset_exist(MAP_PKG):
        fail(f"{MAP_PKG} already exists. Delete the file from the SHELL and re-run "
             f"in a fresh boot:  rm UE-projects/ThirdPerson/Content/Maps/{TASK}/"
             f"L_LiftTower.umap")
    if not les.new_level(MAP_PKG):
        fail(f"new_level({MAP_PKG}) returned False")
    log(f"created {MAP_PKG}")

    # ------------------------------------------------------------------ measure
    # Spawn the car and one landing at the origin first and READ their geometry,
    # so every distance below is solved rather than typed.
    car = eas.spawn_actor_from_class(env["LiftCarActor"], unreal.Vector(0.0, 0.0, 0.0),
                                     unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if car is None:
        fail("could not place the lift car")
    car.set_actor_label("LiftCar")

    platform = car.get_editor_property("platform")
    if platform is None:
        fail("the car has no Platform component")
    car_half_x, car_half_y, car_half_z = box_half(platform)
    car_sill_offset = car_half_z          # platform centred on the actor origin

    landings = []
    for floor in (1, 2, 3):
        a = eas.spawn_actor_from_class(env["LiftLandingActor"],
                                       unreal.Vector(0.0, 0.0, 0.0),
                                       unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
        if a is None:
            fail(f"could not place landing {floor}")
        a.set_actor_label(f"Landing{floor}")
        a.set_editor_property("floor_number", floor)
        landings.append(a)

    deck = landings[0].get_editor_property("deck")
    if deck is None:
        fail("a landing has no Deck component")
    deck_half_x, deck_half_y, deck_half_z = box_half(deck)
    deck_sill_offset = deck_half_z

    # The deck's near edge sits SILL_GAP away from the car floor's edge; the deck
    # centre follows from its own depth.
    landing_x = -(car_half_x + SILL_GAP + deck_half_x)
    log(f"measured: car floor {car_half_x * 2:.0f} x {car_half_y * 2:.0f}, deck "
        f"{deck_half_x * 2:.0f} x {deck_half_y * 2:.0f}; landings solved to "
        f"x={landing_x:.0f} for a {SILL_GAP:.0f} uu sill gap")

    car.set_actor_location(unreal.Vector(0.0, 0.0, SILL_1 - car_sill_offset),
                           False, False)
    car.set_editor_property("travel_speed_uu_per_second", TRAVEL_SPEED)
    car.set_editor_property("door_travel_seconds", DOOR_TRAVEL)
    car.set_editor_property("door_hold_seconds", DOOR_HOLD)

    sills = (SILL_1, SILL_2_DECOY, SILL_3)
    for a, sill in zip(landings, sills):
        a.set_actor_location(
            unreal.Vector(landing_x, 0.0, sill - deck_sill_offset), False, False)

    # ------------------------------------------------------------------- scenery
    ground_span_x = abs(landing_x) + deck_half_x + car_half_x + 900.0
    ground_span_y = max(deck_half_y, car_half_y) * 2.0 + 900.0
    block(env, CUBE,
          unreal.Vector((landing_x - deck_half_x + car_half_x) * 0.5, 0.0,
                        GROUND_TOP - 10.0),
          unreal.Vector(ground_span_x / 100.0, ground_span_y / 100.0, 0.2),
          "Ground", M_FLOOR)

    # The tower behind the landings, and the shaft wall behind the car. Both now reach
    # the underside of the lid, so the tower is closed rather than open-topped.
    tower_top_z = SILL_3 + ROOF_HEADROOM
    tower_face_x = landing_x - deck_half_x - 10.0
    # TOWER FACE: BLOCKING. It is the tower's back wall and it stands immediately behind
    # each landing's far parapet -- its near face is flush with the deck's far edge, so
    # there is no ledge to land on and no gap to drop down. Blocking it is what closes
    # the jump-over-the-parapet fall: a 127.6 uu jump apex clears a 120 uu rail, and
    # before this the character who cleared it fell 18 m straight through a decorative
    # wall. Collision changes nothing about rendering, so no camera pose moves; and it
    # sits 1425 uu from the shaft, so the "a blocking wall beside a moving platform is a
    # way to jam the character" hazard that keeps ShaftBack open does not reach it.
    block(env, CUBE, unreal.Vector(tower_face_x, 0.0, tower_top_z * 0.5),
          unreal.Vector(0.2, (deck_half_y * 2.0 + 80.0) / 100.0,
                        tower_top_z / 100.0),
          "TowerFace", M_DARK)
    shaft_back_x = car_half_x + 60.0
    # SHAFT WALL: STILL NoCollision, DELIBERATELY. It stands 60 uu behind the car floor's
    # edge with the car sliding past it all run, and a blocking wall alongside a moving
    # platform is a way to jam the rider. Closing the back of the car properly means
    # bringing this wall flush with the car floor (410 -> 360), which is a level-layout
    # change plus a re-check of the tower-wide / shaft-ride framing -- costed in notes.md
    # as a separate decision rather than smuggled in here.
    block(env, CUBE, unreal.Vector(shaft_back_x, 0.0, tower_top_z * 0.5),
          unreal.Vector(0.2, (car_half_y * 2.0 + 160.0) / 100.0,
                        tower_top_z / 100.0),
          "ShaftBack", M_DARK, collide=False)

    # THE LID. Solved from the two walls it sits on: it spans from the outer face of the
    # tower wall to the outer face of the shaft wall, and it is as wide as the wider of
    # them, so there is no seam at any corner to slip through. cast_shadow is off because
    # this is a play-space boundary and not set dressing -- a shadow-casting slab
    # overhead would darken every still of the tower interior, and a task that grades
    # clean while being invisible is the exact failure this level's lighting rig exists
    # to avoid.
    roof_x_lo = tower_face_x - 10.0
    roof_x_hi = shaft_back_x + 10.0
    roof_half_y = max(deck_half_y + 40.0, car_half_y + 80.0)
    block(env, CUBE,
          unreal.Vector((roof_x_lo + roof_x_hi) * 0.5, 0.0,
                        tower_top_z + ROOF_THICKNESS * 0.5),
          unreal.Vector((roof_x_hi - roof_x_lo) / 100.0, roof_half_y * 2.0 / 100.0,
                        ROOF_THICKNESS / 100.0),
          "TowerRoof", M_DARK, cast_shadow=False)
    log(f"tower closed: walls to z={tower_top_z:.0f}, lid "
        f"{roof_x_hi - roof_x_lo:.0f} x {roof_half_y * 2.0:.0f} with its underside "
        f"{ROOF_HEADROOM:.0f} uu above the top sill")

    # A ruler up the shaft wall every 300 uu. Deliberately NOT floor markings: the
    # floor heights are staged at run time, so painting them here would be the one
    # thing in the level that lies.
    ticks = 0
    z = RULER_EVERY
    while z <= tower_top_z:
        block(env, CUBE, unreal.Vector(shaft_back_x - 12.0, 0.0, z),
              unreal.Vector(0.05, (car_half_y * 2.0 + 120.0) / 100.0, 0.08),
              f"ShaftTick_{int(z)}", M_STRIPE, collide=False)
        ticks += 1
        z += RULER_EVERY
    log(f"tower face, shaft wall and {ticks} shaft ticks every {RULER_EVERY:.0f} uu")

    # Two landmark pylons of different sizes on the ground, so a moving camera is
    # distinguishable from a still one.
    for i, ly in enumerate((-deck_half_y - 320.0, deck_half_y + 320.0)):
        block(env, CYL, unreal.Vector(landing_x + 200.0, ly, 220.0 + i * 120.0),
              unreal.Vector(1.2 + i * 0.8, 1.2 + i * 0.8, 4.4 + i * 2.4),
              f"Landmark_{i}", M_GLOW if i else M_DARK, collide=False)

    # --------------------------------------------------------- the player + fixture
    # On landing 1, off the call pad, facing the shaft.
    call_pad = landings[0].get_editor_property("call_pad")
    if call_pad is None:
        fail("a landing has no CallPad component")
    start = eas.spawn_actor_from_class(
        unreal.PlayerStart,
        unreal.Vector(landing_x - 150.0, -80.0, SILL_1 + 100.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if start is None:
        fail("could not place PlayerStart")
    start.set_actor_label("PlayerStart")

    ft = eas.spawn_actor_from_class(
        env["LiftTowerFunctionalTest"],
        unreal.Vector(landing_x, -deck_half_y - 500.0, 200.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if ft is None:
        fail("could not place LiftTowerFunctionalTest")
    ft.set_actor_label("LiftTowerFunctionalTest")

    # ------------------------------------------------------------------- lighting
    # new_level() gives a COMPLETELY EMPTY level. On the pad map this shipped five
    # byte-identical BLACK stills against a reference that PASSED and held a valid
    # certificate -- a task that grades clean and is invisible to a reviewer is the
    # exact failure this set exists to avoid.
    sun = eas.spawn_actor_from_class(
        unreal.DirectionalLight, unreal.Vector(0.0, 0.0, SILL_3 + 600.0),
        unreal.Rotator(roll=0.0, pitch=-48.0, yaw=-130.0))
    sky = eas.spawn_actor_from_class(
        unreal.SkyLight, unreal.Vector(0.0, 0.0, SILL_3 + 600.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    atmo = eas.spawn_actor_from_class(
        unreal.SkyAtmosphere, unreal.Vector(0.0, 0.0, 0.0),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    if sun is None or sky is None or atmo is None:
        fail("could not place the lighting rig")
    sun.set_actor_label("DirectionalLight")
    sky.set_actor_label("SkyLight")
    atmo.set_actor_label("SkyAtmosphere")
    log("lighting: DirectionalLight + SkyLight + SkyAtmosphere")

    # =========================================================================
    # REFUSE TO SAVE unless every invariant the fixture depends on holds.
    # =========================================================================
    world = unreal.EditorLevelLibrary.get_editor_world()
    if world.get_world_settings().get_editor_property("default_game_mode") is not None:
        fail("world settings name a game mode; this level must inherit the project "
             "default or both halves of Enhanced Input are dropped and the tower "
             "cannot be walked around by hand")
    log("world settings: no game mode named (inherits BP_ThirdPersonGameMode)")

    all_actors = eas.get_all_level_actors()
    cars = [a for a in all_actors if a.actor_has_tag("LiftCar")]
    decks = [a for a in all_actors if a.actor_has_tag("LiftLanding")]
    if len(cars) != 1:
        fail(f"{len(cars)} actor(s) tagged LiftCar, expected exactly one")
    if len(decks) != 3:
        fail(f"{len(decks)} actor(s) tagged LiftLanding, expected exactly three")

    floors = sorted(int(a.get_editor_property("floor_number")) for a in decks)
    if floors != [1, 2, 3]:
        fail(f"the landings call themselves {floors}; the tower needs 1, 2 and 3")

    def sill_of(a):
        comp = a.get_editor_property("deck") if a.actor_has_tag("LiftLanding") \
            else a.get_editor_property("platform")
        return a.get_actor_location().z + box_half(comp)[2]

    by_floor = {int(a.get_editor_property("floor_number")): a for a in decks}
    got_sills = [sill_of(by_floor[f]) for f in (1, 2, 3)]
    if not (got_sills[0] < got_sills[1] < got_sills[2]):
        fail(f"the landing sills are {got_sills}; they must go up in floor order")
    shaft = got_sills[2] - got_sills[0]
    if shaft < 1200.0:
        fail(f"a {shaft:.0f} uu shaft is too short for the verifier to measure a "
             f"travel speed in")

    # THE DECOY MUST BE A DECOY. If the committed floor-2 sill were close to the
    # height the verifier stages, a lift that read the level at authoring time
    # would be right by accident and one of the task's two hardest gates would
    # measure nothing.
    staged_a = got_sills[0] + shaft * STAGED_FRACTION_A
    staged_b = got_sills[0] + shaft * STAGED_FRACTION_B
    if abs(got_sills[1] - staged_a) < MIN_DECOY_ERROR:
        fail(f"the committed floor-2 sill {got_sills[1]:.0f} is only "
             f"{abs(got_sills[1] - staged_a):.0f} uu from the height the verifier "
             f"stages ({staged_a:.0f}); it is supposed to be a decoy")
    if abs(staged_a - staged_b) < 400.0:
        fail(f"the two staged floor-2 heights ({staged_a:.0f}, {staged_b:.0f}) are "
             f"only {abs(staged_a - staged_b):.0f} uu apart; a lift that cached the "
             f"height once would barely notice the move")
    mid = (got_sills[0] + got_sills[2]) * 0.5
    for label, value in (("committed", got_sills[1]), ("staged A", staged_a),
                         ("staged B", staged_b)):
        if abs(value - mid) < 100.0:
            fail(f"the {label} floor-2 sill {value:.0f} sits within 100 uu of halfway "
                 f"({mid:.0f}); an evenly spaced shaft lets a lift guess the heights")
    log(f"floor sills committed {['%.0f' % s for s in got_sills]}; verifier will "
        f"stage floor 2 to {staged_a:.0f} then {staged_b:.0f}")

    # The car must start parked level with landing 1, in the shaft, unrotated.
    car_sill = sill_of(cars[0])
    if abs(car_sill - got_sills[0]) > 1.0:
        fail(f"the car sill is {car_sill:.0f} and landing 1 is at {got_sills[0]:.0f}; "
             f"the car must start parked level with the bottom landing")
    loc = cars[0].get_actor_location()
    if abs(loc.x) > 1.0 or abs(loc.y) > 1.0:
        fail(f"the car is at ({loc.x:.0f}, {loc.y:.0f}); the shaft is at (0, 0)")
    for a in [cars[0]] + decks:
        r = a.get_actor_rotation()
        if abs(r.roll) > 0.5 or abs(r.pitch) > 0.5 or abs(r.yaw) > 0.5:
            fail(f"{a.get_actor_label()} is rotated {r}; the fixture's pad footprints "
                 f"and local waypoints assume an axis-aligned tower")

    # The sill gap has to be crossable and not fall-through-able.
    gap = (loc.x - car_half_x) - (landing_x + deck_half_x)
    if not (8.0 <= gap <= 40.0):
        fail(f"the gap between the car floor and the landing deck is {gap:.0f} uu; "
             f"under 8 it reads as no gap at all and over 40 the character's 42 uu "
             f"capsule could drop into the shaft")

    # The landings must share one XY, or the car cannot serve all three.
    for a in decks:
        p = a.get_actor_location()
        if abs(p.x - landing_x) > 1.0 or abs(p.y) > 1.0:
            fail(f"{a.get_actor_label()} is at ({p.x:.0f}, {p.y:.0f}) and the other "
                 f"landings are at ({landing_x:.0f}, 0); they share one shaft")

    # The car floor and the landing decks are re-staged at run time and carry the
    # rider; a Static component there is a PIE error, not a warning.
    if platform.get_editor_property("mobility") != unreal.ComponentMobility.MOVABLE:
        fail("the car's Platform is not MOVABLE, so it cannot carry a rider")
    for a in decks:
        if a.get_editor_property("deck").get_editor_property("mobility") \
                != unreal.ComponentMobility.MOVABLE:
            fail(f"{a.get_actor_label()}'s Deck is not MOVABLE and the verifier moves it")

    # EVERY PAD SITS ON THE SURFACE IT BELONGS TO.
    # A CHILD OF A SCALED ROOT INHERITS THAT SCALE. Platform is (7, 7, 0.2) and Deck is
    # (7, 8, 0.2) off the 100 uu engine cube, and UE multiplies BOTH a child's relative
    # offset and its box extent by that -- UBoxComponent::CalcBounds transforms the
    # extent by the full LocalToWorld. So a pad written at a relative 150 uu stands
    # 1050 uu out and a 120 uu box measures 840, unless the scaffold divides that scale
    # back out. Adding the relative numbers to the actor's location, which this script
    # used to do for the call pad, reads 7x and 8x short of where the pad really is.
    #
    # This is the fault the level shipped with on 2026-08-19: the call pad stood at
    # (335, -1760), 1360 uu past the edge of its own 800 uu deck and in mid air, while
    # the in-car pads spread to 840 x 840 -- so the fixture's walk crossed a pad it was
    # not aimed at and it refused to grade the run. Nothing here caught it, and the
    # fixture's own footprint check has a LOWER bound only, which is how an 840 uu pad
    # sailed through. Solve each pad the way UE composes transforms, and check it.
    def pad_world_box(owner, root, pad):
        """A pad's world XY centre and half-extents, composed the way UE does."""
        root_scale = root.get_editor_property("relative_scale3d")
        rel_loc = pad.get_editor_property("relative_location")
        pad_scale = pad.get_editor_property("relative_scale3d")
        extent = pad.get_editor_property("box_extent")
        origin = owner.get_actor_location()
        return (origin.x + rel_loc.x * root_scale.x,
                origin.y + rel_loc.y * root_scale.y,
                abs(extent.x * root_scale.x * pad_scale.x),
                abs(extent.y * root_scale.y * pad_scale.y))

    surfaces = [("landing 1's call pad", landings[0], deck, call_pad,
                 landing_x, 0.0, deck_half_x, deck_half_y)]
    for floor in (1, 2, 3):
        in_car = cars[0].get_editor_property(f"pad{floor}")
        if in_car is None:
            fail(f"the car has no Pad{floor} component")
        surfaces.append((f"the car's pad {floor}", cars[0], platform, in_car,
                         loc.x, loc.y, car_half_x, car_half_y))
    pad_world_x = pad_world_y = 0.0
    for label, owner, root, pad, surf_x, surf_y, surf_half_x, surf_half_y in surfaces:
        cx, cy, half_x, half_y = pad_world_box(owner, root, pad)
        if label.startswith("landing 1"):
            pad_world_x, pad_world_y = cx, cy
        # A ceiling as well as a floor. 110 uu of half-extent is already wider than the
        # 80 uu of clearance the fixture's in-car walks are routed with.
        if not (55.0 <= half_x <= 110.0 and 55.0 <= half_y <= 110.0):
            fail(f"{label} measures {half_x * 2:.0f} x {half_y * 2:.0f} uu; a pad has to "
                 f"be big enough to stand on and narrow enough to walk past. Check that "
                 f"the scaffold divides the root's scale out of the box extent")
        if (abs(cx - surf_x) + half_x > surf_half_x
                or abs(cy - surf_y) + half_y > surf_half_y):
            fail(f"{label} is centred at ({cx:.0f}, {cy:.0f}) with a "
                 f"{half_x * 2:.0f} x {half_y * 2:.0f} uu footprint, which hangs off the "
                 f"surface it belongs to (centred ({surf_x:.0f}, {surf_y:.0f}), "
                 f"{surf_half_x * 2:.0f} x {surf_half_y * 2:.0f}). Nobody can step on a "
                 f"pad that is not on the floor")
    log(f"pads solved on their surfaces; landing call pad at "
        f"({pad_world_x:.0f}, {pad_world_y:.0f})")

    # The player must start ON landing 1 and OFF its call pad.
    sp = start.get_actor_location()
    if abs(sp.z - (got_sills[0] + 100.0)) > 5.0:
        fail(f"the PlayerStart is at z={sp.z:.0f} and landing 1's floor is at "
             f"{got_sills[0]:.0f}")
    if abs(sp.x - pad_world_x) < 150.0 and abs(sp.y - pad_world_y) < 150.0:
        fail("the PlayerStart is on landing 1's call pad; the run would open with a "
             "press nobody made")
    if abs(sp.x - landing_x) > deck_half_x - 60.0 or abs(sp.y) > deck_half_y - 60.0:
        fail(f"the PlayerStart at ({sp.x:.0f}, {sp.y:.0f}) is not comfortably on "
             f"landing 1's deck")

    # The car's three numbers are what the fixture derives every deadline from.
    for prop, want in (("travel_speed_uu_per_second", TRAVEL_SPEED),
                       ("door_travel_seconds", DOOR_TRAVEL),
                       ("door_hold_seconds", DOOR_HOLD)):
        got = float(cars[0].get_editor_property(prop))
        if abs(got - want) > 1e-3:
            fail(f"the car reads {prop}={got} and the tower is built for {want}")
    log(f"car numbers: {TRAVEL_SPEED:.0f} uu/s, doors {DOOR_TRAVEL:.1f} s, hold "
        f"{DOOR_HOLD:.1f} s")

    lit = [a for a in all_actors
           if a.get_class().get_name() in ("DirectionalLight", "SkyLight")]
    if len(lit) < 2:
        fail(f"level has {len(lit)} light actor(s); a capture still would be black "
             f"and the task would grade clean while being invisible")

    # EVERY SOLID BLOCKS WHAT IT LOOKS LIKE IT BLOCKS, AND EVERY BACKDROP BLOCKS
    # NOTHING. The owner's 2026-08-19 play-test found the tower open at the top, and the
    # first hypothesis was that a roof existed and silently failed to block. It did not
    # exist -- but NOTHING HERE WOULD HAVE CAUGHT IT IF IT HAD, and nothing here checked
    # that a `collide=True` block survived its mesh asset's own default profile. Both
    # getters are BlueprintPure on UPrimitiveComponent (PrimitiveComponent.h:2618 and
    # :2634) so python can read them; a wrong name returns None rather than raising,
    # which is why the None arm is explicit rather than assumed away.
    built = env.get("blocks", [])
    if not built:
        fail("no blocks were recorded; the collision audit is measuring nothing")
    for label, actor, comp, wants_solid in built:
        enabled = comp.get_collision_enabled()
        pawn = comp.get_collision_response_to_channel(unreal.CollisionChannel.ECC_PAWN)
        if enabled is None or pawn is None:
            fail(f"could not read {label}'s collision back off its component; the getter "
                 f"names are wrong and this audit proves nothing")
        if wants_solid:
            if enabled == unreal.CollisionEnabled.NO_COLLISION:
                fail(f"{label} is built as a solid and its collision is disabled")
            if pawn != unreal.CollisionResponseType.ECR_BLOCK:
                fail(f"{label} is built as a solid but it answers {pawn} to the Pawn "
                     f"channel -- the character would walk straight through it")
        elif enabled != unreal.CollisionEnabled.NO_COLLISION:
            fail(f"{label} is built as a backdrop and still has collision ({enabled}); "
                 f"scenery beside a moving platform is a way to jam the rider")
    solids = sorted(lbl for lbl, _a, _c, k in built if k)
    log(f"collision audit: {len(built)} blocks, solid = {solids}")

    # THE TOWER IS CLOSED AT THE TOP. Read back off the actors' own world bounds -- so
    # this measures the composed transform (scale x the 100 uu cube) and not the numbers
    # that were fed in, which is the only version of this check that can catch the
    # scale-composition mistake this task has already been bitten by twice.
    by_label = {lbl: a for lbl, a, _c, _k in built}
    for needed in ("TowerRoof", "TowerFace", "ShaftBack", "Ground"):
        if needed not in by_label:
            fail(f"the level has no {needed}")

    def world_box(actor):
        origin, extent = actor.get_actor_bounds(False)
        return (origin.x - extent.x, origin.x + extent.x,
                origin.y - extent.y, origin.y + extent.y,
                origin.z - extent.z, origin.z + extent.z)

    rx0, rx1, ry0, ry1, rz0, _rz1 = world_box(by_label["TowerRoof"])
    fx0, _fx1, fy0, fy1, _fz0, ftop = world_box(by_label["TowerFace"])
    _sx0, sx1, sy0, sy1, _sz0, stop = world_box(by_label["ShaftBack"])
    # 5 uu of slack on the seam checks, because a bound is the MESH's bound scaled, and
    # the two things being compared are scaled by wildly different factors (the lid by
    # 15, the walls by 0.2). Every hole this is guarding against is tens of uu wide, so
    # the slack cannot make it vacuous.
    kSeamUu = 5.0

    if rz0 < got_sills[2] + JUMP_HEAD_UU:
        fail(f"the lid's underside is at {rz0:.0f} and the top sill is at "
             f"{got_sills[2]:.0f}; a character standing there reaches "
             f"{got_sills[2] + JUMP_HEAD_UU:.0f} at the top of a jump and would be "
             f"pinned against his own ceiling")
    if rx0 > fx0 + kSeamUu or rx1 < sx1 - kSeamUu:
        fail(f"the lid spans x {rx0:.0f}..{rx1:.0f} and the tower it has to cover runs "
             f"{fx0:.0f}..{sx1:.0f}; a lid with an open end is not a lid")
    if ry0 > min(fy0, sy0) + kSeamUu or ry1 < max(fy1, sy1) - kSeamUu:
        fail(f"the lid spans y {ry0:.0f}..{ry1:.0f} and the walls it sits on run "
             f"{min(fy0, sy0):.0f}..{max(fy1, sy1):.0f}; the corners are open")
    if ftop < rz0 - kSeamUu or stop < rz0 - kSeamUu:
        fail(f"the tower walls stop at {min(ftop, stop):.0f} and the lid's underside is "
             f"at {rz0:.0f}; that gap is a way out of the top of the tower")
    log(f"tower sealed: lid underside {rz0:.0f} over a top sill of {got_sills[2]:.0f} "
        f"({rz0 - got_sills[2]:.0f} uu of headroom), footprint x {rx0:.0f}..{rx1:.0f} "
        f"y {ry0:.0f}..{ry1:.0f}, walls up to {min(ftop, stop):.0f}")

    fixtures = [a for a in all_actors
                if a.get_class().get_name() == "LiftTowerFunctionalTest"]
    if len(fixtures) != 1:
        fail(f"{len(fixtures)} functional test actor(s) placed, expected exactly one")

    if not les.save_current_level():
        fail("save_current_level() returned False")
    log(f"SAVED {MAP_PKG}")
    unreal.log("LIFTTOWER-DONE")


main()

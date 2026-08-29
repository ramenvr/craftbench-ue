"""Author Content/Maps/t2-crate-you-carry-changes-what-you-can-do/L_HaulYard.umap.

Run headless, from the repo root, with ABSOLUTE paths (a relative one reaches UE
verbatim and the boot dies with "Failed to open descriptor file"):

    REPO=$(pwd)
    MSYS_NO_PATHCONV=1 "$CB_UE_ROOT/Engine/Binaries/Win64/UnrealEditor-Cmd.exe" \
      "$(cygpath -m "$REPO/UE-projects/ThirdPerson/ThirdPerson.uproject")" \
      -ExecutePythonScript="$(cygpath -m "$REPO/tasks/craftbench-public/t2-crate-you-carry-changes-what-you-can-do/authoring/author_map.py")" \
      -nullrhi -unattended -nosplash -stdout -FullStdOutLogOutput

`-FullStdOutLogOutput` is not optional: without it the script runs and prints
NOTHING, which reads exactly like a crash.

Every line is prefixed HAULYARD- and the last on success is HAULYARD-DONE. A boot
that ends without that marker FAILED, whatever its exit code says.

A capability probe runs first because a wrong API name in UE python does not raise
where you can see it -- it returns None and the script sails on to save a broken
level.

THIS LEVEL NAMES NO GAME MODE. It does not need to: the haul character is PLACED
and set to be possessed by player 0, so hitting Play possesses it while the
project's own BP_ThirdPersonGameMode (and therefore BP_ThirdPersonPlayerController,
which is the only class carrying IMC_Default) stays in force. Naming a game mode
here would replace GlobalDefaultGameMode and quietly take the keyboard lane with
it -- a level that grades byte-identically and cannot be walked around by hand.

EVERY DIMENSION BELOW IS SOLVED FROM THE RULES THE FIXTURE GRADES, not tuned by
hand, and the script REFUSES TO SAVE if any of those solutions does not hold.
"""
import unreal

TASK = "t2-crate-you-carry-changes-what-you-can-do"
MAP_PKG = f"/Game/Maps/{TASK}/L_HaulYard"

# --- the rules the yard has to satisfy (all disclosed in the task prompt) -----
HOLD_CM = 330.0          # where a carried crate rides, mid-band (290-380)
PICKUP_CM = 250.0        # a crate this close to your middle is picked up
CRATE_CM = 80.0          # the crate is an 80 cm cube
CAPSULE_R = 42.0         # AThirdPersonCharacter::InitCapsuleSize(42, 96)
CAPSULE_H = 96.0
ARRIVE_TOL = 25.0        # the drive's arrival tolerance at a plate centre
AT_CRATE_CM = 240.0      # the drive stops this far short of a crate it is fetching
BRAKE_CM = 62.0          # 500 uu/s against BrakingDecelerationWalking 2000

# --- the staged yard, all in centimetres, floor top surface at Z = 0 ---------
FLOOR_MIN = unreal.Vector2D(-3800.0, -4600.0)
FLOOR_MAX = unreal.Vector2D(6000.0, 3400.0)
FLOOR_T = 20.0
STRIPE_EVERY = 400.0
STRIPE_W = 14.0

HERO_AT = unreal.Vector(-2800.0, -1200.0, CAPSULE_H)
LANE_LEN = 2600.0

ROW_Y = 2000.0
CRATE_X = (-2000.0, -800.0, 400.0)
CRATE_MASS = (18.0, 42.0, 70.0)   # the fixture re-prices these; these are the paint

PLATE_X = 2400.0
PLATE_Y = (-1200.0, 1200.0)
PLATE_HOLD = (30.0, 55.0)
PAD_HALF = 450.0                  # the pad is 900 x 900 -- the class default, checked below

DOOR_X = 5200.0
DOOR_PANEL_HALF_X = 20.0

# The wall the crate has to stop against. Its depth along the push axis is SOLVED:
# a carry that teleports puts the crate HOLD - CAPSULE_R deep, so the block has to
# be deeper than that plus the crate itself or the gate could never see the fault.
WALL_MID = unreal.Vector2D(-1200.0, -3600.0)
WALL_HALF_X = 200.0
WALL_HALF_Y = 400.0
WALL_H = 500.0

POSTS = ((-3400.0, 3000.0, 1.0), (5600.0, 3000.0, 1.8))

CUBE = "/Engine/BasicShapes/Cube.Cube"
CYL = "/Engine/BasicShapes/Cylinder.Cylinder"
MAT_FLOOR = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray"
MAT_STRIPE = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"
MAT_WALL = "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02"


def log(msg):
    unreal.log(f"HAULYARD- {msg}")


def fail(msg):
    unreal.log_error(f"HAULYARD-ERROR {msg}")
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
    for path in (CUBE, CYL, MAT_FLOOR, MAT_STRIPE, MAT_WALL):
        if not unreal.EditorAssetLibrary.does_asset_exist(path):
            fail(f"asset missing: {path}")
    for cls_name in ("HaulCrateActor", "WeightPlateActor", "LiftDoorActor",
                     "HaulHeroCharacter", "HaulCarryFunctionalTest"):
        if not hasattr(unreal, cls_name):
            fail(f"class {cls_name} is not exposed to python - is the module built?")
        got[cls_name] = getattr(unreal, cls_name)
    if not hasattr(unreal, "AutoReceiveInput"):
        fail("unreal.AutoReceiveInput is missing, so the placed character cannot be "
             "told to be possessed by player 0 and the level would be unplayable")
    log(f"probe OK: {sorted(k for k in got)}")
    return got


def solve_and_check_geometry():
    """The yard's dimensions are consequences, not choices. Refuse if any fails."""
    problems = []

    # 1. A crate set down at the plate centre has to land WHOLLY on the pad. The
    #    character stops within ARRIVE_TOL of the centre and the crate rides
    #    HOLD in front of it.
    reach = HOLD_CM + ARRIVE_TOL + CRATE_CM / 2.0
    if reach > PAD_HALF:
        problems.append(f"a crate set down at the plate centre reaches {reach:.0f} cm "
                        f"from it, past the pad's own {PAD_HALF:.0f} cm half-width")

    # 2. ...and the character fetching that crate back has to end up OFF the pad,
    #    or picking it up would immediately count as setting it down again.
    stand = (HOLD_CM - ARRIVE_TOL) + (AT_CRATE_CM - BRAKE_CM)
    if stand <= PAD_HALF:
        problems.append(f"the character fetching a crate back off a plate ends "
                        f"{stand:.0f} cm from the plate centre, still on a pad that "
                        f"reaches {PAD_HALF:.0f} cm")

    # 3. The wall has to be able to CONTAIN a teleported crate, or the no-clipping
    #    gate could never tell a teleport from a sweep.
    deep = HOLD_CM - CAPSULE_R + CRATE_CM / 2.0
    if 2.0 * WALL_HALF_Y <= deep:
        problems.append(f"the wall is {2.0 * WALL_HALF_Y:.0f} cm deep but a carry that "
                        f"teleports would put the crate {deep:.0f} cm into it, so the "
                        f"crate would come out the far side and the gate would see "
                        f"nothing")
    if WALL_H <= HOLD_CM:
        problems.append("the wall is shorter than the height a crate rides at")

    # 4. Row crates have to be far enough apart that "the nearest one" is never a
    #    coin toss from where the drive stands.
    for i in range(len(CRATE_X) - 1):
        gap = CRATE_X[i + 1] - CRATE_X[i]
        if gap <= 2.0 * PICKUP_CM:
            problems.append(f"crates {i} and {i+1} are {gap:.0f} cm apart, inside twice "
                            f"the {PICKUP_CM:.0f} cm reach")

    # 5. A carried crate must never reach a door, or the sweep that keeps it solid
    #    would stop it against the door and the ride band would fail correct work.
    east_corridor = PLATE_X + PAD_HALF * 10.0 / 3.0
    crate_tip = east_corridor + HOLD_CM + CRATE_CM / 2.0
    if crate_tip + 200.0 > DOOR_X - DOOR_PANEL_HALF_X:
        problems.append(f"a crate carried up the east corridor reaches x={crate_tip:.0f} "
                        f"and the door slab starts at x={DOOR_X - DOOR_PANEL_HALF_X:.0f}")

    # 6. The measured lane and every plate must be clear of the wall by more than
    #    the distance at which the ride band is suspended.
    lane_to_wall = abs(HERO_AT.y - (WALL_MID.y + WALL_HALF_Y))
    if lane_to_wall <= 600.0:
        problems.append(f"the measured lane runs {lane_to_wall:.0f} cm from the wall, "
                        f"inside the 600 cm where the ride band is not judged")
    for py in PLATE_Y:
        d = abs(py - (WALL_MID.y + WALL_HALF_Y))
        if d <= 600.0 + PAD_HALF:
            problems.append(f"the plate at y={py:.0f} is {d:.0f} cm from the wall")

    # 7. Both plates have to be far enough apart that a crate on one is never over
    #    the other, and that the drive's corridors fit between them.
    plate_gap = abs(PLATE_Y[1] - PLATE_Y[0])
    if plate_gap <= 2.0 * PAD_HALF + 2.0 * (HOLD_CM + CRATE_CM / 2.0):
        problems.append(f"the plates are only {plate_gap:.0f} cm apart")

    # 8. Everything has to stand on the floor.
    for x, y, label in ((HERO_AT.x, HERO_AT.y, "the character"),
                        (CRATE_X[0], ROW_Y, "the west crate"),
                        (CRATE_X[-1], ROW_Y, "the east crate"),
                        (DOOR_X, PLATE_Y[0], "the low door"),
                        (WALL_MID.x, WALL_MID.y - WALL_HALF_Y, "the wall")):
        if not (FLOOR_MIN.x + 200.0 <= x <= FLOOR_MAX.x - 200.0
                and FLOOR_MIN.y + 200.0 <= y <= FLOOR_MAX.y - 200.0):
            problems.append(f"{label} at ({x:.0f}, {y:.0f}) is off the floor")

    if problems:
        fail("the yard's dimensions do not satisfy the rules it is graded by: "
             + "; ".join(problems))
    log(f"geometry solved: crate lands {reach:.0f} cm out on a {PAD_HALF:.0f} cm pad, "
        f"fetcher stands {stand:.0f} cm out, a teleported crate would sit {deep:.0f} cm "
        f"into an {2.0 * WALL_HALF_Y:.0f} cm wall")


def block(env, mesh, loc, scale, label, material=None, tags=None):
    """A static-mesh box/cylinder placed as a plain StaticMeshActor."""
    actor = env["eas"].spawn_actor_from_class(
        unreal.StaticMeshActor, loc, unreal.Rotator(0, 0, 0))
    if actor is None:
        fail(f"could not spawn {label}")
    actor.set_actor_label(label)
    comp = actor.static_mesh_component
    comp.set_static_mesh(unreal.EditorAssetLibrary.load_asset(mesh))
    comp.set_editor_property("mobility", unreal.ComponentMobility.STATIC)
    if material is not None:
        comp.set_material(0, unreal.EditorAssetLibrary.load_asset(material))
    actor.set_actor_scale3d(scale)
    if tags:
        actor.tags = [unreal.Name(t) for t in tags]
    return actor


def main():
    env = probe()
    solve_and_check_geometry()
    les, eas = env["les"], env["eas"]

    # new_level() refuses to overwrite, and deleting the package in-session does
    # NOT help because of this repo's TOMBSTONE LAW (once a package is deleted in
    # an editor session the registry never tells the truth about that path again in
    # that boot; the delete reports success and the following new_level still
    # returns False).
    if unreal.EditorAssetLibrary.does_asset_exist(MAP_PKG):
        fail(f"{MAP_PKG} already exists. Delete the file from the SHELL and re-run in "
             f"a fresh boot:  rm UE-projects/ThirdPerson/Content/Maps/{TASK}/L_HaulYard.umap")
    if not les.new_level(MAP_PKG):
        fail(f"new_level({MAP_PKG}) returned False")
    log(f"created {MAP_PKG}")

    # ---- the ground ---------------------------------------------------------
    span_x = FLOOR_MAX.x - FLOOR_MIN.x
    span_y = FLOOR_MAX.y - FLOOR_MIN.y
    mid_x = (FLOOR_MAX.x + FLOOR_MIN.x) / 2.0
    mid_y = (FLOOR_MAX.y + FLOOR_MIN.y) / 2.0
    block(env, CUBE, unreal.Vector(mid_x, mid_y, -FLOOR_T / 2.0),
          unreal.Vector(span_x / 100.0, span_y / 100.0, FLOOR_T / 100.0),
          "Floor", MAT_FLOOR)

    # Stripes 3 cm proud so they catch the sun and throw a thin shadow; flush
    # stripes read as nothing in a still (measured on the pad map).
    n = 0
    x = FLOOR_MIN.x + STRIPE_EVERY
    while x < FLOOR_MAX.x:
        block(env, CUBE, unreal.Vector(x, mid_y, 1.5),
              unreal.Vector(STRIPE_W / 100.0, span_y / 100.0, 0.03),
              f"Stripe_{int(x)}", MAT_STRIPE)
        n += 1
        x += STRIPE_EVERY
    log(f"floor {span_x:.0f} x {span_y:.0f} + {n} stripes")

    # ---- the three crates ---------------------------------------------------
    for i, (cx, mass) in enumerate(zip(CRATE_X, CRATE_MASS)):
        crate = eas.spawn_actor_from_class(
            env["HaulCrateActor"],
            unreal.Vector(cx, ROW_Y, CRATE_CM / 2.0), unreal.Rotator(0, 0, 0))
        if crate is None:
            fail(f"could not place crate {i}")
        crate.set_actor_label(f"Crate_{i}")
        crate.set_editor_property("MassKg", mass)
    log(f"three crates in a row at y={ROW_Y:.0f}, {CRATE_MASS} kg as painted")

    # ---- two plates, two doors, each plate wired to its OWN door -------------
    plates = []
    for i, (py, hold) in enumerate(zip(PLATE_Y, PLATE_HOLD)):
        door = eas.spawn_actor_from_class(
            env["LiftDoorActor"], unreal.Vector(DOOR_X, py, 0.0),
            unreal.Rotator(0, 0, 0))
        plate = eas.spawn_actor_from_class(
            env["WeightPlateActor"], unreal.Vector(PLATE_X, py, 0.0),
            unreal.Rotator(0, 0, 0))
        if door is None or plate is None:
            fail(f"could not place plate/door pair {i}")
        door.set_actor_label(f"Door_{i}")
        plate.set_actor_label(f"Plate_{i}")
        plate.set_editor_property("MinimumHoldKg", hold)
        # The fixture READS this rather than assuming an ordering, which is what
        # lets it catch a plate that drives the other pair's door.
        plate.set_editor_property("LinkedDoor", door)
        # The pad's size is a GRADED quantity -- it is what "resting on the pad"
        # means, and both margins in solve_and_check_geometry() are written against
        # it. It is deliberately left at the class default rather than overridden
        # per instance, because a per-instance scale that silently failed to
        # serialise would move both margins without changing a line of this file.
        # It is checked against the placed actor's real bounds below instead.
        plates.append((plate, door))
    log(f"two plate/door pairs, pads {2.0 * PAD_HALF:.0f} cm square, "
        f"holds from {PLATE_HOLD} kg, each LinkedDoor set to its own door")

    # ---- the wall the crate has to stop against -----------------------------
    block(env, CUBE,
          unreal.Vector(WALL_MID.x, WALL_MID.y, WALL_H / 2.0),
          unreal.Vector(2.0 * WALL_HALF_X / 100.0, 2.0 * WALL_HALF_Y / 100.0,
                        WALL_H / 100.0),
          "YardWall", MAT_WALL, tags=["YardBlocker"])
    log(f"wall {2.0 * WALL_HALF_X:.0f} x {2.0 * WALL_HALF_Y:.0f} x {WALL_H:.0f} at "
        f"({WALL_MID.x:.0f}, {WALL_MID.y:.0f})")

    # ---- the character, PLACED and possessed by player 0 --------------------
    hero = eas.spawn_actor_from_class(env["HaulHeroCharacter"], HERO_AT,
                                      unreal.Rotator(0.0, 0.0, 0.0))
    if hero is None:
        fail("could not place HaulHeroCharacter")
    hero.set_actor_label("HaulHero")
    hero.set_editor_property("auto_possess_player", unreal.AutoReceiveInput.PLAYER0)

    start = eas.spawn_actor_from_class(
        unreal.PlayerStart, unreal.Vector(HERO_AT.x - 300.0, HERO_AT.y, 100.0),
        unreal.Rotator(0.0, 0.0, 0.0))
    if start is None:
        fail("could not place PlayerStart")
    start.set_actor_label("PlayerStart")

    for i, (px, py, s) in enumerate(POSTS):
        block(env, CYL, unreal.Vector(px, py, 300.0 * s),
              unreal.Vector(1.0 + i, 1.0 + i, 6.0 * s), f"Landmark_{i}", MAT_WALL)

    # ---- lighting -----------------------------------------------------------
    # new_level() gives a COMPLETELY EMPTY level. On the pad map this shipped five
    # byte-identical black stills against a reference that PASSED and held a valid
    # certificate: a task that grades clean and is invisible to a reviewer is the
    # exact failure this set exists to avoid.
    sun = eas.spawn_actor_from_class(unreal.DirectionalLight,
                                     unreal.Vector(0.0, 0.0, 1600.0),
                                     unreal.Rotator(-46.0, -35.0, 0.0))
    sky = eas.spawn_actor_from_class(unreal.SkyLight,
                                     unreal.Vector(0.0, 0.0, 1800.0),
                                     unreal.Rotator(0, 0, 0))
    atmo = eas.spawn_actor_from_class(unreal.SkyAtmosphere, unreal.Vector(0, 0, 0),
                                      unreal.Rotator(0, 0, 0))
    if sun is None or sky is None or atmo is None:
        fail("could not place the lighting rig")
    sun.set_actor_label("Sun")
    sky.set_actor_label("SkyLight")
    atmo.set_actor_label("SkyAtmosphere")

    ft = eas.spawn_actor_from_class(env["HaulCarryFunctionalTest"],
                                    unreal.Vector(-3400.0, -3000.0, 100.0),
                                    unreal.Rotator(0, 0, 0))
    if ft is None:
        fail("could not place HaulCarryFunctionalTest")
    ft.set_actor_label("HaulCarryFunctionalTest")

    # ---- REFUSALS: everything the fixture depends on, checked on the LEVEL ---
    actors = eas.get_all_level_actors()

    def tagged(tag):
        return [a for a in actors if unreal.Name(tag) in list(a.tags)]

    counts = {t: len(tagged(t)) for t in
              ("HaulCrate", "WeightPlate", "LiftDoor", "YardBlocker", "HaulHero")}
    want = {"HaulCrate": 3, "WeightPlate": 2, "LiftDoor": 2, "YardBlocker": 1,
            "HaulHero": 1}
    if counts != want:
        fail(f"the yard is not staged as the fixture resolves it: {counts} != {want}")

    # The pad the margins above were solved against has to be the pad that is
    # actually there.
    for plate, _door in plates:
        origin, extent = plate.get_actor_bounds(only_colliding_components=True)
        got_half = min(extent.x, extent.y)
        if abs(got_half - PAD_HALF) > 5.0:
            fail(f"the placed pad is {2.0 * got_half:.0f} cm square, not the "
                 f"{2.0 * PAD_HALF:.0f} cm every margin in this script was solved "
                 f"against; change PAD_HALF here and the pad's class default together")

    seen_doors = []
    for plate, door in plates:
        linked = plate.get_editor_property("LinkedDoor")
        if linked is None:
            fail("a plate has no LinkedDoor, so 'its own door' could not be read")
        if linked in seen_doors:
            fail("two plates are wired to the same door, so 'its own door' could not "
                 "be told from 'a door'")
        seen_doors.append(linked)

    # No game mode. Naming one here would replace GlobalDefaultGameMode and take
    # both halves of Enhanced Input with it.
    world = unreal.EditorLevelLibrary.get_editor_world()
    settings = world.get_world_settings()
    named = settings.get_editor_property("default_game_mode")
    if named is not None:
        fail(f"world settings name a game mode ({named}); this level must name none, "
             f"or it loses BP_ThirdPersonPlayerController and its IMC_Default and "
             f"becomes impossible to walk around by hand")

    # Refuse to save a level nobody can DRIVE. AThirdPersonCharacter declares
    # MoveAction/LookAction/MouseLookAction/JumpAction and assigns none of them, so
    # a native subclass binds nothing at all; and a placed pawn that nothing
    # possesses leaves the player with the project's default character somewhere
    # else entirely. No fixture can catch either (they all drive the pawn through
    # AddMovementInput), which is how a map ships authored, lit, graded and
    # completely uncontrollable. See the 2026-08-17 unplayable-play-lane finding.
    if hero.get_editor_property("auto_possess_player") != unreal.AutoReceiveInput.PLAYER0:
        fail("the placed character is not set to be possessed by player 0")
    unbound = []
    for prop in ("move_action", "look_action", "mouse_look_action", "jump_action"):
        try:
            if not hero.get_editor_property(prop):
                unbound.append(prop)
        except Exception:
            unbound.append(prop)
    if unbound:
        fail(f"the character has nothing bound to {', '.join(unbound)}; the level "
             f"would grade identically and be impossible to walk around")
    log("play lane OK: the placed HaulHero is possessed by player 0 and all four "
        "input actions are bound")

    lit = [a for a in actors
           if a.get_class().get_name() in ("DirectionalLight", "SkyLight")]
    if len(lit) < 2:
        fail(f"level has {len(lit)} light actor(s); a --capture still would be black "
             f"and the task would grade clean while being invisible")
    log(f"lighting check: {len(lit)} light actors present")

    if not les.save_current_level():
        fail("save_current_level() returned False")
    log(f"saved {MAP_PKG}")
    unreal.log("HAULYARD-DONE")


main()

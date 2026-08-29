# Authoring provenance for Content/Maps/gp-double-jump-stamina/L_DoubleJump.umap
# (the committed binary is the ONLY map source; this script is the one-shot
# recipe that produced it - NOT a runner fallback. Re-run only to re-author.)
#
# Shape copied from tasks/cpp/gp-heal-over-time-cpp/aids/
# author_L_HealOverTime.py, which is itself the proven
# tasks/cpp/tp0-sanity-log-on-beginplay/aids/author_L_TpSanity.py
# recipe on this substrate. Only the map path and the fixture class differ.
#
# PREREQUISITE: ThirdPersonEditor must be BUILT first, or
# /Script/CraftBenchTests.DoubleJumpStaminaFunctionalTest does not exist yet
# and load_class returns None.
#
# Run against the ThirdPerson substrate with a REAL off-screen RHI (map
# authoring crashes under -nullrhi - EditorActorSubsystem.spawn_actor_from_class
# asserts without a renderer):
#   UnrealEditor-Cmd.exe <repo>/UE-projects/ThirdPerson/ThirdPerson.uproject \
#     -ExecutePythonScript=<this file> -unattended -nopause -nosplash -RenderOffScreen
#
# WHY ONLY ONE PLACED ACTOR: this task is pawn-shaped. The fixture derives
# ACraftBenchPawnFunctionalTest, which RESOLVES the agent's pawn class, then
# spawns and possesses it itself - so the map must not place a pawn, exactly as
# L_PoisonStack, L_GlideStamina, L_HealthOps and L_HealOverTime do not.
#
# ===========================================================================
# THE FLOOR IS NOT COSMETIC ON THIS TASK. READ THIS BEFORE RE-AUTHORING.
# ===========================================================================
# Every other task in this family is movement-independent, and their aids
# scripts say the Template_Default floor "matters only so a human reviewing the
# film strip sees the mannequin stand rather than fall out of the world". THAT
# SENTENCE IS FALSE HERE. This fixture sets PawnSpawnLocation to z=1200 and the
# whole task is about a FALL, so the floor is inside the graded window.
#
# Is Template_Default's floor a PROBLEM at z=1200? NO - but only barely, and for
# the opposite reason to the one you would guess. ALL NUMBERS BELOW ARE
# PROPOSED - NOT YET MEASURED (hand-traced, never run):
#
#   * AT SPAWN: no problem at all. Template_Default's floor sits at z ~ 0 and
#     the pawn spawns 1200 cm above it, so there is no spawn-penetration risk
#     and no "spawned inside geometry" failure. Free-fall from 1200 gives
#     vZ ~ -686 cm/s at the t=0.7 trigger, comfortably past DJ-2a's
#     MinFallSpeed floor of 100. If anything the drop is generous.
#
#   * AT LANDING: the pawn DOES reach the floor before the run ends, and that is
#     the part that is easy to miss. With the reference's +600 cm/s impulse the
#     apex is z ~ 1144 at t ~ 1.31 and touchdown is at t ~ 2.78 - between cp7
#     (2.7) and cp8 (3.0). With a MINIMALLY-CONFORMING gentle impulse (~200 cm/s,
#     the smallest that clears the fixture's RiseEpsilon of 20 cm) the apex is
#     lower and touchdown is at t ~ 2.25, i.e. BEFORE the Leg-2 trigger at 2.4.
#     So depending on the submission, Leg 2 is either an air leg or a ground leg.
#
#   * WHY THAT IS STILL SOUND: DJ-4 fails on the PRESENCE of a rise beginning in
#     Leg 2. A landing is not a rise - UE's walking-mode floor adjustment lifts
#     the capsule by at most MAX_FLOOR_DIST (~2.4 cm), and CharacterMovement
#     moves SWEPT so there is no deep-penetration pop-up. That is ~8x under
#     RiseEpsilon = 20 cm. And an UNGATED ability triggered at 5 Power still
#     rises whether it jumps from the air or from the ground, so DJ-4 keeps its
#     teeth either way. The ground case only ever makes DJ-4 more lenient, which
#     is the direction PIN.md D3 already accepts.
#
#   * WHAT WOULD BREAK IT (record this before touching a bar): lowering
#     RiseEpsilon below ~5 cm would let the landing's own floor adjustment
#     register as a Leg-2 rise and FALSE-FAIL conforming work at DJ-4. The
#     fixture header's re-pinning hazard note discusses apex jitter only, so this
#     second constraint lives here. Raising the spawn height instead of lowering
#     the floor is the safe direction if more air time is ever needed.
#
#   * DO NOT "FIX" THIS BY DELETING THE FLOOR. A floorless map would let the pawn
#     fall past WorldSettings' KillZ and be destroyed mid-run, which surfaces as
#     "pawn did not spawn/resolve" at a late checkpoint - a harness-shaped FAIL on
#     a conforming submission. The floor is the thing that bounds the fall.
#
#   * VERIFY ON THE FIRST AUTHORING RUN: that Template_Default's floor actually
#     spans the origin in XY (the fixture spawns at x=0, y=0, so a floor that
#     does not cover the origin means the pawn misses it entirely). This has NOT
#     been checked - it is asserted from the sibling aids scripts, not measured.
#     The [DOUBLEJUMP-FINAL] DescribeSegments() output on the first reference run
#     is where the whole trajectory, landing included, becomes readable.
# ===========================================================================
import unreal

MAP_PACKAGE_PATH = "/Game/Maps/gp-double-jump-stamina"
MAP_NAME = "L_DoubleJump"
MAP_OBJECT_PATH = f"{MAP_PACKAGE_PATH}/{MAP_NAME}"
FIXTURE_CLASS_PATH = "/Script/CraftBenchTests.DoubleJumpStaminaFunctionalTest"
FIXTURE_CLASS_NAME = "DoubleJumpStaminaFunctionalTest"

les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

if unreal.EditorAssetLibrary.does_asset_exist(MAP_OBJECT_PATH):
    unreal.log(f"[doublejump] map exists at {MAP_OBJECT_PATH}; re-authoring over it")
    les.load_level(MAP_OBJECT_PATH)
else:
    # Template_Default ships a WorldSettings (raw new_level does not) AND the
    # floor the fall lands on - see the floor block above; both matter here.
    if not les.new_level_from_template(MAP_OBJECT_PATH,
                                       "/Engine/Maps/Templates/Template_Default"):
        raise RuntimeError("new_level_from_template failed")

fixture_cls = unreal.load_class(None, FIXTURE_CLASS_PATH)
if fixture_cls is None:
    raise RuntimeError(
        f"{FIXTURE_CLASS_PATH} not found - build ThirdPersonEditor first")

# Idempotence: clear any prior instance before placing a fresh one.
for actor in list(eas.get_all_level_actors()):
    if actor.get_class().get_name() == FIXTURE_CLASS_NAME:
        eas.destroy_actor(actor)

# The fixture actor's own placement is irrelevant to the grade - it spawns the
# graded pawn at its own PawnSpawnLocation (0, 0, 1200), not relative to itself.
# 120 cm matches every sibling map so the film strips stay comparable.
fixture = eas.spawn_actor_from_class(fixture_cls, unreal.Vector(0.0, 0.0, 120.0))
if fixture is None:
    raise RuntimeError("fixture spawn failed")

# NO GameModeOverride on purpose. PIE will also spawn the substrate's default
# BP_ThirdPersonGameMode pawn at the PlayerStart; it is not an
# ACraftBenchCharacter subclass, so it can never win pawn resolution and no gate
# reads it - the graded pawn is exclusively the one the fixture spawns. Same
# invariant L_PoisonStack, L_GlideStamina, L_HealthOps and L_HealOverTime rely
# on (see any of those task.md's Hidden invariants).

if not les.save_current_level():
    raise RuntimeError("save_current_level failed")
unreal.log(f"[doublejump] authored + saved {MAP_OBJECT_PATH} (fixture={fixture.get_name()})")

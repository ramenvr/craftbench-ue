// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT `no-mesh/` -- ONE DELTA from ../../reference (this file
// only; DoubleJumpPawn.h is byte-identical to the reference). AXIS: a
// behaviourally PERFECT solve on a pawn nobody can see. Defends PIN.md section 3
// AG-8 ("a meshless pawn, conforming but invisible on the film strip").
// EXPECTED: FAIL at DJ-7, CHECKPOINT 0 -- before any other gate exists.
// STATUS: UNVALIDATED / NOT YET RUN (no build, no PIE run, no grade).
//
// THE DELTA, in full: the guarded
// `ConstructorHelpers::FObjectFinder<USkeletalMesh>` on
// `/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple` and the placement that
// follows it are REMOVED. The pawn still constructs its skeletal mesh COMPONENT
// (ACharacter always does) -- it simply has no mesh ASSET assigned, which is
// exactly what DJ-7 tests: `GetSkeletalMeshAsset() != nullptr`, not "is there a
// mesh component".
//
// EVERYTHING ELSE IS THE REFERENCE. The ability is granted, tagged, gated,
// one-shot-debited and impulse-correct; Power inits to 100. This submission
// would pass DJ-1, DJ-2a, DJ-2b, DJ-2c, DJ-3a, DJ-3b, DJ-3c and DJ-4 in full.
// That is the whole point of the row: the owner's 2026-08-06 visibility decision
// exists because a conforming solve can be invisible, and a reviewer watching the
// film strip of an invisible run has nothing to review.
//
// ISOLATION CAVEAT -- THIS ROW SHARES ITS SUBSTRING WITH `empty`. Declared here
// and in MATRIX.md rather than hidden. DJ-7 is the FIRST gate this fixture runs
// (checkpoint 0), and with no overlay `ResolveAgentPawnClass` finds no concrete
// native ACraftBenchCharacter subclass (ACraftBenchBareCharacter is
// UCLASS(Abstract) and ACraftBenchCharacter itself is excluded from the candidate
// list) and no Blueprint subclass under /Game/Tasks, so it falls back to
// ACraftBenchCharacter::StaticClass() -- a pawn whose constructor
// (CraftBenchCharacter.cpp) never assigns a mesh. The empty leg therefore trips
// DJ-7 INCIDENTALLY, on the way past. This row is not a duplicate: it is a
// submission correct on every other axis whose only fault is invisibility, which
// is the only way to prove DJ-7 discriminates on the visibility axis alone. The
// two are separated by the RUN, not by the string. Same shape, same reasoning
// and the same declaration as gp-glide-stamina-cpp's MATRIX
// (`empty` / `no-mesh` collide there for the identical structural reason) and as
// gp-health-attribute-ops-cpp's.
//
// EXPECTED NAMED FAIL (the DJ-7 format string in
// DoubleJumpStaminaFunctionalTest.cpp carries NO placeholders at all, so the
// whole message is one literal run and the recorded substring is the entire
// sentence):
//     the character is not visibly represented: no mesh component with an assigned mesh on the graded pawn
//
// Predicted diagnostics: NO [DOUBLEJUMP-FINAL] line at all. The fixture
// FinishTest(Failed)s at checkpoint 0 and never reaches the final checkpoint
// where both diagnostic lines are emitted. A run of this variant that DID print
// a FINAL line would mean DJ-7 did not fire and the row is measuring something
// else. PREDICTED - NOT YET MEASURED.

#include "DoubleJumpPawn.h"

#include "DoubleJumpAbility.h"
#include "CraftBenchAttributeSet.h"

// Unchanged from the reference. NOT disclosed by the prompt and NOT a gate
// constant -- the verifier presets Power itself before each leg.
// PROPOSED - NOT YET MEASURED.
static constexpr float DoubleJumpInitialPower = 100.0f;

ADoubleJumpPawn::ADoubleJumpPawn()
{
	// Unchanged from the reference.
	if (AttributeSet != nullptr)
	{
		AttributeSet->InitPower(DoubleJumpInitialPower);
	}

	// Unchanged from the reference: the ability IS granted, so DJ-1 and every
	// behavioural gate downstream of it would pass. This row is about nothing but
	// visibility.
	GrantedAbilities.Add(UDoubleJumpAbility::StaticClass());

	// ---- THE ONE DELTA ------------------------------------------------------
	// The reference's mannequin finder and its -90 Z / -90 yaw placement stood
	// here. They are gone, so the character runs the entire task as an invisible
	// capsule: correct in every observable the gameplay gates read, and useless to
	// a human watching the run.
}

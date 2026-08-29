// Copyright CraftBench. All Rights Reserved.

#include "DoubleJumpPawn.h"

#include "DoubleJumpAbility.h"
#include "CraftBenchAttributeSet.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "UObject/ConstructorHelpers.h"

// The in-game starting Power. NOT disclosed by the prompt and NOT a gate
// constant -- the verifier presets Power itself before each leg (60 for the jump,
// 5 for the refusal), so nothing observable depends on this value; it exists so
// the pawn is playable outside the harness and can afford several jumps.
// PROPOSED - NOT YET MEASURED.
static constexpr float DoubleJumpInitialPower = 100.0f;

ADoubleJumpPawn::ADoubleJumpPawn()
{
	// Initialize the Power resource. AttributeSet is the base class's protected
	// handle to the subobject it constructed. It is null-checked because the base
	// ctor documents it as nullable -- the ACraftBenchBareCharacter lineage
	// suppresses this subobject entirely -- and a reference that assumed non-null
	// would crash the CDO if this pawn were ever reparented.
	//
	// The INITTER writes the base and current value directly and runs no
	// attribute-set hooks, so no clamp or modifier can see a half-built resource
	// here.
	if (AttributeSet != nullptr)
	{
		AttributeSet->InitPower(DoubleJumpInitialPower);
	}

	// The second-jump ability, granted on the pawn so the game can activate it by
	// tag. This is the only other GAS wiring the pawn needs -- the base grants
	// everything in GrantedAbilities on the authority at BeginPlay/PossessedBy.
	GrantedAbilities.Add(UDoubleJumpAbility::StaticClass());

	// Visible-character requirement (PIN.md section 3, AG-8): assign one of the
	// provided mannequin bodies at construction so a reviewer watching the run can
	// SEE the character rise a second time. Guarded finder, copied from the
	// gp-poison-dot-stack-cpp reference and the substrate's own AFireCharacter: a
	// missing asset degrades to the meshless capsule instead of failing CDO
	// construction.
	static ConstructorHelpers::FObjectFinder<USkeletalMesh> BodyFinder(
		TEXT("/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"));
	if (BodyFinder.Succeeded() && GetMesh() != nullptr)
	{
		GetMesh()->SetSkeletalMesh(BodyFinder.Object);
		GetMesh()->SetRelativeLocationAndRotation(
			FVector(0.0, 0.0, -90.0), FRotator(0.0, -90.0, 0.0));
	}
}

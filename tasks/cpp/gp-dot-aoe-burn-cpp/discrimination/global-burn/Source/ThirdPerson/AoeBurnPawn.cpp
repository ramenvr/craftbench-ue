// Reference solution — gp-dot-aoe-burn-cpp.

#include "AoeBurnPawn.h"

#include "AoeBurnAbility.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "UObject/ConstructorHelpers.h"

AAoeBurnPawn::AAoeBurnPawn(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	// The burning-area ability, granted on the pawn so the game can activate it
	// by tag. The generic base grants everything in GrantedAbilities on the
	// authority at BeginPlay/PossessedBy; no other GAS wiring is needed — this
	// family's observable lives on the TARGETS, not on this pawn's own
	// attributes.
	GrantedAbilities.Add(UAoeBurnAbility::StaticClass());

	// Visible-character requirement (family standard): assign one of the
	// provided mannequin bodies at construction. Guarded finder, copied from
	// the sibling references — a missing asset degrades to the meshless
	// capsule instead of failing CDO construction.
	static ConstructorHelpers::FObjectFinder<USkeletalMesh> BodyFinder(
		TEXT("/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"));
	if (BodyFinder.Succeeded() && GetMesh() != nullptr)
	{
		GetMesh()->SetSkeletalMesh(BodyFinder.Object);
		GetMesh()->SetRelativeLocationAndRotation(
			FVector(0.0, 0.0, -90.0), FRotator(0.0, -90.0, 0.0));
	}
}

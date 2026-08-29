// Copyright CraftBench. All Rights Reserved.

#include "PoisonPawn.h"

#include "PoisonAbility.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "UObject/ConstructorHelpers.h"

APoisonPawn::APoisonPawn()
{
	// STAGE 2 ONLY -- deliberately skips stage 1: no attribute set is built, so
	// the ASC exposes no Health. The stage-1 gate must FAIL this by name.
	GrantedAbilities.Add(UPoisonAbility::StaticClass());

	// The mannequin body is kept (2026-08-06 visible-character gate) so this
	// variant stays ONE delta from the reference: the missing attribute set.
	// Ordering note: the fixture's stage-1 presence gate (b) runs BEFORE the
	// visibility gate (e), so this variant still FAILs at its named gate.
	static ConstructorHelpers::FObjectFinder<USkeletalMesh> BodyFinder(
		TEXT("/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"));
	if (BodyFinder.Succeeded() && GetMesh() != nullptr)
	{
		GetMesh()->SetSkeletalMesh(BodyFinder.Object);
		GetMesh()->SetRelativeLocationAndRotation(
			FVector(0.0, 0.0, -90.0), FRotator(0.0, -90.0, 0.0));
	}
}

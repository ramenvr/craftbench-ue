// Copyright CraftBench. All Rights Reserved.

#include "HealthOpsPawn.h"

#include "DamageAbility.h"
#include "HealAbility.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "UObject/ConstructorHelpers.h"

AHealthOpsPawn::AHealthOpsPawn()
{
	// STAGE 1 IS MISSING -- THE ONE DELTA. The reference builds it here:
	//
	//   HealthAttributes = CreateDefaultSubobject<UCraftBenchAttributeSet>(TEXT("HealthAttributes"));
	//   HealthAttributes->InitHealth(100.0f);
	//   HealthAttributes->InitMaxHealth(100.0f);
	//
	// This variant does not, so the inherited ASC carries no attribute set at all
	// (ACraftBenchBareCharacter suppresses the pre-built one for the whole
	// lineage). Everything BELOW this comment is the reference verbatim.

	// STAGE 2 -- unchanged from the reference: both abilities granted, so the
	// resolver still picks this pawn on PreferredAbilityTag (Ability.Damage) and
	// HO-6 would pass. The variant is a complete stage 2 on a pawn with nothing
	// for it to operate on.
	GrantedAbilities.Add(UDamageAbility::StaticClass());
	GrantedAbilities.Add(UHealAbility::StaticClass());

	// Visible-character requirement (HO-5) -- unchanged from the reference, so
	// this variant cannot die at HO-5 by accident.
	static ConstructorHelpers::FObjectFinder<USkeletalMesh> BodyFinder(
		TEXT("/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"));
	if (BodyFinder.Succeeded() && GetMesh() != nullptr)
	{
		GetMesh()->SetSkeletalMesh(BodyFinder.Object);
		GetMesh()->SetRelativeLocationAndRotation(
			FVector(0.0, 0.0, -90.0), FRotator(0.0, -90.0, 0.0));
	}
}

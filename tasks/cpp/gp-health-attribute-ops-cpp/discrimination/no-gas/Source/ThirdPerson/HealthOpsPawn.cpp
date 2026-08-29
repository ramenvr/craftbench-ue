// Copyright CraftBench. All Rights Reserved.

#include "HealthOpsPawn.h"

#include "CraftBenchAttributeSet.h"
#include "AbilitySystemComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "UObject/ConstructorHelpers.h"

AHealthOpsPawn::AHealthOpsPawn()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bStartWithTickEnabled = true;

	// STAGE 1 -- the reference verbatim. HO-1 through HO-5 all pass, which is
	// what makes the HO-6 FAIL attributable to the missing-ability axis alone.
	HealthAttributes = CreateDefaultSubobject<UCraftBenchAttributeSet>(TEXT("HealthAttributes"));
	HealthAttributes->InitHealth(100.0f);
	HealthAttributes->InitMaxHealth(100.0f);

	// STAGE 2 IS NOT AN ABILITY -- THE ONE DELTA. The reference grants both here:
	//
	//   GrantedAbilities.Add(UDamageAbility::StaticClass());
	//   GrantedAbilities.Add(UHealAbility::StaticClass());
	//
	// This variant grants nothing, so NumGrantedAbilitiesWithTag(Ability.Damage)
	// reads 0 and TryActivateAbilitiesByTag finds nothing to run. Health still
	// moves -- from Tick, below -- which is exactly AG-3's shape: the numbers
	// move but nothing is activatable.

	// Visible-character requirement (HO-5) -- unchanged from the reference.
	static ConstructorHelpers::FObjectFinder<USkeletalMesh> BodyFinder(
		TEXT("/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"));
	if (BodyFinder.Succeeded() && GetMesh() != nullptr)
	{
		GetMesh()->SetSkeletalMesh(BodyFinder.Object);
		GetMesh()->SetRelativeLocationAndRotation(
			FVector(0.0, 0.0, -90.0), FRotator(0.0, -90.0, 0.0));
	}
}

void AHealthOpsPawn::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	// The "damage system": Health drains every frame once the pawn is below full,
	// with no ability, no effect and no tag anywhere in the path. See the header
	// for why the `Current < Max` guard is load-bearing (an ungated drift dies at
	// HO-3, the wrong gate) and why the rate is tuned to look conforming.
	if (UAbilitySystemComponent* ASC = GetAbilitySystemComponent())
	{
		const float Current = ASC->GetNumericAttribute(UCraftBenchAttributeSet::GetHealthAttribute());
		const float Max = ASC->GetNumericAttribute(UCraftBenchAttributeSet::GetMaxHealthAttribute());
		if (Current < Max)
		{
			ASC->SetNumericAttributeBase(
				UCraftBenchAttributeSet::GetHealthAttribute(),
				Current - HealthOpsDrainRate * DeltaSeconds);
		}
	}
}

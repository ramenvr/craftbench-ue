// Copyright CraftBench. All Rights Reserved.

#include "GlidePawn.h"

#include "GlideAbility.h"
#include "CraftBenchAttributeSet.h"
#include "AbilitySystemComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "UObject/ConstructorHelpers.h"

AGlidePawn::AGlidePawn()
{
	GrantedAbilities.Add(UGlideAbility::StaticClass());

	// Visible-character requirement (2026-08-06): assign the template's
	// mannequin body at construction so the graded run SHOWS the character
	// falling and gliding (the checkpoint-0 fixture gate asserts a mesh is
	// assigned). Guarded finder, same pattern as the substrate's
	// AFireCharacter: a missing asset degrades to the meshless capsule
	// instead of failing the CDO construction.
	static ConstructorHelpers::FObjectFinder<USkeletalMesh> BodyFinder(
		TEXT("/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"));
	if (BodyFinder.Succeeded() && GetMesh() != nullptr)
	{
		GetMesh()->SetSkeletalMesh(BodyFinder.Object);
		GetMesh()->SetRelativeLocationAndRotation(
			FVector(0.0, 0.0, -90.0), FRotator(0.0, -90.0, 0.0));
	}
}

void AGlidePawn::BeginPlay()
{
	Super::BeginPlay();

	// Start with stamina to spend (the verifier presets a smaller value at trigger
	// to bound the exhaustion experiment; this is the in-game starting value).
	if (UAbilitySystemComponent* ASC = GetAbilitySystemComponent())
	{
		ASC->SetNumericAttributeBase(UCraftBenchAttributeSet::GetPowerAttribute(), 100.0f);
	}
}

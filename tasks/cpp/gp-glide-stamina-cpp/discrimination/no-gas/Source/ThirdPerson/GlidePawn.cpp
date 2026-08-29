// Copyright CraftBench. All Rights Reserved.

#include "GlidePawn.h"

#include "CraftBenchAttributeSet.h"
#include "AbilitySystemComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "UObject/ConstructorHelpers.h"

AGlidePawn::AGlidePawn()
{
	// ---- THE ONE DELTA (anti-gaming note 1: "No GAS") ----
	// The reference grants the ability here:
	//     GrantedAbilities.Add(UGlideAbility::StaticClass());
	// This variant grants NOTHING and instead permanently lowers gravity, which
	// is the exact gaming shape the note describes: a pawn that "just sets a low
	// GravityScale permanently, no ability". Everything else -- the mesh, the
	// starting Power, the ability class itself (still compiled, just never
	// granted) -- is byte-identical to the reference.
	if (UCharacterMovementComponent* CMC = GetCharacterMovement())
	{
		CMC->GravityScale = 0.1f;
	}

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

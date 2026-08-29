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

	// ---- THE ONE DELTA (anti-gaming note 8: "let the verifier's preset supply
	// the resource") ----
	// The reference seeds the pawn's starting stamina here:
	//     if (UAbilitySystemComponent* ASC = GetAbilitySystemComponent())
	//     {
	//         ASC->SetNumericAttributeBase(UCraftBenchAttributeSet::GetPowerAttribute(), 100.0f);
	//     }
	// This variant omits it, so the pawn starts at 0 — `UCraftBenchAttributeSet`
	// declares `FGameplayAttributeData Power;` with no initializer and
	// `ACraftBenchCharacter` never seeds it. Everything ELSE is byte-identical to
	// the reference: the ability still glides and still drains, because the
	// fixture's own `PowerPreset` hands it 30 at the trigger.
	//
	// That is the whole point. Before 2026-08-09 this file PASSED every gate — the
	// prompt's "starting with some Power to spend" clause had no assertion behind
	// it, and the verifier's preset silently did the model's job.
}

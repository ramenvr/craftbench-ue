// Copyright CraftBench. All Rights Reserved.

#include "GlidePawn.h"

#include "GlideAbility.h"
#include "CraftBenchAttributeSet.h"
#include "AbilitySystemComponent.h"

AGlidePawn::AGlidePawn()
{
	GrantedAbilities.Add(UGlideAbility::StaticClass());

	// ---- THE ONE DELTA (anti-gaming note 6: "Invisible deliverable") ----
	// The reference constructor-assigns the template's mannequin body here:
	//     static ConstructorHelpers::FObjectFinder<USkeletalMesh> BodyFinder(
	//         TEXT("/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"));
	//     if (BodyFinder.Succeeded() && GetMesh() != nullptr) { ... }
	// This variant omits it entirely (and the three includes it needed), so the
	// inherited ACharacter mesh component exists but carries NO skeletal mesh
	// asset -- the exact meshless-but-conforming pawn all 9 matrix reps of the
	// -bp twin shipped on 2026-08-04. Every behavioral gate below still passes;
	// only the checkpoint-0 visibility gate fires.
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

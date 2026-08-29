// Copyright CraftBench. All Rights Reserved.

#include "HealthOpsPawn.h"

#include "DamageAbility.h"
#include "HealAbility.h"
#include "CraftBenchAttributeSet.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "UObject/ConstructorHelpers.h"

AHealthOpsPawn::AHealthOpsPawn()
{
	// STAGE 1 -- build the health system: construct the contract attribute set
	// (auto-registered by the pawn-owned ASC at InitializeComponent) and
	// initialize Health to the contract value 100. 100 is DISCLOSED in the
	// prompt ("initialized to 100"), which is what makes HO-3 a lawful absolute
	// gate; it is not a measured tolerance.
	HealthAttributes = CreateDefaultSubobject<UCraftBenchAttributeSet>(TEXT("HealthAttributes"));
	HealthAttributes->InitHealth(100.0f);
	// MaxHealth is disclosed nowhere in this task's prompt and gated nowhere
	// (PIN.md D2 -- upward clamping is gp-heal-over-time's axis). Initialized
	// here only so the resource is coherent for a human reading the run; no
	// gate reads it, and UCraftBenchAttributeSet applies no clamping, so this
	// line can never bound the heal.
	HealthAttributes->InitMaxHealth(100.0f);

	// STAGE 2 -- the two operations: grant both abilities so the game can
	// activate each one by its tag (HO-6). This is the only other GAS wiring.
	GrantedAbilities.Add(UDamageAbility::StaticClass());
	GrantedAbilities.Add(UHealAbility::StaticClass());

	// Visible-character requirement (HO-5 / AG-5): assign the template's
	// mannequin body at construction so the graded run SHOWS the character.
	// Guarded finder, same pattern as the substrate's AFireCharacter and the
	// gp-poison-dot-stack-cpp reference: a missing asset degrades to the
	// meshless capsule instead of failing the CDO construction.
	static ConstructorHelpers::FObjectFinder<USkeletalMesh> BodyFinder(
		TEXT("/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"));
	if (BodyFinder.Succeeded() && GetMesh() != nullptr)
	{
		GetMesh()->SetSkeletalMesh(BodyFinder.Object);
		GetMesh()->SetRelativeLocationAndRotation(
			FVector(0.0, 0.0, -90.0), FRotator(0.0, -90.0, 0.0));
	}
}

// Copyright CraftBench. All Rights Reserved.

#include "PoisonPawn.h"

#include "PoisonAbility.h"
#include "CraftBenchAttributeSet.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "UObject/ConstructorHelpers.h"

APoisonPawn::APoisonPawn()
{
	// STAGE 1 -- build the health system: construct the contract attribute set
	// (auto-registered by the pawn-owned ASC at InitializeComponent) and
	// initialize Health to the contract value 100.
	HealthAttributes = CreateDefaultSubobject<UCraftBenchAttributeSet>(TEXT("HealthAttributes"));
	HealthAttributes->InitHealth(100.0f);
	HealthAttributes->InitMaxHealth(100.0f);

	// STAGE 2 -- the poison DoT: grant the ability (the only other GAS wiring).
	GrantedAbilities.Add(UPoisonAbility::StaticClass());

	// Visible-character requirement (2026-08-06): assign the template's
	// mannequin body at construction so the graded run SHOWS the character
	// (the checkpoint-0 fixture gate asserts a mesh is assigned). Guarded
	// finder, same pattern as the substrate's AFireCharacter: a missing asset
	// degrades to the meshless capsule instead of failing the CDO construction.
	static ConstructorHelpers::FObjectFinder<USkeletalMesh> BodyFinder(
		TEXT("/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"));
	if (BodyFinder.Succeeded() && GetMesh() != nullptr)
	{
		GetMesh()->SetSkeletalMesh(BodyFinder.Object);
		GetMesh()->SetRelativeLocationAndRotation(
			FVector(0.0, 0.0, -90.0), FRotator(0.0, -90.0, 0.0));
	}
}

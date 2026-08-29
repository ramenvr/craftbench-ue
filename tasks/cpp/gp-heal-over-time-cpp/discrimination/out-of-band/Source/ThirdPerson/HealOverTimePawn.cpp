// Copyright CraftBench. All Rights Reserved.

#include "HealOverTimePawn.h"

#include "HealOverTimeAbility.h"
#include "HealOverTimeAttributeSet.h"
#include "CraftBenchAttributeSet.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "UObject/ConstructorHelpers.h"

// The health cap. 100 is DISCLOSED in the prompt ("MaxHealth is 100, and your
// pawn must initialize MaxHealth to 100"), which is what makes it a lawful
// absolute here; it is not a measured tolerance.
// PROPOSED - NOT YET MEASURED.
static constexpr float HealOverTimeMaxHealth = 100.0f;

AHealOverTimePawn::AHealOverTimePawn(const FObjectInitializer& ObjectInitializer)
	// Replace the CLASS of the attribute set the base pawn constructs, before the
	// base ctor runs. ACraftBenchCharacter builds it with
	// CreateOptionalDefaultSubobject<UCraftBenchAttributeSet>(TEXT("AttributeSet"))
	// (CraftBenchCharacter.cpp:25), and SetDefaultSubobjectClass registers an
	// override for that name -- legal because UHealOverTimeAttributeSet derives
	// from the class the base asked for. The result is ONE attribute set on the
	// pawn, of the contract lineage, that clamps.
	: Super(ObjectInitializer.SetDefaultSubobjectClass<UHealOverTimeAttributeSet>(TEXT("AttributeSet")))
{
	// Initialize the health resource. AttributeSet is the base class's protected
	// handle to the subobject just constructed (now a UHealOverTimeAttributeSet).
	// It is null-checked because the base ctor documents it as nullable -- the
	// ACraftBenchBareCharacter lineage suppresses this subobject entirely -- and a
	// reference that assumed non-null would crash the CDO if this pawn were ever
	// reparented.
	//
	// The INITTER (InitHealth/InitMaxHealth) writes the base and current value
	// directly and runs no attribute-set hooks, so the order of these two lines
	// cannot matter and the clamp cannot see a MaxHealth of 0 here.
	if (AttributeSet != nullptr)
	{
		AttributeSet->InitMaxHealth(HealOverTimeMaxHealth);
		AttributeSet->InitHealth(HealOverTimeMaxHealth);
	}

	// The restorative ability, granted on the pawn so the game can start it by
	// tag. This is the only other GAS wiring the pawn needs -- the base grants
	// everything in GrantedAbilities on the authority at BeginPlay/PossessedBy.
	GrantedAbilities.Add(UHealOverTimeAbility::StaticClass());

	// Visible-character requirement (PIN.md section 3, AG-7): assign one of the
	// provided mannequin bodies at construction so a reviewer watching the run can
	// SEE the character. Guarded finder, copied from the gp-poison-dot-stack-cpp
	// reference and the substrate's own AFireCharacter: a missing asset degrades
	// to the meshless capsule instead of failing CDO construction.
	static ConstructorHelpers::FObjectFinder<USkeletalMesh> BodyFinder(
		TEXT("/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"));
	if (BodyFinder.Succeeded() && GetMesh() != nullptr)
	{
		GetMesh()->SetSkeletalMesh(BodyFinder.Object);
		GetMesh()->SetRelativeLocationAndRotation(
			FVector(0.0, 0.0, -90.0), FRotator(0.0, -90.0, 0.0));
	}
}

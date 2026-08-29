// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT `no-maxhealth/` -- ONE DELTA from ../../reference.
// AXIS: the pawn never initializes MaxHealth. Defends PIN.md section 3 AG-1.
// EXPECTED: FAIL at HOT-0, checkpoint 0, before any trigger.
// STATUS: UNVALIDATED / NOT YET RUN (no build, no PIE run, no grade).
//
// THE DELTA, in full: the single line
//
//     AttributeSet->InitMaxHealth(HealOverTimeMaxHealth);
//
// is removed. `InitHealth(100)` is deliberately KEPT, and that is what makes
// this the AG-1 shape rather than a generic broken pawn: the submission looks
// healthy (Health reads 100) while the cap it is supposed to respect reads 0,
// so "Health must never exceed MaxHealth" is satisfiable in the WRONG
// direction -- there is nothing to exceed. Every other file in this overlay is
// byte-identical to the reference.
//
// WHY IT DIES WHERE IT DIES. UCraftBenchAttributeSet ships MaxHealth
// UNINITIALIZED (there is no initializer anywhere in either substrate), so
// PawnAttribute(GetMaxHealthAttribute()) reads 0.0. HOT-0 runs FIRST at
// checkpoint 0 -- before HOT-7, before the Leg 1 preset, before any trigger --
// precisely so this defect is named instead of being misattributed: with the
// clamp live and a cap of 0, ClampHealth() would pin every restore to zero and
// Leg 1 would show no rise at all, which without HOT-0 presents as "the restore
// was not periodic". PIN.md D3 exists for exactly this submission.
//
// EXPECTED NAMED FAIL (a literal run of the HOT-0 format string in
// HealOverTimeFunctionalTest.cpp -- no %-placeholder is spanned):
//     MaxHealth was not initialized: read
//
// Predicted diagnostic: the fixture FinishTest()s at cp0, so no
// [HEALOVERTIME-FINAL] line is emitted at all. That absence is itself the tell
// for a cp0 death and separates this row from every last-checkpoint row.
// PREDICTED - NOT YET MEASURED.

#include "HealOverTimePawn.h"

#include "HealOverTimeAbility.h"
#include "HealOverTimeAttributeSet.h"
#include "CraftBenchAttributeSet.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "UObject/ConstructorHelpers.h"

// The value the pawn initializes Health to. Still 100 (the disclosed number) --
// only the MaxHealth initializer is gone.
// PROPOSED - NOT YET MEASURED.
static constexpr float HealOverTimeMaxHealth = 100.0f;

AHealOverTimePawn::AHealOverTimePawn(const FObjectInitializer& ObjectInitializer)
	// Unchanged from the reference: the attribute set subobject's CLASS is still
	// replaced with the clamping subclass. The clamp is NOT the axis here -- it is
	// left intact so this variant differs from the reference on ONE thing only.
	: Super(ObjectInitializer.SetDefaultSubobjectClass<UHealOverTimeAttributeSet>(TEXT("AttributeSet")))
{
	if (AttributeSet != nullptr)
	{
		// THE DELTA: InitMaxHealth is NOT called. MaxHealth keeps its default 0.
		AttributeSet->InitHealth(HealOverTimeMaxHealth);
	}

	GrantedAbilities.Add(UHealOverTimeAbility::StaticClass());

	static ConstructorHelpers::FObjectFinder<USkeletalMesh> BodyFinder(
		TEXT("/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"));
	if (BodyFinder.Succeeded() && GetMesh() != nullptr)
	{
		GetMesh()->SetSkeletalMesh(BodyFinder.Object);
		GetMesh()->SetRelativeLocationAndRotation(
			FVector(0.0, 0.0, -90.0), FRotator(0.0, -90.0, 0.0));
	}
}

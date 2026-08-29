// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT `no-mesh/` -- ONE DELTA from ../../reference.
// AXIS: the pawn is behaviorally PERFECT but invisible. Defends PIN.md
// section 3 AG-7.
// EXPECTED: FAIL at HOT-7, checkpoint 0.
// STATUS: UNVALIDATED / NOT YET RUN (no build, no PIE run, no grade).
//
// THE DELTA, in full: the constructor's mannequin block
//
//     static ConstructorHelpers::FObjectFinder<USkeletalMesh> BodyFinder(...);
//     if (BodyFinder.Succeeded() && GetMesh() != nullptr) { ... }
//
// is removed, together with the three includes only it needed. Nothing else
// changes -- MaxHealth is still initialized to 100, the clamping attribute set
// is still installed, the ability is still granted, and the periodic effect is
// the reference's. On every axis the prompt grades as BEHAVIOR this submission
// is correct; it simply cannot be seen.
//
// WHY THAT MATTERS AS A SEPARATE ROW. `empty` (no overlay at all) also trips the
// visibility gate, because the resolver falls back to a scaffold pawn that is
// meshless AND grants nothing -- for `empty` the visibility gate is an ACCIDENT
// of checkpoint ordering. This variant is the only leg that proves HOT-7
// discriminates on the visibility axis ALONE. Same argument, and the same
// caveat, as gp-glide-stamina-cpp/discrimination/MATRIX.md's `no-mesh/` row.
//
// EXPECTED NAMED FAIL (the WHOLE TEXT() literal in
// HealOverTimeFunctionalTest.cpp -- it carries no %-placeholder at all):
//     the character is not visibly represented: no mesh component with an assigned mesh on the graded pawn
//
// Predicted diagnostic: HOT-0 passes first (MaxHealth reads 100.0), then the
// fixture FinishTest()s at cp0, so no [HEALOVERTIME-FINAL] line is emitted.
// PREDICTED - NOT YET MEASURED.

#include "HealOverTimePawn.h"

#include "HealOverTimeAbility.h"
#include "HealOverTimeAttributeSet.h"
#include "CraftBenchAttributeSet.h"

// The health cap. 100 is DISCLOSED in the prompt, which is what makes it a
// lawful absolute here; it is not a measured tolerance.
// PROPOSED - NOT YET MEASURED.
static constexpr float HealOverTimeMaxHealth = 100.0f;

AHealOverTimePawn::AHealOverTimePawn(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer.SetDefaultSubobjectClass<UHealOverTimeAttributeSet>(TEXT("AttributeSet")))
{
	if (AttributeSet != nullptr)
	{
		AttributeSet->InitMaxHealth(HealOverTimeMaxHealth);
		AttributeSet->InitHealth(HealOverTimeMaxHealth);
	}

	GrantedAbilities.Add(UHealOverTimeAbility::StaticClass());

	// THE DELTA: no mesh is assigned. The inherited ACharacter Mesh component
	// still exists, but GetSkeletalMeshAsset() returns null on it, so the
	// fixture's checkpoint-0 sweep over every UMeshComponent finds nothing with
	// an assigned mesh.
}

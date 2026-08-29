// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION for task gp-heal-over-time-cpp (PIN.md section 4, "A
// PASSING solve"). A subclass of the PROVIDED character that:
//   - initializes Health and MaxHealth to 100 on the provided attribute set;
//   - grants the restorative ability;
//   - wears one of the provided mannequin bodies (the visible-character gate);
//   - swaps the provided attribute set for a clamping subclass of it, so Health
//     can never exceed MaxHealth in EITHER the current or the base value.
//
// DERIVES FROM THE GENERIC ACraftBenchCharacter, NOT ACraftBenchBareCharacter.
// PIN.md D2: this family gets Health pre-built -- stage 1 ("the agent BUILDS the
// health system") is gp-poison-dot-stack-cpp's and gp-health-attribute-ops-cpp's
// axis, and routing a third task through the bare lineage would make the three
// tasks' stage-1 populations a three-way correlation (constraint C1 in
// the g2 task queue) and cost tier 1 a usable graded cell. The generic pawn
// pre-builds a UCraftBenchAttributeSet default subobject named "AttributeSet".
//
// WHY THE SET IS SWAPPED RATHER THAN ADDED. The provided set does no clamping at
// all, so the invariant has to come from somewhere, and the clamp hooks are
// UAttributeSet virtuals -- a subclass is the only place they can live.
// CONSTRUCTING A SECOND attribute set alongside the inherited one would be the
// wrong way to introduce it: the ASC resolves an attribute with
// GetAttributeSubobject(Attribute.GetAttributeSetClass()), which matches on IsA,
// so two registered UCraftBenchAttributeSet-lineage sets both answer
// GetHealthAttribute() and which one wins is enumeration order. Overriding the
// inherited subobject's CLASS through the FObjectInitializer leaves exactly one
// set on the pawn, still of the contract lineage, now with the clamp.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchCharacter.h"
#include "HealOverTimePawn.generated.h"

UCLASS()
class AHealOverTimePawn : public ACraftBenchCharacter
{
	GENERATED_BODY()

public:
	/** Takes the FObjectInitializer explicitly because it has to be MODIFIED
	 *  before it reaches the base ctor -- see the .cpp. */
	AHealOverTimePawn(const FObjectInitializer& ObjectInitializer);
};

// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT `generic-pawn/` for task gp-health-attribute-ops-cpp.
// Anti-gaming note AG-1 (PIN.md section 3): "subclass the *generic* character
// and inherit its pre-built attribute set, skipping stage 1 entirely."
//
// THE ONE DELTA, and it is one line: the parent class is ACraftBenchCharacter
// (the GENERIC scaffold, which pre-builds a UCraftBenchAttributeSet subobject)
// instead of ACraftBenchBareCharacter (the task base, which suppresses it).
// Nothing else changes -- every other byte of this variant is the reference,
// including the stage-1 subobject, InitHealth(100), both granted abilities and
// the mannequin mesh.
//
// EXPECTED: FAIL at HO-1, checkpoint 0, on the named substring
//   "does not derive from the provided task base pawn (CraftBenchBareCharacter)"
// UNVALIDATED / NOT YET RUN -- see discrimination/MATRIX.md.
//
// WHY THE VARIANT KEEPS BUILDING ITS OWN SET (it looks redundant on this
// lineage, and that is the point): leaving stage 1 in place makes this a
// behaviorally COMPLETE solve whose only defect is the parent class, so a FAIL
// here can only be HO-1. A variant that ALSO dropped the subobject would be
// indistinguishable from `no-health-system/` in intent and would prove nothing
// about the derivation axis on its own. Consequence on this lineage: the pawn
// carries TWO UCraftBenchAttributeSet subobjects (the inherited "AttributeSet"
// plus "HealthAttributes"); GetAttributeSubobject returns the first IsA match,
// which is harmless and unreachable anyway -- HO-1 fires at checkpoint 0 before
// any attribute is read.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchCharacter.h"
#include "HealthOpsPawn.generated.h"

class UCraftBenchAttributeSet;

UCLASS()
class AHealthOpsPawn : public ACraftBenchCharacter
{
	GENERATED_BODY()

public:
	AHealthOpsPawn();

private:
	/** Same stage-1 subobject the reference builds -- see the header note on why
	 *  it is deliberately retained on this (generic) lineage. */
	UPROPERTY()
	TObjectPtr<UCraftBenchAttributeSet> HealthAttributes;
};

// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION for task gp-health-attribute-ops-cpp (PIN.md section 4,
// "A PASSING solve"). A character subclass that BUILDS the health system
// (stage 1), grants the two one-shot health operations (stage 2), and wears the
// template's mannequin body (the checkpoint-0 visible-character gate HO-5).
//
// Stage 1 here is LIFTED from gp-poison-dot-stack-cpp's PoisonPawn on purpose:
// that shared stage-1 ladder is the correlation declared as constraint C1 in
// the g2 task queue, and it is why this task costs zero new verifier infra.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchBareCharacter.h"
#include "HealthOpsPawn.generated.h"

class UCraftBenchAttributeSet;

UCLASS()
class AHealthOpsPawn : public ACraftBenchBareCharacter
{
	GENERATED_BODY()

public:
	AHealthOpsPawn();

private:
	/** STAGE 1 -- the health system this pawn builds: the contract attribute
	 *  set, created under a name OTHER than "AttributeSet" (that subobject name
	 *  is suppressed for the whole construction of the ACraftBenchBareCharacter
	 *  lineage). The pawn-owned ASC auto-registers owner-outer'd attribute sets
	 *  at InitializeComponent. */
	UPROPERTY()
	TObjectPtr<UCraftBenchAttributeSet> HealthAttributes;
};

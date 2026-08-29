// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION for task gp-poison-dot-stack-cpp (2026-08-05 health-first
// two-stage shape). A character subclass that BUILDS the health system
// (stage 1), grants the poison ability (stage 2), and wears the template's
// mannequin body (the checkpoint-0 visible-character gate, 2026-08-06).

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchBareCharacter.h"
#include "PoisonPawn.generated.h"

class UCraftBenchAttributeSet;

UCLASS()
class APoisonPawn : public ACraftBenchBareCharacter
{
	GENERATED_BODY()

public:
	APoisonPawn();

private:
	/** STAGE 1 -- the health system this pawn builds: the contract attribute
	 *  set, created under a name OTHER than "AttributeSet" (that subobject name
	 *  is suppressed on the ACraftBenchBareCharacter lineage). The pawn-owned
	 *  ASC auto-registers owner-outer'd attribute sets at InitializeComponent. */
	UPROPERTY()
	TObjectPtr<UCraftBenchAttributeSet> HealthAttributes;
};

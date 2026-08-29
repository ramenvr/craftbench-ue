// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION for task gp-double-jump-stamina. A character subclass of
// the provided pawn (which already owns the ability system and the Power
// resource) that grants the second-jump ability, starts with Power to spend, and
// wears one of the provided mannequin bodies so a reviewer watching the run can
// SEE the character jump.
//
// Derives from ACraftBenchCharacter, NOT ACraftBenchBareCharacter: this family is
// not health-first, so the pre-built attribute set the base constructs is exactly
// what the prompt describes ("a character pawn that already owns ... a depletable
// Power resource"). The Bare lineage suppresses that subobject and would leave
// this pawn with no Power at all.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchCharacter.h"
#include "DoubleJumpPawn.generated.h"

UCLASS()
class ADoubleJumpPawn : public ACraftBenchCharacter
{
	GENERATED_BODY()

public:
	ADoubleJumpPawn();
};

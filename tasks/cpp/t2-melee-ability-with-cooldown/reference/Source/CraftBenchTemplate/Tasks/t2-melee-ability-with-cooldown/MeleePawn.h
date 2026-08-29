// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION for task t2-melee-ability-with-cooldown. A character
// subclass that grants the melee ability.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchCharacter.h"
#include "MeleePawn.generated.h"

UCLASS()
class AMeleePawn : public ACraftBenchCharacter
{
	GENERATED_BODY()

public:
	AMeleePawn();
};

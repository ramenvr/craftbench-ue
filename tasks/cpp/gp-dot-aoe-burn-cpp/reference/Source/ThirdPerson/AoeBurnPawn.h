// Reference solution — gp-dot-aoe-burn-cpp.
//
// The playable character: the generic base plus the burning-area ability in
// its granted set. Same one-decision shape as the sibling families' reference
// pawns.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchCharacter.h"
#include "AoeBurnPawn.generated.h"

UCLASS()
class THIRDPERSON_API AAoeBurnPawn : public ACraftBenchCharacter
{
	GENERATED_BODY()

public:
	AAoeBurnPawn(const FObjectInitializer& ObjectInitializer);
};

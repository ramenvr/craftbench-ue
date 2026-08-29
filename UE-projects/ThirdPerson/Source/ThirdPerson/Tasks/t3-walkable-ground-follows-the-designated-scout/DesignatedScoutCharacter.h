// Copyright CraftBench. All Rights Reserved.
// ADesignatedScoutCharacter - supplied movable base for task t3-walkable-ground-follows-the-designated-scout.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "DesignatedScoutCharacter.generated.h"

/**
 * Supplied movable base for the editable designated-scout Blueprint.
 * The task is to make nearby walkable ground follow this character while it
 * changes neighborhoods; the base supplies only ordinary character movement,
 * AI possession, and stable world identity.
 */
UCLASS(Blueprintable)
class THIRDPERSON_API ADesignatedScoutCharacter : public ACharacter
{
	GENERATED_BODY()

public:
	ADesignatedScoutCharacter(const FObjectInitializer& ObjectInitializer);
};

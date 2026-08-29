// Copyright CraftBench. All Rights Reserved.
//
// ADelayedMoverActor -- pre-existing actor type for task t1-blueprint-event-to-action.
// The constructor stamps the "DelayedMoverRoot" identity tag and provides a plain
// movable root component; no gameplay behavior is implemented here. The required
// behavior is specified in the task prompt. May be subclassed freely (the placed
// instance in the level is a Blueprint subclass of this type).

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "DelayedMoverActor.generated.h"

UCLASS()
class CRAFTBENCHTEMPLATE_API ADelayedMoverActor : public AActor
{
	GENERATED_BODY()

public:
	ADelayedMoverActor();
};

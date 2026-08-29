// Copyright CraftBench. All Rights Reserved.
//
// ACraftQueueActor — pre-existing actor for task gp-crafting-queue. The
// constructor enables tick and stamps the "CraftQueueRoot" identity tag. No
// BeginPlay / queue / timer logic is provided; the required behavior is
// specified in the task prompt and is the agent's to implement. Agents may
// subclass or rename freely.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "CraftQueueActor.generated.h"

UCLASS()
class CRAFTBENCHTEMPLATE_API ACraftQueueActor : public AActor
{
	GENERATED_BODY()

public:
	ACraftQueueActor();
};

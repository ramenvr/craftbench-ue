// Copyright CraftBench. All Rights Reserved.
//
// ACraftQueueActor implementation for task gp-crafting-queue. The constructor
// enables tick and stamps the "CraftQueueRoot" identity tag. No BeginPlay /
// queue / timer logic is provided; the required behavior is specified in the
// task prompt and is the agent's to implement.

#include "CraftQueueActor.h"

ACraftQueueActor::ACraftQueueActor()
{
	PrimaryActorTick.bCanEverTick = true;
	Tags.Add(FName("CraftQueueRoot"));
}

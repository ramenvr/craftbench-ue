// Copyright CraftBench. All Rights Reserved.
//
// ASpawnerActor implementation for task gp-spawner-population. The constructor
// enables tick and stamps the "SpawnerRoot" identity tag. No BeginPlay /
// EndPlay / spawn logic is provided; the required behavior is specified in the
// task prompt and is the agent's to implement.

#include "SpawnerActor.h"

ASpawnerActor::ASpawnerActor()
{
	PrimaryActorTick.bCanEverTick = true;
	Tags.Add(FName("SpawnerRoot"));
}

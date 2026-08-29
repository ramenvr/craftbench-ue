// Copyright CraftBench. All Rights Reserved.
//
// ASpawnerActor — pre-existing actor for task gp-spawner-population. The
// constructor enables tick and stamps the "SpawnerRoot" identity tag. No
// BeginPlay / EndPlay / spawn logic is provided; the required behavior is
// specified in the task prompt and is the agent's to implement. Agents may
// subclass or rename freely.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "SpawnerActor.generated.h"

UCLASS()
class CRAFTBENCHTEMPLATE_API ASpawnerActor : public AActor
{
	GENERATED_BODY()

public:
	ASpawnerActor();
};

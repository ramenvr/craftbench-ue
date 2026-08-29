// Copyright CraftBench. All Rights Reserved.
//
// AHarvestableActor — pre-existing actor for task gp-harvestable-regrow. The
// constructor enables tick, creates a query-only USphereComponent overlap
// volume as the root (so overlap with another actor can be detected — the agent
// binds its begin-overlap event), and stamps the "HarvestableRoot" identity tag.
// No BeginPlay / overlap handler / state logic is provided; the required
// behavior is specified in the task prompt and is the agent's to implement.
// Agents may subclass or rename freely.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "HarvestableActor.generated.h"

class USphereComponent;

UCLASS()
class CRAFTBENCHTEMPLATE_API AHarvestableActor : public AActor
{
	GENERATED_BODY()

public:
	AHarvestableActor();

protected:
	/** Query-only overlap volume + scene root, at the actor's world location.
	 *  The agent binds this component's begin-overlap event. */
	UPROPERTY(VisibleAnywhere)
	USphereComponent* CollisionSphere;
};

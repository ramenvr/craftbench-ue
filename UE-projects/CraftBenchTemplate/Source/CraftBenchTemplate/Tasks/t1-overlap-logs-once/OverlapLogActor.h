// Copyright CraftBench. All Rights Reserved.
//
// AOverlapLogActor — pre-existing actor for task t1-overlap-logs-once. The
// constructor creates a query-only USphereComponent overlap volume as the root
// (so overlap with another actor can be detected — the agent binds its
// begin-overlap event) and stamps the "OverlapLogRoot" identity tag. No overlap
// handling or logging is provided; the required behavior is specified in the
// task prompt and is the agent's to implement. Agents may subclass or rename
// freely.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "OverlapLogActor.generated.h"

class USphereComponent;

UCLASS()
class CRAFTBENCHTEMPLATE_API AOverlapLogActor : public AActor
{
	GENERATED_BODY()

public:
	AOverlapLogActor();

protected:
	/** Query-only overlap volume + scene root. The agent binds this component's
	 *  begin-overlap event. */
	UPROPERTY(VisibleAnywhere)
	USphereComponent* CollisionSphere;
};

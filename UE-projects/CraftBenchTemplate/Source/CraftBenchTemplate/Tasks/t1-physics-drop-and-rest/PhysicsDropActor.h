// Copyright CraftBench. All Rights Reserved.
//
// APhysicsDropActor — pre-existing actor for task t1-physics-drop-and-rest. The
// constructor creates a movable UStaticMeshComponent ("Body") displaying the
// engine cube as the root and stamps the "PhysicsDropRoot" identity tag. Physics
// simulation is OFF and collision is left at defaults; enabling dynamic physics
// and configuring the collision responses is the agent's task, per the prompt.
// Agents may subclass or rename freely.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "PhysicsDropActor.generated.h"

class UStaticMeshComponent;

UCLASS()
class CRAFTBENCHTEMPLATE_API APhysicsDropActor : public AActor
{
	GENERATED_BODY()

public:
	APhysicsDropActor();

protected:
	/** Movable cube mesh + scene root. The agent enables physics on this and
	 *  configures its collision responses. */
	UPROPERTY(VisibleAnywhere)
	UStaticMeshComponent* Body;
};

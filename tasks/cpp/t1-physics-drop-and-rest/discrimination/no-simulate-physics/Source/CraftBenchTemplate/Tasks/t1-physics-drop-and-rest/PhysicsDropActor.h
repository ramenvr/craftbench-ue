// Copyright CraftBench. All Rights Reserved.
//
// Discrimination variant "no-simulate-physics" for task t1-physics-drop-and-rest:
// the collision responses are configured correctly, but rigid-body simulation is
// never enabled — the cube never falls. Targets anti-gaming note #1.

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
	UPROPERTY(VisibleAnywhere)
	UStaticMeshComponent* Body;
};

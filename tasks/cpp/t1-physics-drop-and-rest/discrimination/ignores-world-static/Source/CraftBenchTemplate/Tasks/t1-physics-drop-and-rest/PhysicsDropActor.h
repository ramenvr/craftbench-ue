// Copyright CraftBench. All Rights Reserved.
//
// Discrimination variant "ignores-world-static" for task t1-physics-drop-and-rest:
// the agent "solves" the pass-through-the-player requirement by ignoring EVERY
// channel, including WorldStatic. Targets anti-gaming note #3.

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

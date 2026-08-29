// Copyright CraftBench. All Rights Reserved.
//
// Discrimination variant "fakes-fall-in-tick" for task t1-physics-drop-and-rest:
// physics is never enabled; the descent is faked by moving the actor down every
// tick at a constant rate — so it "falls" but never comes to rest. Targets
// anti-gaming notes #1/#4 (skips the mechanism, never settles).

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

	// DELTA: manual per-frame descent instead of rigid-body simulation.
	virtual void Tick(float DeltaSeconds) override;

protected:
	UPROPERTY(VisibleAnywhere)
	UStaticMeshComponent* Body;
};

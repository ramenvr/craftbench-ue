// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT (teleport-once-then-static) for task
// t1-movement-component-drives-actor. ONE DELTA vs the reference: instead of a
// movement component driving steady motion, a one-shot timer teleports the
// actor forward once shortly after play begins, then leaves it static — the
// anti-gaming note #1 failure mode. Must FAIL the ContinuesMoving gate
// ("the actor is no longer advancing").

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "DriftActor.generated.h"

class UStaticMeshComponent;

UCLASS()
class CRAFTBENCHTEMPLATE_API ADriftActor : public AActor
{
	GENERATED_BODY()

public:
	ADriftActor();

protected:
	virtual void BeginPlay() override;

	void TeleportOnce();

	UPROPERTY(VisibleAnywhere)
	UStaticMeshComponent* Body;

	FTimerHandle TeleportTimerHandle;
};

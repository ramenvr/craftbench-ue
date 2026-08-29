// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT (spawns-tagged-proxy-mover) for task
// t1-movement-component-drives-actor. ONE DELTA vs the reference: instead of
// driving the PLACED actor, BeginPlay spawns a fresh proxy actor, stamps the
// same 'DriftRoot' identity tag on it, and drives THAT with a movement
// component — the wrong-actor / identity-gaming failure mode the spec's
// "Robust identity" clause exists for. Two tagged actors now exist, so the
// fixture must FAIL at the resolve gate
// ("Expected exactly one actor tagged 'DriftRoot'").

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

	UPROPERTY(VisibleAnywhere)
	UStaticMeshComponent* Body;
};

// Copyright CraftBench. All Rights Reserved.
//
// Reference solution for task t1-movement-component-drives-actor: attach a
// projectile movement component configured with zero gravity and a constant
// velocity so the actor glides steadily in a straight line, framerate-independent.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "DriftActor.generated.h"

class UStaticMeshComponent;
class UProjectileMovementComponent;

UCLASS()
class CRAFTBENCHTEMPLATE_API ADriftActor : public AActor
{
	GENERATED_BODY()

public:
	ADriftActor();

protected:
	UPROPERTY(VisibleAnywhere)
	UStaticMeshComponent* Body;

	UPROPERTY(VisibleAnywhere)
	UProjectileMovementComponent* Movement;
};

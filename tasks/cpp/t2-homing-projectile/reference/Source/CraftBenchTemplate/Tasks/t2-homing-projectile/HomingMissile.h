// Copyright CraftBench. All Rights Reserved.
//
// Reference solution for task t2-homing-projectile: a projectile actor whose
// movement component homes on a target component for its entire flight.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "HomingMissile.generated.h"

class UProjectileMovementComponent;
class UStaticMeshComponent;

UCLASS()
class CRAFTBENCHTEMPLATE_API AHomingMissile : public AActor
{
	GENERATED_BODY()

public:
	AHomingMissile();

	/** Aim the initial velocity and home on the given actor's root for the whole flight. */
	void InitHoming(AActor* InTarget);

protected:
	UPROPERTY(VisibleAnywhere)
	TObjectPtr<UProjectileMovementComponent> Movement;

	/** Showcase-visibility only (small sphere); never asserted by the verifier. */
	UPROPERTY(VisibleAnywhere)
	TObjectPtr<UStaticMeshComponent> Visual;
};

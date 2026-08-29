// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT (gravity-acceleration-ramp) for task
// t1-movement-component-drives-actor. Header is byte-identical to the
// reference (the delta is confined to two constructor property values in the
// .cpp): the movement component is kept, but configured so the actor
// ACCELERATES instead of holding a steady speed — the anti-gaming note #2
// failure mode. Must FAIL the ConstantVelocity gate
// ("the drift is not constant-velocity").

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

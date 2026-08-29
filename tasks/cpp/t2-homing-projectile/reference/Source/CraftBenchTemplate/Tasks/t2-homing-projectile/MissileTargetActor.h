// Copyright CraftBench. All Rights Reserved.
//
// Reference copy of the AMissileTargetActor scaffold for task
// t2-homing-projectile. Behavior-identical to the substrate scaffold (tick
// disabled, "MissileTarget" tag, movable scene root); it only adds a small
// cube mesh so the target is visible in review captures.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "MissileTargetActor.generated.h"

class UStaticMeshComponent;

UCLASS()
class CRAFTBENCHTEMPLATE_API AMissileTargetActor : public AActor
{
	GENERATED_BODY()

public:
	AMissileTargetActor();

protected:
	/** Showcase-visibility only (small cube); never asserted by the verifier. */
	UPROPERTY(VisibleAnywhere)
	TObjectPtr<UStaticMeshComponent> Visual;
};

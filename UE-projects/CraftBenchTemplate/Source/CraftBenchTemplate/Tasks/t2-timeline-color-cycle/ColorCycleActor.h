// Copyright CraftBench. All Rights Reserved.
//
// AColorCycleActor — pre-existing display actor for task t2-timeline-color-cycle.
// The constructor builds a visible cube (engine basic shape) and stamps the
// "ColorCycle" identity tag. The cube renders with its default material and
// never changes color; the required color behavior is specified in the task
// prompt and is the agent's to implement. Edit this type in place — a placed
// instance of it is what gets graded; do not rename the class (the level's
// class reference would break).

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ColorCycleActor.generated.h"

class UStaticMeshComponent;

UCLASS()
class CRAFTBENCHTEMPLATE_API AColorCycleActor : public AActor
{
	GENERATED_BODY()

public:
	AColorCycleActor();

protected:
	/** The visible cube. Ships with the engine basic-shape mesh and its
	 *  default material. */
	UPROPERTY(VisibleAnywhere)
	UStaticMeshComponent* DisplayMesh;
};

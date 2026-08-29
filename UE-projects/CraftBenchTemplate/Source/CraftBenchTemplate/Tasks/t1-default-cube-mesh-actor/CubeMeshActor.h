// Copyright CraftBench. All Rights Reserved.
//
// ACubeMeshActor — pre-existing actor for task t1-default-cube-mesh-actor. The
// constructor creates a plain scene root and stamps the "CubeMeshDisplay"
// identity tag. No visual representation is provided; the required default
// appearance is specified in the task prompt and is the agent's to implement.
// Edit this type in place - a placed instance of it is graded, so a new
// subclass never reaches the level and renaming breaks the placed reference.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "CubeMeshActor.generated.h"

UCLASS()
class CRAFTBENCHTEMPLATE_API ACubeMeshActor : public AActor
{
	GENERATED_BODY()

public:
	ACubeMeshActor();

protected:
	/** Plain scene root; the actor ships with no visual component. */
	UPROPERTY(VisibleAnywhere)
	USceneComponent* Root;
};

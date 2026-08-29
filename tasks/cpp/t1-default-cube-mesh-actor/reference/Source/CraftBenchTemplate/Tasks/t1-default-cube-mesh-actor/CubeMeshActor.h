// Copyright CraftBench. All Rights Reserved.
//
// Reference solution for task t1-default-cube-mesh-actor.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "CubeMeshActor.generated.h"

class UStaticMeshComponent;

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

	/** Default visual: the engine's built-in cube, assigned as a class default. */
	UPROPERTY(VisibleAnywhere)
	UStaticMeshComponent* CubeMesh;
};

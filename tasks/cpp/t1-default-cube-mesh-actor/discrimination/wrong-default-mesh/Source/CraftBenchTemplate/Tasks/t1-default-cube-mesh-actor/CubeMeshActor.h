// Copyright CraftBench. All Rights Reserved.
//
// Discrimination variant "wrong-default-mesh" for task
// t1-default-cube-mesh-actor. Correct mechanism (a real class default), wrong
// content: the sphere primitive instead of the cube. The mesh-identity assert
// must fail this — a "shows some primitive by default" gate would wrongly
// pass it.

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

	/** Default visual — but the wrong primitive (sphere, not cube). */
	UPROPERTY(VisibleAnywhere)
	UStaticMeshComponent* CubeMesh;
};

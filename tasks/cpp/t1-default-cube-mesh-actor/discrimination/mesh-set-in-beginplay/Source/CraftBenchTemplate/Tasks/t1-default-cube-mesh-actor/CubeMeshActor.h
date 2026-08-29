// Copyright CraftBench. All Rights Reserved.
//
// Discrimination variant "mesh-set-in-beginplay" for task
// t1-default-cube-mesh-actor. Models the gamed solution the task's runtime-
// assignment anti-gaming note targets: the cube is loaded and assigned inside
// BeginPlay, so the placed instance LOOKS correct at checkpoint time but the
// type carries no default — the pre-BeginPlay observation and the class-default
// probe must both fail this.

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
	virtual void BeginPlay() override;

	/** Plain scene root; the actor ships with no visual component. */
	UPROPERTY(VisibleAnywhere)
	USceneComponent* Root;

	/** Mesh component created as a default subobject — but the mesh asset is
	 *  only assigned at BeginPlay (the gamed half). */
	UPROPERTY(VisibleAnywhere)
	UStaticMeshComponent* CubeMesh;
};

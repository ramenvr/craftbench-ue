// Copyright CraftBench. All Rights Reserved.
//
// Discrimination variant "component-without-mesh" for task
// t1-default-cube-mesh-actor. Half-delivery: the static-mesh component exists
// as a default subobject but no mesh asset is ever assigned, so the actor
// still renders nothing. A component-presence gate would wrongly pass this;
// the mesh-identity asserts must fail it.

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

	/** Mesh component with no mesh asset assigned — renders nothing. */
	UPROPERTY(VisibleAnywhere)
	UStaticMeshComponent* CubeMesh;
};

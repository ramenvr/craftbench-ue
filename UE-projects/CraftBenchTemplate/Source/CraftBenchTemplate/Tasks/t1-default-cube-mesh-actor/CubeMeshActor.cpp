// Copyright CraftBench. All Rights Reserved.
//
// ACubeMeshActor implementation for task t1-default-cube-mesh-actor. The
// constructor creates a plain scene root and stamps the "CubeMeshDisplay"
// identity tag. No visual representation is provided; the required default
// appearance is specified in the task prompt and is the agent's to implement.

#include "CubeMeshActor.h"

ACubeMeshActor::ACubeMeshActor()
{
	PrimaryActorTick.bCanEverTick = false;

	Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	SetRootComponent(Root);

	Tags.Add(FName("CubeMeshDisplay"));
}

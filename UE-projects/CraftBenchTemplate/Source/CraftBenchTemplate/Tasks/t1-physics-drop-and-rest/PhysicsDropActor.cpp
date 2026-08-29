// Copyright CraftBench. All Rights Reserved.
//
// APhysicsDropActor implementation for task t1-physics-drop-and-rest. The
// constructor builds a movable cube mesh root and stamps the "PhysicsDropRoot"
// identity tag. Physics is OFF and collision is default; enabling dynamic
// physics and configuring the collision responses is the agent's task.

#include "PhysicsDropActor.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "UObject/ConstructorHelpers.h"

APhysicsDropActor::APhysicsDropActor()
{
	PrimaryActorTick.bCanEverTick = false;

	Body = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Body"));
	SetRootComponent(Body);
	Body->SetMobility(EComponentMobility::Movable);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(TEXT("/Engine/BasicShapes/Cube.Cube"));
	if (CubeMesh.Succeeded())
	{
		Body->SetStaticMesh(CubeMesh.Object);
	}

	Tags.Add(FName("PhysicsDropRoot"));
}

// Copyright CraftBench. All Rights Reserved.
//
// Reference solution for task t1-default-cube-mesh-actor. The engine cube is
// resolved with a static ConstructorHelpers finder (constructor-time only API)
// and assigned to a default subobject, so every instance of the type carries
// the cube as a class default — present on the CDO and on any placed or
// spawned instance before BeginPlay.

#include "CubeMeshActor.h"

#include "Components/StaticMeshComponent.h"
#include "UObject/ConstructorHelpers.h"

ACubeMeshActor::ACubeMeshActor()
{
	PrimaryActorTick.bCanEverTick = false;

	Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	SetRootComponent(Root);

	CubeMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("CubeMesh"));
	CubeMesh->SetupAttachment(Root);
	CubeMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeFinder(TEXT("/Engine/BasicShapes/Cube"));
	if (CubeFinder.Succeeded())
	{
		CubeMesh->SetStaticMesh(CubeFinder.Object);
	}

	Tags.Add(FName("CubeMeshDisplay"));
}

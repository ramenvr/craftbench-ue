// Copyright CraftBench. All Rights Reserved.
//
// Discrimination variant "wrong-default-mesh": a genuine class default, but
// the sphere primitive instead of the required cube. Expected verdict: FAIL
// via the fixture's mesh-identity message ("instead of the engine cube").

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

	static ConstructorHelpers::FObjectFinder<UStaticMesh> SphereFinder(TEXT("/Engine/BasicShapes/Sphere"));
	if (SphereFinder.Succeeded())
	{
		CubeMesh->SetStaticMesh(SphereFinder.Object);
	}

	Tags.Add(FName("CubeMeshDisplay"));
}

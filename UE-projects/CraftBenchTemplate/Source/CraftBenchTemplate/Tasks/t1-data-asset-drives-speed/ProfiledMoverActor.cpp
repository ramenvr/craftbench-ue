// Copyright CraftBench. All Rights Reserved.
//
// AProfiledMoverActor implementation for task t1-data-asset-drives-speed. The
// constructor builds a movable cube root and stamps the "ProfiledMoverRoot"
// identity tag. No motion is provided; reading the profile's CruiseSpeed and
// moving the actor at that speed is the agent's task.

#include "ProfiledMoverActor.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "UObject/ConstructorHelpers.h"

AProfiledMoverActor::AProfiledMoverActor()
{
	PrimaryActorTick.bCanEverTick = false;

	Body = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Body"));
	SetRootComponent(Body);
	Body->SetMobility(EComponentMobility::Movable);
	Body->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(TEXT("/Engine/BasicShapes/Cube.Cube"));
	if (CubeMesh.Succeeded())
	{
		Body->SetStaticMesh(CubeMesh.Object);
	}

	Profile = nullptr;
	Tags.Add(FName("ProfiledMoverRoot"));
}

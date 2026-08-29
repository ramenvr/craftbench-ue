// Copyright CraftBench. All Rights Reserved.

#include "RailActor.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "UObject/ConstructorHelpers.h"

ARailActor::ARailActor()
{
	PrimaryActorTick.bCanEverTick = false;

	Rail = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Rail"));
	SetRootComponent(Rail);
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube"));
	if (CubeMesh.Succeeded())
	{
		Rail->SetStaticMesh(CubeMesh.Object);
	}
	// 2,400 x 80 x 10 cm from the 100 cm engine cube. Placed with its centre 3 cm
	// below the floor, that leaves the rail standing 2 cm PROUD and 80 cm wide, so it
	// reads as a painted band in a still. Flush and 40 cm wide it was invisible --
	// same height and same material as the floor -- and a reviewer could not tell
	// which block was on the rail or what line it was tracking, which is the whole
	// story of the level. The blocks clear it: they are held 4 cm above the floor.
	Rail->SetRelativeScale3D(FVector(24.0f, 0.8f, 0.10f));
	Rail->SetMobility(EComponentMobility::Static);
	Rail->SetCollisionProfileName(TEXT("BlockAll"));
	Rail->SetSimulatePhysics(false);

	Tags.Add(FName("RailLine"));
}

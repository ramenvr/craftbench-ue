// Copyright CraftBench. All Rights Reserved.

#include "Tasks/t3-only-the-requested-district-enters-and-leaves-the-world/DistrictStreamingRuntime.h"

#include "Components/StaticMeshComponent.h"
#include "UObject/ConstructorHelpers.h"

ADistrictStreamRequest::ADistrictStreamRequest()
{
	PrimaryActorTick.bCanEverTick = false;
	Tags.Add(TEXT("DistrictStreamRequest"));
}

ADistrictStreamLoaderBase::ADistrictStreamLoaderBase()
{
	PrimaryActorTick.bCanEverTick = false;
	Tags.Add(TEXT("DistrictStreamLoader"));
}

void ADistrictStreamLoaderBase::LoadRequestedDistrict_Implementation(
	ADistrictStreamRequest*)
{
}

void ADistrictStreamLoaderBase::UnloadRequestedDistrict_Implementation()
{
}

ADistrictSectionMarker::ADistrictSectionMarker()
{
	PrimaryActorTick.bCanEverTick = false;
	Tags.Add(TEXT("DistrictSectionMarker"));
	VisibleMarker = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("VisibleMarker"));
	SetRootComponent(VisibleMarker);
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(
		TEXT("/Engine/BasicShapes/Cube.Cube"));
	if (Cube.Succeeded())
	{
		VisibleMarker->SetStaticMesh(Cube.Object);
	}
}

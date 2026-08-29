// Copyright CraftBench. All Rights Reserved.
//
// AColorCycleActor — see header. Ticking is disabled here; whether the
// solution needs it is the agent's choice.

#include "ColorCycleActor.h"

#include "Components/StaticMeshComponent.h"
#include "UObject/ConstructorHelpers.h"

AColorCycleActor::AColorCycleActor()
{
	PrimaryActorTick.bCanEverTick = false;

	DisplayMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("DisplayMesh"));
	SetRootComponent(DisplayMesh);
	DisplayMesh->SetMobility(EComponentMobility::Movable);
	DisplayMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeFinder(TEXT("/Engine/BasicShapes/Cube"));
	if (CubeFinder.Succeeded())
	{
		DisplayMesh->SetStaticMesh(CubeFinder.Object);
	}

	Tags.Add(FName("ColorCycle"));
}

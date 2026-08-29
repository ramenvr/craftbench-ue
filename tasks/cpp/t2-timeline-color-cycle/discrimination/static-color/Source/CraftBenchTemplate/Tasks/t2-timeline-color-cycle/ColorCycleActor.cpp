// Copyright CraftBench. All Rights Reserved.
//
// Discrimination variant "static-color" — see header.

#include "ColorCycleActor.h"

#include "Components/StaticMeshComponent.h"
#include "Materials/MaterialInstanceDynamic.h"
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

void AColorCycleActor::BeginPlay()
{
	Super::BeginPlay();
	CycleMid = DisplayMesh->CreateAndSetMaterialInstanceDynamic(0);
	if (CycleMid)
	{
		// Set once, never again — the parameter is readable but static.
		CycleMid->SetVectorParameterValue(TEXT("CycleColor"), FLinearColor(0.f, 1.f, 0.f, 1.f));
		CycleMid->SetVectorParameterValue(TEXT("Color"), FLinearColor(0.f, 1.f, 0.f, 1.f));
	}
}

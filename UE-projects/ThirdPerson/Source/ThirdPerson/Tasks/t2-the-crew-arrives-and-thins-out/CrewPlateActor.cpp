// Copyright CraftBench. All Rights Reserved.

#include "CrewPlateActor.h"

#include "Components/BoxComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/Pawn.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

ACrewPlateActor::ACrewPlateActor()
{
	// Ticks only to ride its own lamp up and down. It decides nothing.
	PrimaryActorTick.bCanEverTick = true;

	// The region is the root so the plate's position IS the region's position:
	// nothing can drift between what you stand on and what notices you. Left at unit
	// scale on purpose -- a scaled root would multiply the region's extent as well as
	// every child's offset. No relative offset either: a root component's relative
	// location is the actor's own, and the deck's saved transform overrides it, so an
	// offset written here would be a comment that does nothing. The region is generous
	// in Z instead, so it reaches a standing body wherever the deck puts the plate.
	PlateVolume = CreateDefaultSubobject<UBoxComponent>(TEXT("PlateVolume"));
	SetRootComponent(PlateVolume);
	PlateVolume->SetBoxExtent(FVector(200.0f, 200.0f, 90.0f));
	PlateVolume->SetCollisionProfileName(TEXT("OverlapAllDynamic"));
	PlateVolume->SetGenerateOverlapEvents(true);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube.Cube"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> SphereMesh(
		TEXT("/Engine/BasicShapes/Sphere.Sphere"));

	// 400 x 400 x 10 cm, standing 10 cm proud of the deck so it is plainly a thing you
	// step onto. Oversized on purpose: the pad is walked onto, and a pad you can miss
	// is a pad that reports the wrong moment.
	Pad = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Pad"));
	Pad->SetupAttachment(PlateVolume);
	Pad->SetRelativeLocation(FVector(0.0f, 0.0f, 5.0f));
	Pad->SetRelativeScale3D(FVector(4.0f, 4.0f, 0.1f));
	Pad->SetCollisionProfileName(TEXT("BlockAll"));
	if (CubeMesh.Succeeded())
	{
		Pad->SetStaticMesh(CubeMesh.Object);
	}

	Lamp = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Lamp"));
	Lamp->SetupAttachment(PlateVolume);
	Lamp->SetRelativeLocation(FVector(0.0f, 0.0f, 120.0f));
	Lamp->SetRelativeScale3D(FVector(0.4f, 0.4f, 0.4f));
	Lamp->SetCollisionProfileName(TEXT("NoCollision"));
	Lamp->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	if (SphereMesh.Succeeded())
	{
		Lamp->SetStaticMesh(SphereMesh.Object);
	}

	Tags.Add(FName(TEXT("CrewPlate")));
}

void ACrewPlateActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	// Presentation only: the lamp rides up while somebody is standing here, so a
	// person watching can see the plate register without reading any numbers.
	// Nothing about a watch is decided here.
	if (Lamp != nullptr)
	{
		Lamp->SetRelativeLocation(
			FVector(0.0f, 0.0f, IsSomebodyStandingHere() ? 190.0f : 120.0f));
	}
}

bool ACrewPlateActor::IsSomebodyStandingHere() const
{
	if (PlateVolume == nullptr)
	{
		return false;
	}
	TArray<AActor*> Standing;
	PlateVolume->GetOverlappingActors(Standing, APawn::StaticClass());
	return Standing.Num() > 0;
}

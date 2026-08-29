// Copyright CraftBench. All Rights Reserved.

#include "ContactPlateActor.h"

#include "Components/BoxComponent.h"
#include "Components/StaticMeshComponent.h"
#include "GameFramework/Pawn.h"
#include "UObject/ConstructorHelpers.h"

AContactPlateActor::AContactPlateActor()
{
	PrimaryActorTick.bCanEverTick = true;

	// The region is the root so the plate's position IS the region's position:
	// nothing can drift between what you stand on and what notices you.
	PlateVolume = CreateDefaultSubobject<UBoxComponent>(TEXT("PlateVolume"));
	SetRootComponent(PlateVolume);
	PlateVolume->SetBoxExtent(FVector(100.0f, 100.0f, 30.0f));
	PlateVolume->SetRelativeLocation(FVector(0.0f, 0.0f, 30.0f));
	PlateVolume->SetCollisionProfileName(TEXT("OverlapAllDynamic"));
	PlateVolume->SetGenerateOverlapEvents(true);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube.Cube"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> SphereMesh(
		TEXT("/Engine/BasicShapes/Sphere.Sphere"));

	// 200 x 200 x 10 cm, sitting just above the floor.
	Pad = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Pad"));
	Pad->SetupAttachment(PlateVolume);
	Pad->SetRelativeLocation(FVector(0.0f, 0.0f, -25.0f));
	Pad->SetRelativeScale3D(FVector(2.0f, 2.0f, 0.1f));
	Pad->SetCollisionProfileName(TEXT("BlockAll"));
	if (CubeMesh.Succeeded())
	{
		Pad->SetStaticMesh(CubeMesh.Object);
	}

	Lamp = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Lamp"));
	Lamp->SetupAttachment(PlateVolume);
	Lamp->SetRelativeLocation(FVector(0.0f, 0.0f, 120.0f));
	Lamp->SetRelativeScale3D(FVector(0.3f, 0.3f, 0.3f));
	Lamp->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	if (SphereMesh.Succeeded())
	{
		Lamp->SetStaticMesh(SphereMesh.Object);
	}

	Tags.Add(FName(TEXT("ContactPlate")));
}

void AContactPlateActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	// Presentation only: the lamp rides up while somebody is standing here, so a
	// person watching can see the plate register without reading any numbers.
	// Nothing about the door is decided here.
	if (PlateVolume == nullptr || Lamp == nullptr)
	{
		return;
	}

	// Presentation only: the lamp rides up while somebody is standing here, so a
	// person watching can see the plate register without reading any numbers.
	// Nothing about the door is decided here.
	TArray<AActor*> Standing;
	PlateVolume->GetOverlappingActors(Standing, APawn::StaticClass());
	Lamp->SetRelativeLocation(FVector(0.0f, 0.0f, Standing.Num() > 0 ? 150.0f : 120.0f));
}

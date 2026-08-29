// Copyright CraftBench. All Rights Reserved.

#include "CrewBerthActor.h"

#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

ACrewBerthActor::ACrewBerthActor()
{
	// Paint decides nothing.
	PrimaryActorTick.bCanEverTick = false;

	// A bare scene root at unit scale; the paint is scaled, the root never is.
	USceneComponent* const Pivot = CreateDefaultSubobject<USceneComponent>(TEXT("Pivot"));
	SetRootComponent(Pivot);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube.Cube"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Look(
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"));

	// A 300 x 300 cm square lying 2 cm proud of the deck.
	Paint = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Paint"));
	Paint->SetupAttachment(Pivot);
	Paint->SetRelativeLocation(FVector(0.0f, 0.0f, 1.0f));
	Paint->SetRelativeScale3D(FVector(3.0f, 3.0f, 0.02f));
	if (CubeMesh.Succeeded())
	{
		Paint->SetStaticMesh(CubeMesh.Object);
	}
	if (Look.Succeeded())
	{
		Paint->SetMaterial(0, Look.Object);
	}
	Paint->SetCollisionProfileName(TEXT("NoCollision"));
	Paint->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	PaintedNumber = CreateDefaultSubobject<UTextRenderComponent>(TEXT("PaintedNumber"));
	PaintedNumber->SetupAttachment(Pivot);
	PaintedNumber->SetRelativeLocation(FVector(0.0f, 0.0f, 4.0f));
	// Laid flat, reading up off the deck.
	PaintedNumber->SetRelativeRotation(FRotator(90.0f, 0.0f, 0.0f));
	PaintedNumber->SetHorizontalAlignment(EHTA_Center);
	PaintedNumber->SetWorldSize(90.0f);
	PaintedNumber->SetTextRenderColor(FColor(230, 230, 230));

	Tags.Add(FName(TEXT("CrewBerth")));
}

void ACrewBerthActor::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);

	if (PaintedNumber != nullptr)
	{
		PaintedNumber->SetText(FText::FromString(FString::FromInt(SpotNumber)));
	}
}

FVector ACrewBerthActor::GetStandLocation() const
{
	// Feet on the paint. A hand's own body sits above its actor location, so this is
	// the actor location a hand is put down at, not the top of its head.
	return GetActorLocation();
}

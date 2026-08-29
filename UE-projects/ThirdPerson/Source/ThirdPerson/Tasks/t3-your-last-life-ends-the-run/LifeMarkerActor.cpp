// Copyright CraftBench. All Rights Reserved.

#include "LifeMarkerActor.h"

#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

ALifeMarkerActor::ALifeMarkerActor()
{
	// It ticks only so the paint can never fall behind the number.
	PrimaryActorTick.bCanEverTick = true;

	// A plain, UNSCALED root, so everything hung off it is the size it says it is
	// rather than the size the disc's own flattening would make it.
	USceneComponent* const Pivot = CreateDefaultSubobject<USceneComponent>(TEXT("Pivot"));
	SetRootComponent(Pivot);

	DiscMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("DiscMesh"));
	DiscMesh->SetupAttachment(Pivot);
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CylinderMesh(
		TEXT("/Engine/BasicShapes/Cylinder"));
	if (CylinderMesh.Succeeded())
	{
		DiscMesh->SetStaticMesh(CylinderMesh.Object);
	}
	// 300 cm across and 6 cm proud of the floor: a disc you walk over, not a step.
	DiscMesh->SetRelativeScale3D(FVector(3.0f, 3.0f, 0.06f));
	DiscMesh->SetRelativeLocation(FVector(0.0f, 0.0f, 3.0f));
	DiscMesh->SetMobility(EComponentMobility::Static);
	DiscMesh->SetCollisionProfileName(TEXT("NoCollision"));
	DiscMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> DiscLook(
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_Round"));
	if (DiscLook.Succeeded())
	{
		DiscMesh->SetMaterial(0, DiscLook.Object);
	}

	PaintedNumber = CreateDefaultSubobject<UTextRenderComponent>(TEXT("PaintedNumber"));
	PaintedNumber->SetupAttachment(Pivot);
	PaintedNumber->SetRelativeLocation(FVector(0.0f, 0.0f, 12.0f));
	PaintedNumber->SetRelativeRotation(FRotator(90.0f, 0.0f, 0.0f));
	PaintedNumber->SetHorizontalAlignment(EHTA_Center);
	PaintedNumber->SetWorldSize(180.0f);
	PaintedNumber->SetTextRenderColor(FColor(255, 248, 210));

	Tags.Add(FName("LifeMarker"));
}

void ALifeMarkerActor::BeginPlay()
{
	Super::BeginPlay();
	RefreshPaint();
}

void ALifeMarkerActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	RefreshPaint();
}

void ALifeMarkerActor::RefreshPaint()
{
	if (PaintedNumber == nullptr || PaintedShown == PaintedLives)
	{
		return;
	}
	PaintedShown = PaintedLives;
	PaintedNumber->SetText(FText::FromString(FString::Printf(TEXT("%d"), PaintedLives)));
}

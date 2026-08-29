// Copyright CraftBench. All Rights Reserved.

#include "FinishDiscActor.h"

#include "Components/SceneComponent.h"
#include "Components/SphereComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

AFinishDiscActor::AFinishDiscActor()
{
	// It ticks only so the paint can never fall behind the number.
	PrimaryActorTick.bCanEverTick = true;

	// A plain, UNSCALED root, so the disc's own flattening never reaches the reach.
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
	DiscMesh->SetRelativeLocation(FVector(0.0f, 0.0f, 3.0f));
	// Movable because the disc is re-sized from DiscRadiusUu when the level places
	// it; a Static component complains when anything moves or scales it.
	DiscMesh->SetMobility(EComponentMobility::Movable);
	DiscMesh->SetCollisionProfileName(TEXT("NoCollision"));
	DiscMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> DiscLook(
		TEXT("/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT"));
	if (DiscLook.Succeeded())
	{
		DiscMesh->SetMaterial(0, DiscLook.Object);
	}

	DiscVolume = CreateDefaultSubobject<USphereComponent>(TEXT("DiscVolume"));
	DiscVolume->SetupAttachment(Pivot);
	DiscVolume->SetRelativeLocation(FVector(0.0f, 0.0f, 60.0f));
	// Noticed, never blocking.
	DiscVolume->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	DiscVolume->SetCollisionResponseToAllChannels(ECR_Overlap);
	DiscVolume->SetGenerateOverlapEvents(true);

	DemandNumber = CreateDefaultSubobject<UTextRenderComponent>(TEXT("DemandNumber"));
	DemandNumber->SetupAttachment(Pivot);
	DemandNumber->SetRelativeLocation(FVector(0.0f, 0.0f, 14.0f));
	DemandNumber->SetRelativeRotation(FRotator(90.0f, 0.0f, 0.0f));
	DemandNumber->SetHorizontalAlignment(EHTA_Center);
	DemandNumber->SetWorldSize(300.0f);
	DemandNumber->SetTextRenderColor(FColor(255, 236, 190));

	Tags.Add(FName("FinishDisc"));
}

void AFinishDiscActor::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);

	// The painted disc and the reach are one number, so what a person walks onto and
	// what the disc says are the same thing.
	if (DiscVolume != nullptr)
	{
		DiscVolume->SetSphereRadius(DiscRadiusUu, false);
	}
	if (DiscMesh != nullptr)
	{
		// The engine cylinder is 100 cm across, so a radius of R needs a scale of
		// R / 50 in the plane. Kept 6 cm proud of the floor.
		const float PlaneScale = DiscRadiusUu / 50.0f;
		DiscMesh->SetRelativeScale3D(FVector(PlaneScale, PlaneScale, 0.06f));
	}
}

void AFinishDiscActor::BeginPlay()
{
	Super::BeginPlay();
	RefreshPaint();
}

void AFinishDiscActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	RefreshPaint();
}

void AFinishDiscActor::RefreshPaint()
{
	if (DemandNumber == nullptr || DemandShown == DemandedLives)
	{
		return;
	}
	DemandShown = DemandedLives;
	DemandNumber->SetText(FText::FromString(FString::Printf(TEXT("%d"), DemandedLives)));
}

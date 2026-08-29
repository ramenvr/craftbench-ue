// Copyright CraftBench. All Rights Reserved.

#include "CallMarkActor.h"

#include "Components/BoxComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

ACallMarkActor::ACallMarkActor()
{
	// Nothing to tick as shipped: a mark decides nothing.
	PrimaryActorTick.bCanEverTick = false;

	// The region is the root so the mark's position IS the region's position: nothing
	// can drift between what you stand on and what notices you. It is left unscaled,
	// because a scaled root would multiply every child's offset AND its bounds.
	StepVolume = CreateDefaultSubobject<UBoxComponent>(TEXT("StepVolume"));
	SetRootComponent(StepVolume);
	StepVolume->SetBoxExtent(FVector(110.0f, 110.0f, 45.0f));
	StepVolume->SetRelativeLocation(FVector(0.0f, 0.0f, 45.0f));
	StepVolume->SetCollisionProfileName(TEXT("OverlapAllDynamic"));
	StepVolume->SetGenerateOverlapEvents(true);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube.Cube"));

	// 220 x 220 x 10 cm, set into the floor so its top is barely proud of it.
	Pad = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Pad"));
	Pad->SetupAttachment(StepVolume);
	Pad->SetRelativeLocation(FVector(0.0f, 0.0f, -45.0f));
	Pad->SetRelativeScale3D(FVector(2.2f, 2.2f, 0.1f));
	Pad->SetCollisionProfileName(TEXT("BlockAll"));
	if (CubeMesh.Succeeded())
	{
		Pad->SetStaticMesh(CubeMesh.Object);
	}

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Look(
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_Round"));
	if (Look.Succeeded())
	{
		Pad->SetMaterial(0, Look.Object);
	}

	Label = CreateDefaultSubobject<UTextRenderComponent>(TEXT("Label"));
	Label->SetupAttachment(StepVolume);
	Label->SetRelativeLocation(FVector(0.0f, 0.0f, 175.0f));
	Label->SetRelativeRotation(FRotator(0.0f, 180.0f, 0.0f));
	Label->SetHorizontalAlignment(EHTA_Center);
	Label->SetWorldSize(110.0f);
	Label->SetTextRenderColor(FColor(255, 226, 140));
	Label->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Label->SetText(FText::GetEmpty());

	Tags.Add(FName(TEXT("CallMark")));
}

void ACallMarkActor::BeginPlay()
{
	Super::BeginPlay();

	// Whatever name the level left on this mark is the name it is showing from the
	// first frame -- and it is the name a person reads off the floating label.
	SetCalledWingName(CalledWingName);
}

void ACallMarkActor::SetCalledWingName(FName InWingName)
{
	CalledWingName = InWingName;

	if (Label != nullptr)
	{
		Label->SetText(CalledWingName.IsNone()
			? FText::GetEmpty()
			: FText::FromString(CalledWingName.ToString().ToUpper()));
	}
}

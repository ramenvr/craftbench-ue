// Copyright CraftBench. All Rights Reserved.

#include "WeightPlateActor.h"

#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	// The engine cube is 100 cm: a 900 x 900 x 20 cm pad.
	const FVector kPadScale(9.0f, 9.0f, 0.2f);
	const TCHAR* const kPadMaterial =
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray");
}

AWeightPlateActor::AWeightPlateActor()
{
	// Ticks for the readout only. Nothing here decides anything.
	PrimaryActorTick.bCanEverTick = true;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube"));

	Pad = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Pad"));
	SetRootComponent(Pad);
	if (CubeMesh.Succeeded())
	{
		Pad->SetStaticMesh(CubeMesh.Object);
	}
	Pad->SetRelativeScale3D(kPadScale);
	Pad->SetMobility(EComponentMobility::Movable);
	Pad->SetCollisionProfileName(TEXT("BlockAll"));

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Look(kPadMaterial);
	if (Look.Succeeded())
	{
		Pad->SetMaterial(0, Look.Object);
	}

	HoldLabel = CreateDefaultSubobject<UTextRenderComponent>(TEXT("HoldLabel"));
	HoldLabel->SetupAttachment(Pad);
	// Divided back out of the pad's scale so the sign stands 200 cm over the pad
	// however the pad is scaled.
	HoldLabel->SetRelativeLocation(FVector(0.0f, 0.0f, 200.0f / kPadScale.Z));
	HoldLabel->SetRelativeScale3D(FVector(1.0f / kPadScale.X, 1.0f / kPadScale.Y,
		1.0f / kPadScale.Z));
	HoldLabel->SetHorizontalAlignment(EHTA_Center);
	HoldLabel->SetWorldSize(70.0f);
	HoldLabel->SetTextRenderColor(FColor(150, 220, 255));
	HoldLabel->SetText(FText::FromString(TEXT("holds from")));
	HoldLabel->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	HoldLabel->SetUsingAbsoluteRotation(true);

	Tags.Add(FName(TEXT("WeightPlate")));
}

void AWeightPlateActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (HoldLabel == nullptr)
	{
		return;
	}
	// Derived from the property every frame, so a re-priced plate repaints itself.
	HoldLabel->SetText(FText::FromString(
		FString::Printf(TEXT("holds from %.0f kg"), MinimumHoldKg)));
	HoldLabel->SetWorldRotation(FRotator(0.0, 90.0, 0.0));
}

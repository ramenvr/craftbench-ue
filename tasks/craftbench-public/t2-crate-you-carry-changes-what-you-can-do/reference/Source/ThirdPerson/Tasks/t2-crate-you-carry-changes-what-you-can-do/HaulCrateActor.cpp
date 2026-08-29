// Copyright CraftBench. All Rights Reserved.

#include "HaulCrateActor.h"

#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	// The engine cube is 100 cm; 0.8 makes the 80 cm box the yard is measured in.
	constexpr float kCrateScale = 0.8f;
	const TCHAR* const kCrateMaterial =
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark");
}

AHaulCrateActor::AHaulCrateActor()
{
	// Ticks for the readout only. Nothing here decides anything.
	PrimaryActorTick.bCanEverTick = true;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube"));

	Body = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Body"));
	SetRootComponent(Body);
	if (CubeMesh.Succeeded())
	{
		Body->SetStaticMesh(CubeMesh.Object);
	}
	Body->SetRelativeScale3D(FVector(kCrateScale, kCrateScale, kCrateScale));
	Body->SetMobility(EComponentMobility::Movable);
	Body->SetCollisionProfileName(TEXT("BlockAll"));

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Look(kCrateMaterial);
	if (Look.Succeeded())
	{
		Body->SetMaterial(0, Look.Object);
	}

	WeightLabel = CreateDefaultSubobject<UTextRenderComponent>(TEXT("WeightLabel"));
	WeightLabel->SetupAttachment(Body);
	// Divided back out of the body's scale so the label sits 70 cm above the lid
	// whatever the box is scaled to.
	WeightLabel->SetRelativeLocation(FVector(0.0f, 0.0f, 110.0f / kCrateScale));
	WeightLabel->SetRelativeScale3D(FVector(1.0f / kCrateScale, 1.0f / kCrateScale,
		1.0f / kCrateScale));
	WeightLabel->SetHorizontalAlignment(EHTA_Center);
	WeightLabel->SetWorldSize(46.0f);
	WeightLabel->SetTextRenderColor(FColor(255, 226, 120));
	WeightLabel->SetText(FText::FromString(TEXT("kg")));
	WeightLabel->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	// Absolute rotation so the number stays readable from the camera's side while
	// the crate is carried around and turned.
	WeightLabel->SetUsingAbsoluteRotation(true);

	Tags.Add(FName(TEXT("HaulCrate")));
}

void AHaulCrateActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (WeightLabel == nullptr)
	{
		return;
	}
	// Derived from the property every frame rather than written once, so a
	// re-priced crate repaints itself and the picture never lies about the grade.
	WeightLabel->SetText(FText::FromString(
		FString::Printf(TEXT("%.0f kg"), MassKg)));
	WeightLabel->SetWorldRotation(FRotator(0.0, 90.0, 0.0));
}

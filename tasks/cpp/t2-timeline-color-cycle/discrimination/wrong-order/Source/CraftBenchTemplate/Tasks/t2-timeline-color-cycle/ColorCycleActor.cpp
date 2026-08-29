// Copyright CraftBench. All Rights Reserved.
//
// Discrimination variant "wrong-order" — see header. Identical to the
// reference except the anchor sequence: green -> RED -> BLUE.

#include "ColorCycleActor.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/World.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	// The one delta from the reference: red and blue are swapped.
	const FLinearColor KAnchors[3] = {
		FLinearColor(0.f, 1.f, 0.f, 1.f),  // green
		FLinearColor(1.f, 0.f, 0.f, 1.f),  // RED (should be blue)
		FLinearColor(0.f, 0.f, 1.f, 1.f),  // BLUE (should be red)
	};
}

AColorCycleActor::AColorCycleActor()
{
	PrimaryActorTick.bCanEverTick = true;

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
		CycleMid->SetVectorParameterValue(TEXT("CycleColor"), KAnchors[0]);
		CycleMid->SetVectorParameterValue(TEXT("Color"), KAnchors[0]);
	}
}

void AColorCycleActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (!CycleMid || CyclePeriod <= 0.f)
	{
		return;
	}
	const double Phase = FMath::Fmod(GetWorld()->GetTimeSeconds(), (double)CyclePeriod) / CyclePeriod;
	const float Scaled = (float)Phase * 3.f;
	const int32 Segment = FMath::Clamp(FMath::FloorToInt32(Scaled), 0, 2);
	const float Alpha = Scaled - (float)Segment;
	const FLinearColor Color = FMath::Lerp(
		KAnchors[Segment], KAnchors[(Segment + 1) % 3], Alpha);
	CycleMid->SetVectorParameterValue(TEXT("CycleColor"), Color);
	CycleMid->SetVectorParameterValue(TEXT("Color"), Color);
}

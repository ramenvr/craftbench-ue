// Copyright CraftBench. All Rights Reserved.
//
// Reference solution for task t2-timeline-color-cycle — see header.

#include "ColorCycleActor.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/World.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	const FLinearColor KAnchors[3] = {
		FLinearColor(0.f, 1.f, 0.f, 1.f),  // green (cycle start)
		FLinearColor(0.f, 0.f, 1.f, 1.f),  // blue  (one third in)
		FLinearColor(1.f, 0.f, 0.f, 1.f),  // red   (two thirds in)
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
		// CycleColor is the task's readable contract; "Color" is the engine
		// basic-shape material's own tint parameter, so the cube VISIBLY
		// matches what the contract reports.
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

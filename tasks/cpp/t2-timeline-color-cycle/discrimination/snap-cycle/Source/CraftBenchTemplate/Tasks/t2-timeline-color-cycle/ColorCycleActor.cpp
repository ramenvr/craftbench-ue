// Copyright CraftBench. All Rights Reserved.
//
// Discrimination variant "snap-cycle" — see header.

#include "ColorCycleActor.h"

#include "Components/StaticMeshComponent.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "TimerManager.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	const FLinearColor KAnchors[3] = {
		FLinearColor(0.f, 1.f, 0.f, 1.f),  // green
		FLinearColor(0.f, 0.f, 1.f, 1.f),  // blue
		FLinearColor(1.f, 0.f, 0.f, 1.f),  // red
	};
}

AColorCycleActor::AColorCycleActor()
{
	PrimaryActorTick.bCanEverTick = false;

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
		// Instant anchor flips on a 2s repeating timer — right order, right
		// period, zero blending.
		GetWorldTimerManager().SetTimer(
			SnapTimer, this, &AColorCycleActor::AdvanceAnchor, 2.0f, true);
	}
}

void AColorCycleActor::AdvanceAnchor()
{
	if (CycleMid)
	{
		AnchorIndex = (AnchorIndex + 1) % 3;
		CycleMid->SetVectorParameterValue(TEXT("CycleColor"), KAnchors[AnchorIndex]);
		CycleMid->SetVectorParameterValue(TEXT("Color"), KAnchors[AnchorIndex]);
	}
}

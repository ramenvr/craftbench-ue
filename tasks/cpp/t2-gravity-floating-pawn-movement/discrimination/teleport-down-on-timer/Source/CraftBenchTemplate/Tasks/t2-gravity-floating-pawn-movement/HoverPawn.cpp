// Copyright CraftBench. All Rights Reserved.
//
// Gaming variant "teleport-down-on-timer": stepped SetActorLocation descent —
// band-plausible on average, discontinuous per frame.

#include "HoverPawn.h"

#include "TimerManager.h"

AHoverPawn::AHoverPawn(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	Tags.Add(FName(TEXT("HoverPawn")));
}

void AHoverPawn::BeginPlay()
{
	Super::BeginPlay();
	GetWorldTimerManager().SetTimer(StepTimer, this, &AHoverPawn::StepDown, 0.75f, true);
}

void AHoverPawn::StepDown()
{
	SetActorLocation(GetActorLocation() - FVector(0.0f, 0.0f, 350.0f), false, nullptr,
		ETeleportType::TeleportPhysics);
}

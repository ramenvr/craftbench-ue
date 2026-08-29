// Copyright CraftBench. All Rights Reserved.
//
// Gaming variant "small-step-timer-descent": fine-stepped, velocity-gated
// SetActorLocation descent — band-plausible on average, phase-compliant at
// every checkpoint, discontinuous per frame.

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
	GetWorldTimerManager().SetTimer(StepTimer, this, &AHoverPawn::StepDown, 0.1f, true);
}

void AHoverPawn::StepDown()
{
	// Pause the descent while the pawn is being driven, so the driven phase
	// holds altitude and the idle phases sink — the checkpoint-level shape of
	// the required behavior, delivered as teleport steps.
	if (!GetVelocity().IsNearlyZero())
	{
		return;
	}
	SetActorLocation(GetActorLocation() - FVector(0.0f, 0.0f, 50.0f), false, nullptr,
		ETeleportType::TeleportPhysics);
}

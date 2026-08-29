// Copyright CraftBench. All Rights Reserved.
//
// Gaming variant "no-resume-after-input": a one-shot latch — the first
// pending input permanently disables the descent.

#include "GravityFloatingPawnMovement.h"

void UGravityFloatingPawnMovement::TickComponent(float DeltaTime, ELevelTick TickType,
	FActorComponentTickFunction* ThisTickFunction)
{
	const bool bHasPendingInput = !GetPendingInputVector().IsNearlyZero();

	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);

	if (!PawnOwner || !UpdatedComponent || ShouldSkipUpdate(DeltaTime))
	{
		return;
	}

	if (bHasPendingInput)
	{
		bEverHadInput = true;
	}
	if (bHasPendingInput || bEverHadInput)
	{
		SinkSpeed = 0.0f;
		return;
	}

	SinkSpeed = FMath::Min(SinkSpeed + SinkAcceleration * DeltaTime, MaxSinkSpeed);
	const FVector Delta(0.0f, 0.0f, -SinkSpeed * DeltaTime);
	FHitResult Hit;
	SafeMoveUpdatedComponent(Delta, UpdatedComponent->GetComponentQuat(), true, Hit);
	if (Hit.IsValidBlockingHit())
	{
		SinkSpeed = 0.0f;
	}
}

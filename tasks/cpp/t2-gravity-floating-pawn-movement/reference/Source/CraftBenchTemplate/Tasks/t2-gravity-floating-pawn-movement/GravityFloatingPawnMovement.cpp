// Copyright CraftBench. All Rights Reserved.
//
// UGravityFloatingPawnMovement implementation (reference solution).
// The pending-input test happens BEFORE Super::TickComponent, because the
// stock component consumes the input vector during its move.

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
		// Attended: fly stock; forget any built-up descent.
		SinkSpeed = 0.0f;
		return;
	}

	// Unattended: ramp the descent smoothly up to the terminal rate and move
	// down with proper collision (SafeMove sweeps, so a floor stops us).
	SinkSpeed = FMath::Min(SinkSpeed + SinkAcceleration * DeltaTime, MaxSinkSpeed);
	const FVector Delta(0.0f, 0.0f, -SinkSpeed * DeltaTime);
	FHitResult Hit;
	SafeMoveUpdatedComponent(Delta, UpdatedComponent->GetComponentQuat(), true, Hit);
	if (Hit.IsValidBlockingHit())
	{
		SinkSpeed = 0.0f;
	}
}

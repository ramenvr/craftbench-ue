// Copyright CraftBench. All Rights Reserved.
//
// Gaming variant "sinks-while-driven": the pending-input branch is missing —
// the descent applies every tick, driven or not.

#include "GravityFloatingPawnMovement.h"

void UGravityFloatingPawnMovement::TickComponent(float DeltaTime, ELevelTick TickType,
	FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);

	if (!PawnOwner || !UpdatedComponent || ShouldSkipUpdate(DeltaTime))
	{
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

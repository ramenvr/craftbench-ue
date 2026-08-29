// Copyright CraftBench. All Rights Reserved.

#include "PredictedDashMovementComponent.h"

UPredictedDashMovementComponent::UPredictedDashMovementComponent() = default;

void UPredictedDashMovementComponent::RequestPredictedDash(
	const FVector& WorldDirection, const float Distance,
	const uint32 RequestNonce)
{
	// Intentionally empty baseline. Implement prediction in this component.
}

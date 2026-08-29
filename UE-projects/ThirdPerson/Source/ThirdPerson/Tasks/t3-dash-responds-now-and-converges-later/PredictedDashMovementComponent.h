// Copyright CraftBench. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "PredictedDashMovementComponent.generated.h"

/** Agent-editable movement surface. The baseline intentionally does no dash work. */
UCLASS(ClassGroup = Movement, meta = (BlueprintSpawnableComponent))
class THIRDPERSON_API UPredictedDashMovementComponent
	: public UCharacterMovementComponent
{
	GENERATED_BODY()

public:
	UPredictedDashMovementComponent();

	/** Supplied protected character calls this on its autonomous proxy. */
	void RequestPredictedDash(
		const FVector& WorldDirection, float Distance, uint32 RequestNonce);
};

// Copyright CraftBench. All Rights Reserved.
//
// UGravityFloatingPawnMovement — reference solution for task
// t2-gravity-floating-pawn-movement. A floating movement that sinks at a
// capped, smoothly ramped rate whenever no movement input is pending, and
// flies exactly like the stock component while input is applied.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/FloatingPawnMovement.h"
#include "GravityFloatingPawnMovement.generated.h"

UCLASS()
class CRAFTBENCHTEMPLATE_API UGravityFloatingPawnMovement : public UFloatingPawnMovement
{
	GENERATED_BODY()

public:
	virtual void TickComponent(float DeltaTime, ELevelTick TickType,
		FActorComponentTickFunction* ThisTickFunction) override;

protected:
	/** Downward acceleration applied while idle, uu/s^2. */
	UPROPERTY(EditAnywhere, Category = "Gravity")
	float SinkAcceleration = 980.0f;

	/** Terminal descent rate, uu/s (inside the required 150-800 band). */
	UPROPERTY(EditAnywhere, Category = "Gravity")
	float MaxSinkSpeed = 500.0f;

private:
	float SinkSpeed = 0.0f;
};

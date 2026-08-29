// Copyright CraftBench. All Rights Reserved.
//
// Gaming variant "no-resume-after-input" for
// t2-gravity-floating-pawn-movement: gravity works until the FIRST movement
// input, then a latch disables it permanently — the idle and driven phases
// both look correct. Expected to FAIL the third phase ("sinking does not
// resume after input ends").

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
	UPROPERTY(EditAnywhere, Category = "Gravity")
	float SinkAcceleration = 980.0f;

	UPROPERTY(EditAnywhere, Category = "Gravity")
	float MaxSinkSpeed = 500.0f;

private:
	float SinkSpeed = 0.0f;
	bool bEverHadInput = false;
};

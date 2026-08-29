// Copyright CraftBench. All Rights Reserved.
//
// Gaming variant "sinks-while-driven" for t2-gravity-floating-pawn-movement:
// gravity is applied UNCONDITIONALLY — the idle phase looks correct, but the
// pawn also loses height the whole time it is being driven. Expected to FAIL
// the driven-phase altitude-held gate ("the pawn sinks while movement is
// applied").

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
};

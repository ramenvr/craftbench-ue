// Copyright CraftBench. All Rights Reserved.
//
// Gaming variant "teleport-down-on-timer" for
// t2-gravity-floating-pawn-movement: the movement component is left stock; a
// repeating timer relocates the pawn downward in COARSE steps whose AVERAGE
// rate (350uu / 0.75s = ~467 uu/s) sits inside the disclosed 150-800 band,
// so any checkpoint-average gate would pass it. Expected to FAIL the
// per-frame continuity guard ("altitude changed by a discontinuous jump") at
// the first step (~t=0.75s). Its fine-stepped, velocity-gated sibling is
// small-step-timer-descent/.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/DefaultPawn.h"
#include "HoverPawn.generated.h"

UCLASS()
class CRAFTBENCHTEMPLATE_API AHoverPawn : public ADefaultPawn
{
	GENERATED_BODY()

public:
	AHoverPawn(const FObjectInitializer& ObjectInitializer);

protected:
	virtual void BeginPlay() override;

private:
	void StepDown();

	FTimerHandle StepTimer;
};

// Copyright CraftBench. All Rights Reserved.
//
// Gaming variant "small-step-timer-descent" for
// t2-gravity-floating-pawn-movement: the movement component is left stock; a
// fast repeating timer (0.1s) relocates the pawn down in SMALL steps (50uu —
// average 500 uu/s, inside the disclosed band) and pauses itself while the
// pawn is moving (velocity-gated), so the driven phase holds altitude and
// the resume phase restarts — every checkpoint-level gate reads correct.
// Expected to FAIL the tightened per-frame continuity guard (50uu in one
// frame vs the ~30uu cap) via "altitude changed by a discontinuous jump" at
// the first step that lands while the test is running (t <= ~0.6s).

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

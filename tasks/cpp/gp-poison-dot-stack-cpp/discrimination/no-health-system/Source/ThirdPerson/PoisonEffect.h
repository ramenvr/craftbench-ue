// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION for task gp-poison-dot-stack-cpp. A periodic, stacking,
// duration-limited GameplayEffect: subtracts Health every ~1s for ~5s, stacks up
// to 3 (AggregateByTarget), the per-tick magnitude scales ~proportionally with
// the stack count (UE 5.8's bFactorInStackCount on a plain -5 modifier -- no
// MMC; see the .cpp), and each application refreshes the duration + resets the
// period.

#pragma once

#include "CoreMinimal.h"
#include "GameplayEffect.h"
#include "PoisonEffect.generated.h"

UCLASS()
class UPoisonEffect : public UGameplayEffect
{
	GENERATED_BODY()

public:
	UPoisonEffect();
};

// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT (no-refresh) for task gp-poison-dot-stack-cpp: the
// reference GE with StackDurationRefreshPolicy = NeverRefresh — re-application
// adds a stack but the poison still expires ~5s after the FIRST application.
// Expected verdict: FAIL, by name, at the Leg C refresh gate
// ("re-application did not refresh the duration"). See PoisonEffect.cpp.

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

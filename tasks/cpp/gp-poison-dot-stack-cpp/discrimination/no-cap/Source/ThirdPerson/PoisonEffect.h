// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT (no-cap) for task gp-poison-dot-stack-cpp — also the
// Leg D calibration probe: the reference GE with StackLimitCount = 0 (no
// limit), so 4 applications drain ~4x the single-stack rate instead of the
// capped ~3x. Expected verdict: FAIL, by name, at the Leg D cap gate
// ("stack cap violated"). See PoisonEffect.cpp.

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

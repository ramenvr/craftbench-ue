// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION for task gp-heal-over-time-cpp. A periodic, duration-limited
// GameplayEffect that RESTORES Health: adds a fixed amount every ~1s for ~5s and
// then ends. The sign-flipped twin of gp-poison-dot-stack-cpp's UPoisonEffect,
// minus the stacking (this family's prompt says nothing about stacking, so the
// plain shape is the right one).
//
// It is deliberately NOT an instant restore (that rises once and then stays flat
// -- PIN.md section 3, AG-3) and deliberately NOT an infinite effect (that never
// stops -- AG-4).

#pragma once

#include "CoreMinimal.h"
#include "GameplayEffect.h"
#include "HealOverTimeEffect.generated.h"

UCLASS()
class UHealOverTimeEffect : public UGameplayEffect
{
	GENERATED_BODY()

public:
	UHealOverTimeEffect();
};

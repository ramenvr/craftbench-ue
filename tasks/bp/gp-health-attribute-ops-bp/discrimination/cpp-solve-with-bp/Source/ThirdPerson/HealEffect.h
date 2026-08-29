// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION for task gp-health-attribute-ops-cpp. The mirror of
// UDamageEffect: an INSTANT GameplayEffect that adds back exactly what one
// damage removed. Deliberately NOT "set Health to MaxHealth" -- that is the
// plausible-wrong solve PIN.md section 4 names, and it dies at HO-10.

#pragma once

#include "CoreMinimal.h"
#include "GameplayEffect.h"
#include "HealEffect.generated.h"

UCLASS()
class UHealEffect : public UGameplayEffect
{
	GENERATED_BODY()

public:
	UHealEffect();
};

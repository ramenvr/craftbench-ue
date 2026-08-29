// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION for task gp-health-attribute-ops-cpp. An INSTANT
// GameplayEffect that subtracts a fixed amount of Health once per application:
// the plain "one operation = one instant effect" recipe, same
// UGameplayEffect-subclass-configured-in-its-constructor shape as
// gp-poison-dot-stack-cpp's UPoisonEffect (which is the periodic variant of the
// same idea).

#pragma once

#include "CoreMinimal.h"
#include "GameplayEffect.h"
#include "DamageEffect.generated.h"

UCLASS()
class UDamageEffect : public UGameplayEffect
{
	GENERATED_BODY()

public:
	UDamageEffect();
};

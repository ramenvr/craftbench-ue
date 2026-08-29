// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION for task gp-heal-over-time-cpp. Tagged Ability.HealOverTime;
// on activation it applies the periodic restore GameplayEffect to the avatar and
// ends immediately (the EFFECT owns the duration, not the ability).
//
// Structurally identical to gp-poison-dot-stack-cpp's UPoisonAbility and
// gp-health-attribute-ops-cpp's UHealAbility -- the same "tag it, apply one
// effect to self, end" shape. That is deliberate: the axis this task grades is
// the effect's periodicity/duration and the attribute set's clamp, not the
// ability's structure.

#pragma once

#include "CoreMinimal.h"
#include "Abilities/GameplayAbility.h"
#include "HealOverTimeAbility.generated.h"

UCLASS()
class UHealOverTimeAbility : public UGameplayAbility
{
	GENERATED_BODY()

public:
	UHealOverTimeAbility();

	virtual void ActivateAbility(
		const FGameplayAbilitySpecHandle Handle,
		const FGameplayAbilityActorInfo* ActorInfo,
		const FGameplayAbilityActivationInfo ActivationInfo,
		const FGameplayEventData* TriggerEventData) override;
};

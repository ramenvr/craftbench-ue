// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION for task gp-health-attribute-ops-cpp. Tagged Ability.Heal;
// the exact mirror of UDamageAbility -- on activation it applies one instant
// heal GameplayEffect to the avatar and ends immediately.

#pragma once

#include "CoreMinimal.h"
#include "Abilities/GameplayAbility.h"
#include "HealAbility.generated.h"

UCLASS()
class UHealAbility : public UGameplayAbility
{
	GENERATED_BODY()

public:
	UHealAbility();

	virtual void ActivateAbility(
		const FGameplayAbilitySpecHandle Handle,
		const FGameplayAbilityActorInfo* ActorInfo,
		const FGameplayAbilityActivationInfo ActivationInfo,
		const FGameplayEventData* TriggerEventData) override;
};

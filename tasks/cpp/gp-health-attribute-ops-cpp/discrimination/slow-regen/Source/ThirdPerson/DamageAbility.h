// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION for task gp-health-attribute-ops-cpp. Tagged
// Ability.Damage; on activation it applies one instant damage GameplayEffect to
// the avatar and ends immediately. Nothing about it is periodic or persistent,
// so Health moves only on activation (HO-11).

#pragma once

#include "CoreMinimal.h"
#include "Abilities/GameplayAbility.h"
#include "DamageAbility.generated.h"

UCLASS()
class UDamageAbility : public UGameplayAbility
{
	GENERATED_BODY()

public:
	UDamageAbility();

	virtual void ActivateAbility(
		const FGameplayAbilitySpecHandle Handle,
		const FGameplayAbilityActorInfo* ActorInfo,
		const FGameplayAbilityActivationInfo ActivationInfo,
		const FGameplayEventData* TriggerEventData) override;
};

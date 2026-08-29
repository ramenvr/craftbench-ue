// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION for task gp-poison-dot-stack-cpp. Tagged Ability.Poison; on
// activation it applies one stack of the periodic poison GameplayEffect to the
// avatar. Re-activating adds another stack (up to the GE's cap) and refreshes it.

#pragma once

#include "CoreMinimal.h"
#include "Abilities/GameplayAbility.h"
#include "PoisonAbility.generated.h"

UCLASS()
class UPoisonAbility : public UGameplayAbility
{
	GENERATED_BODY()

public:
	UPoisonAbility();

	virtual void ActivateAbility(
		const FGameplayAbilitySpecHandle Handle,
		const FGameplayAbilityActorInfo* ActorInfo,
		const FGameplayAbilityActivationInfo ActivationInfo,
		const FGameplayEventData* TriggerEventData) override;
};

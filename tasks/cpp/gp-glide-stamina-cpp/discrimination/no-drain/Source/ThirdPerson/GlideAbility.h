// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT (no-drain) for task gp-glide-stamina-cpp -- the
// reference ability with the Power drain REMOVED (the ONE delta; anti-gaming
// note 3, "Never drains stamina (free glide)"). The ability is still granted,
// still activates on the Ability.Glide tag, and still caps the descent on the
// same timer at the same speed -- it simply never writes the Power attribute,
// so the glide is free and (because Power never reaches zero) never ends. The
// DrainPerTick member goes with the drain it existed for; GlideFallSpeed /
// TickInterval are unchanged.
// Expected verdict: FAIL, by name, at gate (4) -- "the Power resource did not
// drain while gliding (the glide consumed no stamina)". See GlideAbility.cpp.

#pragma once

#include "CoreMinimal.h"
#include "Abilities/GameplayAbility.h"
#include "Engine/TimerHandle.h"
#include "GlideAbility.generated.h"

class ACharacter;

UCLASS()
class UGlideAbility : public UGameplayAbility
{
	GENERATED_BODY()

public:
	UGlideAbility();

	virtual void ActivateAbility(
		const FGameplayAbilitySpecHandle Handle,
		const FGameplayAbilityActorInfo* ActorInfo,
		const FGameplayAbilityActivationInfo ActivationInfo,
		const FGameplayEventData* TriggerEventData) override;

	virtual void EndAbility(
		const FGameplayAbilitySpecHandle Handle,
		const FGameplayAbilityActorInfo* ActorInfo,
		const FGameplayAbilityActivationInfo ActivationInfo,
		bool bReplicateEndAbility,
		bool bWasCancelled) override;

private:
	UFUNCTION()
	void GlideTick();

	TWeakObjectPtr<ACharacter> GlideAvatar;
	FTimerHandle GlideTimer;

	// Glide tuning (reference values -- calibrated so the test discriminates).
	float GlideFallSpeed = 100.0f;  // cap descent at 100 cm/s while gliding (margin under the 0.6x bar)
	float TickInterval = 0.1f;      // 10 ticks/sec
};

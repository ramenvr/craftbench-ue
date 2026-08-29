// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT (no-slow) for task gp-glide-stamina-cpp -- the
// reference ability with the descent cap REMOVED (the ONE delta; anti-gaming
// note 2, "Teleport / no actual slow"). The ability is still granted, still
// activates on the Ability.Glide tag, and still drains Power on the same
// timer -- it simply never touches the avatar's velocity, so the "glide" is an
// unaided free fall. The GlideFallSpeed member goes with the clamp it existed
// for; DrainPerTick / TickInterval are unchanged.
// Expected verdict: FAIL, by name, at gate (3) -- "descent was not slowed by
// the glide: min glide |vZ|=... > 0.60 * free-fall(...) = ...".
// See GlideAbility.cpp.

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
	float DrainPerTick = 3.0f;      // Power spent per tick
	float TickInterval = 0.1f;      // 10 ticks/sec -> 30 Power empties in ~1 s
};

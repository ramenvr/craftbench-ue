// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION for task gp-glide-stamina-cpp (agent-writable runtime module).
// A GameplayAbility tagged Ability.Glide that, while active, caps the avatar's
// downward fall velocity (so it descends slowly) and drains the Power attribute
// on a repeating timer; when Power reaches 0 it stops capping (normal fall
// resumes) and ends. InstancedPerActor so the instance holds the timer + state.

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

	// Glide tuning (reference values — calibrated so the test discriminates).
	float GlideFallSpeed = 100.0f;  // cap descent at 100 cm/s while gliding (margin under the 0.6x bar)
	float DrainPerTick = 3.0f;      // Power spent per tick
	float TickInterval = 0.1f;      // 10 ticks/sec -> 30 Power empties in ~1 s
};

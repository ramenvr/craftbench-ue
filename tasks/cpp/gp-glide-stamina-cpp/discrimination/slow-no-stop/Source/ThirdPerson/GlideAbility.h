// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT (no-stop) for task gp-glide-stamina-cpp -- the
// reference ability with the stop-on-exhaustion branch REMOVED (the ONE delta;
// anti-gaming note 4, "Glide forever, ignore stamina"). The ability is still
// granted, still activates, still caps the descent and still drains Power to
// zero on the same timer -- it just never ends when the resource is gone, so
// the clamp holds for the rest of the schedule. Every tuning member is
// unchanged; the whole delta is the deleted `if (Next <= 0.0f) EndAbility(...)`
// block in GlideTick.
// Expected verdict: FAIL, by name, at gate (5) -- "Power was exhausted
// (min=0.0) but the descent did NOT speed back up in a ...s observation window
// (>= the 0.30s floor): final |vZ|=... is only 1.00x the glide speed ...".
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
	float GlideFallSpeed = 100.0f;  // cap descent at 100 cm/s while gliding (margin under the 0.6x bar)
	// SLOW drain: 1.0 per 0.1s tick = 10/s. From the verifier's PowerPreset of 30
	// that needs 3.0s, and the trigger fires at t=1.5 on a schedule whose last
	// checkpoint is t=4.1 -- so Power NEVER empties on its own inside the window.
	// That is the whole point of this variant: before the 2026-08-09 forced-
	// exhaustion change, gate (5) SKIPPED here and this file PASSED despite
	// never stopping the glide.
	float DrainPerTick = 1.0f;      // Power spent per tick (SLOW - see above)
	float TickInterval = 0.1f;      // 10 ticks/sec -> 30 Power would need ~3 s
};

// Reference solution — gp-dot-aoe-burn-cpp.
//
// An ability that creates a burning area at the character's location: for
// about five seconds, characters within about five meters lose Health once a
// second; characters outside are untouched. Mirrors the tier-1 reference
// idiom (glide's timer + SetNumericAttributeBase pattern), applied to OTHER
// characters' attribute sets rather than the caster's own.

#pragma once

#include "CoreMinimal.h"
#include "Abilities/GameplayAbility.h"
#include "AoeBurnAbility.generated.h"

UCLASS()
class THIRDPERSON_API UAoeBurnAbility : public UGameplayAbility
{
	GENERATED_BODY()

public:
	UAoeBurnAbility();

	virtual void ActivateAbility(
		const FGameplayAbilitySpecHandle Handle,
		const FGameplayAbilityActorInfo* ActorInfo,
		const FGameplayAbilityActivationInfo ActivationInfo,
		const FGameplayEventData* TriggerEventData) override;

	virtual void EndAbility(
		const FGameplayAbilitySpecHandle Handle,
		const FGameplayAbilityActorInfo* ActorInfo,
		const FGameplayAbilityActivationInfo ActivationInfo,
		bool bReplicateEndAbility, bool bWasCancelled) override;

protected:
	void BurnTick();

	/** Area radius around the activation point. ~5 m per the design brief. */
	float BurnRadius = 500.0f;

	/** Health removed from each character inside the area, per tick. */
	float BurnPerTick = 12.0f;  // CALIBRATION DELTA

	/** Tick cadence — about once per second. */
	float BurnPeriod = 1.0f;

	/** Set duration — the area stops burning after this. In the 4-7 s band. */
	float BurnDuration = 5.0f;

	/** Where the area was created (captured at activation — the area does not
	 *  follow the character; it is a place, not an aura). */
	FVector BurnCenter = FVector::ZeroVector;

	int32 TicksFired = 0;
	FTimerHandle BurnTimerHandle;
};

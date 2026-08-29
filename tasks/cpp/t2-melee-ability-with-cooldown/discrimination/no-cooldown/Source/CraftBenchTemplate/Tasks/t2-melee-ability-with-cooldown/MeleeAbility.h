// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION for task t2-melee-ability-with-cooldown. Tagged
// Ability.Melee; on activation it enforces a hand-rolled 2.0s cooldown gate
// (world game-time arithmetic — a refused trigger never re-arms the gate),
// damages every MeleeDummy-tagged target within reach and in front of the
// avatar, then ends.
//
// Why not a cooldown GameplayEffect: granting tags on a GE requires
// UTargetTagsGameplayEffectComponent, and FindOrAddComponent in a GE
// constructor is a guaranteed engine Fatal on UE 5.8 (NewObject inside a CDO
// constructor trips FObjectInitializer::AssertIfInConstructor at module
// load). The gate below is behaviorally identical and timing-deterministic.

#pragma once

#include "CoreMinimal.h"
#include "Abilities/GameplayAbility.h"
#include "MeleeAbility.generated.h"

UCLASS()
class UMeleeAbility : public UGameplayAbility
{
	GENERATED_BODY()

public:
	UMeleeAbility();

	virtual void ActivateAbility(
		const FGameplayAbilitySpecHandle Handle,
		const FGameplayAbilityActorInfo* ActorInfo,
		const FGameplayAbilityActivationInfo ActivationInfo,
		const FGameplayEventData* TriggerEventData) override;

	/** Strike tuning (defaults satisfy the task contract). */
	UPROPERTY(EditDefaultsOnly, Category = "Melee")
	float Reach = 250.f;

	UPROPERTY(EditDefaultsOnly, Category = "Melee")
	float Damage = 25.f;

	/** Cos of the max angle off the avatar's forward that still counts as
	 *  "directly in front" (0.5 = 60 degrees either side). */
	UPROPERTY(EditDefaultsOnly, Category = "Melee")
	float FacingCosine = 0.5f;

};

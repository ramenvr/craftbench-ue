// Copyright CraftBench. All Rights Reserved.

#include "HealOverTimeAbility.h"

#include "HealOverTimeEffect.h"
#include "CraftBenchGameplayTags.h"
#include "AbilitySystemComponent.h"

UHealOverTimeAbility::UHealOverTimeAbility()
{
	InstancingPolicy = EGameplayAbilityInstancingPolicy::InstancedPerActor;

	// The asset tag the game starts the effect by (NumGrantedAbilitiesWithTag /
	// TryActivateAbilitiesByTag). Ability.HealOverTime is this family's tag and is
	// distinct from Ability.Heal, which belongs to the one-shot heal family.
	FGameplayTagContainer Tags;
	Tags.AddTag(FCraftBenchGameplayTags::AbilityHealOverTime());
	SetAssetTags(Tags);
}

void UHealOverTimeAbility::ActivateAbility(
	const FGameplayAbilitySpecHandle Handle,
	const FGameplayAbilityActorInfo* ActorInfo,
	const FGameplayAbilityActivationInfo ActivationInfo,
	const FGameplayEventData* TriggerEventData)
{
	if (!CommitAbility(Handle, ActorInfo, ActivationInfo))
	{
		EndAbility(Handle, ActorInfo, ActivationInfo, /*bReplicate=*/true, /*bWasCancelled=*/true);
		return;
	}

	// One activation = one application of the periodic restore effect to self.
	// The ability does NOT hold itself open for the effect's lifetime, and no
	// cooldown effect is set: an InstancedPerActor ability that is still running
	// refuses its next activation (bRetriggerInstancedAbility defaults false), and
	// this ability is activated more than once across the verifier's schedule.
	if (UAbilitySystemComponent* ASC = GetAbilitySystemComponentFromActorInfo())
	{
		ASC->ApplyGameplayEffectToSelf(
			GetDefault<UHealOverTimeEffect>(), /*Level=*/1.0f, ASC->MakeEffectContext());
	}

	EndAbility(Handle, ActorInfo, ActivationInfo, /*bReplicate=*/true, /*bWasCancelled=*/false);
}

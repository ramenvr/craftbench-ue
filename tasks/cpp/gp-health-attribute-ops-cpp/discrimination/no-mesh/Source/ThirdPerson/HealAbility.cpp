// Copyright CraftBench. All Rights Reserved.

#include "HealAbility.h"

#include "HealEffect.h"
#include "CraftBenchGameplayTags.h"
#include "AbilitySystemComponent.h"

UHealAbility::UHealAbility()
{
	InstancingPolicy = EGameplayAbilityInstancingPolicy::InstancedPerActor;

	FGameplayTagContainer Tags;
	Tags.AddTag(FCraftBenchGameplayTags::AbilityHeal());
	SetAssetTags(Tags);
}

void UHealAbility::ActivateAbility(
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

	// One activation = one instant application = one fixed increase of Health.
	// NOT "restore to MaxHealth": the prompt fixes the per-application amount
	// and HO-10 compares it to what one damage removed.
	if (UAbilitySystemComponent* ASC = GetAbilitySystemComponentFromActorInfo())
	{
		ASC->ApplyGameplayEffectToSelf(
			GetDefault<UHealEffect>(), /*Level=*/1.0f, ASC->MakeEffectContext());
	}

	EndAbility(Handle, ActorInfo, ActivationInfo, /*bReplicate=*/true, /*bWasCancelled=*/false);
}

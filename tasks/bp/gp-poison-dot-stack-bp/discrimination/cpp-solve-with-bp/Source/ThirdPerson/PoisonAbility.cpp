// Copyright CraftBench. All Rights Reserved.

#include "PoisonAbility.h"

#include "PoisonEffect.h"
#include "CraftBenchGameplayTags.h"
#include "AbilitySystemComponent.h"

UPoisonAbility::UPoisonAbility()
{
	InstancingPolicy = EGameplayAbilityInstancingPolicy::InstancedPerActor;

	FGameplayTagContainer Tags;
	Tags.AddTag(FCraftBenchGameplayTags::AbilityPoison());
	SetAssetTags(Tags);
}

void UPoisonAbility::ActivateAbility(
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

	// Apply one stack of the periodic poison effect to self (re-activation stacks).
	if (UAbilitySystemComponent* ASC = GetAbilitySystemComponentFromActorInfo())
	{
		ASC->ApplyGameplayEffectToSelf(
			GetDefault<UPoisonEffect>(), /*Level=*/1.0f, ASC->MakeEffectContext());
	}

	EndAbility(Handle, ActorInfo, ActivationInfo, /*bReplicate=*/true, /*bWasCancelled=*/false);
}

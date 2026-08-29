// Copyright CraftBench. All Rights Reserved.

#include "DamageAbility.h"

#include "DamageEffect.h"
#include "CraftBenchGameplayTags.h"
#include "AbilitySystemComponent.h"

UDamageAbility::UDamageAbility()
{
	InstancingPolicy = EGameplayAbilityInstancingPolicy::InstancedPerActor;

	// The asset tag the fixture triggers on (NumGrantedAbilitiesWithTag /
	// TryActivateAbilitiesByTag). Ability.Damage is this family's
	// PreferredAbilityTag.
	FGameplayTagContainer Tags;
	Tags.AddTag(FCraftBenchGameplayTags::AbilityDamage());
	SetAssetTags(Tags);
}

void UDamageAbility::ActivateAbility(
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

	// One activation = one instant application = one fixed decrease of Health.
	if (UAbilitySystemComponent* ASC = GetAbilitySystemComponentFromActorInfo())
	{
		ASC->ApplyGameplayEffectToSelf(
			GetDefault<UDamageEffect>(), /*Level=*/1.0f, ASC->MakeEffectContext());
	}

	EndAbility(Handle, ActorInfo, ActivationInfo, /*bReplicate=*/true, /*bWasCancelled=*/false);
}

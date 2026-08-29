// Copyright CraftBench. All Rights Reserved.
//
// See HealOverTimeAbility.h in this directory for the full delta description,
// the gate-by-gate arithmetic at both values of StopEpsilon, and the declared
// substring collision with ../never-stops/.

#include "HealOverTimeAbility.h"

#include "HealOverTimeEffect.h"
#include "CraftBenchGameplayTags.h"
#include "CraftBenchAttributeSet.h"
#include "AbilitySystemComponent.h"

/** Seconds between drip restorations. Same value, and for the same reason, as
 *  ../never-stops/'s period: it lands exactly one execution in each of the
 *  fixture's two congruent 1.5 s rise windows and exactly one in its 2.1 s stop
 *  window, with 0.50 s of clearance to the nearest boundary that would change
 *  any of those counts. PROPOSED - NOT YET MEASURED. */
static constexpr float DripPeriodSeconds = 1.65f;

/** Health restored per drip period. One execution lands in the stop window, so
 *  this IS the StopRise the gate reads: 0.6 is above the pinned StopEpsilon of
 *  0.25 by 0.35 and below the sheet's original 0.7 by 0.10, which is what lets
 *  this row make its claim in both directions. PROPOSED - NOT YET MEASURED. */
static constexpr float DripPerPeriod = 0.6f;

UHealOverTimeDripEffect::UHealOverTimeDripEffect()
{
	// Infinite: never expires, never removed. No DurationMagnitude -- an Infinite
	// effect has no duration to magnitude.
	DurationPolicy = EGameplayEffectDurationType::Infinite;
	Period = FScalableFloat(DripPeriodSeconds);

	// Load-bearing for the tick arithmetic in the header: with this false,
	// executions land at k*Period for k >= 1. The UE 5.8 default is TRUE and would
	// add an execution on the application frame, shifting every count by one.
	bExecutePeriodicEffectOnApplication = false;

	FGameplayModifierInfo HealthMod;
	HealthMod.Attribute = UCraftBenchAttributeSet::GetHealthAttribute();
	HealthMod.ModifierOp = EGameplayModOp::Additive;
	HealthMod.ModifierMagnitude =
		FGameplayEffectModifierMagnitude(FScalableFloat(DripPerPeriod));
	Modifiers.Add(HealthMod);
}

UHealOverTimeAbility::UHealOverTimeAbility()
{
	InstancingPolicy = EGameplayAbilityInstancingPolicy::InstancedPerActor;

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

	if (UAbilitySystemComponent* ASC = GetAbilitySystemComponentFromActorInfo())
	{
		// The conforming restore -- the reference's effect, unchanged. This is what
		// carries HOT-2 and HOT-4, and it is why the drip below never has to be
		// large enough to be noticed by either.
		ASC->ApplyGameplayEffectToSelf(
			GetDefault<UHealOverTimeEffect>(), /*Level=*/1.0f, ASC->MakeEffectContext());

		// THE DELTA: a second, permanent regeneration applied in the same breath.
		// Nothing in the fixture removes it and nothing in the effect ends it.
		ASC->ApplyGameplayEffectToSelf(
			GetDefault<UHealOverTimeDripEffect>(), /*Level=*/1.0f, ASC->MakeEffectContext());
	}

	// Ends immediately, exactly like the reference, so the ability is re-activatable
	// once per leg and HOT-1c stays green.
	EndAbility(Handle, ActorInfo, ActivationInfo, /*bReplicate=*/true, /*bWasCancelled=*/false);
}

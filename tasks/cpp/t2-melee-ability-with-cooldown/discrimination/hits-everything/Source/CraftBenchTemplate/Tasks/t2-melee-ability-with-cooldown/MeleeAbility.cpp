// Copyright CraftBench. All Rights Reserved.

#include "MeleeAbility.h"

#include "CraftBenchGameplayTags.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/UnrealType.h"

UMeleeAbility::UMeleeAbility()
{
	InstancingPolicy = EGameplayAbilityInstancingPolicy::InstancedPerActor;

	FGameplayTagContainer AbilityTagContainer;
	AbilityTagContainer.AddTag(FCraftBenchGameplayTags::AbilityMelee());
	SetAssetTags(AbilityTagContainer);
}

void UMeleeAbility::ActivateAbility(
	const FGameplayAbilitySpecHandle Handle,
	const FGameplayAbilityActorInfo* ActorInfo,
	const FGameplayAbilityActivationInfo ActivationInfo,
	const FGameplayEventData* TriggerEventData)
{
	AActor* Avatar = GetAvatarActorFromActorInfo();
	if (Avatar == nullptr || !CommitAbility(Handle, ActorInfo, ActivationInfo))
	{
		EndAbility(Handle, ActorInfo, ActivationInfo, /*bReplicate=*/true, /*bWasCancelled=*/true);
		return;
	}

	// Hand-rolled cooldown gate: refuse while inside the window. A refused
	// trigger does NOT touch LastStrikeTime, so it never extends the window.
	const double Now = Avatar->GetWorld()->GetTimeSeconds();
	if (LastStrikeTime >= 0.0 && Now < LastStrikeTime + static_cast<double>(CooldownSeconds))
	{
		EndAbility(Handle, ActorInfo, ActivationInfo, /*bReplicate=*/true, /*bWasCancelled=*/true);
		return;
	}

	TArray<AActor*> Targets;
	UGameplayStatics::GetAllActorsWithTag(Avatar->GetWorld(), FName(TEXT("MeleeDummy")), Targets);
	for (AActor* Target : Targets)
	{
		// VARIANT hits-everything: no reach or facing filter — every tagged
		// target on the map is damaged. Models the area-nuke gaming shape
		// (anti-gaming note #3).
		// Damage via the disclosed Health contract (reflection keeps this
		// working for any tagged target carrying a float Health). Lands
		// immediately on activation — no wind-up.
		if (FFloatProperty* Prop = FindFProperty<FFloatProperty>(Target->GetClass(), TEXT("Health")))
		{
			const float Before = Prop->GetPropertyValue_InContainer(Target);
			const float After = Before - Damage;
			Prop->SetPropertyValue_InContainer(Target, After);
			UE_LOG(LogTemp, Display,
				TEXT("MeleeAbility: hit %s for %.0f (health %.0f -> %.0f)"),
				*Target->GetName(), Damage, Before, After);
		}
	}
	LastStrikeTime = Now; // arm the cooldown only on a LANDED strike

	EndAbility(Handle, ActorInfo, ActivationInfo, /*bReplicate=*/true, /*bWasCancelled=*/false);
}

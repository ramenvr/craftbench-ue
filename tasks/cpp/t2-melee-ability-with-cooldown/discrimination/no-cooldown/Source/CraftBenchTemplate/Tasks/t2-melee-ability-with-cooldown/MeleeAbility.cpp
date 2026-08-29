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

	// VARIANT no-cooldown: the gate is deleted — every trigger commits and
	// strikes. Models the spammable-melee gaming shape (anti-gaming note #2).

	const FVector Origin = Avatar->GetActorLocation();
	const FVector Forward = Avatar->GetActorForwardVector();

	TArray<AActor*> Targets;
	UGameplayStatics::GetAllActorsWithTag(Avatar->GetWorld(), FName(TEXT("MeleeDummy")), Targets);
	for (AActor* Target : Targets)
	{
		const FVector ToTarget = Target->GetActorLocation() - Origin;
		const float Distance = ToTarget.Size();
		if (Distance > Reach)
		{
			continue; // out of reach
		}
		const FVector Dir = ToTarget.GetSafeNormal();
		if (FVector::DotProduct(Forward, Dir) < FacingCosine)
		{
			continue; // not in front
		}
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

	EndAbility(Handle, ActorInfo, ActivationInfo, /*bReplicate=*/true, /*bWasCancelled=*/false);
}

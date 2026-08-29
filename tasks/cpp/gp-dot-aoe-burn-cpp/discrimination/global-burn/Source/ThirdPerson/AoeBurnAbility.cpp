// Reference solution — gp-dot-aoe-burn-cpp.

#include "AoeBurnAbility.h"

#include "AbilitySystemComponent.h"
#include "AbilitySystemInterface.h"
#include "CraftBenchAttributeSet.h"
#include "CraftBenchCharacter.h"
#include "CraftBenchGameplayTags.h"
#include "Kismet/GameplayStatics.h"
#include "TimerManager.h"

UAoeBurnAbility::UAoeBurnAbility()
{
	InstancingPolicy = EGameplayAbilityInstancingPolicy::InstancedPerActor;
	AbilityTags.AddTag(FCraftBenchGameplayTags::AbilityAoeBurn());
}

void UAoeBurnAbility::ActivateAbility(
	const FGameplayAbilitySpecHandle Handle,
	const FGameplayAbilityActorInfo* ActorInfo,
	const FGameplayAbilityActivationInfo ActivationInfo,
	const FGameplayEventData* TriggerEventData)
{
	if (!CommitAbility(Handle, ActorInfo, ActivationInfo))
	{
		EndAbility(Handle, ActorInfo, ActivationInfo, true, true);
		return;
	}

	const AActor* Avatar = GetAvatarActorFromActorInfo();
	UWorld* World = GetWorld();
	if (Avatar == nullptr || World == nullptr)
	{
		EndAbility(Handle, ActorInfo, ActivationInfo, true, true);
		return;
	}

	// The burning area is a PLACE, fixed where the ability was activated.
	BurnCenter = Avatar->GetActorLocation();
	TicksFired = 0;

	// First burn immediately, then once per second for the set duration.
	BurnTick();
	World->GetTimerManager().SetTimer(
		BurnTimerHandle, this, &UAoeBurnAbility::BurnTick, BurnPeriod, /*bLoop=*/true);
}

void UAoeBurnAbility::BurnTick()
{
	UWorld* World = GetWorld();
	const AActor* Avatar = GetAvatarActorFromActorInfo();
	if (World == nullptr)
	{
		return;
	}

	// Burn every OTHER character inside the area. Identity by the shared
	// character base + its ability-system interface — never by name.
	TArray<AActor*> Characters;
	UGameplayStatics::GetAllActorsOfClass(
		World, ACraftBenchCharacter::StaticClass(), Characters);
	for (AActor* Actor : Characters)
	{
		if (Actor == Avatar)
		{
			continue; // the caster stands in their own area unharmed
		}
		// VARIANT DELTA (global-burn): the distance test is gone — every
		// character in the world burns. One deletion. The near target's burn,
		// rate, total and stop are IDENTICAL to the reference, so this passes
		// every gate except AB-4.
		const IAbilitySystemInterface* AsInterface = Cast<IAbilitySystemInterface>(Actor);
		UAbilitySystemComponent* TargetASC =
			AsInterface ? AsInterface->GetAbilitySystemComponent() : nullptr;
		if (TargetASC == nullptr)
		{
			continue;
		}
		const float Current = TargetASC->GetNumericAttribute(
			UCraftBenchAttributeSet::GetHealthAttribute());
		TargetASC->SetNumericAttributeBase(
			UCraftBenchAttributeSet::GetHealthAttribute(), Current - BurnPerTick);
	}

	// Stop after the set duration: the immediate tick plus one per period.
	++TicksFired;
	if (TicksFired > FMath::RoundToInt32(BurnDuration / BurnPeriod))
	{
		EndAbility(GetCurrentAbilitySpecHandle(), GetCurrentActorInfo(),
			GetCurrentActivationInfo(), true, false);
	}
}

void UAoeBurnAbility::EndAbility(
	const FGameplayAbilitySpecHandle Handle,
	const FGameplayAbilityActorInfo* ActorInfo,
	const FGameplayAbilityActivationInfo ActivationInfo,
	bool bReplicateEndAbility, bool bWasCancelled)
{
	if (UWorld* World = GetWorld())
	{
		World->GetTimerManager().ClearTimer(BurnTimerHandle);
	}
	Super::EndAbility(Handle, ActorInfo, ActivationInfo, bReplicateEndAbility, bWasCancelled);
}

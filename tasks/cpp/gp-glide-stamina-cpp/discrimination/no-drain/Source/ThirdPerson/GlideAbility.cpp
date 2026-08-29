// Copyright CraftBench. All Rights Reserved.

#include "GlideAbility.h"

#include "CraftBenchGameplayTags.h"
#include "CraftBenchAttributeSet.h"
#include "AbilitySystemComponent.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Engine/World.h"
#include "TimerManager.h"

UGlideAbility::UGlideAbility()
{
	InstancingPolicy = EGameplayAbilityInstancingPolicy::InstancedPerActor;

	FGameplayTagContainer Tags;
	Tags.AddTag(FCraftBenchGameplayTags::AbilityGlide());
	SetAssetTags(Tags);
}

void UGlideAbility::ActivateAbility(
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

	if (ActorInfo != nullptr && ActorInfo->AvatarActor.IsValid())
	{
		if (ACharacter* Avatar = Cast<ACharacter>(ActorInfo->AvatarActor.Get()))
		{
			GlideAvatar = Avatar;
			if (UWorld* World = Avatar->GetWorld())
			{
				// Drive the glide on a repeating timer: cap fall speed + drain Power.
				// Do NOT EndAbility here -- the timer ends it when Power runs out.
				World->GetTimerManager().SetTimer(
					GlideTimer, this, &UGlideAbility::GlideTick, TickInterval, /*bLoop=*/true);
			}
		}
	}
}

void UGlideAbility::GlideTick()
{
	ACharacter* Avatar = GlideAvatar.Get();
	if (Avatar == nullptr)
	{
		return;
	}

	// Cap the descent: clamp downward velocity so the character falls slowly.
	// UNCHANGED from the reference -- the slow is real, so gate (3) still passes
	// and the FAIL lands on the stamina axis.
	if (UCharacterMovementComponent* CMC = Avatar->GetCharacterMovement())
	{
		if (CMC->Velocity.Z < -GlideFallSpeed)
		{
			CMC->Velocity.Z = -GlideFallSpeed;
		}
	}

	// ---- THE ONE DELTA (anti-gaming note 3: "free glide") ----
	// The reference spends stamina here and ends the ability when it runs out:
	//     const float Current = ASC->GetNumericAttribute(...GetPowerAttribute());
	//     const float Next = FMath::Max(0.0f, Current - DrainPerTick);
	//     ASC->SetNumericAttributeBase(...GetPowerAttribute(), Next);
	//     if (Next <= 0.0f) { EndAbility(...); }
	// This variant never writes Power. The glide therefore costs nothing and,
	// with no exhaustion to end it, keeps clamping for the rest of the schedule
	// -- but gate (4) fires before gate (5) is reached, so the named FAIL is the
	// no-stamina-cost one. (The ASC lookup went with the drain; the ability
	// system includes are kept so this file's include set still matches the
	// reference's.)
}

void UGlideAbility::EndAbility(
	const FGameplayAbilitySpecHandle Handle,
	const FGameplayAbilityActorInfo* ActorInfo,
	const FGameplayAbilityActivationInfo ActivationInfo,
	bool bReplicateEndAbility,
	bool bWasCancelled)
{
	if (GlideAvatar.IsValid())
	{
		if (UWorld* World = GlideAvatar->GetWorld())
		{
			World->GetTimerManager().ClearTimer(GlideTimer);
		}
	}
	Super::EndAbility(Handle, ActorInfo, ActivationInfo, bReplicateEndAbility, bWasCancelled);
}

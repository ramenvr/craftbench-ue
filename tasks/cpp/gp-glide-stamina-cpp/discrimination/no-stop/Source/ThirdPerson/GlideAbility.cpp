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
				World->GetTimerManager().SetTimer(
					GlideTimer, this, &UGlideAbility::GlideTick, TickInterval, /*bLoop=*/true);
			}
		}
	}
}

void UGlideAbility::GlideTick()
{
	ACharacter* Avatar = GlideAvatar.Get();
	UAbilitySystemComponent* ASC = GetAbilitySystemComponentFromActorInfo();
	if (Avatar == nullptr || ASC == nullptr)
	{
		return;
	}

	// Cap the descent: clamp downward velocity so the character falls slowly.
	// UNCHANGED from the reference.
	if (UCharacterMovementComponent* CMC = Avatar->GetCharacterMovement())
	{
		if (CMC->Velocity.Z < -GlideFallSpeed)
		{
			CMC->Velocity.Z = -GlideFallSpeed;
		}
	}

	// Drain the Power resource. UNCHANGED from the reference -- Power really does
	// reach 0 (FMath::Max floors it there), which is what ARMS gate (5).
	const float Current = ASC->GetNumericAttribute(UCraftBenchAttributeSet::GetPowerAttribute());
	const float Next = FMath::Max(0.0f, Current - DrainPerTick);
	ASC->SetNumericAttributeBase(UCraftBenchAttributeSet::GetPowerAttribute(), Next);

	// ---- THE ONE DELTA (anti-gaming note 4: "glide forever, ignore stamina") ----
	// The reference stops gliding the instant the resource is gone:
	//     if (Next <= 0.0f)
	//     {
	//         EndAbility(CurrentSpecHandle, CurrentActorInfo, CurrentActivationInfo,
	//             /*bReplicate=*/true, /*bWasCancelled=*/false);
	//     }
	// This variant omits that branch, so the timer keeps clamping the descent
	// long after Power hit zero. The clamp phase is a whole number of timer
	// periods away from every post-trigger checkpoint (0.1s timer; checkpoints
	// 1.9/2.3/2.7/3.1/3.6/4.1 all sit at multiples of 0.1s past the 1.5s
	// trigger), so the final sample reads the SAME clamped speed as the glide
	// samples -- a 1.00x resume ratio against gate (5)'s 1.5x bar.
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

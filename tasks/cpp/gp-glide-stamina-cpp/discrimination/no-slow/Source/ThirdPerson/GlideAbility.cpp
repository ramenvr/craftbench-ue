// Copyright CraftBench. All Rights Reserved.

#include "GlideAbility.h"

#include "CraftBenchGameplayTags.h"
#include "CraftBenchAttributeSet.h"
#include "AbilitySystemComponent.h"
#include "GameFramework/Character.h"
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
	UAbilitySystemComponent* ASC = GetAbilitySystemComponentFromActorInfo();
	if (!GlideAvatar.IsValid() || ASC == nullptr)
	{
		return;
	}

	// ---- THE ONE DELTA (anti-gaming note 2: "no actual slow") ----
	// The reference caps the descent here:
	//     if (UCharacterMovementComponent* CMC = Avatar->GetCharacterMovement())
	//     {
	//         if (CMC->Velocity.Z < -GlideFallSpeed) { CMC->Velocity.Z = -GlideFallSpeed; }
	//     }
	// This variant never touches velocity, so the avatar keeps accelerating
	// under full gravity for the whole "glide". (The CharacterMovementComponent
	// include went with the clamp; nothing else in this file used it.)

	// Drain the Power resource. UNCHANGED from the reference -- the stamina cost
	// is real, so gate (4) still passes and the FAIL lands on the slow axis.
	const float Current = ASC->GetNumericAttribute(UCraftBenchAttributeSet::GetPowerAttribute());
	const float Next = FMath::Max(0.0f, Current - DrainPerTick);
	ASC->SetNumericAttributeBase(UCraftBenchAttributeSet::GetPowerAttribute(), Next);

	if (Next <= 0.0f)
	{
		// Exhausted: stop gliding (normal fall resumes) and end the ability.
		EndAbility(CurrentSpecHandle, CurrentActorInfo, CurrentActivationInfo,
			/*bReplicate=*/true, /*bWasCancelled=*/false);
	}
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

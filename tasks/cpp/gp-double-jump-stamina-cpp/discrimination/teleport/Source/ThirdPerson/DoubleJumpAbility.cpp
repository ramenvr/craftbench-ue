// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT `teleport/` -- see DoubleJumpAbility.h for the full
// delta and the DJ-2b vs DJ-2c argument.
// STATUS: UNVALIDATED / NOT YET RUN.

#include "DoubleJumpAbility.h"

#include "CraftBenchGameplayTags.h"
#include "CraftBenchAttributeSet.h"
#include "AbilitySystemComponent.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"

UDoubleJumpAbility::UDoubleJumpAbility()
{
	InstancingPolicy = EGameplayAbilityInstancingPolicy::InstancedPerActor;

	FGameplayTagContainer Tags;
	Tags.AddTag(FCraftBenchGameplayTags::AbilityDoubleJump());
	SetAssetTags(Tags);
}

void UDoubleJumpAbility::ActivateAbility(
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

	UAbilitySystemComponent* ASC = GetAbilitySystemComponentFromActorInfo();
	ACharacter* Avatar = (ActorInfo != nullptr && ActorInfo->AvatarActor.IsValid())
		? Cast<ACharacter>(ActorInfo->AvatarActor.Get())
		: nullptr;

	if (ASC == nullptr || Avatar == nullptr)
	{
		EndAbility(Handle, ActorInfo, ActivationInfo, /*bReplicate=*/true, /*bWasCancelled=*/true);
		return;
	}

	// Unchanged from the reference: the cost is a real gate.
	const float CurrentPower =
		ASC->GetNumericAttribute(UCraftBenchAttributeSet::GetPowerAttribute());
	if (CurrentPower < PowerCost)
	{
		EndAbility(Handle, ActorInfo, ActivationInfo, /*bReplicate=*/true, /*bWasCancelled=*/true);
		return;
	}

	// Unchanged from the reference: one-shot debit of exactly the disclosed cost.
	ASC->SetNumericAttributeBase(
		UCraftBenchAttributeSet::GetPowerAttribute(),
		FMath::Max(0.0f, CurrentPower - PowerCost));

	// ---- THE ONE DELTA ------------------------------------------------------
	// The reference assigns an upward VELOCITY on CharacterMovement. This variant
	// moves the character's POSITION instead and leaves the velocity untouched:
	// gravity keeps whatever downward speed it had built up, so the character is
	// 300 cm higher and still descending at the same rate it was a frame earlier.
	//
	// To a reader the code says "the second jump lifts the character by 300", and
	// on the film strip the character visibly goes up. What never happens is the
	// REVERSAL the prompt asks for ("its descent must reverse and carry it upward
	// again"), and vZ is the only observable that can tell the two apart.
	//
	// bSweep = false and ETeleportType::None on purpose -- see the header: the
	// teleporting FLAGS decide whether the movement component's velocity is
	// disturbed, and this row's claim is specifically that it is NOT.
	if (UCharacterMovementComponent* CMC = Avatar->GetCharacterMovement())
	{
		CMC->SetMovementMode(MOVE_Falling);
	}
	Avatar->SetActorLocation(
		Avatar->GetActorLocation() + FVector(0.0, 0.0, static_cast<double>(TeleportRiseZ)),
		/*bSweep=*/false, /*OutSweepHitResult=*/nullptr, ETeleportType::None);

	EndAbility(Handle, ActorInfo, ActivationInfo, /*bReplicate=*/true, /*bWasCancelled=*/false);
}

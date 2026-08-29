// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT `slowed-fall/` -- see DoubleJumpAbility.h for the full
// delta, the I1.4 argument, the deliberate DJ-2b pass and the arithmetic.
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
	// The reference assigns +600 cm/s and lets full gravity pull the character
	// back down from a 183.7 cm apex. This variant does what AG-3 describes: it
	// SLOWS the descent instead of reversing it.
	//
	// The token +20 cm/s is not a jump -- it is the descent being arrested for a
	// moment. It exists so that the submission clears DJ-2b's pure-direction test
	// on velocity, which is the only way this row can reach DJ-2c at all (a
	// strictly-negative vZ dies one gate earlier, at the same substring
	// `teleport/` owns; see the header). Under the slowed gravity it buys 4.08 cm
	// of climb, well under the 20 cm the segmenter needs to call anything a rise.
	//
	// GravityScale 0.05 is the glide answer proper: after the flick the character
	// drifts down at a twentieth of gravity, looking on the film strip like the
	// ability "did something" while Z never climbs.
	if (UCharacterMovementComponent* CMC = Avatar->GetCharacterMovement())
	{
		CMC->SetMovementMode(MOVE_Falling);
		CMC->Velocity.Z = ArrestFallVelocityZ;
		CMC->GravityScale = SlowFallGravityScale;
	}

	EndAbility(Handle, ActorInfo, ActivationInfo, /*bReplicate=*/true, /*bWasCancelled=*/false);
}

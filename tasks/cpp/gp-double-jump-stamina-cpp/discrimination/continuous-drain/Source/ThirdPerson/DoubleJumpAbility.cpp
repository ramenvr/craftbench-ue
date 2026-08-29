// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT `continuous-drain/` -- see DoubleJumpAbility.h for the
// full delta, the two-sided rate derivation and the discrete-tick check.
// STATUS: UNVALIDATED / NOT YET RUN.

#include "DoubleJumpAbility.h"

#include "CraftBenchGameplayTags.h"
#include "CraftBenchAttributeSet.h"
#include "AbilitySystemComponent.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "TimerManager.h"

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

	// Unchanged from the reference: the full, disclosed 20 is charged here, once,
	// on the activation that pays for it. This is what makes DJ-3a and DJ-3b pass
	// and what makes the row attributable to DJ-3c alone (see the header).
	ASC->SetNumericAttributeBase(
		UCraftBenchAttributeSet::GetPowerAttribute(),
		FMath::Max(0.0f, CurrentPower - PowerCost));

	// ---- THE ONE DELTA ------------------------------------------------------
	// ...and then it keeps billing. A repeating upkeep that is never cleared: not
	// by EndAbility below, not by landing, not by anything. To a reader the code
	// still says "costs 20 Power", and at the only instant a casual check would
	// look -- immediately after the activation -- that is exactly what the
	// resource shows.
	//
	// CreateWeakLambda binds the timer's lifetime to the ability system component
	// rather than to this ability instance, so the upkeep genuinely outlives the
	// activation (an InstancedPerActor ability instance survives EndAbility, but
	// relying on that would make the row depend on an instancing policy it is not
	// about) and cannot outlive the pawn.
	const float Upkeep = UpkeepPerTick;
	Avatar->GetWorldTimerManager().SetTimer(
		UpkeepTimer,
		FTimerDelegate::CreateWeakLambda(ASC, [ASC, Upkeep]()
		{
			const float P =
				ASC->GetNumericAttribute(UCraftBenchAttributeSet::GetPowerAttribute());
			ASC->SetNumericAttributeBase(
				UCraftBenchAttributeSet::GetPowerAttribute(), P - Upkeep);
		}),
		UpkeepInterval,
		/*bLoop=*/true);

	// Unchanged from the reference: a real upward velocity.
	if (UCharacterMovementComponent* CMC = Avatar->GetCharacterMovement())
	{
		CMC->SetMovementMode(MOVE_Falling);
		CMC->Velocity.Z = JumpImpulseZ;
	}

	EndAbility(Handle, ActorInfo, ActivationInfo, /*bReplicate=*/true, /*bWasCancelled=*/false);
}

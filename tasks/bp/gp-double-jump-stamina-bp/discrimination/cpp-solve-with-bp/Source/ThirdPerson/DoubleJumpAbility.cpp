// Copyright CraftBench. All Rights Reserved.

#include "DoubleJumpAbility.h"

#include "CraftBenchGameplayTags.h"
#include "CraftBenchAttributeSet.h"
#include "AbilitySystemComponent.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"

UDoubleJumpAbility::UDoubleJumpAbility()
{
	InstancingPolicy = EGameplayAbilityInstancingPolicy::InstancedPerActor;

	// The asset tag the game activates this ability by
	// (NumGrantedAbilitiesWithTag / TryActivateAbilitiesByTag both read the
	// ability's ASSET tags). Ability.DoubleJump is this family's tag and is
	// distinct from every other ability tag in the substrate.
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

	// --- the cost is a GATE, not a subtraction -------------------------------
	// Below the cost the ability does nothing at all: no jump, and Power is left
	// exactly where it was rather than being driven negative. Checked BEFORE the
	// debit and before the impulse so neither can happen on a refusal.
	const float CurrentPower =
		ASC->GetNumericAttribute(UCraftBenchAttributeSet::GetPowerAttribute());
	if (CurrentPower < PowerCost)
	{
		EndAbility(Handle, ActorInfo, ActivationInfo, /*bReplicate=*/true, /*bWasCancelled=*/true);
		return;
	}

	// --- one-shot debit -------------------------------------------------------
	// Charged once, here, on the activation that pays for it. There is
	// deliberately no timer and no per-tick draw: the ability ends below, so
	// nothing of it survives the activation to keep spending while the character
	// is airborne. FMath::Max is belt-and-braces only -- the gate above already
	// guarantees CurrentPower >= PowerCost.
	ASC->SetNumericAttributeBase(
		UCraftBenchAttributeSet::GetPowerAttribute(),
		FMath::Max(0.0f, CurrentPower - PowerCost));

	// --- the second jump ------------------------------------------------------
	// A real upward velocity on CharacterMovement, which gravity then decelerates
	// and pulls back down: the character genuinely rises a second time and falls
	// from the new apex.
	//
	// ASSIGNED, not added. Mid-fall the character is already carrying a large
	// negative vZ, so ADDING an upward amount to it (LaunchCharacter's default
	// bZOverride = false does exactly that) can leave the velocity still negative
	// and the character still descending -- it would read as "launch the
	// character up by 600" and never reverse anything. Replacing the vertical
	// component makes the reversal independent of how fast it happened to be
	// falling.
	//
	// SetMovementMode first so the ability also behaves sanely if it is ever
	// activated from the ground; it is a no-op when the character is already
	// falling, which is the case the task is about.
	if (UCharacterMovementComponent* CMC = Avatar->GetCharacterMovement())
	{
		CMC->SetMovementMode(MOVE_Falling);
		CMC->Velocity.Z = JumpImpulseZ;
	}

	EndAbility(Handle, ActorInfo, ActivationInfo, /*bReplicate=*/true, /*bWasCancelled=*/false);
}

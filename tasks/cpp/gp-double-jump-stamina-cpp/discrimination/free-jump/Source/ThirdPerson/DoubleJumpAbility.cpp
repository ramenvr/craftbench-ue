// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT `free-jump/` -- ONE DELTA from ../../reference (this
// file only; DoubleJumpAbility.h is byte-identical to the reference and still
// declares PowerCost, which the refusal gate below still reads). AXIS: the
// second jump RISES but DEBITS NOTHING. Defends PIN.md section 3 AG-4, first
// half ("a free double jump (no debit)").
// EXPECTED: FAIL at DJ-3a, last checkpoint.
// STATUS: UNVALIDATED / NOT YET RUN (no build, no PIE run, no grade).
//
// THE DELTA, in full: the reference's one-shot
//     ASC->SetNumericAttributeBase(Power, FMath::Max(0.0f, CurrentPower - PowerCost));
// is REMOVED. Nothing else changes -- the tag, the grant, the mannequin, the
// impulse of +600 and, importantly, the `CurrentPower < PowerCost` REFUSAL GATE
// all stay exactly as the reference has them.
//
// KEEPING THE REFUSAL GATE IS THE DESIGN DECISION HERE, and it is what makes the
// row attributable. This submission reads Power, refuses below the cost, and
// then jumps without ever spending anything: it is the shape that passes a
// casual review ("it checks the cost") while the resource is never actually
// consumed, so a player has infinite double jumps from the first frame. It also
// means the row cannot be mistaken for `fires-when-broke/`: DJ-4 would PASS on
// this submission (at 5 Power the gate refuses and Leg 2 shows no rise), and the
// only gate it can fail is DJ-3a.
//
// WHY DJ-3a AND NOT DJ-3b. Both are Power gates and DJ-3a runs first. DJ-3a is
// the direction predicate ("Power strictly decreased, by more than the noise
// floor"); with no debit at all the measured delta is exactly 0.00 against a
// PowerEpsilon of 0.5, so it is the gate that fires. DJ-3b would also have
// failed here (|0 - 20| = 20 > CostTol) -- the ordering, not the arithmetic, is
// what assigns this row its name, and DJ-3a's message is the honest one for a
// submission that charged nothing at all.
//
// THE MEASURED DELTA IS EXACTLY ZERO, not merely small. Power is written only by
// the fixture's own preset (60.0) and by this ability, and this ability no longer
// writes it, so nothing between the preset and the trigger+0.3 sample can move
// the value. That is the conforming-vs-violating separation this row contributes
// to PowerEpsilon's calibration: violating side 0.00, conforming side 20.00
// (the reference), against a floor of 0.5. PROPOSED - NOT YET MEASURED.
//
// EXPECTED NAMED FAIL (a literal run of the DJ-3a format string in
// DoubleJumpStaminaFunctionalTest.cpp -- the two Power readings that follow are
// %.1f and are NOT part of the recorded substring):
//     the second jump cost no Power: Power went
//
// Predicted diagnostic line 1: `granted=1 legOneActivated=1/1` with a perfectly
// normal jump (`maxVZlegOne=+584 legOneRises=1 legOneRiseZ=184`) and
// `powerAtTrigger=60.0 plus03=60.0 plus12=60.0 debited=0.00 furtherDrop=0.00`.
// PREDICTED - NOT YET MEASURED.

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

	// UNCHANGED from the reference, deliberately: the ability still READS Power
	// and still refuses below the cost, so the refusal leg (DJ-4) behaves exactly
	// as it does on a conforming solve.
	const float CurrentPower =
		ASC->GetNumericAttribute(UCraftBenchAttributeSet::GetPowerAttribute());
	if (CurrentPower < PowerCost)
	{
		EndAbility(Handle, ActorInfo, ActivationInfo, /*bReplicate=*/true, /*bWasCancelled=*/true);
		return;
	}

	// ---- THE ONE DELTA ------------------------------------------------------
	// The reference's one-shot debit stood here. It is gone: the check above
	// gates on a resource that is never actually spent, so Power reads 60.0
	// before the activation and 60.0 after it.

	// Unchanged from the reference: a real upward velocity, so the MOTION gates
	// (DJ-2a, DJ-2b, DJ-2c) all pass and this row can only be about the cost.
	if (UCharacterMovementComponent* CMC = Avatar->GetCharacterMovement())
	{
		CMC->SetMovementMode(MOVE_Falling);
		CMC->Velocity.Z = JumpImpulseZ;
	}

	EndAbility(Handle, ActorInfo, ActivationInfo, /*bReplicate=*/true, /*bWasCancelled=*/false);
}

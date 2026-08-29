// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT `fires-when-broke/` -- ONE DELTA from ../../reference
// (this file only; DoubleJumpAbility.h is byte-identical to the reference).
// AXIS: the cost is a SUBTRACTION, not a GATE -- the ability fires below the
// cost and drives Power negative. Defends PIN.md section 3 AG-6.
// EXPECTED: FAIL at DJ-4, last checkpoint, the last of the eight final gates.
// STATUS: UNVALIDATED / NOT YET RUN (no build, no PIE run, no grade).
//
// THE DELTA, in full, and it is ONE axis stated in AG-6's own words ("debit
// Power but never actually gate on it: the jump fires at 0 Power and the
// resource goes negative"):
//   * the `if (CurrentPower < PowerCost) { EndAbility(cancelled); return; }`
//     refusal is REMOVED, so nothing ever declines to fire;
//   * the debit loses its `FMath::Max(0.0f, ...)` floor, so the resource is
//     genuinely driven under zero rather than resting at 0.
// The two are the same defect seen from either end -- an implementation that
// treats "cost" as arithmetic -- and AG-6 names both halves, so the row exercises
// both halves of DJ-4's disjunction (a Leg-2 rise AND a negative Power) rather
// than only the one the gate happens to test first.
//
// ===========================================================================
// THIS IS THE ROW THAT MAKES THE TASK ABOUT A COST RATHER THAN A SUBTRACTION
// ===========================================================================
// PIN.md section 3 AG-6: "this is the gate that makes the task about a resource
// COST rather than about a subtraction". Every other gate in the fixture passes
// on this submission -- DJ-7 at checkpoint 0, then DJ-1, DJ-2a, DJ-2b, DJ-2c,
// DJ-3a, DJ-3b and DJ-3c -- because Leg 1 is byte-for-byte the reference's
// behaviour: it starts at 60 Power, debits exactly 20 once, and rises 183.7 cm.
// The submission only becomes wrong on Leg 2, where the fixture presets Power to
// 5 against a cost of 20 and re-triggers. That is the whole reason PIN.md D2
// ADDED the refusal clause to the prompt: without Leg 2, "consume 20 stamina" is
// satisfied by a subtraction that never gates anything.
//
// PREDICTED LEG-2 TRACE. Power 5.0 -> -15.0 (the unclamped debit), and the
// character rises another 183.7 cm from wherever the Leg-1 arc left it. DJ-4's
// Leg-2 segment filter is START-keyed (`StartT >= RefusalTriggerTime -
// SegmentBoundarySlack`), and the rise opens at the trigger's own world time, so
// it is inside the window with 0.10 s of slack to spare. The rise closes when a
// following fall covers RiseEpsilon = 20 cm, which takes sqrt(2*20/980) = 0.20 s
// after the apex at trigger+0.61 -- i.e. at about t = 3.21, comfortably before
// the last checkpoint at 3.3, so the segment is CLOSED and emitted rather than
// left dangling. PROPOSED - NOT YET MEASURED; read `fullSegments=` on the second
// [DOUBLEJUMP-FINAL] line before believing it, because I1.4 has never executed.
//
// SKIP-vs-FAIL, and why this row is the one that proves the guard is wired the
// right way round. DJ-4 may hard-FAIL only when DJ-2c passed on Leg 1
// (PIN.md D3, endorsed verbatim by the owner decision of 2026-08-10). This
// submission's Leg 1 is perfect, so `bLegOneRose` is true and the gate is
// HARD-GATED rather than SKIPPED. Expect the `[DJ-REFUSE-DIAG]` line to say so,
// in its first branch, BEFORE the FAIL. A run of this variant that logged the
// SKIPPED branch instead would mean Leg 1 broke, and the DJ-4 verdict would then
// be describing the wrong thing entirely.
//
// EXPECTED NAMED FAIL (a literal run of the DJ-4 format string in
// DoubleJumpStaminaFunctionalTest.cpp -- the climb and the Power reading that
// follow are %.0f/%.1f and are NOT part of the recorded substring; the "5.0" and
// "20" ARE inside the literal run because the fixture hard-codes its own presets
// there):
//     the ability fired without paying for it: with only 5.0 Power (below the 20 cost) the character still rose a second time (Z climbed
//
// Predicted diagnostic line 1: `granted=1 legOneActivated=1/1 legTwoActivated=1/1`
// with `legOneRises=1 legTwoRises=1 legTwoRiseZ=184`, `powerAtTrigger=60.0
// plus03=40.0 plus12=40.0 debited=20.00 furtherDrop=0.00` and
// `minPowerLegTwo=-15.0 lastPowerLegTwo=-15.0` -- a flawless Leg 1 next to a
// resource driven fifteen points under zero.
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

	const float CurrentPower =
		ASC->GetNumericAttribute(UCraftBenchAttributeSet::GetPowerAttribute());

	// ---- THE ONE DELTA ------------------------------------------------------
	// The reference's refusal stood here:
	//     if (CurrentPower < PowerCost) { EndAbility(..., bWasCancelled=true); return; }
	// It is gone. The cost is now purely arithmetic: whatever Power the character
	// holds, the ability fires and subtracts 20 from it. On a full resource that
	// is indistinguishable from the reference -- which is exactly why the fixture
	// needs a second leg to see it at all.
	//
	// The FMath::Max(0.0f, ...) floor is gone with it, so the subtraction is
	// allowed to take the resource below zero. UCraftBenchAttributeSet does no
	// clamping of its own (no PreAttributeChange, no PostGameplayEffectExecute --
	// see CraftBenchAttributeSet.h, "no clamping ... at v1.0"), so nothing
	// downstream will quietly rescue the value.
	ASC->SetNumericAttributeBase(
		UCraftBenchAttributeSet::GetPowerAttribute(),
		CurrentPower - PowerCost);

	// Unchanged from the reference: a real upward velocity, on every activation
	// including the one the character cannot afford.
	if (UCharacterMovementComponent* CMC = Avatar->GetCharacterMovement())
	{
		CMC->SetMovementMode(MOVE_Falling);
		CMC->Velocity.Z = JumpImpulseZ;
	}

	EndAbility(Handle, ActorInfo, ActivationInfo, /*bReplicate=*/true, /*bWasCancelled=*/false);
}

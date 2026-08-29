// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT `teleport/` -- ONE DELTA from ../../reference (this
// file pair only). AXIS: a POSITION CHANGE WITH NO UPWARD VELOCITY. Defends
// PIN.md section 3 AG-2, first half ("teleport the character upward instead of
// applying an impulse").
// EXPECTED: FAIL at DJ-2b, last checkpoint.
// STATUS: UNVALIDATED / NOT YET RUN (no build, no PIE run, no grade).
//
// THE DELTA, in full: `CMC->Velocity.Z = JumpImpulseZ` becomes
// `Avatar->SetActorLocation(location + (0,0,TeleportRiseZ))`. Everything else in
// the overlay is byte-identical to the reference -- the tag, the grant, the
// mannequin, the refusal gate below the cost, and the one-shot debit of exactly
// 20. So DJ-1, DJ-2a, DJ-3a, DJ-3b and DJ-3c would all pass, and DJ-7 passes at
// checkpoint 0. This row isolates the MOTION axis and nothing else.
//
// WHY IT DIES AT DJ-2b AND NOT AT DJ-2c. The teleport moves Z by +300 in a
// single frame, so the SEGMENTER genuinely sees a rise: between two adjacent
// dense samples Z jumps 300 cm, which is 15x RiseEpsilon and is emitted as a
// RISE segment. DJ-2c would therefore PASS this submission. What the teleport
// cannot fake is the VELOCITY: SetActorLocation with bSweep = false and
// ETeleportType::None does not touch CharacterMovement's velocity, so vZ stays
// at whatever gravity produced (about -690 at the trigger, growing more negative
// through the leg) and the maximum vertical velocity in the whole Leg-1 window
// is negative. DJ-2b is a PURE DIRECTION predicate on exactly that number and it
// runs BEFORE DJ-2c.
//
// That ordering is the point of the row: DJ-2b and DJ-2c are not redundant, they
// are the two halves of "a real second jump". This variant proves DJ-2b catches
// what DJ-2c cannot; `slowed-fall/` proves the converse.
//
// THE TELEPORT FLAGS ARE LOAD-BEARING, and this is the line to re-read if the
// row ever passes DJ-2b. ETeleportType::TeleportPhysics resets the movement
// component's physics state and could leave vZ at exactly 0.0 -- which still
// FAILs DJ-2b (the gate is `MaxVZLegOne > 0.0`, so 0.0 is a FAIL) but for a
// reason this header does not claim. bSweep = true would resolve the move as a
// swept collision and could bleed velocity as well. ETeleportType::None with no
// sweep is the plain "put the actor here" form a gaming solve reaches for, and
// it is the one this variant uses.
//
// EXPECTED NAMED FAIL (a literal run of the DJ-2b format string in
// DoubleJumpStaminaFunctionalTest.cpp -- the velocity that follows is a %.0f and
// is NOT part of the recorded substring):
//     the ability produced no upward impulse: the highest vertical velocity after the trigger was
//
// Predicted diagnostic line 1: `granted=1 legOneActivated=1/1` with
// `maxVZlegOne` deeply negative, `legOneRises=1` (the teleport's own step) and
// `powerAtTrigger=60.0 plus03=40.0 debited=20.00` -- i.e. the numbers show a
// perfect ability whose one defect is that nothing was ever pushed upward.
// PREDICTED - NOT YET MEASURED.

#pragma once

#include "CoreMinimal.h"
#include "Abilities/GameplayAbility.h"
#include "DoubleJumpAbility.generated.h"

UCLASS()
class UDoubleJumpAbility : public UGameplayAbility
{
	GENERATED_BODY()

public:
	UDoubleJumpAbility();

	virtual void ActivateAbility(
		const FGameplayAbilitySpecHandle Handle,
		const FGameplayAbilityActorInfo* ActorInfo,
		const FGameplayAbilityActivationInfo ActivationInfo,
		const FGameplayEventData* TriggerEventData) override;

private:
	/** Unchanged from the reference: the DISCLOSED cost.
	 *  PROPOSED - NOT YET MEASURED. */
	float PowerCost = 20.0f;

	/** THE DELTA. Centimetres of Z the ability teleports the character upward,
	 *  replacing the reference's velocity assignment. 300 is chosen to be
	 *  UNAMBIGUOUSLY visible as a position change -- 15x the proposed RiseEpsilon
	 *  of 20 cm -- so that if this row ever failed at DJ-2c instead, the cause
	 *  could not be "the teleport was too small to register as a rise".
	 *  PROPOSED - NOT YET MEASURED. */
	float TeleportRiseZ = 300.0f;
};

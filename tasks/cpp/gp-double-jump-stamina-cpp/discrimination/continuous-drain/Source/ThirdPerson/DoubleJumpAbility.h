// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT `continuous-drain/` -- ONE DELTA from ../../reference
// (this file pair only). AXIS: the cost is charged as a CONTINUOUS UPKEEP that
// keeps spending after the activation, not as a one-shot debit. Defends PIN.md
// section 3 AG-5 ("charge the cost as a per-tick drain while airborne, which
// technically 'consumes stamina'").
// EXPECTED: FAIL at DJ-3c, last checkpoint.
// STATUS: UNVALIDATED / NOT YET RUN (no build, no PIE run, no grade).
//
// THE DELTA, in full: the reference's one-shot debit stays exactly as it is, and
// a REPEATING UPKEEP TIMER is started alongside it that keeps drawing Power for
// as long as the run lasts. The timer is never stopped and nothing cancels it --
// which is the whole gaming shape: the ability "costs 20" at the instant anyone
// looks, and then quietly keeps billing.
//
// ===========================================================================
// WHY THIS ROW HAS TO PASS DJ-3a AND DJ-3b TO BE WORTH ANYTHING
// ===========================================================================
// DJ-3a, DJ-3b and DJ-3c run in that order and all three read Power. A NAIVE
// drain-only variant -- delete the one-shot debit, bill 20 Power/s while
// airborne -- would have debited only 6.0 by the trigger+0.3 sample and would
// die at DJ-3b under the name "did not cost 20 Power", describing a magnitude
// error its author did not make. That is the F5 attribution defect this family
// was authored to avoid, so this variant is built the other way round: it pays
// the disclosed 20 up front, in full, on time, and THEN keeps draining. DJ-3a
// and DJ-3b both pass; only DJ-3c, the "stopped changing" predicate over
// (trigger+0.3, trigger+1.2], can see the defect.
//
// ===========================================================================
// THE RATE IS PINNED BETWEEN TWO GATES, NOT CHOSEN
// ===========================================================================
// Let r be the upkeep rate in Power/s. The fixture samples Power at
// trigger+0.3 (DJ-3a/3b's "to" reading and DJ-3c's window OPEN) and at
// trigger+1.2 (DJ-3c's window CLOSE).
//
//   * DJ-3b must PASS: debited at trigger+0.3 is 20 + 0.3r, and CostTol is 1.0,
//     so 0.3r <= 1.0, i.e. r <= 3.33 Power/s.
//   * DJ-3c must FAIL: the further drop across the 0.9 s window is 0.9r, and
//     PowerEpsilon is 0.5, so 0.9r > 0.5, i.e. r > 0.556 Power/s.
//
// The admissible band is (0.556, 3.33]. This variant uses r = 1.5 Power/s, which
// sits close to the geometric midpoint (1.36) of that band:
//   * DJ-3b margin: debited reads 20.45, which is 0.55 INSIDE the 1.0 tolerance.
//   * DJ-3c margin: the further drop reads 1.35, which is 2.7x the 0.5 floor.
// Both bars are PROPOSED - NOT YET MEASURED, so the band moves with them: if
// either PowerEpsilon or CostTol is re-pinned, RE-DERIVE r FROM THE INEQUALITIES
// ABOVE rather than nudging the constant. A variant tuned against an unmeasured
// bar tests the guess, not the gate.
//
// THE TIMER IS DISCRETE, and the counts are checked rather than assumed (the
// lesson gp-poison-dot-stack-cpp's `permanent-drain/` paid for: a derivation
// that assumes a tick count is exactly the defect that variant measured). At
// UpkeepInterval = 0.1 s and UpkeepPerTick = 0.15 the timer fires at
// trigger+0.1, +0.2, +0.3, ... so:
//   * by trigger+0.3 either 2 or 3 fires have landed (the third sits exactly on
//     the sample instant, so its ordering within that frame is not something
//     this header will pretend to know) -> extra 0.30 or 0.45 -> debited 20.30
//     or 20.45. BOTH are inside CostTol = 1.0, so DJ-3b passes either way.
//   * by trigger+1.2, 11 or 12 fires -> extra 1.65 to 1.80 -> the further drop
//     across the window is between 1.20 and 1.50. BOTH are above
//     PowerEpsilon = 0.5, so DJ-3c fails either way.
// Neither gate's verdict turns on the boundary fire, which is what makes the row
// structural rather than lucky.
//
// SIDE EFFECT ON LEG 2, recorded so a reader is not surprised by the log: the
// timer is never stopped, so Power keeps falling through the Leg-2 preset and
// re-trigger and will read well under 5 by the last checkpoint, possibly
// negative. DJ-3c fires first and DJ-4 is never reached; but if the gate order
// were ever changed, THIS ROW WOULD START FAILING UNDER DJ-4's NAME. That
// dependency on ordering is stated here rather than discovered later.
//
// EXPECTED NAMED FAIL (a literal run of the DJ-3c format string in
// DoubleJumpStaminaFunctionalTest.cpp -- the four numbers that follow are
// %.1f/%.2f and are NOT part of the recorded substring):
//     the Power cost is a continuous drain, not a one-shot debit: Power kept falling after the activation (
//
// Predicted diagnostic line 1: `granted=1 legOneActivated=1/1` with a normal
// jump (`maxVZlegOne=+584 legOneRises=1 legOneRiseZ=184`) and
// `powerAtTrigger=60.0 plus03=39.6 plus12=38.2 debited=20.45 furtherDrop=1.35`.
// PREDICTED - NOT YET MEASURED.

#pragma once

#include "CoreMinimal.h"
#include "Abilities/GameplayAbility.h"
#include "Engine/TimerHandle.h"
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
	/** Unchanged from the reference: the DISCLOSED cost, charged in full and on
	 *  time so DJ-3a and DJ-3b both PASS.
	 *  PROPOSED - NOT YET MEASURED. */
	float PowerCost = 20.0f;

	/** Unchanged from the reference: a real upward velocity, so every motion gate
	 *  passes and this row can only be about the cost.
	 *  PROPOSED - NOT YET MEASURED. */
	float JumpImpulseZ = 600.0f;

	/** THE DELTA, part 1. Power drawn by each upkeep fire. With UpkeepInterval
	 *  below this is a rate of 1.5 Power/s -- derived from the two-sided band in
	 *  the header, not chosen. PROPOSED - NOT YET MEASURED. */
	float UpkeepPerTick = 0.15f;

	/** THE DELTA, part 2. Upkeep period, in seconds. Short relative to both of
	 *  DJ-3c's window edges so neither gate's verdict depends on where a single
	 *  fire lands (see the discrete-tick check in the header).
	 *  PROPOSED - NOT YET MEASURED. */
	float UpkeepInterval = 0.1f;

	/** Handle for the upkeep timer. Never cleared -- that is the defect. */
	FTimerHandle UpkeepTimer;
};

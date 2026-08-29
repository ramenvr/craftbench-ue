// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT `slowed-fall/` -- ONE DELTA from ../../reference (this
// file pair only). AXIS: the descent is merely SLOWED, never reversed into a
// real climb. Defends PIN.md section 3 AG-3 ("reuse the glide answer: slow the
// descent instead of reversing it") and the second half of AG-2 ("nudges Z once
// and lets it keep falling").
// EXPECTED: FAIL at DJ-2c, last checkpoint.
// STATUS: UNVALIDATED / NOT YET RUN (no build, no PIE run, no grade).
//
// ===========================================================================
// THIS IS THE ROW THAT JUSTIFIES I1.4, AND IT IS THE ONE TO READ HARDEST
// ===========================================================================
// DJ-2c gates on a SEGMENTED SECOND RISE: the dense series is decomposed into
// monotonic runs at MinDeltaZ = RiseEpsilon, and a rising run reaching into
// Leg 1 must have travelled at least RiseEpsilon. NONE of the reductions that
// existed before I1.4 can answer that question about THIS submission, and the
// failure mode is not "less precise", it is "wrong for a structural reason":
//
//   * RoseThenFell is FIRST-SAMPLE -> GLOBAL-PEAK -> LAST-SAMPLE, one bool for
//     the whole series. Its verdict on any run is decided by where the first
//     sample happens to sit. On this submission the series starts at the SPAWN
//     (z = 1200), so the global peak IS the first sample and the answer is
//     accidental in one direction; move the sampling start a few frames later,
//     or start it at the trigger, and the token 4 cm flick below becomes the
//     global peak relative to a lower opening sample -- and the same submission
//     reads "rose then fell". Same code, same trajectory, opposite verdict,
//     decided by a sampling boundary rather than by the motion.
//   * ApexDeltaZ is first-sample-to-global-peak: on a series that only ever
//     descends it is 0 or negative, so it cannot distinguish "did not rise" from
//     "rose 4 cm" from "rose 184 cm" without a MAGNITUDE bar -- and the prompt
//     fixes no jump height, so a magnitude bar is exactly the undisclosed floor
//     PIN.md refuses to add ("Why there is no 'the second jump must reach height
//     H' gate").
//   * MaxVelocityZAfter (DJ-2b) is a pure direction test on velocity, and this
//     variant DELIBERATELY PASSES IT -- see below.
//
// Only a SEGMENTED decomposition answers "did Z climb back, after bottoming out,
// by more than the noise floor" without asking how high. This row is the
// evidence that the question is real and that the old reductions would have
// answered it by accident.
//
// ===========================================================================
// WHY THIS VARIANT PASSES DJ-2b ON PURPOSE (the design decision to check)
// ===========================================================================
// DJ-2b (`MaxVelocityZAfter(trigger) > 0`) runs BEFORE DJ-2c. A submission whose
// vertical velocity is negative at every sample therefore dies at DJ-2b and can
// never reach DJ-2c -- which means a PURE slowed fall (vZ clamped to a small
// negative number, the literal glide answer) would land on `teleport/`'s
// substring and would isolate NOTHING beyond it. PIN.md section 3 AG-3 says
// exactly that: "vZ stays negative throughout -> DJ-2b".
//
// So for this row to test DJ-2c at all, the submission must clear DJ-2b. It does
// it the way a real gaming solve does: a TOKEN upward flick that arrests the
// descent for a moment (ArrestFallVelocityZ, a genuinely positive vZ), followed
// by a fall that is merely slowed rather than reversed (SlowFallGravityScale).
// That is precisely the shape DJ-2c's own FAIL message names -- "A one-shot
// upward velocity that is immediately cancelled, or a slowed fall, looks like
// this."
//
// THE HAZARD THIS CREATES, STATED RATHER THAN HIDDEN. The only thing separating
// this variant from a CONFORMING but gentle second jump is the MAGNITUDE of the
// climb: 4.1 cm here against a RiseEpsilon of 20 cm. RiseEpsilon is
// PROPOSED - NOT YET MEASURED, and the fixture's own header calls a too-high
// RiseEpsilon "the unforgivable direction" because it fails a conforming gentle
// jump for not jumping. This row is therefore ALSO the calibration probe for
// that bar: its measured rise is the violating population, the reference's
// 183.7 cm is the conforming one, and PIN.md section 6 owes both with the margin
// on each side. Do not read a green on this row as evidence that RiseEpsilon is
// pinned -- it is evidence that 4.1 cm and 183.7 cm sit on opposite sides of
// whatever 20 cm turns out to be.
//
// ===========================================================================
// THE ARITHMETIC (world gravity -980 cm/s^2, GravityScale 1.0 unmodified)
// ===========================================================================
// With GravityScale = 0.05 the effective gravity is -49 cm/s^2, so at the
// runner's -FPS=60 one frame costs 49/60 = 0.82 cm/s of upward velocity.
//   * DJ-2b margin. The first dense sample strictly after the trigger reads
//     20 - 0.82 = +19.2 cm/s, and the velocity stays positive for
//     20 / 0.82 = ~24 frames (0.41 s). DJ-2b needs one positive sample and gets
//     about twenty-four, so the row cannot slip into `teleport/`'s gate by a
//     frame-ordering accident.
//   * DJ-2c margin. The climb is h = v^2 / (2 * 49) = 400 / 98 = 4.08 cm,
//     against a RiseEpsilon / MinDeltaZ of 20 cm -- 4.9x BELOW the floor. The
//     segmenter absorbs a run of that size entirely (that absorption is what
//     MinDeltaZ is for), so the decomposition should read as one long FALL and
//     `legOneRises` should be 0.
//   * Discretization is not a factor at either end: the sampled apex sits at
//     most g*dt^2/2 = 49 / 7200 = 0.007 cm below the true apex.
//   * The character stays airborne for the whole run, so nothing here is decided
//     by a landing: from z ~= 960 at the trigger, a 49 cm/s^2 descent covers
//     only ~71 cm by the Leg-2 checkpoint at t = 2.4.
// ALL OF THESE ARE PROPOSED - NOT YET MEASURED. Read `legOneSegments=` on the
// second [DOUBLEJUMP-FINAL] line before believing any of them: I1.4 has never
// executed, and this row's whole claim is a statement about its decomposition.
//
// EXPECTED NAMED FAIL (a literal run of the DJ-2c format string in
// DoubleJumpStaminaFunctionalTest.cpp -- the minimum Z that follows is a %.0f
// and is NOT part of the recorded substring):
//     the character did not rise a second time: Z fell to
//
// Predicted diagnostic line 1: `granted=1 legOneActivated=1/1` with
// `maxVZlegOne=+19` (DJ-2b PASSES), `legOneRises=0 legOneRisesRaw=0
// legOneRiseZ=0` and `powerAtTrigger=60.0 plus03=40.0 debited=20.00`.
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

	/** THE DELTA, part 1. A token upward velocity that arrests the descent
	 *  without ever carrying the character anywhere: 20 cm/s buys 4.08 cm of
	 *  climb under the slowed gravity below. Pinned between two bounds rather
	 *  than picked: it must exceed one frame of the slowed gravity (0.82 cm/s) so
	 *  DJ-2b's pure-direction test sees a positive sample, and it must stay under
	 *  sqrt(2 * 49 * 20) = 44.3 cm/s so the resulting climb stays under
	 *  RiseEpsilon. 20 sits an order of magnitude above the first bound and 2.2x
	 *  under the second. PROPOSED - NOT YET MEASURED. */
	float ArrestFallVelocityZ = 20.0f;

	/** THE DELTA, part 2, and the part that makes this "a slowed fall" rather
	 *  than "a small jump": after the flick, the descent resumes at one twentieth
	 *  of gravity. This is the glide answer reused verbatim -- the character
	 *  visibly stops plummeting and drifts down, which satisfies a careless
	 *  reading of "the second jump" while never reversing anything.
	 *  PROPOSED - NOT YET MEASURED. */
	float SlowFallGravityScale = 0.05f;
};

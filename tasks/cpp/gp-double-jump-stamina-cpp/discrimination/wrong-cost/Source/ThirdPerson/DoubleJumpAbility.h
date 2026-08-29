// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT `wrong-cost/` -- ONE DELTA from ../../reference (this
// file only; DoubleJumpAbility.cpp is byte-identical to the reference). AXIS:
// the activation debits a resource cost that is NOT the disclosed 20. Defends
// PIN.md section 3 AG-4, second half ("a cosmetic debit of the wrong size").
// EXPECTED: FAIL at DJ-3b, last checkpoint.
// STATUS: UNVALIDATED / NOT YET RUN (no build, no PIE run, no grade).
//
// THE DELTA, in full: `PowerCost` goes from 20.0f to 35.0f. Nothing else
// changes. The debit is still one-shot, still charged on the activation that
// pays for it, still gated so the ability refuses below its own cost -- every
// structural property the task asks for is present and only the NUMBER is wrong.
//
// WHY IT DIES AT DJ-3b AND NOT AT DJ-3a. DJ-3a is a direction predicate ("Power
// strictly decreased by more than PowerEpsilon") and this submission passes it
// comfortably: 35.0 debited against a 0.5 floor, 70x the noise. Only DJ-3b, the
// ONE real absolute in the fixture, reads the magnitude: |35 - 20| = 15 against
// a CostTol of 1.0, i.e. 15x outside the tolerance. That separation is the point
// of the row -- it proves DJ-3b is not redundant with DJ-3a, and it is the
// violating population for CostTol's calibration (conforming side: the
// reference's 20.00). PROPOSED - NOT YET MEASURED.
//
// WHY 35 AND NOT 40, AND WHY THE ROW IS LAWFUL. 40 would be an exact DOUBLE
// debit, which is a different defect (a cost charged twice) and would invite the
// wrong reading of a FAIL. 35 is not a multiple of 20, so the only description
// of it is "the wrong cost". The row is lawful under TASK-AUTHOR-GUIDE.md
// section C for the same reason DJ-3b itself is: the prompt says "costs 20
// Power" in those words, so a submission charging 35 is violating a DISCLOSED
// number, not an undisclosed magnitude floor.
//
// SIDE EFFECT ON LEG 2, recorded so a reader is not surprised by the log: with a
// cost of 35 the refusal gate refuses at the Leg-2 preset of 5 exactly as the
// reference does, so DJ-4 would also PASS here. It is never reached -- DJ-3b
// fires first -- but the row does not depend on Leg 2 in either direction.
//
// EXPECTED NAMED FAIL (a literal run of the DJ-3b format string in
// DoubleJumpStaminaFunctionalTest.cpp -- the readings that follow are %.1f and
// are NOT part of the recorded substring; note the "60.0" IS inside the literal
// run because the fixture hard-codes its own Leg-1 preset there):
//     the second jump did not cost 20 Power: Power went 60.0 ->
//
// Predicted diagnostic line 1: `granted=1 legOneActivated=1/1` with a normal
// jump (`maxVZlegOne=+584 legOneRises=1 legOneRiseZ=184`) and
// `powerAtTrigger=60.0 plus03=25.0 plus12=25.0 debited=35.00 furtherDrop=0.00`
// -- a perfectly one-shot debit of the wrong size.
// PREDICTED - NOT YET MEASURED.
//
// The rest of this header is the reference's, unchanged.
//
// A GameplayAbility tagged Ability.DoubleJump that, on activation:
//   1. refuses outright when the character holds less than the cost (no jump,
//      no debit, Power never goes negative);
//   2. debits the cost from Power exactly ONCE per activation -- a one-shot,
//      never a per-tick drain, so the ability holds nothing open and needs no
//      timer at all;
//   3. reverses the descent with a real upward velocity on CharacterMovement,
//      which gravity then pulls back down -- not a teleport and not a slowed
//      fall;
//   4. ends immediately.
//
// InstancedPerActor for consistency with the family's other abilities; because
// the ability ends synchronously inside ActivateAbility it never refuses its own
// next activation (bRetriggerInstancedAbility defaults false and only bites an
// instance that is still running), which is what lets the verifier trigger it
// again on a second leg.

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
	/** THE DELTA. The reference charges the DISCLOSED 20; this variant charges 35
	 *  -- structurally identical, numerically wrong. See the header for why 35
	 *  rather than 40 and for the CostTol margin this row measures.
	 *  PROPOSED - NOT YET MEASURED. */
	float PowerCost = 35.0f;

	/** Upward velocity (cm/s) the second jump sets on CharacterMovement.
	 *  UNCHANGED from the reference -- the motion axis is not what this variant
	 *  breaks, so every motion gate must pass on it.
	 *  PROPOSED - NOT YET MEASURED.
	 *
	 *  ARITHMETIC (world gravity is the UE default -980 cm/s^2; nothing in
	 *  ThirdPerson/Config overrides it, and CharacterMovement's GravityScale is
	 *  left at 1.0):
	 *    - a velocity reversal to +v rises h = v^2 / (2 * 980) cm before gravity
	 *      wins, INDEPENDENTLY of how fast it was falling, because the assignment
	 *      replaces the descent velocity rather than adding to it;
	 *    - h(600) = 360000 / 1960 = 183.7 cm;
	 *    - the sheet's RiseEpsilon / MinDeltaZ floor is a PROPOSED 20 cm, so the
	 *      rise clears it by 163.7 cm -- a 9.2x margin;
	 *    - the first dense sample strictly after the trigger reads
	 *      600 - 980/60 = +583.7 cm/s, unambiguously positive for the
	 *      "did vZ ever go positive" direction gate. */
	float JumpImpulseZ = 600.0f;
};

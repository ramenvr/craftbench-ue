// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION for task gp-double-jump-stamina (agent-writable runtime
// module). A GameplayAbility tagged Ability.DoubleJump that, on activation:
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
	/** Power charged per activation. 20 is DISCLOSED by the prompt ("costs 20
	 *  Power, debited once per activation"), which is what makes this a lawful
	 *  absolute rather than an undisclosed magnitude.
	 *  PROPOSED - NOT YET MEASURED. */
	float PowerCost = 20.0f;

	/** Upward velocity (cm/s) the second jump sets on CharacterMovement.
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
	 *    - the smallest impulse that would merely touch that floor is
	 *      sqrt(2 * 980 * 20) = 198.0 cm/s, so 600 sits 3.0x above the cliff in
	 *      velocity terms and the margin degrades quadratically, not linearly;
	 *    - time to apex is 600 / 980 = 0.612 s, which at the fixture's
	 *      -FPS=60 dense sampling is ~37 samples inside the rising run. That
	 *      matters for the segmenter specifically: a rise only a handful of
	 *      samples long is exactly what MinDeltaZ absorption is designed to
	 *      swallow, and a 37-sample monotonic run cannot be mistaken for jitter;
	 *    - discretization: the sampled apex sits at most g*dt^2/2 =
	 *      980 / (2 * 3600) = 0.14 cm below the true apex -- 0.7% of the
	 *      20 cm floor, so sampling never eats the margin;
	 *    - the first dense sample strictly after the trigger reads
	 *      600 - 980/60 = +583.7 cm/s, unambiguously positive for the
	 *      "did vZ ever go positive" direction gate.
	 *
	 *  Chosen as a plausible jump velocity in its own right (the engine's stock
	 *  ACharacter JumpZVelocity is 420-700 across the templates), not tuned to a
	 *  bar. */
	float JumpImpulseZ = 600.0f;
};

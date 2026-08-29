// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT `no-gas/` -- ONE DELTA from ../../reference (this file
// pair only). AXIS: the second jump is implemented in the PAWN's Tick, with
// NOTHING ACTIVATABLE by tag. Defends PIN.md section 3 AG-1.
// EXPECTED: FAIL at DJ-1, last checkpoint, the FIRST final assertion.
// STATUS: UNVALIDATED / NOT YET RUN (no build, no PIE run, no grade).
//
// THE DELTA, in full: `GrantedAbilities.Add(UDoubleJumpAbility::StaticClass())`
// is removed from the constructor, and the second jump is re-implemented as a
// free-running Tick that -- once the character has been falling for a moment --
// debits 20 Power and reverses the descent, exactly once. The ability, tagged
// and correct, still SHIPS in this overlay byte-identical to the reference; it
// is simply never granted. That is precisely the shape AG-1 describes:
// "implement the second jump in the character movement component or on input,
// with nothing activatable by tag".
//
// WHY THE TICK IS NOT DECORATION. DJ-1 is the FIRST final assertion, so this
// variant would FAIL identically with a completely inert pawn. Shipping a
// WORKING second jump behind the Tick is what makes this an ANTI-GAMING row
// rather than a broken-submission row: a naive reading of the prompt ("the
// descent reverses and carries the character upward again, and it costs 20
// Power") is fully satisfied by this pawn on the film strip and in every number
// on the diagnostic line, and the ONLY thing it is missing is the
// activatable-ability contract. That is the discrimination this row buys, and
// it is the attribution claim to check first: the [DOUBLEJUMP-FINAL] line
// should read `granted=0 legOneActivated=0/1` NEXT TO a real rise and a real
// 60.0 -> 40.0 debit.
//
// TIMING. The auto-jump fires after AutoJumpDelay seconds of continuous falling,
// i.e. at world t ~= 0.8 s -- deliberately AFTER the fixture's Leg-1 trigger at
// t = 0.7 s, where the fixture has just preset Power to 60. So the debit reads
// 60.0 -> 40.0 and the rise sits inside the Leg-1 window, which is what makes
// the numbers look like a conforming solve. It is also AFTER the DJ-2a baseline
// read (which happens at the trigger, before anything else at that checkpoint),
// so the falling baseline this variant reports is the genuine free-fall.
// PROPOSED - NOT YET MEASURED: if the realized checkpoint crossing at cp1 drifts
// later than 0.8 s the auto-jump would precede the preset and the debit would
// read 100.0 -> 80.0 instead. That would change the LOGGED NUMBERS only -- DJ-1
// fires on `granted`, which no timing can move -- so the row's verdict is not at
// risk, only the prettiness of its evidence.
//
// PAWN-RESOLUTION CHECK (the thing to re-verify first if this row ever
// disagrees). The fixture overrides PreferredAbilityTag() = Ability.DoubleJump,
// so ResolveAgentPawnClass first looks for a candidate that GRANTS that tag.
// This variant grants nothing, so that preference finds no match and the
// resolver falls back to Candidates[0]
// (CraftBenchPawnFunctionalTest.cpp:68-140). Candidates are the CONCRETE NATIVE
// ACraftBenchCharacter subclasses, excluding ACraftBenchCharacter itself and
// every CLASS_Abstract class. Verified on disk at authoring time: the
// ThirdPerson substrate ships exactly one other subclass,
// ACraftBenchBareCharacter, and it is UCLASS(Abstract) -- so ADoubleJumpPawn is
// still the graded pawn and DJ-7 still passes on it at checkpoint 0 (the
// mannequin is untouched here). IF A FUTURE TASK COMMITS ANOTHER CONCRETE
// NATIVE SUBCLASS INTO Source/ThirdPerson/, RE-CHECK THIS ROW FIRST: enumeration
// order would then decide the fallback and this variant could start failing
// under a different name. (Same check, same wording of the risk, as
// gp-heal-over-time-cpp's and gp-glide-stamina-cpp's `no-gas/` notes.)
//
// EXPECTED NAMED FAIL (a literal run of the DJ-1 format string in
// DoubleJumpStaminaFunctionalTest.cpp -- the trailing granted count is a %d and
// is NOT part of the recorded substring):
//     no activatable ability tagged Ability.DoubleJump on the pawn (the second jump is not an activatable ability). granted=

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchCharacter.h"
#include "DoubleJumpPawn.generated.h"

UCLASS()
class ADoubleJumpPawn : public ACraftBenchCharacter
{
	GENERATED_BODY()

public:
	ADoubleJumpPawn();

	virtual void Tick(float DeltaSeconds) override;

private:
	/** Continuous falling time accumulated since the last time the character was
	 *  not falling. Reset on ground contact so the "one extra jump per airborne
	 *  period" reading is at least as generous as the reference's. */
	float AirborneSeconds = 0.0f;

	/** One-shot latch: the Tick jump fires exactly once per run. */
	bool bAutoJumpUsed = false;

	/** Falling time before the Tick jump fires. Chosen to land just after the
	 *  fixture's Leg-1 trigger at t = 0.7 s (see the header note).
	 *  PROPOSED - NOT YET MEASURED. */
	float AutoJumpDelay = 0.8f;

	/** Power charged by the Tick jump. Same 20 the reference charges -- the cost
	 *  axis is NOT what this variant breaks, and every Power gate must pass on it
	 *  for the row to be attributable to DJ-1.
	 *  PROPOSED - NOT YET MEASURED. */
	float PowerCost = 20.0f;

	/** Upward velocity the Tick jump assigns. Identical to the reference's, for
	 *  the same reason: the motion axis is not what this variant breaks.
	 *  PROPOSED - NOT YET MEASURED. */
	float JumpImpulseZ = 600.0f;
};

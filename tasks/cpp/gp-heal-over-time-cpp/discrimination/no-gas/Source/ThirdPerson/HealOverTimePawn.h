// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT `no-gas/` -- ONE DELTA from ../../reference (this file
// pair only). AXIS: Health moves on a schedule with NOTHING ACTIVATABLE behind
// it. Defends PIN.md section 3 AG-2.
// EXPECTED: FAIL at HOT-1, last checkpoint, first final assertion.
// STATUS: UNVALIDATED / NOT YET RUN (no build, no PIE run, no grade).
//
// THE DELTA, in full: `GrantedAbilities.Add(UHealOverTimeAbility::StaticClass())`
// is removed, and the restore is re-implemented as a free-running Tick that
// raises Health by a fixed amount once per second. The ability, the effect and
// the clamping attribute set all still SHIP in this overlay (byte-identical to
// the reference) -- they are simply never granted, which is exactly the shape
// AG-2 describes: "restore Health from Tick / BeginPlay with nothing
// activatable".
//
// WHY THE TICK IS NOT DECORATION. HOT-1 is the FIRST final assertion, so this
// variant would fail identically with an inert pawn. Shipping the Tick restore
// is what makes the row an ANTI-GAMING row rather than a broken-submission row:
// a naive reading of the prompt ("Health rises repeatedly for about five
// seconds, then stops") is fully satisfied by this pawn, and the ONLY thing it
// is missing is the activatable-ability contract. That is the discrimination
// this row buys.
//
// PAWN-RESOLUTION CHECK (the thing to re-verify first if this row ever
// disagrees). The fixture overrides PreferredAbilityTag() = Ability.HealOverTime,
// so ResolveAgentPawnClass first looks for a candidate that GRANTS that tag.
// This variant grants nothing, so that preference finds no match and the
// resolver falls back to Candidates[0]
// (CraftBenchPawnFunctionalTest.cpp, the "Legacy fallback" block). Candidates
// are the CONCRETE NATIVE ACraftBenchCharacter subclasses, excluding
// ACraftBenchCharacter itself and every CLASS_Abstract class. The ThirdPerson
// substrate ships exactly one other subclass, ACraftBenchBareCharacter, and it
// is UCLASS(Abstract) -- so AHealOverTimePawn is still the graded pawn and
// checkpoint 0 (HOT-0 + HOT-7) still passes on it. IF A FUTURE TASK COMMITS
// ANOTHER CONCRETE NATIVE SUBCLASS INTO THE SUBSTRATE, RE-CHECK THIS ROW FIRST:
// enumeration order would then decide the fallback and this variant could start
// failing under a different name. (Same check, same wording of the risk, as
// gp-glide-stamina-cpp/discrimination/MATRIX.md's `no-gas/` note.)
//
// EXPECTED NAMED FAIL (a literal run of the HOT-1 format string in
// HealOverTimeFunctionalTest.cpp -- the trailing granted count is a %d and is
// NOT part of the recorded substring):
//     no activatable ability tagged Ability.HealOverTime on the pawn (the restore is not an activatable ability). granted=
//
// Predicted diagnostic line 1: `granted=0 activated=0/3` with A1/A2/A3 rising
// normally -- i.e. the numbers show a working restore and the verdict names the
// missing contract, which is the attribution this row exists to prove.
// PREDICTED - NOT YET MEASURED.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchCharacter.h"
#include "HealOverTimePawn.generated.h"

UCLASS()
class AHealOverTimePawn : public ACraftBenchCharacter
{
	GENERATED_BODY()

public:
	AHealOverTimePawn(const FObjectInitializer& ObjectInitializer);

	/** THE DELTA. A free-running restore with no ability behind it. */
	virtual void Tick(float DeltaSeconds) override;

private:
	/** Seconds since the last restore step. */
	float SecondsSinceRestore = 0.0f;
};

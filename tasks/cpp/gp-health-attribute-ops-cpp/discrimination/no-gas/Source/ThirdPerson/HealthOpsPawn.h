// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT `no-gas/` for task gp-health-attribute-ops-cpp.
// Anti-gaming note AG-3 (PIN.md section 3): "change Health from a Tick or from
// BeginPlay with no ability granted, so the numbers move but nothing is
// activatable."
//
// THE ONE DELTA: GrantedAbilities is left EMPTY and Health is driven from Tick
// instead. Stage 1 is the reference verbatim (task base, contract set,
// InitHealth(100), mannequin mesh), and both ability classes are still compiled
// into the module -- they are simply never granted, so nothing is reachable by
// tag.
//
// EXPECTED: FAIL at the final checkpoint, HO-6, on the named substring
//   "no activatable ability tagged Ability.Damage on the pawn (health
//    operations not implemented as activatable abilities). granted="
// (the count after `granted=` spans a %d and is NOT part of the recorded
// literal). UNVALIDATED / NOT YET RUN -- see discrimination/MATRIX.md.
//
// THE POINT OF THE DRIFT RATE: 14.0 Health/s removes 9.8 Health per 0.7s
// window, so drop1 and drop2 both read ~9.8 -- almost exactly the reference's
// per-application magnitude of 10. The [HEALTHOPS-FINAL] line this variant
// emits therefore looks like a conforming solve on every numeric axis
// (HO-7/HO-8/HO-9 would all pass), and the ONLY thing separating it from the
// reference is `grantedDamage=0`. That is the strongest form of this variant:
// it proves HO-6 is what catches a non-ability implementation, rather than the
// numbers happening to come out wrong.
//
// THE `Health < MaxHealth` GUARD IN Tick IS LOAD-BEARING (same trap as
// `regen/`): checkpoints are anchored to ABSOLUTE world game-time
// (CraftBenchFunctionalTest.cpp:99-106) and the pawn is spawned in PrepareTest,
// ~0.5s of world time before checkpoint 0. An ungated 14 Health/s drift would
// have Health at ~93 by the time HO-3 reads it, and the variant would die at
// HO-3 -- a real FAIL at the wrong gate, masking the axis it was built to
// prove. With the guard, Health sits at exactly 100 until the fixture's own
// write probe and preset run inside checkpoint 0.
//
// RESOLUTION CHECK (this is the variant that needs it): with GrantedAbilities
// empty, no candidate grants PreferredAbilityTag() = Ability.Damage, so
// ResolveAgentPawnClass falls back to Candidates[0]
// (CraftBenchPawnFunctionalTest.cpp:138-148). AHealthOpsPawn is the only
// non-abstract native ACraftBenchCharacter subclass in the graded overlay --
// ACraftBenchBareCharacter is UCLASS(Abstract) and is skipped, and every other
// task's pawn lives in its own tasks/<id>/reference/ tree, not in the substrate
// -- so this pawn is still the graded one and checkpoint 0 stays green. If a
// future task commits a concrete ACraftBenchCharacter subclass INTO
// Source/ThirdPerson/, re-check this row first.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchBareCharacter.h"
#include "HealthOpsPawn.generated.h"

class UCraftBenchAttributeSet;

UCLASS()
class AHealthOpsPawn : public ACraftBenchBareCharacter
{
	GENERATED_BODY()

public:
	AHealthOpsPawn();

	/** THE DELTA. The reference does not override Tick at all. */
	virtual void Tick(float DeltaSeconds) override;

private:
	UPROPERTY()
	TObjectPtr<UCraftBenchAttributeSet> HealthAttributes;

	/** Tick-driven Health loss, Health per second. PROPOSED - NOT YET MEASURED.
	 *  14.0 removes 9.8 per 0.7s window -- see the header note on why the
	 *  numbers are deliberately made to look conforming. */
	static constexpr float HealthOpsDrainRate = 14.0f;
};

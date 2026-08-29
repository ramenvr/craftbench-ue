// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT `no-clamp/` -- ONE DELTA from ../../reference (this
// file pair only). AXIS: no cap enforcement at all, so the restore pushes
// Health straight past MaxHealth. Defends PIN.md section 3 AG-5 (first half).
// EXPECTED: FAIL at HOT-5, last checkpoint.
// STATUS: UNVALIDATED / NOT YET RUN (no build, no PIE run, no grade).
//
// THE DELTA, in full: BOTH clamp hooks are removed. PreAttributeChange and
// PostGameplayEffectExecute are no longer overridden and ClampHealth is gone,
// leaving an attribute set that is behaviorally identical to the provided
// UCraftBenchAttributeSet. The pawn still installs THIS class through
// SetDefaultSubobjectClass, so the overlay differs from the reference in
// exactly one file pair.
//
// WHY THE EMPTY SUBCLASS IS KEPT RATHER THAN DELETED. Deleting it would force a
// second edit in HealOverTimePawn.cpp (to drop the SetDefaultSubobjectClass
// call and its include), which is a second file pair and a second axis. Keeping
// the class and emptying it is the one-delta form, and it also matches how a
// real submission of this shape looks: the author knew a subclass was needed
// and did not know which hook to put the invariant in.
//
// PREDICTED TIMELINE. Leg 1 is UNAFFECTED -- the reference's restore never
// approaches the cap from a preset of 40 (40 -> 65), so A1 = 45.0, A2 = 50.0,
// A3 = 60.0, AStop = ATail = 65.0 exactly as the reference, and HOT-2, HOT-3
// and HOT-4 all pass on the reference's own numbers. The defect appears only in
// Leg 2, which presets 95 and applies the same 25:
//     base   95 -> 100 -> 105 -> 110 -> 115 -> 120
//     current tracks the base with nothing intercepting it -> 120
// so the dual read at trigger+5.1 returns current = 120.0 AND base = 120.0,
// both against MaxHealthRead = 100.0 with ClampEpsilon = 0.5. HOT-5 fires with
// 19.5 of margin.
//
// WHAT SEPARATES THIS ROW FROM ../current-only-clamp/. Both die at HOT-5, and
// HealOverTimeFunctionalTest.cpp holds exactly one FinishTest(Failed, ...) for
// that gate, so THE TWO ROWS SHARE ONE SUBSTRING -- see the ISOLATION CAVEAT in
// ../MATRIX.md. What tells them apart is the pair of numbers in the message:
// this row reads current=120.0 base=120.0 (nothing clamped), the sibling reads
// current=100.0 base=120.0 (the read-back was clamped and the stored value was
// not). Those digits sit behind %.1f placeholders, so no grep can match them --
// the separation is in the run, not in the string.
//
// EXPECTED NAMED FAIL (a literal run of the HOT-5 format string):
//     the restore pushed Health past its cap: current=
//
// PREDICTED - NOT YET MEASURED, every number above included.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchAttributeSet.h"
#include "HealOverTimeAttributeSet.generated.h"

UCLASS()
class UHealOverTimeAttributeSet : public UCraftBenchAttributeSet
{
	GENERATED_BODY()

	// THE DELTA: no PreAttributeChange override, no PostGameplayEffectExecute
	// override, no ClampHealth. Health is unbounded above.
};

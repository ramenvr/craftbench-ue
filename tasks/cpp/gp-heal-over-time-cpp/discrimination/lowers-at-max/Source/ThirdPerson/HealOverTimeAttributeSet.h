// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT `lowers-at-max/` -- ONE DELTA from ../../reference
// (this file pair only). AXIS: the "clamp" LOWERS Health when the character is
// already at full. Defends PIN.md section 3 AG-5 (second half -- the half that
// reads "or 'clamp' by SETTING Health to MaxHealth, which lowers it when
// already above").
// EXPECTED: FAIL at HOT-6, last checkpoint.
// STATUS: UNVALIDATED / NOT YET RUN (no build, no PIE run, no grade).
//
// WHY THIS ROW EXISTS AT ALL. Without it HOT-6 is the only gate in the fixture
// with ZERO committed coverage, and it is the gate the prompt's last sentence
// is written for ("Activating the ability while the character is already at
// full health must leave Health at 100: it must not push past it, and it must
// not lower it"). Note that HOT-6 can ONLY ever fire downward: HOT-5 runs
// first and already rejects anything above the cap, so a submission that
// reaches HOT-6 at all has been proven not to overshoot. A variant for this
// gate therefore has to be a clamp that UNDERSHOOTS.
//
// THE DELTA, in full: ClampHealth's upper bound goes GetMaxHealth() ->
// GetMaxHealth() - AtMaxHeadroomReserve, with the reserve set to 2.0. Both
// hooks are otherwise the reference's, byte-for-byte, and nothing else in the
// overlay changes.
//
// WHY A RESERVE IS A PLAUSIBLE-WRONG SOLVE RATHER THAN A CONTRIVANCE. "Leave a
// little headroom so an overheal has somewhere to go" is a shipped-game idiom,
// and it satisfies every sentence of the prompt EXCEPT the last one -- Health
// never exceeds MaxHealth, the restore is periodic, it stops, and it lands in
// the band. The single thing it gets wrong is that activating at full health
// pulls Health DOWN.
//
// PREDICTED TIMELINE (the effective cap is 100.0 - 2.0 = 98.0):
//   Leg 1 (preset 40, the reference's restore reaches 65): never meets the
//         reserve, so A1 = 45.0, A2 = 50.0, A3 = 60.0, AStop = ATail = 65.0 --
//         identical to the reference. HOT-2, HOT-3, HOT-4 all PASS.
//   Leg 2 (preset 95): the base climbs to 100 on the first execution, the
//         current write is clamped to 98.0, and PostGameplayEffectExecute
//         copies 98.0 back down onto the base. At trigger+5.1 the dual read is
//         current = 98.0, base = 98.0 -- BOTH under MaxHealthRead + 0.5, so
//         HOT-5 PASSES. That is deliberate: this row must not die at HOT-5 or
//         it would be a duplicate of ../no-clamp/.
//   Leg 3 (preset 100): the fixture writes the base to 100.0, the current
//         recompute is clamped to 98.0 on the spot, and the first execution
//         copies 98.0 onto the base too. At trigger+5.1 L3Current = 98.0.
//         |98.0 - 100.0| = 2.0 against AtMaxEpsilon = 0.5 -> HOT-6 FIRES with
//         1.5 of margin.
//
// THE RESERVE IS PINNED BY THE GATE PAIR IT HAS TO SIT BETWEEN:
//     > AtMaxEpsilon  = 0.5   so HOT-6 fires at all
//     small enough that Leg 1's peak of 65.0 never meets the effective cap,
//     which would flatten the rise steps and kill the row at HOT-2 instead
// 2.0 clears the first by 1.5 and the second by 33.0.
//
// EXPECTED NAMED FAIL (a literal run of the HOT-6 format string in
// HealOverTimeFunctionalTest.cpp -- the "100.0" in it is a LITERAL in the
// format string, not a placeholder, so the substring below is safe):
//     activating the restore at full health changed Health: 100.0 ->
//
// PREDICTED - NOT YET MEASURED, every number above included.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchAttributeSet.h"
#include "HealOverTimeAttributeSet.generated.h"

struct FGameplayEffectModCallbackData;

UCLASS()
class UHealOverTimeAttributeSet : public UCraftBenchAttributeSet
{
	GENERATED_BODY()

public:
	virtual void PreAttributeChange(const FGameplayAttribute& Attribute, float& NewValue) override;
	virtual void PostGameplayEffectExecute(const FGameplayEffectModCallbackData& Data) override;

private:
	/** Shared body of both hooks. THE DELTA lives here. */
	float ClampHealth(float Value) const;
};

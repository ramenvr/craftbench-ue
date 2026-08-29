// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT `current-only-clamp/` -- ONE DELTA from ../../reference
// (this file pair only). AXIS: the cap is enforced on the value the game READS
// and not on the value it STORES. Defends PIN.md section 3 AG-5 (first half),
// and it is the variant PIN.md section 4 calls "the one a real model writes".
// EXPECTED: FAIL at HOT-5, last checkpoint.
// STATUS: UNVALIDATED / NOT YET RUN (no build, no PIE run, no grade).
//
// THIS ROW IS WHY HOT-5's DUAL READ EXISTS. Without it, this submission passes
// the whole task with a health system that silently absorbs the next 20 points
// of damage: PawnAttribute() returns a clean 100.0 at every read while
// PawnAttributeBase() sits at 120.0. A clamp gate that reads only the current
// value is VACUOUS against precisely this shape, and this shape is the
// most-documented GAS clamp recipe there is. `no-clamp/` cannot substitute for
// this row -- it is caught by a current-only gate too.
//
// THE DELTA, in full: the PostGameplayEffectExecute override is removed.
// PreAttributeChange is kept, byte-for-byte, including its ClampHealth call;
// ClampHealth itself is kept and still reads GetMaxHealth(). Nothing else in
// the overlay changes.
//
// THE MECHANISM, READ OFF THE ENGINE SOURCE ON DISK. The reference's restore is
// a PERIODIC effect, so each execution writes into the BASE value through
// FActiveGameplayEffectsContainer::SetAttributeBaseValue. That function stores
// the base and then routes the recomputed value through
// FGameplayAttribute::SetNumericValueChecked, which calls
// Dest->PreAttributeChange(*this, NewValue) BY REFERENCE and only then does
// DataPtr->SetCurrentValue(NewValue)
// (UE_5.8/Engine/Plugins/Runtime/GameplayAbilities/Source/GameplayAbilities/
// Private/AttributeSet.cpp, FGameplayAttribute::SetNumericValueChecked). So a
// PreAttributeChange-only clamp intercepts the CURRENT write and never touches
// the stored base. PostGameplayEffectExecute is the hook that runs AFTER the
// execution has already moved the base, and it is the one this variant drops.
//
// PREDICTED TIMELINE. Leg 1 is UNAFFECTED (from a preset of 40 the restore
// reaches 65 and never meets the cap), so A1 = 45.0, A2 = 50.0, A3 = 60.0,
// AStop = ATail = 65.0 and HOT-2 / HOT-3 / HOT-4 all pass on the reference's
// own numbers. Leg 2 presets 95 and applies the same 25 in five executions:
//     base    95 -> 100 -> 105 -> 110 -> 115 -> 120     (nothing guards it)
//     current 95 -> 100 -> 100 -> 100 -> 100 -> 100     (PreAttributeChange)
// so the dual read at trigger+5.1 returns current = 100.0 and base = 120.0.
// current is INSIDE the cap and base is 20.0 over it, so HOT-5 fires on the
// SECOND half of its disjunction -- which is the half a current-only gate does
// not have.
//
// SUBSTRING COLLISION, DECLARED: this row and ../no-clamp/ both die at HOT-5,
// and HealOverTimeFunctionalTest.cpp holds exactly one FinishTest(Failed, ...)
// for that gate. See the ISOLATION CAVEAT in ../MATRIX.md. The runs separate
// them (current=100.0 base=120.0 here, current=120.0 base=120.0 there) but the
// digits sit behind %.1f placeholders and no grep can reach them.
//
// EXPECTED NAMED FAIL (a literal run of the HOT-5 format string):
//     the restore pushed Health past its cap: current=
//
// PREDICTED - NOT YET MEASURED, every number above included. Note that PIN.md
// section 4 traces this same solve to a base of ~115 rather than 120: the sheet
// sketched a +4-per-period effect and the committed reference ships +5, so the
// arithmetic here is the sheet's argument recomputed against the reference that
// actually exists.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchAttributeSet.h"
#include "HealOverTimeAttributeSet.generated.h"

UCLASS()
class UHealOverTimeAttributeSet : public UCraftBenchAttributeSet
{
	GENERATED_BODY()

public:
	/** Clamps the CURRENT value of Health to [0, MaxHealth]. Kept verbatim from
	 *  the reference. */
	virtual void PreAttributeChange(const FGameplayAttribute& Attribute, float& NewValue) override;

	// THE DELTA: no PostGameplayEffectExecute override. The stored base value is
	// left to accumulate past the cap.

private:
	float ClampHealth(float Value) const;
};

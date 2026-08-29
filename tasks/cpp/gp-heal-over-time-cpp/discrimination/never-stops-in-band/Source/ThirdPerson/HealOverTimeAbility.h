// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT `never-stops-in-band/` -- ONE DELTA from
// ../../reference (this file pair only). AXIS: a permanent regeneration hidden
// UNDERNEATH a perfectly conforming heal-over-time. Defends PIN.md section 3
// AG-4.
// EXPECTED: FAIL at HOT-3, last checkpoint.
// STATUS: UNVALIDATED / NOT YET RUN (no build, no PIE run, no grade).
//
// THIS IS THE ROW THAT PROVES THE OWNER EDIT OF 2026-08-10 WAS LOAD-BEARING.
// At the sheet's original StopEpsilon = 0.7 this submission passes ALL NINE
// GATES -- HOT-0, HOT-1, HOT-1c, HOT-2, HOT-3, HOT-4, HOT-5, HOT-6, HOT-7 --
// while shipping a health system that regenerates forever. At the pinned
// StopEpsilon = 0.25 it dies at HOT-3. That is a catch that did not exist
// before the edit, not merely a rename of one that did.
//
// READ ../never-stops/Source/ThirdPerson/HealOverTimeEffect.cpp FIRST. That
// sibling variant is the single-effect form of the same axis, and its header
// proves why a single permanent regeneration can NEVER clear HOT-3 and HOT-4
// together (the execution counts in the 2.1 s stop window and over the whole
// observation differ by a factor of only about 4.4, where about 14.3 would be
// needed). This variant is the shape that escapes that bound: it pays HOT-4
// with a SECOND, conforming effect.
//
// THE DELTA, in full: the ability applies TWO effects instead of one. The
// reference's UHealOverTimeEffect -- unchanged, still HasDuration 5.0 s /
// Period 1.0 s / +5.0, total 25 -- plus UHealOverTimeDripEffect, declared
// below: Infinite, Period 1.65 s, +0.6, which never ends. Every other file in
// the overlay is byte-identical to the reference, INCLUDING
// HealOverTimeEffect.{h,cpp}: the conforming restore is untouched, and the
// entire defect lives in the extra application.
//
// WHY THE DRIP CLASS LIVES IN THIS HEADER. Putting it in its own file pair, or
// adding it to HealOverTimeEffect.h, would make the overlay differ from the
// reference in two file pairs and blur which pair carries the axis. UHT accepts
// more than one UCLASS per header, so declaring it here keeps the delta to
// exactly HealOverTimeAbility.{h,cpp}.
//
// ---------------------------------------------------------------------------
// THE ARITHMETIC
// ---------------------------------------------------------------------------
// Fixture Leg 1 samples, as offsets from the trigger at t = 0.5:
//     A1 +1.1   A2 +2.6   A3 +4.1   AStop +7.1   ATail +9.2
// Conforming effect executes at +1, +2, +3, +4, +5 (five times, +5.0 each).
// Drip executes at +1.65, +3.30, +4.95, +6.60, +8.25, +9.90, ... (+0.6 each);
// the 0.50 s minimum clearance from every one of those to the nearest window
// boundary is derived in ../never-stops/'s header and is unchanged here.
//
// Health starts at the fixture's preset of 40.0:
//     A1    (+1.1) = 40 + 5*1 + 0.6*0 = 45.0
//     A2    (+2.6) = 40 + 5*2 + 0.6*1 = 50.6
//     A3    (+4.1) = 40 + 5*4 + 0.6*2 = 61.2
//     AStop (+7.1) = 40 + 5*5 + 0.6*4 = 67.4
//     ATail (+9.2) = 40 + 5*5 + 0.6*5 = 68.0
//
// Gate by gate, at BOTH values of StopEpsilon:
//     HOT-0  MaxHealth reads 100.0                          PASS (untouched)
//     HOT-7  mannequin assigned                             PASS (untouched)
//     HOT-1  granted = 1, activated 3 of 3                  PASS
//     HOT-1c the ability ends immediately, nothing refused   PASS
//     HOT-2  RiseStep1 = 5.6, RiseStep2 = 10.6  > 0.5       PASS
//     HOT-3  StopRise = 68.0 - 67.4 = 0.6
//              vs StopEpsilon 0.70 (sheet)   0.6 <= 0.70    PASS
//              vs StopEpsilon 0.25 (pinned)  0.6 >  0.25    FAIL   <-- expected
//     HOT-4  TotalRestored = 68.0 - 40.0 = 28.0 in [10,40]  PASS
//     HOT-5  Leg 2 presets 95; the reference clamp is intact
//            in BOTH hooks, so current = base = 100.0       PASS
//     HOT-6  Leg 3 presets 100; clamped, stays 100.0        PASS
//
// So the ONLY gate in the whole fixture that separates this submission from a
// conforming one is HOT-3, and it separates them only at 0.25.
//
// THE DRIP MAGNITUDE IS PINNED THE SAME WAY AS ../never-stops/'s. With exactly
// one drip execution in the stop window, the gain there is the magnitude
// itself, so it must satisfy 0.25 < m <= 0.70 for this row to make its claim in
// both directions; m = 0.6 sits 0.35 above the pinned bar and 0.10 below the
// old one. It does NOT need to clear RiseEpsilon on its own here -- the
// conforming effect carries HOT-2 -- which is exactly why this shape is more
// dangerous than the single-effect one: the drip can be made arbitrarily small
// and still defeat a 0.7 bar.
//
// EXPECTED NAMED FAIL (a literal run of the HOT-3 format string in
// HealOverTimeFunctionalTest.cpp):
//     the restore did not STOP after its duration: Health was still rising in the post-band stop window (AStop=
//
// SUBSTRING COLLISION, DECLARED: this is the SAME substring ../never-stops/ is
// expected to die on, because HealOverTimeFunctionalTest.cpp holds exactly one
// FinishTest(Failed, ...) for HOT-3 and both variants reach it. The two rows do
// not isolate at the substring level and ../MATRIX.md says so in an ISOLATION
// CAVEAT rather than pretending they do. What separates them is the RUN: their
// [HEALOVERTIME-FINAL] lines differ in every sample (A1 45.0 vs 40.0, ATail
// 68.0 vs 43.0, total 28.00 vs 3.00), and only this one would have PASSED the
// whole task at StopEpsilon = 0.7.
//
// PREDICTED - NOT YET MEASURED, every number in this header included.

#pragma once

#include "CoreMinimal.h"
#include "Abilities/GameplayAbility.h"
#include "GameplayEffect.h"
#include "HealOverTimeAbility.generated.h"

/**
 * THE DELTA. A permanent regeneration: Infinite duration policy, so nothing
 * ever removes it, restoring a small amount on a slow period. Applied to self
 * alongside the conforming restore, it is invisible to every gate except HOT-3.
 */
UCLASS()
class UHealOverTimeDripEffect : public UGameplayEffect
{
	GENERATED_BODY()

public:
	UHealOverTimeDripEffect();
};

UCLASS()
class UHealOverTimeAbility : public UGameplayAbility
{
	GENERATED_BODY()

public:
	UHealOverTimeAbility();

	virtual void ActivateAbility(
		const FGameplayAbilitySpecHandle Handle,
		const FGameplayAbilityActorInfo* ActorInfo,
		const FGameplayAbilityActivationInfo ActivationInfo,
		const FGameplayEventData* TriggerEventData) override;
};

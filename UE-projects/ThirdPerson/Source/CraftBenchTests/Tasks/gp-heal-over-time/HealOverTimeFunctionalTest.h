// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE -- DO NOT EDIT (policy: Source/CraftBenchTests/.AGENT_WRITE_DENY).
//
// AHealOverTimeFunctionalTest -- L2 fixture for task gp-heal-over-time
// ({-cpp,-bp}) on the ThirdPerson substrate. Implements
// tasks/bp-g2/gp-heal-over-time/PIN.md section 2 EXACTLY, including the
// binding "OWNER DECISION 2026-08-10 -- EDIT, then ACCEPTED" block at the end
// of that sheet (StopEpsilon 0.7 -> 0.25, with the corrected derivation).
// The PIN sheet is normative; this file does not redesign it.
//
// WHAT IS NEW HERE, AND WHY IT IS NEW
// ------------------------------------------------------------------------
// This is the FIRST consumer of the V1.4 dual attribute read
// (PawnAttribute / PawnAttributeBase, CraftBenchPawnFunctionalTest.h:170-191).
// HOT-5 -- the clamp gate -- is VACUOUS without it. A PreAttributeChange-only
// clamp (the recipe every GAS tutorial shows) writes CurrentValue only
// (AttributeSet.cpp:94-95), so a periodic restore executing into the BASE
// value leaves the read-back at a clean 100.0 while the stored base sits at
// ~115: the submission then silently absorbs the next 15 points of damage.
// A current-only clamp gate passes that submission. PIN.md section 4 shows the
// exact before/after pair and PIN.md section 2 calls the dual read "the whole
// point of the gate".
//
// SIGN-FLIPPED FROM POISON. The three-leg schedule below is the poison
// fixture's Leg A shape with the sign reversed (rise, not drop), re-using its
// CONGRUENT-WINDOW discipline: the two gated rise windows are both 1.5 s at
// equal offsets from the same trigger, so tick-count quantization affects both
// identically. See PoisonStackFunctionalTest.cpp:234-240 for why unequal
// windows made poison's stack cap ungateable until they were made congruent.
//
// WHAT THIS FIXTURE DELIBERATELY IS NOT. HOT-2 is a PURE DIRECTION PREDICATE
// with a noise floor -- NOT a rate bar. PIN.md section 2 ("Relative-vs-absolute
// accounting") applies owner decision Q5(b) prospectively: poison's
// PeriodicMinStep = 2.0 over a 1.5 s window is an UNDISCLOSED "> 1.33 HP/s"
// floor, and a perfectly conforming 1 HP/s restore fails it with a message
// describing something it did not do. That is the F5 defect class. HOT-2 asks
// only "is it still moving", so every conforming rate passes. Do not
// reintroduce a magnitude floor here.
//
// Overrides PreferredAbilityTag() = Ability.HealOverTime (PIN.md D5) so
// ResolveAgentPawnClass picks THIS task's pawn and never another committed
// ACraftBenchCharacter subclass by enumeration order
// (CraftBenchPawnFunctionalTest.cpp:134-144). D5 also records WHY the tag is
// new rather than reused: gp-health-attribute-ops already owns Ability.Heal,
// and PreferredAbilityTag must stay unique per GAS family (I1.1).
//
// DERIVATION BASE (PIN.md D2): this family derives from the GENERIC
// ACraftBenchCharacter, not ACraftBenchBareCharacter. Health is PRE-BUILT, so
// there is NO stage-1 ladder here and no derivation gate -- deliberately, so
// this task does not join the stage-1 correlation set with
// gp-poison-dot-stack and gp-health-attribute-ops (QUEUE.md constraint C1).
//
// EVERY NUMERIC BAR BELOW IS `PROPOSED - NOT YET MEASURED`. Bars in this repo
// are pinned by MEASURING and nothing in this family has been measured
// (PIN.md: "Status: nothing built. Every number below is PROPOSED - NOT YET
// MEASURED"). The two [HEALOVERTIME-FINAL] lines the last checkpoint emits are
// the calibration instrument: line 1 carries every raw sample and every
// computed value, line 2 carries the REALIZED window lengths so the congruence
// premise is MEASURED evidence in the log rather than an assumption in a
// comment.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchPawnFunctionalTest.h"
#include "HealOverTimeFunctionalTest.generated.h"

UCLASS()
class CRAFTBENCHTESTS_API AHealOverTimeFunctionalTest : public ACraftBenchPawnFunctionalTest
{
	GENERATED_BODY()

public:
	AHealOverTimeFunctionalTest(const FObjectInitializer& ObjectInitializer);

	virtual void PrepareTest() override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;
	virtual FGameplayTag PreferredAbilityTag() const override;

private:
	/** Index of the last scheduled checkpoint; the final asserts run there. */
	int32 LastCheckpointIndex = 9;

	// --- samples ---------------------------------------------------------------
	// All initialized to 0.0, NOT to a -1.0 sentinel. Health is UNCLAMPED in the
	// substrate attribute set (CraftBenchAttributeSet.h -- "no clamping ... at
	// v1.0"), so a real reading may legitimately be 0 or negative and any
	// sentinel would be ambiguous. Nothing gates on a sentinel: every gate runs
	// at the final checkpoint, by which time every sample has been taken.

	/** HOT-0: MaxHealth read at cp0, BEFORE any trigger and before any fixture
	 *  write. Also the value HOT-5 clamps against -- see the ClampEpsilon note. */
	double MaxHealthRead = 0.0;

	// Leg 1 (periodic + stop), trigger at cp0 (t=0.5):
	double A1 = 0.0;     // cp1 @ 1.6  = trigger+1.1
	double A2 = 0.0;     // cp2 @ 3.1  = trigger+2.6
	double A3 = 0.0;     // cp3 @ 4.6  = trigger+4.1  (last in-band sample)
	double AStop = 0.0;  // cp4 @ 7.6  = trigger+7.1  (stop window OPENS, past the band top)
	double ATail = 0.0;  // cp5 @ 9.7  = trigger+9.2  (stop window closes)

	// Leg 2 (clamp), trigger at cp6 (t=10.7), read at cp7 (t=15.8 = trigger+5.1):
	double L2Current = 0.0;  // PawnAttribute()     -- post-aggregator CURRENT value
	double L2Base = 0.0;     // PawnAttributeBase() -- the stored BASE value (V1.4)
	double L2MaxLive = 0.0;  // MaxHealth re-read at the same instant (DIAGNOSTIC ONLY)

	// Leg 3 (at-max no-op), trigger at cp8 (t=17.0), read at cp9 (t=22.1):
	double L3Current = 0.0;
	double L3Base = 0.0;     // reported in the HOT-6 message, NOT gated -- see below

	/** World game-time at which each checkpoint was actually crossed, appended in
	 *  OnCheckpoint. NOT gated on -- it is CALIBRATION EVIDENCE for the premise
	 *  HOT-2 and HOT-3 rest on. The checkpoint clock crosses on a tick boundary
	 *  (CraftBenchFunctionalTest.h, the checkpoint clock), so the realized windows
	 *  are the scheduled lengths plus at most one frame of jitter each, and the
	 *  second diagnostic line reports them so a reviewer can SEE the congruence of
	 *  the two 1.5 s rise windows rather than assume it. Proving that premise by
	 *  measurement is what closed it on gp-health-attribute-ops (T1.1). */
	TArray<double> CrossingTimes;

	// --- per-tag activation COUNTERS -------------------------------------------
	//
	// COUNTS, not an OR-ed latch. The base's bAbilityActivated
	// (CraftBenchPawnFunctionalTest.h:123) is a single latch across all tags and
	// across all activations, so it cannot tell "all three legs activated" from
	// "leg 1 activated and legs 2 and 3 were silently refused".
	//
	// This fixture triggers Ability.HealOverTime THREE times -- once per leg. UE
	// 5.8 refuses re-activation of an InstancedPerActor ability that is still
	// running (bRetriggerInstancedAbility defaults false), and of any ability
	// whose CommitAbility cooldown has not elapsed; in both cases
	// TryActivateAbilitiesByTag returns false having logged only at Verbose.
	// Those are idiomatic GAS shapes, not gaming. With a latch, a refused leg-2
	// activation surfaces as "the restore pushed Health past its cap" or as a
	// silent HOT-5 PASS on a submission whose clamp was never exercised -- a
	// verdict under a name describing something the submission did not do. This
	// is the HO-6c pattern and rationale, lifted from
	// HealthAttributeOpsFunctionalTest.h:98-112 / .cpp:311-334.
	int32 HealActivations = 0;
	int32 HealTriggerAttempts = 0;

	/** Surfaced as baseline=ok in the diagnostic; true once HOT-0 and HOT-7 have
	 *  both passed at cp0 and the Leg 1 preset has been written. */
	bool bBaselineOk = false;

	// --- constants -------------------------------------------------------------
	// EVERY value in this block is PROPOSED - NOT YET MEASURED. None of them may
	// be treated as calibrated until BOTH populations (conforming and violating)
	// are recorded in notes.md with the chosen bar and the margin on each side
	// (PIN.md section 6).

	/** HOT-0: the disclosed cap. The prompt states "MaxHealth is 100, and your
	 *  pawn must initialize MaxHealth to 100", which is what makes an ABSOLUTE bar
	 *  lawful here under TASK-AUTHOR-GUIDE.md section C. The literal "100" in the
	 *  HOT-0 message must be kept in step with this member if it is ever
	 *  re-pinned. PROPOSED - NOT YET MEASURED. */
	double MaxHealthExpected = 100.0;

	/** HOT-0 tolerance on a direct read-back at cp0. No effect has been applied
	 *  yet at that point, so this absorbs float noise only. Same shape and value
	 *  as the poison fixture's BaselineEpsilon (PoisonStackFunctionalTest.h:84).
	 *  PROPOSED - NOT YET MEASURED. */
	double MaxHealthEpsilon = 0.5;

	/** Leg 1 preset (PIN.md D4 -- "the single highest-risk calibration constraint
	 *  in the family").
	 *
	 *  40, far from BOTH boundaries, on purpose. The disclosed per-application
	 *  total is at most 40, so 40 + 40 = 80 < 100: no conforming solve can
	 *  saturate against the cap anywhere inside the HOT-2 rise window. If a later
	 *  edit moves this preset UP or widens the total band, a conforming restore
	 *  starts hitting the clamp mid-window, its steps go flat, and HOT-2 begins
	 *  false-FAILing conforming work under the name "the restore was not
	 *  periodic". The clamp is exercised by Leg 2, which is a SEPARATE leg with
	 *  its OWN preset -- that separation is the whole answer to F3's objection.
	 *  The literal "40.0" in the HOT-4 message must be kept in step with this.
	 *  PROPOSED - NOT YET MEASURED. */
	double HealthPreset = 40.0;

	/** Leg 2 preset (the clamp leg). 95 so that ANY conforming total in the
	 *  disclosed 10-40 band drives the restore INTO the cap: 95 + 10 = 105 > 100
	 *  even at the band floor, so the clamp is exercised by every conforming
	 *  magnitude, not just a generous one. PROPOSED - NOT YET MEASURED. */
	double ClampPreset = 95.0;

	/** Leg 3 preset (the at-max no-op leg). Exactly MaxHealth. The literal "100.0"
	 *  in the HOT-6 message must be kept in step with this. PROPOSED - NOT YET
	 *  MEASURED. */
	double AtMaxPreset = 100.0;

	/** HOT-2 noise floor. THIS IS NOT A RATE BAR -- read the "WHAT THIS FIXTURE
	 *  DELIBERATELY IS NOT" note at the top of this file before touching it. Each
	 *  of the two congruent 1.5 s rise windows must rise by strictly more than
	 *  this; the value exists only to separate a real restore tick from float
	 *  noise, and any conforming rate clears it. PROPOSED - NOT YET MEASURED. */
	double RiseEpsilon = 0.5;

	/** HOT-3 noise floor. 0.25.
	 *
	 *  OWNER EDIT 2026-08-10 (PIN.md, "OWNER DECISION 2026-08-10 -- EDIT, then
	 *  ACCEPTED"): was 0.7; the sheet's body derivation was wrong and this member
	 *  carries the corrected one. The correction is BINDING and the reasoning
	 *  below must stay quantified over ALL admissible periods -- assuming a tick
	 *  count is precisely the defect the edit fixes.
	 *
	 *  WHAT HOT-3 HAS TO DEFEAT. AG-4 is a PERMANENT regeneration that never
	 *  expires. Such a submission must still pass HOT-2, so with per-tick
	 *  magnitude m and period p it must satisfy nRise(p) * m > RiseEpsilon in
	 *  EACH of the two 1.5 s rise windows, i.e. m > RiseEpsilon / min(nRise(p)).
	 *  Across the 2.1 s stop window the same submission gains nStop(p) * m, so
	 *  HOT-3 has teeth for that period exactly while
	 *
	 *      StopEpsilon < (nStop(p) / min(nRise(p))) * RiseEpsilon,
	 *
	 *  and it has teeth against EVERY permanent regeneration only while
	 *
	 *      StopEpsilon < RiseEpsilon * min over all admissible p of
	 *                    ( nStop(p) / min(nRise(p)) ).
	 *
	 *  THE SHEET'S ORIGINAL 1.4 WAS THE WRONG QUANTITY. It came from the window
	 *  LENGTH ratio 2.1 s / 1.5 s -- reasoning as if tick density scaled
	 *  continuously with window length. IT DOES NOT: ticks are discrete, and a
	 *  period can be phased so that the longer window carries no more ticks than
	 *  the shorter one. Minimising nStop / min(nRise) over EVERY admissible period
	 *  on a 1 ms grid against THIS schedule gives a global minimum of exactly
	 *  1.000, and that minimum is ATTAINED -- e.g. period 0.576 s puts 3 ticks in
	 *  each 1.5 s rise window and 3 in the 2.1 s stop window.
	 *
	 *  So the lawful bound is StopEpsilon < 1.000 * RiseEpsilon = 0.50, and the
	 *  sheet's proposed 0.7 sat ABOVE it: a permanent regeneration tuned to the
	 *  slowest rate HOT-2 still admits leaves >= 0.5 of rise in the stop window,
	 *  and 0.5 <= 0.7 PASSES -- HOT-3 would not have defended AG-4 at all, in a
	 *  family authored specifically not to inherit that bug.
	 *
	 *  0.25 is midway between the conforming population (0.0 -- a restore that
	 *  actually stops leaves exactly zero rise in a window that opens PAST the
	 *  disclosed band top, so no legitimate expiry tick can land inside it) and
	 *  the 0.50 bound. Equal margin each side; the StackRatioMax form.
	 *
	 *  RE-PINNING LAW: this constant is COUPLED to RiseEpsilon and cannot be moved
	 *  independently. Changing RiseEpsilon, either rise window length, or the stop
	 *  window length invalidates the 1.000 factor and the whole minimisation must
	 *  be redone over the new schedule. PROPOSED - NOT YET MEASURED (both
	 *  populations still owed per PIN.md section 6). */
	double StopEpsilon = 0.25;

	/** HOT-5 tolerance on "Health never exceeds MaxHealth", applied to BOTH the
	 *  current and the base read. Absolute bar, lawful because the prompt
	 *  discloses the cap.
	 *
	 *  PIN.md section 6 requires this one to be measured against THREE solves --
	 *  the C++ PreAttributeChange + PostGameplayEffectExecute reference, a BP
	 *  magnitude-calculation lane, and a BP ability-loop lane -- because
	 *  calibrating it against the C++ reference alone is exactly how this gate
	 *  would false-FAIL a conforming BP solve (PIN.md D1). PROPOSED - NOT YET
	 *  MEASURED, and specifically NOT YET measured against any BP lane. */
	double ClampEpsilon = 0.5;

	/** HOT-6 noise floor, applied in BOTH directions to |L3Current - AtMaxPreset|:
	 *  activating at full health must neither push Health past MaxHealth nor lower
	 *  it. Separate from ClampEpsilon on purpose -- one constant doing two jobs is
	 *  the split that had to be made on gp-health-attribute-ops
	 *  (DirectionEpsilon vs IdleEpsilon) after re-pinning one over-constrained the
	 *  other. PROPOSED - NOT YET MEASURED. */
	double AtMaxEpsilon = 0.5;

	/** HOT-4: the DISCLOSED per-application total band ("each application must
	 *  restore a total of between 10 and 40 Health across its lifetime"). Lawful
	 *  as an absolute bar only because the prompt states it. HOT-4 exists so that
	 *  a non-conforming magnitude fails BY ITS OWN NAME instead of being
	 *  misattributed to HOT-2 or HOT-3 -- the F5 failure mode. The literal
	 *  "10-40" in the HOT-4 message must be kept in step with these two.
	 *  PROPOSED - NOT YET MEASURED. */
	double TotalRestoredMin = 10.0;
	double TotalRestoredMax = 40.0;
};

// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE -- DO NOT EDIT (policy: Source/CraftBenchTests/.AGENT_WRITE_DENY).
//
// AHealthAttributeOpsFunctionalTest -- L2 fixture for task gp-health-attribute-ops
// ({-cpp,-bp}) on the ThirdPerson substrate. Implements PIN.md section 2 exactly
// (tasks/bp-g2/gp-health-attribute-ops/PIN.md); the PIN sheet is normative and
// this file does not redesign it.
//
// ZERO NEW INFRA. Everything this fixture needs already exists:
//   - the stage-1 ladder (HO-1..HO-5) is LIFTED from
//     Tasks/gp-poison-dot-stack-bp/PoisonStackFunctionalTest.cpp:73-172 -- same
//     derivation gate, same presence gate, same init-100 read-before-write, same
//     write-probe at 37, same visible-character check, same named FAIL strings.
//     That deliberate reuse is what makes PIN.md constraint C1 binding (the two
//     tasks share a stage 1 and their stage-1 populations are correlated).
//   - the operation seam is a gameplay TAG, not a reflected function name
//     (PIN.md D1): NumGrantedAbilitiesWithTag / TriggerAbilityByTag, both already
//     on the base (CraftBenchPawnFunctionalTest.h:117,120).
//
// Single leg, no reset. Schedule {0.5, 1.2, 1.9, 2.6, 3.3} (PIN.md section 2):
//   cp0 @ 0.5  STAGE-1 LADDER (HO-1 derivation, HO-2 Health present, HO-3 init
//              100 read BEFORE any fixture write, HO-4 write-probe at 37, HO-5
//              visible mesh), then preset Health to 60 and trigger Ability.Damage.
//   cp1 @ 1.2  read (drop1 closes), trigger Ability.Damage again.
//   cp2 @ 1.9  read (drop2 closes), trigger Ability.Heal.
//   cp3 @ 2.6  read (healDelta closes).
//   cp4 @ 3.3  read -- IDLE window, nothing triggered (HO-11). Final asserts.
//
// WHY THE WINDOWS ARE CONGRUENT. HO-9 (drop2/drop1) and HO-10 (healDelta/drop1)
// are ratios, and a ratio of two windows of DIFFERENT length is not pinnable:
// tick-count quantization does not cancel and the same conforming implementation
// reads a different ratio depending on phase. That is exactly why the poison
// fixture could not gate its stack cap until its two rate windows were made
// congruent (PoisonStackFunctionalTest.h:107-116 and .cpp:234-240). Here
// (cp0,cp1], (cp1,cp2] and (cp2,cp3] are ALL 0.7 s at equal offsets from their
// triggers, so the ratios measure the per-application magnitude directly.
//
// Overrides PreferredAbilityTag() = Ability.Damage so the resolver picks THIS
// task's pawn and never another committed ACraftBenchCharacter subclass
// (CraftBenchPawnFunctionalTest.cpp:134-144 -- without it a foreign task's pawn
// can win purely by enumeration order). Poison does exactly this and the reason
// is in its task.md Hidden invariants.
//
// EVERY NUMERIC BAR BELOW IS `PROPOSED - NOT YET MEASURED`. Bars in this repo are
// pinned by MEASURING, and nothing here has been measured. The single
// [HEALTHOPS-FINAL] line the final checkpoint emits is the calibration
// instrument: it carries every raw sample and both ratios so the real population
// can be read off ONE run.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchPawnFunctionalTest.h"
#include "HealthAttributeOpsFunctionalTest.generated.h"

UCLASS()
class CRAFTBENCHTESTS_API AHealthAttributeOpsFunctionalTest : public ACraftBenchPawnFunctionalTest
{
	GENERATED_BODY()

public:
	AHealthAttributeOpsFunctionalTest(const FObjectInitializer& ObjectInitializer);

	virtual void PrepareTest() override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;
	virtual FGameplayTag PreferredAbilityTag() const override;

private:
	/** Index of the last scheduled checkpoint; the final asserts run there. */
	int32 LastCheckpointIndex = 4;

	// --- samples (all initialized to a sentinel that cannot be confused with a
	//     real reading: Health is UNCLAMPED in the substrate attribute set
	//     (CraftBenchAttributeSet.h:29-31 -- no clamping at v1.0), so a real
	//     reading may legitimately be 0 or negative. -1.0 would be ambiguous for
	//     the same reason, so nothing gates on the sentinel; the gates run only
	//     at the final checkpoint, by which time every sample has been taken.
	double InitRead = 0.0;       // HO-3: Health read BEFORE any fixture write
	double WriteProbeRead = 0.0; // HO-4: read-back of the 37 write probe
	double H0 = 0.0;             // cp0, after the preset, BEFORE the damage trigger
	double H1 = 0.0;             // cp1, BEFORE the second damage trigger
	double H2 = 0.0;             // cp2, BEFORE the heal trigger
	double H3 = 0.0;             // cp3
	double H4 = 0.0;             // cp4 (idle window closes)

	/** World game-time at which each checkpoint was actually crossed, appended in
	 *  OnCheckpoint. Not gated on -- it is CALIBRATION EVIDENCE for the premise
	 *  HO-9 and HO-10 rest on: the ratios are only pinnable because the three
	 *  gated windows are CONGRUENT. The checkpoint clock crosses on a tick
	 *  boundary, so the realized windows are the scheduled 0.7 s plus at most one
	 *  frame of jitter each, and the final diagnostic reports them so a reviewer
	 *  can see the congruence rather than assume it. */
	TArray<double> CrossingTimes;

	// --- per-tag activation latches. The base's bAbilityActivated
	//     (CraftBenchPawnFunctionalTest.h:123) is a SINGLE latch across all tags,
	//     so it cannot tell "damage activated but heal did not" from "both
	//     activated" -- and HO-6 has to name WHICH tag failed. Latched from the
	//     bool TriggerAbilityByTag returns (CraftBenchPawnFunctionalTest.cpp:313-326).
	// COUNTS, not latches (2026-08-10 review). The fixture triggers Ability.Damage
	// TWICE; an OR-ed latch cannot tell "both landed" from "the second was
	// silently refused", and UE 5.8 refuses re-activation of an InstancedPerActor
	// ability that is still running, or one whose cooldown has not elapsed,
	// by returning false with only a Verbose log. With a latch that submission
	// read Drop2=0 and was told "your damage is not a fixed amount" - a FAIL by
	// the wrong name, which is the F5 defect class this task exists to avoid.
	int32 DamageActivations = 0;
	int32 DamageTriggerAttempts = 0;
	bool bHealActivated = false;

	/** Surfaced as baseline=ok in the diagnostic; true once the stage-1 ladder passed. */
	bool bBaselineOk = false;

	// --- constants -------------------------------------------------------------
	// EVERY value in this block is PROPOSED - NOT YET MEASURED (PIN.md section 2:
	// "All bars: PROPOSED - NOT YET MEASURED"). None of them may be treated as
	// calibrated until both populations are recorded in notes.md with the chosen
	// bar and the margin on each side (PIN.md section 6).

	/** HO-3: stage-1 contract, Health initializes to 100. Disclosed by the prompt
	 *  ("initialized to 100"), which is what makes an ABSOLUTE bar lawful here
	 *  under TASK-AUTHOR-GUIDE.md section C. PROPOSED - NOT YET MEASURED. */
	double HealthInitExpected = 100.0;

	/** HO-3/HO-4 tolerance on a direct read-back (no drain can have run inside
	 *  checkpoint 0, so this absorbs float noise only). Lifted from the poison
	 *  fixture (PoisonStackFunctionalTest.h:84). PROPOSED - NOT YET MEASURED. */
	double BaselineEpsilon = 0.5;

	/** HO-4 write probe. != HealthInitExpected ON PURPOSE: an inert-write set that
	 *  happens to initialize at 100 would pass a 100-write vacuously (AG-2).
	 *  PROPOSED - NOT YET MEASURED. */
	double WriteProbeValue = 37.0;

	/** The value the fixture presets Health to at cp0, before the first damage.
	 *
	 *  60, NOT 100, on purpose (PIN.md D4, the anti-F3 discipline). It leaves
	 *  headroom BOTH ways for the whole leg: two damages of at most 25 each
	 *  (HO-8's band top) leave Health at >= 10, so a floor clamp cannot bite; and
	 *  one heal of at most 25 leaves Health at <= 85, so a MaxHealth ceiling
	 *  cannot saturate the heal. Either clamp would silently shrink healDelta or
	 *  drop2 and turn a CONFORMING implementation into a misattributed HO-9/HO-10
	 *  FAIL. Presetting to 100 would put the heal leg hard against the ceiling.
	 *  PROPOSED - NOT YET MEASURED. */
	double PresetHealth = 60.0;

	/** HO-8: the disclosed per-application magnitude band. Lawful as an ABSOLUTE
	 *  bar only because the prompt states it ("a fixed amount between 5 and 25").
	 *  HO-8 exists so a non-conforming magnitude fails BY NAME instead of being
	 *  misattributed to HO-9/HO-10 (PIN.md section 2, the F5 failure mode).
	 *  PROPOSED - NOT YET MEASURED. */
	double MagnitudeMin = 5.0;
	double MagnitudeMax = 25.0;

	/** HO-7 direction noise floor and HO-11 idle noise floor.
	 *  PROPOSED - NOT YET MEASURED. */
	// PROPOSED - NOT YET MEASURED. Split 2026-08-10: one constant was doing two
	// unrelated jobs - "is a real damage distinguishable from noise" (HO-7, over
	// a 0.7s window) and "is a passive drift distinguishable from noise" (HO-11,
	// over the idle window). They answer different questions over different
	// windows, so re-pinning either from a measured population over-constrained
	// the other. Reference measures Drop1=10.00 and idleDelta=0.00, so both have
	// enormous margin today.
	double DirectionEpsilon = 0.5;
	double IdleEpsilon = 0.5;

	/** HO-9: |drop2/drop1 - 1| must be within this. The two windows are congruent
	 *  (both 0.7 s), which is what makes the ratio pinnable at all.
	 *  PROPOSED - NOT YET MEASURED. */
	double RepeatTol = 0.10;

	/** HO-10: |healDelta/drop1 - 1| must be within this. Congruent windows again.
	 *  PROPOSED - NOT YET MEASURED. */
	double SymTol = 0.10;
};

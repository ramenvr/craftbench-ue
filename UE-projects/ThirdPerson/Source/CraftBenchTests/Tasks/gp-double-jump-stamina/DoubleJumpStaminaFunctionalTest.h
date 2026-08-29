// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE -- DO NOT EDIT (policy: Source/CraftBenchTests/.AGENT_WRITE_DENY).
//
// ADoubleJumpStaminaFunctionalTest -- L2 fixture for task
// gp-double-jump-stamina ({-cpp,-bp}) on the ThirdPerson substrate. Implements
// tasks/bp-g2/gp-double-jump-stamina/PIN.md section 2 EXACTLY, including the
// binding "OWNER DECISION 2026-08-10 -- EDIT, then ACCEPTED" block at the end of
// that sheet. The PIN sheet is normative; this file does not redesign it.
//
// WHAT THE OWNER DECISION CHANGED, AND WHAT IT ADDED
// ---------------------------------------------------------------------------
//   * DJ-6 ("only ONE extra jump per airborne period") is CUT. There is no
//     gate, no constant and no counter for it anywhere in this file, and AG-7 is
//     re-recorded upstream as an ARGUED note pointing at DJ-2c. Do not
//     reintroduce it without the extra prompt sentence the sheet priced it at:
//     a gate nobody can derive from the prompt is worse than no gate.
//   * MANDATORY ADDITION: the diagnostic must carry DescribeSegments(). It does,
//     on the second [DOUBLEJUMP-FINAL] line, for BOTH the Leg-1 window and the
//     full series. See "THE FIRST CONSUMER OF I1.4" below for why that line is
//     the most important output this fixture produces on its first run.
//
// THE FIRST CONSUMER OF I1.4 -- TREAT THE SAMPLER AS UNPROVEN
// ---------------------------------------------------------------------------
// SetDenseSampling / Segments / NumRises / MeanVerticalRate / DescribeSegments
// (CraftBenchPawnFunctionalTest.h, the I1.4 block) have NEVER EXECUTED. Zero
// callers across both substrates as of 2026-08-10. Neither have the five older
// reductions this file also uses (MaxVelocityZAfter in particular): only
// RecordSample has ever run, and only from the glide fixture's 9-point
// CHECKPOINT schedule. PIN.md D1 is explicit that this task is I1.4's first
// consumer and that the whole sampler must be treated as untested code.
//
// That is the entire reason the second diagnostic line exists and is mandatory.
// DJ-2c gates on a SEGMENT COUNT, and a segment count is a derived quantity: if
// the decomposition is wrong the gate is wrong SILENTLY, in either direction,
// and nothing in a PASS/FAIL verdict would say so. Printing the decomposition
// means a human reads what the segmenter actually saw on the first reference run
// instead of trusting it.
//
// WHY RiseEpsilon IS ALSO THE SEGMENTER'S MinDeltaZ (owner decision, endorsed)
// ---------------------------------------------------------------------------
// DJ-2c's noise floor is passed straight through as Segments()/NumRises()'
// MinDeltaZ, on purpose. That parameter is what ABSORBS APEX JITTER: the
// segmenter only closes a monotonic run when the run that would replace it has
// itself moved MinDeltaZ (CraftBenchPawnFunctionalTest.cpp, the Segments walk).
// Without that absorption ONE noisy sample at the apex splits a single jump into
// three segments -- rise, micro-fall, rise -- and NumRises reads 2 for ONE jump.
// That is a FALSE PASS on the exact axis DJ-2c exists to defend ("did it rise a
// SECOND time"), so the floor and the segmenter's tolerance must be the same
// number and must be re-pinned together. They are never independent constants.
//
// TWO LEGS, AND WHY THE ACTIVATION COUNTERS ARE PER-LEG
// ---------------------------------------------------------------------------
// This fixture triggers Ability.DoubleJump TWICE: once in Leg 1 (the jump + the
// cost) and once in Leg 2 (the refusal). The base's bAbilityActivated
// (CraftBenchPawnFunctionalTest.h) is a single OR-ed latch across every tag and
// every activation, so it cannot tell "Leg 1 activated" from "Leg 1 was silently
// refused and Leg 2 activated" -- and under that latch a Leg-1 refusal surfaces
// as DJ-2b "the ability produced no upward impulse", i.e. a motion defect
// reported for a submission whose actual fault is that the trigger never
// activated at all. So the counters are per leg (the HO-6c pattern and rationale,
// HealthAttributeOpsFunctionalTest.h / .cpp, lifted here).
//
// WHAT IS DELIBERATELY *NOT* LIFTED FROM HO-6c: its "every attempt must land"
// gate. Here it would be WRONG, and wrong in the unforgivable direction. Leg 2
// triggers at 5 Power against a 20 cost, where REFUSING is the CONFORMING
// answer and is precisely what DJ-4 is built to reward. A gate that failed a
// refused re-activation would contradict DJ-4 outright and hard-FAIL correct
// work. Only the LEG-1 counter is gated; the Leg-2 counts are reported in the
// diagnostic and read as evidence, never as a verdict.
//
// EVERY NUMERIC BAR BELOW IS `PROPOSED - NOT YET MEASURED`. PIN.md: "Status:
// nothing built. Every number below is PROPOSED - NOT YET MEASURED", and
// section 6 owes measured jitter populations for RiseEpsilon, PowerEpsilon,
// MinFallSpeed and CostTol with the margin on each side before this reaches G2.
// The two [DOUBLEJUMP-FINAL] lines are the calibration instrument: line 1 is
// every raw sample and every computed value, line 2 is the segment decomposition
// plus the REALIZED checkpoint spacing.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchPawnFunctionalTest.h"
#include "DoubleJumpStaminaFunctionalTest.generated.h"

UCLASS()
class CRAFTBENCHTESTS_API ADoubleJumpStaminaFunctionalTest : public ACraftBenchPawnFunctionalTest
{
	GENERATED_BODY()

public:
	ADoubleJumpStaminaFunctionalTest(const FObjectInitializer& ObjectInitializer);

	virtual void PrepareTest() override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

	/** PIN.md D5: prefer the pawn that GRANTS Ability.DoubleJump so a foreign
	 *  task's committed ACraftBenchCharacter subclass (glide, poison, health-ops,
	 *  heal-over-time) can never win resolution here by enumeration order
	 *  (CraftBenchPawnFunctionalTest.cpp, the ability-aware preference). */
	virtual FGameplayTag PreferredAbilityTag() const override;

private:
	/** Lowest Z among dense samples strictly after FromT; 0.0 when there are
	 *  none. DIAGNOSTIC/MESSAGE ONLY -- no gate branches on it; DJ-2c gates on the
	 *  segment count, and this only fills the "Z fell to %.0f" figure in its FAIL
	 *  message. There is no base-class reduction for "the minimum of the series"
	 *  (ApexDeltaZ answers the opposite question), so this reads the public sample
	 *  array directly rather than re-implementing any base machinery. */
	double MinZAfter(double FromT) const;

	/** Index of the last scheduled checkpoint; every gate runs there. */
	int32 LastCheckpointIndex = 9;

	/** Leg 1 fires here (t=0.7): read the falling baseline, preset Power, trigger. */
	int32 TriggerCheckpoint = 1;

	/** Leg 2 fires here (t=2.4): capture the Leg-1 reductions, then preset Power
	 *  to the refusal value and re-trigger. */
	int32 RefusalCheckpoint = 6;

	// --- realized times -------------------------------------------------------

	double TriggerTime = 0.0;         // world game-time of the Leg 1 trigger
	double RefusalTriggerTime = 0.0;  // world game-time of the Leg 2 trigger

	/** World game-time at which each checkpoint was actually crossed. NOT gated
	 *  on -- calibration evidence only, reported as the realized window lengths on
	 *  the second diagnostic line so the schedule's spacing is MEASURED in the log
	 *  rather than assumed in a comment (the line that proved the same premise on
	 *  gp-health-attribute-ops and gp-heal-over-time). */
	TArray<double> CrossingTimes;

	// --- Leg 1 motion ---------------------------------------------------------
	//
	// All four are captured AT THE LEG-2 CHECKPOINT, BEFORE the Leg-2 preset and
	// re-trigger. That is what windows them to Leg 1 without hand-rolling a
	// windowed variant of any base reduction: MaxVelocityZAfter(T), NumRises() and
	// DescribeSegments() all read the WHOLE sample series and have no upper time
	// bound, so evaluating them at the instant before Leg 2 starts makes the
	// series itself the window. (The base's Tick calls Super::Tick -- which fires
	// OnCheckpoint -- BEFORE appending that tick's dense sample, so the series at
	// cp6 ends one frame short of t=2.4 and cannot contain any Leg-2 motion.)

	double VZAtTrigger = 0.0;      // DJ-2a: live vZ read at the trigger, pre-trigger
	double MaxVZLegOne = 0.0;      // DJ-2b: MaxVelocityZAfter(TriggerTime), Leg-1-windowed
	int32  LegOneRises = 0;        // DJ-2c GATE INPUT: rises reaching into Leg 1
	/** DJ-4's refusal-rise bar as a FRACTION of the same run's Leg-1 jump.
	 *  PROPOSED - NOT YET MEASURED. Added by owner fix 2026-08-10 after the first
	 *  reference run false-FAILed on a +20 mid-fall blip against a +184 real jump
	 *  (11%). RiseEpsilon remains the absolute floor. */
	double RefusalRiseFactor = 0.50;

	/** DJ-2b2 ballistic-consistency slack. A rise produced by velocity v cannot
	 *  exceed v^2/2g; this is how far past that a conforming solve may read
	 *  before we call it a teleport. MEASURED populations on this schedule:
	 *  reference 1.00x, teleport/ 15.4x - 3.0 sits between them with 3x margin to
	 *  the conforming side and 5x to the gaming side. PROPOSED - re-pin if a
	 *  conforming solve using AddImpulse rather than a velocity set reads higher. */
	double BallisticSlackFactor = 3.0;

	/** Gravity used by the ballistic bound. UE's default; not a tunable. */
	double GravityCmPerS2 = 980.0;

	int32  LegOneRisesRaw = 0;     // NumRises(RiseEpsilon) unfiltered at cp6 -- EVIDENCE ONLY
	double LegOneRiseZ = 0.0;      // largest Leg-1 rise, cm (evidence)
	/** End time of the LARGEST qualifying Leg-1 rise. DJ-2d keys its
	 *  "and it came back down" search on this, so only motion after the
	 *  second jump's apex counts and the pre-trigger free-fall (which ends
	 *  before the trigger) is excluded by construction. -1 until set. */
	double LegOneRiseEndT = -1.0;
	double MinZLegOne = 0.0;       // DJ-2c message figure only
	FString LegOneSegmentsDesc;    // DescribeSegments(RiseEpsilon), Leg-1-windowed

	// --- Leg 2 motion ---------------------------------------------------------

	int32  LegTwoRises = 0;        // DJ-4 GATE INPUT: rises BEGINNING in Leg 2
	double LegTwoRiseZ = 0.0;      // largest such rise (the "Z climbed %.0f" figure)

	// --- Power ----------------------------------------------------------------

	double PowerAtTriggerRead = 0.0;  // read back immediately after the Leg-1 preset (evidence)
	double PowerFirstAfter = 0.0;     // cp2 @ 1.0 = trigger+0.3 -- DJ-3a/3b/3c "to" sample
	double PowerAtPlus12 = 0.0;       // cp5 @ 1.9 = trigger+1.2 -- DJ-3c window close
	double PowerLegTwoLast = 0.0;     // cp9 @ 3.3, the last Leg-2 reading (evidence)

	/** BASE-value companions to the two readings above, taken at the SAME instant.
	 *  EVIDENCE ONLY -- no gate reads either, and none may be added without the
	 *  sheet saying so.
	 *
	 *  They exist because every Power gate here reads the POST-AGGREGATOR CURRENT
	 *  value, and the V1.4 law in CraftBenchPawnFunctionalTest.h is explicit that a
	 *  current-only read can be silently wrong in both directions: a
	 *  PreAttributeChange clamp at 0 leaves the read-back at a clean 0.0 while the
	 *  stored base sits at -15, and an infinite/duration modifier moves the current
	 *  value while never touching the base. Either shape makes DJ-3b's debited
	 *  figure or DJ-4's "Power went negative" figure describe something other than
	 *  what the submission stored. Printing both is what makes that legible on the
	 *  first reference run instead of on the third adjudication. */
	double PowerFirstAfterBase = 0.0;
	double PowerLegTwoLastBase = 0.0;

	/** Lowest Power observed from the Leg-2 preset onward. Seeded to the sentinel
	 *  and set to RefusalPreset at the preset itself, so the "Power went negative"
	 *  half of DJ-4 can never fire off an unsampled leg: an un-run Leg 2 reads back
	 *  as the positive value the fixture wrote, which is not negative. */
	double MinPowerLegTwo = TNumericLimits<double>::Max();

	// --- per-leg activation counters (see the header note) --------------------

	int32 LegOneTriggerAttempts = 0;
	int32 LegOneActivations = 0;
	/** Leg-2 counts are EVIDENCE, NEVER A GATE. A refusal here is the conforming
	 *  answer (DJ-4), and it is additionally indistinguishable from an idiomatic
	 *  GAS re-trigger/cooldown refusal -- PIN.md D3 accepts that ambiguity in the
	 *  lenient direction on purpose. */
	int32 LegTwoTriggerAttempts = 0;
	int32 LegTwoActivations = 0;

	/** Surfaced as baseline=ok in the diagnostic; true once DJ-7 has passed at cp0. */
	bool bBaselineOk = false;

	// --- constants ------------------------------------------------------------
	// EVERY value in this block is PROPOSED - NOT YET MEASURED. None may be
	// treated as calibrated until BOTH populations (conforming and violating) are
	// recorded in notes.md with the chosen bar and the margin on each side
	// (PIN.md section 6).

	/** Spawn height. PIN.md section 2: "spawn at z=1200". High enough that the
	 *  pawn is genuinely falling by the trigger at t=0.7. PROPOSED - NOT YET
	 *  MEASURED against this task's map floor -- see the notes returned with this
	 *  change; if the pawn is not airborne at t=0.7 the run dies at DJ-2a, which
	 *  is the harness-sanity gate and reads as such. */
	double PawnSpawnZ = 1200.0;

	/** Leg-1 Power preset. 60 is comfortably above the disclosed 20 cost, so a
	 *  conforming solve cannot be gated by its own starting resource, and far
	 *  enough above it that a double debit (40) is still positive and therefore
	 *  still visible as a magnitude error at DJ-3b rather than as a refusal.
	 *  The literal "60.0" in the DJ-3b message must be kept in step with this.
	 *  PROPOSED - NOT YET MEASURED. */
	double PowerPreset = 60.0;

	/** Leg-2 Power preset -- strictly below the cost, which is the whole premise
	 *  of the refusal leg. The literal "5.0" in the DJ-4 message must be kept in
	 *  step with this. PROPOSED - NOT YET MEASURED. */
	double RefusalPreset = 5.0;

	/** DJ-3b: the DISCLOSED cost. This is the ONE real absolute in the whole
	 *  fixture and it is lawful under TASK-AUTHOR-GUIDE.md section C only because
	 *  the prompt says "costs 20 Power" in those words -- which is also the one
	 *  number the source CSV row itself specifies. The literals "20" and "20.0" in
	 *  the DJ-3b and DJ-4 messages must be kept in step with this. PROPOSED - NOT
	 *  YET MEASURED. */
	double CostExpected = 20.0;

	/** DJ-3b tolerance around the disclosed cost. Absorbs float noise and one
	 *  frame of a periodic implementation, not a different cost. PROPOSED - NOT
	 *  YET MEASURED. */
	double CostTol = 1.0;

	/** Noise floor for every Power direction predicate (DJ-3a "it decreased",
	 *  DJ-3c "it stopped decreasing", DJ-4 "it went negative"). A floor, not a
	 *  bar: it separates signal from jitter and must be pinned from measured
	 *  jitter under `-deterministic -FPS=60`, never chosen. Same shape and value
	 *  as the glide fixture's PowerEpsilon. PROPOSED - NOT YET MEASURED. */
	double PowerEpsilon = 0.5;

	/** DJ-2a: the pawn must be descending faster than this at the trigger. Pure
	 *  direction with a noise floor; this is HARNESS SANITY (PIN.md section 2
	 *  marks DJ-2a's anti-gaming column "--"), not a claim about the submission.
	 *  PROPOSED - NOT YET MEASURED. */
	double MinFallSpeed = 100.0;

	/** DJ-2c: minimum vertical travel for a rise to count as a rise -- AND the
	 *  segmenter's MinDeltaZ, passed through to Segments()/NumRises()/
	 *  DescribeSegments(). Read the "WHY RiseEpsilon IS ALSO THE SEGMENTER'S
	 *  MinDeltaZ" note at the top of this file before touching it: these are not
	 *  two constants that happen to be equal, and re-pinning one without the other
	 *  reintroduces the apex-split false PASS.
	 *
	 *  RE-PINNING HAZARD, BOTH DIRECTIONS. Too LOW and apex jitter splits one jump
	 *  into two rises (false PASS on the DJ-2c axis, and a spurious Leg-2 rise is
	 *  a false FAIL at DJ-4). Too HIGH and a conforming but gentle second jump --
	 *  the prompt fixes no jump height, deliberately (PIN.md, "Why there is no
	 *  'the second jump must reach height H' gate") -- rises less than the floor
	 *  and is failed for not jumping. The second direction is the unforgivable one
	 *  and is the reason this constant must be pinned against a MEASURED
	 *  population of conforming impulses, not against the reference alone.
	 *  PROPOSED - NOT YET MEASURED. */
	double RiseEpsilon = 20.0;

	/** Tolerance, in seconds, on WHICH LEG a segment boundary belongs to. NOT a
	 *  bar and not a physical quantity: the base fires OnCheckpoint from Tick
	 *  BEFORE appending that tick's dense sample, so the local extremum that bounds
	 *  a leg's rise can legitimately sit up to one frame on the wrong side of the
	 *  trigger's world time. At the runner's `-FPS=60` one frame is ~0.017 s;
	 *  0.10 s is several frames of headroom and still far shorter than the 1.7 s
	 *  gap between the two legs, so it cannot make one leg's motion reachable from
	 *  the other. PROPOSED - NOT YET MEASURED. */
	double SegmentBoundarySlack = 0.10;
};

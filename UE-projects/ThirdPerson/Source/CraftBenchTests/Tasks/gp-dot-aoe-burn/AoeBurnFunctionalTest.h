// Copyright CraftBench. All Rights Reserved.
//
// AAoeBurnFunctionalTest - L2 fixture for gp-dot-aoe-burn-{cpp,bp} (CSV 48).
// PIN of record: tasks/bp-g2/gp-dot-aoe-burn-cpp/PIN.md (G1-ACCEPTED 2026-08-11).
//
// THE FIRST WORLD-ACTING FAMILY. Every tier-1 fixture measures the agent's
// effect on the agent's OWN pawn; here the deliverable's effect lands on OTHER
// actors, and those targets are VERIFIER-OWNED: this fixture spawns them
// itself (instances of the committed generic ACraftBenchCharacter, which
// carries the contract attribute set), so a submission cannot pre-rig them.
// The novel graded axis is SPATIAL SELECTIVITY (gate AB-4): in one run, the
// target inside the area burns and the target outside must not move. No other
// gate in the corpus tests "affects A, spares B".
//
// THE CONTROL LANE (AB-0, verdict-neutral): a third, distant target receives
// the fixture's OWN V1.1 periodic drain (CraftBenchTestEffects::
// MakePeriodicAttributeDrain) at a known rate. It proves periodic GE execution
// works in THIS run's world before any gate judges the agent's periodicity -
// and per the V1.1 header's own warning (execute-on-application makes N
// seconds of a 1 s period N+1 executions), expected control totals are
// MEASURED here, never derived by arithmetic. A dead control is a HARNESS
// fault: the FAIL string is prefixed [HARNESS] so `cb discriminate` can never
// credit a leg on it and a human reading a report cannot mistake it for an
// agent failure.
//
// Targets are spawned in PrepareTest but PRESET at checkpoint 0 (in-world,
// after their BeginPlay) - the generic base's attribute defaults are not this
// fixture's contract, the preset is.
//
// Bars follow the tier-1 laws: StepEpsilon is a noise floor, not a rate bar;
// the stop bar obeys StopEpsilon < 1.0 x StepEpsilon (the T1.2 owner
// correction, adopted as-is); every absolute (per-window band, total band,
// duration band) is disclosed in the prompt (section C/F5). All constants below are
// PROPOSED - NOT YET MEASURED until the calibration runs pin them.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchPawnFunctionalTest.h"
#include "AoeBurnFunctionalTest.generated.h"

class ACraftBenchCharacter;

UCLASS()
class CRAFTBENCHTESTS_API AAoeBurnFunctionalTest : public ACraftBenchPawnFunctionalTest
{
	GENERATED_BODY()

public:
	AAoeBurnFunctionalTest(const FObjectInitializer& ObjectInitializer);

	virtual void PrepareTest() override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;
	virtual FGameplayTag PreferredAbilityTag() const override;

	// --- verifier-owned targets (spawned in PrepareTest) ---------------------
	// Committed generic base instances: ASC + contract attribute set, empty
	// GrantedAbilities (the base ships them empty, so targets grant nothing).
	// Distances are measured from the graded pawn's spawn point. The prompt
	// says "about five meters"; 3 m / 15 m leave generous margins on both
	// sides so no reasonable radius reading ever decides a verdict (G1 q1).
	UPROPERTY() TObjectPtr<ACraftBenchCharacter> TargetNear;
	UPROPERTY() TObjectPtr<ACraftBenchCharacter> TargetFar;
	UPROPERTY() TObjectPtr<ACraftBenchCharacter> TargetControl;
	/** EVIDENCE ONLY, added 2026-08-15 on owner request: a fourth target just
	 *  OUTSIDE a literal five-metre reading, sampled at every checkpoint and
	 *  printed, NEVER gated. Owner's ask was "two character, one inside and one
	 *  outside (slightly), and validate with taking gauge at their health at
	 *  each checkpoint".
	 *
	 *  It is not a gate on purpose. The prompt says "about five meters", and
	 *  gating a target 200 uu past 500 would make the agent's reading of
	 *  "about" decide a verdict for the first time in this family — the
	 *  existing 300/1500 uu geometry was chosen precisely so no radius reading
	 *  ever could. Logged evidence answers the question the owner actually
	 *  asked (does a nearest-only or single-overlap solve show up?) without
	 *  manufacturing a false-FAIL class, and a one-shot or nearest-only solve
	 *  still dies on AB-2/AB-3. If the logs later show real over-radius solves
	 *  passing, promoting this to a gate WITH a disclosed band in the prompt is
	 *  a small follow-up; the reverse is not, because a manufactured false FAIL
	 *  cannot be taken back out of runs already measured. */
	UPROPERTY() TObjectPtr<ACraftBenchCharacter> TargetEdge;

	double NearDistance = 300.0;     // uu - inside the disclosed ~5 m
	double FarDistance = 1500.0;     // uu - far outside it
	double ControlDistance = 3000.0; // uu - outside everything, control only
	double EdgeDistance = 700.0;     // uu - just outside a literal 5 m; EVIDENCE ONLY

	/** Current (post-aggregator) Health of a fixture-owned target. The graded
	 *  pawn keeps using the base-class PawnAttribute() family; this helper is
	 *  ONLY for the three targets this fixture owns. */
	static double TargetHealth(const ACraftBenchCharacter* Target);

	/** SetNumericAttributeBase on a fixture-owned target (same write the
	 *  tier-1 fixtures use on the graded pawn - V1.1's "world acts on the
	 *  player" note applies in reverse here: these writes are the fixture
	 *  acting on its OWN actors, which no agent code can intercept and no
	 *  gate ever reads as agent work). */
	static void SetTargetHealth(ACraftBenchCharacter* Target, double Value);

	// --- schedule -------------------------------------------------------------
	// {0.5, 1.87, 3.24, 4.6, 7.6, 9.7} - trigger at 0.5; in-band samples at
	// trigger+1.37/+2.74/+4.1, i.e. THREE EQUAL 1.37 s windows across the same
	// 4.1 s span; stop window (trigger+7.1, trigger+9.2], past the disclosed
	// 4-7 s duration band top.
	//
	// EQUALISED 2026-08-15 (FALSE_FAIL). The windows used to be 1.1/1.5/1.5,
	// while `D1 <= StepEpsilon || D2 <= ... || D3 <= ...` holds all three splits
	// to ONE threshold. A conforming per-second tick therefore had to clear the
	// same bar in a window 27% shorter than the other two, so the FIRST step was
	// the one that failed first — a defect of the schedule, not of the
	// submission. Equal windows make one threshold a fair test of all three.
	//
	// This BREAKS the byte-identity with gp-heal-over-time's spacing, which was
	// the old comment's stated reason for these numbers. That is the right trade:
	// heal-over-time's gate reads a different quantity, and matching its spacing
	// was never worth grading a correct burn as wrong. The stop machinery
	// (cp4/cp5) is untouched and stays comparable.
	//
	// Every other bar is deliberately unmoved: StepEpsilon, MeanRateMin/Max,
	// InBandSpanSeconds (still 4.1), StopEpsilon, TotalMin/Max.
	int32 LastCheckpointIndex = 5;
	double TriggerTime = 0.0;

	// --- samples --------------------------------------------------------------
	double N0 = 0.0;     // near, cp0 after preset+trigger
	double N1 = 0.0;     // cp1 @ 1.87
	double N2 = 0.0;     // cp2 @ 3.24
	double N3 = 0.0;     // cp3 @ 4.6 (last in-band sample)
	double NStop = 0.0;  // cp4 @ 7.6 (stop window opens)
	double NTail = 0.0;  // cp5 @ 9.7 (stop window closes)
	double FarMaxDeviation = 0.0; // max |preset - far| seen at ANY checkpoint
	// Edge target Health at cp0..cp3, evidence only (never compared to a bar).
	double E0 = 0.0, E1 = 0.0, E2 = 0.0, E3 = 0.0;
	double C0 = 0.0, CEnd = 0.0;  // control target, cp0 and cp5

	int32 BurnActivations = 0;
	int32 BurnTriggerAttempts = 0;

	// --- constants (PROPOSED - NOT YET MEASURED; G1-accepted 2026-08-11) ------
	double TargetPreset = 100.0;

	/** Noise floor for "a step happened" / "nothing happened". Same role and
	 *  value as the sibling families' RiseEpsilon/StepEpsilon. */
	double StepEpsilon = 0.5;

	/** Stop bar. MUST stay < 1.0 x StepEpsilon - the T1.2 law: the sheet's old
	 *  1.4x bound assumed tick density scales with window length; the correct
	 *  bound is 1.0x (minimum attained), and at a looser bar a permanent burn
	 *  passes the stop gate. */
	double StopEpsilon = 0.25;

	/** MEAN RATE band, gated over the WHOLE in-band burn span (trigger -> the
	 *  last in-band sample, a fixed 4.1 s by the schedule) - NOT per window.
	 *
	 *  MEASURED 2026-08-11, first calibration run, and this is why the
	 *  per-window form was thrown away: equal-DURATION windows do not hold
	 *  equal TICK COUNTS. The reference (5.0 per tick, 1.0 s period) measured
	 *  D1=5.00 D2=5.00 D3=10.00 - the 1.5 s windows D2 and D3 caught one tick
	 *  and two respectively, purely from phase. A per-window band would then
	 *  false-FAIL a CONFORMING 12-per-tick solve (D3 = 24 against a 15 top)
	 *  under a message claiming its rate was out of the disclosed band. That
	 *  is the F5 defect class exactly: an enforced literal that punishes work
	 *  the prompt permits. Same trap the heal-over-time family avoids by
	 *  keeping HOT-2 a pure direction predicate and gating magnitude only on
	 *  the total.
	 *
	 *  The enforced band is DELIBERATELY WIDER than the disclosed 3-15: phase
	 *  costs up to +/-1 tick out of ~5 over the span (~20%), so enforcing the
	 *  disclosed edge exactly would punish a solve sitting legitimately on it.
	 *  Enforcing LOOSER than disclosed can only ever miss a bad solve;
	 *  enforcing TIGHTER manufactures false FAILs - the asymmetry the F5 law
	 *  is about. A wildly wrong rate still dies here by name, and AB-6's
	 *  total band plus AB-5's stop window pin the rest. */
	double MeanRateMin = 2.0;
	double MeanRateMax = 20.0;

	/** The in-band span AB-3 divides by: trigger (cp0, 0.5) -> last in-band
	 *  sample (cp3, 4.6). Fixed by the schedule; a literal so the FAIL message
	 *  can never disagree with the arithmetic. */
	double InBandSpanSeconds = 4.1;

	/** Disclosed total band per application, preset -> NTail.
	 *
	 *  THE TOP IS DERIVED, NOT CHOSEN: it must be the product of the other two
	 *  disclosed bands' tops, or the prompt asks for something it then
	 *  punishes. MEASURED 2026-08-11 by the `conforming-fast` calibration
	 *  solve (12 per tick - squarely inside the disclosed 3-15 per second):
	 *  it burned 72.00 total and FAILed against an earlier 60.0 top, while
	 *  every other gate went green. Nothing was wrong with that solve; the
	 *  two disclosed bands simply could not both be satisfied - rate up to 15
	 *  for a duration up to 7 s is 105, not 60. A prompt whose own numbers
	 *  contradict each other is the F5 defect in its purest form, and no
	 *  amount of variant-writing finds it: only a CONFORMING solve at a
	 *  different point in the disclosed space does.
	 *
	 *  So: 3 x 4 = 12 floor, 15 x 7 = 105 ceiling. The gate is now a
	 *  consistency backstop against a wildly wrong magnitude; AB-3 (mean
	 *  rate) and AB-5 (stop window) do the real bounding. */
	double TotalMin = 12.0;
	double TotalMax = 105.0;

	// Control drain: known-rate periodic Health drain on TargetControl.
	// -2/tick at 1 Hz for 20 s (spans the run; the world ends before it does).
	double ControlPerTick = -2.0;
	double ControlPeriod = 1.0;
	double ControlDuration = 20.0;
};

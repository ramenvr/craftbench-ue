// Copyright CraftBench. All Rights Reserved.

#include "DoubleJumpStaminaFunctionalTest.h"

#include "CraftBenchGameplayTags.h"
#include "CraftBenchCharacter.h"
#include "CraftBenchAttributeSet.h"
#include "AbilitySystemComponent.h"
#include "Components/MeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"

ADoubleJumpStaminaFunctionalTest::ADoubleJumpStaminaFunctionalTest(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
}

// PIN.md D5: Ability.DoubleJump is ONE NEW native tag, landing in the runtime
// module's FCraftBenchGameplayTags alongside AbilityGlide / AbilityPoison /
// AbilityDamage / AbilityHeal / AbilityHealOverTime. It must be distinct from
// every one of them so PreferredAbilityTag stays unique per GAS family (I1.1):
// ResolveAgentPawnClass prefers the candidate that GRANTS an ability carrying
// this tag, so all five committed sibling pawns can sit in the same project
// without any of them winning resolution here by enumeration order.
FGameplayTag ADoubleJumpStaminaFunctionalTest::PreferredAbilityTag() const
{
	return FCraftBenchGameplayTags::AbilityDoubleJump();
}

double ADoubleJumpStaminaFunctionalTest::MinZAfter(double FromT) const
{
	double MinZ = 0.0;
	bool bAny = false;
	for (const FCraftBenchTrajectorySample& S : Samples)
	{
		if (S.T > FromT)
		{
			MinZ = bAny ? FMath::Min(MinZ, S.Location.Z) : S.Location.Z;
			bAny = true;
		}
	}
	return bAny ? MinZ : 0.0;
}

void ADoubleJumpStaminaFunctionalTest::PrepareTest()
{
	// Spawn high so the pawn is in a real, fast free-fall by the trigger at
	// t=0.7 -- the second jump is only meaningful from a fall, and DJ-2a asserts
	// that premise rather than assuming it.
	PawnSpawnLocation = FVector(0.0, 0.0, PawnSpawnZ);
	Super::PrepareTest(); // resolve (by Ability.DoubleJump) + spawn + possess

	// DENSE SAMPLING ON -- I1.4's FIRST EXECUTION ANYWHERE (PIN.md D1).
	//
	// This is not an optimisation, it is the only way DJ-2c is answerable. The
	// pre-existing reductions answer questions about the series as a WHOLE
	// (ApexDeltaZ is first-sample-to-global-peak; RoseThenFell is one bool for the
	// entire run), and even a correct "rose twice" reduction would alias away on
	// the 9-point CHECKPOINT schedule the sampler has ever run at: two vertical
	// reversals inside ~1.2 s simply are not visible at 0.3 s resolution. Dense
	// sampling records one sample per tick, so at the runner's -FPS=60 a jump
	// arc is ~70 samples instead of ~4.
	//
	// It is opt-in and default OFF precisely so that turning it on HERE changes
	// nothing for glide or poison (their series stay byte-identical and no
	// committed verdict can move -- I1.6's numeric-invariance check is a re-run,
	// not a re-calibration).
	//
	// CONSEQUENCE FOR THIS FILE: OnCheckpoint deliberately does NOT call
	// RecordSample. The dense path already samples every tick, and a second
	// append at the checkpoint instant would put two samples in the series at
	// (nearly) the same T for no gain.
	SetDenseSampling(true);

	// 10-checkpoint, TWO-LEG schedule -- PIN.md section 2, verbatim:
	//
	//   LEG 1 (the jump + the cost)
	//     0.4   DJ-7 (visible mesh); free-fall sample.
	//     0.7   DJ-2a baseline (live vZ, read BEFORE the trigger), preset Power
	//           to 60, trigger Ability.DoubleJump.
	//     1.0   trigger+0.3 -- first post-trigger Power sample (DJ-3a/3b "to",
	//           and DJ-3c's window OPEN).
	//     1.3 / 1.6
	//     1.9   trigger+1.2 -- DJ-3c's window CLOSE.
	//
	//   LEG 2 (the refusal -- DJ-4)
	//     2.4   capture every Leg-1 reduction FIRST, then preset Power to 5 and
	//           re-trigger.
	//     2.7 / 3.0
	//     3.3   last Leg-2 sample; all gates run here.
	//
	// WHY LEG 2 SITS 1.7 s AFTER THE LEG-1 TRIGGER (PIN.md D3). An ability with a
	// cooldown that also happens to block the Leg-2 re-trigger is indistinguishable
	// from a correct cost gate; that ambiguity is unavoidable and is accepted in
	// the LENIENT direction (it can only make DJ-4 pass, never fail). 1.7 s is the
	// sheet's pinned spacing. If calibration finds conforming solves using longer
	// cooldowns, DJ-4 must move to a FRESH FALL rather than tighten.
	//
	// SetCheckpointSchedule() auto-extends the failure TimeLimit to last +
	// TimeLimitMargin (3.3 + 2.0 = 5.3 s), so no separate time-limit change is
	// needed.
	//
	// Literal braces on purpose: the film-strip describer statically parses the
	// braced schedule literal out of this source for per-frame time labels (a
	// variable-built TArray would demote every label to index-only).
	SetCheckpointSchedule({0.4, 0.7, 1.0, 1.3, 1.6, 1.9,
	                       2.4, 2.7, 3.0, 3.3});
	LastCheckpointIndex = 9;
}

void ADoubleJumpStaminaFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	if (!Pawn.IsValid())
	{
		FinishTest(EFunctionalTestResult::Failed, TEXT("pawn did not spawn/resolve"));
		return;
	}

	// A MISSING ASC IS NOT FAILED HERE, DELIBERATELY (the glide fixture's rule).
	// DJ-1 already owns that failure by name ("no activatable ability tagged
	// Ability.DoubleJump on the pawn"), and stealing the FAIL here would report a
	// non-GAS submission under a generic harness-shaped name instead. Every write
	// below is guarded on ASC individually; every read goes through the base's
	// PawnAttribute(), which returns 0.0 rather than crashing when there is no
	// ability system. DJ-1 runs FIRST among the final gates, so no Power gate can
	// be reached on a pawn whose readings are meaningless.
	UAbilitySystemComponent* ASC = PawnASC();

	// Post-aggregator CURRENT value -- the V1.4 default, and what every Power gate
	// in this fixture reads. A base-only read would false-FAIL a cost implemented
	// as a duration or infinite modifier, which never touches the base.
	auto Power = [this]() -> double
	{
		return PawnAttribute(UCraftBenchAttributeSet::GetPowerAttribute());
	};
	// BASE value at the same instant. EVIDENCE ONLY -- see the header. Guarded
	// inside the base class against the ensure that fires on an ASC with no
	// matching attribute set, so a non-GAS pawn reads 0.0 here rather than zeroing
	// the whole fixture with an automation error.
	auto PowerBase = [this]() -> double
	{
		return PawnAttributeBase(UCraftBenchAttributeSet::GetPowerAttribute());
	};
	auto SetPower = [ASC](double V)
	{
		if (ASC != nullptr)
		{
			ASC->SetNumericAttributeBase(UCraftBenchAttributeSet::GetPowerAttribute(), static_cast<float>(V));
		}
	};

	const FGameplayTag JumpTag = FCraftBenchGameplayTags::AbilityDoubleJump();

	// Realized crossing time -- evidence only, no gate reads it.
	CrossingTimes.Add(TimeSeconds);

	if (CheckpointIndex == 0)
	{
		// DJ-7 -- VISIBLE-CHARACTER gate (AG-8; owner decision 2026-08-06, applied
		// to the whole glide/poison family, which this family inherits). The graded
		// pawn must carry a skeletal/static mesh component with a mesh actually
		// assigned, so a human reviewing the film strip can SEE the character.
		// Structural and deterministic. Same shape and the same message as
		// GlideStaminaFunctionalTest.cpp, PoisonStackFunctionalTest.cpp,
		// HealthAttributeOpsFunctionalTest.cpp and HealOverTimeFunctionalTest.cpp.
		// Visible-character gate — hoisted to the base class 2026-08-11. The
		// inlined copy this replaces (in FIVE fixtures) asserted only "a mesh
		// asset is assigned somewhere", so a mesh hidden in game or scaled to
		// nothing passed the gate that exists BECAUSE reps shipped pawns nobody
		// could see. See ACraftBenchPawnFunctionalTest::PawnVisiblyRepresented
		// for what is deliberately NOT asserted (asset path, mesh type, size).
		FString VisWhy;
		if (!PawnVisiblyRepresented(VisWhy))
		{
			FinishTest(EFunctionalTestResult::Failed, VisWhy);
			return;
		}
		bBaselineOk = true;
	}
	else if (CheckpointIndex == TriggerCheckpoint)
	{
		// ---- LEG 1: the falling baseline, then the preset + the trigger ----
		//
		// ORDER IS LOAD-BEARING. vZ is read FIRST, live, BEFORE anything is preset
		// or triggered: it is DJ-2a's whole input and it must describe the fall the
		// second jump is asked to reverse, not the state the ability left behind.
		// The glide fixture learned this the expensive way -- an instant-clamp
		// implementation logged vZ=-150 next to a gate input of 1208.7 at the same
		// checkpoint and the mismatch cost a manual adjudication.
		VZAtTrigger = Pawn->GetVelocity().Z;

		TriggerTime = TimeSeconds; // set unconditionally: the Leg-1/Leg-2 segment
		                           // split below is keyed on these two times, and a
		                           // zero here would misattribute Leg-1 rises.

		SetPower(PowerPreset);
		PowerAtTriggerRead = Power(); // read back -- evidence that the write landed

		++LegOneTriggerAttempts;
		if (TriggerAbilityByTag(JumpTag))
		{
			++LegOneActivations;
		}
	}
	else if (CheckpointIndex == 2)
	{
		// trigger+0.3. The "to" side of DJ-3a/DJ-3b, and DJ-3c's window OPEN.
		// 0.3 s after the activation so an instant debit has certainly landed and
		// a one-frame-late implementation is not mistaken for a free jump.
		PowerFirstAfter = Power();
		PowerFirstAfterBase = PowerBase(); // same instant; evidence only
	}
	else if (CheckpointIndex == 5)
	{
		// trigger+1.2. DJ-3c's window CLOSE.
		PowerAtPlus12 = Power();
	}
	else if (CheckpointIndex == RefusalCheckpoint)
	{
		// ---- capture every LEG-1 reduction, THEN start LEG 2 ----
		//
		// THIS ORDER IS THE WINDOW. MaxVelocityZAfter(T), NumRises() and
		// DescribeSegments() all read the WHOLE sample series and take no upper
		// time bound, so the only way to window them to Leg 1 without hand-rolling
		// a variant of each is to evaluate them at the last instant before Leg 2
		// can contribute a sample. The base's Tick runs Super::Tick (which fires
		// this callback) BEFORE appending the tick's own dense sample, so the
		// series here ends one frame short of t=2.4.
		//
		// The realized Leg-1 window is therefore (0.7, ~2.38] rather than the
		// sheet's (0.7, 1.9]. That is a SUPERSET, and only in the lenient
		// direction: the extra 0.5 s is post-apex free-fall, which can add a FALL
		// segment but not a RISE, and can only lower a maximum vertical velocity.
		MaxVZLegOne = MaxVelocityZAfter(TriggerTime);
		MinZLegOne = MinZAfter(TriggerTime);
		LegOneSegmentsDesc = DescribeSegments(RiseEpsilon);

		// NumRises() over the series as it stands -- EVIDENCE ONLY, never gated.
		// It is recorded because I1.4 has never executed and this is the cheapest
		// independent cross-check on the gate input computed just below: the two
		// must agree except for rises that ended BEFORE the trigger, and a
		// divergence with no such rise in the printed decomposition means the
		// segmenter is not doing what this file assumes.
		LegOneRisesRaw = NumRises(RiseEpsilon);

		// DJ-2c's GATE INPUT: rising segments that reach INTO Leg 1. Deliberately
		// not the unfiltered NumRises above -- dense sampling starts at spawn, so
		// the series also covers the pre-trigger free-fall, and a pawn that rose
		// BEFORE the trigger (an auto-jump on BeginPlay) would otherwise satisfy
		// "it rose a second time" without ever responding to the ability.
		//
		// The rule is `EndT > TriggerTime` (the rise reaches into the leg), NOT
		// `StartT >= TriggerTime`. The base fires this callback from Tick BEFORE
		// appending that tick's dense sample, so the local MINIMUM that opens the
		// jump's rise legitimately sits one frame before the trigger's world time,
		// and a start-keyed filter would drop the real jump and FALSE-FAIL
		// conforming work at DJ-2c. It cannot let a pre-trigger rise in: such a
		// rise ENDS before the trigger, and DJ-2a independently asserts the pawn
		// was still descending when the ability fired.
		//
		// THE PRINCIPLE, and it is why this leg's rule differs from Leg 2's below:
		// each leg gets the boundary rule whose error direction is toward PASS.
		// DJ-2c fails on the ABSENCE of a rise, so its window is inclusive; DJ-4
		// fails on the PRESENCE of one, so its window is exclusive.
		for (const FCraftBenchMotionSegment& Seg : Segments(RiseEpsilon))
		{
			if (Seg.bRising && Seg.DeltaZ() >= RiseEpsilon && Seg.EndT > TriggerTime)
			{
				++LegOneRises;
				if (Seg.DeltaZ() > LegOneRiseZ)
				{
					LegOneRiseEndT = Seg.EndT;   // DJ-2d searches for a fall after THIS
				}
				LegOneRiseZ = FMath::Max(LegOneRiseZ, Seg.DeltaZ());
			}
		}

		RefusalTriggerTime = TimeSeconds; // set unconditionally, as at Leg 1

		SetPower(RefusalPreset);
		// Seed the running minimum with the value we just WROTE, so the "Power went
		// negative" half of DJ-4 can never fire off a leg that was never sampled:
		// an unsampled Leg 2 reads back the positive preset, which is not negative.
		MinPowerLegTwo = RefusalPreset;

		++LegTwoTriggerAttempts;
		if (TriggerAbilityByTag(JumpTag))
		{
			++LegTwoActivations;
		}
	}
	else if (CheckpointIndex > RefusalCheckpoint)
	{
		// Leg-2 samples (2.7 / 3.0 / 3.3).
		const double P = Power();
		MinPowerLegTwo = FMath::Min(MinPowerLegTwo, P);
		PowerLegTwoLast = P;
		PowerLegTwoLastBase = PowerBase(); // same instant; evidence only
	}

	if (CheckpointIndex < LastCheckpointIndex)
	{
		return;
	}

	// ---- final assertions (DJ-1, DJ-2a/b/c, DJ-3a/b/c, DJ-4) -----------------
	//
	// NOTE ON DENOMINATORS: this fixture forms NO ratio and performs NO division.
	// Every gate below is either a direction/shape predicate with a noise floor
	// (DJ-2a, DJ-2b, DJ-2c, DJ-3a, DJ-3c, DJ-4) or an absolute bar against a
	// DISCLOSED number (DJ-3b's cost of 20). Seven of the eight are therefore
	// immune to the agent's choice of jump height or impulse strength, which is
	// PIN.md's "Relative-vs-absolute accounting" note applied literally: there is
	// no denominator here to guard, and none may be introduced without also
	// introducing the guard. The one division-shaped construct in the file is the
	// Window() lambda below, which subtracts two array entries and is
	// index-guarded rather than trusted. MeanVerticalRate's own division is
	// guarded inside the base class and its result is diagnostic only.

	const int32 Granted = NumGrantedAbilitiesWithTag(JumpTag);

	// DJ-4's GATE INPUT: rising segments that BEGIN in Leg 2. Filtering the base
	// segmenter's OUTPUT by time is what makes the second leg answerable at all --
	// Segments()/NumRises() have no time window, so a whole-series count cannot
	// tell a Leg-1 jump from a Leg-2 one. RiseEpsilon is passed as MinDeltaZ here
	// for the same reason it is everywhere else in this file: it is the apex-jitter
	// absorption, not a separate tolerance.
	//
	// START-keyed, the OPPOSITE of Leg 1's rule above, and for the same reason:
	// each leg gets the boundary rule whose error direction is toward PASS. DJ-4
	// FAILS on the presence of a rise, so a Leg-1 rise that somehow ran long must
	// not be able to leak in and fail a submission that never jumped twice.
	// SegmentBoundarySlack covers the one frame by which the local minimum opening
	// a genuine Leg-2 rise can precede the trigger's world time (see the header);
	// at 0.10 s it is orders of magnitude short of the 1.7 s between the legs, so
	// it cannot reach Leg 1's arc.
	for (const FCraftBenchMotionSegment& Seg : Segments(RiseEpsilon))
	{
		if (Seg.bRising
			&& Seg.DeltaZ() >= RiseEpsilon
			&& Seg.StartT >= RefusalTriggerTime - SegmentBoundarySlack)
		{
			++LegTwoRises;
			LegTwoRiseZ = FMath::Max(LegTwoRiseZ, Seg.DeltaZ());
		}
	}

	const int32 NumRisesAll = NumRises(RiseEpsilon);
	const FString FullSegmentsDesc = DescribeSegments(RiseEpsilon);

	// Sentinel-safe: MinPowerLegTwo is seeded at the Leg-2 preset, so this only
	// differs from it on a path where the preset never ran (no ASC), and it maps
	// to the positive preset -- never to a value that could read as "negative".
	const double MinPowerLegTwoShown =
		(MinPowerLegTwo == TNumericLimits<double>::Max()) ? RefusalPreset : MinPowerLegTwo;

	const double Debited = PowerPreset - PowerFirstAfter;          // DJ-3a / DJ-3b
	const double FurtherDrop = PowerFirstAfter - PowerAtPlus12;    // DJ-3c

	// Advisory rates over the two legs' first 0.6 s. Diagnostic ONLY -- no gate
	// reads either, deliberately: a rate bar would be an undisclosed magnitude
	// floor on a prompt that fixes no jump height (PIN.md, "Why there is no 'the
	// second jump must reach height H' gate"). They are here because I1.4 has
	// never executed and a second independent view of the same motion is what
	// makes a wrong decomposition legible.
	const double MeanRateLegOne = MeanVerticalRate(TriggerTime, TriggerTime + 0.6);
	const double MeanRateLegTwo = MeanVerticalRate(RefusalTriggerTime, RefusalTriggerTime + 0.6);

	// The predicates, computed BEFORE any gate fires, so the diagnostics can speak
	// about DJ-4's skip-vs-fail decision and every line survives a FAIL.
	const bool bLegOneRose = (LegOneRises >= 1);
	// OWNER FIX 2026-08-10, on the FIRST reference run: DJ-4's rise test is now a
	// RATIO against the same run's real jump, not the raw segmenter epsilon.
	//
	// MEASURED, and it FALSE-FAILED the conforming reference. Leg 1 jumped +184.
	// Leg 2 correctly refused - DoubleJumpAbility.cpp gates on
	// CurrentPower < PowerCost BEFORE both the debit and the impulse, and the run
	// confirms it: lastPowerLegTwo=5.0, nothing debited. Yet the series still
	// carried a +20 rise at t=2.77, mid-fall at -716 cm/s, which
	// `LegTwoRises >= 1` attributed to the ability and hard-FAILED with "the
	// ability fired without paying for it".
	//
	// A +20 blip is 11% of this run's actual jump. The absolute segmenter epsilon
	// cannot separate the two, and no absolute one can: it has to be small enough
	// to see a modest jump, which is small enough to catch physics jitter on a
	// fast fall. So use the pre-state this same run already measured - the repo's
	// standing preference for a ratio of a measured baseline over an absolute
	// magnitude, the same shape as glide's ResumeFactor fallback.
	//
	// The segmenter epsilon stays as a FLOOR so a run whose Leg 1 rise is tiny
	// cannot make the bar vanish.
	const double RefusalRiseBar =
		FMath::Max(RefusalRiseFactor * LegOneRiseZ, RiseEpsilon);
	const bool bLegTwoRose = (LegTwoRises >= 1) && (LegTwoRiseZ >= RefusalRiseBar);
	const bool bPowerWentNegative = (MinPowerLegTwoShown < -PowerEpsilon);

	// THE CALIBRATION INSTRUMENT, part 1. Every bar in PIN.md is PROPOSED - NOT
	// YET MEASURED, so this one line has to be enough to read the real population
	// off a SINGLE run: both legs' activation counts, every motion reduction, every
	// Power sample and every computed value. `maxVZtail` is the UNWINDOWED
	// MaxVelocityZAfter(TriggerTime) re-read here at the end; it is NOT gated on
	// and exists so that a divergence from the Leg-1-windowed `maxVZlegOne` is
	// visible -- the two differ exactly when Leg 2 produced upward velocity, which
	// is DJ-4's business and must never satisfy DJ-2b.
	UE_LOG(LogTemp, Display,
		TEXT("[DOUBLEJUMP-FINAL] granted=%d legOneActivated=%d/%d legTwoActivated=%d/%d "
		     "vZatTrigger=%.0f maxVZlegOne=%.0f maxVZtail=%.0f minZlegOne=%.0f "
		     "legOneRises=%d legOneRisesRaw=%d legTwoRises=%d risesAll=%d "
		     "legOneRiseZ=%.0f legTwoRiseZ=%.0f "
		     "powerPreset=%.1f powerAtTrigger=%.1f plus03=%.1f plus12=%.1f debited=%.2f furtherDrop=%.2f "
		     "refusalPreset=%.1f minPowerLegTwo=%.1f lastPowerLegTwo=%.1f "
		     "baseAtPlus03=%.1f baseLegTwoLast=%.1f "
		     "meanRateLegOne=%.0f meanRateLegTwo=%.0f triggerT=%.2f refusalT=%.2f"),
		Granted, LegOneActivations, LegOneTriggerAttempts, LegTwoActivations, LegTwoTriggerAttempts,
		VZAtTrigger, MaxVZLegOne, MaxVelocityZAfter(TriggerTime), MinZLegOne,
		LegOneRises, LegOneRisesRaw, LegTwoRises, NumRisesAll,
		LegOneRiseZ, LegTwoRiseZ,
		PowerPreset, PowerAtTriggerRead, PowerFirstAfter, PowerAtPlus12, Debited, FurtherDrop,
		RefusalPreset, MinPowerLegTwoShown, PowerLegTwoLast,
		PowerFirstAfterBase, PowerLegTwoLastBase,
		MeanRateLegOne, MeanRateLegTwo, TriggerTime, RefusalTriggerTime);

	// THE CALIBRATION INSTRUMENT, part 2 -- MANDATORY per the owner decision of
	// 2026-08-10: "log DescribeSegments() in the diagnostic line. I1.4 has never
	// executed -- this reference run is its first test as well as the task's, and
	// a wrong decomposition must be visible in the log rather than silently
	// mis-gating."
	//
	// Both decompositions are printed: the Leg-1-windowed one that DJ-2c actually
	// gated on, and the full-series one that DJ-4's Leg-2 filter was taken from.
	// Read them BEFORE believing any DJ-2c or DJ-4 verdict on the first runs.
	// What a WRONG decomposition looks like: one jump appearing as
	// RISE|FALL|RISE with a micro-FALL of a few cm at the apex (RiseEpsilon too
	// low -- a false PASS on DJ-2c and a possible false FAIL on DJ-4), or a real
	// second jump swallowed into one long FALL (RiseEpsilon too high -- a false
	// FAIL on DJ-2c against a gentle but conforming impulse).
	//
	// The w-values are the REALIZED checkpoint spacing, so the schedule's timing
	// premises (DJ-3c's trigger+0.3 -> trigger+1.2 window, and D3's 1.7 s Leg-1
	// to Leg-2 gap) are MEASURED evidence in the log rather than assumptions in a
	// comment. Index-guarded because a fixture that FinishTest(Failed)s early
	// never reaches here with a full array.
	auto Window = [this](int32 A, int32 B) -> double
	{
		return (CrossingTimes.IsValidIndex(A) && CrossingTimes.IsValidIndex(B))
			? (CrossingTimes[B] - CrossingTimes[A]) : 0.0;
	};
	UE_LOG(LogTemp, Display,
		TEXT("[DOUBLEJUMP-FINAL] baseline=%s samples=%d legOneSegments=%s fullSegments=%s "
		     "w1=%.3f w2=%.3f w3=%.3f w4=%.3f w5=%.3f w6=%.3f w7=%.3f w8=%.3f w9=%.3f "
		     "(bars PROPOSED - NOT YET MEASURED: riseEpsilon %.1f (== the segmenter's MinDeltaZ), "
		     "powerEpsilon %.2f, cost %.1f +/- %.2f, minFallSpeed %.0f, preset %.1f, refusalPreset %.1f, "
		     "segmentBoundarySlack %.2f)"),
		bBaselineOk ? TEXT("ok") : TEXT("unchecked"), Samples.Num(),
		*LegOneSegmentsDesc, *FullSegmentsDesc,
		Window(0, 1), Window(1, 2), Window(2, 3), Window(3, 4), Window(4, 5),
		Window(5, 6), Window(6, 7), Window(7, 8), Window(8, 9),
		RiseEpsilon, PowerEpsilon, CostExpected, CostTol, MinFallSpeed, PowerPreset, RefusalPreset,
		SegmentBoundarySlack);

	// DJ-4's SKIP-vs-FAIL decision, stated BEFORE the gates run so it is in the
	// log whichever way the verdict goes (PIN.md D3, endorsed verbatim by the
	// owner decision: "DJ-4's skip-vs-fail is right and must not be 'simplified'").
	if (bLegOneRose)
	{
		UE_LOG(LogTemp, Display, TEXT(
			"[DJ-REFUSE-DIAG] Leg 1 established a second rise (legOneRises=%d), so the refusal leg is "
			"HARD-GATED: at %.1f Power (below the %.1f cost) a rise (legTwoRises=%d, climbed %.0f) or a "
			"negative Power (%.1f) FAILs DJ-4. legTwoActivated=%d/%d - a REFUSED re-activation is "
			"CONFORMING here and is never failed: it is what the prompt asks for below the cost, and it is "
			"additionally indistinguishable from an idiomatic re-trigger/cooldown refusal, which PIN.md D3 "
			"accepts in the lenient direction on purpose."),
			LegOneRises, RefusalPreset, CostExpected, LegTwoRises, LegTwoRiseZ,
			MinPowerLegTwoShown, LegTwoActivations, LegTwoTriggerAttempts);
	}
	else
	{
		UE_LOG(LogTemp, Display, TEXT(
			"[DJ-REFUSE-DIAG] Leg 1 never established a second rise (legOneRises=%d at riseEpsilon=%.1f), so "
			"Leg 2 proves NOTHING about refusal - a run that cannot jump cannot demonstrate declining to "
			"jump. DJ-4 is SKIPPED, not failed. Failing it here would report a second-jump defect under a "
			"resource-gating name; DJ-2c below owns that failure by its own name."),
			LegOneRises, RiseEpsilon);
	}

	// DJ-1 -- the second jump is an ACTIVATABLE ABILITY, granted on the pawn and
	// reachable by tag. This is the AG-1 defense: a second jump implemented in the
	// character movement component or on input moves the character without ever
	// being activatable, and a pawn with no ability system at all lands here too
	// (which is why no earlier gate steals this FAIL).
	if (Granted < 1)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("no activatable ability tagged Ability.DoubleJump on the pawn (the second jump is not an "
			     "activatable ability). granted=%d"), Granted));
		return;
	}
	// PER-LEG counter, NOT the base's OR-ed latch (see the header note). The latch
	// is true if EITHER leg activated, so under it a silently-refused LEG-1
	// activation followed by a Leg-2 activation reads exactly like a working
	// submission -- and the run then dies at DJ-2b, "the ability produced no
	// upward impulse", describing a motion defect for a submission whose actual
	// fault is that the trigger never activated. Naming the refusal here is what
	// keeps DJ-2b/DJ-2c honest. Leg 2 has NO equivalent gate on purpose: a refusal
	// there is the conforming answer and is DJ-4's evidence, not a failure.
	if (LegOneActivations < LegOneTriggerAttempts)
	{
		FinishTest(EFunctionalTestResult::Failed, TEXT(
			"an ability tagged Ability.DoubleJump was granted but did NOT activate on TryActivateAbilitiesByTag"));
		return;
	}

	// DJ-2a -- HARNESS SANITY, not an anti-gaming gate (PIN.md section 2 marks its
	// anti-gaming column "--"): the pawn really was descending when the ability
	// was triggered. Direction plus a noise floor. If this fires, read the spawn
	// height and the map's floor before reading anything into the submission.
	if (!(VZAtTrigger < -MinFallSpeed))
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("no falling baseline: the character was not descending when the ability was triggered "
			     "(vZ=%.0f, need vZ < -%.0f). The second jump is only meaningful from a fall."),
			VZAtTrigger, MinFallSpeed));
		return;
	}

	// DJ-2b -- A REAL UPWARD IMPULSE. PURE DIRECTION, no magnitude at all: the
	// highest vertical velocity anywhere in the Leg-1 window must be positive.
	//
	// THIS IS THE FAMILY'S LOAD-BEARING DISCRIMINATOR (PIN.md section 4). The
	// plausible-wrong solve a real model writes is
	// LaunchCharacter((0,0,600), bZOverride=false), which ADDS to the existing
	// velocity: mid-fall at vZ=-780 that is -780+600 = -180, so the character
	// never goes upward at all while the ability activates, the tag is right, the
	// Power debit is perfect and the deliverable shape is right. It passes DJ-1,
	// DJ-2a, DJ-3a, DJ-3b, DJ-3c, DJ-4 and DJ-7 and dies only here. The same gate
	// catches a position teleport (which leaves vZ at whatever gravity produced)
	// and the reused glide answer (a merely slowed descent, vZ negative
	// throughout) -- AG-2 and AG-3.
	if (!(MaxVZLegOne > 0.0))
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("the ability produced no upward impulse: the highest vertical velocity after the trigger was "
			     "%.0f, never positive. A real second jump reverses the descent; a teleport leaves vZ at "
			     "whatever gravity produced."),
			MaxVZLegOne));
		return;
	}

	// DJ-2b2 -- BALLISTIC CONSISTENCY. Added by owner fix 2026-08-10 on the first
	// discrimination matrix, where `teleport/` PASSED the whole task.
	//
	// The comment above states the premise the gate was built on: "a teleport
	// leaves vZ at whatever gravity produced". MEASURED, that is simply FALSE for
	// SetActorLocation - the teleport variant recorded maxVZ = +194, comfortably
	// positive, so `MaxVZLegOne > 0` passed and the rise gate passed too (it rose,
	// by being moved). The variant authored to prove AG-2 proved instead that AG-2
	// was undefended.
	//
	// The discriminator is physics, not a tuned magnitude: a rise produced by an
	// upward VELOCITY cannot exceed v^2/2g. Measured on this very schedule -
	//     reference: v=600 -> v^2/2g = 184, and it rose 184.  ratio 1.00
	//     teleport : v=194 -> v^2/2g =  19, and it rose 293.  ratio 15.4
	// A displacement that outruns its own velocity by 15x is not a jump. The bar
	// sits between two MEASURED populations, which is the repo's calibration law,
	// and it is RELATIVE - it introduces no magnitude the prompt would have to
	// disclose, so it cannot become an F5-shaped undisclosed literal.
	const double BallisticRise = (MaxVZLegOne * MaxVZLegOne) / (2.0 * GravityCmPerS2);
	if (LegOneRiseZ > BallisticSlackFactor * BallisticRise)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("the second jump was not produced by an upward impulse: the character rose %.0f, but its "
			     "highest upward velocity of %.0f can only carry it %.0f (v^2/2g), and %.0f is more than "
			     "%.1fx that. Moving the character up without giving it the velocity to get there is a "
			     "teleport, not a jump."),
			LegOneRiseZ, MaxVZLegOne, BallisticRise, LegOneRiseZ, BallisticSlackFactor));
		return;
	}

	// DJ-2c -- A SEGMENTED SECOND RISE. PURE SHAPE: after the descent bottoms out,
	// Z must climb back by more than RiseEpsilon before the leg ends. This is the
	// gate I1.4 was built for, and RiseEpsilon is passed through as the
	// segmenter's MinDeltaZ so apex jitter is ABSORBED rather than read as extra
	// reversals (see the header note -- without that absorption one noisy sample
	// at the apex splits one jump into three segments and the count reads 2 for a
	// single jump). It catches the AG-2 variant DJ-2b cannot: a one-shot upward
	// velocity that is immediately cancelled, which shows a positive vZ sample but
	// no travel.
	if (!bLegOneRose)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("the character did not rise a second time: Z fell to %.0f and never climbed back by more "
			     "than %.1f before the leg ended. A one-shot upward velocity that is immediately cancelled, "
			     "or a slowed fall, looks like this."),
			MinZLegOne, RiseEpsilon));
		return;
	}

	// DJ-2d -- AND IT CAME BACK DOWN. Added 2026-08-11 (fixture audit).
	//
	// DJ-2c above asserts the character ROSE. Nothing asserted it then FELL, so a
	// submission that leaves the character suspended at the top passes it: set
	// `GravityScale = 0` (or zero the velocity and never restore it) and Z climbs
	// by more than RiseEpsilon and simply stays there. That is not a jump, it is
	// a levitation, and this task's own anti-gaming note AG-3 predicts a model
	// primed by the glide task is ACTIVELY LIKELY to reach for gravity
	// manipulation here.
	//
	// DELIBERATELY NOT `RoseThenFell`, though that helper reads like it was
	// written for this and has zero callers. It is a WHOLE-SERIES reduction —
	// first sample -> global peak -> last sample — and this fixture's series
	// spans BOTH legs plus the pre-trigger free-fall, so its one bool cannot say
	// anything about the second jump in particular. bp-g2-scaleup-plan.md F2
	// says exactly this ("Double-jump's 'rose a second time' is NOT free reuse"),
	// and reaching for it anyway would have re-made the mistake that plan
	// documents. The segmented machinery (I1.4) is the right instrument, and it
	// is what DJ-2c already uses.
	//
	// SAFE FOR CONFORMING WORK, checked against recorded data: the reference's
	// trace rises +184 and then falls 1292 -> 730 (-562), clearing a RiseEpsilon
	// bar by a wide margin. It re-reads the SAME sample series DJ-2c walks, so it
	// adds no checkpoint and cannot shift any timing-sensitive bar.
	bool bFellAfterRise = false;
	for (const FCraftBenchMotionSegment& Seg : Segments(RiseEpsilon))
	{
		// Keyed on the rise's END time, so only motion AFTER the second jump's
		// apex counts. The pre-trigger free-fall is excluded by construction:
		// it ends before the trigger, and LegOneRiseEndT is at or after it.
		if (!Seg.bRising && Seg.StartT >= LegOneRiseEndT && -Seg.DeltaZ() >= RiseEpsilon)
		{
			bFellAfterRise = true;
			break;
		}
	}
	if (!bFellAfterRise)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("the character rose a second time but never came back down: Z climbed %.0f "
			     "(rise ended t=%.2f) and no falling stretch of at least %.1f followed it before "
			     "the leg ended. A second JUMP is followed by a fall  -  cancelling gravity, or "
			     "holding the character up, is not a jump. Segments: %s"),
			LegOneRiseZ, LegOneRiseEndT, RiseEpsilon, *DescribeSegments(RiseEpsilon)));
		return;
	}

	// DJ-3a -- Power WAS DEBITED. Direction plus a noise floor; AG-4's first half
	// (a free double jump).
	if (!(Debited > PowerEpsilon))
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("the second jump cost no Power: Power went %.1f -> %.1f across the activation (delta %.2f). "
			     "The ability must debit the character's Power."),
			PowerPreset, PowerFirstAfter, Debited));
		return;
	}

	// DJ-3b -- THE COST IS EXACTLY 20. The ONE real absolute in this fixture, and
	// lawful under TASK-AUTHOR-GUIDE.md section C only because the prompt says
	// "costs 20 Power" in those words -- which is also the one number the source
	// row itself specifies. AG-4's second half (a cosmetic debit of the wrong
	// size). The literals "20" and "60.0" below are per PIN.md section 2; keep
	// them in step with CostExpected and PowerPreset if either is re-pinned.
	if (FMath::Abs(Debited - CostExpected) > CostTol)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("the second jump did not cost 20 Power: Power went 60.0 -> %.1f (debited %.1f, need 20.0 "
			     "+/- %.1f). The prompt fixes the cost at 20."),
			PowerFirstAfter, Debited, CostTol));
		return;
	}

	// DJ-3c -- ONE-SHOT, NOT A CONTINUOUS DRAIN. A pure "stopped changing"
	// predicate over (trigger+0.3, trigger+1.2], i.e. AFTER the debit has landed,
	// so a correct one-shot cost contributes nothing to this window. AG-5: a
	// per-tick drain while airborne technically "consumes stamina" and passes both
	// DJ-3a and (at the first sample) DJ-3b, and is caught only here.
	if (FurtherDrop > PowerEpsilon)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("the Power cost is a continuous drain, not a one-shot debit: Power kept falling after the "
			     "activation (%.1f at trigger+0.3 -> %.1f at trigger+1.2, further drop %.2f > %.2f). The cost "
			     "must be charged once per activation."),
			PowerFirstAfter, PowerAtPlus12, FurtherDrop, PowerEpsilon));
		return;
	}

	// DJ-4 -- REFUSAL BELOW THE COST. THE GATE THAT MAKES THIS TASK ABOUT A
	// RESOURCE COST RATHER THAN ABOUT A SUBTRACTION (AG-6): a submission that
	// debits Power but never gates on it fires at 5 Power and drives the resource
	// negative, and passes every gate above.
	//
	// SKIP-vs-FAIL, and it MUST NOT BE "SIMPLIFIED" (PIN.md D3, endorsed verbatim
	// by the owner decision 2026-08-10). It may hard-FAIL only when DJ-2c passed
	// on Leg 1. Below that condition a "did not rise" observation in Leg 2 proves
	// nothing about refusal -- the ability may simply not work -- and failing here
	// would report a second-jump defect under a resource-gating name. The
	// bLegOneRose guard is deliberately explicit rather than relying on DJ-2c's
	// early return above: the guard is the CONTRACT, the ordering is an accident
	// of layout, and a later reorder must not silently convert a skip into a FAIL.
	// The skip itself was already announced on the [DJ-REFUSE-DIAG] line.
	//
	// PIN.md D3's second, unavoidable ambiguity is accepted in the LENIENT
	// direction: an ability whose cooldown happens to block the Leg-2 re-trigger is
	// indistinguishable from a correct cost gate, and is passed. If calibration
	// finds conforming solves using longer cooldowns, this leg moves to a FRESH
	// FALL rather than tightening.
	if (bLegOneRose && (bLegTwoRose || bPowerWentNegative))
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("the ability fired without paying for it: with only 5.0 Power (below the 20 cost) the "
			     "character still rose a second time (Z climbed %.0f, against a bar of %.0f = %.2f x "
			     "this run's own %.0f jump) and/or Power went negative (%.1f). "
			     "Below the cost the ability must not fire."),
			LegTwoRiseZ, RefusalRiseBar, RefusalRiseFactor, LegOneRiseZ, MinPowerLegTwoShown));
		return;
	}

	// DJ-4b — IT CHARGED WITHOUT DELIVERING. Added 2026-08-11 (fixture audit).
	//
	// The gate above is a disjunction, and its Power half asks whether Power went
	// NEGATIVE (`MinPowerLegTwoShown < -PowerEpsilon`). That question is only
	// answerable when the debit is unclamped. A submission that writes
	//     SetPower(FMath::Max(0.0f, Current - Cost))
	// lands on exactly 0.0 with only 5.0 Power against a 20 cost — "not
	// negative", so that half is silent — and if its Leg-2 rise falls under
	// RefusalRiseBar the other half is silent too. It took the money and did not
	// deliver the jump, and passed.
	//
	// This is the glide DEFECT-2 shape: a magnitude/sign artefact standing in for
	// the property actually being asked about. "Below the cost the ability must
	// not fire" is about SPENDING, and the clamp only hides the sign.
	//
	// NOT hypothetical, and the closest thing to a proof this repo can offer: the
	// committed reference itself ships that clamp (reference/Source/ThirdPerson/
	// DoubleJumpAbility.cpp, `FMath::Max(0.0f, CurrentPower - PowerCost)`,
	// commented "belt-and-braces only -- the gate above already guarantees
	// CurrentPower >= PowerCost"). The exploit is the reference MINUS its cost
	// gate: delete one `if` and the clamp that was defensive becomes the thing
	// that hides the theft.
	//
	// SAFE FOR CONFORMING WORK, checked against recorded data before adding: the
	// reference refuses and leaves Leg-2 Power untouched at the 5.0 preset
	// (`minPowerLegTwo=5.0`, `lastPowerLegTwo=5.0` in discrimination/MATRIX.md),
	// so it clears this by the full 5.0. The unclamped variant reads -15.0 and is
	// caught by BOTH gates — placed after the disjunction so it keeps the older,
	// recorded FAIL message rather than silently changing which substring a
	// MATRIX row must match.
	if (bLegOneRose && (RefusalPreset - MinPowerLegTwoShown) > PowerEpsilon)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("the ability charged without delivering: with only %.1f Power (below the %.1f "
			     "cost) it did not produce a qualifying second jump (Z climbed %.0f, bar %.0f) "
			     "yet Power still fell to %.1f  -  %.1f was spent. Below the cost the ability "
			     "must not fire, which means it must not SPEND either; a debit clamped at zero "
			     "hides the charge, it does not undo it."),
			RefusalPreset, CostExpected, LegTwoRiseZ, RefusalRiseBar,
			MinPowerLegTwoShown, RefusalPreset - MinPowerLegTwoShown));
		return;
	}

	// All nine deterministic gates passed -- DJ-7 at cp0, DJ-1 / DJ-2a / DJ-2b /
	// DJ-2c / DJ-3a / DJ-3b / DJ-3c / DJ-4 here. DJ-6 is CUT (owner decision
	// 2026-08-10) and has no representation anywhere in this file. The base
	// finishes Succeeded after the last checkpoint.
}

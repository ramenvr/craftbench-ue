// Copyright CraftBench. All Rights Reserved.

#include "HealOverTimeFunctionalTest.h"

#include "CraftBenchGameplayTags.h"
#include "CraftBenchCharacter.h"
#include "CraftBenchAttributeSet.h"
#include "AbilitySystemComponent.h"
#include "Components/MeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"

AHealOverTimeFunctionalTest::AHealOverTimeFunctionalTest(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
}

// PIN.md D5: Ability.HealOverTime is ONE NEW native tag, landed in
// Source/ThirdPerson/CraftBenchGameplayTags.{h,cpp} alongside AbilityGlide /
// AbilityPoison / AbilityDamage / AbilityHeal. It is deliberately DISTINCT from
// gp-health-attribute-ops's Ability.Heal so PreferredAbilityTag stays unique per
// GAS family (I1.1): ResolveAgentPawnClass prefers the candidate that GRANTS an
// ability carrying this tag (CraftBenchPawnFunctionalTest.cpp:134-144), so the
// glide pawn, the poison pawn and the health-ops pawn can all be committed
// alongside this task's pawn without any of them winning resolution here purely
// by enumeration order.
FGameplayTag AHealOverTimeFunctionalTest::PreferredAbilityTag() const
{
	return FCraftBenchGameplayTags::AbilityHealOverTime();
}

void AHealOverTimeFunctionalTest::PrepareTest()
{
	PawnSpawnLocation = FVector(0.0, 0.0, 200.0); // the pawn need not move; nothing here samples motion
	Super::PrepareTest();                          // resolve (by Ability.HealOverTime) + spawn + possess

	// 10-checkpoint, THREE-LEG schedule -- PIN.md section 2, verbatim:
	//
	//   LEG 1 (periodic + stop)
	//     0.5   HOT-0 (MaxHealth, read BEFORE any trigger), HOT-7 (visible mesh),
	//           preset Health to 40, trigger Ability.HealOverTime.
	//     1.6   A1     = trigger+1.1
	//     3.1   A2     = trigger+2.6   <- (A1,A2] is a 1.5 s rise window
	//     4.6   A3     = trigger+4.1   <- (A2,A3] is a 1.5 s rise window, CONGRUENT
	//     7.6   AStop  = trigger+7.1   <- stop window OPENS, PAST the 4-7 s band top
	//     9.7   ATail  = trigger+9.2   <- stop window closes (2.1 s)
	//
	//   LEG 2 (clamp -- HOT-5)
	//    10.7   preset Health to 95, trigger.
	//    15.8   read CURRENT and BASE (trigger+5.1).
	//
	//   LEG 3 (at-max no-op -- HOT-6)
	//    18.1   preset Health to 100, trigger.
	//    23.2   read (trigger+5.1). Final asserts.
	//           (CORRECTED 2026-08-11: this said 17.0/22.1 while the schedule
	//           literal below has always shipped 18.1/23.2. No verdict moves --
	//           the trigger+5.1 offset the gates depend on is preserved -- but
	//           every film-strip label read off this comment was wrong.)
	//
	// WHY THE TWO RISE WINDOWS ARE CONGRUENT. HOT-2 compares two step sizes
	// against one shared noise floor, and HOT-3's lawful bound is derived from the
	// ratio of the stop window's tick count to the SMALLER of the two rise
	// windows' (see the StopEpsilon comment in the header). Both arguments assume
	// the two rise windows are the same length at equal offsets from the same
	// trigger, which is what makes the tick-count quantization identical in each.
	// Unequal windows are exactly what kept the poison fixture's stack cap
	// ungateable until they were made congruent
	// (PoisonStackFunctionalTest.cpp:234-240). The realized lengths are MEASURED
	// and logged on the second [HEALOVERTIME-FINAL] line so the premise is
	// evidence, not an assumption.
	//
	// WHY THE CLAMP LEGS ARE SEPARATE LEGS WITH THEIR OWN PRESETS (PIN.md D4).
	// F3's objection -- "a clamp saturates the periodic steps" -- is a SCHEDULE
	// problem, not a mechanism problem: it bites only if the periodic gate and the
	// clamp gate share a leg. Leg 1 starts at 40 and the disclosed total is at
	// most 40, so no conforming solve can reach 100 inside the HOT-2 window.
	//
	// Literal braces on purpose: the film-strip describer statically parses the
	// braced schedule literal out of this source for per-frame time labels (a
	// variable-built TArray would demote every label to index-only).
	SetCheckpointSchedule({0.5, 1.6, 3.1, 4.6, 7.6, 9.7,
	                       10.7, 15.8,
	                       18.1, 23.2});
	LastCheckpointIndex = 9;
}

void AHealOverTimeFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	if (!Pawn.IsValid())
	{
		FinishTest(EFunctionalTestResult::Failed, TEXT("pawn did not spawn/resolve"));
		return;
	}
	UAbilitySystemComponent* ASC = PawnASC(); // CraftBenchPawnFunctionalTest.h:113
	if (ASC == nullptr)
	{
		FinishTest(EFunctionalTestResult::Failed, TEXT("pawn has no AbilitySystemComponent"));
		return;
	}

	// Read the POST-AGGREGATOR CURRENT value for every rise/stop sample (the V1.4
	// law, CraftBenchPawnFunctionalTest.h:170-185): a restore implemented as a
	// duration or infinite modifier never touches the base value, so a base-only
	// read would false-FAIL a conforming implementation and report zero rise.
	// HOT-5 is the one gate that reads BOTH, and it must -- see its comment.
	auto Health = [&]() -> double
	{
		return PawnAttribute(UCraftBenchAttributeSet::GetHealthAttribute());
	};
	auto HealthBase = [&]() -> double
	{
		return PawnAttributeBase(UCraftBenchAttributeSet::GetHealthAttribute());
	};
	auto MaxHealth = [&]() -> double
	{
		return PawnAttribute(UCraftBenchAttributeSet::GetMaxHealthAttribute());
	};
	// The write side has no base-class helper; SetNumericAttributeBase is the same
	// call the poison and health-ops fixtures use
	// (PoisonStackFunctionalTest.cpp:66-69).
	auto SetHealth = [&](double V)
	{
		ASC->SetNumericAttributeBase(UCraftBenchAttributeSet::GetHealthAttribute(), static_cast<float>(V));
	};

	const FGameplayTag HoTTag = FCraftBenchGameplayTags::AbilityHealOverTime();

	// Record the REALIZED crossing time (world game-time -- the clock the base's
	// checkpoint loop reads). Evidence only; no gate reads it.
	CrossingTimes.Add(TimeSeconds);

	switch (CheckpointIndex)
	{
		case 0: // ---- HOT-0, HOT-7, then the Leg 1 preset + trigger ----
		{
			// HOT-0 -- MaxHealth initialized to 100. THIS RUNS FIRST, BEFORE ANY
			// TRIGGER AND BEFORE ANY FIXTURE WRITE (PIN.md D3, and it is the reason
			// D3 exists).
			//
			// MaxHealth ships UNINITIALIZED in UCraftBenchAttributeSet -- there is
			// no initializer anywhere in either substrate, so it reads 0. A pawn
			// that never sets it has a cap of zero, which clamps EVERY restore to
			// nothing: Leg 1 then shows no rise at all and, without this gate,
			// presents as "the restore was not periodic" -- a misattributed FAIL on
			// a submission whose only fault is one missing initializer. That is the
			// poison stage-1 lesson applied here, and it is why every later gate in
			// this fixture is allowed to assume a real cap.
			//
			// PawnAttribute() also returns 0.0 when the ASC carries no attribute set
			// exposing MaxHealth at all (CraftBenchPawnFunctionalTest.cpp:467-478).
			// That case is NOT given its own gate here: PIN.md D2 routes this family
			// through the GENERIC ACraftBenchCharacter, which pre-builds
			// UCraftBenchAttributeSet unconditionally (CraftBenchCharacter.cpp), so
			// an attribute-set-less pawn can only arise from a submission that
			// deliberately suppressed the subobject -- and the message below names
			// the 0 read and its consequence explicitly, so that submission is told
			// the truth rather than misattributed.
			MaxHealthRead = MaxHealth();
			if (FMath::Abs(MaxHealthRead - MaxHealthExpected) > MaxHealthEpsilon)
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(TEXT(
					"MaxHealth was not initialized: read %.1f, expected 100 (+/- %.2f). The cap the restore "
					"must respect is read from the pawn's own MaxHealth attribute; an uninitialized attribute "
					"reads 0 and would clamp every restore to zero."),
					MaxHealthRead, MaxHealthEpsilon));
				return;
			}

			// HOT-7 -- VISIBLE-CHARACTER gate (AG-7; owner decision 2026-08-06,
			// applied to the whole glide/poison family, which this family inherits).
			// The graded pawn must carry a skeletal/static mesh component with a mesh
			// actually assigned, so a human reviewing the film strip can SEE the
			// character. Structural and deterministic. Same shape and the same
			// message as PoisonStackFunctionalTest.cpp:143-172 and
			// HealthAttributeOpsFunctionalTest.cpp:176-205.
			{
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
			}

			// Leg 1 preset -- 40, far from BOTH boundaries (PIN.md D4; see the
			// HealthPreset comment in the header for what breaks if this moves).
			SetHealth(HealthPreset);
			bBaselineOk = true;
			++HealTriggerAttempts;
			if (TriggerAbilityByTag(HoTTag)) { ++HealActivations; }
			break;
		}
		case 1: A1 = Health(); break;     // trigger+1.1
		case 2: A2 = Health(); break;     // trigger+2.6 -- closes rise window 1
		case 3: A3 = Health(); break;     // trigger+4.1 -- closes rise window 2 (CONGRUENT)
		case 4: AStop = Health(); break;  // trigger+7.1 -- stop window OPENS, past the band top
		case 5: ATail = Health(); break;  // trigger+9.2 -- stop window closes

		case 6: // ---- LEG 2 (clamp): preset 95, trigger ----
			// 95 so that every conforming total in the disclosed 10-40 band drives
			// the restore INTO the cap (95 + 10 > 100 even at the band floor), which
			// is what makes HOT-5 non-vacuous for every conforming magnitude rather
			// than only for a generous one.
			SetHealth(ClampPreset);
			++HealTriggerAttempts;
			if (TriggerAbilityByTag(HoTTag)) { ++HealActivations; }
			break;
		case 7: // trigger+5.1 -- THE DUAL READ (V1.4). Both values, at the same instant.
			L2Current = Health();
			L2Base = HealthBase();
			L2MaxLive = MaxHealth(); // DIAGNOSTIC ONLY -- HOT-5 gates against MaxHealthRead
			break;

		case 8: // ---- LEG 3 (at-max no-op): preset 100, trigger ----
			SetHealth(AtMaxPreset);
			++HealTriggerAttempts;
			if (TriggerAbilityByTag(HoTTag)) { ++HealActivations; }
			break;
		case 9: // trigger+5.1 -- HOT-6 gates the CURRENT value; the base is reported.
			L3Current = Health();
			L3Base = HealthBase();
			break;

		default:
			break;
	}

	if (CheckpointIndex < LastCheckpointIndex)
	{
		return;
	}

	// ---- final assertions (HOT-1 .. HOT-6) ------------------------------------
	//
	// NOTE ON DENOMINATORS: this fixture forms NO ratio. Every gate below is
	// either a direction predicate with a noise floor (HOT-2, HOT-3, HOT-6) or an
	// absolute bar against a disclosed number (HOT-0, HOT-4, HOT-5), so there is
	// no denominator to guard -- deliberately, per PIN.md's "Relative-vs-absolute
	// accounting" note. The only division-shaped construct in the file is the
	// window lambda below, which subtracts two array entries and is index-guarded
	// rather than trusted.

	const int32 Granted = NumGrantedAbilitiesWithTag(HoTTag); // .h:117

	const double RiseStep1 = A2 - A1;        // over the first  1.5 s rise window
	const double RiseStep2 = A3 - A2;        // over the second 1.5 s rise window (CONGRUENT)
	const double StopRise = ATail - AStop;   // over the 2.1 s stop window
	const double TotalRestored = ATail - HealthPreset; // HOT-4: preset(40) -> ATail

	// THE CALIBRATION INSTRUMENT, part 1. Every bar in PIN.md is PROPOSED - NOT
	// YET MEASURED, so this one line has to be enough to read the real population
	// off a SINGLE run: the cap read, every raw sample from all three legs, every
	// computed value, and the activation counts. Emitted BEFORE the gates so it
	// survives a FAIL.
	UE_LOG(LogTemp, Display,
		TEXT("[HEALOVERTIME-FINAL] granted=%d activated=%d/%d maxHealth=%.1f preset1=%.1f "
		     "A1=%.1f A2=%.1f A3=%.1f AStop=%.1f ATail=%.1f "
		     "total=%.2f riseStep1=%.2f riseStep2=%.2f stopRise=%.2f "
		     "L2cur=%.1f L2base=%.1f L2maxLive=%.1f L3cur=%.1f L3base=%.1f"),
		Granted, HealActivations, HealTriggerAttempts, MaxHealthRead, HealthPreset,
		A1, A2, A3, AStop, ATail,
		TotalRestored, RiseStep1, RiseStep2, StopRise,
		L2Current, L2Base, L2MaxLive, L3Current, L3Base);

	// THE CALIBRATION INSTRUMENT, part 2 -- the REALIZED window lengths, so the
	// congruence premise HOT-2 and HOT-3 both rest on is MEASURED evidence in the
	// log rather than an assumption in a comment. (This is the line that proved
	// the same premise on T1.1, gp-health-attribute-ops.) w2 and w3 are the two
	// rise windows and must read the same to within one frame; w5 is the 2.1 s
	// stop window whose tick count the StopEpsilon derivation is quantified over.
	// Index-guarded because a fixture that FinishTest(Failed)s early never reaches
	// here with a full array.
	auto Window = [this](int32 A, int32 B) -> double
	{
		return (CrossingTimes.IsValidIndex(A) && CrossingTimes.IsValidIndex(B))
			? (CrossingTimes[B] - CrossingTimes[A]) : 0.0;
	};
	UE_LOG(LogTemp, Display,
		TEXT("[HEALOVERTIME-FINAL] baseline=%s w1=%.3f w2=%.3f w3=%.3f w4=%.3f w5=%.3f "
		     "w6=%.3f w7=%.3f w8=%.3f w9=%.3f "
		     "(congruent rise pair = w2,w3; stop window = w5; bars PROPOSED - NOT YET MEASURED: "
		     "riseEpsilon %.2f, stopEpsilon %.2f, clampEpsilon %.2f, atMaxEpsilon %.2f, "
		     "maxHealthEpsilon %.2f, total band %.0f-%.0f)"),
		bBaselineOk ? TEXT("ok") : TEXT("unchecked"),
		Window(0, 1), Window(1, 2), Window(2, 3), Window(3, 4), Window(4, 5),
		Window(5, 6), Window(6, 7), Window(7, 8), Window(8, 9),
		RiseEpsilon, StopEpsilon, ClampEpsilon, AtMaxEpsilon,
		MaxHealthEpsilon, TotalRestoredMin, TotalRestoredMax);

	// HOT-1 -- the restore is an ACTIVATABLE ABILITY, granted on the pawn and
	// reachable by tag. This is the AG-2 defense: an implementation that raises
	// Health from Tick or BeginPlay moves the number without ever being
	// activatable.
	if (Granted < 1)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("no activatable ability tagged Ability.HealOverTime on the pawn (the restore is not an "
			     "activatable ability). granted=%d"), Granted));
		return;
	}
	if (HealActivations < 1)
	{
		FinishTest(EFunctionalTestResult::Failed, TEXT(
			"an ability tagged Ability.HealOverTime was granted but did NOT activate on TryActivateAbilitiesByTag"));
		return;
	}
	// HOT-1c -- EVERY activation must have landed, and this must be said BY NAME.
	//
	// The counters exist instead of an OR-ed latch precisely for this gate (see
	// the header). This fixture triggers the same tag once per leg, three legs in
	// one run. UE 5.8 refuses re-activation of an InstancedPerActor ability that
	// is still running (bRetriggerInstancedAbility defaults false) and of any
	// ability whose CommitAbility cooldown has not elapsed, returning false with
	// only a Verbose log in both cases -- idiomatic GAS shapes, not gaming. With a
	// latch, a refused leg-2 activation leaves Health sitting at the leg-2 preset
	// of 95, which passes HOT-5 vacuously (nothing ever pushed at the cap), and a
	// refused leg-3 activation passes HOT-6 vacuously for the same reason: the
	// two gates this whole family exists for would both go green having tested
	// nothing. Naming the refusal here is what keeps them honest. Same pattern and
	// rationale as HealthAttributeOpsFunctionalTest.cpp:311-334 (HO-6c).
	if (HealActivations < HealTriggerAttempts)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("an ability tagged Ability.HealOverTime refused a later activation: %d of %d activations "
			     "were accepted. The verifier activates the restore once per leg, three legs in one run, "
			     "and each activation must land its full effect - an ability that is still running when the "
			     "next activation arrives, or that is on cooldown, is not counted."),
			HealActivations, HealTriggerAttempts));
		return;
	}

	// HOT-2 -- PERIODIC: Health kept RISING in steps across two congruent 1.5 s
	// windows. A PURE DIRECTION PREDICATE with a noise floor, NOT a rate bar
	// (PIN.md, "Relative-vs-absolute accounting" / owner decision Q5(b)): any
	// conforming rate passes, including the slowest one the prompt admits. This is
	// the AG-3 defense -- one instant restore of the full amount rises once and is
	// then flat, so its second step is 0.
	if (!(RiseStep1 > RiseEpsilon && RiseStep2 > RiseEpsilon))
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("the restore was not periodic: Health did not keep rising in steps (A1=%.1f A2=%.1f "
			     "A3=%.1f; each step must rise by more than %.2f). An instant restore rises once then "
			     "stays flat."),
			A1, A2, A3, RiseEpsilon));
		return;
	}

	// HOT-3 -- it STOPS after its duration. The window opens at trigger+7.1, PAST
	// the top of the DISCLOSED 4-7 s acceptance band, so a conforming duration
	// (including a 7 s one) leaves zero legitimate ticks inside it and StopEpsilon
	// absorbs jitter only, never a legitimate expiry tick. This is the AG-4
	// defense against a permanent regeneration; the bound StopEpsilon must respect
	// for that defense to have teeth is derived in the header, quantified over
	// ALL admissible periods.
	if (StopRise > StopEpsilon)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("the restore did not STOP after its duration: Health was still rising in the post-band "
			     "stop window (AStop=%.1f at trigger+7.1 -> ATail=%.1f at trigger+9.2, rise %.1f > %.2f). "
			     "The fixture accepts any duration in the 4-7s band; a heal-over-time must end, a permanent "
			     "regeneration keeps climbing."),
			AStop, ATail, StopRise, StopEpsilon));
		return;
	}

	// HOT-4 -- the total restored sits inside the DISCLOSED 10-40 band. Absolute
	// bar, lawful only because the prompt states it. This is the AG-6 defense
	// against a token 1 HP restore that technically makes every window rise, and
	// it exists so a non-conforming magnitude fails by its OWN name instead of
	// being misattributed to HOT-2 or HOT-3 (the F5 failure mode). The literal
	// "40.0" and "10-40" digits below are per PIN.md section 2 -- keep them in
	// step with HealthPreset / TotalRestoredMin / TotalRestoredMax if any is ever
	// re-pinned.
	if (TotalRestored < TotalRestoredMin || TotalRestored > TotalRestoredMax)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("the total restored is outside the stated 10-40 band: Health went 40.0 -> %.1f over one "
			     "application (total %.1f). The prompt fixes a per-application total between 10 and 40."),
			ATail, TotalRestored));
		return;
	}

	// HOT-5 -- THE CLAMP GATE, AND THE REASON V1.4 EXISTS. Health must never
	// exceed MaxHealth: not the value the game reads back (CURRENT), and not the
	// underlying stored value it accumulates into (BASE).
	//
	// READING ONLY THE CURRENT VALUE MAKES THIS GATE VACUOUS. A
	// PreAttributeChange-only clamp -- the recipe every GAS tutorial shows, and
	// what "Health must never exceed MaxHealth" reads like to a competent
	// engineer -- guards CurrentValue only (AttributeSet.cpp:94-95). A PERIODIC
	// effect executes into the BASE value, so with the Leg 2 preset of 95 and a
	// conforming total the read-back is a clean 100.0 while the stored base has
	// accumulated to ~115: the submission passes a current-only gate while
	// silently absorbing the next 15 points of damage. PIN.md section 4 traces
	// exactly that pair. Both values are read at the SAME instant (cp7) so they
	// cannot be reconciled by timing.
	//
	// The cap compared against is MaxHealthRead -- the value HOT-0 already pinned
	// to 100 at cp0, BEFORE any trigger -- and not a live re-read. A live re-read
	// would let a submission raise its own cap at activation time and clear the
	// gate by moving the goalposts; the live value is logged as L2maxLive above
	// so that divergence is visible rather than silently absorbed.
	if (L2Current > MaxHealthRead + ClampEpsilon || L2Base > MaxHealthRead + ClampEpsilon)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("the restore pushed Health past its cap: current=%.1f base=%.1f against MaxHealth=%.1f "
			     "(+/- %.2f). Health must never exceed MaxHealth - neither the value read back nor the "
			     "underlying stored value."),
			L2Current, L2Base, MaxHealthRead, ClampEpsilon));
		return;
	}

	// HOT-6 -- at-max NO-OP: activating at full health leaves Health at MaxHealth,
	// in BOTH directions (it must not push past it, and it must not lower it).
	// This is the other half of the AG-5 defense: "clamp" implemented as SETTING
	// Health to MaxHealth on activation lowers Health whenever it was above, and a
	// restore with no cap at all pushes past.
	//
	// GATED ON THE CURRENT VALUE ONLY, DELIBERATELY. PIN.md section 4 states that
	// the plausible-WRONG PreAttributeChange-only solve "passes HOT-0 through
	// HOT-4, HOT-6 and HOT-7" and dies at HOT-5 -- so HOT-6 must NOT gate the base
	// value, or the sheet's own discrimination story collapses into two gates
	// firing on one defect and HOT-5 stops being the named cause. The base read is
	// still REPORTED in the message (and in the diagnostic line) because it is the
	// number a reviewer needs to tell the two defects apart.
	if (FMath::Abs(L3Current - AtMaxPreset) > AtMaxEpsilon)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("activating the restore at full health changed Health: 100.0 -> %.1f (base %.1f). At full "
			     "health the effect must leave Health at MaxHealth - it must neither push past it nor "
			     "lower it."),
			L3Current, L3Base));
		return;
	}

	// All nine deterministic gates passed -- HOT-0 and HOT-7 at cp0, HOT-1/HOT-1c
	// and HOT-2..HOT-6 here. The base finishes Succeeded after the last checkpoint.
}

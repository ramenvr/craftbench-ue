// Copyright CraftBench. All Rights Reserved.

#include "PoisonStackFunctionalTest.h"

#include "CraftBenchGameplayTags.h"
#include "CraftBenchCharacter.h"
#include "CraftBenchBareCharacter.h"
#include "CraftBenchAttributeSet.h"
#include "AbilitySystemComponent.h"
#include "Components/MeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"

APoisonStackFunctionalTest::APoisonStackFunctionalTest(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
}

FGameplayTag APoisonStackFunctionalTest::PreferredAbilityTag() const
{
	return FCraftBenchGameplayTags::AbilityPoison();
}

void APoisonStackFunctionalTest::PrepareTest()
{
	PawnSpawnLocation = FVector(0.0, 0.0, 200.0); // pawn need not move
	Super::PrepareTest();                          // resolve (by Ability.Poison) + spawn + possess

	// 16-checkpoint schedule (2026-08-06 Leg C/D redefinition: the stack CAP and
	// duration REFRESH the prompt always demanded are now real gates — they were
	// advisory/unobservable on the retired 8-checkpoint schedule):
	//   Leg A @ 0.5  (stage-1 gate, then trigger x1): samples 1.6/3.1/4.6,
	//                stop window 7.6 -> 9.7 (opens PAST the ~5s band top).
	//   Leg C @ 10.7 (reset + trigger x1): mid 12.3 (log), RE-APPLY @ 14.3
	//                (= trigger+3.6, inside every conforming ~5s window),
	//                refresh window 17.9 -> 19.4, refreshed-stop 21.4 -> 23.5.
	//   Leg B @ 24.5 (reset + trigger x4): mid 26.1 (log), BEnd @ 28.6
	//                (= trigger+4.1 — CONGRUENT with the Leg A rate window; see
	//                the RateB comment in the final asserts).
	// Literal braces on purpose: the film-strip describer statically parses the
	// braced schedule literal below out of this source for per-frame time
	// labels (a variable-built TArray would demote every label to index-only).
	SetCheckpointSchedule({0.5, 1.6, 3.1, 4.6, 7.6, 9.7,
	                       10.7, 12.3, 14.3, 17.9, 19.4, 21.4, 23.5,
	                       24.5, 26.1, 28.6});
	LastCheckpointIndex = 15;
}

void APoisonStackFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	if (!Pawn.IsValid())
	{
		FinishTest(EFunctionalTestResult::Failed, TEXT("pawn did not spawn/resolve"));
		return;
	}
	UAbilitySystemComponent* ASC = PawnASC();
	if (ASC == nullptr)
	{
		FinishTest(EFunctionalTestResult::Failed, TEXT("pawn has no AbilitySystemComponent"));
		return;
	}
	auto Health = [&]() -> double
	{
		return static_cast<double>(ASC->GetNumericAttribute(UCraftBenchAttributeSet::GetHealthAttribute()));
	};
	auto SetHealth = [&](double V)
	{
		ASC->SetNumericAttributeBase(UCraftBenchAttributeSet::GetHealthAttribute(), static_cast<float>(V));
	};

	switch (CheckpointIndex)
	{
		case 0: // STAGE-1 verification (2026-08-05 redefinition), then the Leg A trigger
		{
			// Stage-1 gate (a) — derivation: the graded pawn must derive from the
			// provided ASC-only task base. An empty submission resolves to the
			// generic scaffold pawn; a submission that subclasses the generic pawn
			// instead of the task base inherits its PRE-BUILT health system and
			// skips stage 1 — both are named FAILs here, never a misgrade later.
			if (!Pawn->IsA(ACraftBenchBareCharacter::StaticClass()))
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(TEXT(
					"stage 1 not built: the graded pawn (%s) does not derive from the provided task base "
					"pawn (CraftBenchBareCharacter). An empty submission resolves to the generic scaffold "
					"pawn; a submission subclassing the generic scaffold pawn inherits a pre-built health "
					"system and skips stage 1."),
					*GetNameSafe(Pawn->GetClass())));
				return;
			}
			// Stage-1 gate (b) — presence: the ASC must actually carry the Health
			// attribute. GetNumericAttribute on a missing attribute set silently
			// reads 0 and SetNumericAttributeBase silently no-ops, so WITHOUT this
			// gate a health-less submission would fail later as "not periodic"
			// (misattributed) instead of by name here. (Proven 2026-08-05: a
			// no-attribute-set pawn FAILs exactly here — the promoted
			// discrimination/no-health-system/ variant.)
			if (!ASC->HasAttributeSetForAttribute(UCraftBenchAttributeSet::GetHealthAttribute()))
			{
				FinishTest(EFunctionalTestResult::Failed, TEXT(
					"stage 1 not built: the pawn's health attribute system is absent - the ASC has no "
					"attribute set exposing Health, so reads return 0 and writes no-op. A pawn that never "
					"builds (or detaches) the contract attribute set looks exactly like this."));
				return;
			}
			// Stage-1 gate (c) — initialization: Health must read 100 BEFORE any
			// fixture write (the agent initializes it; the fixture's own preset
			// below would mask an uninitialized attribute if this read came later).
			const double InitRead = Health();
			if (FMath::Abs(InitRead - HealthInitExpected) > BaselineEpsilon)
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(TEXT(
					"stage 1 incomplete: Health must initialize to %.0f but read %.1f before any fixture "
					"write (|delta| %.2f > %.2f). An attribute set that is registered but never "
					"initialized reads 0 here."),
					HealthInitExpected, InitRead, FMath::Abs(InitRead - HealthInitExpected), BaselineEpsilon));
				return;
			}
			// Stage-1 gate (d) — writability: write-then-read at a value != the
			// init value (an inert-write set that initializes at 100 would pass a
			// 100-write vacuously). The trigger has not fired yet, so no drain can
			// have moved Health inside this checkpoint.
			SetHealth(WriteProbeValue);
			const double ReadBack = Health();
			if (FMath::Abs(ReadBack - WriteProbeValue) > BaselineEpsilon)
			{
				FinishTest(EFunctionalTestResult::Failed, FString::Printf(TEXT(
					"stage 1 incomplete: health attribute is inert, write-then-read failed (wrote %.1f, "
					"read back %.1f, |delta| %.2f > %.2f). An inert or shadowed attribute set accepts the "
					"write but keeps reading its own value."),
					WriteProbeValue, ReadBack, FMath::Abs(ReadBack - WriteProbeValue), BaselineEpsilon));
				return;
			}
			// Stage-1 gate (e) — VISIBLE-CHARACTER gate (2026-08-06, owner
			// decision; applied to the whole glide/poison family, both variants
			// — this fixture is shared). The graded pawn must carry a
			// skeletal/static mesh component with a mesh actually assigned, so
			// a human reviewer watching the run (film strip / preview) can SEE
			// the character. Structural + deterministic — the fixture-level
			// twin of the -bp variant's L2I pawn_visibly_represented check
			// (measured 2026-08-04 on the glide family: 9/9 matrix reps
			// meshless; this task's film strips showed an empty scene). Named
			// FAIL here at checkpoint 0, never a misattributed later gate.
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
			SetHealth(HealthPreset); // restore the Leg A preset after the probe
			bBaselineOk = true;
			TriggerAbilityByTag(FCraftBenchGameplayTags::AbilityPoison());
			AStartT = TimeSeconds;
			break;
		}
		case 1: A1 = Health(); break;
		case 2: A2 = Health(); break;
		case 3: A3 = Health(); A3T = TimeSeconds; break;                 // last in-band sample (trigger+4.1)
		case 4: AStop = Health(); break;                                 // stop window opens (trigger+7.1, PAST the band top)
		case 5: ATail = Health(); break;                                 // stop window closes (trigger+9.2)
		case 6: // Leg C: refresh — single application, re-applied mid-window at idx 8
			SetHealth(HealthPreset);
			TriggerAbilityByTag(FCraftBenchGameplayTags::AbilityPoison());
			CStartT = TimeSeconds;
			break;
		case 7: CMid = Health(); break;                                  // mid-drain (logged only)
		case 8: // RE-APPLY inside the original window (trigger+3.6): late enough
		        // that the refreshed expiry clears the UN-refreshed band top
		        // (+7.0) by >= 1.5s, early enough to sit inside every conforming
		        // ~4-7s duration. Health read BEFORE the trigger (an
		        // execute-on-application tick must not blur the sample).
			CAtReapply = Health();
			TriggerAbilityByTag(FCraftBenchGameplayTags::AbilityPoison());
			CReapplyT = TimeSeconds;
			break;
		case 9:  CPost1 = Health(); break;                               // refresh window opens (CStart+7.2 > un-refreshed band top)
		case 10: CPost2 = Health(); break;                               // refresh window closes (CStart+8.7)
		case 11: CStop1 = Health(); break;                               // refreshed-stop window opens (re-apply+7.1)
		case 12: CStop2 = Health(); break;                               // refreshed-stop window closes (re-apply+9.2)
		case 13: // Leg B/D: 4 applications -> the cap must hold them at 3 stacks
			SetHealth(HealthPreset);
			TriggerAbilityByTag(FCraftBenchGameplayTags::AbilityPoison());
			TriggerAbilityByTag(FCraftBenchGameplayTags::AbilityPoison());
			TriggerAbilityByTag(FCraftBenchGameplayTags::AbilityPoison());
			TriggerAbilityByTag(FCraftBenchGameplayTags::AbilityPoison());
			BStartT = TimeSeconds;
			break;
		case 14: break;                                                  // mid-drain (logged only)
		case 15: BEnd = Health(); BEndT = TimeSeconds; break;            // trigger+4.1 — congruent with the Rate1 window
		default: break;
	}

	UE_LOG(LogTemp, Display,
		TEXT("[POISON] idx=%d t=%.2f health=%.1f baseline=%s (A3=%.1f AStop=%.1f ATail=%.1f CPost1=%.1f CPost2=%.1f CStop2=%.1f BEnd=%.1f)"),
		CheckpointIndex, TimeSeconds, Health(), bBaselineOk ? TEXT("ok") : TEXT("unchecked"),
		A3, AStop, ATail, CPost1, CPost2, CStop2, BEnd);

	if (CheckpointIndex < LastCheckpointIndex)
	{
		return;
	}

	// ---- final assertions ----
	const FGameplayTag PoisonTag = FCraftBenchGameplayTags::AbilityPoison();
	const int32 Granted = NumGrantedAbilitiesWithTag(PoisonTag);

	// Guard on the capture TIMES, not the Health values: Health can legitimately go
	// negative (the substrate AttributeSet does not clamp), so a ">= 0" sentinel
	// would wrongly treat a real negative reading as "unset".
	//
	// The two rate windows are CONGRUENT on purpose (both (trigger, trigger+4.1]):
	// with equal windows at equal offsets from their triggers, tick-count
	// quantization cancels for ANY conforming period/duration/on-application
	// config, and the ratio measures the stack multiplier directly. (The retired
	// 8-checkpoint fixture measured Leg B over 3.1s vs Leg A over 4.1s — that
	// asymmetry alone moved a conforming capped GE anywhere from 2.98x to 3.97x
	// depending on period phase, which is WHY the cap could not be gated then.)
	const double Rate1 = (A3T > AStartT) ? (HealthPreset - A3) / (A3T - AStartT) : 0.0;
	const double RateB = (BEndT > BStartT) ? (HealthPreset - BEnd) / (BEndT - BStartT) : 0.0;
	const double Ratio = (Rate1 > 0.01) ? (RateB / Rate1) : 0.0;

	UE_LOG(LogTemp, Display,
		TEXT("[POISON-FINAL] granted=%d activated=%d A1=%.1f A2=%.1f A3=%.1f AStop=%.1f ATail=%.1f CAtReapply=%.1f CPost1=%.1f CPost2=%.1f CStop1=%.1f CStop2=%.1f BEnd=%.1f Rate1=%.2f RateB=%.2f ratio=%.2f"),
		Granted, bAbilityActivated ? 1 : 0, A1, A2, A3, AStop, ATail,
		CAtReapply, CPost1, CPost2, CStop1, CStop2, BEnd, Rate1, RateB, Ratio);

	if (Granted < 1)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("no activatable ability tagged Ability.Poison on the pawn (GAS not implemented). granted=%d"), Granted));
		return;
	}
	if (!bAbilityActivated)
	{
		FinishTest(EFunctionalTestResult::Failed, TEXT(
			"an ability tagged Ability.Poison was granted but did NOT activate on TryActivateAbilitiesByTag"));
		return;
	}
	// (A) periodic: Health fell in steps across the window (not a single instant hit).
	if (!(A1 - A2 >= PeriodicMinStep && A2 - A3 >= PeriodicMinStep))
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("poison was not periodic: Health did not keep dropping in steps (A1=%.1f A2=%.1f A3=%.1f; need each step >= %.1f). "
			     "An instant hit drops once then stays flat."), A1, A2, A3, PeriodicMinStep));
		return;
	}
	// (A) stops: past the ~5s acceptance band, Health is stable (not a permanent
	// drain). The window opens at trigger+7.1 — PAST the band top — so a
	// conforming ~4-7s duration (including a ~6s one) shows zero ticks here and
	// StopEpsilon only absorbs jitter, never legitimate expiry ticks.
	if (AStop - ATail > StopEpsilon)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("poison did not STOP after its duration: Health was still dropping in the post-band stop window "
			     "(AStop=%.1f at trigger+7.1 -> ATail=%.1f at trigger+9.2, drop %.1f > %.1f). The fixture accepts any "
			     "duration inside the ~5s band (~4-7s); a DoT must end, a permanent drain keeps falling."),
			AStop, ATail, AStop - ATail, StopEpsilon));
		return;
	}
	// (C) refresh, direction 1 — the re-application EXTENDED the drain: Health
	// must still be dropping in (CStart+7.2, CStart+8.7], which lies PAST the
	// un-refreshed acceptance-band top (CStart+7.0) but INSIDE the refreshed
	// window (re-apply at CStart+3.6 + a conforming ~4-7s duration).
	if (CPost1 - CPost2 < RefreshMinStep)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("re-application did not refresh the duration: after a mid-window re-apply (trigger+3.6) the drain "
			     "was already over before the refreshed expiry (CPost1=%.1f -> CPost2=%.1f across the post-original-"
			     "expiry window, drop %.1f < %.1f). The poison must last ~5s from the MOST RECENT application, "
			     "not from the first."), CPost1, CPost2, CPost1 - CPost2, RefreshMinStep));
		return;
	}
	// (C) refresh, direction 2 — the refreshed effect still EXPIRES: stable in
	// (re-apply+7.1, re-apply+9.2], past the refreshed acceptance-band top.
	if (CStop1 - CStop2 > StopEpsilon)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("refreshed poison never expired: Health was still dropping past the refreshed duration band "
			     "(CStop1=%.1f at re-apply+7.1 -> CStop2=%.1f at re-apply+9.2, drop %.1f > %.1f). A refresh extends "
			     "the DoT to ~5s from the last application - it must still end."),
			CStop1, CStop2, CStop1 - CStop2, StopEpsilon));
		return;
	}
	// (B) stacking scales the rate: 4 applications must drain >= StackRatioMin x
	// the single-stack rate (a flat, non-stacking drain fails).
	if (Ratio < StackRatioMin)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("stacking did not scale the drain rate: 4-application rate %.2f / single-stack rate %.2f = %.2fx < %.1fx "
			     "(stacks must drain proportionally faster)."), RateB, Rate1, Ratio, StackRatioMin));
		return;
	}
	// (D) the stack CAP holds (GATED 2026-08-06, was advisory): with a cap of
	// three and ~proportional per-stack scaling, 4 applications drain ~3x one
	// stack. Uncapped reads ~4x; superlinear (e.g. double stack-scaling) reads
	// higher still — both violate the prompt ("a fourth application must not
	// exceed three stacks", "three stacks ~= three times the per-second loss").
	if (Ratio > StackRatioMax)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(
			TEXT("stack cap violated (or scaling is not ~proportional): 4 applications drained %.2fx the single-stack "
			     "rate (RateB=%.2f / Rate1=%.2f > %.1fx). A fourth application must not exceed three stacks, so the "
			     "4-application rate must read ~3x, not ~4x (uncapped) or more (superlinear)."),
			Ratio, RateB, Rate1, StackRatioMax));
		return;
	}
	// The exact 3x multiplier itself stays ADVISORY (logged): the two ratio
	// gates already bound it to [StackRatioMin, StackRatioMax].
	UE_LOG(LogTemp, Display, TEXT(
		"[POISON-ADVISORY] 4-application / single-stack drain-rate ratio = %.2fx "
		"(gated to [%.1f, %.1f]; the exact 3x value is logged, not pinned)"),
		Ratio, StackRatioMin, StackRatioMax);

	// All deterministic gates passed — base finishes Succeeded after the last checkpoint.
}

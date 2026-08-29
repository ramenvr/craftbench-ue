// Copyright CraftBench. All Rights Reserved.

#include "AoeBurnFunctionalTest.h"

#include "AbilitySystemComponent.h"
#include "AbilitySystemInterface.h"
#include "CraftBenchTestEffects.h"
#include "CraftBenchAttributeSet.h"
#include "CraftBenchCharacter.h"
#include "CraftBenchGameplayTags.h"

AAoeBurnFunctionalTest::AAoeBurnFunctionalTest(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	// Movement-independent family: default (sparse) sampling; the base's
	// checkpoint clock is the only time source used.
}

FGameplayTag AAoeBurnFunctionalTest::PreferredAbilityTag() const
{
	return FCraftBenchGameplayTags::AbilityAoeBurn();
}

double AAoeBurnFunctionalTest::TargetHealth(const ACraftBenchCharacter* Target)
{
	if (Target == nullptr)
	{
		return 0.0;
	}
	const IAbilitySystemInterface* AsInterface = Cast<IAbilitySystemInterface>(Target);
	UAbilitySystemComponent* ASC = AsInterface ? AsInterface->GetAbilitySystemComponent() : nullptr;
	if (ASC == nullptr)
	{
		return 0.0;
	}
	return ASC->GetNumericAttribute(UCraftBenchAttributeSet::GetHealthAttribute());
}

void AAoeBurnFunctionalTest::SetTargetHealth(ACraftBenchCharacter* Target, double Value)
{
	const IAbilitySystemInterface* AsInterface = Cast<IAbilitySystemInterface>(Target);
	UAbilitySystemComponent* ASC = AsInterface ? AsInterface->GetAbilitySystemComponent() : nullptr;
	if (ASC != nullptr)
	{
		ASC->SetNumericAttributeBase(
			UCraftBenchAttributeSet::GetHealthAttribute(), static_cast<float>(Value));
	}
}

void AAoeBurnFunctionalTest::PrepareTest()
{
	Super::PrepareTest(); // resolve (by Ability.AoeBurn) + spawn + possess the graded pawn

	// Verifier-owned targets: instances of the COMMITTED generic base, spawned
	// by the fixture - the submission can neither author nor pre-configure
	// them. Class-level pawn resolution is untouched (targets are instances of
	// the fallback class the resolver already knows about; resolution happened
	// in Super::PrepareTest above, from classes, not placed actors).
	UWorld* World = GetWorld();
	if (World == nullptr)
	{
		FinishTest(EFunctionalTestResult::Failed, TEXT("[HARNESS] no world in PrepareTest"));
		return;
	}
	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride =
		ESpawnActorCollisionHandlingMethod::AdjustIfPossibleButAlwaysSpawn;
	const FVector Base = PawnSpawnLocation;
	TargetNear = World->SpawnActor<ACraftBenchCharacter>(
		ACraftBenchCharacter::StaticClass(), Base + FVector(NearDistance, 0.0, 0.0),
		FRotator::ZeroRotator, Params);
	TargetFar = World->SpawnActor<ACraftBenchCharacter>(
		ACraftBenchCharacter::StaticClass(), Base + FVector(FarDistance, 0.0, 0.0),
		FRotator::ZeroRotator, Params);
	TargetControl = World->SpawnActor<ACraftBenchCharacter>(
		ACraftBenchCharacter::StaticClass(), Base + FVector(ControlDistance, 0.0, 0.0),
		FRotator::ZeroRotator, Params);
	// Evidence-only fourth target just outside a literal 5 m - see the header
	// for why this is sampled and printed but never gated.
	TargetEdge = World->SpawnActor<ACraftBenchCharacter>(
		ACraftBenchCharacter::StaticClass(), Base + FVector(EdgeDistance, 0.0, 0.0),
		FRotator::ZeroRotator, Params);

	// EQUAL in-band windows (see the header). Base sets TimeLimit from the last
	// checkpoint, so a stuck run FAILs instead of hanging.
	SetCheckpointSchedule({0.5, 1.87, 3.24, 4.6, 7.6, 9.7});
}

void AAoeBurnFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	// Track the far target's worst deviation at EVERY checkpoint - damage need
	// not be monotone and a final-read-only check would miss a burn-then-heal.
	auto EdgeHealth = [this]() -> double
	{
		return TargetEdge != nullptr ? TargetHealth(TargetEdge) : -1.0;
	};
	auto TrackFar = [this]()
	{
		if (TargetFar != nullptr)
		{
			FarMaxDeviation = FMath::Max(
				FarMaxDeviation, FMath::Abs(TargetPreset - TargetHealth(TargetFar)));
		}
	};

	switch (CheckpointIndex)
	{
	case 0: // 0.5s - preset, control, visibility, trigger (in that order)
	{
		if (TargetNear == nullptr || TargetFar == nullptr || TargetControl == nullptr)
		{
			FinishTest(EFunctionalTestResult::Failed,
				TEXT("[HARNESS] a verifier-owned target failed to spawn - environment fault, "
				     "do not grade this run against the submission"));
			return;
		}

		// Presets happen IN-WORLD, after the targets' BeginPlay - the generic
		// base's attribute defaults are not this fixture's contract.
		SetTargetHealth(TargetNear, TargetPreset);
		SetTargetHealth(TargetFar, TargetPreset);
		if (TargetEdge != nullptr) { SetTargetHealth(TargetEdge, TargetPreset); }
		SetTargetHealth(TargetControl, TargetPreset);

		// Control lane: the fixture's OWN periodic drain at a known rate.
		{
			const IAbilitySystemInterface* AsInterface = Cast<IAbilitySystemInterface>(TargetControl.Get());
			UAbilitySystemComponent* ControlASC =
				AsInterface ? AsInterface->GetAbilitySystemComponent() : nullptr;
			UGameplayEffect* ControlDrain = CraftBenchTestEffects::MakePeriodicAttributeDrain(
				UCraftBenchAttributeSet::GetHealthAttribute(),
				static_cast<float>(ControlPerTick), static_cast<float>(ControlPeriod),
				static_cast<float>(ControlDuration), FGameplayTag());
			if (ControlASC == nullptr || ControlDrain == nullptr)
			{
				FinishTest(EFunctionalTestResult::Failed,
					TEXT("[HARNESS] the control drain could not be built or applied - "
					     "environment fault, do not grade this run against the submission"));
				return;
			}
			ControlASC->ApplyGameplayEffectToSelf(
				ControlDrain, 1.0f, ControlASC->MakeEffectContext());
		}
		C0 = TargetHealth(TargetControl);

		// AB-7 - family-standard visibility gate, before anything else.
		// VisWhy is ALREADY a complete sentence ("the character is not visibly
		// represented: ..."), so it is passed through verbatim exactly as every
		// sibling fixture does. Wrapping it in another Printf doubled the
		// sentence in the FAIL string - measured 2026-08-11 on the empty leg.
		FString VisWhy;
		if (!PawnVisiblyRepresented(VisWhy))
		{
			FinishTest(EFunctionalTestResult::Failed, VisWhy);
			return;
		}

		TriggerTime = TimeSeconds;
		++BurnTriggerAttempts;
		if (TriggerAbilityByTag(FCraftBenchGameplayTags::AbilityAoeBurn()))
		{
			++BurnActivations;
		}
		N0 = TargetHealth(TargetNear);
		E0 = EdgeHealth();
		TrackFar();
		break;
	}
	case 1: N1 = TargetHealth(TargetNear); E1 = EdgeHealth(); TrackFar(); break;
	case 2: N2 = TargetHealth(TargetNear); E2 = EdgeHealth(); TrackFar(); break;
	case 3: N3 = TargetHealth(TargetNear); E3 = EdgeHealth(); TrackFar(); break;
	case 4: NStop = TargetHealth(TargetNear); TrackFar(); break;
	case 5: // 9.7s - final reads + every gate, in PIN order
	{
		NTail = TargetHealth(TargetNear);
		CEnd = TargetHealth(TargetControl);
		TrackFar();

		const double D1 = N0 - N1;
		const double D2 = N1 - N2;
		const double D3 = N2 - N3;
		const double StopDrop = NStop - NTail;
		const double Total = TargetPreset - NTail;
		const double ControlDrop = C0 - CEnd;

		// One evidence line off a SINGLE run, before any verdict - the tier-1
		// discipline: every gate figure and every window, greppable.
		AddInfo(FString::Printf(
			TEXT("[AOEBURN-FINAL] granted=%d activated=%d/%d preset=%.1f "
			     "N0=%.1f N1=%.1f N2=%.1f N3=%.1f NStop=%.1f NTail=%.1f "
			     "D1=%.2f D2=%.2f D3=%.2f meanRate=%.2f stopDrop=%.2f total=%.2f "
			     "farMaxDev=%.2f edge(EVIDENCE-ONLY,%.0fuu) E0=%.1f E1=%.1f E2=%.1f E3=%.1f "
			     "control C0=%.1f CEnd=%.1f drop=%.2f "
			     "triggerT=%.2f (bars PROPOSED - NOT YET MEASURED: stepEpsilon %.2f, "
			     "stopEpsilon %.2f, meanRate %.1f-%.1f enforced over %.1fs (disclosed 3-15), "
			     "total %.1f-%.1f)"),
			NumGrantedAbilitiesWithTag(FCraftBenchGameplayTags::AbilityAoeBurn()),
			BurnActivations, BurnTriggerAttempts, TargetPreset,
			N0, N1, N2, N3, NStop, NTail, D1, D2, D3,
			(TargetPreset - N3) / InBandSpanSeconds, StopDrop, Total,
			FarMaxDeviation, EdgeDistance, E0, E1, E2, E3, C0, CEnd, ControlDrop, TriggerTime,
			StepEpsilon, StopEpsilon, MeanRateMin, MeanRateMax, InBandSpanSeconds,
			TotalMin, TotalMax));

		// AB-0 - the control lane, FIRST: if the fixture's own known-rate drain
		// did not tick, no periodicity verdict below is attributable to the
		// submission. [HARNESS] prefix on purpose - see the header.
		if (ControlDrop <= StepEpsilon)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("[HARNESS] the control burn did not tick (control Health moved %.2f over "
				     "the run against a known-rate fixture-owned drain) - environment fault, "
				     "do not grade this run against the submission"), ControlDrop));
			return;
		}

		// AB-1 - granted + activated, by name.
		if (NumGrantedAbilitiesWithTag(FCraftBenchGameplayTags::AbilityAoeBurn()) < 1
			|| BurnActivations < BurnTriggerAttempts)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("no activatable ability tagged Ability.AoeBurn on the pawn (the burning "
				     "area is not an activatable ability, or its activation was refused). "
				     "granted=%d activated=%d/%d"),
				NumGrantedAbilitiesWithTag(FCraftBenchGameplayTags::AbilityAoeBurn()),
				BurnActivations, BurnTriggerAttempts));
			return;
		}

		// AB-2 - periodic, in steps (pure direction + noise floor).
		//
		// D1 IS EVIDENCE, NOT A GATE, since 2026-08-15 (FALSE_FAIL). Equalising
		// the windows to 1.37 s each (see the header) fixed the unequal-bar
		// defect but could not fix this one: a submission whose period is longer
		// than a window lands NO tick inside the first one, so D1 = 0 trips the
		// noise floor while the same submission is visibly, correctly periodic
		// over D2 and D3. The prompt says "about once a second"; it does not
		// promise a tick inside an undisclosed 1.37 s slice, and the header's own
		// 2026-08-11 calibration already recorded that equal-DURATION windows do
		// not hold equal TICK COUNTS (measured D1=5.00 D2=5.00 D3=10.00 from
		// phase alone).
		//
		// The two sibling fixtures on this schedule (heal-over-time,
		// poison-stack) likewise gate only their congruent windows, so this
		// aligns the family rather than loosening one member of it. Nothing is
		// lost: a one-shot hit still dies on D2 and D3, and D1 is still printed
		// in the evidence line above and in the FAIL text below, so a reviewer
		// reading either sees exactly what the first window did.
		if (D2 <= StepEpsilon || D3 <= StepEpsilon)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("the burn was not periodic: the character inside the area did not keep "
				     "losing Health in steps (D2=%.2f D3=%.2f; each gated step must exceed "
				     "%.2f; D1=%.2f is evidence only). A one-shot hit drops once then stays "
				     "flat."),
				D2, D3, StepEpsilon, D1));
			return;
		}

		// AB-3 - MEAN rate over the whole in-band span. Per-window banding was
		// measured unsound on 2026-08-11 (see the header): equal-duration
		// windows hold unequal tick counts, so a conforming solve can read
		// double its own rate in one window.
		const double MeanRate = (TargetPreset - N3) / InBandSpanSeconds;
		if (MeanRate < MeanRateMin || MeanRate > MeanRateMax)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("the burn rate is outside the stated band: the character inside the area "
				     "lost %.2f Health over the %.1fs the area was burning (%.2f per second) "
				     "against the disclosed three-to-fifteen per second."),
				TargetPreset - N3, InBandSpanSeconds, MeanRate));
			return;
		}

		// AB-4 - THE AREA GATE: the far character must be untouched.
		if (FarMaxDeviation > StepEpsilon)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("the burn is not an AREA effect: a character well outside the area "
				     "lost %.2f Health (must stay within %.2f of its starting value). "
				     "Burning every character in the world is not an area-of-effect."),
				FarMaxDeviation, StepEpsilon));
			return;
		}

		// AB-5 - stops after its duration.
		if (StopDrop > StopEpsilon)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("the burn never expired: the character inside the area was still losing "
				     "Health in the post-duration window (%.1f -> %.1f, drop %.2f > %.2f). "
				     "The fixture accepts any duration in the stated 4-7s band; a set-duration "
				     "burn must end."),
				NStop, NTail, StopDrop, StopEpsilon));
			return;
		}

		// AB-6 - disclosed total band.
		if (Total < TotalMin || Total > TotalMax)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(
				TEXT("the total burn is outside the stated band: the character inside the "
				     "area went %.1f -> %.1f (total %.2f) against the disclosed %.1f-%.1f "
				     "per application."),
				TargetPreset, NTail, Total, TotalMin, TotalMax));
			return;
		}

		FinishTest(EFunctionalTestResult::Succeeded, TEXT("gp-dot-aoe-burn: all gates green"));
		break;
	}
	default:
		break;
	}
}

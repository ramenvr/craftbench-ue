// Copyright CraftBench. All Rights Reserved.

#include "MeleeCooldownFunctionalTest.h"

#include "CraftBenchGameplayTags.h"
#include "CraftBenchCharacter.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/UnrealType.h"

AMeleeCooldownFunctionalTest::AMeleeCooldownFunctionalTest(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
}

FGameplayTag AMeleeCooldownFunctionalTest::PreferredAbilityTag() const
{
	return FCraftBenchGameplayTags::AbilityMelee();
}

void AMeleeCooldownFunctionalTest::PrepareTest()
{
	// Pin the two map-shipped targets BEFORE the base spawns the agent pawn:
	// at this point nothing agent-owned has spawned from the pawn's BeginPlay,
	// so pawn-spawned decoys can never be pinned. (Residual: the agent owns
	// the scaffold source, so scaffold-BeginPlay decoys remain possible — see
	// MATRIX.md's honestly-bounded coverage note; the delta/symmetry gates,
	// not the pin alone, carry that case.) Name-sort for determinism.
	TArray<AActor*> Tagged;
	UGameplayStatics::GetAllActorsWithTag(GetWorld(), FName(TEXT("MeleeDummy")), Tagged);
	Tagged.Sort([](const AActor& A, const AActor& B) { return A.GetName() < B.GetName(); });
	PinnedTaggedCount = Tagged.Num();
	if (Tagged.Num() >= 2)
	{
		NearDummy = Tagged[0];
		FarDummy = Tagged[1];
	}

	// Low spawn over the floor: the pawn settles well before cp0 at 0.6s.
	PawnSpawnLocation = FVector(0.0, 0.0, 120.0);
	Super::PrepareTest(); // resolve (by Ability.Melee) + spawn + possess

	if (PinnedTaggedCount < 2)
	{
		// The committed map ships exactly two; a submission cannot remove them.
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(TEXT(
			"HARNESS-PRECONDITION: expected 2 MeleeDummy-tagged targets in the map, found %d"),
			PinnedTaggedCount));
		return;
	}

	// Trigger #1 @0.6 (window 0.6..2.6); in-window re-triggers @1.2 and @2.2
	// with hold-checks @1.8 and @2.5; deferred-strike check + trigger #3 @3.4
	// (past expiry, 0.8s margin); recovery + far recheck @4.0.
	const TArray<double> Schedule = {0.6, 1.2, 1.8, 2.2, 2.5, 3.4, 4.0};
	LastCheckpointIndex = Schedule.Num() - 1;
	SetCheckpointSchedule(Schedule);
}

double AMeleeCooldownFunctionalTest::ReadHealth(AActor* Target, bool& bOk) const
{
	bOk = false;
	if (Target == nullptr)
	{
		return 0.0;
	}
	const FFloatProperty* Prop = FindFProperty<FFloatProperty>(Target->GetClass(), TEXT("Health"));
	if (Prop == nullptr)
	{
		return 0.0;
	}
	bOk = true;
	return static_cast<double>(Prop->GetPropertyValue_InContainer(Target));
}

bool AMeleeCooldownFunctionalTest::FarStillUntouched(double FarNow)
{
	if (FMath::Abs(FarBase - FarNow) > NoChangeEpsilon)
	{
		FinishTest(EFunctionalTestResult::Failed, FString::Printf(TEXT(
			"an out-of-reach enemy was damaged by the strike (far target health "
			"%.1f -> %.1f; only enemies within reach and in front may be hit)"),
			FarBase, FarNow));
		return false;
	}
	return true;
}

void AMeleeCooldownFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	if (!Pawn.IsValid())
	{
		FinishTest(EFunctionalTestResult::Failed, TEXT("pawn did not spawn/resolve"));
		return;
	}
	if (!NearDummy.IsValid() || !FarDummy.IsValid())
	{
		FinishTest(EFunctionalTestResult::Failed, TEXT(
			"a pinned MeleeDummy target is no longer valid at checkpoint time"));
		return;
	}

	bool bNearOk = false, bFarOk = false;
	const double NearNow = ReadHealth(NearDummy.Get(), bNearOk);
	const double FarNow = ReadHealth(FarDummy.Get(), bFarOk);
	if (!bNearOk || !bFarOk)
	{
		FinishTest(EFunctionalTestResult::Failed, TEXT(
			"a MeleeDummy-tagged target has no readable float Health property"));
		return;
	}

	UE_LOG(LogTemp, Display,
		TEXT("[MELEE] idx=%d t=%.2f near=%.1f far=%.1f (base near=%.1f far=%.1f after1=%.1f)"),
		CheckpointIndex, TimeSeconds, NearNow, FarNow, NearBase, FarBase, NearAfterFirst);

	switch (CheckpointIndex)
	{
	case 0:
	{
		// Geometry is fixture-owned: place the targets relative to the SETTLED
		// pawn so map placement and floor height never need re-calibration.
		const FVector PawnLoc = Pawn->GetActorLocation();
		const FVector Fwd = Pawn->GetActorForwardVector();
		NearDummy->SetActorLocation(PawnLoc + Fwd * NearDistance);
		FarDummy->SetActorLocation(PawnLoc + Fwd * FarDistance);

		bool bOk2 = false;
		NearBase = ReadHealth(NearDummy.Get(), bOk2);
		FarBase = ReadHealth(FarDummy.Get(), bOk2);
		bBaselineCaptured = true;
		if (FMath::Abs(NearBase - FarBase) > NoChangeEpsilon)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(TEXT(
				"the two practice targets did not start at equal health (near=%.1f far=%.1f) - "
				"target health must not be pre-spent before any strike"), NearBase, FarBase));
			return;
		}

		// Trigger #1. The empty leg dies here: nothing granted / nothing activates.
		TriggerAbilityByTag(FCraftBenchGameplayTags::AbilityMelee());
		const int32 Granted = NumGrantedAbilitiesWithTag(FCraftBenchGameplayTags::AbilityMelee());
		if (Granted < 1)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(TEXT(
				"no activatable ability tagged Ability.Melee on the pawn (the strike is not "
				"implemented through the ability system). granted=%d"), Granted));
			return;
		}
		if (!bAbilityActivated)
		{
			FinishTest(EFunctionalTestResult::Failed, TEXT(
				"an ability tagged Ability.Melee was granted but did NOT activate on the tag trigger"));
			return;
		}
		break;
	}
	case 1:
	{
		if (!bBaselineCaptured)
		{
			FinishTest(EFunctionalTestResult::Error, TEXT(
				"HARNESS-PRECONDITION: checkpoint 1 ran without a captured baseline"));
			return;
		}
		if (NearBase - NearNow < MinDamage)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(TEXT(
				"the strike did not damage the enemy within reach (health %.1f -> %.1f, "
				"need a drop >= %.1f)"), NearBase, NearNow, MinDamage));
			return;
		}
		if (!FarStillUntouched(FarNow))
		{
			return;
		}
		NearAfterFirst = NearNow;
		bAfterFirstCaptured = true;
		// First in-window re-trigger (window runs to 2.6). A correct solution
		// refuses; do not assert the call's return — the health trace decides.
		TriggerAbilityByTag(FCraftBenchGameplayTags::AbilityMelee());
		break;
	}
	case 2: // 1.8 — hold-check for the 1.2 re-trigger
	case 4: // 2.5 — hold-check for the 2.2 re-trigger (window narrows here)
	{
		if (!bAfterFirstCaptured)
		{
			FinishTest(EFunctionalTestResult::Error, TEXT(
				"HARNESS-PRECONDITION: a hold checkpoint ran without the post-strike capture"));
			return;
		}
		if (NearAfterFirst - NearNow > NoChangeEpsilon)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(TEXT(
				"a strike landed during the cooldown window (health %.1f -> %.1f while "
				"the cooldown was still active)"), NearAfterFirst, NearNow));
			return;
		}
		break;
	}
	case 3: // 2.2 — second in-window re-trigger
	{
		TriggerAbilityByTag(FCraftBenchGameplayTags::AbilityMelee());
		break;
	}
	case 5: // 3.4 — deferred-strike trap, then the recovery trigger
	{
		if (bAfterFirstCaptured && NearAfterFirst - NearNow > NoChangeEpsilon)
		{
			// A buffered in-window trigger that executed at expiry (2.6) shows
			// up as a drop in the 2.5..3.4 window nobody legitimately strikes in.
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(TEXT(
				"a deferred strike landed after the cooldown window (health %.1f -> %.1f "
				"with no trigger since the window closed)"), NearAfterFirst, NearNow));
			return;
		}
		// Past the cooldown expiry — the strike must work again.
		TriggerAbilityByTag(FCraftBenchGameplayTags::AbilityMelee());
		break;
	}
	case 6: // 4.0 — recovery + the far target must STILL be untouched
	{
		if (NearAfterFirst - NearNow < MinDamage)
		{
			FinishTest(EFunctionalTestResult::Failed, FString::Printf(TEXT(
				"the strike never recovered after the cooldown (health %.1f -> %.1f after "
				"a post-cooldown trigger; need a drop >= %.1f)"),
				NearAfterFirst, NearNow, MinDamage));
			return;
		}
		if (!FarStillUntouched(FarNow))
		{
			return;
		}
		break;
	}
	default:
		break;
	}
	// All gates passed at the last checkpoint — the base finishes Succeeded.
}

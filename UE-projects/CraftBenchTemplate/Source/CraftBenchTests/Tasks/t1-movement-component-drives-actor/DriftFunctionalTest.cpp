// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// ADriftFunctionalTest implementation. PIE-native: the engine ticks the world;
// the fixture only samples the host's location at scheduled checkpoints. Uses a
// displacement-rate constant-velocity check (robust regardless of whether the
// agent's motion populates GetVelocity()).

#include "DriftFunctionalTest.h"

#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Kismet/GameplayStatics.h"

namespace
{
	static const FName DriftRootTag(TEXT("DriftRoot"));

	// Tolerances (world units). Reference drifts ~200 uu/s => ~100 uu per 0.5 s
	// step, giving generous headroom over MoveMin.
	constexpr double MoveMin = 20.0;   // min displacement to count as "moving"
	constexpr double RateTolPct = 0.30; // allowed variation between equal-interval steps
}

ADriftFunctionalTest::ADriftFunctionalTest(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
}

void ADriftFunctionalTest::PrepareTest()
{
	Super::PrepareTest();

	UWorld* World = GetWorld();
	if (World == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error, TEXT("PrepareTest: no UWorld available"));
		return;
	}

	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(World, DriftRootTag, Found);
	if (Found.Num() != 1)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("Expected exactly one actor tagged 'DriftRoot' in the test level; found %d."), Found.Num()));
		return;
	}

	Host = Found[0];
	StartLocation = Host->GetActorLocation();
	Samples.Reset();
	SetCheckpointSchedule({ 0.5, 1.0, 1.5, 2.0 });
}

void ADriftFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	if (Host == nullptr)
	{
		FinishTest(EFunctionalTestResult::Failed, TEXT("Host actor went missing during the test."));
		return;
	}

	Samples.Add(Host->GetActorLocation());

	if (CheckpointIndex == 0)
	{
		const double Moved = FVector::Dist(Samples[0], StartLocation);
		if (Moved <= MoveMin)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(
					TEXT("At t=%.2fs the actor has barely moved from its start (%.1f uu); it should be gliding. Is any self-motion configured?"),
					TimeSeconds, Moved));
			return;
		}
	}

	if (CheckpointIndex == 3 && Samples.Num() == 4)
	{
		const double d01 = FVector::Dist(Samples[1], Samples[0]);
		const double d12 = FVector::Dist(Samples[2], Samples[1]);
		const double d23 = FVector::Dist(Samples[3], Samples[2]);

		// Continues moving to the end (defeats move-then-stop and teleport-then-static).
		if (d23 <= MoveMin)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(
					TEXT("At t=%.2fs the actor is no longer advancing (last-interval step %.1f uu); a steady drift keeps moving."),
					TimeSeconds, d23));
			return;
		}

		// Constant velocity: equal displacement across equal intervals (defeats
		// acceleration ramps and one-shot teleports).
		auto WithinPct = [](double A, double B, double TolPct) -> bool
		{
			const double Ref = FMath::Max(FMath::Abs(A), FMath::Abs(B));
			if (Ref <= KINDA_SMALL_NUMBER)
			{
				return true;
			}
			return FMath::Abs(A - B) / Ref <= TolPct;
		};

		if (!WithinPct(d12, d01, RateTolPct) || !WithinPct(d23, d12, RateTolPct))
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(
					TEXT("At t=%.2fs the drift is not constant-velocity: per-interval steps were %.1f, %.1f, %.1f uu (should be roughly equal)."),
					TimeSeconds, d01, d12, d23));
			return;
		}
	}
}

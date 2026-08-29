// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// AProfiledMoverFunctionalTest implementation. PIE-native: the engine ticks; the
// fixture samples the host's location at checkpoints and checks the displacement
// rate matches the profile's CruiseSpeed. The expected speed mirrors the value
// the scaffolder authors into DA_MovementProfile (undisclosed to the agent) —
// keep in sync with Tools/scaffold_L_ProfiledMover.py.

#include "ProfiledMoverFunctionalTest.h"

#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Kismet/GameplayStatics.h"

namespace
{
	static const FName ProfiledMoverRootTag(TEXT("ProfiledMoverRoot"));

	// The CruiseSpeed the scaffolder authors into DA_MovementProfile (uu/s).
	// Non-round + undisclosed so a hardcoded speed guess is implausible. Keep in
	// sync with Tools/scaffold_L_ProfiledMover.py.
	constexpr double ExpectedCruiseSpeed = 173.0;
	constexpr double RateTolPct = 0.12;   // measured rate must be within 12% of the profile speed
	constexpr double SampleInterval = 0.5;
	constexpr double MoveMin = 20.0;      // min displacement to count as "moving"
}

AProfiledMoverFunctionalTest::AProfiledMoverFunctionalTest(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
}

void AProfiledMoverFunctionalTest::PrepareTest()
{
	Super::PrepareTest();

	UWorld* World = GetWorld();
	if (World == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error, TEXT("PrepareTest: no UWorld available"));
		return;
	}

	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(World, ProfiledMoverRootTag, Found);
	if (Found.Num() != 1)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("Expected exactly one actor tagged 'ProfiledMoverRoot' in the test level; found %d."), Found.Num()));
		return;
	}

	Host = Found[0];
	StartLocation = Host->GetActorLocation();
	Samples.Reset();
	SetCheckpointSchedule({ 0.5, 1.0, 1.5 });
}

void AProfiledMoverFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
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
					TEXT("At t=%.2fs the actor has barely moved (%.1f uu); it should be cruising at the profile's CruiseSpeed. Was the profile read and applied?"),
					TimeSeconds, Moved));
			return;
		}
	}

	if (CheckpointIndex == 2 && Samples.Num() == 3)
	{
		// Average measured speed over the two equal intervals.
		const double d01 = FVector::Dist(Samples[1], Samples[0]);
		const double d12 = FVector::Dist(Samples[2], Samples[1]);
		const double MeasuredSpeed = ((d01 + d12) / 2.0) / SampleInterval;

		const double LowerBound = ExpectedCruiseSpeed * (1.0 - RateTolPct);
		const double UpperBound = ExpectedCruiseSpeed * (1.0 + RateTolPct);
		if (MeasuredSpeed < LowerBound || MeasuredSpeed > UpperBound)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(
					TEXT("At t=%.2fs the measured cruise speed was %.1f uu/s, expected ~%.1f (the profile's CruiseSpeed, +/-%.0f%%). ")
					TEXT("A near-zero speed means the profile was never read/applied; a wrong speed means the value did not come from the profile."),
					TimeSeconds, MeasuredSpeed, ExpectedCruiseSpeed, RateTolPct * 100.0));
			return;
		}
	}
}

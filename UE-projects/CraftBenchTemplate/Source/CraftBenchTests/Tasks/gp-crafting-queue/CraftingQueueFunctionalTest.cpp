// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// ACraftingQueueFunctionalTest implementation. PIE-native: no manual ticking,
// no manual DispatchBeginPlay. The base (ACraftBenchFunctionalTest) drives the
// checkpoint clock off the PIE world game-time; we resolve the host by tag, then
// at each checkpoint sample the running count of CraftCompleted marker actors.
// The expected count climbs by exactly one per second (0,1,2,3,4) — this gates
// strict one-at-a-time FIFO pacing AND that all four actions complete.

#include "CraftingQueueFunctionalTest.h"

#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Kismet/GameplayStatics.h"

namespace
{
	static const FName CraftQueueRootTag(TEXT("CraftQueueRoot"));
	static const FName CraftCompletedTag(TEXT("CraftCompleted"));

	// Expected cumulative CraftCompleted count at each checkpoint, by index.
	// Checkpoints fire at 0.5, 1.5, 2.5, 3.5, 4.5s (the midpoints of each
	// one-second window), giving a correct one-per-second solution slack on
	// both sides while still rejecting bursts (too high early) and stalls
	// (too low late).
	constexpr int32 ExpectedCounts[] = { 0, 1, 2, 3, 4 };
	constexpr int32 NumCheckpoints = static_cast<int32>(UE_ARRAY_COUNT(ExpectedCounts));

	int32 CountCompleted(UWorld* World)
	{
		if (World == nullptr)
		{
			return 0;
		}
		TArray<AActor*> Found;
		UGameplayStatics::GetAllActorsWithTag(World, CraftCompletedTag, Found);
		return Found.Num();
	}
}

ACraftingQueueFunctionalTest::ACraftingQueueFunctionalTest(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
}

void ACraftingQueueFunctionalTest::PrepareTest()
{
	Super::PrepareTest();

	UWorld* World = GetWorld();
	if (World == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error, TEXT("PrepareTest: no UWorld available"));
		return;
	}

	// Identity by tag, not by class — the agent may subclass the host actor.
	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(World, CraftQueueRootTag, Found);
	if (Found.Num() != 1)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("Expected exactly one actor tagged 'CraftQueueRoot' in the test level; found %d."), Found.Num()));
		return;
	}

	// Sample the running completion count at the midpoint of each one-second
	// window (seconds since the PIE world began play).
	SetCheckpointSchedule({ 0.5, 1.5, 2.5, 3.5, 4.5 });
}

void ACraftingQueueFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	if (CheckpointIndex < 0 || CheckpointIndex >= NumCheckpoints)
	{
		return;
	}

	const int32 Expected = ExpectedCounts[CheckpointIndex];
	const int32 Actual = CountCompleted(GetWorld());

	if (Actual != Expected)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(
				TEXT("At t=%.2fs: expected exactly %d 'CraftCompleted' marker actor(s) (one craft completed per second, FIFO); found %d."),
				TimeSeconds, Expected, Actual));
		return;
	}

	// On the final checkpoint, every expected completion is accounted for — the
	// base finishes the test as success.
}

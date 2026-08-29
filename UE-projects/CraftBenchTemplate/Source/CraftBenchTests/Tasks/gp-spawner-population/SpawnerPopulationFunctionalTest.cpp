// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// ASpawnerPopulationFunctionalTest implementation. PIE-native: no manual ticking,
// no manual DispatchBeginPlay. The base (ACraftBenchFunctionalTest) drives the
// checkpoint clock off the PIE world game-time; we resolve the host by tag, then
// at each checkpoint sample (and perturb) the SpawnedMinion population to probe
// the three behaviors the task requires: spawn-on-BeginPlay (count + radius),
// respawn-on-destroy, and cleanup-on-destroy.

#include "SpawnerPopulationFunctionalTest.h"

#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Kismet/GameplayStatics.h"

namespace
{
	static const FName SpawnerRootTag(TEXT("SpawnerRoot"));
	static const FName SpawnedMinionTag(TEXT("SpawnedMinion"));

	constexpr int32 TargetPopulation = 5;
	// The prompt asks for spawns within 500 units; this allows slack a correct
	// solution never needs, and rejects a population dumped at a fixed far point.
	//
	// WHAT THIS GATE CANNOT DO, corrected 2026-08-19 after a variant measured it:
	// it does NOT catch a rootless minion. The comment here used to claim "the host
	// is placed OFF the world origin, so rootless minions that report (0,0,0) land
	// far outside this" — that is false. The placed ASpawnerActor scaffold creates
	// no root component, so the HOST reports (0,0,0) too (UE 5.8 Actor.h:4465), and
	// this check computes Dist(origin, origin) = 0. The same false claim reached
	// task.md's anti-gaming note 3 and cameras.json's framing note; both are
	// corrected. The rootless route is caught by the spread gate below instead.
	constexpr double MaxSpawnDistance = 650.0;
	// Two minions count as sharing a position within this. Deliberately tiny: the
	// spread gate below only has to reject IDENTICAL placement, so the epsilon
	// exists to absorb float noise, not to impose a minimum spacing the prompt
	// never asked for. A correct solution scattering over a 500-unit disc clears it
	// by orders of magnitude; five minions on one hard-coded point do not.
	constexpr double DistinctLocationEpsilon = 1.0;

	void GetMinions(UWorld* World, TArray<AActor*>& Out)
	{
		Out.Reset();
		if (World != nullptr)
		{
			UGameplayStatics::GetAllActorsWithTag(World, SpawnedMinionTag, Out);
		}
	}
}

ASpawnerPopulationFunctionalTest::ASpawnerPopulationFunctionalTest(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
}

void ASpawnerPopulationFunctionalTest::PrepareTest()
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
	UGameplayStatics::GetAllActorsWithTag(World, SpawnerRootTag, Found);
	if (Found.Num() != 1)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("Expected exactly one actor tagged 'SpawnerRoot' in the test level; found %d."), Found.Num()));
		return;
	}

	SpawnerLocation = Found[0]->GetActorLocation();

	// Sample (and perturb) the population at these times (seconds since the PIE
	// world began play). 1s gaps give a respawn solution ample time to react.
	SetCheckpointSchedule({ 0.5, 1.5, 2.5 });
}

void ASpawnerPopulationFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	UWorld* World = GetWorld();
	TArray<AActor*> Minions;
	GetMinions(World, Minions);

	switch (CheckpointIndex)
	{
		case 0:
		{
			// (1) spawn-on-BeginPlay: exactly N children, all within radius.
			if (Minions.Num() != TargetPopulation)
			{
				FinishTest(
					EFunctionalTestResult::Failed,
					FString::Printf(
						TEXT("At t=%.2fs: expected %d SpawnedMinion actor(s) spawned on BeginPlay; found %d."),
						TimeSeconds, TargetPopulation, Minions.Num()));
				return;
			}
			int32 DistinctLocations = 0;
			for (const AActor* Minion : Minions)
			{
				const double Dist = FVector::Dist(Minion->GetActorLocation(), SpawnerLocation);
				if (Dist > MaxSpawnDistance)
				{
					FinishTest(
						EFunctionalTestResult::Failed,
						FString::Printf(
							TEXT("At t=%.2fs: a SpawnedMinion is %.0f units from the spawner (limit %.0f)."),
							TimeSeconds, Dist, MaxSpawnDistance));
					return;
				}
				// Count minions whose position no EARLIER minion already occupies.
				bool bSeenHere = false;
				for (const AActor* Other : Minions)
				{
					if (Other == Minion) { break; }
					if (FVector::Dist(Other->GetActorLocation(), Minion->GetActorLocation())
						<= DistinctLocationEpsilon)
					{
						bSeenHere = true;
						break;
					}
				}
				if (!bSeenHere)
				{
					++DistinctLocations;
				}
			}

			// (1b) RANDOM placement, in its weakest observable form. Randomness cannot be
			// judged from one run, but its minimum consequence can: five minions must not
			// all sit on one point. This accepts any distribution and rejects only
			// identical placement.
			//
			// It also closes a route the radius gate above CANNOT see. A minion spawned
			// with no scene root reports (0,0,0) (UE 5.8 Actor.h:4465,
			// TemplateGetActorLocation returns ZeroVector when RootComponent is null), and
			// so does the placed host, whose scaffold class creates no root component
			// either -- so the radius check compares the origin against itself and passes
			// any number of locationless minions. Identical points fail HERE instead,
			// reviving that defense without changing the class every submission inherits.
			if (Minions.Num() > 1 && DistinctLocations < 2)
			{
				FinishTest(
					EFunctionalTestResult::Failed,
					FString::Printf(
						TEXT("At t=%.2fs: all %d SpawnedMinion actor(s) occupy the same position; each was to be spawned at a random location, and identical placement is also what a minion with no scene root reports."),
						TimeSeconds, Minions.Num()));
				return;
			}
			// Destroy one child to probe respawn-on-destroy.
			if (Minions[0] != nullptr)
			{
				Minions[0]->Destroy();
			}
			break;
		}
		case 1:
		{
			// (2) respawn-on-destroy: population restored to N.
			if (Minions.Num() != TargetPopulation)
			{
				FinishTest(
					EFunctionalTestResult::Failed,
					FString::Printf(
						TEXT("At t=%.2fs: after destroying one child, expected the population to return to %d; found %d."),
						TimeSeconds, TargetPopulation, Minions.Num()));
				return;
			}
			// Destroy the host to probe cleanup-on-destroy.
			TArray<AActor*> Hosts;
			if (World != nullptr)
			{
				UGameplayStatics::GetAllActorsWithTag(World, SpawnerRootTag, Hosts);
			}
			if (Hosts.Num() == 1 && Hosts[0] != nullptr)
			{
				Hosts[0]->Destroy();
			}
			else
			{
				FinishTest(
					EFunctionalTestResult::Failed,
					FString::Printf(TEXT("At t=%.2fs: expected exactly one 'SpawnerRoot' to destroy; found %d."),
						TimeSeconds, Hosts.Num()));
				return;
			}
			break;
		}
		case 2:
		{
			// (3) cleanup-on-destroy: no orphan children remain after the host dies.
			if (Minions.Num() != 0)
			{
				FinishTest(
					EFunctionalTestResult::Failed,
					FString::Printf(
						TEXT("At t=%.2fs: after destroying the spawner, expected 0 SpawnedMinion actor(s); found %d."),
						TimeSeconds, Minions.Num()));
				return;
			}
			// All three behaviors verified — the base finishes the test as success.
			break;
		}
		default:
			break;
	}
}

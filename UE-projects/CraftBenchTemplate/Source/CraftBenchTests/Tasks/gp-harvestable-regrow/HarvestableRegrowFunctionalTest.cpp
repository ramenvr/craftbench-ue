// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// AHarvestableRegrowFunctionalTest implementation. PIE-native: no manual ticking,
// no manual DispatchBeginPlay. The base (ACraftBenchFunctionalTest) drives the
// checkpoint clock off the PIE world game-time; we resolve the host by tag, then
// at each checkpoint sample the "Regrowing" tag to probe the state machine and
// induce the harvest by overlapping a spawned probe with the host:
//   (1) starts active        — checkpoint 0 asserts NO "Regrowing" tag, then
//                              spawns the probe to fire begin-overlap (harvest);
//   (2) regrowing on overlap — checkpoint 1 (~1.5 s later) asserts the
//                              "Regrowing" tag is present;
//   (3) returns to active    — checkpoint 2 (~7 s after harvest, past the 5 s
//                              regrow delay) asserts the "Regrowing" tag is gone.

#include "HarvestableRegrowFunctionalTest.h"

#include "Components/SphereComponent.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Kismet/GameplayStatics.h"

namespace
{
	static const FName HarvestableRootTag(TEXT("HarvestableRoot"));
	static const FName RegrowingTag(TEXT("Regrowing"));

	bool HasRegrowingTag(const AActor* Actor)
	{
		return Actor != nullptr && Actor->Tags.Contains(RegrowingTag);
	}
}

AHarvestableRegrowFunctionalTest::AHarvestableRegrowFunctionalTest(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
}

void AHarvestableRegrowFunctionalTest::PrepareTest()
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
	UGameplayStatics::GetAllActorsWithTag(World, HarvestableRootTag, Found);
	if (Found.Num() != 1)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("Expected exactly one actor tagged 'HarvestableRoot' in the test level; found %d."), Found.Num()));
		return;
	}

	Harvestable = Found[0];

	// See the header for what each checkpoint carries and why the bounds are where
	// they are. Harvest at ~0.5s => deadline ~5.5s; 5.0 and 6.0 straddle it by 0.5s,
	// which is >= 10 frames at 60 FPS and >= 10 frames at 20 FPS.
	SetCheckpointSchedule({ 0.5, 2.0, 5.0, 6.0, 7.0 });
}

bool AHarvestableRegrowFunctionalTest::InduceHarvestOverlap()
{
	UWorld* World = GetWorld();
	if (World == nullptr || Harvestable == nullptr)
	{
		return false;
	}

	const FVector Target = Harvestable->GetActorLocation();

	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;

	AActor* Probe = World->SpawnActor<AActor>(AActor::StaticClass(), Target, FRotator::ZeroRotator, Params);
	if (Probe == nullptr)
	{
		return false;
	}

	// Give the probe an overlap-enabled sphere root so it overlaps the
	// harvestable's volume and fires the harvestable's begin-overlap event — the
	// headless stand-in for a player walking into the harvestable.
	USphereComponent* ProbeSphere = NewObject<USphereComponent>(Probe, TEXT("ProbeSphere"));
	Probe->SetRootComponent(ProbeSphere);
	ProbeSphere->InitSphereRadius(48.0f);
	ProbeSphere->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	ProbeSphere->SetCollisionObjectType(ECC_WorldDynamic);
	ProbeSphere->SetCollisionResponseToAllChannels(ECR_Overlap);
	ProbeSphere->SetGenerateOverlapEvents(true);
	ProbeSphere->RegisterComponent();

	// Place exactly on the harvestable and force an overlap update so begin-overlap
	// fires deterministically this frame rather than waiting on physics movement.
	Probe->SetActorLocation(Target);
	ProbeSphere->UpdateOverlaps();

	Probes.Add(Probe);
	return true;
}

void AHarvestableRegrowFunctionalTest::DestroyProbes()
{
	for (const TWeakObjectPtr<AActor>& Weak : Probes)
	{
		if (AActor* Probe = Weak.Get())
		{
			Probe->Destroy();
		}
	}
	Probes.Reset();
}

void AHarvestableRegrowFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	switch (CheckpointIndex)
	{
		case 0:
		{
			// (1) starts active: no "Regrowing" tag before the harvest is induced.
			if (HasRegrowingTag(Harvestable))
			{
				FinishTest(
					EFunctionalTestResult::Failed,
					FString::Printf(
						TEXT("At t=%.2fs: the harvestable carries the 'Regrowing' tag before any harvest; it should start active."),
						TimeSeconds));
				return;
			}
			// Induce the harvest by overlapping a probe with the harvestable.
			if (!InduceHarvestOverlap())
			{
				FinishTest(
					EFunctionalTestResult::Failed,
					FString::Printf(TEXT("At t=%.2fs: failed to spawn the overlap probe to induce a harvest."), TimeSeconds));
				return;
			}
			break;
		}
		case 1:
		{
			// (2) regrowing on overlap: the tag is present ~1.5 s after harvest.
			if (!HasRegrowingTag(Harvestable))
			{
				FinishTest(
					EFunctionalTestResult::Failed,
					FString::Printf(
						TEXT("At t=%.2fs: after being walked into, the harvestable should be regrowing (carry the 'Regrowing' tag) but it does not."),
						TimeSeconds));
				return;
			}
			// A SECOND walk-in, DURING the regrow window. "It must not be
			// harvestable again - walking into it while it is regrowing does
			// nothing." Nothing observable happens here; the consequence is read at
			// t=6.0, because a host with no re-entrancy guard re-harvests NOW and so
			// pushes its own deadline out to ~7.0s. A fresh probe, since
			// begin-overlap fires on the transition and probe A is already inside.
			if (!InduceHarvestOverlap())
			{
				FinishTest(
					EFunctionalTestResult::Failed,
					FString::Printf(TEXT("At t=%.2fs: failed to spawn the second overlap probe."), TimeSeconds));
				return;
			}
			break;
		}
		case 2:
		{
			// (3) the delay's LOWER bound: 0.5 s short of the deadline it must still
			// be regrowing. Before this, nothing after t=2.0 constrained an
			// early return, so a 2-second regrow passed as a 5-second one.
			if (!HasRegrowingTag(Harvestable))
			{
				FinishTest(
					EFunctionalTestResult::Failed,
					FString::Printf(
						TEXT("At t=%.2fs: the harvestable has already returned to active, ~4.5 s after being harvested; the regrow delay is 5 seconds."),
						TimeSeconds));
				return;
			}
			// Clear the induced overlaps BEFORE the host is due back. A host that
			// re-reads its current overlaps on waking would otherwise re-harvest
			// itself immediately - correct behavior punished by the fixture's own
			// leftovers.
			DestroyProbes();
			break;
		}
		case 3:
		{
			// (4) returns to active 5 s after harvest, and NOT later. At t=6.0 a
			// correct host has been active for ~0.5 s, while a host that restarted
			// its clock on the t=2.0 walk-in still has ~1.0 s to go - so this one
			// assertion carries both the tightened upper bound and the
			// no-re-entrancy verdict.
			if (HasRegrowingTag(Harvestable))
			{
				FinishTest(
					EFunctionalTestResult::Failed,
					FString::Printf(
						TEXT("At t=%.2fs: the harvestable still carries the 'Regrowing' tag ~5.5 s after being harvested; either the regrow delay is longer than 5 seconds, or a second walk-in during the regrow window restarted the clock (it must do nothing)."),
						TimeSeconds));
				return;
			}
			// (5) set up the re-harvest: a fresh walk-in now that it is active again.
			if (!InduceHarvestOverlap())
			{
				FinishTest(
					EFunctionalTestResult::Failed,
					FString::Printf(TEXT("At t=%.2fs: failed to spawn the re-harvest overlap probe."), TimeSeconds));
				return;
			}
			break;
		}
		case 4:
		{
			// (6) "it can be harvested again after returning to active". Previously
			// the run ended once the tag cleared, so a host that woke up permanently
			// inert - never harvestable a second time - scored a full pass.
			if (!HasRegrowingTag(Harvestable))
			{
				FinishTest(
					EFunctionalTestResult::Failed,
					FString::Printf(
						TEXT("At t=%.2fs: after returning to active the harvestable was walked into again but did not begin regrowing; it must be harvestable again."),
						TimeSeconds));
				return;
			}
			// Every leg verified — the base finishes the test as success.
			break;
		}
		default:
			break;
	}
}

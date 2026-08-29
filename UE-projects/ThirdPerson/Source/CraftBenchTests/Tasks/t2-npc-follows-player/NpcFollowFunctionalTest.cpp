// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// ANpcFollowFunctionalTest implementation. PIE-native (see header). The base
// (ACraftBenchFunctionalTest) owns the PIE lever, fixed-timestep, and the
// checkpoint clock; this fixture owns the tagged-actor resolution, the NPC
// continuity guard, the mid-run hero relocation + escape walk, and the three
// distance-gated assertions. All FAIL message text is ASCII-only (the cp1252
// log read-back rule).

#include "NpcFollowFunctionalTest.h"

#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "Kismet/GameplayStatics.h"

namespace
{
	static const FName ChaserNpcTag(TEXT("ChaserNpc"));
	static const FName FollowHeroTag(TEXT("FollowHero"));

	// cp0 floor: the NPC is authored ~1,615uu from the PlayerStart. A run that
	// begins with the NPC already this close to the player did not FOLLOW —
	// it started on top of the target (or was snapped there before cp0).
	constexpr double KStartMinDistance = 800.0;

	// cp1 follow gate: distance must shrink below this fraction of the
	// run-measured start distance. The reference (default character ground
	// speed ~600uu/s over the 3s follow phase) fully arrives — measuring a
	// ratio near 0.1 — while a stalled NPC measures 1.0. 0.55 also passes a
	// legitimately slower mover that closed only ~half the gap.
	constexpr double KFollowRatio = 0.55;

	// cp3 re-acquisition tolerance vs the player's CURRENT position. The
	// reference path-follows to its acceptance radius (~100uu) plus capsule
	// separation; 350 absorbs both plus one re-issue period of drift.
	constexpr double KReacquireTolerance = 350.0;

	// Continuity guard: the largest single-frame displacement a walking NPC
	// can legitimately make. Default character ground speed 600uu/s at the
	// deterministic 60Hz step is 10uu/frame; 50 gives 5x headroom while any
	// teleport-style relocation (hundreds of uu) trips it by an order of
	// magnitude.
	constexpr double KMaxFrameStepUU = 50.0;

	// Where the fixture relocates the hero at cp1 (far corner of the floor,
	// on the navmesh) and the direction it then walks it for one second —
	// ending near X=2100. Both are fixture-chosen and undisclosed; a solution
	// that re-read the player's position exactly once at relocation time
	// still ends ~500uu short of the player's final spot and fails cp3.
	const FVector KRelocatedHeroSpot(2600.0, -600.0, 92.0);
	const FVector KHeroEscapeDir(-1.0, 0.0, 0.0);
}

ANpcFollowFunctionalTest::ANpcFollowFunctionalTest(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
}

void ANpcFollowFunctionalTest::PrepareTest()
{
	Super::PrepareTest();  // base: snapshot FApp globals + set fixed dt

	UWorld* World = GetWorld();
	if (World == nullptr)
	{
		FinishTest(EFunctionalTestResult::Error, TEXT("HARNESS-PRECONDITION: PrepareTest: no UWorld available"));
		return;
	}

	// Identity by tag, never by class: agents may subclass the NPC (the
	// ctor-stamped tag inherits) and the hero is whatever the game mode
	// possessed at the PlayerStart.
	TArray<AActor*> Found;
	UGameplayStatics::GetAllActorsWithTag(World, ChaserNpcTag, Found);
	if (Found.Num() != 1)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("Expected exactly one actor tagged 'ChaserNpc' (the enemy) in the running level; found %d."), Found.Num()));
		return;
	}
	Npc = Found[0];

	Found.Reset();
	UGameplayStatics::GetAllActorsWithTag(World, FollowHeroTag, Found);
	if (Found.Num() != 1)
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("Expected exactly one actor tagged 'FollowHero' (the game-mode-possessed player character) in the running level; found %d."), Found.Num()));
		return;
	}
	Hero = Cast<ACharacter>(Found[0]);
	if (!Hero.IsValid())
	{
		FinishTest(EFunctionalTestResult::Failed,
			TEXT("HARNESS-PRECONDITION: PrepareTest: the 'FollowHero' actor is not a Character (map/game-mode contract broken)"));
		return;
	}

	// cp0 at 1.0 (nav data live, actors settled), cp1 at 4.0 (3s follow
	// phase), cp2 at 5.0 (hero escape walk ends), cp3 at 9.5 (~4.5s to
	// re-acquire across ~2,200uu at default ground speed). The continuity
	// guard covers every frame from cp0 on (see Tick).
	SetCheckpointSchedule({ 1.0, 4.0, 5.0, 9.5 });
}

void ANpcFollowFunctionalTest::Tick(float DeltaSeconds)
{
	// CONTINUOUS teleport guard — evaluated BEFORE the base checkpoint clock
	// so the frame that CROSSES the final checkpoint is still covered (after
	// Super::Tick finishes the test, IsRunning() is false and a last-frame
	// jump would go unchecked). A per-checkpoint sample alone would miss a
	// timed relocation that fires between checkpoints. Armed at cp0 so
	// spawn/settle noise before the first checkpoint never trips it. Only
	// the NPC is guarded; the HERO is fixture-relocated by design.
	if (IsRunning() && bGuardArmed && Npc.IsValid())
	{
		const FVector NpcPos = Npc->GetActorLocation();
		if (FVector::Dist2D(NpcPos, LastNpcPos) > KMaxFrameStepUU)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(TEXT("Expected the enemy to move continuously toward the player; observed it moved by a discontinuous jump (%.0f units in one frame)."),
					FVector::Dist2D(NpcPos, LastNpcPos)));
			return;
		}
		LastNpcPos = NpcPos;
	}

	Super::Tick(DeltaSeconds);  // base runs the checkpoint clock

	if (!IsRunning())
	{
		return;
	}

	// Sustain the hero's escape walk (movement input is consumed per frame).
	if (bDrivingHero && Hero.IsValid())
	{
		Hero->AddMovementInput(KHeroEscapeDir, 1.0f);
	}
}

bool ANpcFollowFunctionalTest::GuardActors(int32 CheckpointIndex)
{
	if (!Npc.IsValid() || !Hero.IsValid())
	{
		FinishTest(
			EFunctionalTestResult::Failed,
			FString::Printf(TEXT("At checkpoint %d: the enemy or the player character is no longer valid (neither may be destroyed)."), CheckpointIndex));
		return false;
	}
	return true;
}

double ANpcFollowFunctionalTest::DistanceNpcToHero() const
{
	return (Npc.IsValid() && Hero.IsValid())
		? FVector::Dist2D(Npc->GetActorLocation(), Hero->GetActorLocation())
		: TNumericLimits<double>::Max();
}

void ANpcFollowFunctionalTest::OnCheckpoint(int32 CheckpointIndex, double TimeSeconds)
{
	if (!GuardActors(CheckpointIndex))
	{
		return;
	}
	const double Distance = DistanceNpcToHero();
	UE_LOG(LogTemp, Display, TEXT("[t2-npcfollow calib] cp%d t=%.2f dist=%.1f npc=(%.0f,%.0f) hero=(%.0f,%.0f)"),
		CheckpointIndex, TimeSeconds, Distance,
		Npc->GetActorLocation().X, Npc->GetActorLocation().Y,
		Hero->GetActorLocation().X, Hero->GetActorLocation().Y);

	switch (CheckpointIndex)
	{
	case 0:  // t=1.0 — settled; follow phase begins from here.
		if (Distance < KStartMinDistance)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(TEXT("Expected the enemy to still be far from the player shortly after play begins; observed it already next to the player at the start - it began on top of the player or closed the gap faster than a normal ground move (distance %.0f)."), Distance));
			return;
		}
		StartDistance = Distance;
		LastNpcPos = Npc->GetActorLocation();
		bGuardArmed = true;
		break;

	case 1:  // t=4.0 — the follow gate, ratio of the run-measured baseline.
		if (Distance > StartDistance * KFollowRatio)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(TEXT("Expected the enemy to close the distance to the player during play; observed it is not closing on the player (distance %.0f of starting %.0f)."),
					Distance, StartDistance));
			return;
		}
		// Followed. Now move the target: relocate the hero far away and walk
		// it for one second — re-acquisition must track the CURRENT position.
		Hero->SetActorLocation(KRelocatedHeroSpot, false, nullptr, ETeleportType::TeleportPhysics);
		bDrivingHero = true;
		break;

	case 2:  // t=5.0 — the escape walk ends (~500uu from the relocation spot).
		bDrivingHero = false;
		break;

	case 3:  // t=9.5 — re-acquisition of the moved (and then walked) player.
		if (Distance > KReacquireTolerance)
		{
			FinishTest(
				EFunctionalTestResult::Failed,
				FString::Printf(TEXT("Expected the enemy to keep following after the player moved elsewhere; observed it never re-acquired the moved player (distance %.0f)."), Distance));
			return;
		}
		FinishTest(EFunctionalTestResult::Succeeded, TEXT(""));
		break;

	default:
		break;
	}
}

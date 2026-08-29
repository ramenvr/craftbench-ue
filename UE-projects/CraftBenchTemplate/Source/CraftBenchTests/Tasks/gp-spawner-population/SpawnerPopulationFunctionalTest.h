// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// ASpawnerPopulationFunctionalTest — L2 verifier fixture for task
// gp-spawner-population (the g2-4 "Spawner" port). Placed in
// L_SpawnerPopulation.umap alongside the SpawnerRoot-tagged host actor.
// PIE-native: the engine ticks the actor, BeginPlay auto-fires on the host
// (spawning the population), and FTimerManager runs — so a timer- OR
// delegate- OR tick-based solution is sampled correctly with no manual ticking.
//
// Checkpoint contract (seconds since the PIE world began play, 60Hz fixed-step):
//   t=0.5s — exactly 5 SpawnedMinion actors, each within radius of the host
//            (spawn-on-BeginPlay). The fixture then destroys ONE minion.
//   t=1.5s — exactly 5 SpawnedMinion actors again (respawn-on-destroy). The
//            fixture then destroys the host actor.
//   t=2.5s — exactly 0 SpawnedMinion actors (cleanup-on-destroy).

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "SpawnerPopulationFunctionalTest.generated.h"

UCLASS()
class CRAFTBENCHTESTS_API ASpawnerPopulationFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	ASpawnerPopulationFunctionalTest(const FObjectInitializer& ObjectInitializer);

	virtual void PrepareTest() override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	/** Host location cached in PrepareTest (the host is static; this anchors the
	 *  radius check even after the host is destroyed at checkpoint 1). */
	FVector SpawnerLocation = FVector::ZeroVector;
};

// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// ACraftingQueueFunctionalTest — L2 verifier fixture for task gp-crafting-queue
// (the g2-5 "Crafting queue" port). Placed in L_CraftingQueue.umap alongside the
// CraftQueueRoot-tagged host actor. PIE-native: the engine ticks the actor,
// BeginPlay auto-fires on the host (queuing the actions and starting the timer),
// and FTimerManager runs — so a timer- OR tick-paced solution is sampled
// correctly with no manual ticking.
//
// Checkpoint contract (seconds since the PIE world began play, 60Hz fixed-step):
//   t=0.5s — exactly 0 CraftCompleted actors (nothing finishes before ~1s).
//   t=1.5s — exactly 1 CraftCompleted actor (first craft done by ~1s).
//   t=2.5s — exactly 2 CraftCompleted actors (second craft done by ~2s).
//   t=3.5s — exactly 3 CraftCompleted actors (third craft done by ~3s).
//   t=4.5s — exactly 4 CraftCompleted actors (all four done by ~4s).
// The strictly +1-per-second sequence gates one-at-a-time FIFO pacing AND that
// all four actions complete; a burst / stall / too-fast solution fails an
// exact-count assertion.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "CraftingQueueFunctionalTest.generated.h"

UCLASS()
class CRAFTBENCHTESTS_API ACraftingQueueFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	ACraftingQueueFunctionalTest(const FObjectInitializer& ObjectInitializer);

	virtual void PrepareTest() override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;
};

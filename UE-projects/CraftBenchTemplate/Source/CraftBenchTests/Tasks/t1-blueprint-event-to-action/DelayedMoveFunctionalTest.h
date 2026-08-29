// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE -- DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// ADelayedMoveFunctionalTest -- L2 verifier fixture for task
// t1-blueprint-event-to-action.
//
// The agent edits the pre-existing Blueprint asset
// /Game/Tasks/t1-blueprint-event-to-action/BP_DelayedMover (a subclass of the
// ADelayedMoverActor scaffold) so that the one instance placed in L_DelayedMove
// waits 1.0 s after gameplay begins, then makes one single 300-unit move along
// world +X, and never moves again. This fixture:
//
//   1. PrepareTest() resolves the placed actor by the "DelayedMoverRoot" tag
//      (never by class -- agents may subclass), then applies three
//      asset-surface pins: the Blueprint asset exists at its required path,
//      the placed actor is an instance of it, and the Blueprint chain itself
//      implements a start-of-gameplay or per-frame event (the behavior must
//      live in the editable asset, not in an edit to the C++ parent -- a
//      Blueprint-implemented event materializes as a UFunction on the
//      Blueprint-generated class; a C++ edit never creates one there).
//   2. Checkpoints at world game-time {0.5, 1.5, 2.5} s sample the actor's
//      location: still at the placed start at 0.5 (delay respected), at
//      start + (300, 0, 0) at 1.5 (move completed, +/-2 units), and still
//      there at 2.5 (no further movement).
//
// Identity is pinned in PrepareTest (weak pointer): a destroy-and-respawn
// stand-in reads null at the next checkpoint and fails by name. The base class
// (ACraftBenchFunctionalTest) owns the PIE lever, fixed-timestep determinism,
// and the checkpoint clock -- never re-implement those here.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "DelayedMoveFunctionalTest.generated.h"

UCLASS()
class CRAFTBENCHTESTS_API ADelayedMoveFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	ADelayedMoveFunctionalTest(const FObjectInitializer& ObjectInitializer);

	virtual void PrepareTest() override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	/** The one placed mover, resolved by tag in PrepareTest. Weak on purpose:
	 *  identity is pinned to this instance, so a destroyed-and-respawned
	 *  stand-in reads null and fails with a named message. */
	TWeakObjectPtr<AActor> TargetActor;
};

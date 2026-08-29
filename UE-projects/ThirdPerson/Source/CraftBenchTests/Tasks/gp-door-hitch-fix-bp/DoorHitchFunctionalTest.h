// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// ADoorHitchFunctionalTest — the gp-door-hitch-fix-bp fixture (the Edit(Debug)
// family's first member). The level places one door actor tagged 'HitchDoor'
// whose Blueprint the agent EDITS in place; the shipped baseline snaps when
// its Interact entry fires mid-swing (the restart-instead-of-resume defect),
// and the graded fix is CONTINUITY, observed per-tick.
//
// Owner constraint (scaleup slate T2.3, 2026-08-07): the continuity gate runs
// on a Tick override, NOT on OnCheckpoint — checkpoint spacing is 0.4-1.5 s
// and a one-frame teleport is invisible at that resolution. Tick calls Super
// first (the base checkpoint clock stays the sequencer); the monitor only
// samples.
//
// Behavior gates, each a distinct FinishTest(Failed) literal (ASCII only):
//   quiet window        the door must not move before any Interact
//   opens               Interact from closed opens it (>= MinSwingDeg)
//   closes              Interact from open returns it to the closed pose
//   mid-swing reversal  Interact while swinging must NOT teleport the door
//                       (max single-tick jump, angle + position) ...
//   reversal honored    ... and must actually reverse it (ends closed)
//
// No gameplay tags anywhere in this fixture (the Editor-type module's native
// tag hazard is documented; actor tags are plain FNames).

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"

#include "DoorHitchFunctionalTest.generated.h"

class UStaticMeshComponent;

UCLASS()
class CRAFTBENCHTESTS_API ADoorHitchFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	ADoorHitchFunctionalTest(const FObjectInitializer& ObjectInitializer);

	/** Resolves the tagged door + its mesh parts + the Interact seam, then
	 *  sets the checkpoint schedule. */
	virtual void PrepareTest() override;

	/** Super first (base checkpoint clock), then the per-tick continuity
	 *  monitor: world-rotation and world-location deltas of every tracked
	 *  mesh part since the previous tick. */
	virtual void Tick(float DeltaSeconds) override;

protected:
	/** The phase sequencer: fires Interacts and evaluates the pose gates. */
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	/** FindFunction('Interact') with the sprint-fixture parameter law: a
	 *  return value is tolerated, any real parameter is not. */
	UFunction* ResolveInteractSeam() const;
	void FireInteract();

	/** Max over tracked parts of the angular distance (degrees) between the
	 *  part's current world rotation and its recorded closed pose. */
	double DisplacementFromClosedDeg() const;

	/** Records each part's current world transform as the closed pose. */
	void RecordClosedPose();

	TWeakObjectPtr<AActor> Door;
	UFunction* InteractFn = nullptr;

	/** Tracked mesh parts (resolved once in PrepareTest) + their poses. */
	TArray<TWeakObjectPtr<UStaticMeshComponent>> Parts;
	TArray<FQuat> ClosedRotations;
	TArray<FVector> ClosedLocations;
	TArray<FQuat> PrevRotations;
	TArray<FVector> PrevLocations;
	bool bHavePrevSample = false;

	/** Continuity monitor state (armed from the first Interact). */
	bool bMonitorArmed = false;
	double MaxTickAngleDeg = 0.0;
	double MaxTickAngleTime = 0.0;
	double MaxTickLocDelta = 0.0;
	double MaxTickLocTime = 0.0;

};

// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// ATeleportPortalFunctionalTest — L2 verifier fixture for task
// t1-overlap-teleport-portal. Lives at
// Source/CraftBenchTests/Tasks/t1-overlap-teleport-portal/. Placed in
// Content/Maps/t1-overlap-teleport-portal/L_TeleportPortal.umap alongside the
// "TeleportPortal"-tagged portal frame and the "TeleportDestination"-tagged
// marker.
//
// PIE-native: the engine ticks this fixture. The fixture supplies its own
// moving body — it spawns a plain engine ACharacter, possesses it via
// SpawnDefaultController() (possession is MANDATORY: an unpossessed Character
// is inert — Slice-0 spike), and sustains locomotion toward the portal by
// feeding AddMovementInput every frame while driving (movement input is
// consumed per frame; never tick the world). In PrepareTest the fixture MOVES
// the destination marker to a fixture-chosen spot, so a solution that bakes in
// the marker's authored map coordinates delivers to the wrong place and fails
// the delivery gate — the marker's position must be read at teleport time.
//
// Checkpoint contract (world game-time; walker contact with the portal is
// expected at ~1.9s given the ~740uu approach at default character ground
// speed):
//   t=0.5 — walker settled, NOT near the destination; start driving
//   t=3.5 — walker delivered: within DeliverTolerance of the marker's
//           fixture-chosen spot; then relocate the walker RelocateOffset away
//           and stop driving. The failure message is BRANCHED on where the
//           walker actually is: still near the portal (never relocated — the
//           empty-submission shape) vs relocated somewhere that is not the
//           destination (the memorized-coordinates shape) — two distinct
//           named substrings.
//   t=5.0 — walker still away from the destination (no repeated snapping)
//           -> PASS
// Between cp0 and delivery, Tick runs a CONTINUOUS pre-contact guard: if the
// walker turns up at the destination while its best approach progress
// (MaxApproachX) is still short of the portal's contact zone, the delivery
// happened without contact — a timer/BeginPlay unconditional teleport — and
// the test FAILs immediately with the same named message as cp0. A
// single-instant cp0 sample alone would miss any cheat that fires in the
// (0.5s, contact] window.
// The drive stops automatically once the walker crosses the portal's X plane,
// so an un-teleported walker brakes just past the portal instead of walking
// toward the destination on its own. All FAIL message text is ASCII-only (the
// cp1252 log read-back rule). The four FinishTest(Error) precondition paths
// carry a "HARNESS-PRECONDITION: " prefix — today they still GRADE as a FAIL
// (automation Error lands as state Fail in index.json); the prefix is the
// hook for a future runner-side routing rule.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "TeleportPortalFunctionalTest.generated.h"

class ACharacter;

UCLASS()
class CRAFTBENCHTESTS_API ATeleportPortalFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	ATeleportPortalFunctionalTest(const FObjectInitializer& ObjectInitializer);

	virtual void PrepareTest() override;

	/** Chains the base checkpoint clock, then sustains movement input toward
	 *  the portal while driving. Never ticks the world. */
	virtual void Tick(float DeltaSeconds) override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	/** Shared per-checkpoint guard: walker still valid. Returns false after
	 *  raising the named FAIL. */
	bool GuardWalker(int32 CheckpointIndex);

	/** 3D distance from the walker to the fixture-chosen destination spot. */
	double DistanceToDestination() const;

	TWeakObjectPtr<ACharacter> Walker;
	TWeakObjectPtr<AActor> Portal;
	TWeakObjectPtr<AActor> Marker;

	/** The fixture-chosen spot the marker is moved to in PrepareTest. */
	FVector DestinationSpot = FVector::ZeroVector;

	/** Portal center cached at PrepareTest; the drive target and stop plane. */
	FVector PortalSpot = FVector::ZeroVector;

	/** Best (largest) X the walker has WALKED to while approaching — updated
	 *  only on un-delivered ticks, so a teleport cannot inflate it. The
	 *  continuous pre-contact guard reads it to tell "delivered on contact"
	 *  from "delivered while still short of the portal". */
	double MaxApproachX = 0.0;

	bool bDriving = false;
};

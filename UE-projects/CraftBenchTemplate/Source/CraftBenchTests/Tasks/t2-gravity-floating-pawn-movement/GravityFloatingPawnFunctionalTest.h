// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// AGravityFloatingPawnFunctionalTest — L2 verifier fixture for task
// t2-gravity-floating-pawn-movement. Lives at
// Source/CraftBenchTests/Tasks/t2-gravity-floating-pawn-movement/. Placed in
// Content/Maps/t2-gravity-floating-pawn-movement/L_GravityFloatingPawn.umap
// alongside the "HoverPawn"-tagged pawn (high in clear air — see the map
// contract in the task's notes.md).
//
// PIE-native: the engine ticks this fixture. The fixture resolves the placed
// pawn by tag, possesses it via SpawnDefaultController() (possession is
// MANDATORY — an unpossessed pawn's movement component is inert: the stock
// floating movement gates its whole move on Controller && IsLocalController),
// and judges the gravity-when-idle contract purely from the pawn's measured
// trajectory across three phases:
//
//   phase A (idle,   cp0 t=0.5 -> cp1 t=2.5): the pawn must LOSE altitude —
//           drop within the prompt-disclosed sink band; ratio anchor D_A.
//   phase B (driven, cp1 -> cp2 t=5.0): the fixture feeds AddMovementInput
//           every frame; the pawn must make lateral progress AND hold
//           altitude (Z loss small relative to D_A).
//   phase C (idle,   cp2 -> cp3 t=6.5): input released; sinking must RESUME
//           (drop again a meaningful fraction of D_A).
//
// A continuous continuity guard PAIR runs the whole time: (1) any single
// simulated frame whose |dZ| exceeds KMaxFrameDropUU (~2x the band ceiling
// per fixed 60Hz frame) FAILs immediately — displacement, not motion; and
// (2) a rolling ~0.25s window caps total altitude loss at 1.5x the band
// ceiling, so bursts of sub-per-frame steps trip too. The pair bounds a
// stepped descent's AMPLITUDE — surviving both means the movement is
// fine-grained, band-rate motion. All gates except the disclosed band are
// RATIOS of the run's own phase-A measurement, never absolute world
// constants. Both guard constants are derived for the spec's -FPS=60 leg.
//
// All FAIL message text is ASCII-only (the cp1252 log read-back rule). The
// FinishTest(Error) precondition paths carry a "HARNESS-PRECONDITION: "
// prefix — today they still GRADE as a FAIL (automation Error lands as state
// Fail in index.json); the prefix is the hook for a future runner-side
// routing rule.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "GravityFloatingPawnFunctionalTest.generated.h"

class APawn;

UCLASS()
class CRAFTBENCHTESTS_API AGravityFloatingPawnFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	AGravityFloatingPawnFunctionalTest(const FObjectInitializer& ObjectInitializer);

	virtual void PrepareTest() override;

	/** Chains the base checkpoint clock, then (a) runs the per-frame altitude
	 *  continuity guard and (b) sustains movement input while driving. Never
	 *  ticks the world. */
	virtual void Tick(float DeltaSeconds) override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	/** Shared per-checkpoint guard: pawn still valid. Returns false after
	 *  raising the named FAIL. */
	bool GuardPawn(int32 CheckpointIndex);

	TWeakObjectPtr<APawn> Hover;

	/** Altitude sampled at each checkpoint crossing. */
	double Z0 = 0.0;
	double Z1 = 0.0;
	double Z2 = 0.0;

	/** Lateral (X) position at cp1, for the phase-B progress gate. */
	double X1 = 0.0;

	/** Phase-A drop (Z0 - Z1) — the run's own ratio anchor. */
	double PhaseADrop = 0.0;

	/** Last frame's Z, for the per-frame continuity guard. */
	double LastZ = 0.0;
	bool bHaveLastZ = false;

	/** Rolling window of recent per-frame Z samples (~0.25s at the fixed
	 *  60Hz step), for the windowed rate guard. */
	TArray<double> RecentZ;

	bool bDriving = false;
};

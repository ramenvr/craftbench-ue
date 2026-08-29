// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// ALadderClimbFunctionalTest — L2 verifier fixture for task
// t2-ladder-climb-volume. Lives at Source/CraftBenchTests/Tasks/
// t2-ladder-climb-volume/. Placed in Content/Maps/t2-ladder-climb-volume/
// L_LadderClimb.umap; the map's world settings select ALadderGameMode, which
// spawns and possesses the "ClimbHero"-tagged character at the PlayerStart.
//
// PIE-native: the engine ticks this fixture; the possessed character's
// CharacterMovement ticks. The fixture walks the hero to the ladder with
// per-frame AddMovementInput (movement input is consumed per frame — sampling
// alone would never move the pawn), and requests/ends climbs purely by
// reflection: the fixture compiles against git HEAD, where
// DoClimbStart/DoClimbEnd do not exist, so FindFunction + ProcessEvent is the
// only sound call path. A missing or non-parameterless seam is the named
// FAIL-on-empty gate.
//
// Checkpoint contract (seconds of world game-time, fixed-step; the ladder
// volume's world bounds are read once in PrepareTest — center X ~600, top Z
// ~1200 per the map contract):
//   t=0.6 — hero settled at the PlayerStart, ~540uu from the ladder; record
//           Z0; invoke DoClimbStart AWAY from the ladder (must do nothing)
//   t=1.6 — assert no ascent from the away request; invoke DoClimbEnd; start
//           the walk toward the ladder (arrival ~2.7s at stock ground speed)
//   [arrival, in Tick] — stop the drive, invoke DoClimbStart, record the
//           climb-start height; from here every climb-phase frame runs the
//           per-frame ascent-continuity guard (a one-frame jump > 50uu FAILs)
//   t=4.0 — assert steady ascent actually happened (>= 150uu gained); invoke
//           DoClimbEnd; record the hold height
//   t=5.2 — assert the height HELD (|dZ| <= 60) after the climb was ended;
//           invoke DoClimbStart again
//   [top cross, in Tick] — the hero reaching just under the volume's top is
//           recorded (epsilon BELOW the top, so an exit-at-the-boundary
//           solution is not asked to overshoot); the agent's own
//           leave-the-ladder logic must end the climb
//   t=9.8 — assert the top was actually reached AND the hero has fallen back
//           below it (gravity resumed; a hoverer/riser FAILs). Worst
//           legitimate case: a boundary-exit solution stops at ~top+5 by
//           ~8.2s, leaving >= 1.6s of fall — landed well below top-50 -> PASS
// Every checkpoint logs an ASCII "[t2-ladder calib]" line for calibration.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "LadderClimbFunctionalTest.generated.h"

class ACharacter;
class UFunction;

UCLASS()
class CRAFTBENCHTESTS_API ALadderClimbFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	ALadderClimbFunctionalTest(const FObjectInitializer& ObjectInitializer);

	virtual void PrepareTest() override;

	/** Chains the base checkpoint clock, then runs the phase machine: the walk
	 *  drive, the arrival climb request, the per-frame ascent-continuity guard,
	 *  and the top-exit detection. Never ticks the world. */
	virtual void Tick(float DeltaSeconds) override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	/** Fixture phases, advanced by checkpoints + Tick-side events. */
	enum class EPhase : uint8
	{
		Settling,      // before cp0
		AwayProbe,     // cp0 invoked DoClimbStart away from the ladder
		WalkToLadder,  // cp1 ended the away probe; driving toward the ladder
		Climb1,        // arrived; DoClimbStart invoked at the ladder
		Hold,          // cp2 invoked DoClimbEnd mid-ladder
		Climb2,        // cp3 invoked DoClimbStart again
		Exited,        // the hero crossed the volume's top during Climb2
	};

	/** Resolves a reflected, effectively-parameterless (a return value is
	 *  tolerated; real input parameters are not) UFunction by name on the hero.
	 *  nullptr when absent/unsuitable — the caller raises the named FAIL. */
	UFunction* ResolveParameterlessSeam(const FName FunctionName) const;

	/** ProcessEvent with a properly initialized zeroed parameter buffer (covers
	 *  a tolerated return value). No-op when the hero or function is gone. */
	void InvokeSeam(UFunction* Function);

	/** Shared per-checkpoint guard (hero still valid). Returns false after
	 *  raising the named FAIL. */
	bool GuardHero(int32 CheckpointIndex);

	TWeakObjectPtr<ACharacter> Hero;
	TWeakObjectPtr<AActor> Ladder;
	UFunction* ClimbStartFn = nullptr;
	UFunction* ClimbEndFn = nullptr;

	EPhase Phase = EPhase::Settling;
	FVector LadderCenter = FVector::ZeroVector;
	double LadderTopZ = 0.0;
	double Z0 = 0.0;            // height at cp0 (away probe baseline)
	double ClimbStartZ = 0.0;   // height when the at-ladder climb was requested
	double HoldZ = 0.0;         // height when the climb was ended at cp2
	double LastTickZ = 0.0;     // previous fixture-tick height (continuity guard)
	bool bLastTickZValid = false;
};

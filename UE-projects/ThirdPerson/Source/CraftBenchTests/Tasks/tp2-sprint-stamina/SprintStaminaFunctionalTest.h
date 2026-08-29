// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// ASprintStaminaFunctionalTest — L2 verifier fixture for task
// tp2-sprint-stamina. Lives at Source/CraftBenchTests/Tasks/tp2-sprint-stamina/.
// Placed in Content/Maps/tp2-sprint-stamina/L_TpSprint.umap; the map's world
// settings select ASprintGameMode, which spawns and possesses the
// "SprintHero"-tagged character at the PlayerStart.
//
// PIE-native: the engine ticks this fixture; the possessed character's
// CharacterMovement ticks. The fixture sustains forward locomotion by feeding
// AddMovementInput(+X) every frame while the test runs (movement input is
// consumed per frame — sampling alone would never move the pawn), and invokes
// the agent-defined sprint seam purely by reflection: the fixture compiles
// against git HEAD, where DoSprintStart/DoSprintEnd do not exist, so
// FindFunction + ProcessEvent is the only sound call path. A missing or
// non-parameterless seam is the named FAIL-on-empty gate.
//
// Checkpoint contract (seconds since StartTest, fixed-step; stamina timeline
// per the disclosed constants 100 start/cap, 25/s drain, 20/s regen, 30 floor):
//   t=1.0  — baseline ground speed in [400,600]; record V0; invoke DoSprintStart
//   t=3.0  — sprinting (stamina 50): speed/V0 in [1.55,1.85]
//   t=6.2  — stamina hit 0 at t=5.0, regen to 24 (<30): speed back at V0
//            (ratio <= 1.15); invoke DoSprintStart (below floor — must be
//            ignored AND not remembered)
//   t=7.0  — still baseline: catches both instant below-floor sprint (its
//            illegal sprint is still live until ~7.16) and a latched
//            auto-start when stamina crossed 30 at t=6.5
//   t=9.0  — still baseline (no request pending; stamina ~80); invoke
//            DoSprintStart (above floor)
//   t=10.5 — sprinting again (stamina ~42.5): speed/V0 in [1.55,1.85] -> PASS
// Every checkpoint also asserts the pawn is valid and on the ground, and logs
// an ASCII "[tp2-sprint calib]" line for tolerance calibration.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "SprintStaminaFunctionalTest.generated.h"

class ACharacter;
class UFunction;

UCLASS()
class CRAFTBENCHTESTS_API ASprintStaminaFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	ASprintStaminaFunctionalTest(const FObjectInitializer& ObjectInitializer);

	virtual void PrepareTest() override;

	/** Chains the base checkpoint clock, then sustains forward movement input
	 *  on the possessed character while the test runs. Never ticks the world. */
	virtual void Tick(float DeltaSeconds) override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	/** Resolves a reflected, effectively-parameterless (a return value is
	 *  tolerated; real input parameters are not) UFunction by name on the hero.
	 *  nullptr when absent/unsuitable — the caller raises the named FAIL. */
	UFunction* ResolveParameterlessSeam(const FName FunctionName) const;

	/** ProcessEvent with a properly initialized zeroed parameter buffer (covers
	 *  a tolerated return value). No-op when the hero or function is gone. */
	void InvokeSeam(UFunction* Function);

	/** Ground-speed sample + shared per-checkpoint guards (hero valid, not
	 *  falling). Returns false after raising the named FAIL. */
	bool SampleGroundSpeed(int32 CheckpointIndex, double& OutSpeed);

	TWeakObjectPtr<ACharacter> Hero;
	UFunction* SprintStartFn = nullptr;
	UFunction* SprintEndFn = nullptr;
	double BaselineSpeed = 0.0;
};

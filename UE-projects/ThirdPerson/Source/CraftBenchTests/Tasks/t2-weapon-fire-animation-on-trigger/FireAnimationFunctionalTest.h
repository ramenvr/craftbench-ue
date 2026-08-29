// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// AFireAnimationFunctionalTest — L2 verifier fixture for task
// t2-weapon-fire-animation-on-trigger. Lives at Source/CraftBenchTests/Tasks/
// t2-weapon-fire-animation-on-trigger/. Placed in Content/Maps/
// t2-weapon-fire-animation-on-trigger/L_FireAnimation.umap; the map's world
// settings select AFireGameMode, which spawns and possesses the
// "FireHero"-tagged character at the PlayerStart.
//
// PIE-native: the engine ticks the possessed character's anim instance
// (spike-proven 2026-07-30: montage state is fully observable headless under
// -nullrhi — GetCurrentActiveMontage() returns the active montage and
// Montage_GetPosition advances exactly in step with the fixed dt, on the
// DEFAULT VisibilityBasedAnimTickOption). The fire request is invoked purely
// by reflection: the fixture compiles against git HEAD, where DoFireStart does
// not exist, so FindFunction + ProcessEvent is the only sound call path. A
// missing or non-parameterless seam is the named FAIL-on-empty gate.
//
// Checkpoint contract (seconds of world game-time, fixed-step):
//   t=0.5 — nothing may be playing before any fire request (the anim
//           blueprint's locomotion is not a montage; only montages count);
//           then invoke DoFireStart
//   t=0.8 — a firing animation (montage) must be active
//   t=1.4 — if the same montage is still active its position must have
//           advanced (a paused/frozen start is not "playing"); a montage that
//           already ran its natural length and ended passes this gate
//   t=6.0 — nothing may be playing anymore: the animation ran once for its
//           natural length and ended (the prompt discloses "a second or two,
//           not on a loop")
// Every checkpoint logs an ASCII "[t2-fireanim calib]" line for calibration.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "FireAnimationFunctionalTest.generated.h"

class ACharacter;
class UAnimInstance;
class UAnimMontage;
class UFunction;

UCLASS()
class CRAFTBENCHTESTS_API AFireAnimationFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	AFireAnimationFunctionalTest(const FObjectInitializer& ObjectInitializer);

	virtual void PrepareTest() override;

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

	/** The hero's anim instance, re-read per checkpoint (an agent may swap the
	 *  mesh's anim class at runtime). nullptr raises the named graded FAIL. */
	UAnimInstance* ResolveAnimInstance(int32 CheckpointIndex);

	/** Shared per-checkpoint guard (hero still valid). Returns false after
	 *  raising the named FAIL. */
	bool GuardHero(int32 CheckpointIndex);

	TWeakObjectPtr<ACharacter> Hero;
	UFunction* FireStartFn = nullptr;

	TWeakObjectPtr<UAnimMontage> FireMontage;  // what cp1 saw active
	float PositionAtCp1 = -1.f;
};

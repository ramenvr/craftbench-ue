// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// See Source/CraftBenchTests/.AGENT_WRITE_DENY for the no-edit policy.
//
// AHomingProjectileFunctionalTest — L2 verifier fixture for task
// t2-homing-projectile. PIE-native: BeginPlay auto-fires on the placed
// launcher, which must fire ONE projectile tagged "HomingMissile" that
// continuously steers toward the target.
//
// Discrimination design:
//  * at checkpoint 1 (t=1.0s) the fixture RELOCATES the target +800 units
//    laterally — a straight-line shot aimed at the original position stops
//    closing and fails; only genuine homing keeps closing;
//  * the projectile's IDENTITY IS PINNED at first sighting — interception
//    counts only for the pinned actor, so destroy-and-respawn-at-target is
//    just "the projectile disappeared";
//  * PER-FRAME displacement is policed against the disclosed max speed
//    (1200 u/s, generous slack) — a SetActorLocation teleport between
//    checkpoints is caught even though sampling gates run at checkpoints;
//  * at the first checkpoint (0.5s) the projectile must still be far away
//    (> 55% of the initial launcher->target distance) — spawn-at-target
//    cheats fail;
//  * interception = per-frame MIN distance < 150 units; the test
//    EARLY-SUCCEEDS at the first checkpoint after interception, so a
//    destroy-on-hit projectile never fails a later existence check.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "HomingProjectileFunctionalTest.generated.h"

UCLASS()
class CRAFTBENCHTESTS_API AHomingProjectileFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	AHomingProjectileFunctionalTest(const FObjectInitializer& ObjectInitializer);

	virtual void PrepareTest() override;
	virtual void Tick(float DeltaSeconds) override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	/** Count actors currently tagged HomingMissile (for the exactly-one gate). */
	int32 CountMissiles(TArray<AActor*>& OutFound) const;
	/** Distance from the pinned missile to the CURRENT target location. */
	double MissileTargetDistance() const;

	TWeakObjectPtr<AActor> Target;
	/** The ONE projectile, pinned at first sighting; identity is load-bearing. */
	TWeakObjectPtr<AActor> Missile;
	FVector LauncherLocation = FVector::ZeroVector;
	double InitialDistance = 0.0;
	/** Distance at the previous checkpoint (re-baselined after the target move). */
	double PrevDistance = -1.0;
	double PrevCheckpointTime = 0.0;
	/** Per-frame minimum pinned-missile->target distance seen so far.
	 *  (Sentinel large value, NOT TNumericLimits<double>::Max() — a template
	 *  call in a UCLASS default member initializer crashes UE 5.8's UHT with
	 *  "Unhandled aggregate exceptions", killing parent-class registration
	 *  for the whole module.) */
	double MinDistanceSeen = 1.0e18;
	/** Per-frame teleport detection on the pinned missile. */
	FVector LastMissileLocation = FVector::ZeroVector;
	bool bHaveLastLocation = false;
	double WorstFrameSpeed = 0.0;   // u/s, max per-frame displacement rate seen
	bool bImpossibleMotion = false;
	bool bTargetMoved = false;
};

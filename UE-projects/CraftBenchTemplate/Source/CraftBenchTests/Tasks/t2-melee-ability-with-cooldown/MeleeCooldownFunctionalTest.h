// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT (policy: Source/CraftBenchTests/.AGENT_WRITE_DENY).
//
// AMeleeCooldownFunctionalTest — L2 fixture for task t2-melee-ability-with-cooldown.
// Pins the two map-shipped MeleeDummy targets BEFORE the base spawns the agent
// pawn (so nothing the pawn's BeginPlay spawns can be pinned), then places them
// relative to the settled pawn (near = in reach and in front, far = well
// outside), and drives the strike by the Ability.Melee tag on a schedule whose
// traps sit INSIDE the cheat windows. Cooldown window: 0.6 + 2.0 = 2.6.
//   cp0 (0.6): position targets, equal-baseline check, trigger #1 (empty leg
//              dies here on the granted/activated checks).
//   cp1 (1.2): near damaged, far untouched; RE-trigger (inside the window).
//   cp2 (1.8): near UNCHANGED since cp1 — the cooldown held.
//   cp3 (2.2): second in-window RE-trigger (narrows the accepted band: a
//              cooldown ending before ~2.5 lets this one land).
//   cp4 (2.5): near still unchanged — the window reaches at least this far.
//   cp5 (3.4): near STILL unchanged (a buffered in-window trigger executing at
//              expiry would show here — the deferred-strike trap), then
//              trigger #3, now past the 2.6 expiry.
//   cp6 (4.0): near dropped again — the strike recovered; far still untouched.
// Dummy Health is read by REFLECTION (FindFProperty on "Health") so agent
// subclasses of the dummy stay legal.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchPawnFunctionalTest.h"
#include "MeleeCooldownFunctionalTest.generated.h"

UCLASS()
class CRAFTBENCHTESTS_API AMeleeCooldownFunctionalTest : public ACraftBenchPawnFunctionalTest
{
	GENERATED_BODY()

public:
	AMeleeCooldownFunctionalTest(const FObjectInitializer& ObjectInitializer);

	virtual void PrepareTest() override;

protected:
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;
	virtual FGameplayTag PreferredAbilityTag() const override;

private:
	/** Reflection read of the actor's float "Health". Sets bOk=false when the
	 *  property is absent/not a float (agent-caused: a tagged target must keep
	 *  the disclosed Health contract). */
	double ReadHealth(AActor* Target, bool& bOk) const;

	/** Shared far-target gate for cp1 and cp6: FinishTest(Failed) and return
	 *  false if the far target's health moved off its baseline. */
	bool FarStillUntouched(double FarNow);

	int32 LastCheckpointIndex = 0;

	/** The two map-shipped targets, pinned BEFORE the agent pawn exists
	 *  (name-sorted). Pawn-BeginPlay-spawned decoys are never candidates. */
	TWeakObjectPtr<AActor> NearDummy;
	TWeakObjectPtr<AActor> FarDummy;
	int32 PinnedTaggedCount = 0;

	// Recorded values (guard on the capture FLAGS, not sentinels — Health may
	// legitimately go negative).
	double NearBase = 0.0, FarBase = 0.0;
	double NearAfterFirst = 0.0;
	bool bBaselineCaptured = false;
	bool bAfterFirstCaptured = false;

	// Calibrated bands.
	double MinDamage = 1.0;       // a strike must remove at least this much Health
	double NoChangeEpsilon = 0.1; // "untouched/unchanged" tolerance
	double NearDistance = 150.0;  // inside the disclosed ~250uu reach
	double FarDistance = 900.0;   // far outside it
};

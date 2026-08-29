// Copyright CraftBench. All Rights Reserved.
//
// L2 for t1-spikes-hurt-you-and-you-respawn-at-your-marker.
//
// Three corpus rows merged into one run -- hurt, die, come back -- graded with
// SEPARATELY NAMED assertions per segment, so "damage works but the respawn target
// is wrong" and "nothing was built" are different verdicts.
//
// Contact is computed GEOMETRICALLY by this fixture (the slab's world box expanded
// by the capsule), never taken from the submission's own overlap plumbing: a
// submission cannot make itself look contacted, and any legitimate detection route
// grades identically.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "SpikeContactRespawnFunctionalTest.generated.h"

class ACharacter;

UCLASS()
class ASpikeContactRespawnFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	ASpikeContactRespawnFunctionalTest(const FObjectInitializer& ObjectInitializer);

protected:
	virtual void PrepareTest() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	/** One leg of the walk: waypoints in order, then the phase advances. */
	struct FPhase
	{
		TArray<FVector> Waypoints;
		/** Seconds this phase may take before DriveReachedItsWaypoints fires. */
		double Deadline = 0.0;
		/** Stand still here until the driven character's health reaches zero. */
		bool bWaitForDeath = false;
		/** Hold position for this long once the waypoints are done. */
		double HoldSeconds = 0.0;
		const TCHAR* Label = TEXT("");
	};

	bool ResolveStaging();
	AActor* FindDriven() const;
	AActor* FindTwin() const;

	/** Reflection reads of the SUPPLIED surfaces. */
	float ReadHealth(AActor* Character) const;
	int32 ReadCurrentPadOrder() const;
	bool ReadPadMarked(AActor* Pad) const;
	int32 ReadPadOrder(AActor* Pad) const;
	/** First run of digits in the floating number; -1 when there is none. */
	int32 ReadFloatingNumber(AActor* Character) const;

	bool TouchingSlab(AActor* Character) const;
	bool StandingOnPad(AActor* Character, AActor* Pad) const;

	void AdvancePhase(double Now);
	/** Runs when the last leg closes: the gates that are vacuous unless their
	 *  leg actually happened, each with its own precondition-reached message. */
	void FinalGrade();
	void LogCalib(int32 Index, double Now) const;

	TWeakObjectPtr<AActor> Course;
	TWeakObjectPtr<AActor> Slab;
	TWeakObjectPtr<AActor> StartMark;
	TWeakObjectPtr<AActor> Pad1;
	TWeakObjectPtr<AActor> Pad2;
	TWeakObjectPtr<AActor> Twin;
	FVector TwinStart = FVector::ZeroVector;
	/** The far end of the bystander's lane, and how far it has actually walked. A
	 *  control that never moves proves only that a submission did not damage a
	 *  stationary object; this one has to be exercised or the gate is empty. */
	FVector TwinPatrolTo = FVector::ZeroVector;
	FVector TwinWasAt = FVector::ZeroVector;
	double TwinTravelled = 0.0;
	bool bTwinOutbound = true;
	FVector SlabStart = FVector::ZeroVector;
	FVector RailA = FVector::ZeroVector;
	FVector RailB = FVector::ZeroVector;

	TArray<FPhase> Phases;
	int32 PhaseIndex = -1;
	int32 Waypoint = 0;
	double PhaseStarted = 0.0;
	double HoldUntil = -1.0;

	/** Damage bookkeeping, all fixture-owned. */
	bool bWasTouching = false;
	int32 ContactWindows = 0;
	float HealthAtWindowOpen = 100.0f;
	float LastHealth = 100.0f;
	int32 DeductionsThisWindow = 0;
	bool bSlabEverMoved = false;
	double SlabMovedAfterContactAt = -1.0;
	double FirstContactAt = -1.0;

	/** Death bookkeeping. */
	int32 Deaths = 0;
	double DeathAt = -1.0;
	bool bAwaitingRespawn = false;
	FVector RespawnExpectedAt = FVector::ZeroVector;
	const TCHAR* RespawnExpectedName = TEXT("");
	double RespawnSeenAt = -1.0;
	FVector RespawnSeenLocation = FVector::ZeroVector;

	/** Pad bookkeeping. */
	bool bPad1Entered = false;
	bool bPad2Entered = false;
	bool bWalkedBackOntoPad1 = false;
	bool bReTouchedCurrentPad = false;
	bool bRollBackSeen = false;
};

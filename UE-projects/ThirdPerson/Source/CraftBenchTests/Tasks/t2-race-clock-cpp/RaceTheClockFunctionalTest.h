// Copyright CraftBench. All Rights Reserved.
//
// L2 for t2-race-clock.
//
// The clock is the interesting half: it is checked CONTINUOUSLY against the world's
// own play time, not only at the end, so a round that jumps straight to zero or
// drifts and then snaps right fails while it is happening.

#pragma once

#include "CoreMinimal.h"
#include "CraftBenchFunctionalTest.h"
#include "RaceTheClockFunctionalTest.generated.h"

class ACharacter;
class UTextRenderComponent;

UCLASS()
class ARaceTheClockFunctionalTest : public ACraftBenchFunctionalTest
{
	GENERATED_BODY()

public:
	ARaceTheClockFunctionalTest(const FObjectInitializer& ObjectInitializer);

protected:
	virtual void PrepareTest() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void OnCheckpoint(int32 CheckpointIndex, double TimeSeconds) override;

private:
	struct FCoin
	{
		TWeakObjectPtr<AActor> Actor;
		FVector Placed = FVector::ZeroVector;
		int32 Value = 0;
		bool bConsumed = false;
	};

	bool ResolveStaging();
	int32 ReadScore() const;
	float ReadTimeRemaining() const;
	FString ReadRoundState() const;
	FString ReadFace(const TCHAR* Name) const;
	int32 ReadCoinValue(AActor* Coin) const;
	bool CoinVisiblyGone(const FCoin& Coin) const;

	/** Every frame: are the readouts facing the player, and has the replay pad been
	 *  asked for a second round yet. */
	void SampleReadoutsAndReplay();
	void LogCalib(int32 Index, double Now) const;

	TWeakObjectPtr<AActor> Round;
	TWeakObjectPtr<ACharacter> Hero;
	TArray<FCoin> Coins;
	/** The one the route never visits. */
	int32 ControlIndex = INDEX_NONE;

	/** Waypoints in order; the drive holds at the last pre-deadline one. */
	TArray<FVector> Route;
	int32 Waypoint = 0;
	bool bWaitingOutTheClock = false;

	/** The replay pad, resolved by TAG from the level -- the pattern that has been
	 *  reliable here. An earlier version looked for a component by name on the round
	 *  board and silently got the origin, which the drive then "reached" by walking
	 *  through the middle of the arena. */
	TWeakObjectPtr<AActor> ReplayPad;
	FVector ReplayPadAt = FVector::ZeroVector;
	/** Rounds seen. The clock coming back up from nothing is a new one. */
	int32 RoundsSeen = 1;
	float RoundSeconds = 10.0f;
	bool bWasTimedOut = false;
	/** How often the readouts were sampled, and how often they faced the character. */
	int32 FacingSamples = 0;
	int32 FacingHits = 0;
	bool bStoodOnReplayPad = false;
	/** World time the CURRENT round started, so the clock can be checked across
	 *  a replay rather than only across the first round. */
	double RoundStartedAtWorld = 0.0;

	int32 LastScore = 0;
	int32 ExpectedScore = 0;
	bool bEverTimedOut = false;
	int32 ScoreAtTimeout = 0;
	double TimeoutSeenAt = -1.0;
};

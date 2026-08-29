// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION for t2-race-clock.
//
// Three things beyond banking the points: the readouts TURN TO FACE the character
// every frame, the clock is measured from when THIS round started rather than from
// world time (a clock derived from world time can only ever count down once, which
// makes a replay impossible however the pad is wired), and stepping onto the supplied
// replay pad after the round has timed out starts a fresh one.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "RaceRoundBase.generated.h"

class USceneComponent;
class UTextRenderComponent;

UCLASS()
class THIRDPERSON_API ARaceRoundBase : public AActor
{
	GENERATED_BODY()

public:
	ARaceRoundBase();

	/** Whole points banked so far. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Round")
	int32 Score = 0;

	/** Seconds left in the round. Never negative. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Round")
	float TimeRemaining = 10.0f;

	/** InProgress before zero, TimedOut at and after it. Those two words only. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Round")
	FString RoundState = TEXT("InProgress");

	/** Unscaled root, so the readout offsets below are plain centimetres. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Round")
	USceneComponent* BoardRoot = nullptr;

	/** The three readouts. All ship showing frozen placeholder text. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Round")
	UTextRenderComponent* ScoreText = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Round")
	UTextRenderComponent* ClockText = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Round")
	UTextRenderComponent* StateText = nullptr;

	/** A coin was consumed: bank its value. Ignored once the round has ended. */
	void AddPoints(int32 Points);

	bool IsRoundRunning() const { return RoundState == TEXT("InProgress"); }

protected:
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

private:
	void RefreshFaces();
	/** Turn the three readouts to face a watcher, about the vertical only. */
	void FaceTheReadoutsAt(const FVector& Watcher);
	/** Full clock, no score, running again. */
	void StartFreshRound();

	/** The supplied pad, found once by tag. */
	TWeakObjectPtr<AActor> ReplayPad;
	/** When THIS round started. */
	double RoundStartedAt = 0.0;
	/** So the pad has to be STEPPED ON: somebody already standing there when the
	 *  clock runs out does not get an endless string of rounds. */
	bool bReplayArmed = false;
	float RoundLengthSeconds = 10.0f;
};

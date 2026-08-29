// Copyright CraftBench. All Rights Reserved.
//
// The round marker for task t2-race-clock-cpp: the one place an outside
// observer reads the score, the clock and the round's word. All three ship at their
// starting values and nothing keeps them current yet.

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
};

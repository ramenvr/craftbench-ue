// Copyright CraftBench. All Rights Reserved.
//
// ASprintCharacter — playable character for task tp2-sprint-stamina, with the
// sprint/stamina system implemented (reference solution).

#pragma once

#include "CoreMinimal.h"
#include "ThirdPersonCharacter.h"
#include "SprintCharacter.generated.h"

UCLASS()
class THIRDPERSON_API ASprintCharacter : public AThirdPersonCharacter
{
	GENERATED_BODY()

public:
	ASprintCharacter();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	/** Requests a sprint; only takes effect if stamina is at least the floor. */
	UFUNCTION(BlueprintCallable, Category="Sprint")
	void DoSprintStart();

	/** Ends the sprint and restores the normal maximum ground speed. */
	UFUNCTION(BlueprintCallable, Category="Sprint")
	void DoSprintEnd();

private:
	static constexpr float MaxStamina = 100.f;
	static constexpr float DrainPerSecond = 25.f;
	static constexpr float RegenPerSecond = 20.f;
	static constexpr float MinSprintStamina = 30.f;
	static constexpr float SprintMultiplier = 1.7f;

	float Stamina = MaxStamina;
	bool bSprinting = false;
	float BaseMaxWalkSpeed = 0.f;
};

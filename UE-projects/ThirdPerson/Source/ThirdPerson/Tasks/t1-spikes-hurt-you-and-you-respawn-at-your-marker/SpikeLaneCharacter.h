// Copyright CraftBench. All Rights Reserved.
//
// A character standing in the lane for task
// t1-spikes-hurt-you-and-you-respawn-at-your-marker. It arrives visible, animated,
// drivable, with a floating number above it, and nothing else: nothing takes health
// away, nothing notices death, and nothing writes to the number.

#pragma once

#include "CoreMinimal.h"
#include "ThirdPersonCharacter.h"
#include "SpikeLaneCharacter.generated.h"

class UTextRenderComponent;

UCLASS()
class THIRDPERSON_API ASpikeLaneCharacter : public AThirdPersonCharacter
{
	GENERATED_BODY()

public:
	ASpikeLaneCharacter();

	/** Floats above the capsule. It is supposed to show Health; nothing writes it. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Lane")
	UTextRenderComponent* HealthReadout = nullptr;

	/** Current health, out of MaxHealth. Both start at 100. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Lane")
	float Health = 100.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Lane")
	float MaxHealth = 100.0f;
};

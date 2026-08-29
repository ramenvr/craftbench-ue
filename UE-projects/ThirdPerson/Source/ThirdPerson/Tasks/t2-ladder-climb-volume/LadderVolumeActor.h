// Copyright CraftBench. All Rights Reserved.
//
// ALadderVolumeActor — pre-existing ladder frame for task
// t2-ladder-climb-volume. Placed in the task level; the constructor builds the
// tall query-only volume that marks the ladder's reach and stamps the
// "LadderVolume" identity tag. The required behavior is specified in the task
// prompt and is the agent's to implement. Agents may subclass or rename
// freely.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "LadderVolumeActor.generated.h"

class UBoxComponent;

UCLASS()
class THIRDPERSON_API ALadderVolumeActor : public AActor
{
	GENERATED_BODY()

public:
	ALadderVolumeActor();

protected:
	/** Tall ladder-shaped overlap volume (root). Query-only; overlaps all channels. */
	UPROPERTY(VisibleAnywhere, Category = "Ladder")
	TObjectPtr<UBoxComponent> LadderVolume;
};

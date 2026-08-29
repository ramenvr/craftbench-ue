// Copyright CraftBench. All Rights Reserved.
//
// The course for task t1-spikes-hurt-you-and-you-respawn-at-your-marker: the one
// place that says which pad is current. The value ships at 0, meaning "no pad yet --
// the painted start mark". Nothing keeps it truthful yet; that is part of the work.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "SpikeLaneCourse.generated.h"

UCLASS()
class THIRDPERSON_API ASpikeLaneCourse : public AActor
{
	GENERATED_BODY()

public:
	ASpikeLaneCourse();

	/** 1 or 2 once a pad has been walked onto; 0 means the start mark. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Course")
	int32 CurrentPadOrder = 0;
};

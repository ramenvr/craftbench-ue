// Copyright CraftBench. All Rights Reserved.
//
// ALadderVolumeActor implementation for task t2-ladder-climb-volume. The
// constructor builds the overlap volume and stamps the "LadderVolume" identity
// tag. No behavior is provided; the required behavior is specified in the task
// prompt and is the agent's to implement.

#include "LadderVolumeActor.h"

#include "Components/BoxComponent.h"

ALadderVolumeActor::ALadderVolumeActor()
{
	PrimaryActorTick.bCanEverTick = false;

	LadderVolume = CreateDefaultSubobject<UBoxComponent>(TEXT("LadderVolume"));
	SetRootComponent(LadderVolume);
	LadderVolume->SetBoxExtent(FVector(60.0f, 60.0f, 600.0f));
	LadderVolume->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	LadderVolume->SetCollisionResponseToAllChannels(ECR_Overlap);
	LadderVolume->SetGenerateOverlapEvents(true);

	Tags.Add(FName("LadderVolume"));
}

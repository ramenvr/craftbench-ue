// Reference solution for task t0-sanity-log-on-beginplay.
// Single-emission UE_LOG to LogTemp at Display verbosity inside BeginPlay.
// Super::BeginPlay() is invoked so the engine-side lifecycle proceeds normally.

#include "SanityActor.h"

ASanityActor::ASanityActor()
{
	PrimaryActorTick.bCanEverTick = false;
	Tags.Add(FName("SanityRoot"));
}

void ASanityActor::BeginPlay()
{
	Super::BeginPlay();
	UE_LOG(LogTemp, Display, TEXT("CRAFTBENCH_SANITY_OK"));
}

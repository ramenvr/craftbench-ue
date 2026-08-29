// Discrimination variant "logs-then-destroys-self": violates the prompt's
// "the actor should otherwise remain in the world" requirement. The literal is
// emitted correctly (once, LogTemp, Display, in BeginPlay) but the actor then
// Destroy()s itself. Expected verdict: FAIL at the tag-resolve gate -- BeginPlay
// fires on placed actors BEFORE AFunctionalTest::PrepareTest in PIE, so by the
// time PrepareTest runs GetAllActorsWithTag("SanityRoot") finds 0 actors.

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
	Destroy();
}

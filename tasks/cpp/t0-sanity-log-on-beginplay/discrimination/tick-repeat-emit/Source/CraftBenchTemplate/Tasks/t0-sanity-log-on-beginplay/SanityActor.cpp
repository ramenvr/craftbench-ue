// Discrimination variant "tick-repeat-emit": anti-gaming note #4 (multiple
// emits). The emission moves from BeginPlay into Tick, so it fires every frame
// -- a submission shape that would satisfy any ">= 1" check. Expected verdict:
// FAIL at the emission-count gate: the fixture asserts == 1, and by the 0.1s
// checkpoint (~6 fixed-step frames at 60 FPS) the listener has observed >= 2.

#include "SanityActor.h"

ASanityActor::ASanityActor()
{
	PrimaryActorTick.bCanEverTick = true;
	Tags.Add(FName("SanityRoot"));
}

void ASanityActor::BeginPlay()
{
	Super::BeginPlay();
}

void ASanityActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	UE_LOG(LogTemp, Display, TEXT("CRAFTBENCH_SANITY_OK"));
}

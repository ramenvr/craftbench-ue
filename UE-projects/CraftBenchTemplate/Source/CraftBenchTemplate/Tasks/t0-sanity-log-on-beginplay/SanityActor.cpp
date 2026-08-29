// Copyright CraftBench. All Rights Reserved.
//
// ASanityActor implementation for task t0-sanity-log-on-beginplay. The
// constructor disables tick and stamps the "SanityRoot" identity tag. No
// BeginPlay override is provided here; the required behavior is specified in
// the task prompt and is the agent's to implement.

#include "SanityActor.h"

ASanityActor::ASanityActor()
{
	PrimaryActorTick.bCanEverTick = false;
	Tags.Add(FName("SanityRoot"));
}

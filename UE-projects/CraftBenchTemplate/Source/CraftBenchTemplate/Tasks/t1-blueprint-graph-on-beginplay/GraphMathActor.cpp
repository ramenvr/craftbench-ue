// Copyright CraftBench. All Rights Reserved.
//
// AGraphMathActor implementation for task t1-blueprint-graph-on-beginplay.
// The constructor disables tick and stamps the "GraphMathRoot" identity tag.
// No lifecycle overrides are provided here; the required behavior is
// specified in the task prompt and is the agent's to implement.

#include "GraphMathActor.h"

AGraphMathActor::AGraphMathActor()
{
	PrimaryActorTick.bCanEverTick = false;
	Tags.Add(FName("GraphMathRoot"));
}

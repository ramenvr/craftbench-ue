// Copyright CraftBench. All Rights Reserved.
//
// ATagGateActor implementation for task t1-gameplay-tag-gate. The constructor
// disables tick and stamps the "TagGateRoot" identity tag; the native state
// marker is defined here so it is registered whenever this module is loaded.
// The accessor bodies are intentionally empty: the marker storage and the
// behavior it controls are specified in the task prompt and are the agent's to
// implement.

#include "TagGateActor.h"

UE_DEFINE_GAMEPLAY_TAG_COMMENT(TAG_CraftBench_TagGate_Active, "CraftBench.TagGate.Active",
	"State marker that gates the repeating announcement for task t1-gameplay-tag-gate.");

ATagGateActor::ATagGateActor()
{
	PrimaryActorTick.bCanEverTick = false;
	Tags.Add(FName("TagGateRoot"));
}

void ATagGateActor::AddGateTag(FGameplayTag Tag)
{
	// The agent implements this: record the marker in the actor's marker set.
}

void ATagGateActor::RemoveGateTag(FGameplayTag Tag)
{
	// The agent implements this: remove the marker from the actor's marker set.
}

// Copyright CraftBench. All Rights Reserved.
//
// ADelayedMoverActor implementation for task t1-blueprint-event-to-action. The
// constructor disables tick, creates a movable scene root (so instances have a
// transform that can be moved at runtime), and stamps the "DelayedMoverRoot"
// identity tag. No lifecycle overrides are provided here; the required behavior
// is specified in the task prompt.

#include "DelayedMoverActor.h"

#include "Components/SceneComponent.h"

ADelayedMoverActor::ADelayedMoverActor()
{
	PrimaryActorTick.bCanEverTick = false;
	RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	RootComponent->SetMobility(EComponentMobility::Movable);
	Tags.Add(FName("DelayedMoverRoot"));
}

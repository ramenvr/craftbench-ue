// Copyright CraftBench. All Rights Reserved.
//
// ATeleportDestinationMarker implementation for task
// t1-overlap-teleport-portal. The constructor stamps the "TeleportDestination"
// identity tag. The marker is deliberately inert.

#include "TeleportDestinationMarker.h"

#include "Components/SceneComponent.h"

ATeleportDestinationMarker::ATeleportDestinationMarker()
{
	PrimaryActorTick.bCanEverTick = false;

	SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("Root")));

	Tags.Add(FName("TeleportDestination"));
}

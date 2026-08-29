// Copyright CraftBench. All Rights Reserved.
//
// ATeleportPortalActor implementation for task t1-overlap-teleport-portal.
// The constructor builds the overlap volume and stamps the "TeleportPortal"
// identity tag. No behavior is provided; the required behavior is specified
// in the task prompt and is the agent's to implement.

#include "TeleportPortalActor.h"

#include "Components/BoxComponent.h"

ATeleportPortalActor::ATeleportPortalActor()
{
	PrimaryActorTick.bCanEverTick = false;

	PortalVolume = CreateDefaultSubobject<UBoxComponent>(TEXT("PortalVolume"));
	SetRootComponent(PortalVolume);
	PortalVolume->SetBoxExtent(FVector(60.0f, 120.0f, 120.0f));
	PortalVolume->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	PortalVolume->SetCollisionResponseToAllChannels(ECR_Overlap);
	PortalVolume->SetGenerateOverlapEvents(true);

	Tags.Add(FName("TeleportPortal"));
}

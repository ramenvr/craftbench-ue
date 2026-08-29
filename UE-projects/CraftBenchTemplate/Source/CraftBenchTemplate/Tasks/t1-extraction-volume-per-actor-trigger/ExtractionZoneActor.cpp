// Copyright CraftBench. All Rights Reserved.
//
// AExtractionZoneActor implementation for task
// t1-extraction-volume-per-actor-trigger. The constructor creates a query-only
// UBoxComponent detection volume as the root (overlap events generated,
// response to all channels) so actors entering the zone can be detected, and
// stamps the "ExtractionZone" identity tag. No overlap handling, bookkeeping,
// or logging is provided; the required behavior is specified in the task
// prompt and is the agent's to implement.

#include "ExtractionZoneActor.h"

#include "Components/BoxComponent.h"

AExtractionZoneActor::AExtractionZoneActor()
{
	PrimaryActorTick.bCanEverTick = false;

	ZoneVolume = CreateDefaultSubobject<UBoxComponent>(TEXT("ZoneVolume"));
	SetRootComponent(ZoneVolume);
	ZoneVolume->InitBoxExtent(FVector(200.0f, 200.0f, 100.0f));
	ZoneVolume->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	ZoneVolume->SetCollisionObjectType(ECC_WorldStatic);
	ZoneVolume->SetCollisionResponseToAllChannels(ECR_Overlap);
	ZoneVolume->SetGenerateOverlapEvents(true);

	Tags.Add(FName("ExtractionZone"));
}

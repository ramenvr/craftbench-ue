// Copyright CraftBench. All Rights Reserved.
//
// Discrimination variant "global-once": extraction latches globally after the
// first entrant, so the second distinct individual never triggers it.

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

void AExtractionZoneActor::NotifyActorBeginOverlap(AActor* OtherActor)
{
	Super::NotifyActorBeginOverlap(OtherActor);

	if (OtherActor == nullptr || OtherActor == this)
	{
		return;
	}
	if (bExtractionTriggered)
	{
		return;
	}
	bExtractionTriggered = true;
	UE_LOG(LogTemp, Display, TEXT("CRAFTBENCH_EXTRACTION_OK"));
}

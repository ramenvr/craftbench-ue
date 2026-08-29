// Copyright CraftBench. All Rights Reserved.
//
// Reference solution for task t1-extraction-volume-per-actor-trigger.

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
	// Extraction fires exactly once per distinct individual: a returning
	// individual is already recorded and adds nothing.
	if (ExtractedIndividuals.Contains(OtherActor))
	{
		return;
	}
	ExtractedIndividuals.Add(OtherActor);
	UE_LOG(LogTemp, Display, TEXT("CRAFTBENCH_EXTRACTION_OK"));
}

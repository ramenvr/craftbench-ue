// Copyright CraftBench. All Rights Reserved.
//
// Discrimination variant "log-every-entry": reacts to entries but never
// deduplicates, so a returning individual re-triggers extraction.

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
	// Gamed: no per-individual record — every entry logs again.
	UE_LOG(LogTemp, Display, TEXT("CRAFTBENCH_EXTRACTION_OK"));
}

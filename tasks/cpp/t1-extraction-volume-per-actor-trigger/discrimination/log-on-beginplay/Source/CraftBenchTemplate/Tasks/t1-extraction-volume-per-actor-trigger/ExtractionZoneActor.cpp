// Copyright CraftBench. All Rights Reserved.
//
// Discrimination variant "log-on-beginplay": the gamed shape that emits the
// marker at startup without any entry ever happening.

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

void AExtractionZoneActor::BeginPlay()
{
	Super::BeginPlay();
	// Gamed: fires at startup, no entry required.
	UE_LOG(LogTemp, Display, TEXT("CRAFTBENCH_EXTRACTION_OK"));
}

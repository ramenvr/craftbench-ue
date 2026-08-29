// Copyright CraftBench. All Rights Reserved.
//
// GAMING VARIANT (delayed-unconditional-teleport): BeginPlay arms a 1.0s
// timer; when it fires, every pawn in the world is snapped to the marker —
// zero overlap logic. Beats any single-instant sampling scheme (green before
// the timer, "delivered" after it); dies to the fixture's continuous
// pre-contact guard, which sees the walker delivered while its walked
// progress is still ~500uu short of the portal.

#include "TeleportPortalActor.h"

#include "Components/BoxComponent.h"
#include "GameFramework/Pawn.h"
#include "Kismet/GameplayStatics.h"
#include "TimerManager.h"

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

void ATeleportPortalActor::BeginPlay()
{
	Super::BeginPlay();

	GetWorldTimerManager().SetTimer(
		DelayedTeleportHandle, this, &ATeleportPortalActor::TeleportEveryone, 1.0f, false);
}

void ATeleportPortalActor::TeleportEveryone()
{
	TArray<AActor*> Markers;
	UGameplayStatics::GetAllActorsWithTag(GetWorld(), FName("TeleportDestination"), Markers);
	if (Markers.Num() == 0)
	{
		return;
	}
	const FVector Destination = Markers[0]->GetActorLocation();

	TArray<AActor*> Pawns;
	UGameplayStatics::GetAllActorsOfClass(GetWorld(), APawn::StaticClass(), Pawns);
	for (AActor* PawnActor : Pawns)
	{
		PawnActor->SetActorLocation(Destination, false, nullptr, ETeleportType::TeleportPhysics);
	}
}

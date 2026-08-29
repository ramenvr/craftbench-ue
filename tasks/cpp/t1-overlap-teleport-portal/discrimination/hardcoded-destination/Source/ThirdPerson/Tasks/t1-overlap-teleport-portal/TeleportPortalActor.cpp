// Copyright CraftBench. All Rights Reserved.
//
// GAMING VARIANT (hardcoded-destination): teleports the entrant to the
// coordinates the marker was authored at in the map — (3200, 900, 90) — read
// once from the editor and pasted into code. Works in a casual manual test;
// dies the moment the marker is somewhere else, which is exactly what the
// fixture arranges before play.

#include "TeleportPortalActor.h"

#include "Components/BoxComponent.h"
#include "GameFramework/Pawn.h"

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

void ATeleportPortalActor::NotifyActorBeginOverlap(AActor* OtherActor)
{
	Super::NotifyActorBeginOverlap(OtherActor);

	APawn* Pawn = Cast<APawn>(OtherActor);
	if (Pawn == nullptr)
	{
		return;
	}

	// The marker's authored placement, memorized instead of resolved.
	const FVector KnownSpot(3200.0, 900.0, 90.0);
	Pawn->SetActorLocation(KnownSpot, false, nullptr, ETeleportType::TeleportPhysics);
}

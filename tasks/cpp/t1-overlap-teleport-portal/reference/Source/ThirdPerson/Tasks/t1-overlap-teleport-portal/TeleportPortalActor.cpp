// Copyright CraftBench. All Rights Reserved.
//
// ATeleportPortalActor reference implementation for task
// t1-overlap-teleport-portal. Teleports each character that ENTERS the volume
// (begin-overlap edge — no tick logic) to the destination marker's CURRENT
// location, resolved by tag at the moment of the teleport so a moved marker
// is honored.

#include "TeleportPortalActor.h"

#include "Components/BoxComponent.h"
#include "GameFramework/Pawn.h"
#include "Kismet/GameplayStatics.h"

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

	// The marker's position is read NOW — never cached from level start.
	TArray<AActor*> Markers;
	UGameplayStatics::GetAllActorsWithTag(GetWorld(), FName("TeleportDestination"), Markers);
	if (Markers.Num() == 0)
	{
		return;
	}

	Pawn->SetActorLocation(Markers[0]->GetActorLocation(), false, nullptr, ETeleportType::TeleportPhysics);
}

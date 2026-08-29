// Copyright CraftBench. All Rights Reserved.
//
// GAMING VARIANT (resnap-after-exit): the begin-overlap edge is honored (so
// the pre-contact and delivery checks pass), but the entrant is remembered
// and re-pinned to the marker every tick afterwards — teleport-as-handcuffs.
// The fixture's checkpoint 2 samples 1.5s after it walked the character away
// and finds it dragged back.

#include "TeleportPortalActor.h"

#include "Components/BoxComponent.h"
#include "GameFramework/Pawn.h"
#include "Kismet/GameplayStatics.h"

ATeleportPortalActor::ATeleportPortalActor()
{
	PrimaryActorTick.bCanEverTick = true;

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

	if (Cast<APawn>(OtherActor) != nullptr)
	{
		CaughtPawn = OtherActor;
	}
}

void ATeleportPortalActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (!CaughtPawn.IsValid())
	{
		return;
	}
	TArray<AActor*> Markers;
	UGameplayStatics::GetAllActorsWithTag(GetWorld(), FName("TeleportDestination"), Markers);
	if (Markers.Num() == 0)
	{
		return;
	}
	CaughtPawn->SetActorLocation(Markers[0]->GetActorLocation(), false, nullptr, ETeleportType::TeleportPhysics);
}

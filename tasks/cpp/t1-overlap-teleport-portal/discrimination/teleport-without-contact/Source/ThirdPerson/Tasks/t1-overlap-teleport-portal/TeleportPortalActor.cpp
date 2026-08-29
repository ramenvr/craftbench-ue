// Copyright CraftBench. All Rights Reserved.
//
// GAMING VARIANT (teleport-without-contact): every tick, every pawn in the
// world is snapped to the marker — "the player ends up at the destination"
// satisfied with zero overlap logic. The fixture's checkpoint 0 samples the
// walker BEFORE it reaches the portal and finds it already delivered.

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

void ATeleportPortalActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

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

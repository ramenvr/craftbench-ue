// Copyright CraftBench. All Rights Reserved.

#include "RelicPickup.h"

#include "Components/SphereComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "UObject/ConstructorHelpers.h"

ARelicPickup::ARelicPickup()
{
	PrimaryActorTick.bCanEverTick = false;

	RelicVolume = CreateDefaultSubobject<USphereComponent>(TEXT("RelicVolume"));
	SetRootComponent(RelicVolume);
	RelicVolume->SetSphereRadius(120.0f);
	RelicVolume->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	RelicVolume->SetCollisionResponseToAllChannels(ECR_Overlap);
	RelicVolume->SetGenerateOverlapEvents(true);

	RelicMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("RelicMesh"));
	RelicMesh->SetupAttachment(RelicVolume);
	static ConstructorHelpers::FObjectFinder<UStaticMesh> ConeMesh(
		TEXT("/Engine/BasicShapes/Cone"));
	if (ConeMesh.Succeeded())
	{
		RelicMesh->SetStaticMesh(ConeMesh.Object);
	}
	// Floated off the floor and slimmed, so a relic reads as a prize rather than
	// scenery, and so its absence is obvious in a still.
	RelicMesh->SetRelativeLocation(FVector(0.0f, 0.0f, 40.0f));
	RelicMesh->SetRelativeScale3D(FVector(0.9f, 0.9f, 1.6f));
	RelicMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	Tags.Add(FName("ArenaRelic"));
}

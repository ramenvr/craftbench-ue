// Copyright CraftBench. All Rights Reserved.

#include "RelicPickup.h"

#include "Components/SphereComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "ExitGate.h"
#include "GameFramework/Character.h"
#include "Kismet/GameplayStatics.h"
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
	RelicMesh->SetRelativeLocation(FVector(0.0f, 0.0f, 40.0f));
	RelicMesh->SetRelativeScale3D(FVector(0.9f, 0.9f, 1.6f));
	RelicMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	Tags.Add(FName("ArenaRelic"));
}

void ARelicPickup::BeginPlay()
{
	Super::BeginPlay();

	if (RelicVolume != nullptr)
	{
		RelicVolume->OnComponentBeginOverlap.AddDynamic(
			this, &ARelicPickup::OnRelicBegin);
	}
}

void ARelicPickup::OnRelicBegin(UPrimitiveComponent*, AActor* OtherActor,
	UPrimitiveComponent*, int32, bool, const FHitResult&)
{
	// Once only, and only for the character. bGathered guards against a second
	// overlap edge from the same walk-through.
	if (bGathered || Cast<ACharacter>(OtherActor) == nullptr)
	{
		return;
	}
	bGathered = true;

	// Tell the exit BEFORE leaving the arena, so the count is banked even though
	// this actor is about to stop existing.
	TArray<AActor*> Exits;
	UGameplayStatics::GetAllActorsWithTag(GetWorld(), FName(TEXT("ArenaExit")), Exits);
	for (AActor* E : Exits)
	{
		if (AExitGate* const Gate = Cast<AExitGate>(E))
		{
			Gate->NotifyRelicGathered();
		}
	}

	// Gone for good: walking back over the spot can do nothing, because there is
	// nothing there to overlap.
	Destroy();
}

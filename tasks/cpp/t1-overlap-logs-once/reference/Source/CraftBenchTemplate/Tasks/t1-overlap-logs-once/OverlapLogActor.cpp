// Copyright CraftBench. All Rights Reserved.
//
// Reference solution for task t1-overlap-logs-once.

#include "OverlapLogActor.h"

#include "Components/SphereComponent.h"

AOverlapLogActor::AOverlapLogActor()
{
	PrimaryActorTick.bCanEverTick = false;

	CollisionSphere = CreateDefaultSubobject<USphereComponent>(TEXT("CollisionSphere"));
	SetRootComponent(CollisionSphere);
	CollisionSphere->InitSphereRadius(64.0f);
	CollisionSphere->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	CollisionSphere->SetCollisionObjectType(ECC_WorldDynamic);
	CollisionSphere->SetCollisionResponseToAllChannels(ECR_Overlap);
	CollisionSphere->SetGenerateOverlapEvents(true);

	Tags.Add(FName("OverlapLogRoot"));
}

void AOverlapLogActor::BeginPlay()
{
	Super::BeginPlay();
	if (CollisionSphere != nullptr)
	{
		CollisionSphere->OnComponentBeginOverlap.AddDynamic(this, &AOverlapLogActor::HandleOverlap);
	}
}

void AOverlapLogActor::HandleOverlap(UPrimitiveComponent* /*OverlappedComponent*/, AActor* OtherActor,
	UPrimitiveComponent* /*OtherComp*/, int32 /*OtherBodyIndex*/, bool /*bFromSweep*/,
	const FHitResult& /*SweepResult*/)
{
	// Ignore a self-overlap; log the marker once for a genuine other-actor overlap.
	if (OtherActor == nullptr || OtherActor == this)
	{
		return;
	}
	UE_LOG(LogTemp, Display, TEXT("CRAFTBENCH_OVERLAP_OK"));
}

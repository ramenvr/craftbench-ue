// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT logs-per-tick (anti-gaming note #3): the overlap
// handler only arms a flag; Tick emits the marker every frame while armed.

#include "OverlapLogActor.h"

#include "Components/SphereComponent.h"

AOverlapLogActor::AOverlapLogActor()
{
	// VARIANT DELTA: tick enabled so the per-frame log path runs.
	PrimaryActorTick.bCanEverTick = true;

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

void AOverlapLogActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	// VARIANT DELTA: re-emit the marker every frame after the first overlap.
	if (bMarkerActive)
	{
		UE_LOG(LogTemp, Display, TEXT("CRAFTBENCH_OVERLAP_OK"));
	}
}

void AOverlapLogActor::HandleOverlap(UPrimitiveComponent* /*OverlappedComponent*/, AActor* OtherActor,
	UPrimitiveComponent* /*OtherComp*/, int32 /*OtherBodyIndex*/, bool /*bFromSweep*/,
	const FHitResult& /*SweepResult*/)
{
	// Ignore a self-overlap; arm the per-tick marker path for a genuine overlap.
	if (OtherActor == nullptr || OtherActor == this)
	{
		return;
	}
	// VARIANT DELTA: arm the flag instead of logging once here.
	bMarkerActive = true;
}

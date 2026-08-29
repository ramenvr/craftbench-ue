// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT wrong-verbosity (anti-gaming note #2): binds the
// overlap correctly but emits the marker at Verbose -- quieter than the
// Display floor the listener enforces -- so the emission is never counted.
// Must FAIL at checkpoint 1 (exactly-once), observed 0.

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
	// VARIANT DELTA: Verbose instead of Display -- below the listener's floor.
	UE_LOG(LogTemp, Verbose, TEXT("CRAFTBENCH_OVERLAP_OK"));
}

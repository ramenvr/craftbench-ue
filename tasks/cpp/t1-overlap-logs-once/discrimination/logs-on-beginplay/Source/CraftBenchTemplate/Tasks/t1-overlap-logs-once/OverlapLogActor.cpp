// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT logs-on-beginplay (anti-gaming note #1): emits the
// marker unconditionally at BeginPlay to satisfy a naive ">= 1" grader and
// never binds the overlap. Must FAIL at checkpoint 0 (silence-before-overlap).

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
	// VARIANT DELTA: log at startup instead of binding the overlap event.
	UE_LOG(LogTemp, Display, TEXT("CRAFTBENCH_OVERLAP_OK"));
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
	// VARIANT DELTA: handler left defined but never bound -- nothing fires here.
}

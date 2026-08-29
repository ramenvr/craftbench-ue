// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT (teleport-once-then-static) for task
// t1-movement-component-drives-actor. ONE DELTA vs the reference: no movement
// component; a 0.35 s one-shot timer snaps the actor +400 uu on X once, then
// it sits still. The 0.35 s deferral lands the hop AFTER PrepareTest captures
// StartLocation (checkpoints run on world game-time; BeginPlay fires before
// PrepareTest, so an immediate teleport would fold into StartLocation) and
// BEFORE checkpoint 0 at t=0.5 s, so MovingFromStart passes and the fixture
// reaches the ContinuesMoving gate with a ~0 final-interval step.

#include "DriftActor.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "TimerManager.h"
#include "UObject/ConstructorHelpers.h"

ADriftActor::ADriftActor()
{
	PrimaryActorTick.bCanEverTick = false;

	Body = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Body"));
	SetRootComponent(Body);
	Body->SetMobility(EComponentMobility::Movable);
	Body->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(TEXT("/Engine/BasicShapes/Cube.Cube"));
	if (CubeMesh.Succeeded())
	{
		Body->SetStaticMesh(CubeMesh.Object);
	}

	Tags.Add(FName("DriftRoot"));
}

void ADriftActor::BeginPlay()
{
	Super::BeginPlay();

	// One-shot: hop the actor forward once shortly after play begins, then stop.
	GetWorldTimerManager().SetTimer(TeleportTimerHandle, this, &ADriftActor::TeleportOnce, 0.35f, false);
}

void ADriftActor::TeleportOnce()
{
	SetActorLocation(GetActorLocation() + FVector(400.0f, 0.0f, 0.0f));
}

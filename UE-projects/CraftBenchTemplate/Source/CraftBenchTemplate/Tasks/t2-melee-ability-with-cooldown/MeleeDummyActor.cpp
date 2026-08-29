// Copyright CraftBench. All Rights Reserved.

#include "MeleeDummyActor.h"

#include "Components/StaticMeshComponent.h"
#include "UObject/ConstructorHelpers.h"

AMeleeDummyActor::AMeleeDummyActor()
{
	PrimaryActorTick.bCanEverTick = false;

	Body = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Body"));
	SetRootComponent(Body);
	// Movable so gameplay/tooling may reposition placed instances at runtime
	// (a Static-mobility root refuses SetActorLocation in play).
	Body->SetMobility(EComponentMobility::Movable);
	// The dummy is a passive target: no collision so it never blocks or bumps
	// whatever moves around it.
	Body->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CylinderMesh(
		TEXT("/Engine/BasicShapes/Cylinder"));
	if (CylinderMesh.Succeeded())
	{
		Body->SetStaticMesh(CylinderMesh.Object);
	}

	Tags.Add(FName(TEXT("MeleeDummy")));
}

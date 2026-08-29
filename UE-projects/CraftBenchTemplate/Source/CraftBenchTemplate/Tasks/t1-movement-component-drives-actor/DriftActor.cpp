// Copyright CraftBench. All Rights Reserved.
//
// ADriftActor implementation for task t1-movement-component-drives-actor. The
// constructor builds a cube mesh root and stamps the "DriftRoot" identity tag.
// No self-motion is provided; driving the actor at a steady velocity is the
// agent's task.

#include "DriftActor.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
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

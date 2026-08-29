// Copyright CraftBench. All Rights Reserved.
//
// Discrimination variant "component-without-mesh": the component is created as
// a default subobject but no mesh asset is assigned. Expected verdict: FAIL
// via the fixture's no-mesh message ("with no mesh assigned").

#include "CubeMeshActor.h"

#include "Components/StaticMeshComponent.h"

ACubeMeshActor::ACubeMeshActor()
{
	PrimaryActorTick.bCanEverTick = false;

	Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	SetRootComponent(Root);

	CubeMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("CubeMesh"));
	CubeMesh->SetupAttachment(Root);
	CubeMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	// No SetStaticMesh call anywhere — the delivery stops half way.

	Tags.Add(FName("CubeMeshDisplay"));
}

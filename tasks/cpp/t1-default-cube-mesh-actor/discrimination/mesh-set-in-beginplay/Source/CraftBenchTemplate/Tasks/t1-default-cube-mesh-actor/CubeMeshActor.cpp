// Copyright CraftBench. All Rights Reserved.
//
// Discrimination variant "mesh-set-in-beginplay": runtime assignment instead
// of a class default. Expected verdict: FAIL via the fixture's runtime-
// assignment message ("assigned at runtime rather than carried as a class
// default") — the instance shows a cube at checkpoint time, but neither the
// pre-BeginPlay window nor the class default object carries it.

#include "CubeMeshActor.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"

ACubeMeshActor::ACubeMeshActor()
{
	PrimaryActorTick.bCanEverTick = false;

	Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	SetRootComponent(Root);

	CubeMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("CubeMesh"));
	CubeMesh->SetupAttachment(Root);
	CubeMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	// Movable, or the BeginPlay-time SetStaticMesh below can be silently
	// swallowed by the engine's static-mobility guard once the world has begun
	// play — which would make this variant die at the WRONG named assert
	// (component-without-mesh's) instead of the runtime-assignment one it
	// models. The t2-homing-projectile MissileTargetActor uses the same
	// mobility for post-BeginPlay mutation.
	CubeMesh->SetMobility(EComponentMobility::Movable);
	// NOTE: no mesh assigned here — the class default carries nothing.

	Tags.Add(FName("CubeMeshDisplay"));
}

void ACubeMeshActor::BeginPlay()
{
	Super::BeginPlay();

	// The gamed move: acquire the cube at runtime, after the default state has
	// already been observed.
	if (CubeMesh != nullptr && CubeMesh->GetStaticMesh() == nullptr)
	{
		if (UStaticMesh* Cube = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube")))
		{
			CubeMesh->SetStaticMesh(Cube);
		}
	}
}

// Copyright CraftBench. All Rights Reserved.

#include "SpikeSlabActor.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

ASpikeSlabActor::ASpikeSlabActor()
{
	PrimaryActorTick.bCanEverTick = false;

	SlabMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("SlabMesh"));
	SetRootComponent(SlabMesh);
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube"));
	if (CubeMesh.Succeeded())
	{
		SlabMesh->SetStaticMesh(CubeMesh.Object);
	}
	// 240 x 240 x 200 cm from the 100 cm engine cube.
	SlabMesh->SetRelativeScale3D(FVector(2.4f, 2.4f, 2.0f));
	SlabMesh->SetMobility(EComponentMobility::Movable);
	// Query-only, overlap on every channel: it is noticed, never blocking. A slab
	// that could push would move a character the level never intended to move.
	SlabMesh->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	SlabMesh->SetCollisionResponseToAllChannels(ECR_Overlap);
	SlabMesh->SetGenerateOverlapEvents(true);

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Hazard(
		TEXT("/Game/Variant_Combat/Materials/M_Lava"));
	if (Hazard.Succeeded())
	{
		SlabMesh->SetMaterial(0, Hazard.Object);
	}

	Tags.Add(FName("SlidingSpikes"));
}

// Copyright CraftBench. All Rights Reserved.

#include "MudPatchActor.h"

#include "Components/BoxComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

AMudPatchActor::AMudPatchActor()
{
	PrimaryActorTick.bCanEverTick = false;

	PatchMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("PatchMesh"));
	SetRootComponent(PatchMesh);
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube"));
	if (CubeMesh.Succeeded())
	{
		PatchMesh->SetStaticMesh(CubeMesh.Object);
	}
	// 400 cm of lane, dark and flat: something you walk over, not something you climb.
	PatchMesh->SetRelativeScale3D(FVector(4.0f, 4.0f, 0.04f));
	PatchMesh->SetRelativeLocation(FVector(0.0f, 0.0f, 2.0f));
	PatchMesh->SetMobility(EComponentMobility::Static);
	PatchMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Dark(
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"));
	if (Dark.Succeeded())
	{
		PatchMesh->SetMaterial(0, Dark.Object);
	}

	PatchVolume = CreateDefaultSubobject<UBoxComponent>(TEXT("PatchVolume"));
	PatchVolume->SetupAttachment(PatchMesh);
	// Authored in world centimetres, undone from the mesh's own scale.
	PatchVolume->SetBoxExtent(FVector(200.0f, 200.0f, 120.0f));
	PatchVolume->SetRelativeScale3D(FVector(1.0f / 4.0f, 1.0f / 4.0f, 1.0f / 0.04f));
	PatchVolume->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	PatchVolume->SetCollisionResponseToAllChannels(ECR_Overlap);
	PatchVolume->SetGenerateOverlapEvents(true);

	Tags.Add(FName("MudPatch"));
}

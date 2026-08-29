// Copyright CraftBench. All Rights Reserved.

#include "CrumbleGroundActor.h"

#include "Components/BoxComponent.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	/** Half the patch, in world centimetres: 800 along the floor, 3000 across it. */
	const FVector kPatchHalfExtentUu(400.0f, 1500.0f, 120.0f);
}

ACrumbleGroundActor::ACrumbleGroundActor()
{
	PrimaryActorTick.bCanEverTick = false;

	// A plain, UNSCALED root. Everything hung off it is then the size it says it is:
	// a shape parented to a flattened slab would inherit that flattening.
	USceneComponent* const Pivot = CreateDefaultSubobject<USceneComponent>(TEXT("Pivot"));
	SetRootComponent(Pivot);

	PatchMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("PatchMesh"));
	PatchMesh->SetupAttachment(Pivot);
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube"));
	if (CubeMesh.Succeeded())
	{
		PatchMesh->SetStaticMesh(CubeMesh.Object);
	}
	// 800 x 3000 cm of broken ground, 8 cm proud of the floor.
	PatchMesh->SetRelativeScale3D(FVector(8.0f, 30.0f, 0.08f));
	PatchMesh->SetRelativeLocation(FVector(0.0f, 0.0f, 4.0f));
	PatchMesh->SetMobility(EComponentMobility::Static);
	PatchMesh->SetCollisionProfileName(TEXT("NoCollision"));
	PatchMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> PatchLook(
		TEXT("/Game/Variant_Combat/Materials/M_Lava"));
	if (PatchLook.Succeeded())
	{
		PatchMesh->SetMaterial(0, PatchLook.Object);
	}

	PatchVolume = CreateDefaultSubobject<UBoxComponent>(TEXT("PatchVolume"));
	PatchVolume->SetupAttachment(Pivot);
	PatchVolume->SetBoxExtent(kPatchHalfExtentUu);
	PatchVolume->SetRelativeLocation(FVector(0.0f, 0.0f, 60.0f));
	// Noticed, never blocking: ground that could push would move a runner the level
	// never intended to move.
	PatchVolume->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	PatchVolume->SetCollisionResponseToAllChannels(ECR_Overlap);
	PatchVolume->SetGenerateOverlapEvents(true);

	Tags.Add(FName("CrumbleGround"));
}

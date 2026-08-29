// Copyright CraftBench. All Rights Reserved.

#include "LanePadActor.h"

#include "Components/BoxComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

ALanePadActor::ALanePadActor()
{
	PrimaryActorTick.bCanEverTick = false;

	PadMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("PadMesh"));
	SetRootComponent(PadMesh);
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube"));
	if (CubeMesh.Succeeded())
	{
		PadMesh->SetStaticMesh(CubeMesh.Object);
	}
	// 200 x 200 x 8 cm, sitting on the floor: a pad you walk over, not a step.
	PadMesh->SetRelativeScale3D(FVector(2.0f, 2.0f, 0.08f));
	PadMesh->SetRelativeLocation(FVector(0.0f, 0.0f, 4.0f));
	PadMesh->SetMobility(EComponentMobility::Static);
	PadMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	PadVolume = CreateDefaultSubobject<UBoxComponent>(TEXT("PadVolume"));
	PadVolume->SetupAttachment(PadMesh);
	// The box is authored in world centimetres, so it is undone from the mesh's own
	// scale: 100 x 100 x 110 half-extents against a (2.0, 2.0, 0.08) parent.
	PadVolume->SetBoxExtent(FVector(100.0f, 100.0f, 110.0f));
	PadVolume->SetRelativeScale3D(FVector(1.0f / 2.0f, 1.0f / 2.0f, 1.0f / 0.08f));
	PadVolume->SetRelativeLocation(FVector(0.0f, 0.0f, 0.0f));
	PadVolume->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	PadVolume->SetCollisionResponseToAllChannels(ECR_Overlap);
	PadVolume->SetGenerateOverlapEvents(true);

	// The two supplied looks. Both are substrate content, so there is nothing to
	// author and nothing to import.
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Dark(
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Bright(
		TEXT("/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT"));
	DarkLook = Dark.Succeeded() ? Dark.Object : nullptr;
	BrightLook = Bright.Succeeded() ? Bright.Object : nullptr;
	if (DarkLook != nullptr)
	{
		PadMesh->SetMaterial(0, DarkLook);
	}

	Tags.Add(FName("LanePad"));
}

void ALanePadActor::SetMarkedCurrent(bool bInMarked)
{
	bMarkedCurrent = bInMarked;
	UMaterialInterface* const Look = bInMarked ? BrightLook : DarkLook;
	if (PadMesh != nullptr && Look != nullptr)
	{
		PadMesh->SetMaterial(0, Look);
	}
}

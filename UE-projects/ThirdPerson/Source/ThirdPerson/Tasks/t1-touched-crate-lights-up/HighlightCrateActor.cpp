// Copyright CraftBench. All Rights Reserved.

#include "HighlightCrateActor.h"

#include "Components/PointLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	constexpr float kLitIntensity = 7000.0f;
	const FLinearColor kLampColour(1.0f, 0.82f, 0.25f);
	const TCHAR* const kLitMaterial =
		TEXT("/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT");
	const TCHAR* const kPlainMaterial =
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark");
}

AHighlightCrateActor::AHighlightCrateActor()
{
	// Nothing to tick: nothing here decides anything.
	PrimaryActorTick.bCanEverTick = false;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube"));

	Body = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Body"));
	SetRootComponent(Body);
	if (CubeMesh.Succeeded())
	{
		Body->SetStaticMesh(CubeMesh.Object);
	}
	// A 160 cm crate. The actor stands with the mesh's CENTRE at its location, so the
	// yard places it at half its height and it sits on the floor.
	Body->SetRelativeScale3D(FVector(1.6f, 1.6f, 1.6f));
	Body->SetMobility(EComponentMobility::Movable);
	Body->SetCollisionProfileName(TEXT("BlockAll"));

	Lamp = CreateDefaultSubobject<UPointLightComponent>(TEXT("Lamp"));
	Lamp->SetupAttachment(Body);
	// Divided back out of the body's 1.6 scale, so the lamp sits just above the crate.
	Lamp->SetRelativeLocation(FVector(0.0f, 0.0f, 120.0f / 1.6f));
	Lamp->SetLightColor(kLampColour);
	Lamp->SetIntensity(0.0f);
	Lamp->SetAttenuationRadius(800.0f);
	Lamp->SetMobility(EComponentMobility::Movable);

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Lit(kLitMaterial);
	if (Lit.Succeeded())
	{
		LitLook = Lit.Object;
	}
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Plain(kPlainMaterial);
	if (Plain.Succeeded())
	{
		PlainLook = Plain.Object;
		Body->SetMaterial(0, Plain.Object);
	}

	Tags.Add(FName("HighlightCrate"));
}

void AHighlightCrateActor::BeginPlay()
{
	Super::BeginPlay();

	// Plain from the first frame, whatever the editor left behind.
	SetHighlighted(false);
}

void AHighlightCrateActor::SetHighlighted(bool bNewHighlighted)
{
	bHighlighted = bNewHighlighted;
	if (Lamp != nullptr)
	{
		Lamp->SetIntensity(bNewHighlighted ? kLitIntensity : 0.0f);
	}
	UMaterialInterface* const Look = bNewHighlighted ? LitLook : PlainLook;
	if (Body != nullptr && Look != nullptr)
	{
		Body->SetMaterial(0, Look);
	}
}

// Copyright CraftBench. All Rights Reserved.

#include "HighlightCrateActor.h"

#include "Components/PointLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/Pawn.h"
#include "Kismet/GameplayStatics.h"
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
	// Every frame: somebody can walk in or out of reach at any moment, and the yard
	// allows half a second to catch up.
	PrimaryActorTick.bCanEverTick = true;

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

void AHighlightCrateActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	// The character the player controls. Resolved every frame rather than cached at
	// BeginPlay: it is spawned and possessed by the game mode, and a cached pointer
	// would be null on any frame before that has happened.
	const APawn* const Watched = UGameplayStatics::GetPlayerPawn(this, 0);
	if (Watched == nullptr)
	{
		SetHighlighted(false);
		return;
	}

	// THIS crate's own reach, read off this crate. Nothing here knows what the other
	// crate is set to, or where either of them stands -- which is why the yard giving
	// them different reaches and then swapping their places costs this nothing.
	// Flat distance: the crate notices somebody standing near it, not above it.
	const double Distance =
		FVector::Dist2D(GetActorLocation(), Watched->GetActorLocation());
	SetHighlighted(Distance <= NoticeRadiusUu);
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

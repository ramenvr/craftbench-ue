// Copyright CraftBench. All Rights Reserved.

#include "StealthMastActor.h"

#include "Components/PointLightComponent.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	constexpr float kMastLampIntensity = 11000.0f;
}

AStealthMastActor::AStealthMastActor()
{
	// The mast is ticked. Nothing here does anything with those ticks.
	PrimaryActorTick.bCanEverTick = true;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CylMesh(
		TEXT("/Engine/BasicShapes/Cylinder"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> SphereMesh(
		TEXT("/Engine/BasicShapes/Sphere"));

	// An unscaled anchor at floor level is the root, and everything hangs off it at
	// plain centimetres above the floor.
	Anchor = CreateDefaultSubobject<USceneComponent>(TEXT("Anchor"));
	SetRootComponent(Anchor);

	Column = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Column"));
	Column->SetupAttachment(Anchor);
	if (CylMesh.Succeeded())
	{
		Column->SetStaticMesh(CylMesh.Object);
	}
	// A 50 cm mast, 600 cm tall, standing on the floor.
	Column->SetRelativeLocation(FVector(0.0f, 0.0f, 300.0f));
	Column->SetRelativeScale3D(FVector(0.5f, 0.5f, 6.0f));
	// The PROFILE as well as the enum: on an earlier task set_collision_enabled alone
	// did not survive into the saved level, and a mast that quietly stops a line is
	// indistinguishable from a bug in the submission.
	Column->SetCollisionProfileName(TEXT("NoCollision"));
	Column->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> ColumnLook(
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"));
	if (ColumnLook.Succeeded())
	{
		Column->SetMaterial(0, ColumnLook.Object);
	}

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Lit(
		TEXT("/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT"));
	if (Lit.Succeeded())
	{
		LitLook = Lit.Object;
	}
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Dark(
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02"));
	if (Dark.Succeeded())
	{
		DarkLook = Dark.Object;
	}

	// Every lamp hangs off the ANCHOR, never off the column: the column is scaled 6x
	// vertically and a child inherits its parent's scale, so 300 cm up a 6x column is
	// 1,800 cm up. Off the anchor these heights are plain centimetres above the floor.
	auto MakeShade = [this](const TCHAR* Name, float FloorZ)
	{
		UStaticMeshComponent* const Shade =
			CreateDefaultSubobject<UStaticMeshComponent>(Name);
		Shade->SetupAttachment(Anchor);
		if (SphereMesh.Succeeded())
		{
			Shade->SetStaticMesh(SphereMesh.Object);
		}
		Shade->SetRelativeLocation(FVector(0.0f, 0.0f, FloorZ));
		// 80 cm across: 0.8 of the engine sphere, with nothing to undo.
		Shade->SetRelativeScale3D(FVector(0.8f, 0.8f, 0.8f));
		Shade->SetCollisionProfileName(TEXT("NoCollision"));
		Shade->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		if (DarkLook != nullptr)
		{
			Shade->SetMaterial(0, DarkLook);
		}
		return Shade;
	};

	auto MakeLight = [this](const TCHAR* Name, float FloorZ, const FLinearColor& Colour)
	{
		UPointLightComponent* const Light =
			CreateDefaultSubobject<UPointLightComponent>(Name);
		Light->SetupAttachment(Anchor);
		Light->SetRelativeLocation(FVector(0.0f, 0.0f, FloorZ));
		Light->SetLightColor(Colour);
		Light->SetIntensity(0.0f);
		Light->SetAttenuationRadius(2600.0f);
		Light->SetMobility(EComponentMobility::Movable);
		return Light;
	};

	// Top to bottom: running, away, caught. Heights are centimetres above the floor.
	RunningShade = MakeShade(TEXT("RunningShade"), 520.0f);
	AwayShade = MakeShade(TEXT("AwayShade"), 400.0f);
	CaughtShade = MakeShade(TEXT("CaughtShade"), 280.0f);

	RunningLight = MakeLight(TEXT("RunningLight"), 520.0f, FLinearColor(1.0f, 0.86f, 0.42f));
	AwayLight = MakeLight(TEXT("AwayLight"), 400.0f, FLinearColor(0.25f, 1.0f, 0.36f));
	CaughtLight = MakeLight(TEXT("CaughtLight"), 280.0f, FLinearColor(1.0f, 0.18f, 0.14f));

	Tags.Add(FName(TEXT("StealthMast")));
}

void AStealthMastActor::BeginPlay()
{
	Super::BeginPlay();

	// Dark from the first frame, whatever the editor left behind. Nothing here decides
	// when any of the three should burn.
	SetRunningLit(false);
	SetAwayLit(false);
	SetCaughtLit(false);
}

void AStealthMastActor::Throw(UPointLightComponent* Light, UStaticMeshComponent* Shade,
							  bool bNewLit)
{
	if (Light != nullptr)
	{
		Light->SetIntensity(bNewLit ? kMastLampIntensity : 0.0f);
	}
	UMaterialInterface* const Look = bNewLit ? LitLook : DarkLook;
	if (Shade != nullptr && Look != nullptr)
	{
		Shade->SetMaterial(0, Look);
	}
}

void AStealthMastActor::SetRunningLit(bool bNewLit)
{
	bRunningLit = bNewLit;
	Throw(RunningLight, RunningShade, bNewLit);
}

void AStealthMastActor::SetAwayLit(bool bNewLit)
{
	bAwayLit = bNewLit;
	Throw(AwayLight, AwayShade, bNewLit);
}

void AStealthMastActor::SetCaughtLit(bool bNewLit)
{
	bCaughtLit = bNewLit;
	Throw(CaughtLight, CaughtShade, bNewLit);
}

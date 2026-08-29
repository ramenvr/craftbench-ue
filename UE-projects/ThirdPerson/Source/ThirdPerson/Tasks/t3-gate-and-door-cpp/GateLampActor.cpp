// Copyright CraftBench. All Rights Reserved.

#include "GateLampActor.h"

#include "Components/PointLightComponent.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	const FVector kBracketScale(0.18f, 0.18f, 0.5f);
	const FVector kBulbDarkScale(0.34f, 0.34f, 0.34f);
	const FVector kBulbLitScale(0.54f, 0.54f, 0.54f);
	constexpr double kBulbZ = 68.0;

	const TCHAR* const kDarkMaterial =
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark");
	const TCHAR* const kLitMaterial =
		TEXT("/Game/LevelPrototyping/Materials/MI_DefaultColorway");
}

AGateLampActor::AGateLampActor()
{
	// Nothing to do every frame: the lamp only ever changes when its switch is
	// thrown.
	PrimaryActorTick.bCanEverTick = false;

	Mount = CreateDefaultSubobject<USceneComponent>(TEXT("Mount"));
	SetRootComponent(Mount);
	// The bulb swells and the light turns on, so nothing here may be pinned static.
	Mount->SetMobility(EComponentMobility::Movable);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> SphereMesh(
		TEXT("/Engine/BasicShapes/Sphere"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> DarkFinder(kDarkMaterial);
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> LitFinder(kLitMaterial);
	DarkLook = DarkFinder.Succeeded() ? DarkFinder.Object : nullptr;
	LitLook = LitFinder.Succeeded() ? LitFinder.Object : nullptr;

	Bracket = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Bracket"));
	Bracket->SetupAttachment(Mount);
	if (CubeMesh.Succeeded())
	{
		Bracket->SetStaticMesh(CubeMesh.Object);
	}
	if (DarkLook != nullptr)
	{
		Bracket->SetMaterial(0, DarkLook);
	}
	Bracket->SetRelativeScale3D(kBracketScale);
	Bracket->SetRelativeLocation(FVector(0.0, 0.0, 25.0));
	Bracket->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Bracket->SetCollisionProfileName(TEXT("NoCollision"));

	Bulb = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Bulb"));
	Bulb->SetupAttachment(Mount);
	if (SphereMesh.Succeeded())
	{
		Bulb->SetStaticMesh(SphereMesh.Object);
	}
	if (DarkLook != nullptr)
	{
		Bulb->SetMaterial(0, DarkLook);
	}
	Bulb->SetRelativeScale3D(kBulbDarkScale);
	Bulb->SetRelativeLocation(FVector(0.0, 0.0, kBulbZ));
	Bulb->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Bulb->SetCollisionProfileName(TEXT("NoCollision"));

	Light = CreateDefaultSubobject<UPointLightComponent>(TEXT("Light"));
	Light->SetupAttachment(Mount);
	Light->SetRelativeLocation(FVector(0.0, 0.0, kBulbZ));
	Light->SetAttenuationRadius(900.0f);
	Light->SetLightColor(FLinearColor(1.0f, 0.86f, 0.52f));
	Light->SetIntensity(0.0f);
	Light->SetCastShadows(false);

	SlotPlate = CreateDefaultSubobject<UTextRenderComponent>(TEXT("SlotPlate"));
	SlotPlate->SetupAttachment(Mount);
	SlotPlate->SetRelativeLocation(FVector(0.0, 0.0, 130.0));
	SlotPlate->SetHorizontalAlignment(EHTA_Center);
	SlotPlate->SetWorldSize(34.0f);
	SlotPlate->SetTextRenderColor(FColor(210, 210, 210));
	SlotPlate->SetText(FText::FromString(TEXT("--")));
	SlotPlate->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	SlotPlate->SetUsingAbsoluteRotation(true);

	Tags.Add(FName(TEXT("GateLamp")));
}

void AGateLampActor::BeginPlay()
{
	Super::BeginPlay();

	// Dark to begin with, whatever the level was saved holding.
	SetLit(false);

	if (SlotPlate != nullptr)
	{
		SlotPlate->SetWorldRotation(FRotator(0.0, 90.0, 0.0));
		SlotPlate->SetText(FText::FromString(NameSlot == 0
			? TEXT("1st")
			: TEXT("2nd")));
	}
}

void AGateLampActor::SetLit(bool bLit)
{
	if (Light != nullptr)
	{
		// Visible either way: dark is an intensity of nothing, never a hidden light,
		// so what is burning can always be read straight off the lamp.
		Light->SetVisibility(true);
		Light->SetIntensity(bLit ? LitIntensity : 0.0f);
	}

	if (Bulb != nullptr)
	{
		Bulb->SetRelativeScale3D(bLit ? kBulbLitScale : kBulbDarkScale);
		// A material SWAP rather than a parameter write: not every prototype material
		// here carries a colour parameter, and a write that silently does nothing
		// would leave a burning lamp looking dark. Both were resolved when the lamp
		// was built -- asset lookup outside a constructor is not allowed.
		UMaterialInterface* const Wanted = bLit ? LitLook : DarkLook;
		if (Wanted != nullptr)
		{
			Bulb->SetMaterial(0, Wanted);
		}
	}
}

bool AGateLampActor::IsLit() const
{
	return Light != nullptr && Light->IsVisible() && Light->Intensity > 0.0f;
}

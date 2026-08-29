// Copyright CraftBench. All Rights Reserved.

#include "SightGuardActor.h"

#include "Components/PointLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	constexpr float kLitIntensity = 5000.0f;
	const FLinearColor kLitColour(1.0f, 0.08f, 0.05f);
	const FLinearColor kDarkColour(0.06f, 0.06f, 0.07f);
}

ASightGuardActor::ASightGuardActor()
{
	PrimaryActorTick.bCanEverTick = false;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CylMesh(
		TEXT("/Engine/BasicShapes/Cylinder"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> SphereMesh(
		TEXT("/Engine/BasicShapes/Sphere"));

	Body = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Body"));
	SetRootComponent(Body);
	if (CylMesh.Succeeded())
	{
		Body->SetStaticMesh(CylMesh.Object);
	}
	// ~60 cm across, 180 cm tall, sitting on the floor.
	Body->SetRelativeScale3D(FVector(0.6f, 0.6f, 1.8f));
	Body->SetRelativeLocation(FVector(0.0f, 0.0f, 90.0f));
	Body->SetMobility(EComponentMobility::Movable);
	Body->SetCollisionProfileName(TEXT("BlockAll"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> BodyLook(
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"));
	if (BodyLook.Succeeded())
	{
		Body->SetMaterial(0, BodyLook.Object);
	}

	// In FRONT of the body on purpose: a line drawn from here toward anything never
	// starts inside the guard's own collision.
	Eye = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Eye"));
	Eye->SetupAttachment(Body);
	if (SphereMesh.Succeeded())
	{
		Eye->SetStaticMesh(SphereMesh.Object);
	}
	// The body is scaled (0.6, 0.6, 1.8), so the offsets below are undone from it to
	// land the eye at world (40, 0, 170) relative to the guard.
	Eye->SetRelativeScale3D(FVector(0.25f / 0.6f, 0.25f / 0.6f, 0.25f / 1.8f));
	Eye->SetRelativeLocation(FVector(40.0f / 0.6f, 0.0f, (170.0f - 90.0f) / 1.8f));
	Eye->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	Bulb = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Bulb"));
	Bulb->SetupAttachment(Body);
	if (SphereMesh.Succeeded())
	{
		Bulb->SetStaticMesh(SphereMesh.Object);
	}
	Bulb->SetRelativeScale3D(FVector(0.45f / 0.6f, 0.45f / 0.6f, 0.45f / 1.8f));
	Bulb->SetRelativeLocation(FVector(0.0f, 0.0f, (200.0f - 90.0f) / 1.8f));
	Bulb->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	AlertLamp = CreateDefaultSubobject<UPointLightComponent>(TEXT("AlertLamp"));
	AlertLamp->SetupAttachment(Body);
	AlertLamp->SetRelativeLocation(FVector(0.0f, 0.0f, (200.0f - 90.0f) / 1.8f));
	AlertLamp->SetLightColor(kLitColour);
	AlertLamp->SetIntensity(0.0f);
	AlertLamp->SetAttenuationRadius(600.0f);
	AlertLamp->SetMobility(EComponentMobility::Movable);

	Tags.Add(FName("SightGuard"));
}

void ASightGuardActor::BeginPlay()
{
	Super::BeginPlay();

	if (Bulb != nullptr)
	{
		BulbMaterial = Bulb->CreateAndSetMaterialInstanceDynamic(0);
	}
	// Dark from the first frame, whatever the editor left behind.
	SetSpotted(false);
}

void ASightGuardActor::SetSpotted(bool bNewSpotted)
{
	bSpotted = bNewSpotted;
	if (AlertLamp != nullptr)
	{
		AlertLamp->SetIntensity(bNewSpotted ? kLitIntensity : 0.0f);
	}
	if (BulbMaterial != nullptr)
	{
		BulbMaterial->SetVectorParameterValue(
			TEXT("Color"), bNewSpotted ? kLitColour : kDarkColour);
	}
}

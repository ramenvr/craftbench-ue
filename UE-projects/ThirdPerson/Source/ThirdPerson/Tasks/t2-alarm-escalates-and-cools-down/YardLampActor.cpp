// Copyright CraftBench. All Rights Reserved.

#include "YardLampActor.h"

#include "Components/PointLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	constexpr float kLitIntensity = 9000.0f;
	const FLinearColor kLampColour(1.0f, 0.72f, 0.20f);
}

AYardLampActor::AYardLampActor()
{
	// Nothing to tick: nothing here decides anything.
	PrimaryActorTick.bCanEverTick = false;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CylMesh(
		TEXT("/Engine/BasicShapes/Cylinder"));

	Body = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Body"));
	SetRootComponent(Body);
	if (CylMesh.Succeeded())
	{
		Body->SetStaticMesh(CylMesh.Object);
	}
	// A 60 cm mast, 400 cm tall, centred on the actor's location.
	Body->SetRelativeScale3D(FVector(0.6f, 0.6f, 4.0f));
	// Non-colliding on every channel, and the PROFILE as well as the enum. A prop that
	// quietly blocks a sightline would make a submission that asks "is anything in the
	// way?" disagree with a yard that never asks.
	Body->SetCollisionProfileName(TEXT("NoCollision"));
	Body->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	Glow = CreateDefaultSubobject<UPointLightComponent>(TEXT("Glow"));
	Glow->SetupAttachment(Body);
	// Divided back out of the body's 4.0 vertical scale, so the light sits at the top
	// of the mast rather than inside it.
	Glow->SetRelativeLocation(FVector(0.0f, 0.0f, 220.0f / 4.0f));
	Glow->SetLightColor(kLampColour);
	Glow->SetIntensity(0.0f);
	Glow->SetAttenuationRadius(2500.0f);
	Glow->SetMobility(EComponentMobility::Movable);

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Lit(
		TEXT("/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT"));
	if (Lit.Succeeded())
	{
		LitLook = Lit.Object;
	}
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Dark(
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark"));
	if (Dark.Succeeded())
	{
		DarkLook = Dark.Object;
		Body->SetMaterial(0, Dark.Object);
	}

	Tags.Add(FName("YardLamp"));
}

void AYardLampActor::BeginPlay()
{
	Super::BeginPlay();

	// Dark from the first frame, whatever the editor left behind. Note that the yard
	// starting calm does NOT mean every floodlight starts dark: one of them burns from
	// the calmest setting, so somebody has to light it.
	SetLit(false);
}

void AYardLampActor::SetLit(bool bNewLit)
{
	bLit = bNewLit;
	if (Glow != nullptr)
	{
		Glow->SetIntensity(bNewLit ? kLitIntensity : 0.0f);
	}
	UMaterialInterface* const Look = bNewLit ? LitLook : DarkLook;
	if (Body != nullptr && Look != nullptr)
	{
		Body->SetMaterial(0, Look);
	}
}

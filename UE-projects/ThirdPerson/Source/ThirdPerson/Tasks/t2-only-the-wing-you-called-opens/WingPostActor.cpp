// Copyright CraftBench. All Rights Reserved.

#include "WingPostActor.h"

#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

AWingPostActor::AWingPostActor()
{
	// Nothing to tick: a post decides nothing.
	PrimaryActorTick.bCanEverTick = false;

	Pivot = CreateDefaultSubobject<USceneComponent>(TEXT("Pivot"));
	SetRootComponent(Pivot);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube.Cube"));

	// A 40 x 40 x 420 cm post standing on the actor's own location.
	Post = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Post"));
	Post->SetupAttachment(Pivot);
	Post->SetRelativeLocation(FVector(0.0f, 0.0f, 210.0f));
	Post->SetRelativeScale3D(FVector(0.4f, 0.4f, 4.2f));
	// Non-colliding on every channel, and the PROFILE as well as the enum: a prop that
	// quietly blocks the floor would change where a person can walk, and the whole
	// task is about walking onto things.
	Post->SetCollisionProfileName(TEXT("NoCollision"));
	Post->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	if (CubeMesh.Succeeded())
	{
		Post->SetStaticMesh(CubeMesh.Object);
	}

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Look(
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray"));
	if (Look.Succeeded())
	{
		Post->SetMaterial(0, Look.Object);
	}

	Nameplate = CreateDefaultSubobject<UTextRenderComponent>(TEXT("Nameplate"));
	Nameplate->SetupAttachment(Pivot);
	Nameplate->SetRelativeLocation(FVector(0.0f, 0.0f, 470.0f));
	Nameplate->SetRelativeRotation(FRotator(0.0f, 180.0f, 0.0f));
	Nameplate->SetHorizontalAlignment(EHTA_Center);
	Nameplate->SetWorldSize(130.0f);
	Nameplate->SetTextRenderColor(FColor(255, 255, 255));
	Nameplate->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Nameplate->SetText(FText::GetEmpty());

	Tags.Add(FName(TEXT("WingPost")));
}

void AWingPostActor::BeginPlay()
{
	Super::BeginPlay();

	// Presentation only: paint this post's own wing name where a person can read it.
	if (Nameplate != nullptr)
	{
		Nameplate->SetText(WingName.IsNone()
			? FText::GetEmpty()
			: FText::FromString(WingName.ToString().ToUpper()));
	}
}

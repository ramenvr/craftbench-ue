// Copyright CraftBench. All Rights Reserved.

#include "WingFittingActor.h"

#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

AWingFittingActor::AWingFittingActor()
{
	// Nothing to tick: a fitting decides nothing.
	PrimaryActorTick.bCanEverTick = false;

	Pivot = CreateDefaultSubobject<USceneComponent>(TEXT("Pivot"));
	SetRootComponent(Pivot);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CylMesh(
		TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));

	// A 90 cm column, 320 cm tall, standing on the actor's own location.
	Column = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Column"));
	Column->SetupAttachment(Pivot);
	Column->SetRelativeLocation(FVector(0.0f, 0.0f, 160.0f));
	Column->SetRelativeScale3D(FVector(0.9f, 0.9f, 3.2f));
	Column->SetCollisionProfileName(TEXT("BlockAll"));
	Column->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
	if (CylMesh.Succeeded())
	{
		Column->SetStaticMesh(CylMesh.Object);
	}

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Look(
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02"));
	if (Look.Succeeded())
	{
		Column->SetMaterial(0, Look.Object);
	}

	Nameplate = CreateDefaultSubobject<UTextRenderComponent>(TEXT("Nameplate"));
	Nameplate->SetupAttachment(Pivot);
	Nameplate->SetRelativeLocation(FVector(0.0f, 0.0f, 360.0f));
	Nameplate->SetRelativeRotation(FRotator(0.0f, 180.0f, 0.0f));
	Nameplate->SetHorizontalAlignment(EHTA_Center);
	Nameplate->SetWorldSize(60.0f);
	Nameplate->SetTextRenderColor(FColor(235, 235, 235));
	Nameplate->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Nameplate->SetText(FText::GetEmpty());

	Tags.Add(FName(TEXT("WingFitting")));
}

void AWingFittingActor::BeginPlay()
{
	Super::BeginPlay();

	// Presentation only: put this fitting's own wing name on its plate so a person
	// standing in the host can read the hall at a glance.
	if (Nameplate != nullptr)
	{
		Nameplate->SetText(WingLabel.IsNone()
			? FText::GetEmpty()
			: FText::FromString(WingLabel.ToString().ToUpper()));
	}
}

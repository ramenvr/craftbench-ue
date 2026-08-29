// Copyright CraftBench. All Rights Reserved.

#include "CrewHandActor.h"

#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

ACrewHandActor::ACrewHandActor()
{
	// A hand decides nothing and never moves.
	PrimaryActorTick.bCanEverTick = false;

	// A bare scene root, deliberately left at unit scale: a scaled root would
	// multiply every child's offset as well as its size.
	USceneComponent* const Pivot = CreateDefaultSubobject<USceneComponent>(TEXT("Pivot"));
	SetRootComponent(Pivot);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CylMesh(
		TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> SphereMesh(
		TEXT("/Engine/BasicShapes/Sphere.Sphere"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Look(
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02"));

	// A 60 cm trunk 140 cm tall, standing on the spot's own floor level.
	Body = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Body"));
	Body->SetupAttachment(Pivot);
	Body->SetRelativeLocation(FVector(0.0f, 0.0f, 70.0f));
	Body->SetRelativeScale3D(FVector(0.6f, 0.6f, 1.4f));
	if (CylMesh.Succeeded())
	{
		Body->SetStaticMesh(CylMesh.Object);
	}
	if (Look.Succeeded())
	{
		Body->SetMaterial(0, Look.Object);
	}
	// Nothing on a hand blocks anything, PROFILE as well as enum: a hand that could
	// be shoved would be a hand that moved, and the deck promises they do not.
	Body->SetCollisionProfileName(TEXT("NoCollision"));
	Body->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	Head = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Head"));
	Head->SetupAttachment(Pivot);
	Head->SetRelativeLocation(FVector(0.0f, 0.0f, 165.0f));
	Head->SetRelativeScale3D(FVector(0.5f, 0.5f, 0.5f));
	if (SphereMesh.Succeeded())
	{
		Head->SetStaticMesh(SphereMesh.Object);
	}
	if (Look.Succeeded())
	{
		Head->SetMaterial(0, Look.Object);
	}
	Head->SetCollisionProfileName(TEXT("NoCollision"));
	Head->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	Badge = CreateDefaultSubobject<UTextRenderComponent>(TEXT("Badge"));
	Badge->SetupAttachment(Pivot);
	Badge->SetRelativeLocation(FVector(0.0f, 0.0f, 230.0f));
	Badge->SetHorizontalAlignment(EHTA_Center);
	Badge->SetWorldSize(48.0f);
	Badge->SetTextRenderColor(FColor(255, 232, 150));
	// The badge reads square-on to whoever the hand is facing, so putting a hand down
	// facing the way its standing spot faces makes the number readable from the deck.
	Badge->SetText(FText::GetEmpty());

	Tags.Add(FName(TEXT("CrewHand")));
}

void ACrewHandActor::SetBadgeCode(int32 NewCode)
{
	if (Badge != nullptr)
	{
		Badge->SetText(FText::FromString(FString::FromInt(NewCode)));
	}
}

int32 ACrewHandActor::GetBadgeCode() const
{
	if (Badge == nullptr)
	{
		return 0;
	}
	// Read back off the thing on screen, never off a private copy, so the number a
	// hand is WEARING and the number it thinks it has can never disagree.
	return FCString::Atoi(*Badge->Text.ToString());
}

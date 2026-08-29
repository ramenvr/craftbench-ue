// Copyright CraftBench. All Rights Reserved.

#include "StealthGateActor.h"

#include "Components/BoxComponent.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/Pawn.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

AStealthGateActor::AStealthGateActor()
{
	// Nothing to tick: the gate is asked, it does not announce.
	PrimaryActorTick.bCanEverTick = false;

	// An unscaled anchor at floor level is the root, and everything hangs off it at
	// plain centimetres above the floor. The volume is NOT the root: a root component's
	// relative location IS the actor's location, so seating the gateway above the floor
	// by moving it would move the whole actor.
	Anchor = CreateDefaultSubobject<USceneComponent>(TEXT("Anchor"));
	SetRootComponent(Anchor);

	GateVolume = CreateDefaultSubobject<UBoxComponent>(TEXT("GateVolume"));
	GateVolume->SetupAttachment(Anchor);
	// A 400 x 240 cm doorway, 300 cm tall, rising from the floor.
	GateVolume->SetBoxExtent(FVector(200.0f, 120.0f, 150.0f));
	GateVolume->SetRelativeLocation(FVector(0.0f, 0.0f, 150.0f));
	GateVolume->SetCollisionProfileName(TEXT("OverlapAllDynamic"));
	GateVolume->SetGenerateOverlapEvents(true);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Look(
		TEXT("/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT"));

	auto MakeFrame = [this](const TCHAR* Name, const FVector& Offset,
							const FVector& Scale)
	{
		UStaticMeshComponent* const Part =
			CreateDefaultSubobject<UStaticMeshComponent>(Name);
		// Hung off the ANCHOR, not the volume: heights are then plain centimetres above
		// the floor and nothing has to be undone if the gateway's box ever changes.
		Part->SetupAttachment(Anchor);
		if (CubeMesh.Succeeded())
		{
			Part->SetStaticMesh(CubeMesh.Object);
		}
		Part->SetRelativeLocation(Offset);
		Part->SetRelativeScale3D(Scale);
		// The PROFILE as well as the enum -- the gate must never stop a line.
		Part->SetCollisionProfileName(TEXT("NoCollision"));
		Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		if (Look.Succeeded())
		{
			Part->SetMaterial(0, Look.Object);
		}
		return Part;
	};

	// The root is unscaled, so these offsets and scales are plain centimetres above the
	// floor: two 340 cm uprights standing on it, and a lintel across the top of them.
	PostLeft = MakeFrame(TEXT("PostLeft"), FVector(-220.0f, 0.0f, 170.0f),
						 FVector(0.4f, 0.4f, 3.4f));
	PostRight = MakeFrame(TEXT("PostRight"), FVector(220.0f, 0.0f, 170.0f),
						  FVector(0.4f, 0.4f, 3.4f));
	Lintel = MakeFrame(TEXT("Lintel"), FVector(0.0f, 0.0f, 360.0f),
					   FVector(4.8f, 0.4f, 0.4f));

	Tags.Add(FName(TEXT("StealthGate")));
}

bool AStealthGateActor::IsSomebodyStandingInIt() const
{
	if (GateVolume == nullptr)
	{
		return false;
	}
	TArray<AActor*> Standing;
	GateVolume->GetOverlappingActors(Standing, APawn::StaticClass());
	return Standing.Num() > 0;
}

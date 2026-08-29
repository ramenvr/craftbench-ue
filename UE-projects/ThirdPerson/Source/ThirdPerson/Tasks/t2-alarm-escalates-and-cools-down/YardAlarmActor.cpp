// Copyright CraftBench. All Rights Reserved.

#include "YardAlarmActor.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

AYardAlarmActor::AYardAlarmActor()
{
	// Nothing to tick: a board of dials decides nothing.
	PrimaryActorTick.bCanEverTick = false;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube"));

	Board = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Board"));
	SetRootComponent(Board);
	if (CubeMesh.Succeeded())
	{
		Board->SetStaticMesh(CubeMesh.Object);
	}
	// A 240 x 40 x 200 cm board standing on its edge, centred on the actor's location.
	Board->SetRelativeScale3D(FVector(2.4f, 0.4f, 2.0f));
	// Non-colliding on every channel, and the PROFILE as well as the enum -- see
	// AYardLampActor for why a prop that quietly blocks a sightline is a hazard here.
	Board->SetCollisionProfileName(TEXT("NoCollision"));
	Board->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Look(
		TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray_02"));
	if (Look.Succeeded())
	{
		Board->SetMaterial(0, Look.Object);
	}

	Tags.Add(FName("YardAlarm"));
}

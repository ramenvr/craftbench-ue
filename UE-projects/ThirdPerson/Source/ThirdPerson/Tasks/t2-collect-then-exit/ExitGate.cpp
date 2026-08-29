// Copyright CraftBench. All Rights Reserved.

#include "ExitGate.h"

#include "Components/BoxComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "UObject/ConstructorHelpers.h"

AExitGate::AExitGate()
{
	PrimaryActorTick.bCanEverTick = false;

	ExitMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("ExitMesh"));
	SetRootComponent(ExitMesh);
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube"));
	if (CubeMesh.Succeeded())
	{
		ExitMesh->SetStaticMesh(CubeMesh.Object);
	}
	// A wide slab standing across the lane: unmistakable in a still, and not solid,
	// so the character walks INTO the exit rather than being stopped at its face.
	ExitMesh->SetRelativeScale3D(FVector(0.5f, 5.0f, 3.0f));
	ExitMesh->SetRelativeLocation(FVector(0.0f, 0.0f, 150.0f));
	ExitMesh->SetMobility(EComponentMobility::Static);
	ExitMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	ExitVolume = CreateDefaultSubobject<UBoxComponent>(TEXT("ExitVolume"));
	ExitVolume->SetupAttachment(ExitMesh);
	ExitVolume->SetBoxExtent(FVector(240.0f, 50.0f, 50.0f));
	ExitVolume->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	ExitVolume->SetCollisionResponseToAllChannels(ECR_Overlap);
	ExitVolume->SetGenerateOverlapEvents(true);

	ExitLamp = CreateDefaultSubobject<UPointLightComponent>(TEXT("ExitLamp"));
	ExitLamp->SetupAttachment(ExitMesh);
	ExitLamp->SetRelativeLocation(FVector(0.0f, 0.0f, 40.0f));
	ExitLamp->SetIntensity(0.0f);
	ExitLamp->SetAttenuationRadius(1500.0f);
	ExitLamp->SetLightColor(FLinearColor(0.35f, 1.0f, 0.45f));
	ExitLamp->SetMobility(EComponentMobility::Movable);

	Tags.Add(FName("ArenaExit"));
}

// Copyright CraftBench. All Rights Reserved.

#include "RaceCoinBase.h"

#include "Components/SphereComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

ARaceCoinBase::ARaceCoinBase()
{
	PrimaryActorTick.bCanEverTick = false;

	CoinRegion = CreateDefaultSubobject<USphereComponent>(TEXT("CoinRegion"));
	SetRootComponent(CoinRegion);
	CoinRegion->SetSphereRadius(60.0f);
	CoinRegion->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	CoinRegion->SetCollisionResponseToAllChannels(ECR_Overlap);
	CoinRegion->SetGenerateOverlapEvents(true);

	CoinMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("CoinMesh"));
	CoinMesh->SetupAttachment(CoinRegion);
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CylMesh(
		TEXT("/Engine/BasicShapes/Cylinder"));
	if (CylMesh.Succeeded())
	{
		CoinMesh->SetStaticMesh(CylMesh.Object);
	}
	// A coin on edge: flat and wide, tipped upright so it reads as a coin rather
	// than a puck from the camera angles a reviewer will use.
	CoinMesh->SetRelativeScale3D(FVector(0.7f, 0.7f, 0.08f));
	CoinMesh->SetRelativeRotation(FRotator(90.0f, 0.0f, 0.0f));
	CoinMesh->SetRelativeLocation(FVector(0.0f, 0.0f, 10.0f));
	CoinMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Glow(
		TEXT("/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/MI_GlowNT"));
	if (Glow.Succeeded())
	{
		CoinMesh->SetMaterial(0, Glow.Object);
	}

	Tags.Add(FName("RaceCoin"));
}

// Copyright CraftBench. All Rights Reserved.

#include "RunResumeProtectedTypes.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "RunResumePersistenceComponent.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	UStaticMesh* LoadCube()
	{
		static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(
			TEXT("/Engine/BasicShapes/Cube.Cube"));
		return Cube.Object;
	}
}

ARunResumeCheckpoint::ARunResumeCheckpoint()
{
	PrimaryActorTick.bCanEverTick = false;
	MarkerMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("MarkerMesh"));
	SetRootComponent(MarkerMesh);
	MarkerMesh->SetStaticMesh(LoadCube());
	MarkerMesh->SetWorldScale3D(FVector(0.45, 0.45, 1.5));
}

ARunResumeReward::ARunResumeReward()
{
	PrimaryActorTick.bCanEverTick = false;
	RewardMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("RewardMesh"));
	SetRootComponent(RewardMesh);
	RewardMesh->SetStaticMesh(LoadCube());
	RewardMesh->SetWorldScale3D(FVector(0.35));
}

void ARunResumeReward::SetRetired(bool bInRetired)
{
	bRetired = bInRetired;
	SetActorHiddenInGame(bRetired);
	SetActorEnableCollision(!bRetired);
	RewardMesh->SetVisibility(!bRetired, true);
}

ARunResumeSubject::ARunResumeSubject()
{
	PrimaryActorTick.bCanEverTick = false;
	SubjectMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("SubjectMesh"));
	SetRootComponent(SubjectMesh);
	SubjectMesh->SetStaticMesh(LoadCube());
	SubjectMesh->SetWorldScale3D(FVector(0.55, 0.55, 1.0));
	Persistence = CreateDefaultSubobject<URunResumePersistenceComponent>(
		TEXT("RunResumePersistence"));
}

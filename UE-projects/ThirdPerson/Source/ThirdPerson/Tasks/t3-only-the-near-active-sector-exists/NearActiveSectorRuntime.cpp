// Copyright CraftBench. All Rights Reserved.

#include "Tasks/t3-only-the-near-active-sector-exists/NearActiveSectorRuntime.h"

#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/WorldPartitionStreamingSourceComponent.h"
#include "UObject/ConstructorHelpers.h"
#include "WorldPartition/DataLayer/DataLayerManager.h"

ANearActiveSectorRequest::ANearActiveSectorRequest()
{
	PrimaryActorTick.bCanEverTick = false;
	SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("Root")));
}

ANearActiveSectorStreamingSource::ANearActiveSectorStreamingSource()
{
	PrimaryActorTick.bCanEverTick = false;
	SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("Root")));
	StreamingSource = CreateDefaultSubobject<UWorldPartitionStreamingSourceComponent>(
		TEXT("SectorStreamingSource"));
	StreamingSource->TargetState = EStreamingSourceTargetState::Activated;
	StreamingSource->Priority = EStreamingSourcePriority::High;
	StreamingSource->EnableStreamingSource();
}

ANearActiveSectorMarker::ANearActiveSectorMarker()
{
	PrimaryActorTick.bCanEverTick = false;
	VisibleMarker = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("VisibleMarker"));
	SetRootComponent(VisibleMarker);
	VisibleMarker->SetMobility(EComponentMobility::Static);
	VisibleMarker->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(
		TEXT("/Engine/BasicShapes/Cube.Cube"));
	if (Cube.Succeeded())
	{
		VisibleMarker->SetStaticMesh(Cube.Object);
	}
}

void ANearActiveSectorMarker::BeginPlay()
{
	Super::BeginPlay();
	++BeginPlayEpoch;
}

void ANearActiveSectorMarker::EndPlay(
	const EEndPlayReason::Type EndPlayReason)
{
	++EndPlayEpoch;
	Super::EndPlay(EndPlayReason);
}

ANearActiveSectorControllerBase::ANearActiveSectorControllerBase()
{
	PrimaryActorTick.bCanEverTick = false;
	SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("Root")));
}

UDataLayerManager*
ANearActiveSectorControllerBase::GetSectorDataLayerManager() const
{
	return UDataLayerManager::GetDataLayerManager(this);
}

void ANearActiveSectorControllerBase::ApplySectorRequest_Implementation(
	ANearActiveSectorRequest* Request)
{
}

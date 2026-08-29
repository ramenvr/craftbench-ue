// Copyright CraftBench. All Rights Reserved.

#include "CheckpointDirectorActor.h"

#include "Components/SceneComponent.h"

ACheckpointDirectorActor::ACheckpointDirectorActor()
{
	// Nothing to tick: nothing here decides anything yet.
	PrimaryActorTick.bCanEverTick = false;

	Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	SetRootComponent(Root);

	// The yard finds this piece by its tag, not by its class name.
	Tags.Add(FName(TEXT("CheckpointDirector")));
}

void ACheckpointDirectorActor::BeginPlay()
{
	Super::BeginPlay();

	// Empty on purpose.
}

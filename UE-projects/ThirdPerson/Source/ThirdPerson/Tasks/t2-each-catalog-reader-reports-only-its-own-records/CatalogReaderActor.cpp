// Copyright CraftBench. All Rights Reserved.
//
// Empty scaffold implementation for task
// t2-each-catalog-reader-reports-only-its-own-records. The constructor owns
// identity and a transform root only. The behavior in the prompt is the
// agent's to implement.

#include "CatalogReaderActor.h"

#include "Components/SceneComponent.h"

ACatalogReaderActor::ACatalogReaderActor()
{
	PrimaryActorTick.bCanEverTick = false;
	Tags.Add(FName(TEXT("CatalogReader")));

	USceneComponent* SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("SceneRoot"));
	SetRootComponent(SceneRoot);
}

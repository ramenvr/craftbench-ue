// Copyright CraftBench. All Rights Reserved.
//
// AHarvestableActor implementation for task gp-harvestable-regrow. The
// constructor enables tick, creates a query-only USphereComponent overlap
// volume as the root (overlap events generated, response to all channels) so an
// actor overlapping it can be detected, and stamps the "HarvestableRoot"
// identity tag. No BeginPlay / overlap binding / state logic is provided; the
// required behavior is specified in the task prompt and is the agent's to
// implement.

#include "HarvestableActor.h"

#include "Components/SphereComponent.h"

AHarvestableActor::AHarvestableActor()
{
	PrimaryActorTick.bCanEverTick = true;

	// A real root component so the actor's world location is meaningful and so an
	// overlap volume exists for "walked into it" detection. The agent binds this
	// component's begin-overlap event; the constructor only configures collision.
	CollisionSphere = CreateDefaultSubobject<USphereComponent>(TEXT("CollisionSphere"));
	SetRootComponent(CollisionSphere);
	CollisionSphere->InitSphereRadius(64.0f);
	CollisionSphere->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	CollisionSphere->SetCollisionObjectType(ECC_WorldDynamic);
	CollisionSphere->SetCollisionResponseToAllChannels(ECR_Overlap);
	CollisionSphere->SetGenerateOverlapEvents(true);

	Tags.Add(FName("HarvestableRoot"));
}

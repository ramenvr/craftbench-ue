// Copyright CraftBench. All Rights Reserved.
//
// AOverlapLogActor implementation for task t1-overlap-logs-once. The constructor
// creates a query-only USphereComponent overlap volume as the root (overlap
// events generated, response to all channels) so an actor overlapping it can be
// detected, and stamps the "OverlapLogRoot" identity tag. No overlap handling or
// logging is provided; the required behavior is specified in the task prompt and
// is the agent's to implement.

#include "OverlapLogActor.h"

#include "Components/SphereComponent.h"

AOverlapLogActor::AOverlapLogActor()
{
	PrimaryActorTick.bCanEverTick = false;

	CollisionSphere = CreateDefaultSubobject<USphereComponent>(TEXT("CollisionSphere"));
	SetRootComponent(CollisionSphere);
	CollisionSphere->InitSphereRadius(64.0f);
	CollisionSphere->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	CollisionSphere->SetCollisionObjectType(ECC_WorldDynamic);
	CollisionSphere->SetCollisionResponseToAllChannels(ECR_Overlap);
	CollisionSphere->SetGenerateOverlapEvents(true);

	Tags.Add(FName("OverlapLogRoot"));
}

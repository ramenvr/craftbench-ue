// Copyright CraftBench. All Rights Reserved.
//
// AMissileTargetActor implementation for task t2-homing-projectile. The
// constructor disables tick, stamps the "MissileTarget" identity tag, and
// gives the actor a movable root so runtime relocation is possible.

#include "MissileTargetActor.h"
#include "Components/SceneComponent.h"

AMissileTargetActor::AMissileTargetActor()
{
	PrimaryActorTick.bCanEverTick = false;
	USceneComponent* Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	Root->SetMobility(EComponentMobility::Movable);
	SetRootComponent(Root);
	Tags.Add(FName("MissileTarget"));
}

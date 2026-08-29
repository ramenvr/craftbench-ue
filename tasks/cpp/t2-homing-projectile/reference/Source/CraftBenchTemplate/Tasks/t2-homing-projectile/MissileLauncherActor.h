// Copyright CraftBench. All Rights Reserved.
//
// Reference solution for task t2-homing-projectile: the launcher fires one
// homing projectile at the target when gameplay begins.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "MissileLauncherActor.generated.h"

UCLASS()
class CRAFTBENCHTEMPLATE_API AMissileLauncherActor : public AActor
{
	GENERATED_BODY()

public:
	AMissileLauncherActor();

protected:
	virtual void BeginPlay() override;
};

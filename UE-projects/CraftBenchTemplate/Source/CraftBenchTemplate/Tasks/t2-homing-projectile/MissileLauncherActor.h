// Copyright CraftBench. All Rights Reserved.
//
// AMissileLauncherActor — pre-existing actor for task t2-homing-projectile.
// The constructor stamps the "MissileLauncher" identity tag; no gameplay
// behavior is declared. The required behavior is specified in the task prompt
// and is the agent's to implement. Agents may subclass or rename freely.

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
};

// Copyright CraftBench. All Rights Reserved.
//
// AMissileTargetActor — pre-existing actor for task t2-homing-projectile.
// The constructor stamps the "MissileTarget" identity tag; the actor has no
// behavior of its own (the level places it ~2000 units from the launcher).
// Agents may subclass or rename freely; identity is the tag.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "MissileTargetActor.generated.h"

UCLASS()
class CRAFTBENCHTEMPLATE_API AMissileTargetActor : public AActor
{
	GENERATED_BODY()

public:
	AMissileTargetActor();
};

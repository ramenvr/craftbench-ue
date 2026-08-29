// Copyright CraftBench. All Rights Reserved.
//
// ATeleportDestinationMarker — pre-existing destination marker for task
// t1-overlap-teleport-portal. A plain movable point in the world; the
// constructor stamps the "TeleportDestination" identity tag. It carries no
// behavior of its own and needs none — it only marks a spot.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "TeleportDestinationMarker.generated.h"

UCLASS()
class THIRDPERSON_API ATeleportDestinationMarker : public AActor
{
	GENERATED_BODY()

public:
	ATeleportDestinationMarker();
};

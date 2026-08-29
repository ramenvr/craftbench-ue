// Copyright CraftBench. All Rights Reserved.
//
// ATeleportPortalActor — pre-existing portal frame for task
// t1-overlap-teleport-portal. Placed in the task level; the constructor builds
// the doorway-shaped query-only volume and stamps the "TeleportPortal"
// identity tag. The required behavior is specified in the task prompt and is
// the agent's to implement. Edit this type in place - a placed instance of
// it is graded, so a new subclass never reaches the level and renaming
// breaks the placed reference.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "TeleportPortalActor.generated.h"

class UBoxComponent;

UCLASS()
class THIRDPERSON_API ATeleportPortalActor : public AActor
{
	GENERATED_BODY()

public:
	ATeleportPortalActor();

protected:
	/** Doorway-shaped overlap volume (root). Query-only; overlaps all channels. */
	UPROPERTY(VisibleAnywhere, Category = "Portal")
	TObjectPtr<UBoxComponent> PortalVolume;
};

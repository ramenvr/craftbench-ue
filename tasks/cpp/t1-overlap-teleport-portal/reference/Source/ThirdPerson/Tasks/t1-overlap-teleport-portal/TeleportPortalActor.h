// Copyright CraftBench. All Rights Reserved.
//
// ATeleportPortalActor — reference solution for task t1-overlap-teleport-portal.
// The portal relocates any character that enters its volume to wherever the
// level's destination marker currently is, read at the moment of the teleport.

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

	virtual void NotifyActorBeginOverlap(AActor* OtherActor) override;

protected:
	/** Doorway-shaped overlap volume (root). Query-only; overlaps all channels. */
	UPROPERTY(VisibleAnywhere, Category = "Portal")
	TObjectPtr<UBoxComponent> PortalVolume;
};

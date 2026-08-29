// Copyright CraftBench. All Rights Reserved.
//
// GAMING VARIANT (resnap-after-exit) — models anti-gaming note #4: the portal
// remembers whoever entered and keeps pinning them to the marker every tick,
// so "the player is at the destination" holds at any sampling instant. The
// fixture walks the delivered character OUT of the destination after the
// delivery check; this variant drags it back. Must FAIL checkpoint 2 ("no
// repeated snapping back").

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
	virtual void Tick(float DeltaSeconds) override;

protected:
	UPROPERTY(VisibleAnywhere, Category = "Portal")
	TObjectPtr<UBoxComponent> PortalVolume;

private:
	TWeakObjectPtr<AActor> CaughtPawn;
};

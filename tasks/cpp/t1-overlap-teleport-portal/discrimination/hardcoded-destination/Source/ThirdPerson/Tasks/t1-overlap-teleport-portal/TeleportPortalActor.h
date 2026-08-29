// Copyright CraftBench. All Rights Reserved.
//
// GAMING VARIANT (hardcoded-destination) — models anti-gaming note #3: the
// overlap wiring is correct, but the landing spot is the marker's AUTHORED
// map coordinates baked into code; the marker actor is never consulted. The
// fixture moves the marker in PrepareTest, so the entrant is delivered to the
// wrong place. Must FAIL checkpoint 1 ("delivered to the marked
// destination").

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
	UPROPERTY(VisibleAnywhere, Category = "Portal")
	TObjectPtr<UBoxComponent> PortalVolume;
};

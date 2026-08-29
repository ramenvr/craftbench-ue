// Copyright CraftBench. All Rights Reserved.
//
// GAMING VARIANT (delayed-unconditional-teleport) — models anti-gaming note
// #2's timed shape: no overlap logic at all; one second after BeginPlay a
// timer relocates every character in the world to the marker. An
// instant-only pre-contact sample (t=0.5) is green, and by any later sample
// the walker is "delivered" — only the fixture's CONTINUOUS pre-contact
// guard catches the delivery happening while the walker is still short of
// the portal. Must FAIL in the guard window, via that guard's own literal
// ("delivered mid-approach without ever reaching the portal") and NOT via
// cp0's - the two were separated by the 2026-08-17 message-only split.

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

	virtual void BeginPlay() override;

protected:
	UPROPERTY(VisibleAnywhere, Category = "Portal")
	TObjectPtr<UBoxComponent> PortalVolume;

private:
	void TeleportEveryone();

	FTimerHandle DelayedTeleportHandle;
};

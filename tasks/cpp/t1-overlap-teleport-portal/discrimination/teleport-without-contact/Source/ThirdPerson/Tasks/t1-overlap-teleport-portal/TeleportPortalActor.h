// Copyright CraftBench. All Rights Reserved.
//
// GAMING VARIANT (teleport-without-contact) — models anti-gaming note #2:
// the portal relocates every character in the world on its own schedule,
// without any entry/contact. Must FAIL checkpoint 0 ("before entering the
// portal").

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

	virtual void Tick(float DeltaSeconds) override;

protected:
	UPROPERTY(VisibleAnywhere, Category = "Portal")
	TObjectPtr<UBoxComponent> PortalVolume;
};

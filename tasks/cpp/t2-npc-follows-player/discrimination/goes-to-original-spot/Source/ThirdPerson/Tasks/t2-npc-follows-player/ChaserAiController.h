// GAMING VARIANT (goes-to-original-spot): the controller reads the player's
// position exactly once, then forever path-follows to that CACHED LOCATION —
// never to the live player. Indistinguishable from a real chase while the
// player stands still; the moment the player is elsewhere, the NPC keeps
// commuting to the stale spot.

#pragma once

#include "CoreMinimal.h"
#include "AIController.h"
#include "ChaserAiController.generated.h"

UCLASS()
class THIRDPERSON_API AChaserAiController : public AAIController
{
	GENERATED_BODY()

protected:
	virtual void OnPossess(APawn* InPawn) override;
	virtual void OnUnPossess() override;

private:
	void IssueChase();

	FTimerHandle ChaseTimer;
	FVector CachedSpot = FVector::ZeroVector;
	bool bSpotCached = false;
};

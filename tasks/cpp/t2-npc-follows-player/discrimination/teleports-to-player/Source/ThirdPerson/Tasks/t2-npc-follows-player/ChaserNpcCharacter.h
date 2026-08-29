// GAMING VARIANT (teleports-to-player): no pathing, no walking — a looping
// timer snaps the NPC to just short of the player's position. Every
// checkpoint-instant distance sample looks like a perfect chase; the
// continuous per-frame displacement guard must catch the snap itself.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "ChaserNpcCharacter.generated.h"

UCLASS()
class THIRDPERSON_API AChaserNpcCharacter : public ACharacter
{
	GENERATED_BODY()

public:
	AChaserNpcCharacter();

protected:
	virtual void BeginPlay() override;

private:
	void SnapToPlayer();

	FTimerHandle SnapTimer;
};

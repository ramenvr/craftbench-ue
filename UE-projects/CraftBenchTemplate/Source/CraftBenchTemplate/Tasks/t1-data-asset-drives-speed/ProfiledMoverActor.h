// Copyright CraftBench. All Rights Reserved.
//
// AProfiledMoverActor — pre-existing actor for task t1-data-asset-drives-speed.
// The constructor builds a movable cube root and stamps the "ProfiledMoverRoot"
// identity tag. The Profile data asset is assigned on the placed instance.
// Reading CruiseSpeed from the profile and moving the actor forward at that
// speed is the agent's task, per the prompt. Agents may subclass or rename
// freely.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ProfiledMoverActor.generated.h"

class UStaticMeshComponent;
class UMovementProfileAsset;

UCLASS()
class CRAFTBENCHTEMPLATE_API AProfiledMoverActor : public AActor
{
	GENERATED_BODY()

public:
	AProfiledMoverActor();

protected:
	UPROPERTY(VisibleAnywhere)
	UStaticMeshComponent* Body;

	// Designer content configuring how fast this actor cruises. Read CruiseSpeed
	// from it and move the actor forward at that speed.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Movement")
	UMovementProfileAsset* Profile;
};

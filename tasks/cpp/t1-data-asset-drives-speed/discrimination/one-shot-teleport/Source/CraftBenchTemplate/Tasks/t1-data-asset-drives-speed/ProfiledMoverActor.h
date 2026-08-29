// Copyright CraftBench. All Rights Reserved.
//
// Reference solution for task t1-data-asset-drives-speed: read CruiseSpeed from
// the assigned movement-profile data asset and drive the actor forward at that
// speed via a projectile movement component (zero gravity, constant velocity).

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ProfiledMoverActor.generated.h"

class UStaticMeshComponent;
class UMovementProfileAsset;
class UProjectileMovementComponent;

UCLASS()
class CRAFTBENCHTEMPLATE_API AProfiledMoverActor : public AActor
{
	GENERATED_BODY()

public:
	AProfiledMoverActor();

protected:
	virtual void BeginPlay() override;

	// GAMED DELTA (variant one-shot-teleport): tick-driven pre-cp0 teleport
	// burst; see the .cpp for the full mechanism and timing argument.
	virtual void Tick(float DeltaSeconds) override;

	UPROPERTY(VisibleAnywhere)
	UStaticMeshComponent* Body;

	UPROPERTY(VisibleAnywhere)
	UProjectileMovementComponent* Movement;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Movement")
	UMovementProfileAsset* Profile;
};

// Copyright CraftBench. All Rights Reserved.
//
// UMovementProfileAsset — substrate data-asset class for task
// t1-data-asset-drives-speed. A standalone designer-tunable content asset whose
// CruiseSpeed the agent reads at runtime and applies as the actor's forward
// speed. The agent reads it; it does NOT edit this class.

#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "MovementProfileAsset.generated.h"

UCLASS(BlueprintType)
class CRAFTBENCHTEMPLATE_API UMovementProfileAsset : public UPrimaryDataAsset
{
	GENERATED_BODY()

public:
	// Forward cruise speed, in unreal units per second.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Movement")
	float CruiseSpeed = 0.0f;
};

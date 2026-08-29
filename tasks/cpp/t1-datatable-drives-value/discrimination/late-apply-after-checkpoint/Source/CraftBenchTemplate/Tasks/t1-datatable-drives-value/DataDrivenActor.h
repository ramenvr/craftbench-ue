// Copyright CraftBench. All Rights Reserved.
//
// Reference solution for task t1-datatable-drives-value: in BeginPlay, look up
// the "Default" row of the assigned tuning record and copy its TunedValue onto
// ConfiguredValue.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "DataDrivenActor.generated.h"

class UDataTable;

UCLASS()
class CRAFTBENCHTEMPLATE_API ADataDrivenActor : public AActor
{
	GENERATED_BODY()

public:
	ADataDrivenActor();

	UPROPERTY(BlueprintReadWrite, Category = "DataDriven")
	float ConfiguredValue = -1.0f;

protected:
	virtual void BeginPlay() override;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "DataDriven")
	UDataTable* TuningTable;
};

// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT (double-typed-property) for task
// t1-datatable-drives-value. ONE DELTA vs the reference: ConfiguredValue is
// retyped float -> double (a realistic UE5-era drift when an agent rewrites
// the header). The record lookup itself is correct, but the fixture reads a
// float 'ConfiguredValue' UPROPERTY by reflection (CastField<FFloatProperty>),
// so the read fails. Targets anti-gaming note #4 (wrong property).

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
	double ConfiguredValue = -1.0;

protected:
	virtual void BeginPlay() override;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "DataDriven")
	UDataTable* TuningTable;
};

// Copyright CraftBench. All Rights Reserved.
//
// ADataDrivenActor — pre-existing actor for task t1-datatable-drives-value. The
// constructor stamps the "DataDrivenRoot" identity tag and leaves ConfiguredValue
// at its -1 sentinel. The TuningTable data record is assigned on the placed
// instance. Reading a row's value from the record and applying it to
// ConfiguredValue is the agent's task, per the prompt. Agents may subclass or
// rename freely.

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

	// Exposed setting other gameplay code can read. Starts at the -1 sentinel;
	// must be populated from the data record at runtime.
	UPROPERTY(BlueprintReadWrite, Category = "DataDriven")
	float ConfiguredValue = -1.0f;

protected:
	// The project's tuning record (rows = FTuningRow), assigned on the placed
	// instance. Read a row's value from this; do not hard-code the value.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "DataDriven")
	UDataTable* TuningTable;
};

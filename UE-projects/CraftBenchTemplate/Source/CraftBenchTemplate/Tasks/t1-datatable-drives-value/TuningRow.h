// Copyright CraftBench. All Rights Reserved.
//
// Substrate row struct for task t1-datatable-drives-value: the row type of the
// project's tuning data table (Content/Data/DT_Tuning). The agent reads a row's
// TunedValue at runtime; it does NOT edit this struct.

#pragma once

#include "CoreMinimal.h"
#include "Engine/DataTable.h"
#include "TuningRow.generated.h"

USTRUCT(BlueprintType)
struct FTuningRow : public FTableRowBase
{
	GENERATED_BODY()

	// The tunable numeric value the row carries.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tuning")
	float TunedValue = 0.0f;
};

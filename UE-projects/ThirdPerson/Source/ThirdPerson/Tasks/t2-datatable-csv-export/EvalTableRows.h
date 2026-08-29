// Row structs for task t2-datatable-csv-export.
//
// Three FTableRowBase structs backing the three data tables shipped under
// Content/Tasks/t2-datatable-csv-export/data/. Mixed field types (string /
// integer / float) on purpose: the tables exist to hold real, typed data.
#pragma once

#include "CoreMinimal.h"
#include "Engine/DataTable.h"
#include "EvalTableRows.generated.h"

USTRUCT(BlueprintType)
struct FEvalItemRow : public FTableRowBase
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Eval")
	FString DisplayName;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Eval")
	int32 Cost = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Eval")
	float Weight = 0.f;
};

USTRUCT(BlueprintType)
struct FEvalWaveRow : public FTableRowBase
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Eval")
	int32 EnemyCount = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Eval")
	float SpawnInterval = 0.f;
};

USTRUCT(BlueprintType)
struct FEvalTuningRow : public FTableRowBase
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Eval")
	float Value = 0.f;
};

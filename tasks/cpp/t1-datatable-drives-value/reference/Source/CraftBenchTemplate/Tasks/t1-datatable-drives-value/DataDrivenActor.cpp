// Copyright CraftBench. All Rights Reserved.
//
// Reference solution for task t1-datatable-drives-value.

#include "DataDrivenActor.h"

#include "TuningRow.h"
#include "Engine/DataTable.h"

ADataDrivenActor::ADataDrivenActor()
{
	PrimaryActorTick.bCanEverTick = false;
	Tags.Add(FName("DataDrivenRoot"));
	TuningTable = nullptr;
}

void ADataDrivenActor::BeginPlay()
{
	Super::BeginPlay();
	if (TuningTable != nullptr)
	{
		static const FString Context(TEXT("t1-datatable-drives-value"));
		const FTuningRow* Row = TuningTable->FindRow<FTuningRow>(FName("Default"), Context);
		if (Row != nullptr)
		{
			ConfiguredValue = Row->TunedValue;
		}
	}
}

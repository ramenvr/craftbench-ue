// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT (double-typed-property) for task
// t1-datatable-drives-value. The .cpp is byte-identical to the reference
// (the lookup is correct); the single delta lives in the header, where
// ConfiguredValue was retyped float -> double.

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

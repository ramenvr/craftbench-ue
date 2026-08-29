// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT (late-apply-after-checkpoint) for task
// t1-datatable-drives-value. ONE DELTA vs the reference: the record lookup is
// correct but DEFERRED behind a 1.5 s timer ("wait for assets to settle"
// reasoning), so ConfiguredValue still holds the -1 sentinel when the first
// verification checkpoint samples at world t=1.0 s. Probes the
// does-it-at-the-wrong-time boundary of anti-gaming note #2: the value must be
// applied when gameplay begins, not eventually.

#include "DataDrivenActor.h"

#include "TuningRow.h"
#include "Engine/DataTable.h"
#include "TimerManager.h"

ADataDrivenActor::ADataDrivenActor()
{
	PrimaryActorTick.bCanEverTick = false;
	Tags.Add(FName("DataDrivenRoot"));
	TuningTable = nullptr;
}

void ADataDrivenActor::BeginPlay()
{
	Super::BeginPlay();
	FTimerHandle Handle;
	GetWorldTimerManager().SetTimer(Handle, FTimerDelegate::CreateLambda([this]()
	{
		if (TuningTable != nullptr)
		{
			static const FString Context(TEXT("t1-datatable-drives-value"));
			const FTuningRow* Row = TuningTable->FindRow<FTuningRow>(FName("Default"), Context);
			if (Row != nullptr)
			{
				ConfiguredValue = Row->TunedValue;
			}
		}
	}), 1.5f, false);
}

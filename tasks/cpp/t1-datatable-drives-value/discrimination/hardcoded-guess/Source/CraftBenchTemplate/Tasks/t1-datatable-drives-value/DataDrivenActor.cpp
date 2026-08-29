// Copyright CraftBench. All Rights Reserved.
//
// DISCRIMINATION VARIANT (hardcoded-guess) for task t1-datatable-drives-value.
// ONE DELTA vs the reference: BeginPlay writes a plausible guessed constant to
// ConfiguredValue and never reads the assigned tuning record. Targets
// anti-gaming note #1 (hardcoded constant). Must FAIL the L2 value gate at
// cp0 (wrong value, not the -1 sentinel).

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
	// Gaming shape: a number written in code instead of a record lookup. The
	// row's TunedValue is undisclosed and non-round, so a guess misses the
	// +/-0.01 assertion window.
	ConfiguredValue = 100.0f;
}

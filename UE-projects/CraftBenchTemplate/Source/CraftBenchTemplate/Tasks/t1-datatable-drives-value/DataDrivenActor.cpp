// Copyright CraftBench. All Rights Reserved.
//
// ADataDrivenActor implementation for task t1-datatable-drives-value. The
// constructor stamps the "DataDrivenRoot" identity tag. No row lookup is
// provided; ConfiguredValue stays at its -1 sentinel until the agent reads the
// record and applies a value.

#include "DataDrivenActor.h"

ADataDrivenActor::ADataDrivenActor()
{
	PrimaryActorTick.bCanEverTick = false;
	Tags.Add(FName("DataDrivenRoot"));
	TuningTable = nullptr;
}

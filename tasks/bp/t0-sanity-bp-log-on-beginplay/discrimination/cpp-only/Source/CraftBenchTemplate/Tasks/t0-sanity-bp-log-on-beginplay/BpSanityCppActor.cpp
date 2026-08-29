// Discrimination variant "cpp-only" for task t0-sanity-bp-log-on-beginplay. See .h.

#include "BpSanityCppActor.h"

#include "Kismet/KismetSystemLibrary.h"

ABpSanityCppActor::ABpSanityCppActor()
{
	PrimaryActorTick.bCanEverTick = false;
}

void ABpSanityCppActor::BeginPlay()
{
	Super::BeginPlay();
	// Emits on LogBlueprintUserMessages/Log (same channel Print String uses), so
	// the token WOULD be captured — but only if an instance ran. This produces no
	// .uasset at /Game/Tasks/t0-sanity-bp-log-on-beginplay/BP_Announcer, so the fixture's load fails and it
	// never runs: L2 FAILs at PrepareTest. That is the intended outcome.
	UKismetSystemLibrary::PrintString(
		this, TEXT("CRAFTBENCH_BP_OK"), true, true, FLinearColor::Green, 2.0f);
}

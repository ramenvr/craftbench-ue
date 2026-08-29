// Discrimination variant "cpp-only" for task t0-sanity-bp-log-on-beginplay.
//
// A C++ actor that emits the exact token on BeginPlay. It builds cleanly (L1
// passes) and, IF placed and played, would print CRAFTBENCH_BP_OK once. But this
// task requires a BLUEPRINT at /Game/Tasks/t0-sanity-bp-log-on-beginplay/BP_Announcer: a C++ edit produces
// no .uasset at that path, so the L2 fixture's StaticLoadClass returns null.
//
// Expected verdict: FAIL at PrepareTest ("No Actor Blueprint found at the required
// path ...") — the anti-gaming #1 defense that makes this a Blueprint task.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "BpSanityCppActor.generated.h"

UCLASS()
class CRAFTBENCHTEMPLATE_API ABpSanityCppActor : public AActor
{
	GENERATED_BODY()

public:
	ABpSanityCppActor();

protected:
	virtual void BeginPlay() override;
};

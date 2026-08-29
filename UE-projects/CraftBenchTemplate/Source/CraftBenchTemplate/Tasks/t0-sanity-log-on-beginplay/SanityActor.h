// Copyright CraftBench. All Rights Reserved.
//
// ASanityActor — pre-existing actor for task t0-sanity-log-on-beginplay. The
// constructor stamps the "SanityRoot" identity tag; no BeginPlay override is
// declared. The required behavior is specified in the task prompt and is the
// agent's to implement. Agents may subclass or rename freely.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "SanityActor.generated.h"

UCLASS()
class CRAFTBENCHTEMPLATE_API ASanityActor : public AActor
{
	GENERATED_BODY()

public:
	ASanityActor();
};

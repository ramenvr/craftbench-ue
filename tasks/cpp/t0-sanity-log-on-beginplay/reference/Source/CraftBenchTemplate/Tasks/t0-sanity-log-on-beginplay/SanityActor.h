// Reference solution for task t0-sanity-log-on-beginplay.
// Adds a BeginPlay override to the substrate's ASanityActor declaration. The
// implementation in SanityActor.cpp emits the literal "CRAFTBENCH_SANITY_OK"
// to LogTemp at Display verbosity exactly once.

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

protected:
	virtual void BeginPlay() override;
};

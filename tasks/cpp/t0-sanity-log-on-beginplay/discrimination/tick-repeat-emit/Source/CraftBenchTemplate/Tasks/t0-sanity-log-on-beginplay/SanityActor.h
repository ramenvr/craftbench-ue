// Discrimination variant "tick-repeat-emit" for task t0-sanity-log-on-beginplay.
// Delta vs the reference header: a Tick override is declared so the .cpp can
// emit the literal every frame instead of exactly once in BeginPlay.

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

	virtual void Tick(float DeltaSeconds) override;

protected:
	virtual void BeginPlay() override;
};

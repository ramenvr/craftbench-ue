// Discrimination variant "wrong-category-log" for task t0-sanity-log-on-beginplay.
// Header is unchanged from the reference: the delta lives entirely in the .cpp
// (the emission is routed to a custom log category instead of LogTemp).

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

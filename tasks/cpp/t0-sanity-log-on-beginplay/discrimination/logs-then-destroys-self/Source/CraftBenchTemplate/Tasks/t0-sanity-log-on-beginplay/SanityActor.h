// Discrimination variant "logs-then-destroys-self" for task
// t0-sanity-log-on-beginplay. Header is unchanged from the reference: the
// delta lives entirely in the .cpp (the actor destroys itself after logging).

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

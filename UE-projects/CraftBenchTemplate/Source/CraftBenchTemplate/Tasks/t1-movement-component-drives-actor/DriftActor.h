// Copyright CraftBench. All Rights Reserved.
//
// ADriftActor — pre-existing actor for task t1-movement-component-drives-actor.
// The constructor creates a visible cube mesh root and stamps the "DriftRoot"
// identity tag. It has no self-motion, so it sits still when gameplay begins;
// making it glide at a steady velocity is the agent's task, per the prompt.
// Agents may subclass or rename freely.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "DriftActor.generated.h"

class UStaticMeshComponent;

UCLASS()
class CRAFTBENCHTEMPLATE_API ADriftActor : public AActor
{
	GENERATED_BODY()

public:
	ADriftActor();

protected:
	UPROPERTY(VisibleAnywhere)
	UStaticMeshComponent* Body;
};

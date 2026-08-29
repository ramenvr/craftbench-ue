// Copyright CraftBench. All Rights Reserved.
//
// A round marker for task t3-reach-the-exit-before-they-see-you. Two of these carry
// the tag of each round; a watcher paces between the pair whose tag matches its own.
//
// NON-COLLIDING on every channel, deliberately. The yard promises that a post never
// blocks anything, and a post that quietly stopped a line between two places would
// make a submission that asks "is anything in the way?" disagree with a yard that
// never asks.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "StealthPostActor.generated.h"

class UStaticMeshComponent;

UCLASS()
class THIRDPERSON_API AStealthPostActor : public AActor
{
	GENERATED_BODY()

public:
	AStealthPostActor();

	/** The post you can see. No collision at all. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Post")
	UStaticMeshComponent* Body = nullptr;
};

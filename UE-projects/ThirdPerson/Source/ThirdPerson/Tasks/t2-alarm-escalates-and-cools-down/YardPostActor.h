// Copyright CraftBench. All Rights Reserved.
//
// A round marker for task t2-alarm-escalates-and-cools-down. Two of these carry the
// tag RoundNorth and two carry RoundSouth; a guard paces between the pair whose tag
// matches its own RoundTag.
//
// NON-COLLIDING on every channel, deliberately. The yard promises there is nothing to
// hide behind, and a post that blocks a trace would make a submission that asks "is
// anything in the way?" disagree with a yard that never asks.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "YardPostActor.generated.h"

class UStaticMeshComponent;

UCLASS()
class THIRDPERSON_API AYardPostActor : public AActor
{
	GENERATED_BODY()

public:
	AYardPostActor();

	/** The post you can see. No collision at all. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Post")
	UStaticMeshComponent* Body = nullptr;
};

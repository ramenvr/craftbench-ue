// Copyright CraftBench. All Rights Reserved.
//
// The one empty piece in the yard, for task t3-checkpoint-restores-the-world.
//
// The yard around it works. Pads light when something tells them to and know where
// somebody sent back to them should stand. Doors latch open off their own plates and
// go back through their own operation. Coins can be taken and put back. The counter
// holds CARRIED and BANKED and shows both. Hot floor says when somebody has touched
// it. See CheckpointYardProps.h -- none of it is yours to change.
//
// What nothing in the yard does is decide what should happen NEXT: which pad is the
// mark, what the yard looked like when that mark was set, and what to put back when a
// life ends. That decision has to land HERE. Every prop and this director are placed
// instances in a map you cannot edit, so a subclass would never be instantiated -- it
// is this class that has to carry the answer.
//
// As shipped: no tick, no timer, no reference to any prop, and no state.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "CheckpointDirectorActor.generated.h"

UCLASS()
class THIRDPERSON_API ACheckpointDirectorActor : public AActor
{
	GENERATED_BODY()

public:
	ACheckpointDirectorActor();

	/** Somewhere for the piece to stand in the yard. It has no size and no collision. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Director")
	USceneComponent* Root = nullptr;

protected:
	virtual void BeginPlay() override;
};

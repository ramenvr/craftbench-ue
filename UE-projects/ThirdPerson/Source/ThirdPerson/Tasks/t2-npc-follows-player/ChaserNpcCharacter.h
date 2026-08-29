// Copyright CraftBench. All Rights Reserved.
//
// AChaserNpcCharacter — pre-existing enemy NPC body for task
// t2-npc-follows-player. A concrete character subclass placed in the task
// level; the constructor stamps the "ChaserNpc" identity tag. No controller
// logic and no movement logic ship — the required behavior is specified in
// the task prompt and is the agent's to implement. Edit this type in place
// (its class defaults reach the placed instance); do not rename the class —
// a placed instance of it is graded.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "ChaserNpcCharacter.generated.h"

UCLASS()
class THIRDPERSON_API AChaserNpcCharacter : public ACharacter
{
	GENERATED_BODY()

public:
	AChaserNpcCharacter();
};

// Copyright CraftBench. All Rights Reserved.
//
// AChaserNpcCharacter — reference solution for task t2-npc-follows-player.
// The class defaults now select the chasing AI controller; the placed map
// instance picks both up at load (unedited placed-actor properties read the
// class defaults).

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

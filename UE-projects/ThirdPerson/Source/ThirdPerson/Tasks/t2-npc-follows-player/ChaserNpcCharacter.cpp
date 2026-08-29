// Copyright CraftBench. All Rights Reserved.
//
// AChaserNpcCharacter implementation for task t2-npc-follows-player. The
// constructor stamps the "ChaserNpc" identity tag. No behavior is provided;
// the required behavior is specified in the task prompt and is the agent's
// to implement.

#include "ChaserNpcCharacter.h"

AChaserNpcCharacter::AChaserNpcCharacter()
{
	Tags.Add(FName("ChaserNpc"));
}

// Copyright CraftBench. All Rights Reserved.
//
// AMissileLauncherActor implementation for task t2-homing-projectile. The
// constructor disables tick and stamps the "MissileLauncher" identity tag.
// No gameplay behavior is provided here; the required behavior is specified
// in the task prompt and is the agent's to implement.

#include "MissileLauncherActor.h"

AMissileLauncherActor::AMissileLauncherActor()
{
	PrimaryActorTick.bCanEverTick = false;
	Tags.Add(FName("MissileLauncher"));
}

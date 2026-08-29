// Copyright CraftBench. All Rights Reserved.
//
// Reference solution for task t2-homing-projectile: on BeginPlay, resolve the
// target by its tag and fire exactly one homing projectile at it.

#include "MissileLauncherActor.h"

#include "HomingMissile.h"
#include "Kismet/GameplayStatics.h"

AMissileLauncherActor::AMissileLauncherActor()
{
	PrimaryActorTick.bCanEverTick = false;
	Tags.Add(FName("MissileLauncher"));
}

void AMissileLauncherActor::BeginPlay()
{
	Super::BeginPlay();

	TArray<AActor*> Targets;
	UGameplayStatics::GetAllActorsWithTag(GetWorld(), FName("MissileTarget"), Targets);
	if (Targets.Num() == 0)
	{
		return;
	}

	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	AHomingMissile* Missile = GetWorld()->SpawnActor<AHomingMissile>(
		GetActorLocation(), FRotator::ZeroRotator, Params);
	if (Missile != nullptr)
	{
		Missile->InitHoming(Targets[0]);
	}
}

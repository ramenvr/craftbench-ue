// Copyright CraftBench. All Rights Reserved.
//
// Reference solution for task t1-physics-drop-and-rest: enable dynamic physics on
// the cube and set its collision so it ignores the Pawn channel but blocks
// WorldStatic, so it falls under gravity and rests on the floor.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "PhysicsDropActor.generated.h"

class UStaticMeshComponent;

UCLASS()
class CRAFTBENCHTEMPLATE_API APhysicsDropActor : public AActor
{
	GENERATED_BODY()

public:
	APhysicsDropActor();

protected:
	UPROPERTY(VisibleAnywhere)
	UStaticMeshComponent* Body;
};

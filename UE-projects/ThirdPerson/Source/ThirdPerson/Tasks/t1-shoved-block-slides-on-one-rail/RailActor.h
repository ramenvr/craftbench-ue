// Copyright CraftBench. All Rights Reserved.
//
// The painted rail: a long, low plinth the world never moves. Its FORWARD axis
// is the rail direction, so the rail bearing can be read straight off this
// actor rather than guessed from the level.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "RailActor.generated.h"

class UStaticMeshComponent;

UCLASS()
class THIRDPERSON_API ARailActor : public AActor
{
	GENERATED_BODY()

public:
	ARailActor();

	/** The painted plinth. Solid, immovable, and safe to anchor to. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Bench")
	UStaticMeshComponent* Rail = nullptr;
};

// Copyright CraftBench. All Rights Reserved.
//
// A relic standing in the arena for task t2-collect-then-exit. It arrives visible,
// with the contact volume the level's rules are written against, and nothing else:
// walking into one does not yet do anything.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "RelicPickup.generated.h"

class USphereComponent;
class UStaticMeshComponent;

UCLASS()
class THIRDPERSON_API ARelicPickup : public AActor
{
	GENERATED_BODY()

public:
	ARelicPickup();

	/** The contact volume: a 120 cm sphere, query-only, overlap events on. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Relic")
	USphereComponent* RelicVolume = nullptr;

	/** What you can see of the relic. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Relic")
	UStaticMeshComponent* RelicMesh = nullptr;
};

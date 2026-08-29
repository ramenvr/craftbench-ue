// Copyright CraftBench. All Rights Reserved.
//
// The spiked slab on the rail for task
// t1-spikes-hurt-you-and-you-respawn-at-your-marker. It arrives still: it does not
// move and it does not hurt anybody. Its collision is query-only, so it can never
// push or block a character -- it can only be noticed.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "SpikeSlabActor.generated.h"

class UStaticMeshComponent;

UCLASS()
class THIRDPERSON_API ASpikeSlabActor : public AActor
{
	GENERATED_BODY()

public:
	ASpikeSlabActor();

	/** The 240 x 240 x 200 cm slab. Movable, overlap-only. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Spikes")
	UStaticMeshComponent* SlabMesh = nullptr;
};

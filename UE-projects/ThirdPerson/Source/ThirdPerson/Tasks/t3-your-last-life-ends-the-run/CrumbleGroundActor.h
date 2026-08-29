// Copyright CraftBench. All Rights Reserved.
//
// The patch of crumbling ground for task t3-your-last-life-ends-the-run. It lies flat
// across the floor part way down, wide enough to span the lane, and it is the only
// thing in the level that can claim a runner.
//
// It arrives inert. It notices bodies and blocks nothing -- a runner walks straight
// over it and is never pushed or stopped by it -- and it does nothing about what it
// notices. Nothing here decides that anybody has been claimed.
//
// PatchVolume is the shape of the patch, in world centimetres. Read it; the ground is
// not yours to move or resize.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "CrumbleGroundActor.generated.h"

class UBoxComponent;
class UStaticMeshComponent;

UCLASS()
class THIRDPERSON_API ACrumbleGroundActor : public AActor
{
	GENERATED_BODY()

public:
	ACrumbleGroundActor();

	/** The broken ground you can see. Flat, non-colliding, walked straight over. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Crumble")
	UStaticMeshComponent* PatchMesh = nullptr;

	/** The shape of the patch: query-only, overlapping everything, blocking nothing. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Crumble")
	UBoxComponent* PatchVolume = nullptr;
};

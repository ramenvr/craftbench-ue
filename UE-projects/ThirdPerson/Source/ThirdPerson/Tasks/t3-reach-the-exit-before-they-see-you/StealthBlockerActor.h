// Copyright CraftBench. All Rights Reserved.
//
// A crate stack, or a length of wall, for task t3-reach-the-exit-before-they-see-you.
//
// SOLID on every channel and standing from the floor to well above head height, so
// there is no height at which it stops being in the way. Its footprint is whatever the
// yard set on it; both the block you walk into and the block you see are the same box,
// so what you can hide behind and what you can walk around can never disagree.
//
// Nothing here decides anything. It is a thing in a yard.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "StealthBlockerActor.generated.h"

class UBoxComponent;
class USceneComponent;
class UStaticMeshComponent;

UCLASS()
class THIRDPERSON_API AStealthBlockerActor : public AActor
{
	GENERATED_BODY()

public:
	AStealthBlockerActor();

	virtual void OnConstruction(const FTransform& Transform) override;

	/** Where the block stands. The ROOT, unscaled, and at floor level: the actor's own
	 *  location is the middle of the block's footprint, on the floor. Nothing hangs off
	 *  a scaled root here on purpose -- a scaled root multiplies both a child's offset
	 *  AND its collision extent, so a box authored as 300 wide on a root scaled 2 is
	 *  600 wide and every number in the level is a lie. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Blocker")
	USceneComponent* Anchor = nullptr;

	/** The solid box, sized directly rather than scaled, standing on the floor. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Blocker")
	UBoxComponent* Block = nullptr;

	/** The crate face you can see. Follows the box exactly. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Blocker")
	UStaticMeshComponent* Body = nullptr;

	/** Half the size of this block, in centimetres, measured from its centre. The
	 *  block sits ON the floor: the actor's own location is at floor level and the box
	 *  rises from there. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Blocker")
	FVector BlockHalfExtentUu = FVector(200.0f, 200.0f, 220.0f);

	/** Half the size of this block, in centimetres. */
	UFUNCTION(BlueprintPure, Category = "Blocker")
	FVector GetBlockHalfExtentUu() const { return BlockHalfExtentUu; }
};

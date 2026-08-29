// Copyright CraftBench. All Rights Reserved.
//
// A patch of marked ground for task t1-walks-around-the-marked-ground-to-the-goal.
// It is PAINT, not a wall: nothing about it blocks anything, and a figure can walk
// straight over it. What it carries is a flag saying whether crossing it is allowed
// this trip, and a geometry test for whether a point is on it. Both are supplied.
//
// Two of these stand in the yard. They are the same shape and the same colour when
// they are in the same state; which one is out of bounds is decided per trip and
// shows on the patch itself.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "MarkedGroundActor.generated.h"

class UMaterialInterface;
class UStaticMeshComponent;

UCLASS()
class THIRDPERSON_API AMarkedGroundActor : public AActor
{
	GENERATED_BODY()

public:
	AMarkedGroundActor();

	/** The three strokes of the U, in order: the far wall, then the two arms that
	 *  reach back toward the near side. Flat on the floor, and NONE of them block. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Marked Ground")
	TArray<UStaticMeshComponent*> Strokes;

	/** Whether stepping on this patch is out of bounds RIGHT NOW. The LEVEL ships
	 *  with one of the two patches already marked, so the yard means something the
	 *  moment somebody presses Play; the fixture then re-marks them for each of its
	 *  trips. A real UPROPERTY on purpose -- it has to be readable, both by whatever
	 *  routes the walker and by the yard checking that nobody quietly changed the
	 *  question -- and EditAnywhere so the level can set it. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Marked Ground")
	bool bOutOfBounds = false;

	UFUNCTION(BlueprintPure, Category = "Marked Ground")
	bool IsOutOfBounds() const { return bOutOfBounds; }

	/** Sets the flag and repaints the patch so the state is visible. */
	UFUNCTION(BlueprintCallable, Category = "Marked Ground")
	void SetOutOfBounds(bool bNewOutOfBounds);

	/** True when a world-space point is on the painted ground. Supplied so that
	 *  working out the shape is not the exercise -- deciding a route around it is. */
	UFUNCTION(BlueprintPure, Category = "Marked Ground")
	bool CoversPoint(const FVector& WorldPoint) const;

	/** The outer extent of the whole patch, world space, for coarse tests. */
	UFUNCTION(BlueprintPure, Category = "Marked Ground")
	FBox WorldFootprint() const;

protected:
	virtual void BeginPlay() override;

private:
	/** The two looks the paint takes. Swapped WHOLESALE rather than driven by a
	 *  material parameter: the prototype materials in this substrate do not all
	 *  carry a colour parameter, and a SetVectorParameterValue that silently does
	 *  nothing would leave the state invisible while looking like it worked. */
	UPROPERTY()
	UMaterialInterface* OutOfBoundsLook = nullptr;

	UPROPERTY()
	UMaterialInterface* AllowedLook = nullptr;
};

// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION for t2-crate-you-carry-changes-what-you-can-do.
//
// A weight plate: a 900 x 900 cm pad you can walk onto, with the least it will hold
// for painted on it. Every frame it works out what is RESTING on its pad -- a SET,
// re-derived from the world, never a flag or a remembered occupant -- adds up those
// crates' weights, compares the total with THIS plate's own MinimumHoldKg, and tells
// THIS plate's own LinkedDoor to hold or let go.
//
// Three things here are the whole task and each is easy to get subtly wrong:
//   * the load is a SUM over a SET, so taking one of two crates off does not clear it;
//   * the threshold is read off THIS plate, not off a constant or off another plate;
//   * the door driven is THIS plate's LinkedDoor, not the first door in the level.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "WeightPlateActor.generated.h"

class UStaticMeshComponent;
class UTextRenderComponent;

UCLASS()
class THIRDPERSON_API AWeightPlateActor : public AActor
{
	GENERATED_BODY()

public:
	AWeightPlateActor();

	virtual void Tick(float DeltaSeconds) override;

	/** The pad. 900 x 900 x 20 cm, THE ROOT, so the plate's position IS the pad's
	 *  position and nothing can drift between what you stand on and what weighs. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Plate")
	TObjectPtr<UStaticMeshComponent> Pad;

	/** Prints MinimumHoldKg every frame. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Plate")
	TObjectPtr<UTextRenderComponent> HoldLabel;

	/** The least this plate will hold its door open for, in kilograms. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Plate")
	float MinimumHoldKg = 30.0f;

	/** The door this plate belongs to. Set on each placed plate. */
	UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category = "Plate")
	TObjectPtr<AActor> LinkedDoor;

	/** What is resting on this pad right now, in kilograms. Recomputed each frame
	 *  from the world; nothing about it is remembered between frames. */
	UFUNCTION(BlueprintPure, Category = "Plate")
	float GetRestingLoadKg() const { return RestingLoadKg; }

private:
	float RestingLoadKg = 0.0f;
};

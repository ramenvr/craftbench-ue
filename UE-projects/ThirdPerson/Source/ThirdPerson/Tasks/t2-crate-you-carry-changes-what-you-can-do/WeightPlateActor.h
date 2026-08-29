// Copyright CraftBench. All Rights Reserved.
//
// A weight plate, and the one door it is wired to.
//
// As shipped the plate is a 900 x 900 cm pad you can walk onto, with the least it
// will hold for painted on it. It weighs nothing, decides nothing, and the door it
// points at never moves. Adding up what is resting on the pad, comparing that with
// THIS plate's own MinimumHoldKg, and driving THIS plate's own LinkedDoor is the work.
//
// LinkedDoor is set per placed instance in the yard: each plate belongs to its own
// door, and one plate must never move the other's. MinimumHoldKg, like the crates'
// weights, is set as the yard is laid out and changes again part way through.

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
	 *  position and nothing can drift between what you stand on and what weighs.
	 *  20 cm is under the character's step height, so it is walked onto, not
	 *  climbed. */
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
};

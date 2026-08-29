// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION for t1-door-stays-open-while-you-stand-on-the-plate.
//
// A pressure plate, and the door it belongs to.
//
// As shipped the plate notices what stands on it and lights its lamp, and
// nothing else happens: the door it points at never moves. Making that door be
// open while somebody stands here, and shut the rest of the time, is the work.
//
// LinkedDoor is already set on each placed plate — each plate belongs to its own
// door, and one plate must not move the other's.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ContactPlateActor.generated.h"

class UBoxComponent;
class UStaticMeshComponent;

UCLASS()
class THIRDPERSON_API AContactPlateActor : public AActor
{
	GENERATED_BODY()

public:
	AContactPlateActor();

	virtual void Tick(float DeltaSeconds) override;

	/** The 200 x 200 cm pad you can stand on. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Plate")
	TObjectPtr<UStaticMeshComponent> Pad;

	/** The region just above the pad. It reports what enters and leaves and
	 *  blocks nothing. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Plate")
	TObjectPtr<UBoxComponent> PlateVolume;

	/** Lit while something is standing on this plate. A readout for whoever is
	 *  watching; nothing reads it back. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Plate")
	TObjectPtr<UStaticMeshComponent> Lamp;

	/** The door this plate belongs to. Set on each placed plate. */
	UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category = "Plate")
	TObjectPtr<AActor> LinkedDoor;

private:
	/** Is anything standing on this plate right now. */
	bool IsOccupied() const;

	/** What was asked of the door last frame, so the plate only speaks up when
	 *  the answer changes. */
	bool bLastRequestedOpen = false;
};

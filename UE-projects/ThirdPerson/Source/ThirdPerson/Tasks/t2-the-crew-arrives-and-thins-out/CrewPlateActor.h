// Copyright CraftBench. All Rights Reserved.
//
// A floor plate for task t2-the-crew-arrives-and-thins-out.
//
// SUPPLIED AND WORKING. It notices what is standing on it and says so, and its little
// lamp rides up while somebody is there so a person watching can see it register.
// NOTHING DECIDES WHAT TO DO ABOUT THAT. The plate has never heard of a board, a
// standing spot, a hand or a badge.
//
// Each plate carries the name of the board it belongs to, and whether it is that
// board's CALL plate or its STAND-DOWN plate.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "CrewPlateActor.generated.h"

class UBoxComponent;
class UStaticMeshComponent;

UCLASS()
class THIRDPERSON_API ACrewPlateActor : public AActor
{
	GENERATED_BODY()

public:
	ACrewPlateActor();

	virtual void Tick(float DeltaSeconds) override;

	/** The region just above the pad. It reports what enters and leaves and blocks
	 *  nothing. Bind to it or ask it -- either works. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Plate")
	UBoxComponent* PlateVolume = nullptr;

	/** The 400 x 400 cm pad you can stand on. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Plate")
	UStaticMeshComponent* Pad = nullptr;

	/** Rides up while somebody is standing here. A readout for whoever is watching;
	 *  nothing reads it back. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Plate")
	UStaticMeshComponent* Lamp = nullptr;

	/** Which board this plate belongs to. Every board, standing spot and floor plate
	 *  on the deck carries the name of the board it belongs to. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Plate")
	FName BoardTag = NAME_None;

	/** True on a board's CALL plate, false on its STAND-DOWN plate. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Plate")
	bool bIsCallPlate = true;

	/** Is anybody standing on this plate right now? */
	UFUNCTION(BlueprintPure, Category = "Plate")
	bool IsSomebodyStandingHere() const;
};

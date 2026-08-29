// Copyright CraftBench. All Rights Reserved.
//
// A door that can swing about its hinge.
//
// As shipped it never moves. The panel is the part a person sees swing; the
// floating number above it prints how far that panel has turned from the pose it
// started play in, so whoever is watching can read the angle off the level.
//
// Making the door open and shut is the work. Nothing here does it.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "SwingDoorActor.generated.h"

class UStaticMeshComponent;
class UTextRenderComponent;

UCLASS()
class THIRDPERSON_API ASwingDoorActor : public AActor
{
	GENERATED_BODY()

public:
	ASwingDoorActor();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	/** The hinge. The panel sweeps about this. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Door")
	TObjectPtr<USceneComponent> Hinge;

	/** The part a person sees swing. Offset from the hinge so it sweeps clear of
	 *  the walking lane. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Door")
	TObjectPtr<UStaticMeshComponent> DoorPanel;

	/** Prints the panel's current angle from its play-start pose. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Door")
	TObjectPtr<UTextRenderComponent> AngleReadout;

private:
	/** The panel's pose when play began — what "shut" means for this door. */
	FRotator ShutRotation = FRotator::ZeroRotator;
	/** Hinge yaw at play start. */
	double ShutHingeYaw = 0.0;
};

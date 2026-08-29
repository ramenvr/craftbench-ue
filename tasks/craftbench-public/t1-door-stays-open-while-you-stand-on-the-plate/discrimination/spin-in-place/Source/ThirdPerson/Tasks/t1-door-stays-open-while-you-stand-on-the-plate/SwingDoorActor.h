// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION for t1-door-stays-open-while-you-stand-on-the-plate.
//
// One correct answer, not the only one. The prompt asks for observable behaviour
// and says nothing about how; a solution that animates the swing, drives it from
// a timeline, or puts the whole thing on the plate instead is equally correct.

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

	/** Ask the door to be open, or to be shut. Called by whatever is watching the
	 *  plate; the door itself does not care who asked or why. */
	void SetOpenRequested(bool bWantOpen);

	/** The hinge. The panel sweeps about this. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Door")
	TObjectPtr<USceneComponent> Hinge;

	/** The part a person sees swing. Offset from the hinge so it sweeps clear of
	 *  the walking lane. KEEP THIS NAME: it is what makes the visible panel the
	 *  graded part rather than whichever component happens to be biggest. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Door")
	TObjectPtr<UStaticMeshComponent> DoorPanel;

	/** Prints the panel's current angle from its play-start pose. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Door")
	TObjectPtr<UTextRenderComponent> AngleReadout;


private:
	/** The panel's pose when play began — what "shut" means for this door. */
	FRotator ShutRotation = FRotator::ZeroRotator;
	/** Hinge yaw at play start; the swing is measured from here. */
	double ShutHingeYaw = 0.0;

	bool bOpenRequested = false;
	/** VARIANT: the accumulated spin. Kept HERE because the hinge is never
	 *  moved, so reading it back gives the same value every frame. */
	double SpinYaw = 0.0;
};

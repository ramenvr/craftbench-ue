// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION for t2-crate-you-carry-changes-what-you-can-do.
//
// A door whose slab lifts straight up out of its frame. Frame is the root and never
// moves; Panel is the part a person watches rise, and the floating number above it
// prints how far that slab has risen from the pose it started play in, read off the
// slab's own live position so the readout can never disagree with what it is doing.
//
// A door is TOLD, it does not decide: SetHeldOpen is the whole of its interface, and
// nothing here knows a weight plate exists.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "LiftDoorActor.generated.h"

class USceneComponent;
class UStaticMeshComponent;
class UTextRenderComponent;

UCLASS()
class THIRDPERSON_API ALiftDoorActor : public AActor
{
	GENERATED_BODY()

public:
	ALiftDoorActor();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	/** The doorway. THE ROOT, and it does not move: the slab moves inside it. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Door")
	TObjectPtr<USceneComponent> Frame;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Door")
	TObjectPtr<UStaticMeshComponent> PostLeft;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Door")
	TObjectPtr<UStaticMeshComponent> PostRight;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Door")
	TObjectPtr<UStaticMeshComponent> Lintel;

	/** THE SLAB. 400 x 400 cm, movable, solid. This is the part that lifts. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Door")
	TObjectPtr<UStaticMeshComponent> Panel;

	/** Prints how far the slab has risen from its play-start pose, in cm. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Door")
	TObjectPtr<UTextRenderComponent> LiftLabel;

	/** Where the slab was when play began -- what "shut" means for this door. */
	UFUNCTION(BlueprintPure, Category = "Door")
	double GetShutPanelHeight() const { return ShutPanelZ; }

	/** Hold the slab up, or let it back down. Told once a frame by whichever plate
	 *  this door belongs to; harmless to be told the same thing repeatedly. */
	UFUNCTION(BlueprintCallable, Category = "Door")
	void SetHeldOpen(bool bNewHeldOpen) { bHeldOpen = bNewHeldOpen; }

	UFUNCTION(BlueprintPure, Category = "Door")
	bool IsHeldOpen() const { return bHeldOpen; }

private:
	double ShutPanelZ = 0.0;

	/** The slab's shut pose in the FRAME's own space, so the travel is unaffected
	 *  by where in the yard the door happens to stand. */
	double ShutPanelRelZ = 0.0;

	bool bHeldOpen = false;
};

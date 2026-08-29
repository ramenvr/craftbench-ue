// Copyright CraftBench. All Rights Reserved.
//
// A door whose slab lifts straight up out of its frame.
//
// As shipped the frame stands and the slab never moves. Panel is the part a person
// watches rise; the floating number above it prints how far that panel has risen
// from the pose it started play in, read off the panel's own live position so the
// readout can never disagree with what the slab is actually doing.
//
// Making the slab lift and drop is the work. Nothing here does it, and nothing here
// knows a weight plate exists -- a door is told, it does not decide.

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

	/** Where the slab was when play began -- what "shut" means for this door.
	 *  Recorded once, so a door that has been driven still knows its way home. */
	UFUNCTION(BlueprintPure, Category = "Door")
	double GetShutPanelHeight() const { return ShutPanelZ; }

private:
	double ShutPanelZ = 0.0;
};

// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION for t1-pad-throws-you-up-on-contact.
//
// This is one correct answer, not the only one. The prompt asks for observable
// behaviour and says nothing about how; a solution that polls for anything
// standing on the plate, or that drives the character up some other way, is
// equally correct and the gates are written to accept it.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ContactPadActor.generated.h"

class UBoxComponent;
class UPrimitiveComponent;
class UStaticMeshComponent;

UCLASS()
class THIRDPERSON_API AContactPadActor : public AActor
{
	GENERATED_BODY()

public:
	AContactPadActor();

	/** The visible plate, flush with the floor. 400 x 400 x 20 cm. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Pad")
	TObjectPtr<UStaticMeshComponent> Plate;

	/** The region standing on the plate. 400 x 400 x 500 cm. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Pad")
	TObjectPtr<UBoxComponent> Region;

protected:
	virtual void BeginPlay() override;

	/** Throws whatever just arrived on the pad straight up. */
	UFUNCTION()
	void OnRegionEntered(UPrimitiveComponent* OverlappedComponent,
	                     AActor* OtherActor,
	                     UPrimitiveComponent* OtherComp,
	                     int32 OtherBodyIndex,
	                     bool bFromSweep,
	                     const FHitResult& SweepResult);
};

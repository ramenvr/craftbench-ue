// Copyright CraftBench. All Rights Reserved.
//
// The rail truck for task t3-reach-the-exit-before-they-see-you.
//
// It drives itself: back and forth along its own rail, all night, at its own speed.
// Nothing here decides anything and nothing here can be told to stop.
//
// SOLID on every channel and standing from the floor to well above head height, like
// the crates and the wall -- so where it happens to be at this instant decides what is
// and is not in the way at this instant.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "StealthTruckActor.generated.h"

class UBoxComponent;
class USceneComponent;
class UStaticMeshComponent;

UCLASS()
class THIRDPERSON_API AStealthTruckActor : public AActor
{
	GENERATED_BODY()

public:
	AStealthTruckActor();

	virtual void OnConstruction(const FTransform& Transform) override;

	/** Where the truck rides. The ROOT, unscaled, and at floor level: the actor's own
	 *  location is the middle of the truck's footprint, on the floor, and moving the
	 *  actor along its rail moves everything with it. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Truck")
	USceneComponent* Anchor = nullptr;

	/** The solid box, sized directly rather than scaled. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Truck")
	UBoxComponent* Block = nullptr;

	/** The truck you can see. Follows the box exactly. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Truck")
	UStaticMeshComponent* Body = nullptr;

	/** Half the size of the truck, in centimetres, measured from its centre. It rides
	 *  ON the floor: the actor's own location is at floor level. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Truck")
	FVector TruckHalfExtentUu = FVector(600.0f, 180.0f, 220.0f);

	/** Half the rail, as an offset in centimetres from where the truck was placed. The
	 *  truck runs from (placed - this) to (placed + this) and back, for ever. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Truck")
	FVector RailHalfSpanUu = FVector(0.0f, 1800.0f, 0.0f);

	/** How fast it grinds along that rail. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Truck")
	float RailSpeedUuPerSec = 420.0f;

	/** Half the size of the truck, in centimetres. */
	UFUNCTION(BlueprintPure, Category = "Truck")
	FVector GetTruckHalfExtentUu() const { return TruckHalfExtentUu; }

	/** The two ends of the rail, in world space. Valid from the first frame of play. */
	UFUNCTION(BlueprintPure, Category = "Truck")
	FVector GetRailEndA() const { return HomeLocation - RailHalfSpanUu; }

	UFUNCTION(BlueprintPure, Category = "Truck")
	FVector GetRailEndB() const { return HomeLocation + RailHalfSpanUu; }

protected:
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

private:
	/** Where the yard put it. The middle of its rail. */
	FVector HomeLocation = FVector::ZeroVector;

	/** Which end it is currently running toward. */
	bool bHeadingToB = true;
};

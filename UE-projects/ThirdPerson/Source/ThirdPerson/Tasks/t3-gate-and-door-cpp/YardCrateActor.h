// Copyright CraftBench. All Rights Reserved.
//
// A crate on a rail, for task t3-gate-and-door-cpp.
//
// Everything the crate needs in order to SLIDE and to SAY WHAT IT IS is supplied and
// working: put your body against it and walk into it and it runs along its own rail
// toward the hard stop at that end, and the name it carries floats above it, printed
// straight off the crate itself so the two can never disagree.
//
// The rail is the crate's own forward line through the place it is standing when play
// begins. That place is one hard stop; the other is RailLengthUu further along. The
// crate never leaves the segment between them, it never changes height, and nothing
// else ever moves it. It also stops short of another crate standing in its way, so two
// crates whose rails share a stop can only take it one at a time -- shove the one that
// is home off it before the other one can have it.
//
// Nothing in here notices a pad, a door or a gate, and nothing in here decides
// anything.
//
// CrateName is this crate's own name, set as the yard is laid out. Keep it as a
// property with this name and this type.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "YardCrateActor.generated.h"

class USceneComponent;
class UStaticMeshComponent;
class UTextRenderComponent;

UCLASS()
class THIRDPERSON_API AYardCrateActor : public AActor
{
	GENERATED_BODY()

public:
	AYardCrateActor();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	/** Root, at floor level in the middle of the crate's footprint. Everything else
	 *  hangs off it unscaled, so every relative number below is in world units. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Crate")
	USceneComponent* Mount = nullptr;

	/** The 120 x 120 x 120 cm box. Solid: you shove it with your body, and it stops
	 *  you the way any other solid thing would. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Crate")
	UStaticMeshComponent* Crate = nullptr;

	/** Prints this crate's own name above it. Nothing reads it back. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Crate")
	UTextRenderComponent* NamePlate = nullptr;

	/** The name written on this crate. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Crate")
	FName CrateName;

	/** How far apart this crate's two hard stops are, along its own rail. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Crate")
	float RailLengthUu = 900.0f;

	/** How fast the crate runs along its rail while somebody is shoving it. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Crate")
	float ShoveSpeedUu = 220.0f;

	/** How close somebody has to be, measured flat, before their walking counts as a
	 *  shove on this crate. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Crate")
	float ShoveReachUu = 165.0f;

	/** Where the crate was standing when play began -- one of its two hard stops. */
	UFUNCTION(BlueprintPure, Category = "Crate")
	FVector GetRailAnchor() const { return RailAnchor; }

	/** The rail's bearing, flat and unit length, pointing from the anchor stop toward
	 *  the other one. */
	UFUNCTION(BlueprintPure, Category = "Crate")
	FVector GetRailAxis() const { return RailAxis; }

	/** How far along the rail the crate is standing right now, measured from the
	 *  anchor stop. Read off the crate's live position, never off a stored number. */
	UFUNCTION(BlueprintPure, Category = "Crate")
	float GetRailParamUu() const;

private:
	/** Set once, when play begins, off the crate's own starting pose. */
	FVector RailAnchor = FVector::ZeroVector;
	FVector RailAxis = FVector::ForwardVector;

	/** What the name plate is currently showing, so it is only rewritten when the
	 *  name it is printing has actually changed. */
	FName ShownName;
};

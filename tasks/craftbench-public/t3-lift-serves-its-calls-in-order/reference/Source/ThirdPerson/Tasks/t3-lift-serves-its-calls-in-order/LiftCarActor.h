// Copyright CraftBench. All Rights Reserved.
//
// The lift car for task t3-lift-serves-its-calls-in-order. Everything the car needs to
// DO its job is supplied and working: a floor you can stand on, a pair of sliding door
// leaves with the mechanism that slides them, three pads with three lamps, and the three
// numbers the car is built to. Nothing decides WHEN to use any of it. That decision --
// which floors are outstanding, which one to serve next, when to open, how long to hold,
// when to move and how far -- is the whole job.
//
// THREE THINGS ABOUT THIS FILE THAT ARE LOAD-BEARING, BECAUSE THE VERIFIER READS THEM:
//
//  1. Platform is the ROOT. A character standing on it is carried when the actor moves,
//     because UCharacterMovementComponent::UpdateBasedMovement applies the base's
//     TRANSFORM DELTA to whoever stands on it -- and only for a MOVABLE base
//     (MovementBaseUtility::IsDynamicBase -> IsPhysicsOwnerMovable, Character.cpp:814).
//     Platform therefore ships Movable + BlockAll, and it is the root so that moving the
//     ACTOR moves the floor the rider is standing on.
//  2. GetSillHeight() is the top of Platform's world bounds. The verifier computes the
//     car's sill the same way from the same component, so "level with the landing" means
//     exactly one thing to both of us and the two cannot drift apart.
//  3. AdvanceDoors() is the supplied door mechanism and it is driven from Tick(). If you
//     rewrite Tick, KEEP THAT CALL -- otherwise the leaves never move, the open fraction
//     never leaves 0, and nothing you write afterwards can ever be seen.

#pragma once

#include "CoreMinimal.h"
#include "Engine/HitResult.h"
#include "GameFramework/Actor.h"
#include "LiftCarActor.generated.h"

class ALiftLandingActor;
class UBoxComponent;
class UPointLightComponent;
class UStaticMeshComponent;
class UTextRenderComponent;

UCLASS()
class THIRDPERSON_API ALiftCarActor : public AActor
{
	GENERATED_BODY()

public:
	ALiftCarActor();

	// --------------------------------------------------------------- the car, as built

	/** THE ROOT and the floor you stand on: 700 x 700, Movable, BlockAll. IT IS SCALED
	 *  (7, 7, 0.2 off the 100 uu engine cube), and every component parented to it
	 *  inherits that scale -- offsets AND extents alike. Anything you attach here should
	 *  divide it back out; see the top of LiftCarActor.cpp. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Lift|Car")
	UStaticMeshComponent* Platform = nullptr;

	/** Roof. Decorative. NoCollision on purpose: nothing about this car may trap or jam
	 *  the character, so Platform is the only part that blocks. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Lift|Car")
	UStaticMeshComponent* Cage = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Lift|Car")
	UStaticMeshComponent* WallBack = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Lift|Car")
	UStaticMeshComponent* WallLeft = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Lift|Car")
	UStaticMeshComponent* WallRight = nullptr;

	/** The two leaves. They slide apart along the car's Y and they collide with nothing,
	 *  so a closing door can never shut on anybody. Their SEPARATION is what "the doors
	 *  are open" means -- see GetDoorOpenFraction(). */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Lift|Doors")
	UStaticMeshComponent* DoorLeftLeaf = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Lift|Doors")
	UStaticMeshComponent* DoorRightLeaf = nullptr;

	/** The three pads inside the car, one per landing. The volumes exist and they
	 *  generate overlap events. NOTHING IS BOUND TO THEM. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Lift|Pads")
	UBoxComponent* Pad1 = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Lift|Pads")
	UBoxComponent* Pad2 = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Lift|Pads")
	UBoxComponent* Pad3 = nullptr;

	/** The lamps over the three pads. These are the VISIBLE face of a latched call and
	 *  they are what a reviewer -- and the verifier -- reads. A flag saying the car
	 *  noticed you is not a lamp. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Lift|Pads")
	UPointLightComponent* PadLamp1 = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Lift|Pads")
	UPointLightComponent* PadLamp2 = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Lift|Pads")
	UPointLightComponent* PadLamp3 = nullptr;

	/** The three numbers below, painted on the inside of the back wall so a human can
	 *  read them off the car. Written in BeginPlay from the properties. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Lift|Car")
	UTextRenderComponent* NumbersReadout = nullptr;

	// ------------------------------------------ the three numbers written on THIS car

	/** How fast this car travels. The same speed up or down, near or far. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Lift|Numbers")
	float TravelSpeedUuPerSecond = 200.0f;

	/** How long the leaves take to go all the way open, or all the way shut. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Lift|Numbers")
	float DoorTravelSeconds = 2.0f;

	/** How long the doors must stay ALL the way open once they get there. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Lift|Numbers")
	float DoorHoldSeconds = 3.0f;

	/** The leaves' Y separation when shut and when fully open. The open fraction IS
	 *  (measured separation - shut) / (open - shut), so it is a measurement of where the
	 *  doors ARE and not a flag anybody can set. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Lift|Doors")
	float DoorShutSeparationUu = 140.0f;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Lift|Doors")
	float DoorOpenSeparationUu = 320.0f;

	// ------------------------------------------------------------ the supplied switches

	/** Tell the doors to go open. They take DoorTravelSeconds to get there. */
	UFUNCTION(BlueprintCallable, Category = "Lift|Doors")
	void OpenDoors();

	/** Tell the doors to go shut. They take DoorTravelSeconds to get there. */
	UFUNCTION(BlueprintCallable, Category = "Lift|Doors")
	void CloseDoors();

	/** 0 = shut, 1 = all the way open, measured from where the leaves actually are.
	 *  EXACTLY 0.0f and EXACTLY 1.0f at the two ends -- this function snaps them -- so
	 *  `>= 1.0f` and `<= 0.0f` are safe tests and are the intended ones. The snap is
	 *  done here rather than left to the leaves landing perfectly, because the engine is
	 *  entitled to drop the last sliver of the door's travel; the comment beside
	 *  kLeafEndSlackUu in LiftCarActor.cpp has the measurement. */
	UFUNCTION(BlueprintPure, Category = "Lift|Doors")
	float GetDoorOpenFraction() const;

	/** What the doors were last TOLD to do. Not where they are. */
	UFUNCTION(BlueprintPure, Category = "Lift|Doors")
	bool AreDoorsCommandedOpen() const { return bCommandedOpen; }

	/** Light or clear the in-car pad for a floor. FloorNumber is 1..3. */
	UFUNCTION(BlueprintCallable, Category = "Lift|Pads")
	void SetPadLit(int32 FloorNumber, bool bLit);

	UFUNCTION(BlueprintPure, Category = "Lift|Pads")
	bool IsPadLit(int32 FloorNumber) const;

	/** The in-car pad volume for a floor, so you can bind to it. 1..3; null otherwise. */
	UFUNCTION(BlueprintPure, Category = "Lift|Pads")
	UBoxComponent* GetPad(int32 FloorNumber) const;

	/** World Z of the TOP of Platform -- the surface somebody in the car is standing on.
	 *  This is what "level with a landing" is measured between. */
	UFUNCTION(BlueprintPure, Category = "Lift|Car")
	float GetSillHeight() const;

	virtual void Tick(float DeltaSeconds) override;

protected:
	virtual void BeginPlay() override;

	/** THE SUPPLIED DOOR MECHANISM. Slides both leaves toward the commanded state at
	 *  DoorTravelSeconds and snaps hard to the two ends. Called from Tick -- keep that
	 *  call there. */
	void AdvanceDoors(float DeltaSeconds);

private:
	/** What OpenDoors/CloseDoors last asked for. */
	bool bCommandedOpen = false;

	/** 0..1, how far the leaves have got. Nothing outside AdvanceDoors reads it; the
	 *  open fraction is always re-measured off the leaves themselves. */
	float DoorPhase = 0.0f;

	void ApplyDoorLeaves();
	UPointLightComponent* GetPadLamp(int32 FloorNumber) const;

	// =================================================================================
	// REFERENCE SOLUTION. Everything above this line ships with the task; everything
	// below it is the answer.
	//
	// The car owns the whole lift: it finds the landings at play, binds all six pads,
	// latches every press whatever it happens to be doing, serves the latched set in
	// collective order, drives itself at the speed written on it, and keeps all three
	// signs on the floor it is nearest and the way it is about to go.
	// =================================================================================

	/** Open/hold/close are STATES, not an animation, because the interlock is the
	 *  point: the car may only move in Travelling, and Travelling is only entered from
	 *  a shut door. */
	enum class EPhase : uint8
	{
		Idle,
		Opening,
		Holding,
		Closing,
		Travelling
	};

	/** One handler for all six pads -- the three in the car and the three on the
	 *  landings. It never asks what the lift is doing. */
	UFUNCTION()
	void OnPadTouched(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor,
		UPrimitiveComponent* OtherComp, int32 OtherBodyIndex, bool bFromSweep,
		const FHitResult& SweepResult);

	void CollectLandings();
	void Latch(int32 Floor);
	/** Discharge the call for the floor the scheduler COMMITTED to open at. Takes no
	 *  sill, on purpose: which floor this opening is for was decided when the car
	 *  chose to open, and working it out a second time here from the sill would be the
	 *  same fact derived twice from two different inputs. */
	void ServeHere();
	/** THE ONLY THING THAT WRITES A LAMP. All six lamps are re-asserted from Calls
	 *  every frame, so no lamp can ever be left where an edge happened to leave it. */
	void RefreshLamps();
	/** The next stop WITHOUT committing to it, so the sign and the scheduler cannot
	 *  drift apart. Returns 0 for "nothing left to serve". */
	int32 PeekNextStop(float Sill, int32& OutDirection) const;
	/** The next stop, committing the service direction. */
	int32 ChooseNextStop(float Sill);
	int32 FloorAtSill(float Sill) const;
	/** Asked at the moment of use, every time. Landing heights are not constants.
	 *  A floor with no landing answers "where the car already is", which makes it
	 *  un-chooseable rather than a place to teleport to. */
	float SillOfFloor(int32 Floor) const;
	void UpdateSigns(float Sill);

	UPROPERTY()
	TArray<ALiftLandingActor*> Landings;

	/** The latched call set. A press adds to it; only an opening at that floor removes
	 *  it. Nothing else clears it, and nothing refuses to add to it. THIS IS THE ONE
	 *  PLACE A CALL LIVES: the six lamps are a view of it, not a second copy. */
	TSet<int32> Calls;

	EPhase Phase = EPhase::Idle;
	/** The floor this opening is for -- set on every one of the three routes into
	 *  Opening, cleared when the call is discharged. */
	int32 ServingFloor = 0;
	/** +1 up, -1 down, 0 nothing to serve. This is what makes the lift a lift. */
	int32 ServiceDirection = 0;
	float HoldTimer = 0.0f;

	int32 LastShownFloor = -1;
	int32 LastShownDirection = -99;
};

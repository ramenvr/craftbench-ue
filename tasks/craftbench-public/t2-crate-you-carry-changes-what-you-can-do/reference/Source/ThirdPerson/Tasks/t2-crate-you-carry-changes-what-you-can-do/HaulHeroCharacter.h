// Copyright CraftBench. All Rights Reserved.
//
// REFERENCE SOLUTION for t2-crate-you-carry-changes-what-you-can-do.
//
// The whole carry state machine lives here because this is the class the yard
// places and the player possesses. Five channels are driven off ONE piece of
// state -- whether a crate is being carried:
//   1. where the crate is, every frame, by a SWEPT move so the world still stops it;
//   2. the crate and this character ignoring each other while held, both ways,
//      so the thing being carried never becomes the thing blocking the carrier;
//   3. top ground speed, halved while carrying and put back on release;
//   4. jumping, off while carrying and back on release -- below the input layer,
//      so it holds however the jump is asked for;
//   5. picking up and setting down, each with the one guard that stops the two
//      rules chasing each other every frame.

#pragma once

#include "CoreMinimal.h"
#include "ThirdPersonCharacter.h"
#include "HaulHeroCharacter.generated.h"

class AActor;

UCLASS()
class THIRDPERSON_API AHaulHeroCharacter : public AThirdPersonCharacter
{
	GENERATED_BODY()

public:
	AHaulHeroCharacter();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	/** What is riding in front of us, or null. */
	UFUNCTION(BlueprintPure, Category = "Haul")
	AActor* GetCarriedCrate() const { return Carried.Get(); }

protected:
	/** Jumping is refused at the CHARACTER's own gate rather than at the key, so
	 *  it holds whatever asks -- the keyboard, a script, anything. The empty-handed
	 *  half is just as load-bearing: forget it and the character can never jump
	 *  again after its first haul. */
	virtual bool CanJumpInternal_Implementation() const override;

private:
	void TryPickUp(double Now);
	void SetDown(double Now);
	void CarryTick();

	/** The pad box of the plate the character is standing on, or null. Uses the
	 *  plate's COLLIDING bounds, which is the pad and nothing else -- the same
	 *  measurement the yard's own rule is written in. */
	AActor* PlateUnderfoot() const;

	TWeakObjectPtr<AActor> Carried;

	/** This character's own top ground speed, taken once before anything has had a
	 *  chance to change it. Restoring to a written-down number instead would be
	 *  wrong for any character but this one. */
	float FreeWalkSpeed = 0.0f;

	/** The yard floor, measured once from where the crates stand. Solved rather than
	 *  assumed: the character's own capsule bottom is NOT the floor -- measured
	 *  2026-08-20 it sits 31 cm below the crates' underside, which is what made a
	 *  carry aimed at "150 above my feet" arrive 119 above the floor. */
	float YardFloorZ = 0.0f;
	bool bYardFloorMeasured = false;

	/** World time of the last set-down. A crate put down in front of you is inside
	 *  no pick-up radius worth having, but the wait makes the two rules provably
	 *  unable to chase each other. */
	double ReleasedAt = -1000.0;

	/** World time the character last began standing still on a plate; negative
	 *  when it is not standing still on one. */
	double StillOnPlateSince = -1.0;
};

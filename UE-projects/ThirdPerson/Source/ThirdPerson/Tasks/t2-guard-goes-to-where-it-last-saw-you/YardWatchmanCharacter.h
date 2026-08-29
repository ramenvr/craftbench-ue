// Copyright CraftBench. All Rights Reserved.
//
// A watchman for task t2-guard-goes-to-where-it-last-saw-you. Three things it already
// owns and that work: EYES (CanSeeActor), FEET (WalkToSpot / StandStill /
// HasArrivedAtSpot) and a POST (PostLocation, latched from where the yard placed it).
//
// What it does not own is any idea of what to do with them. There is no state, no
// timer, no memory of where anybody was, no reference to the character, no reference
// to the other watchman, and no way for one watchman to tell the other anything. Tick
// walks toward a goal if one has been set and does nothing else.
//
// The yard holds two of these and they are both PLACED INSTANCES in a map that cannot
// be edited, so a subclass would never be constructed: the work has to land on this
// class.
//
// WHY IT IS A CHARACTER AND WHY IT AUTO-POSSESSES. UCharacterMovementComponent only
// runs ControlledCharacterMove when the character IsLocallyControlled() (or has no
// controller AND bRunPhysicsWithNoController) -- CharacterMovementComponent.cpp:1749.
// An unpossessed placed ACharacter is therefore inert: AddMovementInput would be
// accepted and silently discarded. EAutoPossessAI::PlacedInWorldOrSpawned makes
// APawn::PostInitializeComponents spawn the engine's default AAIController
// (Pawn.cpp:134-162, AIControllerClassName=/Script/AIModule.AIController,
// BaseEngine.ini:142), which in a standalone PIE world is a local controller
// (Controller.cpp:94), so the movement component runs. AAIController's constructor
// creates only an optional UPathFollowingComponent and sets bStartAILogicOnPossess
// false (AIController.cpp:39-55) -- no navigation system, no navmesh, nothing is
// asked of it, and nothing here ever calls MoveTo.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "YardWatchmanCharacter.generated.h"

UCLASS()
class THIRDPERSON_API AYardWatchmanCharacter : public ACharacter
{
	GENERATED_BODY()

public:
	AYardWatchmanCharacter();

	/** How fast this watchman walks, in uu per second. The yard sets it on the placed
	 *  instance; read it, do not change it. Mirrored into the movement component so
	 *  the number on the watchman and the speed it actually walks are the same thing. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Watchman")
	float WalkPaceUuPerSecond = 300.0f;

	/** How far this watchman can see, in uu. The yard sets it on the placed instance;
	 *  read it, do not change it. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Watchman")
	float SightRangeUu = 2000.0f;

	/** Where this watchman was standing when the yard opened, latched in BeginPlay. */
	UPROPERTY(BlueprintReadOnly, Category = "Watchman")
	FVector PostLocation = FVector::ZeroVector;

	/** THE EYES. True when an unobstructed straight line runs from this watchman's
	 *  chest to the other actor's, and the other actor is no further away than
	 *  SightRangeUu. Truthful, cheap, and safe to call every frame. */
	UFUNCTION(BlueprintPure, Category = "Watchman")
	bool CanSeeActor(const AActor* Other) const;

	/** THE FEET. Walk to a spot in the yard, under this watchman's own power, at its
	 *  own pace, stopping when it gets there. Calling it again re-aims. */
	UFUNCTION(BlueprintCallable, Category = "Watchman")
	void WalkToSpot(const FVector& Spot);

	/** Stand where you are. */
	UFUNCTION(BlueprintCallable, Category = "Watchman")
	void StandStill();

	/** True when there is a goal and this watchman is standing on it. */
	UFUNCTION(BlueprintPure, Category = "Watchman")
	bool HasArrivedAtSpot() const;

	/** The goal WalkToSpot was last given. Only meaningful while HasGoal(). */
	UFUNCTION(BlueprintPure, Category = "Watchman")
	FVector GetGoalSpot() const { return GoalSpot; }

	UFUNCTION(BlueprintPure, Category = "Watchman")
	bool HasGoal() const { return bHasGoal; }

protected:
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	/** How close counts as standing on the goal. The feet stop here rather than
	 *  grinding into it, which is also what keeps two watchmen converging on one spot
	 *  from shoving each other or the character. */
	static constexpr float StandOffUu = 150.0f;

private:
	bool bHasGoal = false;
	FVector GoalSpot = FVector::ZeroVector;
};

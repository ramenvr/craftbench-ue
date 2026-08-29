// Copyright CraftBench. All Rights Reserved.
//
// A watchman for task t2-guard-goes-to-where-it-last-saw-you. Three things it already
// owns and that work: EYES (CanSeeActor), FEET (WalkToSpot / StandStill /
// HasArrivedAtSpot) and a POST (PostLocation, latched from where the yard placed it).
//
// REFERENCE SOLUTION. The eyes, feet and post below are exactly as supplied; what has
// been added is the decision -- a four-state machine driven by the sight true->false
// EDGE, a radio that carries a PLACE, and a give-up timer that starts on ARRIVAL.
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

	/** THE RADIO. One watchman calls this on the other the moment it loses sight, and
	 *  what it hands over is a PLACE. Not the character (the receiver never saw them
	 *  and must not resolve a live transform), and not the caller's own position (which
	 *  by then is a long way back from where the character actually was). */
	UFUNCTION(BlueprintCallable, Category = "Watchman")
	void ReportLastSeen(const FVector& Spot);

protected:
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	/** How close counts as standing on the goal. The feet stop here rather than
	 *  grinding into it, which is also what keeps two watchmen converging on one spot
	 *  from shoving each other or the character. */
	static constexpr float StandOffUu = 150.0f;

	/** How long to stand at the last-seen spot before giving up, in seconds. The clock
	 *  starts when the watchman ARRIVES, not when the alert was raised: the walk there
	 *  takes longer than this, so a timer started on the alert has already expired by
	 *  the time the watchman gets anywhere. */
	static constexpr double SearchSeconds = 6.0;

private:
	enum class EWatch : uint8
	{
		OnPost,        // nothing has happened; stand still
		Closing,       // I can see them; go after them
		GoingToSpot,   // I cannot see them; walk to where they were last seen
		Searching,     // standing on that spot, counting down
		GoingHome      // gave up; walk back to my post
	};

	/** Resolves the character the player controls, once, and caches it. */
	AActor* FindQuarry();

	/** Hand a PLACE to every other watchman in the yard. */
	void TellTheOthers(const FVector& Spot);

	EWatch State = EWatch::OnPost;

	/** Whether the eyes reported true on the previous frame. The whole task hangs off
	 *  the true->false EDGE of this, not off its value. */
	bool bCouldSeeLastFrame = false;

	/** Refreshed EVERY frame the character is in sight, so on the frame sight is lost
	 *  it already holds where they were on the last frame that could still see them.
	 *  Writing it only inside an "acquired" branch would store where they were FIRST
	 *  spotted, which in this yard is thousands of uu away. */
	FVector LastSeenSpot = FVector::ZeroVector;
	bool bHasLastSeenSpot = false;

	/** World game-time the search began, or < 0 while not searching. */
	double SearchStartedAt = -1.0;

	TWeakObjectPtr<AActor> Quarry;

	bool bHasGoal = false;
	FVector GoalSpot = FVector::ZeroVector;
};
